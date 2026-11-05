"""Adaptador Hyprland y su ecosistema.

Hyprland es un compositor Wayland que guarda toda la personalización en
archivos de texto. El respaldo es deliberadamente restrictivo: solo se copian
archivos de configuración de una lista blanca. Fotos, wallpapers, documentos,
scripts y credenciales quedan fuera.

Los atajos de teclado se interpretan (sin ejecutarlos) y se guardan en el
manifest para mostrarlos en la app; al restaurar se recuperan sus archivos.
"""

from __future__ import annotations

import configparser
import re
from pathlib import Path

from ..ecosystem import collect_ecosystem
from ..hypr import (
    SOURCE_SUFFIXES,
    HyprState,
    feed_text,
    source_paths,
    split_comment,
)
from ..privacy import iter_config_files, read_config_text
from ..util import expand, home, is_within, to_portable
from .base import Adapter, Collector

# Solo configuración de Hyprland. Los scripts no entran.
HYPR_SUFFIXES = (".conf",)

SETCURSOR_RE = re.compile(
    r"hyprctl\s+setcursor\s+([^\s,]+)(?:\s+(\d+))?", re.IGNORECASE
)
ENV_CURSOR_RE = re.compile(r"XCURSOR_THEME\s*,\s*([^\s,]+)", re.IGNORECASE)
ENV_GTK_RE = re.compile(r"GTK_THEME\s*,\s*([^\s,]+)", re.IGNORECASE)


def _gtk_values() -> dict[str, str]:
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


def _text_of(path: Path) -> str:
    text, _reason = read_config_text(path, allowed_suffixes=frozenset(HYPR_SUFFIXES))
    return text or ""


def _hypr_texts() -> list[str]:
    """Texto de los .conf seguros dentro de ~/.config/hypr."""
    found: list[str] = []
    for candidate, reason in iter_config_files(
        "~/.config/hypr", allowed_suffixes=frozenset(HYPR_SUFFIXES)
    ):
        if reason:
            continue
        text = _text_of(candidate)
        if text:
            found.append(text)
    return found


def _path_from_value(value: str) -> Path | None:
    raw = value.strip().strip("'\"")
    if not raw:
        return None
    # En `wallpaper = monitor,ruta` la ruta está después de la coma.
    if "," in raw:
        raw = raw.rsplit(",", 1)[-1].strip()
    candidate = expand(raw)
    if candidate.is_file():
        return candidate
    return None


def _wallpapers_from_text(text: str) -> list[Path]:
    found: list[Path] = []
    in_wallpaper_block = False

    for raw in text.splitlines():
        content, _comment = split_comment(raw)
        if not content:
            continue
        lower = content.lower()
        if lower.startswith("wallpaper") and "{" in content:
            in_wallpaper_block = True
            continue
        if in_wallpaper_block and content.strip() == "}":
            in_wallpaper_block = False
            continue

        for key in ("preload", "wallpaper", "path", "image", "background"):
            if not lower.startswith(key):
                continue
            _, _, value = content.partition("=")
            if not value:
                continue
            candidate = _path_from_value(value)
            if candidate is not None and candidate not in found:
                found.append(candidate)

        # `exec-once = swaybg -i ~/fondo.png`
        for match in re.finditer(r"(?:swaybg[^\n]*?)(?:-i|--image)\s+([^\s'\"]+)", content):
            candidate = _path_from_value(match.group(1))
            if candidate is not None and candidate not in found:
                found.append(candidate)

    return found


