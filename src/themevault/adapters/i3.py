"""Adaptador i3 (X11)."""

from __future__ import annotations

from pathlib import Path

from ..ecosystem import collect_ecosystem, gtk_values, wallpapers_from_text, x11_wallpapers_from_text
from ..privacy import read_config_text
from ..sway import include_paths, parse
from ..util import expand, home, is_within, to_portable, xdg_config_home
from .base import Adapter, Collector


def _config_path() -> Path:
    return xdg_config_home() / "i3" / "config"


class I3Adapter(Adapter):
    id = "i3"
    label = "i3"
    priority = 22

    def _collect(self, collector: Collector) -> None:
        state = {"binds": {}, "order": 0, "variables": {}, "wallpapers": []}
        visited: set[Path] = set()
        main = _config_path()
        if main.is_file():
            self._parse_file(main, collector, state, visited, 0)
        collector.add_config_files(
            "~/.config/i3",
            "layout",
            allowed_names=("config",),
            allowed_suffixes=(".conf",),
            skip_dirs=("config.d",),
            tag={"i3_config": True},
        )
        collector.add_config_files(
            "~/.config/i3/config.d",
            "layout",
            allowed_suffixes=(".conf",),
            allow_no_extension=True,
            tag={"i3_config": True},
        )
        collect_ecosystem(collector, shells=False)
        collector.meta.setdefault("keybinds", []).extend(state["binds"].values())

    def _parse_file(self, path, collector, state, visited, depth):
        if depth > 8:
            return
        try:
            resolved = path.resolve()
        except OSError:
            return
        if resolved in visited or not is_within(resolved, home()):
            return
        text, reason = read_config_text(
            resolved,
            allowed_names=("config",),
            allowed_suffixes=(".conf",),
            allow_no_extension=resolved.parent.name == "config.d",
        )
        if text is None:
            collector.skipped.append((str(path), reason))
            return
        item = collector.add_file(resolved, "layout")
        if item is None:
            return
        visited.add(resolved)
        item.meta.update(
            {
                "keybind_format": "sway",
                "format_order": state["order"],
                "i3_config": True,
            }
        )
        state["order"] += 1
        parsed = parse(text, to_portable(resolved), variables=state["variables"])
        state["variables"].update(parsed["variables"])
        for entry in parsed["binds"]:
            state["binds"][(entry["mode"], entry["combo"], entry["kind"])] = entry
        state["wallpapers"].extend(parsed["wallpapers"])
        for raw in text.splitlines():
            for candidate in x11_wallpapers_from_text(raw):
                if candidate not in state["wallpapers"]:
                    state["wallpapers"].append(candidate)
        for raw in text.splitlines():
            stripped = raw.strip()
            if stripped.startswith("include "):
                for candidate in include_paths(
                    stripped.split("include ", 1)[1], resolved.parent, state["variables"]
                ):
                    self._parse_file(candidate, collector, state, visited, depth + 1)

    def _texts(self) -> list[str]:
        path = _config_path()
        if not path.is_file():
            return []
        seen: set[Path] = set()
        found: list[str] = []

        def visit(candidate: Path, depth: int):
            if depth > 8:
                return
            try:
                resolved = candidate.resolve()
            except OSError:
                return
            if resolved in seen or not is_within(resolved, home()):
                return
            text, reason = read_config_text(
                resolved,
                allowed_names=("config",),
                allowed_suffixes=(".conf",),
                allow_no_extension=resolved.parent.name == "config.d",
            )
            if text is None:
                return
            seen.add(resolved)
            found.append(text)
            parsed = parse(text)
            for raw in text.splitlines():
                stripped = raw.strip()
                if stripped.startswith("include "):
                    for item in include_paths(
                        stripped.split("include ", 1)[1], resolved.parent, parsed["variables"]
                    ):
                        visit(item, depth + 1)

        visit(path, 0)
        return found

    def themes(self) -> dict[str, str]:
        values = gtk_values()
        return {
            "icons": values.get("gtk-icon-theme-name", ""),
            "cursor": values.get("gtk-cursor-theme-name", ""),
            "gtk": values.get("gtk-theme-name", ""),
        }

    def preview_sources(self) -> list[Path]:
        found: list[Path] = []
        for text in self._texts():
            for candidate in wallpapers_from_text(text) + x11_wallpapers_from_text(text):
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
    from ..sway import keybinds_from_items as _from_items

    return _from_items(items, store)
