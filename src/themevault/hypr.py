"""Parser de configuración de Hyprland.

Hyprland usa un formato propio: variables con ``$nombre = valor``, bloques,
``source = ...`` y líneas ``bind``/``unbind``. Acá se interpreta ese texto sin
ejecutarlo, para guardar los atajos en el manifest y mostrarlos en la app.
"""

from __future__ import annotations

import glob
import os
import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path

from .util import expand, home, is_within, to_portable

# Archivos que pueden ser fuente de Hyprland. Son configuración, no scripts.
SOURCE_SUFFIXES = {
    ".conf",
    ".ini",
    ".json",
    ".jsonc",
    ".toml",
    ".yaml",
    ".yml",
    ".css",
    ".rasi",
    ".kvconfig",
    ".colors",
    ".theme",
    ".xml",
}

_VAR_RE = re.compile(r"\$([A-Za-z0-9_]+)")
_DIRECTIVE_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*)\s*=\s*(.*)$")
_VARIABLE_RE = re.compile(r"^\$([A-Za-z0-9_]+)\s*=\s*(.*)$")
_GLOB_CHARS = set("*?[")


@dataclass
class HyprState:
    variables: dict[str, str] = field(default_factory=dict)
    binds: list[dict] = field(default_factory=list)
    submap: str = ""


def split_comment(raw: str) -> tuple[str, str]:
    """Separa la directiva de un comentario ``#`` respetando comillas."""
    body: list[str] = []
    comment: list[str] = []
    in_string = False
    quote = ""
    escaped = False

    for index, char in enumerate(raw):
        if escaped:
            body.append(char)
            escaped = False
            continue
        if char == "\\":
            body.append(char)
            escaped = True
            continue
        if in_string:
            body.append(char)
            if char == quote:
                in_string = False
            continue
        if char in ('"', "'"):
            in_string = True
            quote = char
            body.append(char)
            continue
        if char == "#":
            comment = list(raw[index + 1 :])
            break
        body.append(char)

    return "".join(body).strip(), "".join(comment).strip()


def directive(content: str) -> tuple[str, str] | None:
    match = _DIRECTIVE_RE.match(content)
    if not match:
        return None
    return match.group(1).lower(), match.group(2).strip()


def parse_variable(content: str) -> tuple[str, str] | None:
    match = _VARIABLE_RE.match(content)
    if not match:
        return None
    return match.group(1), match.group(2).strip()


def expand_vars(value: str, variables: dict[str, str], depth: int = 0) -> str:
    """Expande ``$variable`` de forma recursiva, sin tocar ``$HOME``."""
    if depth > 10 or "$" not in value:
        return value

    def replace(match: re.Match[str]) -> str:
        return variables.get(match.group(1), match.group(0))

    expanded = _VAR_RE.sub(replace, value)
    if expanded == value:
        return expanded
    return expand_vars(expanded, variables, depth + 1)


def _normalize_mods(value: str) -> str:
    return " ".join(value.replace("+", " ").split())


def combo(mods: str, key: str) -> str:
    parts = [part for part in (mods, key) if part]
    return " + ".join(parts)


def _script_from_arg(arg: str) -> str:
    """Ruta de un script mencionado en ``exec``, solo como dependencia."""
    if not arg:
        return ""
    try:
        tokens = shlex.split(arg)
    except ValueError:
        tokens = arg.split()
    for token in tokens:
        raw = token.strip().strip("'\"")
        if not raw or raw.startswith("-"):
            continue
        if not (raw.startswith("~") or raw.startswith("$HOME") or raw.startswith("/")):
            continue
        candidate = expand(raw)
        if not candidate.is_file():
            continue
        try:
            if not is_within(candidate.resolve(), home()):
                continue
        except OSError:
            continue
        return to_portable(candidate)
    return ""


