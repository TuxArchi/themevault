"""Registro de adaptadores.

Para sumar un entorno nuevo alcanza con heredar de `Adapter` y anotarlo aca.
"""

from __future__ import annotations

from .base import Adapter, Collector
from .gnome import GnomeAdapter
from .hyprland import HyprlandAdapter
from .kde import KdeAdapter
from .labwc import LabwcAdapter
from .niri import NiriAdapter
from .river import RiverAdapter
from .sway import SwayAdapter
from .wayfire import WayfireAdapter
from .xfce import XfceAdapter

REGISTRY: dict[str, type[Adapter]] = {
    cls.id: cls
    for cls in (
        GnomeAdapter,
        KdeAdapter,
        HyprlandAdapter,
        NiriAdapter,
        SwayAdapter,
        RiverAdapter,
        WayfireAdapter,
        LabwcAdapter,
        XfceAdapter,
    )
}


def all_adapters() -> list[Adapter]:
    return [cls() for cls in sorted(REGISTRY.values(), key=lambda c: c.priority)]


def get_adapter(adapter_id: str) -> Adapter | None:
    cls = REGISTRY.get(adapter_id)
    return cls() if cls else None


def detected_adapters() -> list[Adapter]:
    return [adapter for adapter in all_adapters() if adapter.detect()]


__all__ = [
    "Adapter",
    "Collector",
    "REGISTRY",
    "all_adapters",
    "detected_adapters",
    "get_adapter",
]
