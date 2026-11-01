"""Adaptador KDE Plasma (5 y 6).

Plasma guarda casi todo en INI dentro de ~/.config, y los temas como arboles
en ~/.local/share. A diferencia de dconf no hace falta un backend especial:
copiar los archivos y reiniciar la sesion aplica los cambios.
"""

from __future__ import annotations

import configparser
from pathlib import Path

from ..util import expand, home, run, xdg_config_home
from .base import Adapter, Collector

CONFIG_FILES: tuple[tuple[str, str, str], ...] = (
    ("~/.config/kdeglobals", "theme", "kdeglobals"),
    ("~/.config/plasmarc", "theme", "plasmarc"),
    ("~/.config/kwinrc", "theme", "kwinrc"),
    ("~/.config/breezerc", "theme", "breezerc"),
    ("~/.config/ksplashrc", "theme", "ksplashrc"),
    ("~/.config/kcminputrc", "config", "kcminputrc"),
    ("~/.config/klauncherrc", "config", "klauncherrc"),
    ("~/.config/kdedefaults/kdeglobals", "theme", "kdedefaults/kdeglobals"),
    # Geometria de las barras: grosor, flotante y modo de visibilidad.
    ("~/.config/plasmashellrc", "layout", "plasmashellrc"),
    # Layout completo: paneles, widgets colocados, orden y ajustes de cada uno.
    ("~/.config/plasma-org.kde.plasma.desktop-appletsrc", "layout", "Layout de Plasma"),
)

DATA_TREES: tuple[tuple[str, str], ...] = (
    ("~/.local/share/color-schemes", "colorscheme"),
    ("~/.local/share/plasma/desktoptheme", "theme"),
    ("~/.local/share/plasma/look-and-feel", "theme"),
    ("~/.local/share/aurorae/themes", "theme"),
    ("~/.local/share/kwin/scripts", "shell"),
    ("~/.local/share/konsole", "colorscheme"),
    ("~/.config/Kvantum", "theme"),
    # Widgets que el usuario instalo (Discover / Obtener nuevos)
    ("~/.local/share/plasma/plasmoids", "layout"),
)


class KdeAdapter(Adapter):
    id = "kde"
    label = "KDE Plasma"
    priority = 10

    def _collect(self, collector: Collector) -> None:
        for raw, category, name in CONFIG_FILES:
            collector.add_file(raw, category, name)
        for raw, category in DATA_TREES:
            collector.add_children_as_trees(raw, category)

    def themes(self) -> dict[str, str]:
        return {
            "icons": _kde_value("kdeglobals", "Icons", "Theme"),
            "cursor": _kde_value("kcminputrc", "Mouse", "cursorTheme"),
            "plasma": _kde_value("plasmarc", "Theme", "name"),
            "color_scheme": _kde_value("kdeglobals", "General", "ColorScheme"),
            "gtk": _gtk_theme(),
        }

    def preview_sources(self) -> list[Path]:
        appletsrc = xdg_config_home() / "plasma-org.kde.plasma.desktop-appletsrc"
        found: list[Path] = []
        if appletsrc.exists():
            for line in appletsrc.read_text(errors="replace").splitlines():
                if not line.startswith("Image="):
                    continue
                raw = line.split("=", 1)[1].strip()
                if raw.startswith("file://"):
                    raw = raw[len("file://") :]
                candidate = Path(raw)
                if candidate.exists():
                    found.append(candidate)
        if not found:
            pictures = home() / "Pictures"
            if pictures.is_dir():
                for entry in sorted(pictures.iterdir()):
                    if entry.is_file() and entry.suffix.lower() in (".jpg", ".png", ".jpeg", ".webp"):
                        found.append(entry)
                        break
        return found


# ------------------------------------------------------------------- helpers


def _kde_value(filename: str, group: str, key: str) -> str:
    """Lee un valor de configuracion de KDE, con o sin kreadconfig."""
    for tool in ("kreadconfig6", "kreadconfig5"):
        proc = run([tool, "--file", filename, "--group", group, "--key", key])
        if proc is not None and proc.returncode == 0:
            value = proc.stdout.decode("utf-8", "replace").strip()
            if value:
                return value

    path = xdg_config_home() / filename
    if not path.is_file():
        return ""
    try:
        parser = configparser.RawConfigParser(strict=False)
        parser.optionxform = str
        parser.read_string(path.read_text(errors="replace"))
    except (OSError, configparser.Error):
        return ""
    if parser.has_option(group, key):
        return str(parser.get(group, key)).strip()
    return ""


def _gtk_theme() -> str:
    path = expand("~/.config/gtk-3.0/settings.ini")
    if not path.is_file():
        return ""
    try:
        parser = configparser.RawConfigParser(strict=False)
        parser.optionxform = str
        parser.read_string(path.read_text(errors="replace"))
    except (OSError, configparser.Error):
        return ""
    if parser.has_option("Settings", "gtk-theme-name"):
        return str(parser.get("Settings", "gtk-theme-name")).strip()
    return ""
