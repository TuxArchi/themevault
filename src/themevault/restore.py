"""Motor de restauracion: plan -> revision -> aplicar -> rollback.

Reglas de oro:
  * primero se muestra el plan (dry-run) y recien despues se aplica
  * antes de tocar nada se crea una copia del estado actual (rollback)
  * nunca se escribe fuera de $HOME: /usr/share solo se referencia
"""

from __future__ import annotations

import configparser
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from .backup import BackupEngine
from .detect import scan_system_assets
from .drivers import dconf_available, dconf_load, set_prop, xfconf_available
from .model import KIND_DCONF, KIND_FILE, KIND_SETTING, KIND_TREE, Item, Manifest
from .store import BlobStore
from .util import from_portable, home, is_within, run, which, xdg_config_home

OK = "ok"
WARN = "warn"
BLOCKED = "blocked"


@dataclass
class Action:
    item: Item
    status: str = OK
    message: str = ""


@dataclass
class RestoreReport:
    actions: list[Action] = field(default_factory=list)
    applied: int = 0
    failures: list[tuple[str, str]] = field(default_factory=list)
    safety_id: str | None = None
    safety_error: str | None = None
    missing_assets: list[str] = field(default_factory=list)

    @property
    def blocked(self) -> list[Action]:
        return [a for a in self.actions if a.status == BLOCKED]

    @property
    def warnings(self) -> list[Action]:
        return [a for a in self.actions if a.status == WARN]

    @property
    def ok(self) -> bool:
        return not self.failures and not self.blocked


# ------------------------------------------------------------------------ plan


def _check_item(item: Item, store: BlobStore | None) -> Action:
    action = Action(item)

    if item.kind == KIND_DCONF and not dconf_available():
        action.status = BLOCKED
        action.message = "dconf no esta instalado en este sistema"
        return action
    if item.kind == KIND_SETTING:
        if item.backend == "xfconf" and not xfconf_available():
            action.status = BLOCKED
            action.message = "xfconf-query no esta instalado en este sistema"
            return action
        if item.backend == "dconf" and not dconf_available():
            action.status = BLOCKED
            action.message = "dconf no esta instalado en este sistema"
            return action
        if item.backend not in ("xfconf", "dconf", "ini"):
            action.status = BLOCKED
            action.message = f"backend desconocido: {item.backend}"
            return action

    if item.kind in (KIND_FILE, KIND_TREE):
        if not item.source.startswith("~"):
            action.status = BLOCKED
            action.message = f"ruta fuera del home: {item.source}"
            return action
        destination = from_portable(item.source)
        if not is_within(destination, home()):
            action.status = BLOCKED
            action.message = f"ruta fuera del home: {destination}"
            return action

    if item.blob and store is not None and not store.path_of(item.blob).exists():
        action.status = BLOCKED
        action.message = "falta el contenido en la copia (blob inexistente)"

    return action


def missing_assets(manifest: Manifest, restored: set[str] | None = None) -> list[str]:
    """Temas/iconos que la copia referencia pero este sistema no tiene.

    `restored` son los nombres que la propia restauracion va a reponer: esos
    no se reportan como faltantes.
    """
    recorded: dict = manifest.host.get("assets") or {}
    current = scan_system_assets()
    restored = restored or set()
    missing: list[str] = []
    for kind, names in recorded.items():
        local = set(current.get(kind, []))
        for name in names:
            if name not in local and name not in restored:
                missing.append(name)
    return sorted(set(missing))


def build_plan(
    manifest: Manifest,
    store: BlobStore | None = None,
    *,
    only: set[str] | None = None,
    exclude: set[str] | None = None,
) -> list[Action]:
    actions: list[Action] = []
    for item in manifest.items:
        if only and item.category not in only:
            continue
        if exclude and item.category in exclude:
            continue
        actions.append(_check_item(item, store))
    return actions


# --------------------------------------------------------------------- aplicar


def apply_plan(
    actions: list[Action],
    store: BlobStore | None,
    *,
    safety: bool = True,
    engine_root: Path | None = None,
) -> RestoreReport:
    report = RestoreReport(actions=actions)

    if safety and any(a.status == OK for a in actions):
        try:
            engine = BackupEngine(engine_root)
            snapshot = engine.create(
                label="Punto de restauracion (automatico)",
                notes="Creado antes de restaurar una copia.",
                preview=False,
            )
            report.safety_id = snapshot.id
        except Exception as exc:  # sin entorno detectable no se puede, pero no bloquea
            report.safety_error = str(exc)

    for action in actions:
        if action.status != OK:
            continue
        item = action.item
        try:
            _apply_item(item, store)
            report.applied += 1
        except Exception as exc:
            action.status = "failed"
            action.message = str(exc)
            report.failures.append((item.name, str(exc)))

    return report


