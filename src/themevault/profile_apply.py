"""Aplicación de un perfil de comunidad completo."""

from __future__ import annotations

import shutil
import tarfile
import zipfile
from pathlib import Path

from .backup import BackupEngine
from .profile import Profile, to_manifest
from .restore import apply_plan, build_plan
from .util import expand, home, is_within, run, which
from . import wallpaper_apply


def _safe_extract(archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    if archive.suffix.lower() == ".zip":
        with zipfile.ZipFile(archive) as zipped:
            for member in zipped.infolist():
                target = destination / member.filename
                try:
                    target.resolve().relative_to(destination.resolve())
                except ValueError as exc:
                    raise RuntimeError("el plugin contiene una ruta fuera del destino") from exc
                if member.external_attr & 0o170000 == 0o120000:
                    raise RuntimeError("el plugin contiene enlaces no permitidos")
            zipped.extractall(destination)
        return

    with tarfile.open(archive, "r:gz") as tar:
        members = tar.getmembers()
        for member in members:
            target = destination / member.name
            try:
                target.resolve().relative_to(destination.resolve())
            except ValueError as exc:
                raise RuntimeError("el plugin contiene una ruta fuera del destino") from exc
            if member.issym() or member.islnk():
                raise RuntimeError("el plugin contiene enlaces no permitidos")
        if hasattr(tarfile, "data_filter"):
            tar.extractall(destination, members=members, filter="data")
        else:
            tar.extractall(destination, members=members)


def install_plugin(plugin: dict, bundle_dir: Path) -> None:
    file = Path(bundle_dir) / str(plugin.get("file", ""))
    target = expand(str(plugin.get("target", "")))
    if not file.is_file():
        raise RuntimeError("falta el archivo del plugin")
    if not str(target).startswith(str(home())) or not is_within(target, home()):
        raise RuntimeError("destino de plugin fuera del home")
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = target.parent / f".themevault-plugin-{target.name}"
    previous = target.parent / f".themevault-plugin-old-{target.name}"
    if staging.exists():
        shutil.rmtree(staging)
    _safe_extract(file, staging)
    extracted = staging / target.name
    if not extracted.is_dir():
        children = [child for child in staging.iterdir() if child.is_dir()]
        if len(children) == 1:
            extracted = children[0]
        else:
            shutil.rmtree(staging, ignore_errors=True)
            raise RuntimeError("el plugin no tiene un directorio raíz esperado")
    try:
        if previous.exists():
            shutil.rmtree(previous)
        if target.exists() or target.is_symlink():
            target.rename(previous)
        extracted.rename(target)
    except BaseException:
        if not target.exists() and previous.exists():
            previous.rename(target)
        raise
    finally:
        shutil.rmtree(staging, ignore_errors=True)
        if previous.exists() and target.exists():
            shutil.rmtree(previous, ignore_errors=True)


def _gsettings(schema: str, key: str, value: str) -> bool:
    if not value or which("gsettings") is None:
        return False
    proc = run(["gsettings", "set", schema, key, value], timeout=20)
    return proc is not None and proc.returncode == 0


def apply_appearance(profile: Profile) -> int:
    appearance = profile.appearance or {}
    applied = 0
    schemas = {
        "gnome": [
            ("org.gnome.desktop.interface", "icon-theme", "icon_theme"),
            ("org.gnome.desktop.interface", "cursor-theme", "cursor_theme"),
            ("org.gnome.desktop.interface", "gtk-theme", "gtk_theme"),
        ],
        "budgie": [
            ("org.gnome.desktop.interface", "icon-theme", "icon_theme"),
            ("org.gnome.desktop.interface", "cursor-theme", "cursor_theme"),
            ("org.gnome.desktop.interface", "gtk-theme", "gtk_theme"),
        ],
        "cinnamon": [
            ("org.cinnamon.desktop.interface", "icon-theme", "icon_theme"),
            ("org.cinnamon.desktop.interface", "cursor-theme", "cursor_theme"),
            ("org.cinnamon.desktop.interface", "gtk-theme", "gtk_theme"),
        ],
        "mate": [
            ("org.mate.interface", "icon-theme", "icon_theme"),
            ("org.mate.interface", "gtk-theme", "gtk_theme"),
            ("org.mate.peripherals-mouse", "cursor-theme", "cursor_theme"),
        ],
    }.get(profile.desktop, [])
    for schema, key, field in schemas:
        if _gsettings(schema, key, str(appearance.get(field, ""))):
            applied += 1
    return applied


def apply_profile(
    profile: Profile,
    bundle_dir: Path,
    *,
    engine_root: Path | None = None,
    safety: bool = True,
    apply_wallpaper: bool = True,
    install_plugins: bool = True,
    apply_settings: bool = True,
) -> dict:
    report = {
        "id": profile.id,
        "applied": 0,
        "failures": [],
        "plugins": [],
        "assets": [],
        "wallpaper": {},
        "appearance": 0,
        "manual": {
            "keybinds": len(profile.keybinds),
            "layout": 1 if (profile.layout or {}).get("containers") else 0,
        },
        "safety": "",
        "safetyError": "",
    }

    if safety:
        try:
            engine = BackupEngine(engine_root)
            snapshot = engine.create(
                label="Punto de retorno (perfil comunidad)",
                notes=f"Antes de aplicar {profile.id}",
                preview=False,
            )
            report["safety"] = snapshot.id
        except Exception as exc:
            report["safetyError"] = str(exc)

    if apply_settings:
        manifest = to_manifest(profile)
        actions = build_plan(manifest, None)
        result = apply_plan(actions, None, safety=False)
        report["applied"] += result.applied
        report["failures"].extend([[name, message] for name, message in result.failures])

    if install_plugins:
        for plugin in profile.plugins:
            try:
                install_plugin(plugin, Path(bundle_dir))
                report["plugins"].append(plugin.get("id", ""))
                report["applied"] += 1
            except Exception as exc:
                report["failures"].append([plugin.get("id", "plugin"), str(exc)])

    if install_plugins:
        for asset in profile.assets:
            if not asset.get("file"):
                continue
            try:
                install_plugin(asset, Path(bundle_dir))
                report["assets"].append(asset.get("name", ""))
                report["applied"] += 1
            except Exception as exc:
                report["failures"].append(
                    [f"asset:{asset.get('name', '?')}", str(exc)]
                )

    if apply_wallpaper and profile.wallpaper:
        try:
            result = wallpaper_apply.apply(
                profile.wallpaper,
                Path(bundle_dir),
                profile_id=profile.id,
                desktop=profile.desktop,
            )
            report["wallpaper"] = result
            if result.get("applied"):
                report["applied"] += 1
        except Exception as exc:
            report["failures"].append(["wallpaper", str(exc)])

    if apply_settings:
        report["appearance"] = apply_appearance(profile)

    return report
