"""Utilidades comunes para normalizar atajos de teclado.

Cada compositor tiene su propio formato de configuración, pero todos guardan
los atajos en ``Manifest.keybinds`` con la misma forma para que la UI y la CLI
puedan mostrarlos sin saber de qué compositor vienen.
"""

from __future__ import annotations

import shlex
from pathlib import Path

from .util import expand, home, is_within, to_portable


def split_combo(combo: str) -> tuple[str, str]:
    """``Super+Shift+Q`` -> (``Super+Shift``, ``Q``)."""
    parts = [part for part in (combo or "").split("+") if part]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return "", parts[0]
    return "+".join(parts[:-1]), parts[-1]


def script_from_command(command: str) -> str:
    """Ruta de un script dentro del home mencionada en un comando."""
    if not command:
        return ""
    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()
    for token in tokens:
        raw = token.strip().strip("'\"")
        if not raw or raw.startswith("-"):
            continue
        if not (raw.startswith("~") or raw.startswith("$HOME") or raw.startswith("/")):
            continue
        candidate = Path(expand(raw))
        if not candidate.is_file():
            continue
        try:
            if not is_within(candidate.resolve(), home()):
                continue
        except OSError:
            continue
        return to_portable(candidate)
    return ""


def bind_entry(
    *,
    combo: str,
    dispatcher: str,
    arg: str = "",
    options: dict | None = None,
    mode: str = "",
    source: str = "",
    line: int = 0,
    fmt: str = "",
    kind: str = "",
    description: str = "",
    flags: list[str] | None = None,
    actions: list[dict] | None = None,
) -> dict:
    mods, key = split_combo(combo)
    command = " ".join(part for part in (dispatcher, arg) if part)
    entry = {
        "combo": combo,
        "mods": mods,
        "key": key,
        "dispatcher": dispatcher,
        "arg": arg,
        "options": options or {},
        "mode": mode,
        "source": source,
        "line": line,
        "format": fmt,
        "kind": kind,
        "description": description,
        "flags": flags or [],
        "script": script_from_command(command),
        "restorable": True,
    }
    if actions:
        entry["actions"] = actions
    return entry


def keybinds_from_items(items, store) -> list[dict]:
    """Reconstruye atajos de todos los compositores de una copia."""
    from . import hypr, labwc, niri, river, sway, wayfire

    groups: dict[str, list] = {}
    for item in items:
        fmt = (item.meta or {}).get("keybind_format")
        if not fmt:
            continue
        groups.setdefault(fmt, []).append(item)

    found: list[dict] = []
    for fmt, selected in groups.items():
        module = {
            "hypr": hypr,
            "niri": niri,
            "sway": sway,
            "river": river,
            "wayfire": wayfire,
            "labwc": labwc,
        }.get(fmt)
        if module is None or not hasattr(module, "keybinds_from_items"):
            continue
        try:
            found.extend(module.keybinds_from_items(selected, store))
        except Exception:
            continue
    return found
