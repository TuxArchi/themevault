"""Atajos guardados en dconf (Cinnamon, MATE, Budgie).

Se parsea el volcado de texto de dconf: secciones tipo ``custom0`` con
``name``/``command``/``binding`` y secciones de atajos del window manager o
media keys. No se ejecuta nada.
"""

from __future__ import annotations

import re

from .keybinds import bind_entry

_STRING = re.compile(r"'((?:[^'\\]|\\.)*)'")
_SECTION = re.compile(r"^\[(.*)\]$")


def _unquote(value: str) -> str:
    return value.replace("\\'", "'").replace("\\\\", "\\")


def _strings(value: str) -> list[str]:
    return [_unquote(match.group(1)) for match in _STRING.finditer(value)]


def _looks_like_combo(value: str, key: str) -> bool:
    if key in ("binding", "bindings"):
        return bool(_strings(value))
    return any(marker in value for marker in ("<", "XF86", "Above_Tab"))


def parse(text: str, source: str) -> list[dict]:
    sections: dict[str, dict[str, str]] = {}
    current = ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        section = _SECTION.match(line)
        if section:
            current = section.group(1)
            sections.setdefault(current, {})
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        sections.setdefault(current, {})[key.strip()] = value.strip()

    found: list[dict] = []
    for section, values in sections.items():
        mode = section if section not in ("/", "") else ""
        command = values.get("command") or values.get("action") or ""
        name = values.get("name") or ""
        if command:
            strings = _strings(command)
            command = strings[0] if strings else command
        if name:
            strings = _strings(name)
            name = strings[0] if strings else name
        for key, value in values.items():
            if key in ("command", "action", "name", "custom-list"):
                continue
            if not _looks_like_combo(value, key):
                continue
            combos = _strings(value)
            if not combos:
                continue
            for combo in combos:
                if not combo or combo == "disabled":
                    continue
                dispatcher = "command" if mode.startswith("custom") and command else key
                arg = command if dispatcher == "command" else ""
                entry = bind_entry(
                    combo=combo,
                    dispatcher=dispatcher,
                    arg=arg,
                    options={},
                    mode=mode,
                    source=source,
                    line=0,
                    fmt="dconf",
                    kind="dconf-binding",
                    description=name,
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
        path = str((item.data or {}).get("path") or "")
        found.extend(parse(text, f"dconf:{path}"))
    return found
