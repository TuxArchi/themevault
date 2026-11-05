"""Adaptador MATE."""

from __future__ import annotations

from pathlib import Path

from ..drivers import dconf_available
from ..ecosystem import collect_ecosystem
from .base import Adapter, Collector
from .dconf_helpers import collect_bindings, fallback_wallpaper, gsetting, themes_from, uri_to_path

DCONF_PATHS: tuple[tuple[str, str, str], ...] = (
    ("/org/mate/desktop/interface/", "theme", "Apariencia MATE"),
    ("/org/mate/desktop/background/", "wallpaper", "Fondo de escritorio"),
    ("/org/mate/marco/window-keybindings/", "config", "Atajos de ventanas"),
    ("/org/mate/marco/global-keybindings/", "config", "Atajos globales"),
    ("/org/mate/desktop/keybindings/", "config", "Atajos personalizados"),
)

CONFIG_TREES: tuple[tuple[str, str], ...] = (
    ("~/.local/share/mate-panel/applets", "shell"),
    ("~/.local/share/mate/applets", "shell"),
)


class MateAdapter(Adapter):
    id = "mate"
    label = "MATE"
    priority = 12

    def _collect(self, collector: Collector) -> None:
        if dconf_available():
            for path, category, name in DCONF_PATHS:
                if "keybindings" in path:
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
                ("org.mate.interface", "icon-theme"),
                ("org.mate.interface", "gtk-theme"),
                ("org.mate.peripherals-mouse", "cursor-theme"),
            ]
        )

    def preview_sources(self) -> list[Path]:
        for schema, key in (
            ("org.mate.background", "picture-filename"),
            ("org.mate.background", "picture-uri"),
        ):
            candidate = uri_to_path(gsetting(schema, key))
            if candidate is not None:
                return [candidate]
        return fallback_wallpaper()
