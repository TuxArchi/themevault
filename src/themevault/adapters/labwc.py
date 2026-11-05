"""Adaptador labwc."""

from __future__ import annotations

from pathlib import Path

from ..ecosystem import collect_ecosystem, gtk_values, wallpapers_from_text
from ..labwc import parse
from ..util import expand, xdg_config_home
from .base import Adapter, Collector


def _config_dir() -> Path:
    return xdg_config_home() / "labwc"


class LabwcAdapter(Adapter):
    id = "labwc"
    label = "labwc"
    priority = 20

    def _collect(self, collector: Collector) -> None:
        state = {"binds": {}, "order": 0, "cursor": "", "wallpapers": []}
        paths = (
            ("rc.xml", "layout", "labwc"),
            ("menu.xml", "shell", "labwc"),
            ("autostart", "layout", "labwc"),
            ("environment", "layout", "labwc"),
            ("themerc", "theme", "labwc"),
        )
        for name, category, tag in paths:
            path = _config_dir() / name
            item = collector.add_safe_file(
                path,
                category,
                allowed_names=(name,),
                allow_no_extension=True,
                allow_shebang=True,
                tag={f"{tag}_config": True},
            )
            if item is None:
                continue
            if name == "rc.xml":
                item.meta.update({"keybind_format": "labwc", "format_order": 0})
                try:
                    text = collector.store.read(item.blob).decode("utf-8", "replace")
                except OSError:
                    text = ""
                parsed = parse(text, item.source or "")
                for entry in parsed["binds"]:
                    state["binds"][entry["combo"]] = entry
                state["cursor"] = parsed["cursor"]
                state["wallpapers"] = parsed["wallpapers"]
            elif name == "autostart":
                try:
                    text = collector.store.read(item.blob).decode("utf-8", "replace")
                except OSError:
                    text = ""
                for candidate in wallpapers_from_text(text):
                    if candidate not in state["wallpapers"]:
                        state["wallpapers"].append(candidate)

        collector.add_config_files(
            "~/.config/labwc",
            "layout",
            allowed_suffixes=(".xml", ".conf", ".ini"),
            tag={"labwc_config": True},
        )
        collect_ecosystem(collector)
        collector.meta.setdefault("keybinds", []).extend(state["binds"].values())

    def themes(self) -> dict[str, str]:
        values = gtk_values()
        cursor = values.get("gtk-cursor-theme-name", "")
        rc = _config_dir() / "rc.xml"
        if rc.is_file():
            parsed = parse(rc.read_text(errors="replace"))
            if parsed["cursor"]:
                cursor = parsed["cursor"]
        themerc = _config_dir() / "themerc"
        if themerc.is_file():
            for line in themerc.read_text(errors="replace").splitlines():
                key, _, value = line.partition("=")
                if key.strip().lower() in ("cursortheme", "cursor_theme"):
                    cursor = value.strip()
                    break
        return {
            "icons": values.get("gtk-icon-theme-name", ""),
            "cursor": cursor,
            "gtk": values.get("gtk-theme-name", ""),
        }

    def preview_sources(self) -> list[Path]:
        found: list[Path] = []
        autostart = _config_dir() / "autostart"
        if autostart.is_file():
            text = autostart.read_text(errors="replace")
            for candidate in wallpapers_from_text(text):
                if candidate not in found:
                    found.append(candidate)
        rc = _config_dir() / "rc.xml"
        if rc.is_file():
            for candidate in parse(rc.read_text(errors="replace"))["wallpapers"]:
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
