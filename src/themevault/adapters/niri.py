"""Adaptador niri y sus derivados.

niri guarda su configuración en KDL. Se respaldan solo archivos .kdl de su
directorio, siguiendo includes dentro del home y extrayendo atajos, cursor y
comandos de arranque para la portada.
"""

from __future__ import annotations

import glob
import os
from pathlib import Path

from ..ecosystem import collect_ecosystem, gtk_values, wallpapers_from_text
from ..niri import (
    binds_from_nodes,
    cursor_from_nodes,
    environment_from_nodes,
    include_specs,
    parse,
    startup_commands,
    wallpapers,
)
from ..privacy import iter_config_files, read_config_text
from ..util import expand, home, is_within, to_portable, xdg_config_home
from .base import Adapter, Collector


def _config_path() -> Path:
    raw = os.environ.get("NIRI_CONFIG", "").strip()
    if raw:
        return expand(raw)
    return xdg_config_home() / "niri" / "config.kdl"


def _resolve_include(raw: str, base_dir: Path) -> list[Path]:
    value = os.path.expandvars(os.path.expanduser(raw.strip().strip("'\"")))
    if not value:
        return []
    candidate = Path(value)
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


class NiriAdapter(Adapter):
    id = "niri"
    label = "niri"
    priority = 16

    def _collect(self, collector: Collector) -> None:
        state = {"binds": {}, "order": 0}
        visited: set[Path] = set()
        main = _config_path()

        if main.is_file():
            self._parse_file(main, collector, state, visited, 0)

        collector.add_config_files(
            "~/.config/niri",
            "layout",
            allowed_suffixes=(".kdl",),
            tag={"niri_config": True},
        )
        collect_ecosystem(collector)

        # Si no hay config.kdl, igual extraemos atajos de los .kdl presentes.
        if not main.is_file():
            collected = [
                item
                for item in collector.items
                if (item.meta or {}).get("niri_config") and item.blob
            ]
            collected.sort(key=lambda item: item.source or "")
            for item in collected:
                try:
                    text = collector.store.read(item.blob).decode("utf-8", "replace")
                except OSError:
                    continue
                item.meta["keybind_format"] = "niri"
                item.meta["format_order"] = state["order"]
                state["order"] += 1
                for entry in binds_from_nodes(parse(text), item.source or ""):
                    state["binds"][entry["combo"]] = entry

        collector.meta.setdefault("keybinds", []).extend(state["binds"].values())

    def _parse_file(
        self,
        path: Path,
        collector: Collector,
        state: dict,
        visited: set[Path],
        depth: int,
    ) -> None:
        if depth > 8:
            collector.skipped.append((str(path), "demasiados niveles de include"))
            return
        try:
            resolved = path.resolve()
        except OSError:
            collector.skipped.append((str(path), "no se pudo resolver la ruta"))
            return
        if resolved in visited:
            return
        if not is_within(resolved, home()):
            collector.skipped.append((str(path), "include fuera del home"))
            return
        if resolved.suffix.lower() != ".kdl":
            collector.skipped.append((str(path), "include no es .kdl"))
            return

        text, reason = read_config_text(resolved, allowed_suffixes=(".kdl",))
        if text is None:
            collector.skipped.append((str(path), reason))
            return

        item = collector.add_file(resolved, "layout")
        if item is None:
            return
        visited.add(resolved)
        item.meta.update(
            {
                "keybind_format": "niri",
                "format_order": state["order"],
                "niri_config": True,
            }
        )
        state["order"] += 1

        nodes = parse(text)
        for entry in binds_from_nodes(nodes, to_portable(resolved)):
            state["binds"][entry["combo"]] = entry

        for raw_include, optional in include_specs(nodes):
            candidates = _resolve_include(raw_include, resolved.parent)
            if not candidates and optional:
                continue
            for candidate in candidates:
                if optional and not candidate.is_file():
                    continue
                self._parse_file(candidate, collector, state, visited, depth + 1)

    # ------------------------------------------------------------------ previa

    def _texts(self) -> list[tuple[str, str]]:
        found: list[tuple[str, str]] = []
        seen: set[Path] = set()

        def visit(path: Path, depth: int) -> None:
            if depth > 8:
                return
            try:
                resolved = path.resolve()
            except OSError:
                return
            if resolved in seen or not is_within(resolved, home()):
                return
            if resolved.suffix.lower() != ".kdl":
                return
            text, reason = read_config_text(resolved, allowed_suffixes=(".kdl",))
            if text is None:
                return
            seen.add(resolved)
            found.append((to_portable(resolved), text))
            for raw_include, optional in include_specs(parse(text)):
                candidates = _resolve_include(raw_include, resolved.parent)
                if not candidates and optional:
                    continue
                for candidate in candidates:
                    if optional and not candidate.is_file():
                        continue
                    visit(candidate, depth + 1)

        main = _config_path()
        if main.is_file():
            visit(main, 0)
        for candidate, reason in iter_config_files(
            "~/.config/niri", allowed_suffixes=(".kdl",)
        ):
            if not reason:
                visit(candidate, 0)
        return found

    def themes(self) -> dict[str, str]:
        values = gtk_values()
        cursor = values.get("gtk-cursor-theme-name", "")
        gtk = values.get("gtk-theme-name", "")
        for _source, text in self._texts():
            nodes = parse(text)
            cursor_values = cursor_from_nodes(nodes)
            env = environment_from_nodes(nodes)
            if cursor_values.get("xcursor-theme"):
                cursor = cursor_values["xcursor-theme"]
            if env.get("XCURSOR_THEME"):
                cursor = env["XCURSOR_THEME"]
            if env.get("GTK_THEME"):
                gtk = env["GTK_THEME"].split(":", 1)[0]
        return {
            "icons": values.get("gtk-icon-theme-name", ""),
            "cursor": cursor,
            "gtk": gtk,
        }

    def preview_sources(self) -> list[Path]:
        found: list[Path] = []
        for _source, text in self._texts():
            for candidate in wallpapers(parse(text)):
                if candidate not in found:
                    found.append(candidate)
            for command in startup_commands(parse(text)):
                for candidate in wallpapers_from_text(command):
                    if candidate not in found:
                        found.append(candidate)
        if found:
            return found
        for raw in ("~/Pictures/Wallpapers", "~/Pictures", "~/Imágenes"):
            folder = expand(raw)
            if not folder.is_dir():
                continue
            for entry in sorted(folder.iterdir()):
                if entry.is_file() and entry.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
                    return [entry]
        return []


def keybinds_from_items(items, store) -> list[dict]:
    from ..niri import keybinds_from_items as _from_items

    return _from_items(items, store)
