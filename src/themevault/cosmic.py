"""Parser de atajos de COSMIC (RON)."""

from __future__ import annotations

import re

from .ecosystem import images_from_text
from .keybinds import bind_entry

_MODIFIERS = re.compile(r"modifiers\s*:\s*\[([^\]]*)\]", re.DOTALL)
_KEY = re.compile(r"key\s*:\s*\"([^\"]*)\"")
_DESCRIPTION = re.compile(r"description\s*:\s*Some\(\s*\"([^\"]*)\"\s*\)", re.DOTALL)


def _strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return re.sub(r"//[^\n]*", "", text)


def _balanced(text: str, index: int, open_char: str, close_char: str) -> tuple[str, int]:
    depth = 0
    in_string = False
    escaped = False
    start = index
    while index < len(text):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            index += 1
            continue
        if char == open_char:
            depth += 1
        elif char == close_char:
            depth -= 1
            if depth == 0:
                return text[start : index + 1], index + 1
        index += 1
    return text[start:], index


def shortcuts(text: str, source: str = "") -> list[dict]:
    clean = _strip_comments(text)
    found: list[dict] = []
    index = 0
    while index < len(clean):
        if clean[index] != "(":
            index += 1
            continue
        attrs, index = _balanced(clean, index, "(", ")")
        while index < len(clean) and clean[index] in " \t\r\n":
            index += 1
        if index >= len(clean) or clean[index] != ":":
            continue
        index += 1
        while index < len(clean) and clean[index] in " \t\r\n":
            index += 1
        match = re.match(r"[A-Za-z_][A-Za-z0-9_]*", clean[index:])
        if not match:
            continue
        action = match.group(0)
        index += len(action)
        while index < len(clean) and clean[index] in " \t\r\n":
            index += 1
        arg = ""
        if index < len(clean) and clean[index] == "(":
            inner, index = _balanced(clean, index, "(", ")")
            arg = inner[1:-1].strip()
            if arg.startswith('"') and arg.endswith('"'):
                arg = arg[1:-1]

        modifiers = _MODIFIERS.search(attrs)
        key = _KEY.search(attrs)
        description = _DESCRIPTION.search(attrs)
        mods = []
        if modifiers:
            mods = [
                part.strip()
                for part in modifiers.group(1).split(",")
                if part.strip()
            ]
        key_name = key.group(1).strip() if key else ""
        combo = "+".join([*mods, key_name]) if key_name else "+".join(mods)
        if not combo:
            continue
        entry = bind_entry(
            combo=combo,
            dispatcher=action,
            arg=arg,
            options={},
            mode="",
            source=source,
            line=0,
            fmt="cosmic",
            kind="cosmic-shortcut",
            description=description.group(1) if description else "",
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
        found.extend(shortcuts(text, item.source or ""))
    return found


def wallpapers(text: str) -> list:
    return images_from_text(text)
