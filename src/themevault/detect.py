"""Deteccion del sistema: distro, escritorio, sesion y activos instalados."""

from __future__ import annotations

import os
from pathlib import Path

from .util import home, xdg_data_home

# Normaliza los valores de XDG_CURRENT_DESKTOP / DESKTOP_SESSION.
_DE_ALIASES = {
    "gnome": "gnome",
    "gnome-classic": "gnome",
    "gnome-flashback": "gnome",
    "ubuntu": "gnome",
    "unity": "gnome",
    "kde": "kde",
    "plasma": "kde",
    "xfce": "xfce",
    "x-cinnamon": "cinnamon",
    "cinnamon": "cinnamon",
    "mate": "mate",
    "budgie": "budgie",
    "budgie-desktop": "budgie",
    "lxqt": "lxqt",
    "lxde": "lxde",
    "pantheon": "pantheon",
    "deepin": "deepin",
    "cosmic": "cosmic",
    "sway": "sway",
    "scroll": "sway",
    "hyprland": "hyprland",
    "niri": "niri",
    "river": "river",
    "wayfire": "wayfire",
    "labwc": "labwc",
    "i3": "i3",
    "openbox": "openbox",
}


def _read_os_release() -> dict[str, str]:
    data: dict[str, str] = {}
    for path in (Path("/etc/os-release"), Path("/usr/lib/os-release")):
        if not path.exists():
            continue
        for line in path.read_text(errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            data[key.strip()] = value.strip().strip('"').strip("'")
        break
    return data


def detect_distro() -> dict[str, str]:
    info = _read_os_release()
    return {
        "id": info.get("ID", "desconocida"),
        "name": info.get("NAME", info.get("ID", "Desconocida")),
        "version": info.get("VERSION_ID", ""),
        "pretty": info.get("PRETTY_NAME", info.get("NAME", "Desconocida")),
        "family": info.get("ID_LIKE", ""),
    }


def _desktop_candidates() -> list[str]:
    raw: list[str] = []
    for var in ("XDG_CURRENT_DESKTOP", "XDG_SESSION_DESKTOP", "DESKTOP_SESSION"):
        value = os.environ.get(var, "")
        if value:
            raw.extend(part for part in value.split(":") if part)
    return [part.strip().lower() for part in raw]


def detect_de() -> str:
    """Devuelve un identificador interno: gnome, kde, xfce, ...

    Si las variables de entorno no dicen nada (p.ej. ejecutando por SSH),
    se adivina por la presencia de directorios de configuracion.
    """
    for candidate in _desktop_candidates():
        if candidate in _DE_ALIASES:
            return _DE_ALIASES[candidate]

    probes = (
        ("hyprland", home() / ".config" / "hypr" / "hyprland.conf"),
        ("niri", home() / ".config" / "niri" / "config.kdl"),
        ("sway", home() / ".config" / "sway" / "config"),
        ("river", home() / ".config" / "river" / "init"),
        ("wayfire", home() / ".config" / "wayfire.ini"),
        ("labwc", home() / ".config" / "labwc" / "rc.xml"),
        ("kde", xdg_data_home() / "plasma" / "desktoptheme"),
        ("kde", home() / ".config" / "plasma-org.kde.plasma.desktop-appletsrc"),
        ("gnome", xdg_data_home() / "gnome-shell" / "extensions"),
        ("xfce", home() / ".config" / "xfce4" / "xfconf"),
        ("cinnamon", home() / ".config" / "cinnamon"),
    )
    for de, probe in probes:
        if probe.exists():
            return de
    return "desconocido"


def detect_session() -> str:
    kind = os.environ.get("XDG_SESSION_TYPE", "")
    if kind:
        return kind
    if os.environ.get("WAYLAND_DISPLAY"):
        return "wayland"
    if os.environ.get("DISPLAY"):
        return "x11"
    return "desconocida"


def detect_host() -> dict:
    return {
        "distro": detect_distro(),
        "de": detect_de(),
        "session": detect_session(),
        "desktop_env": os.environ.get("XDG_CURRENT_DESKTOP", ""),
        "assets": scan_system_assets(),
    }


# --------------------------------------------------------------------- activos

ASSET_DIRS = {
    "themes": (
        "~/.themes",
        "~/.local/share/themes",
        "/usr/share/themes",
        "/usr/local/share/themes",
    ),
    "icons": (
        "~/.icons",
        "~/.local/share/icons",
        "/usr/share/icons",
        "/usr/local/share/icons",
    ),
}


def scan_system_assets() -> dict[str, list[str]]:
    """Lista los nombres de temas/iconos disponibles en el sistema.

    Sirve para avisar al restaurar en otra maquina: si un tema se referencia
    pero no existe, la copia no se puede aplicar al 100%.
    """
    from .util import expand

    assets: dict[str, list[str]] = {}
    for kind, dirs in ASSET_DIRS.items():
        names: set[str] = set()
        for raw in dirs:
            directory = expand(raw)
            if not directory.is_dir():
                continue
            for entry in directory.iterdir():
                if entry.is_dir() and not entry.name.startswith("."):
                    names.add(entry.name)
        assets[kind] = sorted(names)
    return assets
