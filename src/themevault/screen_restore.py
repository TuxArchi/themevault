"""Restaurar una pantalla concreta sobre otra (KDE Plasma).

Aplica la mezcla de `plasma_layout.merge()` sobre el appletsrc vivo, con
respaldo `.bak`, restauración del fondo de esa pantalla y reinicio de
plasmashell con rollback automático si no vuelve a levantar.
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

from . import plasma_layout
from .model import Manifest
from .store import BlobStore
from .util import child_env, run, xdg_config_home, xdg_data_home


def _item_text(manifest: Manifest, store: BlobStore, suffix: str) -> str:
    for item in manifest.items:
        if (item.source or "").endswith(suffix) and item.blob:
            try:
                return store.read(item.blob).decode("utf-8", "replace")
            except OSError:
                return ""
    return ""


def _appletsrc_item(manifest: Manifest):
    return next(
        (
            item
            for item in manifest.items
            if (item.source or "").endswith(plasma_layout.APPLETSRC) and item.blob
        ),
        None,
    )


def live_path() -> Path:
    return xdg_config_home() / plasma_layout.APPLETSRC


def _restart_plasma() -> str:
    """Reinicia plasmashell. Devuelve el mecanismo usado."""
    probe = run(["systemctl", "--user", "is-active", "plasma-plasmashell"], timeout=10)
    if probe is not None and probe.stdout.decode("utf-8", "replace").strip() == "active":
        run(["systemctl", "--user", "restart", "plasma-plasmashell"], timeout=40)
        return "systemctl"

    run(["kquitapp6", "plasmashell"], timeout=15)
    time.sleep(0.4)
    try:
        subprocess.Popen(
            ["plasmashell", "--replace"],
            env=child_env(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError:
        return ""
    return "plasmashell"


def _alive() -> bool:
    probe = run(["pgrep", "-x", "plasmashell"], timeout=10)
    return probe is not None and probe.returncode == 0


def _write_atomic(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + ".themevault.tmp")
    tmp.write_text(text)
    os.replace(tmp, path)


def apply(
    manifest: Manifest,
    store: BlobStore,
    mapping: dict[int, int],
    *,
    restart: bool = True,
) -> dict:
    if not mapping:
        raise RuntimeError("no elegiste ninguna pantalla para restaurar")

    item = _appletsrc_item(manifest)
    if item is None:
        raise RuntimeError("la copia no incluye el layout de Plasma")

    saved_text = store.read(item.blob).decode("utf-8", "replace")
    destination = live_path()
    if not destination.is_file():
        raise RuntimeError(f"no se encontro el layout actual en {destination}")

    live_text = destination.read_text(errors="replace")
    merged, report = plasma_layout.merge(saved_text, live_text, mapping)

    # geometria del panel: grosor, flotante y modo de ocultado viven aparte
    shell_saved = _item_text(manifest, store, "plasmashellrc")
    shell_path = xdg_config_home() / "plasmashellrc"
    shell_backup = shell_path.with_suffix(".themevault.bak")
    merged_shell = ""
    if shell_path.is_file():
        live_shell = shell_path.read_text(errors="replace")
        merged_shell = plasma_layout.merge_shellrc(
            shell_saved, live_shell, report.cid_map, report.replaced
        )
        _write_atomic(shell_backup, live_shell)

    # fondos: copiar el archivo del respaldo y apuntar el containment
    wallpapers = []
    for source, target in mapping.items():
        entry = next(
            (s for s in manifest.preview.get("screens", []) if s.get("index") == source), None
        )
        if not entry or not entry.get("wallpaper"):
            continue
        name = entry.get("wallpaper_name") or f"themevault-screen-{source}.png"
        folder = xdg_data_home() / "wallpapers" / "themevault"
        folder.mkdir(parents=True, exist_ok=True)
        target_file = folder / name
        try:
            target_file.write_bytes(store.read(entry["wallpaper"]))
        except OSError:
            report.warnings.append(f"no se pudo restaurar el fondo de la pantalla {source}")
            continue
        merged = plasma_layout.rewrite_wallpaper(merged, target, target_file.as_uri())
        wallpapers.append(str(target_file))

    backup_file = destination.with_suffix(".themevault.bak")
    _write_atomic(backup_file, live_text)
    _write_atomic(destination, merged)
    if merged_shell:
        _write_atomic(shell_path, merged_shell)

    mechanism = ""
    if restart:
        mechanism = _restart_plasma()
        time.sleep(2.0)
        if mechanism and not _alive():
            _write_atomic(destination, live_text)
            _restart_plasma()
            raise RuntimeError(
                "plasmashell no volvio a iniciar; se restauro el layout anterior"
            )

    return {
        "screens": len(mapping),
        "replaced": report.replaced,
        "added": report.added,
        "wallpapers": wallpapers,
        "warnings": report.warnings,
        "backup": str(backup_file),
        "restarted": bool(mechanism),
    }


def revert() -> bool:
    """Vuelve al layout previo guardado en el .bak."""
    destination = live_path()
    backup_file = destination.with_suffix(".themevault.bak")
    if not backup_file.is_file():
        return False
    _write_atomic(destination, backup_file.read_text(errors="replace"))

    shell_path = xdg_config_home() / "plasmashellrc"
    shell_backup = shell_path.with_suffix(".themevault.bak")
    if shell_backup.is_file():
        _write_atomic(shell_path, shell_backup.read_text(errors="replace"))

    _restart_plasma()
    return True
