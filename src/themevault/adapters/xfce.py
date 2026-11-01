"""Adaptador XFCE.

xfconf no expone un dump plano: se parsea el XML del canal (que trae tipo y
valor) y se restaura propiedad por propiedad con xfconf-query, sin reiniciar
la sesion.
"""

from __future__ import annotations

from pathlib import Path

from ..drivers import read_channel, xfconf_available
from .base import Adapter, Collector

CHANNELS: tuple[tuple[str, str], ...] = (
    ("xsettings", "theme"),      # tema GTK, iconos, cursor, fuentes
    ("xfwm4", "theme"),          # decoracion de ventanas
    ("xfce4-desktop", "wallpaper"),
    ("thunar", "config"),
    ("xfce4-panel", "config"),
    ("xfce4-power-manager", "config"),
    ("keyboard-layout", "config"),
)

CONFIG_FILES: tuple[tuple[str, str, str], ...] = (
    ("~/.config/xfce4/terminal/terminalrc", "colorscheme", "terminalrc"),
    ("~/.config/xfce4/xfconf/xfconfd/xfconf-perchannel-xml/xsettings.xml", "theme", "xsettings.xml"),
    # Paneles: tamano, posicion, ocultado automatico y plugins colocados.
    ("~/.config/xfce4/xfconf/xfconfd/xfconf-perchannel-xml/xfce4-panel.xml", "layout", "xfce4-panel.xml"),
    ("~/.config/xfce4/xfconf/xfconf-perchannel-xml/xfce4-panel.xml", "layout", "xfce4-panel.xml"),
)


class XfceAdapter(Adapter):
    id = "xfce"
    label = "Xfce"
    priority = 20

    def _collect(self, collector: Collector) -> None:
        if not xfconf_available():
            collector.skipped.append(("xfconf", "xfconf-query no esta instalado"))
        for channel, category in CHANNELS:
            props, skipped = read_channel(channel)
            if not props:
                continue
            for prop in props:
                collector.add_setting(
                    category,
                    f"{channel}:{prop['prop']}",
                    backend="xfconf",
                    data=prop,
                )
            if skipped:
                collector.skipped.append(
                    (f"canal {channel}", f"{skipped} propiedades de tipo array omitidas")
                )

        for raw, category, name in CONFIG_FILES:
            collector.add_file(raw, category, name)

    def themes(self) -> dict[str, str]:
        props, _ = read_channel("xsettings")
        values = {prop["prop"]: prop["value"] for prop in props}
        return {
            "icons": values.get("/Net/IconThemeName", ""),
            "cursor": values.get("/Gtk/CursorThemeName", ""),
            "gtk": values.get("/Net/ThemeName", ""),
        }

    def preview_sources(self) -> list[Path]:
        props, _ = read_channel("xfce4-desktop")
        found: list[Path] = []
        for prop in props:
            if not prop["prop"].endswith("/last-image"):
                continue
            candidate = Path(prop["value"])
            if candidate.exists():
                found.append(candidate)
        return found


def _parse_position(raw: str) -> tuple[int | None, int | None]:
    """'p=6;x=960;y=1066' -> (960, 1066)."""
    values: dict[str, int] = {}
    for chunk in (raw or "").split(";"):
        key, _, value = chunk.partition("=")
        try:
            values[key.strip()] = int(value.strip())
        except ValueError:
            continue
    return values.get("x"), values.get("y")
