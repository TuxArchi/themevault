"""Adaptador Wayfire."""

from __future__ import annotations

from pathlib import Path

from ..ecosystem import collect_ecosystem, gtk_values, wallpapers_from_text
from ..util import expand, xdg_config_home
from ..wayfire import parse
from .base import Adapter, Collector


def _config_path() -> Path:
    return xdg_config_home() / "wayfire.ini"


class WayfireAdapter(Adapter):
    id = "wayfire"
    label = "Wayfire"
    priority = 19

    def _collect(self, collector: Collector) -> None:
        state = {"binds": {}, "order": 0, "cursor": "", "wallpapers": []}
        main = _config_path()
        item = collector.add_safe_file(
            main,
            "layout",
            allowed_names=("wayfire.ini",),
            allowed_suffixes=(".ini",),
            tag={"wayfire_config": True},
        )
        if item is not None:
            item.meta.update({"keybind_format": "wayfire", "format_order": 0})
            try:
                text = collector.store.read(item.blob).decode("utf-8", "replace")
            except OSError:
                text = ""
            parsed = parse(text, item.source or "")
            for entry in parsed["binds"]:
                state["binds"][entry["combo"]] = entry
            state["cursor"] = parsed["cursor"]
            state["wallpapers"] = parsed["wallpapers"]

        # wf-shell es la barra/panel habitual de Wayfire.
        collector.add_safe_file(
            "~/.config/wf-shell.ini",
            "shell",
            allowed_names=("wf-shell.ini",),
            allowed_suffixes=(".ini",),
            tag={"wf_shell": True},
        )
        collector.add_config_files(
            "~/.config/wayfire",
            "layout",
            allowed_suffixes=(".ini",),
            tag={"wayfire_config": True},
        )
        collect_ecosystem(collector)
        collector.meta.setdefault("keybinds", []).extend(state["binds"].values())

    def themes(self) -> dict[str, str]:
        values = gtk_values()
        cursor = values.get("gtk-cursor-theme-name", "")
        path = _config_path()
        if path.is_file():
            parsed = parse(path.read_text(errors="replace"))
            if parsed["cursor"]:
                cursor = parsed["cursor"]
        return {
            "icons": values.get("gtk-icon-theme-name", ""),
            "cursor": cursor,
            "gtk": values.get("gtk-theme-name", ""),
        }

    def preview_sources(self) -> list[Path]:
        path = _config_path()
        found: list[Path] = []
        if path.is_file():
            text = path.read_text(errors="replace")
            for candidate in parse(text)["wallpapers"]:
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
    from ..wayfire import keybinds_from_items as _from_items

    return _from_items(items, store)
