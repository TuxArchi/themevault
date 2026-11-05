"""Parser de configuración de Sway."""

from __future__ import annotations

import glob
import os
import re
from pathlib import Path

from .ecosystem import wallpapers_from_text
from .keybinds import bind_entry

_VAR = re.compile(r"\$([A-Za-z_][A-Za-z0-9_]*)")
_INCLUDE = re.compile(r"^\s*include\s+(.+)$")
_SET = re.compile(r"^\s*set\s+\$([A-Za-z_][A-Za-z0-9_]*)\s+(.*)$")
_BIND = re.compile(r"^\s*(bindsym|bindcode|unbindsym|unbindcode)\s+(.*)$")
_MODE = re.compile(r'^\s*mode\s+(?:"([^"]+)"|(\S+))\s*\{?\s*$')
_BG = re.compile(r"^\s*output\s+\S+\s+bg\s+([^\s]+)")
_XCURSOR = re.compile(r"^\s*seat\s+\S+\s+xcursor_theme\s+([^\s]+)(?:\s+(\d+))?")


def expand_vars(value: str, variables: dict[str, str]) -> str:
    def replace(match: re.Match[str]) -> str:
        return variables.get(match.group(1), match.group(0))

    previous = ""
    current = value
    for _ in range(10):
        if current == previous:
            break
        previous = current
        current = _VAR.sub(replace, current)
    return current


def _strip_comment(line: str) -> str:
    out: list[str] = []
    escaped = False
    for char in line:
        if escaped:
            out.append(char)
            escaped = False
            continue
        if char == "\\":
            out.append(char)
            escaped = True
            continue
        if char == "#":
            break
        out.append(char)
    return "".join(out).strip()


def _split_bind(value: str) -> tuple[list[str], str, str]:
    """Separa flags, combinación y comando."""
    try:
        tokens = value.split()
    except ValueError:
        return [], "", ""
    flags: list[str] = []
    index = 0
    while index < len(tokens) and tokens[index].startswith("--"):
        flags.append(tokens[index])
        index += 1
    if index >= len(tokens):
        return flags, "", ""
    combo = tokens[index]
    command = " ".join(tokens[index + 1 :]).strip()
    return flags, combo, command


def parse(
    text: str,
    source: str = "",
    *,
    variables: dict[str, str] | None = None,
) -> dict:
    variables = dict(variables or {})
    binds: dict[tuple[str, str, str], dict] = {}
    mode = "default"
    bars: list[dict] = []
    wallpapers: list[Path] = []
    cursor_theme = ""
    cursor_size = ""
    bar: dict | None = None
    depth = 0

    for line_number, raw in enumerate(text.splitlines(), start=1):
        line = _strip_comment(raw)
        if not line:
            continue

        set_match = _SET.match(line)
        if set_match:
            variables[set_match.group(1)] = expand_vars(set_match.group(2), variables)
            continue

        bg_match = _BG.match(line)
        if bg_match:
            candidate = Path(expand_vars(bg_match.group(1), variables)).expanduser()
            if candidate.is_file() and candidate not in wallpapers:
                wallpapers.append(candidate)
            continue

        xcursor = _XCURSOR.match(line)
        if xcursor:
            cursor_theme = xcursor.group(1)
            cursor_size = xcursor.group(2) or ""
            continue

        mode_match = _MODE.match(line)
        if mode_match:
            mode = mode_match.group(1) or mode_match.group(2) or "default"
            if "{" in line:
                depth += 1
            continue

        if line.strip() == "}":
            depth = max(0, depth - 1)
            if depth == 0:
                if bar is not None:
                    bars.append(bar)
                    bar = None
                mode = "default"
            continue

        if line.startswith("bar") and "{" in line:
            depth += 1
            bar = {"position": "bottom", "height": None, "status_command": "", "mode": "dock"}
            continue

        if bar is not None:
            for key in ("position", "height", "status_command", "mode"):
                if line.startswith(key):
                    value = line[len(key) :].strip()
                    if key == "height":
                        try:
                            bar[key] = int(value)
                        except ValueError:
                            bar[key] = None
                    else:
                        bar[key] = value
                    break
            continue

        bind_match = _BIND.match(line)
        if not bind_match:
            continue
        kind, value = bind_match.groups()
        flags, combo, command = _split_bind(value)
        combo = expand_vars(combo, variables)
        command = expand_vars(command, variables)
        if not combo:
            continue

        if kind in ("unbindsym", "unbindcode"):
            for key, _entry in list(binds.items()):
                if key[0] == mode and key[1] == combo and key[2] == kind.removeprefix("un"):
                    del binds[key]
            continue

        if kind == "bindcode":
            flags.append("--to-code")
        dispatcher = command.split(" ", 1)[0] if command else ""
        arg = command.split(" ", 1)[1] if " " in command else ""
        entry = bind_entry(
            combo=combo,
            dispatcher=dispatcher,
            arg=arg,
            options={},
            mode=mode,
            source=source,
            line=line_number,
            fmt="sway",
            kind=kind,
            flags=flags,
        )
        binds[(mode, combo, kind)] = entry

    for command in _startup_commands(text):
        for candidate in wallpapers_from_text(command):
            if candidate not in wallpapers:
                wallpapers.append(candidate)

    return {
        "binds": list(binds.values()),
        "bars": bars,
        "wallpapers": wallpapers,
        "cursor": cursor_theme,
        "cursor_size": cursor_size,
        "variables": variables,
    }


def _startup_commands(text: str) -> list[str]:
    commands: list[str] = []
    for raw in text.splitlines():
        line = _strip_comment(raw)
        if line.startswith("exec ") or line.startswith("exec_always "):
            commands.append(line.split(" ", 1)[1])
    return commands


def include_paths(value: str, base_dir: Path, variables: dict[str, str]) -> list[Path]:
    raw = expand_vars(value.strip(), variables)
    raw = os.path.expandvars(os.path.expanduser(raw)).strip().strip("'\"")
    if not raw:
        return []
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = base_dir / candidate
    text = str(candidate)
    if any(char in text for char in "*?["):
        matches = [Path(item) for item in sorted(glob.glob(text, recursive=True))]
    else:
        matches = [candidate]
    found: list[Path] = []
    for item in matches:
        try:
            resolved = item.resolve()
        except OSError:
            resolved = item
        if resolved not in found:
            found.append(resolved)
    return found


def parse_bar(text: str) -> list[dict]:
    return parse(text)["bars"]


def keybinds_from_items(items, store) -> list[dict]:
    selected = [item for item in items if item.blob]
    selected.sort(key=lambda item: int((item.meta or {}).get("format_order") or 0))
    found: dict[tuple[str, str, str], dict] = {}
    variables: dict[str, str] = {}
    for item in selected:
        try:
            text = store.read(item.blob).decode("utf-8", "replace")
        except OSError:
            continue
        parsed = parse(text, item.source or "", variables=variables)
        variables.update(parsed["variables"])
        for entry in parsed["binds"]:
            found[(entry.get("mode", ""), entry["combo"], entry.get("kind", ""))] = entry
    return list(found.values())
