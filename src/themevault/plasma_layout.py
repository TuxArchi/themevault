"""Mezcla del layout de Plasma para restaurar una pantalla sobre otra.

Todo el escritorio vive en un unico INI (`plasma-org.kde.plasma.desktop-appletsrc`).
Cada panel y cada escritorio es un *containment* con su `lastScreen`. Restaurar
la pantalla A sobre la B significa:

  * tomar los containments de A,
  * renumerarlos (containments y applets) para que no choquen con los del
    sistema actual,
  * apuntarlos al `lastScreen` y a la actividad vigentes,
  * reemplazar los containments que hoy viven en B,

sin tocar el resto del archivo (los otros monitores y los ajustes globales).

Los canales de escritorio no se pueden tocar con la API de scripting sin perder
configuracion fina de los widgets, por eso se trabaja sobre el archivo y con
respaldo previo.
"""

from __future__ import annotations

import configparser
import io
import re
from dataclasses import dataclass, field
from pathlib import Path

APPLETSRC = "plasma-org.kde.plasma.desktop-appletsrc"

_CONTAINMENT = re.compile(r"^Containments\]\[(\d+)(?:\]|$)")
# listar applets: la seccion tiene que terminar en el id
_APPLET = re.compile(r"^Containments\]\[(\d+)\]\[Applets\]\[(\d+)$")
# renombrar: tambien alcanza a la configuracion del applet
_APPLET_ANY = re.compile(r"^Containments\]\[(\d+)\]\[Applets\]\[(\d+)(?:\]|$)")


def parse_layout(text: str) -> configparser.RawConfigParser:
    return _parse(text)


def _parse(text: str) -> configparser.RawConfigParser:
    parser = configparser.RawConfigParser(strict=False)
    parser.optionxform = str
    parser.read_string(text)
    return parser


def _clone(parser: configparser.RawConfigParser) -> configparser.RawConfigParser:
    copy = configparser.RawConfigParser(strict=False)
    copy.optionxform = str
    for section in parser.sections():
        copy.add_section(section)
        for key, value in parser.items(section):
            copy.set(section, key, value)
    return copy


# ------------------------------------------------------------------ consultas


def containment_ids(parser: configparser.RawConfigParser) -> list[str]:
    ids: list[str] = []
    for section in parser.sections():
        match = re.fullmatch(r"Containments\]\[(\d+)$", section)
        if match:
            ids.append(match.group(1))
    return ids


def screen_of(parser: configparser.RawConfigParser, cid: str) -> int:
    section = f"Containments][{cid}"
    if not parser.has_section(section):
        return 0
    try:
        return int(parser.get(section, "lastScreen") or 0)
    except (ValueError, configparser.Error):
        return 0


def sections_of(parser: configparser.RawConfigParser, cid: str) -> list[str]:
    prefix = f"Containments][{cid}"
    return [
        s for s in parser.sections() if s == prefix or s.startswith(prefix + "]")
    ]


def applets_of(parser: configparser.RawConfigParser, cid: str) -> list[str]:
    found: list[str] = []
    for section in parser.sections():
        match = _APPLET.match(section)
        if match and match.group(1) == cid:
            found.append(match.group(2))
    return sorted(found, key=int)


def applet_ids(parser: configparser.RawConfigParser) -> list[str]:
    found: set[str] = set()
    for section in parser.sections():
        match = _APPLET.match(section)
        if match:
            found.add(match.group(2))
    return sorted(found, key=int)


def by_screen(parser: configparser.RawConfigParser) -> dict[int, list[str]]:
    grouped: dict[int, list[str]] = {}
    for cid in containment_ids(parser):
        grouped.setdefault(screen_of(parser, cid), []).append(cid)
    return grouped


def current_activity(parser: configparser.RawConfigParser) -> str:
    """La actividad mas usada en el archivo vivo (o cadena vacia)."""
    counts: dict[str, int] = {}
    for cid in containment_ids(parser):
        value = parser.get(f"Containments][{cid}", "activityId", fallback="").strip()
        if value:
            counts[value] = counts.get(value, 0) + 1
    if not counts:
        return ""
    return max(counts, key=counts.get)


def wallpapers_by_screen(parser: configparser.RawConfigParser) -> dict[int, str]:
    """Ruta del fondo de cada pantalla (solo escritorios con imagen)."""
    found: dict[int, str] = {}
    for cid in containment_ids(parser):
        section = f"Containments][{cid}"
        if parser.get(section, "plugin", fallback="") not in (
            "org.kde.plasma.folder",
            "org.kde.desktopcontainment",
        ):
            continue
        screen = screen_of(parser, cid)
        for candidate in parser.sections():
            if not candidate.startswith(f"Containments][{cid}][Wallpaper]"):
                continue
            if not candidate.endswith("[General"):
                continue
            value = parser.get(candidate, "Image", fallback="").strip()
            if value.startswith("file://"):
                value = value[len("file://") :]
            if value and Path(value).is_file() and screen not in found:
                found[screen] = value
    return found


