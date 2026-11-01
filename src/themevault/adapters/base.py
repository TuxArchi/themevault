"""Base de los adaptadores por entorno de escritorio.

Un adaptador solo declara: como detectarse, que recoger y de donde sale el
fondo de pantalla para la portada. Toda la mecanica (blobs, manifest,
restauracion) vive en el core y no necesita saber de GNOME ni de KDE.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from ..detect import detect_de
from ..model import (
    KIND_DCONF,
    KIND_FILE,
    KIND_SETTING,
    KIND_TREE,
    Item,
)
from ..store import BlobStore
from ..util import expand, to_portable

MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_TREE_BYTES = 512 * 1024 * 1024


def dir_size(path: Path) -> int:
    total = 0
    for entry in path.rglob("*"):
        try:
            if entry.is_file() and not entry.is_symlink():
                total += entry.stat().st_size
        except OSError:
            continue
    return total


class Collector:
    """Acumula items y escribe los blobs en la copia en curso."""

    def __init__(self, store: BlobStore):
        self.store = store
        self.items: list[Item] = []
        self.skipped: list[tuple[str, str]] = []

    # ------------------------------------------------------------ primitivas

    def add_file(
        self,
        path: str | Path,
        category: str,
        name: str | None = None,
        requires: Iterable[str] = (),
    ) -> Item | None:
        src = expand(path)
        if not src.is_file():
            return None
        try:
            size = src.stat().st_size
        except OSError:
            return None
        if size > MAX_FILE_BYTES:
            self.skipped.append((str(src), "archivo demasiado grande"))
            return None
        try:
            blob, sha, stored = self.store.put_file(src)
        except OSError as exc:
            self.skipped.append((str(src), f"error de lectura: {exc}"))
            return None
        item = Item(
            kind=KIND_FILE,
            category=category,
            name=name or src.name,
            source=to_portable(src),
            blob=blob,
            sha256=sha,
            size=stored,
            requires=list(requires),
        )
        self.items.append(item)
        return item

    def add_tree(
        self,
        path: str | Path,
        category: str,
        name: str | None = None,
        max_bytes: int = MAX_TREE_BYTES,
    ) -> Item | None:
        src = expand(path)
        if not src.is_dir() or src.is_symlink():
            return None
        size = dir_size(src)
        if size == 0:
            return None
        if size > max_bytes:
            self.skipped.append((str(src), f"demasiado grande ({size // 1024 // 1024} MB)"))
            return None
        try:
            blob, sha, stored, count = self.store.put_tree(src, arcname=src.name)
        except OSError as exc:
            self.skipped.append((str(src), f"error de empaquetado: {exc}"))
            return None
        item = Item(
            kind=KIND_TREE,
            category=category,
            name=name or src.name,
            source=to_portable(src),
            blob=blob,
            sha256=sha,
            size=stored,
            meta={"files": count, "raw_size": size},
        )
        self.items.append(item)
        return item

    def add_children_as_trees(self, path: str | Path, category: str) -> None:
        """Cada subdirectorio se guarda como item independiente (dedupe real)."""
        base = expand(path)
        if not base.is_dir():
            return
        for child in sorted(base.iterdir()):
            if child.is_dir() and not child.is_symlink():
                self.add_tree(child, category)

    def add_dconf(self, path: str, category: str, name: str) -> Item | None:
        from ..drivers import dconf_dump

        data = dconf_dump(path)
        if not data or not data.strip():
            return None
        blob, sha, size = self.store.put_bytes(data)
        item = Item(
            kind=KIND_DCONF,
            category=category,
            name=name,
            blob=blob,
            sha256=sha,
            size=size,
            backend="dconf",
            data={"path": path},
            meta={"keys": data.count(b"\n")},
        )
        self.items.append(item)
        return item

    def add_setting(
        self,
        category: str,
        name: str,
        *,
        backend: str,
        data: dict,
    ) -> Item:
        item = Item(
            kind=KIND_SETTING,
            category=category,
            name=name,
            backend=backend,
            data=data,
        )
        self.items.append(item)
        return item


class Adapter:
    id = ""
    label = ""
    priority = 100

    # ------------------------------------------------------------- deteccion

    def detect(self) -> bool:
        return detect_de() == self.id

    # -------------------------------------------------------------- recoleccion

    def collect(self, collector: Collector) -> None:
        self._collect_common(collector)
        self._collect(collector)

    def _collect(self, collector: Collector) -> None:  # pragma: no cover
        raise NotImplementedError

    def _collect_common(self, collector: Collector) -> None:
        """Activos de usuario que existen en cualquier DE."""
        collector.add_children_as_trees("~/.themes", "theme")
        collector.add_children_as_trees("~/.local/share/themes", "theme")
        collector.add_children_as_trees("~/.icons", "cursor")
        collector.add_children_as_trees("~/.local/share/icons", "icons")
        collector.add_children_as_trees("~/.local/share/fonts", "font")
        collector.add_children_as_trees("~/.fonts", "font")

        collector.add_children_as_trees("~/.config/fontconfig", "config")

        for raw, label in (
            ("~/.config/gtk-3.0/settings.ini", "gtk-3.0/settings.ini"),
            ("~/.config/gtk-4.0/settings.ini", "gtk-4.0/settings.ini"),
            ("~/.config/gtk-3.0/gtk.css", "gtk-3.0/gtk.css"),
            ("~/.config/gtk-4.0/gtk.css", "gtk-4.0/gtk.css"),
            ("~/.config/gtk-2.0/gtkrc", "gtk-2.0/gtkrc"),
            ("~/.gtkrc-2.0", ".gtkrc-2.0"),
        ):
            collector.add_file(raw, "config", label)

    # ----------------------------------------------------------------- previa

    def themes(self) -> dict[str, str]:
        """Nombres de tema activos: iconos, cursor, GTK, Plasma."""
        return {}

    def preview_sources(self) -> list[Path]:
        """Candidatos a wallpaper para generar la portada de la copia."""
        return []
