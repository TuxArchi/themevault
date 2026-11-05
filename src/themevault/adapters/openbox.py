"""Adaptador Openbox (X11)."""

from __future__ import annotations

from pathlib import Path

from ..ecosystem import collect_ecosystem, gtk_values, wallpapers_from_text, x11_wallpapers_from_text
from ..labwc import parse
from ..util import expand, xdg_config_home
from .base import Adapter, Collector


class OpenboxAdapter(Adapter):
    id = "openbox"
    label = "Openbox"
    priority = 23

    def _collect(self, collector: Collector) -> None:
        state = {"binds": {}, "cursor": "", "wallpapers": []}
        for name, category in (
            ("rc.xml", "layout"),
            ("menu.xml", "shell"),
            ("autostart", "layout"),
        ):
            path = xdg_config_home() / "openbox" / name
            item = collector.add_safe_file(
                path,
                category,
                allowed_names=(name,),
                allowed_suffixes=(".xml",),
                allow_no_extension=True,
                allow_shebang=True,
                tag={"openbox_config": True},
            )
            if item is None:
                continue
            try:
                text = collector.store.read(item.blob).decode("utf-8", "replace")
            except OSError:
                text = ""
            if name == "rc.xml":
                item.meta.update({"keybind_format": "labwc", "format_order": 0})
                parsed = parse(text, item.source or "")
                for entry in parsed["binds"]:
                    state["binds"][entry["combo"]] = entry
                state["cursor"] = parsed["cursor"]
                state["wallpapers"] = parsed["wallpapers"]
            elif name == "autostart":
                for candidate in wallpapers_from_text(text) + x11_wallpapers_from_text(text):
                    if candidate not in state["wallpapers"]:
                        state["wallpapers"].append(candidate)
        collector.meta.setdefault("keybinds", []).extend(state["binds"].values())
        collect_ecosystem(collector, shells=False)

    def themes(self) -> dict[str, str]:
        values = gtk_values()
        cursor = values.get("gtk-cursor-theme-name", "")
        rc = xdg_config_home() / "openbox" / "rc.xml"
        if rc.is_file():
            parsed = parse(rc.read_text(errors="replace"))
            if parsed["cursor"]:
                cursor = parsed["cursor"]
        return {
            "icons": values.get("gtk-icon-theme-name", ""),
            "cursor": cursor,
            "gtk": values.get("gtk-theme-name", ""),
        }

    def preview_sources(self) -> list[Path]:
        found: list[Path] = []
        autostart = xdg_config_home() / "openbox" / "autostart"
        if autostart.is_file():
            text = autostart.read_text(errors="replace")
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
    from ..labwc import keybinds_from_items as _from_items

    return _from_items(items, store)
