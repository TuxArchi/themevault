"""Configuración compartida del ecosistema Wayland.

Los compositores que soportamos comparten barras, lanzadores, notificaciones,
terminales, shells y utilidades. Esta lista se usa desde Hyprland, niri, Sway,
River, Wayfire y labwc para no duplicar la lista blanca en cada adaptador.
"""

from __future__ import annotations

import configparser
import re
from pathlib import Path

from .util import expand

# (ruta, categoría, nombres permitidos, extensiones permitidas)
COMMON_CONFIG_DIRS: tuple[tuple[str, str, tuple[str, ...], tuple[str, ...]], ...] = (
    ("~/.config/waybar", "layout", ("config", "config.jsonc"), (".json", ".jsonc", ".css", ".conf")),
    ("~/.config/wlogout", "layout", ("layout", "style.css"), (".json", ".css", ".conf")),
    ("~/.config/wofi", "shell", ("config",), (".css", ".conf", ".ini")),
    ("~/.config/rofi", "shell", ("config",), (".rasi", ".css", ".conf", ".ini")),
    ("~/.config/fuzzel", "shell", ("fuzzel.ini",), (".ini",)),
    ("~/.config/swaync", "shell", ("config",), (".json", ".css", ".conf")),
    ("~/.config/mako", "shell", ("config",), (".conf", ".ini")),
    ("~/.config/dunst", "shell", ("dunstrc",), (".conf",)),
    ("~/.config/kitty", "config", (), (".conf",)),
    ("~/.config/alacritty", "config", ("alacritty.toml",), (".toml", ".yml", ".yaml")),
    ("~/.config/foot", "config", ("foot.ini",), (".ini",)),
    ("~/.config/ghostty", "config", ("config",), (".conf",)),
    ("~/.config/qt5ct", "theme", ("qt5ct.conf",), (".conf",)),
    ("~/.config/qt6ct", "theme", ("qt6ct.conf",), (".conf",)),
    ("~/.config/Kvantum", "theme", ("kvantum.kvconfig",), (".kvconfig",)),
    ("~/.config/xsettingsd", "theme", ("xsettingsd.conf",), (".conf",)),
    ("~/.local/share/color-schemes", "colorscheme", (), (".colors",)),
)

SHELL_SUFFIXES = (
    ".qml",
    ".js",
    ".ts",
    ".json",
    ".jsonc",
    ".css",
    ".scss",
    ".toml",
    ".yaml",
    ".yml",
    ".kdl",
    ".conf",
    ".ini",
)

# Shells de escritorio que se usan con varios compositores.
SHELL_CONFIG_DIRS: tuple[tuple[str, str, tuple[str, ...], tuple[str, ...]], ...] = (
    ("~/.config/noctalia", "shell", (), (".toml", ".json", ".css")),
    ("~/.local/state/noctalia", "shell", ("settings.toml",), (".toml",)),
    ("~/.config/DankMaterialShell", "shell", (), (".json", ".css", ".conf", ".toml")),
    ("~/.config/quickshell", "shell", (), SHELL_SUFFIXES),
    ("~/.config/ags", "shell", (), SHELL_SUFFIXES),
)

WALLPAPER_RE = re.compile(
    r"(?:swaybg[^\n]*?(?:-i|--image)|swww\s+img|wbg|mpvpaper[^\n]*?)\s+[\"']?([^\"'\s]+)",
    re.IGNORECASE,
)

X11_WALLPAPER_RE = re.compile(
    r"(?:feh[^\n]*?|nitrogen[^\n]*?|xwallpaper[^\n]*?|hsetroot[^\n]*?)\s+[\"']?([^\"'\s]+)",
    re.IGNORECASE,
)

IMAGE_PATH_RE = re.compile(
    r"((?:~|/)[^\s\"'\n]+?\.(?:png|jpe?g|webp|avif))",
    re.IGNORECASE,
)


def gtk_values() -> dict[str, str]:
    path = expand("~/.config/gtk-3.0/settings.ini")
    if not path.is_file():
        return {}
    parser = configparser.RawConfigParser(strict=False)
    parser.optionxform = str
    try:
        parser.read_string(path.read_text(errors="replace"))
    except (OSError, configparser.Error):
        return {}
    if not parser.has_section("Settings"):
        return {}
    return {key: str(value).strip() for key, value in parser.items("Settings")}


def themes_from_gtk() -> dict[str, str]:
    values = gtk_values()
    return {
        "icons": values.get("gtk-icon-theme-name", ""),
        "cursor": values.get("gtk-cursor-theme-name", ""),
        "gtk": values.get("gtk-theme-name", ""),
    }


def collect_ecosystem(collector, *, shells: bool = True) -> None:
    """Recolecta apps y shells compartidas por todos los compositores."""
    dirs = COMMON_CONFIG_DIRS + (SHELL_CONFIG_DIRS if shells else ())
    for raw, category, names, suffixes in dirs:
        added = collector.add_config_files(
            raw,
            category,
            allowed_names=names,
            allowed_suffixes=suffixes,
        )
        if raw == "~/.config/waybar":
            for item in added:
                if item.name in ("config", "config.jsonc"):
                    item.meta["waybar_config"] = True


def wallpapers_from_text(text: str) -> list[Path]:
    """Busca fondos en comandos de autostart tipo swaybg/swww/wbg."""
    found: list[Path] = []
    for match in WALLPAPER_RE.finditer(text):
        raw = match.group(1).strip().strip("'\"")
        if not raw or raw.startswith("-"):
            continue
        candidate = expand(raw)
        if candidate.is_file() and candidate not in found:
            found.append(candidate)
    for match in IMAGE_PATH_RE.finditer(text):
        candidate = expand(match.group(1))
        if candidate.is_file() and candidate not in found:
            found.append(candidate)
    return found


def x11_wallpapers_from_text(text: str) -> list[Path]:
    """Busca fondos en comandos de X11: feh, nitrogen, xwallpaper, hsetroot."""
    found: list[Path] = []
    for match in X11_WALLPAPER_RE.finditer(text):
        raw = match.group(1).strip().strip("'\"")
        if not raw or raw.startswith("-"):
            continue
        candidate = expand(raw)
        if candidate.is_file() and candidate not in found:
            found.append(candidate)
    for match in IMAGE_PATH_RE.finditer(text):
        candidate = expand(match.group(1))
        if candidate.is_file() and candidate not in found:
            found.append(candidate)
    return found


def images_from_text(text: str) -> list[Path]:
    """Busca rutas de imagen existentes dentro de configuraciones RON/JSON."""
    found: list[Path] = []
    for match in IMAGE_PATH_RE.finditer(text):
        candidate = expand(match.group(1))
        if candidate.is_file() and candidate not in found:
            found.append(candidate)
    return found