def _apply_item(item: Item, store: BlobStore | None) -> None:
    if item.kind in (KIND_FILE, KIND_TREE) and store is None:
        raise RuntimeError("falta el almacen de la copia para este elemento")
    if item.kind == KIND_FILE:
        _restore_file(item, store)
    elif item.kind == KIND_TREE:
        _restore_tree(item, store)
    elif item.kind == KIND_DCONF:
        ok, message = dconf_load(item.data["path"], store.read(item.blob))
        if not ok:
            raise RuntimeError(message or "dconf load fallo")
    elif item.kind == KIND_SETTING:
        _apply_setting(item)
    else:
        raise RuntimeError(f"tipo de item desconocido: {item.kind}")


def _apply_setting(item: Item) -> None:
    data = item.data or {}
    if item.backend == "xfconf":
        ok, message = set_prop(
            data.get("channel", ""),
            data.get("prop", ""),
            data.get("type", "string"),
            data.get("value", ""),
        )
        if not ok:
            raise RuntimeError(message)
        return

    if item.backend == "dconf":
        path = (data.get("path") or "").rstrip("/")
        key = data.get("key") or ""
        if not path or not key:
            raise RuntimeError("ajuste dconf incompleto")
        proc = run(["dconf", "write", f"{path}/{key}", str(data.get("value", ""))], timeout=20)
        if proc is None or proc.returncode != 0:
            detail = proc.stderr.decode("utf-8", "replace").strip() if proc else "dconf no disponible"
            raise RuntimeError(detail or "dconf write fallo")
        return

    if item.backend == "ini":
        _write_ini(data)
        return

    raise RuntimeError(f"backend desconocido: {item.backend}")


def _write_ini(data: dict) -> None:
    filename = str(data.get("file") or "")
    group = str(data.get("group") or "")
    key = str(data.get("key") or "")
    value = str(data.get("value") or "")
    if not filename or not group or not key:
        raise RuntimeError("ajuste ini incompleto")

    tool = which("kwriteconfig6", "kwriteconfig5")
    if tool is not None:
        proc = run(
            [tool, "--file", filename, "--group", group, "--key", key, "--type", "string", value],
            timeout=20,
        )
        if proc is not None and proc.returncode == 0:
            return

    path = xdg_config_home() / filename
    parser = configparser.RawConfigParser(strict=False)
    parser.optionxform = str
    if path.is_file():
        try:
            parser.read_string(path.read_text(errors="replace"))
        except configparser.Error:
            parser = configparser.RawConfigParser(strict=False)
            parser.optionxform = str
    if not parser.has_section(group):
        parser.add_section(group)
    parser.set(group, key, value)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".themevault.tmp")
    import io as _io

    buffer = _io.StringIO()
    parser.write(buffer)
    tmp.write_text(buffer.getvalue())
    os.replace(tmp, path)


def _guard(destination: Path) -> None:
    if not is_within(destination, home()):
        raise ValueError(f"se niega a escribir fuera del home: {destination}")


def _restore_file(item: Item, store: BlobStore) -> None:
    data = store.read(item.blob)
    destination = from_portable(item.source)
    _guard(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp = destination.with_name(f".{destination.name}.themevault.tmp")
    tmp.write_bytes(data)
    os.replace(tmp, destination)


def _restore_tree(item: Item, store: BlobStore) -> None:
    destination = from_portable(item.source)
    _guard(destination)
    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True)

    staging = parent / f".themevault-new-{destination.name}"
    if staging.exists():
        shutil.rmtree(staging)
    store.extract_tree(item.blob, staging)

    extracted = staging / destination.name
    if not extracted.is_dir():
        shutil.rmtree(staging, ignore_errors=True)
        raise RuntimeError("el paquete no contiene el directorio esperado")

    previous = parent / f".themevault-old-{destination.name}"
    try:
        if previous.exists():
            shutil.rmtree(previous)

        if destination.exists() or destination.is_symlink():
            destination.rename(previous)
        extracted.rename(destination)
    except BaseException:
        # Dejar el sistema como estaba antes del intento.
        if not destination.exists() and previous.exists():
            previous.rename(destination)
        raise
    finally:
        shutil.rmtree(staging, ignore_errors=True)
        if previous.exists() and destination.exists():
            shutil.rmtree(previous, ignore_errors=True)


# ------------------------------------------------------------------- resumenes


def summarize(actions: list[Action]) -> str:
    total = len(actions)
    blocked = sum(1 for a in actions if a.status == BLOCKED)
    warn = sum(1 for a in actions if a.status == WARN)
    ok = total - blocked - warn
    parts = [f"{ok} cambios aplicables"]
    if warn:
        parts.append(f"{warn} advertencias")
    if blocked:
        parts.append(f"{blocked} bloqueados")
    return f"{total} items: " + ", ".join(parts)
