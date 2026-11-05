"""Ayudas para escritorios basados en dconf."""

from __future__ import annotations

from pathlib import Path

from ..dconf_keys import parse
from ..drivers import gsettings_get
from ..ecosystem import gtk_values
from ..util import expand


def collect_bindings(collector, path: str, category: str = "config", name: str = "Atajos"):
    item = collector.add_dconf(path, category, name)
    if item is None:
        return None
    item.meta["keybind_format"] = "dconf"
    try:
        text = collector.store.read(item.blob).decode("utf-8", "replace")
    except OSError:
        return item
    entries = parse(text, f"dconf:{path}")
    if entries:
        collector.meta.setdefault("keybinds", []).extend(entries)
    return item


def gsetting(schema: str, key: str) -> str:
    value = gsettings_get(schema, key) or ""
    return value.strip().strip("'\"")


def themes_from(keys: list[tuple[str, str]]) -> dict[str, str]:
    values = gtk_values()
    found: dict[str, str] = {
        "icons": values.get("gtk-icon-theme-name", ""),
        "cursor": values.get("gtk-cursor-theme-name", ""),
        "gtk": values.get("gtk-theme-name", ""),
    }
    for schema, key in keys:
        value = gsetting(schema, key)
        if not value:
            continue
        if key in ("icon-theme", "icon_theme"):
            found["icons"] = value
        elif key in ("cursor-theme", "cursor_theme"):
            found["cursor"] = value
        elif key in ("gtk-theme", "gtk_theme"):
            found["gtk"] = value
        elif key in ("name", "theme"):
            found["theme"] = value
    return found


def uri_to_path(value: str) -> Path | None:
    raw = (value or "").strip().strip("'\"")
    if raw.startswith("file://"):
        raw = raw[len("file://") :]
    if not raw:
        return None
    candidate = expand(raw)
    return candidate if candidate.is_file() else None


def fallback_wallpaper() -> list[Path]:
    for raw in (
        "~/Pictures/Wallpapers",
        "~/Pictures",
        "~/Imágenes",
        "~/Imagenes",
        "~/Fondos",
    ):
        folder = expand(raw)
        if not folder.is_dir():
            continue
        for entry in sorted(folder.iterdir()):
            if entry.is_file() and entry.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
                return [entry]
    return []

