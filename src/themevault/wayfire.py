"""Parser de configuración de Wayfire (`wayfire.ini`)."""

from __future__ import annotations

import configparser
from pathlib import Path

from .ecosystem import wallpapers_from_text
from .keybinds import bind_entry


def _strip_comments(text: str) -> str:
    lines = []
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#") or stripped.startswith(";"):
            continue
        lines.append(line.split("#", 1)[0])
    return "\n".join(lines)


def _parser(text: str) -> configparser.RawConfigParser:
    parser = configparser.RawConfigParser(strict=False)
    parser.optionxform = str
    parser.read_string(_strip_comments(text))
    return parser


def parse(text: str, source: str = "") -> dict:
    try:
        parser = _parser(text)
    except configparser.Error:
        return {
            "binds": [],
            "cursor": "",
            "cursor_size": "",
            "wallpapers": [],
        }

    binds: dict[str, dict] = {}
    cursor = ""
    cursor_size = ""
    wallpapers: list[Path] = []
    line = 1

    for section in parser.sections():
        values = dict(parser.items(section))
        lower = {key.lower(): value for key, value in values.items()}

        for key in ("xcursor_theme", "cursor_theme", "cursorTheme"):
            if key.lower() in lower and not cursor:
                cursor = lower[key.lower()].strip()
        for key in ("xcursor_size", "cursor_size", "cursorSize"):
            if key.lower() in lower and not cursor_size:
                cursor_size = lower[key.lower()].strip()

        for key, value in values.items():
            lower_key = key.lower()
            if lower_key.startswith("binding_"):
                name = key[len("binding_") :]
                command = (
                    values.get(f"command_{name}")
                    or values.get(f"exec_{name}")
                    or values.get(f"action_{name}")
                    or ""
                )
                if command:
                    dispatcher = "exec"
                    arg = command.strip()
                else:
                    dispatcher = section
                    arg = name
                combo = value.strip()
                if not combo:
                    continue
                entry = bind_entry(
                    combo=combo,
                    dispatcher=dispatcher,
                    arg=arg,
                    options={},
                    mode=section,
                    source=source,
                    line=line,
                    fmt="wayfire",
                    kind="wayfire-binding",
                )
                binds[combo] = entry
                continue

            # Algunas secciones usan `nombre = <super> KEY_Q` directamente.
            if (
                section not in ("command", "autostart")
                and "<" in value
                and "KEY_" in value
            ):
                entry = bind_entry(
                    combo=value.strip(),
                    dispatcher=key,
                    arg="",
                    options={},
                    mode=section,
                    source=source,
                    line=line,
                    fmt="wayfire",
                    kind="wayfire-binding",
                )
                binds[value.strip()] = entry

        if section in ("autostart", "command"):
            for value in values.values():
                for candidate in wallpapers_from_text(value):
                    if candidate not in wallpapers:
                        wallpapers.append(candidate)
        for key in ("image", "wallpaper", "background"):
            value = lower.get(key, "").strip()
            if not value:
                continue
            candidate = Path(value).expanduser()
            if candidate.is_file() and candidate not in wallpapers:
                wallpapers.append(candidate)

    return {
        "binds": list(binds.values()),
        "cursor": cursor,
        "cursor_size": cursor_size,
        "wallpapers": wallpapers,
    }


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
