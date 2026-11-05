"""Adaptador LXQt."""

from __future__ import annotations

from pathlib import Path

from ..ecosystem import collect_ecosystem, gtk_values
from ..lxqt import keybindings, theme_values, wallpaper_from_settings
from ..util import expand, xdg_config_home
from .base import Adapter, Collector
from .dconf_helpers import fallback_wallpaper


class LxqtAdapter(Adapter):
    id = "lxqt"
    label = "LXQt"
    priority = 21

    def _collect(self, collector: Collector) -> None:
        added = collector.add_config_files(
            "~/.config/lxqt",
            "layout",
            allowed_suffixes=(".conf",),
            tag={"lxqt_config": True},
        )
        collector.add_safe_file(
            "~/.config/pcmanfm-qt/lxqt/settings.conf",
            "wallpaper",
            allowed_suffixes=(".conf",),
            tag={"lxqt_wallpaper": True},
        )
        collector.add_safe_file(
            "~/.config/openbox/lxqt-rc.xml",
            "layout",
            allowed_suffixes=(".xml",),
            tag={"lxqt_openbox": True},
        )
        for item in added:
            if item.name == "globalkeyshortcuts.conf" and item.blob:
                try:
                    text = collector.store.read(item.blob).decode("utf-8", "replace")
                except OSError:
                    continue
                item.meta["keybind_format"] = "lxqt"
                collector.meta.setdefault("keybinds", []).extend(
                    keybindings(text, item.source or "")
                )
        for raw, category in (
            ("~/.local/share/lxqt/themes", "theme"),
            ("~/.local/share/lxqt/palettes", "colorscheme"),
        ):
            collector.add_children_as_trees(raw, category)
        collect_ecosystem(collector, shells=False)

    def themes(self) -> dict[str, str]:
        values = gtk_values()
        found = {
            "icons": values.get("gtk-icon-theme-name", ""),
            "cursor": values.get("gtk-cursor-theme-name", ""),
            "gtk": values.get("gtk-theme-name", ""),
        }
        path = xdg_config_home() / "lxqt" / "lxqt.conf"
        if path.is_file():
            parsed = theme_values(path.read_text(errors="replace"))
            found["icons"] = parsed.get("icon_theme", found["icons"])
            found["theme"] = parsed.get("theme", parsed.get("style", ""))
            found["cursor"] = parsed.get("cursor_theme", found["cursor"])
        return found

    def preview_sources(self) -> list[Path]:
        path = expand("~/.config/pcmanfm-qt/lxqt/settings.conf")
        if path.is_file():
            candidate = wallpaper_from_settings(path.read_text(errors="replace"))
            if candidate is not None:
                return [candidate]
        return fallback_wallpaper()


def keybinds_from_items(items, store) -> list[dict]:
    from ..lxqt import keybinds_from_items as _from_items

    return _from_items(items, store)