def parse_bind(
    kind: str,
    value: str,
    *,
    comment: str = "",
    source: str = "",
    line: int = 0,
    submap: str = "",
    variables: dict[str, str],
) -> dict | None:
    parts = [part.strip() for part in value.split(",", 3)]
    if len(parts) < 3:
        return None

    mods = _normalize_mods(expand_vars(parts[0], variables))
    key = expand_vars(parts[1], variables).strip()
    dispatcher = expand_vars(parts[2], variables).strip()
    arg = expand_vars(parts[3], variables).strip() if len(parts) > 3 else ""
    if not key and not dispatcher:
        return None

    return {
        "mods": mods,
        "key": key,
        "dispatcher": dispatcher,
        "arg": arg,
        "combo": combo(mods, key),
        "submap": submap,
        "description": comment,
        "kind": kind,
        "flags": kind[4:] if kind.startswith("bind") else "",
        "source": source,
        "line": line,
        "script": _script_from_arg(arg) if dispatcher.startswith("exec") else "",
        "restorable": True,
    }


def parse_unbind(value: str, *, variables: dict[str, str]) -> tuple[str, str] | None:
    parts = [part.strip() for part in value.split(",", 1)]
    if len(parts) != 2:
        return None
    mods = _normalize_mods(expand_vars(parts[0], variables))
    key = expand_vars(parts[1], variables).strip()
    if not key:
        return None
    return mods, key


def remove_bind(binds: list[dict], mods: str, key: str, submap: str) -> bool:
    for index in range(len(binds) - 1, -1, -1):
        entry = binds[index]
        if (
            entry.get("mods") == mods
            and entry.get("key") == key
            and entry.get("submap") == submap
        ):
            del binds[index]
            return True
    return False


def feed_text(
    state: HyprState,
    text: str,
    source: str,
    *,
    on_source=None,
) -> None:
    """Procesa un archivo de configuración en orden.

    ``on_source`` recibe el valor crudo de cada ``source = ...`` para que el
    adaptador resuelva y procese los includes en el mismo punto del archivo.
    """
    for line_number, raw in enumerate(text.splitlines(), start=1):
        content, comment = split_comment(raw)
        if not content:
            continue

        variable = parse_variable(content)
        if variable is not None:
            name, value = variable
            state.variables[name] = expand_vars(value, state.variables)
            continue

        current = directive(content)
        if current is None:
            continue
        name, value = current

        if name == "source":
            if on_source is not None:
                on_source(expand_vars(value, state.variables))
            continue

        if name == "submap":
            state.submap = "" if value.strip().lower() in ("", "reset") else value.strip()
            continue

        if name == "unbind":
            parsed = parse_unbind(value, variables=state.variables)
            if parsed is not None:
                remove_bind(state.binds, parsed[0], parsed[1], state.submap)
            continue

        if name.startswith("bind"):
            entry = parse_bind(
                name,
                value,
                comment=comment,
                source=source,
                line=line_number,
                submap=state.submap,
                variables=state.variables,
            )
            if entry is not None:
                state.binds.append(entry)


def source_paths(value: str, base_dir: Path, variables: dict[str, str]) -> list[Path]:
    """Resuelve un ``source``: variables, ``~``, rutas relativas y globs."""
    raw = expand_vars(value.strip(), variables)
    raw = os.path.expandvars(os.path.expanduser(raw)).strip().strip("'\"")
    if not raw:
        return []

    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = Path(base_dir) / candidate

    text = str(candidate)
    if any(char in text for char in _GLOB_CHARS):
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


def keybinds_from_items(items, store) -> list[dict]:
    """Reconstruye atajos desde los blobs de una copia (para ``rebuild``)."""
    selected = [
        item
        for item in items
        if (item.meta or {}).get("hypr") and item.blob
    ]
    selected.sort(
        key=lambda item: (
            0 if (item.meta or {}).get("hypr_order") else 1,
            int((item.meta or {}).get("hypr_order") or 0),
            item.source or "",
        )
    )

    state = HyprState()
    for item in selected:
        try:
            text = store.read(item.blob).decode("utf-8", "replace")
        except OSError:
            continue
        feed_text(state, text, item.source or to_portable(item.source))
    return state.binds
