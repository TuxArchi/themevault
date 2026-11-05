"""Parser de LXQt (INIs y atajos globales)."""

from __future__ import annotations

import configparser
from pathlib import Path
from urllib.parse import unquote

from .keybinds import bind_entry


def _parser(text: str) -> configparser.RawConfigParser:
    parser = configparser.RawConfigParser(strict=False)
    parser.optionxform = str
    parser.read_string(text)
    return parser


def keybindings(text: str, source: str = "") -> list[dict]:
    try:
        parser = _parser(text)
    except configparser.Error:
        return []

    found: list[dict] = []
    for section in parser.sections():
        combo = section.rsplit(".", 1)[0]
        combo = unquote(combo)
        if not combo:
            continue
        values = dict(parser.items(section))
        command = str(values.get("Exec") or values.get("Command") or "").strip()
        description = str(values.get("Comment") or values.get("Name") or "").strip()
        enabled = str(values.get("Enabled", "true")).lower() not in ("false", "0", "no")
        entry = bind_entry(
            combo=combo,
            dispatcher="exec" if command else "",
            arg=command,
            options={"enabled": enabled},
            source=source,
            line=0,
            fmt="lxqt",
            kind="lxqt-global",
            description=description,
        )
        found.append(entry)
    return found


def keybinds_from_items(items, store) -> list[dict]:
    found: list[dict] = []
    for item in items:
        if not item.blob:
            continue
        try:
            text = store.read(item.blob).decode("utf-8", "replace")
        except OSError:
            continue
        found.extend(keybindings(text, item.source or ""))
    return found


def wallpaper_from_settings(text: str) -> Path | None:
    try:
        parser = _parser(text)
    except configparser.Error:
        return None
    for section in parser.sections():
        for key in ("wallpaper", "Wallpaper"):
            if parser.has_option(section, key):
                raw = str(parser.get(section, key)).strip().strip("'\"")
                if raw.startswith("file://"):
                    raw = raw[len("file://") :]
                candidate = Path(raw).expanduser()
                if candidate.is_file():
                    return candidate
    return None


def theme_values(text: str) -> dict[str, str]:
    try:
        parser = _parser(text)
    except configparser.Error:
        return {}
    values: dict[str, str] = {}
    for section in parser.sections():
        for key, value in parser.items(section):
            lower = key.lower()
            if lower in ("icon_theme", "theme", "style", "cursor_theme"):
                values[lower] = str(value).strip()
    return values
