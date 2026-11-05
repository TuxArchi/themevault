"""Parser de la configuración de River (script `init`)."""

from __future__ import annotations

import re
import shlex
from pathlib import Path

from .ecosystem import wallpapers_from_text
from .keybinds import bind_entry

_ASSIGN = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)=(.*)$")
_MAP = re.compile(r"^\s*riverctl\s+(map(?:-pointer|-switch|-gesture)?)\s+(.*)$")
_UNMAP = re.compile(r"^\s*riverctl\s+(unmap(?:-pointer|-switch|-gesture)?)\s+(.*)$")
_XCURSOR = re.compile(r"^\s*riverctl\s+xcursor-theme\s+(\S+)(?:\s+(\d+))?")
_SOURCE = re.compile(r"^\s*(?:source|\.)\s+(\S+)")


def _strip_comment(line: str) -> str:
    return line.split("#", 1)[0].strip()


def _expand(value: str, variables: dict[str, str]) -> str:
    for name, replacement in variables.items():
        value = value.replace(f"${name}", replacement)
        value = value.replace(f"${{{name}}}", replacement)
    return value


def parse(text: str, source: str = "") -> dict:
    variables: dict[str, str] = {}
    binds: dict[tuple[str, str, str], dict] = {}
    cursor = ""
    cursor_size = ""
    wallpapers: list[Path] = []
    sources: list[str] = []

    for line_number, raw in enumerate(text.splitlines(), start=1):
        line = _strip_comment(raw)
        if not line:
            continue

        assign = _ASSIGN.match(line)
        if assign and not line.startswith("riverctl"):
            variables[assign.group(1)] = assign.group(2).strip().strip("'\"")
            continue

        source_match = _SOURCE.match(line)
        if source_match:
            sources.append(source_match.group(1))
            continue

        xcursor = _XCURSOR.match(line)
        if xcursor:
            cursor = xcursor.group(1)
            cursor_size = xcursor.group(2) or ""
            continue

        unmap = _UNMAP.match(line)
        if unmap:
            try:
                parts = shlex.split(unmap.group(2))
            except ValueError:
                continue
            mode = parts[0] if parts else "normal"
            combo = parts[1] if len(parts) > 1 else ""
            kind = "river-" + unmap.group(1).removeprefix("un")
            for key in list(binds):
                if key[0] == mode and key[1] == combo and key[2] == kind:
                    del binds[key]
            continue

        mapping = _MAP.match(line)
        if not mapping:
            for candidate in wallpapers_from_text(line):
                if candidate not in wallpapers:
                    wallpapers.append(candidate)
            continue

        kind = "river-" + mapping.group(1)
        try:
            parts = shlex.split(mapping.group(2))
        except ValueError:
            continue
        flags: list[str] = []
        while parts and parts[0].startswith("-"):
            flags.append(parts.pop(0))
        if len(parts) < 3:
            continue
        mode = parts[0]
        combo = _expand(parts[1], variables)
        action = _expand(parts[2], variables)
        arg = " ".join(_expand(part, variables) for part in parts[3:])
        entry = bind_entry(
            combo=combo,
            dispatcher=action,
            arg=arg,
            options={},
            mode=mode,
            source=source,
            line=line_number,
            fmt="river",
            kind=kind,
            flags=flags,
        )
        binds[(mode, combo, kind)] = entry

    for candidate in wallpapers_from_text(text):
        if candidate not in wallpapers:
            wallpapers.append(candidate)

    return {
        "binds": list(binds.values()),
        "cursor": cursor,
        "cursor_size": cursor_size,
        "wallpapers": wallpapers,
        "sources": sources,
        "variables": variables,
    }


def source_paths(value: str, base_dir: Path, variables: dict[str, str]) -> list[Path]:
    raw = _expand(value.strip().strip("'\""), variables)
    raw = raw.replace("~", str(Path.home()))
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = base_dir / candidate
    try:
        return [candidate.resolve()]
    except OSError:
        return [candidate]


def keybinds_from_items(items, store) -> list[dict]:
    selected = [item for item in items if item.blob]
    selected.sort(key=lambda item: int((item.meta or {}).get("format_order") or 0))
    found: dict[tuple[str, str, str], dict] = {}
    for item in selected:
        try:
            text = store.read(item.blob).decode("utf-8", "replace")
        except OSError:
            continue
        for entry in parse(text, item.source or "")["binds"]:
            found[(entry.get("mode", ""), entry["combo"], entry.get("kind", ""))] = entry
    return list(found.values())
