"""Adaptador GNOME (y derivados que usan dconf: Ubuntu, Pop!_OS...)."""

from __future__ import annotations

from pathlib import Path

from ..drivers import dconf_available, gsettings_get
from ..util import expand
from .base import Adapter, Collector

# Ramas de dconf relevantes para la apariencia. Se guardan como volcado de
# texto: es atomico, legible y se restaura con `dconf load`.
DCONF_PATHS: tuple[tuple[str, str, str], ...] = (
    ("/org/gnome/desktop/interface/", "theme", "Apariencia GNOME"),
    ("/org/gnome/desktop/background/", "wallpaper", "Fondo de escritorio"),
    ("/org/gnome/desktop/screensaver/", "wallpaper", "Fondo del protector"),
    ("/org/gnome/desktop/wm/preferences/", "theme", "Ventanas"),
    ("/org/gnome/mutter/", "theme", "Mutter"),
    ("/org/gnome/desktop/notifications/", "config", "Notificaciones"),
    ("/org/gnome/shell/", "shell", "Shell"),
    ("/org/gnome/shell/extensions/user-theme/", "shell", "Tema del shell"),
    # Configuracion propia de los docks/paneles extendidos.
    ("/org/gnome/shell/extensions/dash-to-dock/", "shell", "Dock (dash-to-dock)"),
    ("/org/gnome/shell/extensions/ubuntu-dock/", "shell", "Dock (ubuntu-dock)"),
    ("/org/gnome/shell/extensions/dash-to-panel/", "shell", "Panel (dash-to-panel)"),
)

# Extensiones de shell instaladas por el usuario.
SHELL_DIRS: tuple[tuple[str, str], ...] = (
    ("~/.local/share/gnome-shell/extensions", "shell"),
    ("~/.local/share/themes", "theme"),
)


def _uri_to_path(value: str | None) -> Path | None:
    if not value:
        return None
    raw = value.strip().strip("'\"")
    if raw.startswith("file://"):
        raw = raw[len("file://") :]
    path = Path(raw)
    return path if path.exists() else None


class GnomeAdapter(Adapter):
    id = "gnome"
    label = "GNOME"
    priority = 10

    def _collect(self, collector: Collector) -> None:
        if dconf_available():
            for path, category, name in DCONF_PATHS:
                collector.add_dconf(path, category, name)
        else:
            collector.skipped.append(("dconf", "dconf no esta instalado"))

        collector.add_children_as_trees("~/.local/share/gnome-shell/extensions", "shell")
        collector.add_file("~/.config/gtk-4.0/gtk.css", "theme", "GTK4 CSS")

    def themes(self) -> dict[str, str]:
        def read(key: str) -> str:
            value = gsettings_get("org.gnome.desktop.interface", key) or ""
            return value.strip().strip("'\"")

        return {
            "icons": read("icon-theme"),
            "cursor": read("cursor-theme"),
            "gtk": read("gtk-theme"),
            "color_scheme": read("color-scheme"),
        }

    def preview_sources(self) -> list[Path]:
        found: list[Path] = []
        for schema, key in (
            ("org.gnome.desktop.background", "picture-uri-dark"),
            ("org.gnome.desktop.background", "picture-uri"),
        ):
            path = _uri_to_path(gsettings_get(schema, key))
            if path is not None:
                found.append(path)
        # Fallback: los wallpapers que trae el sistema se pueden reconocer por nombre
        for entry in sorted(expand("/usr/share/backgrounds").glob("*")):
            if entry.is_file() and entry.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
                found.append(entry)
                break
        return found
