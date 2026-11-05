"""Exportación saneada de una copia local.

La copia original no se modifica. Se copian solo los elementos configurables y
se eliminan imágenes personales, historial, shells, configuraciones privadas de
applets y atajos inseguros.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path

from .audit import APPLET_PREFIXES, HISTORY_KEYS, HOME_PATH, SECRET, SHELL_PREFIXES
from .model import KIND_DCONF, KIND_FILE, KIND_TREE, Manifest
from .profile import safe_keybinds
from .store import BlobStore
from .util import is_within

SECTION = re.compile(r"^\[(.*)\]$")
APPLET_CONFIG_SECTION = re.compile(r"\[Containments\]\[\d+\]\[Applets\]\[\d+\]\[Configuration\]")

PRIVATE_PREFIXES = SHELL_PREFIXES + ("~/.cinnamon/configs",)
ASSET_PREFIXES = (
    "~/.themes",
    "~/.local/share/themes",
    "~/.icons",
    "~/.local/share/icons",
    "~/.local/share/fonts",
    "~/.fonts",
)


def _sensitive_line(line: str) -> bool:
    return bool(HOME_PATH.search(line) or SECRET.search(line) or HISTORY_KEYS.search(line))


def _sanitize_text(text: str, source: str) -> str:
    lines: list[str] = []
    skip_section = False
    appletsrc = source.endswith("plasma-org.kde.plasma.desktop-appletsrc")
    for raw in text.splitlines():
        line = raw.strip()
        section = SECTION.match(line)
        if section:
            skip_section = bool(appletsrc and APPLET_CONFIG_SECTION.match(line))
            if skip_section:
                continue
        if skip_section:
            continue
        if _sensitive_line(line):
            continue
        if line.startswith(("Image=", "Image ", "picture-uri", "picture-filename")):
            continue
        lines.append(raw)
    return "\n".join(lines).rstrip() + "\n"


def _sanitize_containers(containers: list[dict]) -> list[dict]:
    out = []
    for container in containers:
        safe = {
            key: value
            for key, value in container.items()
            if key in (
                "id",
                "kind",
                "name",
                "location",
                "screen",
                "size",
                "floating",
                "visibility",
                "alignment",
                "length",
                "order",
                "widgets",
            )
        }
        out.append(safe)
    return out


def _sanitize_widgets(widgets: list[dict]) -> list[dict]:
    out = []
    for widget in widgets:
        safe = {
            key: value
            for key, value in widget.items()
            if key in ("id", "name", "kind", "container", "position", "installed", "hidden")
        }
        out.append(safe)
    return out


def sanitized_copy(
    manifest: Manifest,
    store: BlobStore,
    destination: Path,
    *,
    include_wallpaper: bool = False,
    include_plugins: bool = False,
) -> tuple[Manifest, dict]:
    """Crea una copia saneada en `destination`. Devuelve (manifest, reporte)."""
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    new_store = BlobStore(destination)
    report = {"removed": [], "sanitized": [], "kept": 0, "images": 0}

    new = copy.deepcopy(manifest)
    source_items = copy.deepcopy(manifest.items)
    new.items = []
    new.keybinds = safe_keybinds(manifest.keybinds)
    new.containers = _sanitize_containers(manifest.containers)
    new.widgets = _sanitize_widgets(manifest.widgets)
    new.notes = ""
    new.preview = {
        "palette": list((manifest.preview or {}).get("palette") or []),
        "themes": dict((manifest.preview or {}).get("themes") or {}),
    }
    new.host = copy.deepcopy(manifest.host)
    new.host["skipped"] = []
    new.host["sanitized"] = True

    for item in source_items:
        source = item.source or item.name
        if any(source.startswith(prefix) for prefix in PRIVATE_PREFIXES):
            report["removed"].append(source)
            continue
        if not include_plugins and any(
            source.startswith(prefix) for prefix in APPLET_PREFIXES + ASSET_PREFIXES
        ):
            report["removed"].append(source)
            continue
        if not item.blob:
            report["removed"].append(source)
            continue
        if item.kind == KIND_DCONF:
            try:
                text = store.read(item.blob).decode("utf-8", "replace")
            except OSError:
                report["removed"].append(source)
                continue
            clean = _sanitize_text(text, source)
            if not clean.strip():
                report["removed"].append(source)
                continue
            blob, sha, size = new_store.put_bytes(clean.encode())
            item.blob, item.sha256, item.size = blob, sha, size
            item.meta = {"keys": clean.count("\n")}
            new.items.append(item)
            report["sanitized"].append(source)
            continue
        if item.kind == KIND_FILE:
            try:
                data = store.read(item.blob)
            except OSError:
                report["removed"].append(source)
                continue
            if b"\x00" not in data[:4096]:
                try:
                    text = data.decode("utf-8")
                except UnicodeDecodeError:
                    text = ""
                if text:
                    clean = _sanitize_text(text, source)
                    if clean != text:
                        data = clean.encode()
                        report["sanitized"].append(source)
            blob, sha, size = new_store.put_bytes(data)
            item.blob, item.sha256, item.size = blob, sha, size
            new.items.append(item)
            report["kept"] += 1
            continue
        if item.kind == KIND_TREE:
            try:
                data = store.read(item.blob)
            except OSError:
                report["removed"].append(source)
                continue
            blob, sha, size = new_store.put_bytes(data)
            item.blob, item.sha256, item.size = blob, sha, size
            new.items.append(item)
            report["kept"] += 1

    if include_wallpaper:
        preview = manifest.preview or {}
        rel = preview.get("wallpaper")
        if rel:
            source = store.root / rel
            if source.is_file() and is_within(source.resolve(), store.root):
                (destination / "preview").mkdir(parents=True, exist_ok=True)
                target = destination / "preview" / Path(rel).name
                target.write_bytes(source.read_bytes())
                new.preview["wallpaper"] = f"preview/{target.name}"
                report["images"] = 1

    Path(destination / "manifest.json").write_text(
        json.dumps(new.to_dict(), indent=2, ensure_ascii=False)
    )
    return new, report
