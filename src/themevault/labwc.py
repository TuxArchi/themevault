"""Parser de configuración de labwc (`rc.xml`)."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from .ecosystem import wallpapers_from_text
from .keybinds import bind_entry

_MODS = {
    "W": "Super",
    "A": "Alt",
    "C": "Ctrl",
    "S": "Shift",
    "M": "Meta",
    "Mod4": "Super",
    "Mod1": "Alt",
}


def _combo(raw: str) -> str:
    value = (raw or "").strip()
    if not value:
        return ""
    parts = value.split("-")
    if len(parts) <= 1:
        return value
    mods = [_MODS.get(part, part) for part in parts[:-1]]
    key = parts[-1]
    return "+".join([*mods, key])


def parse(text: str, source: str = "") -> dict:
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return {"binds": [], "cursor": "", "wallpapers": []}

    binds: list[dict] = []
    cursor = ""
    wallpapers: list[Path] = []

    keyboard = root.find("keyboard")
    if keyboard is not None:
        for keybind in keyboard.findall("keybind"):
            combo = _combo(keybind.get("key", ""))
            if not combo:
                continue
            actions = keybind.findall("action")
            if not actions:
                continue
            primary = actions[0]
            dispatcher = primary.get("name", "")
            command = (primary.findtext("command") or "").strip()
            arg = command or (primary.text or "").strip()
            entry = bind_entry(
                combo=combo,
                dispatcher=dispatcher,
                arg=arg,
                options={},
                mode="",
                source=source,
                line=0,
                fmt="labwc",
                kind="labwc-keybind",
            )
            binds.append(entry)

    theme = root.find("theme")
    if theme is not None:
        for name in ("cursorTheme", "cursor_theme", "cursor"):
            value = theme.findtext(name)
            if value:
                cursor = value.strip()
                break

    for action in root.iter("action"):
        command = action.findtext("command") or ""
        for candidate in wallpapers_from_text(command):
            if candidate not in wallpapers:
                wallpapers.append(candidate)

    return {"binds": binds, "cursor": cursor, "wallpapers": wallpapers}


def keybinds_from_items(items, store) -> list[dict]:
    selected = [item for item in items if item.blob]
    found: dict[str, dict] = {}
    for item in selected:
        try:
            text = store.read(item.blob).decode("utf-8", "replace")
        except OSError:
            continue
        for entry in parse(text, item.source or "")["binds"]:
            found[entry["combo"]] = entry
    return list(found.values())
