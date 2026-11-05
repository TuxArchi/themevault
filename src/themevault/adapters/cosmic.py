"""Adaptador COSMIC (System76)."""

from __future__ import annotations

from pathlib import Path

from ..cosmic import images_from_text, keybinds_from_items as _keybinds_from_items, shortcuts
from ..ecosystem import collect_ecosystem, gtk_values
from ..privacy import iter_config_files, read_config_text
from ..util import expand
from .base import Adapter, Collector

SHORTCUTS_SUFFIX = "com.system76.CosmicSettings.Shortcuts/v1/custom"


class CosmicAdapter(Adapter):
    id = "cosmic"
    label = "COSMIC"
    priority = 24

    def _collect(self, collector: Collector) -> None:
        added = collector.add_config_files(
            "~/.config/cosmic",
            "layout",
            allow_any_name=True,
            tag={"cosmic_config": True},
        )
        for item in added:
            source = item.source or ""
            if not source.endswith(SHORTCUTS_SUFFIX):
                continue
            try:
                text = collector.store.read(item.blob).decode("utf-8", "replace")
            except OSError:
                continue
            item.meta["keybind_format"] = "cosmic"
            collector.meta.setdefault("keybinds", []).extend(
                shortcuts(text, source)
            )
        collect_ecosystem(collector, shells=False)

    def themes(self) -> dict[str, str]:
        values = gtk_values()
        return {
            "icons": values.get("gtk-icon-theme-name", ""),
            "cursor": values.get("gtk-cursor-theme-name", ""),
            "gtk": values.get("gtk-theme-name", ""),
        }

    def preview_sources(self) -> list[Path]:
        found: list[Path] = []
        for candidate, reason in iter_config_files(
            "~/.config/cosmic", allow_any_name=True
        ):
            if reason:
                continue
            text, _reason = read_config_text(candidate, allow_any_name=True)
            if text is None:
                continue
            for image in images_from_text(text):
                if image not in found:
                    found.append(image)
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
    return _keybinds_from_items(items, store)
