"""Modelo de datos: Item y Manifest.

Un `Item` es una unidad restaurable. Hay cuatro tipos:
  - file:    un archivo suelto (kdeglobals, settings.ini, .colors...)
  - tree:    un arbol completo empaquetado en tar.gz (un tema, iconos, fuentes)
  - dconf:   un volcado de texto de una rama de dconf (GNOME, Cinnamon, MATE)
  - setting: un ajuste puntual aplicado via CLI (xfconf)

El `Manifest` es el indice de la copia y se guarda junto a los blobs.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from . import __version__

SCHEMA_VERSION = 1
APP_VERSION = __version__

KIND_FILE = "file"
KIND_TREE = "tree"
KIND_DCONF = "dconf"
KIND_SETTING = "setting"

CATEGORIES = (
    "theme",
    "icons",
    "cursor",
    "font",
    "wallpaper",
    "colorscheme",
    "layout",
    "shell",
    "config",
    "other",
)

CATEGORY_LABELS = {
    "theme": "Temas",
    "icons": "Iconos",
    "cursor": "Cursores",
    "font": "Fuentes",
    "wallpaper": "Fondos",
    "colorscheme": "Esquemas de color",
    "layout": "Escritorio y paneles",
    "shell": "Shell / extensiones",
    "config": "Configuracion",
    "other": "Otros",
}


@dataclass
class Item:
    kind: str
    category: str
    name: str
    source: str = ""
    blob: str = ""
    sha256: str = ""
    size: int = 0
    backend: str = "copy"
    data: dict[str, Any] = field(default_factory=dict)
    requires: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def category_label(self) -> str:
        return CATEGORY_LABELS.get(self.category, self.category)

    def to_dict(self) -> dict[str, Any]:
        raw = asdict(self)
        for key in ("data", "meta"):
            if not raw[key]:
                raw.pop(key)
        if not raw["requires"]:
            raw.pop("requires")
        return raw

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Item":
        known = {k: v for k, v in raw.items() if k in cls.__dataclass_fields__}
        return cls(**known)


@dataclass
class Manifest:
    id: str
    created: str
    host: dict[str, Any]
    items: list[Item] = field(default_factory=list)
    preview: dict[str, Any] = field(default_factory=dict)
    containers: list[dict[str, Any]] = field(default_factory=list)
    widgets: list[dict[str, Any]] = field(default_factory=list)
    keybinds: list[dict[str, Any]] = field(default_factory=list)
    label: str = ""
    notes: str = ""
    schema: int = SCHEMA_VERSION
    app_version: str = APP_VERSION

    # ---------------------------------------------------------------- consultas

    @property
    def de(self) -> str:
        return str(self.host.get("de", "desconocido"))

    @property
    def total_size(self) -> int:
        return sum(item.size for item in self.items)

    def by_category(self) -> dict[str, list[Item]]:
        grouped: dict[str, list[Item]] = {}
        for item in self.items:
            grouped.setdefault(item.category, []).append(item)
        return grouped

    def display_name(self) -> str:
        if self.label:
            return self.label
        try:
            when = datetime.fromisoformat(self.created)
            return when.strftime("%d/%m/%Y %H:%M")
        except ValueError:
            return self.id

    # -------------------------------------------------------------- serializar

    def to_dict(self) -> dict[str, Any]:
        raw = {
            "schema": self.schema,
            "app_version": self.app_version,
            "id": self.id,
            "created": self.created,
            "label": self.label,
            "notes": self.notes,
            "host": self.host,
            "preview": self.preview,
            "containers": self.containers,
            "widgets": self.widgets,
            "items": [item.to_dict() for item in self.items],
        }
        if self.keybinds:
            raw["keybinds"] = self.keybinds
        return raw

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Manifest":
        return cls(
            id=raw["id"],
            created=raw["created"],
            host=raw.get("host", {}),
            items=[Item.from_dict(i) for i in raw.get("items", [])],
            preview=raw.get("preview", {}),
            containers=raw.get("containers", []),
            widgets=raw.get("widgets", []),
            keybinds=raw.get("keybinds") or [],
            label=raw.get("label", ""),
            notes=raw.get("notes", ""),
            schema=raw.get("schema", SCHEMA_VERSION),
            app_version=raw.get("app_version", APP_VERSION),
        )
