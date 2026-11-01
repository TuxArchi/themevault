"""Modelo de lista que alimenta la galeria de QML.

Cada fila es una copia ya "aplanada" a tipos que QML entiende: nada de
objetos Python complejos ni de leer archivos desde la vista.
"""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QAbstractListModel, QByteArray, QModelIndex, QUrl, Qt

from ..model import Manifest
from ..util import human_size

MONTHS = (
    "ene",
    "feb",
    "mar",
    "abr",
    "may",
    "jun",
    "jul",
    "ago",
    "sep",
    "oct",
    "nov",
    "dic",
)

DE_LABELS = {
    "gnome": "GNOME",
    "kde": "KDE Plasma",
    "xfce": "Xfce",
    "cinnamon": "Cinnamon",
    "mate": "MATE",
    "budgie": "Budgie",
    "lxqt": "LXQt",
    "lxde": "LXDE",
    "pantheon": "Pantheon",
    "deepin": "Deepin",
    "cosmic": "COSMIC",
    "desconocido": "Desconocido",
}


def de_label(de: str) -> str:
    return DE_LABELS.get(de, de.capitalize() if de else "Desconocido")


def pretty_date(created: str) -> str:
    try:
        when = datetime.fromisoformat(created)
    except ValueError:
        return created
    return f"{when.day} {MONTHS[when.month - 1]} {when.year} · {when:%H:%M}"


def thumb_url(path, base, *, size=None, radius=None, top_only=True) -> str:
    """Miniatura cacheada con esquinas redondeadas."""
    from pathlib import Path

    from .thumbs import HERO_RADIUS, HERO_SIZE, THUMB_RADIUS, THUMB_SIZE, make_thumbnail

    if not path:
        return ""
    candidate = Path(base) / path
    if not candidate.exists():
        return ""
    preview = make_thumbnail(
        candidate,
        size=size or THUMB_SIZE,
        radius=radius or THUMB_RADIUS,
        top_only=top_only,
    )
    return QUrl.fromLocalFile(str(preview or candidate)).toString()


def preview_source(manifest, base: str, keys=("cover", "screenshot", "wallpaper")) -> str:
    """Elige la mejor imagen de portada: captura si sirve, si no el wallpaper."""
    from pathlib import Path

    from ..preview import is_blank_image

    preview = manifest.preview or {}
    for key in keys:
        rel = preview.get(key)
        if not rel:
            continue
        candidate = Path(base) / rel
        if candidate.is_file() and not is_blank_image(candidate):
            return rel
    return ""


ROLES = {
    "backupId": Qt.UserRole + 1,
    "title": Qt.UserRole + 2,
    "subtitle": Qt.UserRole + 3,
    "de": Qt.UserRole + 4,
    "deLabel": Qt.UserRole + 5,
    "sizeText": Qt.UserRole + 6,
    "itemsText": Qt.UserRole + 7,
    "thumb": Qt.UserRole + 8,
    "palette": Qt.UserRole + 9,
    "notes": Qt.UserRole + 10,
    "hasThumb": Qt.UserRole + 11,
    "covers": Qt.UserRole + 12,
}


class BackupListModel(QAbstractListModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list[dict] = []

    def roleNames(self) -> dict[int, QByteArray]:
        return {role: QByteArray(name.encode()) for name, role in ROLES.items()}

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._rows)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._rows):
            return None
        row = self._rows[index.row()]
        name = next((n for n, r in ROLES.items() if r == role), None)
        return row.get(name) if name else None

    def set_manifests(self, manifests: list[Manifest], base_dirs: dict[str, str]) -> None:
        self.beginResetModel()
        self._rows = [self._row(m, base_dirs.get(m.id, "")) for m in manifests]
        self.endResetModel()

    @staticmethod
    def _row(manifest: Manifest, base: str) -> dict:
        preview = manifest.preview or {}
        covers: list[str] = []
        for rel in preview.get("covers") or ([preview["cover"]] if preview.get("cover") else []):
            url = thumb_url(rel, base, top_only=False)
            if url:
                covers.append(url)
        if not covers:
            rel = preview_source(manifest, base)
            if rel:
                covers = [thumb_url(rel, base, top_only=False)]
        thumb = covers[0] if covers else ""
        return {
            "backupId": manifest.id,
            "title": manifest.label or pretty_date(manifest.created),
            "subtitle": f"{pretty_date(manifest.created)}  ·  {human_size(manifest.total_size)}",
            "de": manifest.de,
            "deLabel": de_label(manifest.de),
            "sizeText": human_size(manifest.total_size),
            "itemsText": f"{len(manifest.items)} elementos"
            + (f" · {len(manifest.widgets)} widgets" if manifest.widgets else ""),
            "thumb": thumb,
            "hasThumb": bool(thumb),
            "covers": covers,
            "palette": list(preview.get("palette") or []),
            "notes": manifest.notes or "",
        }