class HyprlandAdapter(Adapter):
    id = "hyprland"
    label = "Hyprland"
    priority = 15

    # -------------------------------------------------------------- recoleccion

    def _collect(self, collector: Collector) -> None:
        state = HyprState()
        visited: set[Path] = set()
        main = expand("~/.config/hypr/hyprland.conf")

        if main.is_file():
            self._parse_file(main, collector, state, visited, 0)

        # Archivos del directorio principal que no se alcanzaron por `source`.
        collector.add_config_files(
            "~/.config/hypr",
            "layout",
            allowed_suffixes=HYPR_SUFFIXES,
            tag={"hypr_config": True},
        )

        # Apps y shells compartidas por todos los compositores Wayland.
        collect_ecosystem(collector)

        # Si no hay hyprland.conf, igual intentamos leer los .conf presentes.
        if not main.is_file():
            collected = [
                item
                for item in collector.items
                if (item.meta or {}).get("hypr_config") and item.blob
            ]
            collected.sort(key=lambda item: item.source or "")
            for item in collected:
                try:
                    text = collector.store.read(item.blob).decode("utf-8", "replace")
                except OSError:
                    continue
                item.meta["hypr"] = True
                item.meta["keybind_format"] = "hypr"
                feed_text(state, text, item.source or "")

        collector.meta.setdefault("keybinds", []).extend(state.binds)

    def _parse_file(
        self,
        path: Path,
        collector: Collector,
        state: HyprState,
        visited: set[Path],
        depth: int,
    ) -> None:
        if depth > 8:
            collector.skipped.append((str(path), "demasiados niveles de source"))
            return

        try:
            resolved = path.resolve()
        except OSError:
            collector.skipped.append((str(path), "no se pudo resolver la ruta"))
            return
        if resolved in visited:
            return
        if not is_within(resolved, home()):
            collector.skipped.append((str(path), "source fuera del home"))
            return
        original_suffix = path.suffix.lower()
        resolved_suffix = resolved.suffix.lower()
        if original_suffix and original_suffix not in SOURCE_SUFFIXES:
            collector.skipped.append((str(path), "source no es configuración permitida"))
            return
        if resolved_suffix and resolved_suffix not in SOURCE_SUFFIXES:
            collector.skipped.append((str(path), "source no es configuración permitida"))
            return
        if not original_suffix and not resolved_suffix:
            collector.skipped.append((str(path), "source sin extensión reconocida"))
            return

        text, reason = read_config_text(
            resolved,
            allowed_names=frozenset({path.name.lower(), resolved.name.lower()}),
            allowed_suffixes=frozenset(SOURCE_SUFFIXES),
        )
        if text is None:
            collector.skipped.append((str(path), reason))
            return

        item = collector.add_file(resolved, "layout")
        if item is None:
            return
        visited.add(resolved)
        item.meta.update(
            {
                "hypr": True,
                "hypr_config": True,
                "hypr_order": len(visited),
                "keybind_format": "hypr",
            }
        )

        def on_source(raw: str) -> None:
            for candidate in source_paths(raw, resolved.parent, state.variables):
                self._parse_file(candidate, collector, state, visited, depth + 1)

        feed_text(state, text, to_portable(resolved), on_source=on_source)

    # ------------------------------------------------------------------ previa

    def themes(self) -> dict[str, str]:
        values = _gtk_values()
        texts = _hypr_texts()
        cursor = values.get("gtk-cursor-theme-name", "")

        for text in texts:
            active = "\n".join(split_comment(line)[0] for line in text.splitlines())
            match = ENV_CURSOR_RE.search(active) or SETCURSOR_RE.search(active)
            if match:
                cursor = match.group(1)
                break
        gtk = values.get("gtk-theme-name", "")
        for text in texts:
            active = "\n".join(split_comment(line)[0] for line in text.splitlines())
            match = ENV_GTK_RE.search(active)
            if match:
                gtk = match.group(1).split(":", 1)[0]
                break

        return {
            "icons": values.get("gtk-icon-theme-name", ""),
            "cursor": cursor,
            "gtk": gtk,
        }

    def preview_sources(self) -> list[Path]:
        found: list[Path] = []
        for name in ("hyprpaper.conf", "hyprlock.conf"):
            path = expand(f"~/.config/hypr/{name}")
            if not path.is_file():
                continue
            for candidate in _wallpapers_from_text(_text_of(path)):
                if candidate not in found:
                    found.append(candidate)

        for text in _hypr_texts():
            for candidate in _wallpapers_from_text(text):
                if candidate not in found:
                    found.append(candidate)

        if found:
            return found

        # Fallback: la primera imagen de las carpetas típicas.
        for raw in ("~/Pictures/Wallpapers", "~/Pictures", "~/Imágenes"):
            folder = expand(raw)
            if not folder.is_dir():
                continue
            for entry in sorted(folder.iterdir()):
                if entry.is_file() and entry.suffix.lower() in (
                    ".jpg",
                    ".jpeg",
                    ".png",
                    ".webp",
                ):
                    return [entry]
        return []
