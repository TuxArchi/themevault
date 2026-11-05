"""Parser de configuración de niri (KDL).

No se ejecuta nada: se interpreta un subconjunto de KDL suficiente para
extraer includes, atajos, cursor, variables de entorno y comandos de arranque.
Si un archivo usa KDL muy exótico, el respaldo de archivos sigue funcionando y
solo se pierde la vista de atajos.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .ecosystem import wallpapers_from_text
from .keybinds import bind_entry


@dataclass
class KdlNode:
    name: str
    args: list[str] = field(default_factory=list)
    props: dict[str, str] = field(default_factory=dict)
    children: list["KdlNode"] = field(default_factory=list)
    line: int = 0


@dataclass
class _Token:
    kind: str
    value: str = ""
    line: int = 0


def _read_string(text: str, index: int) -> tuple[str, int]:
    quote = text[index]
    index += 1
    out: list[str] = []
    while index < len(text):
        char = text[index]
        if char == "\\" and index + 1 < len(text):
            nxt = text[index + 1]
            out.append(
                {
                    "n": "\n",
                    "r": "\r",
                    "t": "\t",
                    '"': '"',
                    "\\": "\\",
                }.get(nxt, nxt)
            )
            index += 2
            continue
        if char == quote:
            return "".join(out), index + 1
        out.append(char)
        index += 1
    return "".join(out), index


def _read_raw_string(text: str, index: int) -> tuple[str, int]:
    # r#"texto"# o r"texto"
    index += 1
    hashes = 0
    while index < len(text) and text[index] == "#":
        hashes += 1
        index += 1
    if index >= len(text) or text[index] != '"':
        return "", index
    index += 1
    end = '"' + "#" * hashes
    position = text.find(end, index)
    if position < 0:
        return text[index:], len(text)
    return text[index:position], position + len(end)


def _tokenize(text: str) -> list[_Token]:
    tokens: list[_Token] = []
    index = 0
    line = 1
    length = len(text)

    while index < length:
        char = text[index]
        if char in " \t\r":
            index += 1
            continue
        if char == "\n":
            tokens.append(_Token("NEWLINE", "\n", line))
            line += 1
            index += 1
            continue
        if char == "/" and index + 1 < length:
            nxt = text[index + 1]
            if nxt == "/":
                index += 2
                while index < length and text[index] not in "\r\n":
                    index += 1
                continue
            if nxt == "*":
                index += 2
                while index + 1 < length and not (
                    text[index] == "*" and text[index + 1] == "/"
                ):
                    if text[index] == "\n":
                        line += 1
                    index += 1
                index += 2
                continue
            if nxt == "-":
                tokens.append(_Token("SLASHDASH", "/-", line))
                index += 2
                continue
        if char == "{":
            tokens.append(_Token("LBRACE", "{", line))
            index += 1
            continue
        if char == "}":
            tokens.append(_Token("RBRACE", "}", line))
            index += 1
            continue
        if char == ";":
            tokens.append(_Token("SEMI", ";", line))
            index += 1
            continue
        if char == "=":
            tokens.append(_Token("EQUALS", "=", line))
            index += 1
            continue
        if char == "(":
            # Anotación de tipo KDL: se ignora.
            index += 1
            depth = 1
            while index < length and depth:
                if text[index] == "(":
                    depth += 1
                elif text[index] == ")":
                    depth -= 1
                index += 1
            continue
        if char in ('"', "'"):
            value, index = _read_string(text, index)
            tokens.append(_Token("VALUE", value, line))
            continue
        if char in ("r", "R") and index + 1 < length and text[index + 1] in ('"', "#"):
            value, index = _read_raw_string(text, index)
            tokens.append(_Token("VALUE", value, line))
            continue

        start = index
        while index < length and text[index] not in " \t\r\n{};=()":
            index += 1
        raw = text[start:index]
        if raw:
            tokens.append(_Token("VALUE", raw, line))
        else:
            index += 1
    return tokens


def parse(text: str) -> list[KdlNode]:
    tokens = _tokenize(text)
    index = 0

    def skip_separators(pos: int) -> int:
        while pos < len(tokens) and tokens[pos].kind in ("NEWLINE", "SEMI"):
            pos += 1
        return pos

    def parse_node(pos: int, discard: bool = False) -> tuple[KdlNode | None, int]:
        if pos >= len(tokens) or tokens[pos].kind in ("RBRACE", "NEWLINE", "SEMI"):
            return None, pos
        token = tokens[pos]
        if token.kind not in ("VALUE",):
            return None, pos + 1
        node = KdlNode(name=token.value, line=token.line)
        pos += 1

        while pos < len(tokens):
            current = tokens[pos]
            if current.kind in ("NEWLINE", "SEMI", "RBRACE"):
                break
            if current.kind == "SLASHDASH":
                pos += 1
                if pos < len(tokens):
                    pos += 1 if tokens[pos].kind == "VALUE" else 0
                continue
            if current.kind == "LBRACE":
                children, pos = parse_children(pos + 1)
                if not discard:
                    node.children = children
                break
            if current.kind == "EQUALS":
                if node.args:
                    prop = node.args.pop()
                    pos += 1
                    if pos < len(tokens) and tokens[pos].kind == "VALUE":
                        node.props[prop] = tokens[pos].value
                        pos += 1
                else:
                    pos += 1
                continue
            if current.kind == "VALUE":
                if not discard:
                    node.args.append(current.value)
                pos += 1
                continue
            pos += 1
        return None if discard else node, pos

    def parse_children(pos: int) -> tuple[list[KdlNode], int]:
        nodes: list[KdlNode] = []
        while pos < len(tokens):
            pos = skip_separators(pos)
            if pos >= len(tokens):
                break
            if tokens[pos].kind == "RBRACE":
                pos += 1
                break
            if tokens[pos].kind == "SLASHDASH":
                pos += 1
                _discarded, pos = parse_node(pos, discard=True)
                continue
            node, pos = parse_node(pos)
            if node is not None:
                nodes.append(node)
            else:
                pos += 1
        return nodes, pos

    nodes: list[KdlNode] = []
    while index < len(tokens):
        index = skip_separators(index)
        if index >= len(tokens):
            break
        if tokens[index].kind == "SLASHDASH":
            index += 1
            _discarded, index = parse_node(index, discard=True)
            continue
        node, index = parse_node(index)
        if node is not None:
            nodes.append(node)
        else:
            index += 1
    return nodes


def walk(nodes: list[KdlNode]):
    for node in nodes:
        yield node
        yield from walk(node.children)


def find_nodes(nodes: list[KdlNode], name: str) -> list[KdlNode]:
    return [node for node in walk(nodes) if node.name == name]


def includes_from_nodes(nodes: list[KdlNode]) -> list[str]:
    return [node.args[0] for node in nodes if node.name == "include" and node.args]


def include_specs(nodes: list[KdlNode]) -> list[tuple[str, bool]]:
    found: list[tuple[str, bool]] = []
    for node in nodes:
        if node.name != "include" or not node.args:
            continue
        optional = str(node.props.get("optional", "")).strip().lower() in (
            "true",
            "1",
            "yes",
        )
        found.append((node.args[0], optional))
    return found


def startup_commands(nodes: list[KdlNode]) -> list[str]:
    commands: list[str] = []
    for node in walk(nodes):
        if node.name == "spawn-at-startup" and node.args:
            commands.append(" ".join(node.args))
        elif node.name == "spawn-sh-at-startup" and node.args:
            commands.append(node.args[0])
    return commands


def cursor_from_nodes(nodes: list[KdlNode]) -> dict[str, str]:
    values: dict[str, str] = {}
    for node in find_nodes(nodes, "cursor"):
        for child in node.children:
            if child.args:
                values[child.name] = child.args[0]
    return values


def environment_from_nodes(nodes: list[KdlNode]) -> dict[str, str]:
    values: dict[str, str] = {}
    for node in find_nodes(nodes, "environment"):
        for child in node.children:
            if child.args:
                values[child.name] = child.args[0]
    return values


def _action_from_node(node: KdlNode) -> dict:
    return {
        "name": node.name,
        "args": list(node.args),
        "options": dict(node.props),
    }


def binds_from_nodes(nodes: list[KdlNode], source: str) -> list[dict]:
    binds: dict[str, dict] = {}
    for binds_node in find_nodes(nodes, "binds"):
        for bind in binds_node.children:
            if not bind.name or not bind.children:
                continue
            actions = [_action_from_node(child) for child in bind.children]
            primary = actions[0] if actions else {"name": "", "args": [], "options": {}}
            options = dict(bind.props)
            if primary.get("options"):
                options.update(primary["options"])
            description = (
                options.get("hotkey-overlay-title")
                or options.get("description")
                or ""
            )
            entry = bind_entry(
                combo=bind.name,
                dispatcher=str(primary.get("name", "")),
                arg=" ".join(str(part) for part in primary.get("args", [])).strip(),
                options=options,
                source=source,
                line=bind.line,
                fmt="niri",
                kind="niri-bind",
                description=description,
                actions=actions if len(actions) > 1 else None,
            )
            binds[bind.name] = entry
    return list(binds.values())


def keybinds_from_items(items, store) -> list[dict]:
    selected = [item for item in items if item.blob]
    selected.sort(key=lambda item: int((item.meta or {}).get("format_order") or 0))
    found: dict[str, dict] = {}
    for item in selected:
        try:
            text = store.read(item.blob).decode("utf-8", "replace")
        except OSError:
            continue
        for entry in binds_from_nodes(parse(text), item.source or ""):
            found[entry["combo"]] = entry
    return list(found.values())


def wallpapers(nodes: list[KdlNode]) -> list[Path]:
    found: list[Path] = []
    for command in startup_commands(nodes):
        for candidate in wallpapers_from_text(command):
            if candidate not in found:
                found.append(candidate)
    return found
