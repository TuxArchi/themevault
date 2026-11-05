"""Adaptador Sway."""

from __future__ import annotations

from pathlib import Path

from ..ecosystem import collect_ecosystem, gtk_values, wallpapers_from_text
from ..privacy import iter_config_files, read_config_text
from ..sway import include_paths, parse
from ..util import expand, home, is_within, to_portable, xdg_config_home
from .base import Adapter, Collector


def _config_path() -> Path:
    return xdg_config_home() / "sway" / "config"


def _safe_text(path: Path) -> tuple[str | None, str]:
    no_extension = path.parent.name == "config.d"
    return read_config_text(
        path,
        allowed_names=("config",),
        allowed_suffixes=(".conf",),
        allow_no_extension=no_extension,
    )


class SwayAdapter(Adapter):
    id = "sway"
    label = "Sway"
    priority = 17

    def _collect(self, collector: Collector) -> None:
        state = {
            "binds": {},
            "order": 0,
            "bars": [],
            "wallpapers": [],
            "cursor": "",
            "variables": {},
        }
        visited: set[Path] = set()
        main = _config_path()
        if main.is_file():
            self._parse_file(main, collector, state, visited, 0)

        collector.add_config_files(
            "~/.config/sway",
            "layout",
            allowed_names=("config",),
            allowed_suffixes=(".conf",),
            allow_any_name=False,
            skip_dirs=("config.d",),
            tag={"sway_config": True},
        )
        collector.add_config_files(
            "~/.config/sway/config.d",
            "layout",
            allowed_suffixes=(".conf",),
            allow_no_extension=True,
            tag={"sway_config": True},
        )
        collect_ecosystem(collector)

        if not main.is_file():
            collected = [
                item
                for item in collector.items
                if (item.meta or {}).get("sway_config") and item.blob
            ]
            collected.sort(key=lambda item: item.source or "")
            for item in collected:
                try:
                    text = collector.store.read(item.blob).decode("utf-8", "replace")
                except OSError:
                    continue
                item.meta["keybind_format"] = "sway"
                item.meta["format_order"] = state["order"]
                state["order"] += 1
                parsed = parse(text, item.source or "")
                for entry in parsed["binds"]:
                    state["binds"][(entry["mode"], entry["combo"], entry["kind"])] = entry

        collector.meta.setdefault("keybinds", []).extend(state["binds"].values())
        collector.meta["sway_bars"] = state["bars"]
        collector.meta["sway_cursor"] = state["cursor"]
        collector.meta["sway_wallpapers"] = state["wallpapers"]

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
        text, reason = _safe_text(resolved)
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
                "sway_config": True,
            }
        )
        state["order"] += 1

        parsed = parse(text, to_portable(resolved), variables=state["variables"])
        state["variables"].update(parsed["variables"])
        for entry in parsed["binds"]:
            state["binds"][(entry["mode"], entry["combo"], entry["kind"])] = entry
        state["bars"].extend(parsed["bars"])
        state["wallpapers"].extend(
            candidate for candidate in parsed["wallpapers"] if candidate not in state["wallpapers"]
        )
        if parsed["cursor"]:
            state["cursor"] = parsed["cursor"]

        for raw in text.splitlines():
            stripped = raw.strip()
            if not stripped.startswith("include "):
                continue
            value = stripped.split("include ", 1)[1].strip()
            for candidate in include_paths(value, resolved.parent, parsed["variables"]):
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
            text, reason = _safe_text(resolved)
            if text is None:
                return
            seen.add(resolved)
            found.append((to_portable(resolved), text))
            parsed = parse(text)
            for raw in text.splitlines():
                stripped = raw.strip()
                if not stripped.startswith("include "):
                    continue
                value = stripped.split("include ", 1)[1].strip()
                for candidate in include_paths(value, resolved.parent, parsed["variables"]):
                    visit(candidate, depth + 1)

        main = _config_path()
        if main.is_file():
            visit(main, 0)
        for candidate, reason in iter_config_files(
            "~/.config/sway", allowed_names=("config",), allowed_suffixes=(".conf",)
        ):
            if not reason:
                visit(candidate, 0)
        return found

    def themes(self) -> dict[str, str]:
        values = gtk_values()
        cursor = values.get("gtk-cursor-theme-name", "")
        for _source, text in self._texts():
            parsed = parse(text)
            if parsed["cursor"]:
                cursor = parsed["cursor"]
        return {
            "icons": values.get("gtk-icon-theme-name", ""),
            "cursor": cursor,
            "gtk": values.get("gtk-theme-name", ""),
        }

    def preview_sources(self) -> list[Path]:
        found: list[Path] = []
        for _source, text in self._texts():
            parsed = parse(text)
            for candidate in parsed["wallpapers"]:
                if candidate not in found:
                    found.append(candidate)
            for line in text.splitlines():
                for candidate in wallpapers_from_text(line):
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
