"""Adaptador Cinnamon (Linux Mint y derivados)."""

from __future__ import annotations

from pathlib import Path

from ..drivers import dconf_available
from ..ecosystem import collect_ecosystem
from .base import Adapter, Collector
from .dconf_helpers import collect_bindings, fallback_wallpaper, themes_from, uri_to_path

DCONF_PATHS: tuple[tuple[str, str, str], ...] = (
    ("/org/cinnamon/desktop/interface/", "theme", "Apariencia Cinnamon"),
    ("/org/cinnamon/desktop/background/", "wallpaper", "Fondo de escritorio"),
    ("/org/cinnamon/desktop/wm/preferences/", "theme", "Ventanas"),
    ("/org/cinnamon/theme/", "theme", "Tema Cinnamon"),
    ("/org/cinnamon/desktop/keybindings/", "config", "Atajos Cinnamon"),
)

CONFIG_TREES: tuple[tuple[str, str], ...] = (
    ("~/.local/share/cinnamon/applets", "shell"),
    ("~/.local/share/cinnamon/desklets", "shell"),
    ("~/.local/share/cinnamon/extensions", "shell"),
    ("~/.cinnamon/configs", "layout"),
)


class CinnamonAdapter(Adapter):
    id = "cinnamon"
    label = "Cinnamon"
    priority = 12

    def _collect(self, collector: Collector) -> None:
        if dconf_available():
            for path, category, name in DCONF_PATHS:
                if path.endswith("keybindings/"):
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
                ("org.cinnamon.desktop.interface", "icon-theme"),
                ("org.cinnamon.desktop.interface", "cursor-theme"),
                ("org.cinnamon.desktop.interface", "gtk-theme"),
                ("org.cinnamon.theme", "name"),
            ]
        )

    def preview_sources(self) -> list[Path]:
        from .dconf_helpers import gsetting

        for schema, key in (
            ("org.cinnamon.desktop.background", "picture-uri-dark"),
            ("org.cinnamon.desktop.background", "picture-uri"),
        ):
            candidate = uri_to_path(gsetting(schema, key))
            if candidate is not None:
                return [candidate]
        return fallback_wallpaper()