# --------------------------------------------------------------------- mezcla


@dataclass
class MergeReport:
    replaced: list[str] = field(default_factory=list)
    added: list[str] = field(default_factory=list)
    mapping: dict[int, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "replaced": self.replaced,
            "added": self.added,
            "mapping": {str(k): v for k, v in self.mapping.items()},
            "warnings": self.warnings,
        }


def merge(
    saved_text: str,
    live_text: str,
    mapping: dict[int, int],
    activity_id: str | None = None,
) -> tuple[str, MergeReport]:
    """Devuelve (texto nuevo del appletsrc, reporte).

    `mapping` va de pantalla de origen (en la copia) a pantalla destino (ahora).
    """
    saved = _parse(saved_text)
    live = _parse(live_text)
    report = MergeReport(mapping=dict(mapping))

    if not mapping:
        return live_text, report

    used_c = {int(c) for c in containment_ids(saved)} | {int(c) for c in containment_ids(live)}
    used_a = {int(a) for a in applet_ids(saved)} | {int(a) for a in applet_ids(live)}
    next_c = max(used_c, default=0) + 1
    next_a = max(used_a, default=0) + 1

    saved_screens = by_screen(saved)
    activity = activity_id or current_activity(live)

    # --- 1) asignar ids nuevos ------------------------------------------------
    cid_map: dict[str, str] = {}
    aid_map: dict[str, str] = {}
    to_copy: list[tuple[str, int]] = []  # (cid, pantalla destino)

    def allocate(cid: str, target: int) -> None:
        nonlocal next_c
        if cid in cid_map:
            return
        cid_map[cid] = str(next_c)
        next_c += 1
        to_copy.append((cid, target))

    for source, target in mapping.items():
        if source not in saved_screens:
            report.warnings.append(f"la copia no tiene la pantalla {source}")
            continue
        for cid in saved_screens[source]:
            allocate(cid, target)

    # un containment referenciado (p. ej. la bandeja) viaja con su padre
    for cid, target in list(to_copy):
        for section in sections_of(saved, cid):
            value = saved.get(section, "SystrayContainmentId", fallback="").strip()
            if value and value in containment_ids(saved) and value not in cid_map:
                allocate(value, target)

    for cid in cid_map:
        for aid in applets_of(saved, cid):
            if aid not in aid_map:
                aid_map[aid] = str(next_a)
                next_a += 1

    # --- 2) sacar del archivo vivo lo que esta en las pantallas destino ------
    targets = set(mapping.values())
    for cid in containment_ids(live):
        if screen_of(live, cid) in targets:
            for section in sections_of(live, cid):
                if live.has_section(section):
                    live.remove_section(section)
            report.replaced.append(cid)

    # --- 3) copiar lo de la copia con los ids nuevos -------------------------
    for cid, target in to_copy:
        new_cid = cid_map[cid]
        if new_cid not in report.added:
            report.added.append(new_cid)
        for section in sections_of(saved, cid):
            new_section = _rename_section(section, cid, new_cid, aid_map)
            if not live.has_section(new_section):
                live.add_section(new_section)
            for key, value in saved.items(section):
                live.set(new_section, key, _rewrite_value(key, value, cid_map, aid_map))

            if section == f"Containments][{cid}":
                live.set(new_section, "lastScreen", str(target))
                if activity:
                    live.set(new_section, "activityId", activity)

    buffer = io.StringIO()
    live.write(buffer)
    return buffer.getvalue(), report


def _rename_section(
    section: str, cid: str, new_cid: str, aid_map: dict[str, str]
) -> str:
    renamed = section.replace(f"Containments][{cid}", f"Containments][{new_cid}", 1)
    match = _APPLET_ANY.match(renamed)
    if match:
        old_aid = match.group(2)
        if old_aid in aid_map:
            renamed = renamed.replace(f"[Applets][{old_aid}", f"[Applets][{aid_map[old_aid]}", 1)
    return renamed


def _rewrite_value(
    key: str, value: str, cid_map: dict[str, str], aid_map: dict[str, str]
) -> str:
    if key == "AppletOrder" and value:
        parts = [part.strip() for part in re.split(r"[;,:]", value) if part.strip()]
        return ";".join(aid_map.get(part, part) for part in parts)
    if key == "SystrayContainmentId" and value.strip() in cid_map:
        return cid_map[value.strip()]
    return value


# ------------------------------------------------------------------ utilidades


def rewrite_wallpaper(text: str, target_screen: int, new_path: str) -> str:
    """Apunta el fondo de esa pantalla al archivo restaurado."""
    parser = _parse(text)
    for cid in containment_ids(parser):
        section = f"Containments][{cid}"
        if screen_of(parser, cid) != target_screen:
            continue
        for candidate in parser.sections():
            if candidate.startswith(f"Containments][{cid}][Wallpaper]") and candidate.endswith("[General"):
                parser.set(candidate, "Image", new_path)
    buffer = io.StringIO()
    parser.write(buffer)
    return buffer.getvalue()
