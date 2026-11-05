"""Adaptador Budgie."""

from __future__ import annotations

from pathlib import Path

from ..drivers import dconf_available
from ..ecosystem import collect_ecosystem
from .base import Adapter, Collector
from .dconf_helpers import collect_bindings, fallback_wallpaper, gsetting, themes_from, uri_to_path

DCONF_PATHS: tuple[tuple[str, str, str], ...] = (
    ("/org/gnome/desktop/interface/", "theme", "Apariencia Budgie"),
    ("/org/gnome/desktop/background/", "wallpaper", "Fondo de escritorio"),
    ("/org/gnome/desktop/wm/keybindings/", "config", "Atajos de ventanas"),
    ("/org/gnome/settings-daemon/plugins/media-keys/", "config", "Atajos multimedia"),
    ("/com/solus-project/budgie-panel/", "layout", "Panel Budgie"),
    ("/org/budgie-desktop/", "theme", "Budgie"),
)

CONFIG_TREES: tuple[tuple[str, str], ...] = (
    ("~/.local/share/budgie-desktop", "shell"),
)


class BudgieAdapter(Adapter):
    id = "budgie"
    label = "Budgie"
    priority = 12

    def _collect(self, collector: Collector) -> None:
        if dconf_available():
            for path, category, name in DCONF_PATHS:
                if "keybindings" in path or "media-keys" in path:
                    collect_bindings(collector, path, category, name)
                else:
                    collector.add_dconf(path, category, name)
        else:
            collector.skipped.append(("dconf", "dconf no esta instalado"))
        for raw, category in CONFIG_TREES:
            collector.add_children_as_trees(raw, category)
        collect_ecosystem(collector, shells=False)

    def themes(self) -> dict[str, str]:
        return themes_from(
            [
                ("org.gnome.desktop.interface", "icon-theme"),
                ("org.gnome.desktop.interface", "cursor-theme"),
                ("org.gnome.desktop.interface", "gtk-theme"),
            ]
        )

    def preview_sources(self) -> list[Path]:
        for schema, key in (
            ("org.gnome.desktop.background", "picture-uri-dark"),
            ("org.gnome.desktop.background", "picture-uri"),
        ):
            candidate = uri_to_path(gsetting(schema, key))
            if candidate is not None:
                return [candidate]
        return fallback_wallpaper()
