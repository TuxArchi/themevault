"""Preparación de assets embebidos en un perfil de comunidad.

Incluye wallpaper (imagen o video), cover y plugins de terceros que ya están
dentro de la copia. El perfil sigue siendo una lista blanca: los plugins se
copian como archivos declarados, nunca se ejecutan durante la exportación.
"""

from __future__ import annotations

import hashlib
import re
import shutil
from pathlib import Path

from .model import KIND_TREE
from .profile import Profile, safe_value
from .store import BlobStore
from .util import expand, is_within
from .video import MAX_VIDEO_BYTES, VideoError, is_video, transcode

PLUGIN_PREFIXES: tuple[tuple[str, str], ...] = (
    ("~/.local/share/plasma/plasmoids/", "plasmoid"),
    ("~/.local/share/gnome-shell/extensions/", "gnome-extension"),
    ("~/.local/share/cinnamon/applets/", "cinnamon-applet"),
    ("~/.local/share/cinnamon/desklets/", "cinnamon-desklet"),
    ("~/.local/share/cinnamon/extensions/", "cinnamon-extension"),
    ("~/.local/share/budgie-desktop/plugins/", "budgie-plugin"),
)

ASSET_PREFIXES: tuple[tuple[str, str], ...] = (
    ("~/.themes/", "theme"),
    ("~/.local/share/themes/", "theme"),
    ("~/.icons/", "icons"),
    ("~/.local/share/icons/", "icons"),
    ("~/.local/share/fonts/", "font"),
    ("~/.fonts/", "font"),
)

MAX_EMBEDDED_ASSET = 25 * 1024 * 1024

VIDEO_PATH_RE = re.compile(
    r"((?:~|/)[^\s\"'<>]+?\.(?:mp4|mkv|webm|mov|avi|m4v|gif))",
    re.IGNORECASE,
)


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()



def _image_wallpaper(source: Path, directory: Path) -> dict:
    target = directory / "wallpaper.jpg"
    try:
        from PIL import Image
    except ImportError:
        suffix = source.suffix.lower() if source.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp") else ".jpg"
        target = directory / f"wallpaper{suffix}"
        shutil.copyfile(source, target)
    else:
        try:
            with Image.open(source) as raw:
                image = raw.convert("RGB")
                image.thumbnail((2560, 2560), Image.LANCZOS)
                image.save(target, format="JPEG", quality=90, optimize=True)
        except Exception:
            suffix = source.suffix.lower() if source.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp") else ".jpg"
            target = directory / f"wallpaper{suffix}"
            shutil.copyfile(source, target)
    return {
        "kind": "image",
        "file": target.name,
        "fallback": target.name,
        "sha256": _sha(target),
        "size": target.stat().st_size,
        "width": 0,
        "height": 0,
    }


def _video_wallpaper(source: Path, directory: Path) -> dict:
    target = directory / "wallpaper.mp4"
    info = transcode(source, target, max_bytes=MAX_VIDEO_BYTES)
    fallback = directory / "wallpaper.jpg"
    return {
        "kind": "video",
        "file": target.name,
        "fallback": fallback.name,
        "sha256": _sha(target),
        "size": target.stat().st_size,
        "width": int(info.get("width") or 0),
        "height": int(info.get("height") or 0),
        "duration": round(float(info.get("duration") or 0), 3),
        "codec": "h264",
    }


def _image_from_preview(manifest, store: BlobStore) -> Path | None:
    preview = manifest.preview or {}
    for key in ("wallpaper",):
        rel = preview.get(key)
        if rel:
            candidate = (store.root / rel).resolve()
            if candidate.is_file() and is_within(candidate, store.root):
                return candidate
    for screen in preview.get("screens") or []:
        rel = screen.get("wallpaper")
        if rel:
            candidate = store.path_of(rel)
            if candidate.is_file():
                return candidate
    return None


def _video_from_items(manifest, store: BlobStore) -> Path | None:
    for item in manifest.items:
        if not item.blob:
            continue
        try:
            data = store.read(item.blob)
        except OSError:
            continue
        if b"\x00" in data[:4096]:
            continue
        try:
            text = data.decode("utf-8", "replace")
        except UnicodeDecodeError:
            continue
        for match in VIDEO_PATH_RE.finditer(text):
            candidate = expand(match.group(1))
            if candidate.is_file() and is_video(candidate):
                return candidate
    return None


def prepare_wallpaper(
    profile: Profile,
    manifest,
    store: BlobStore,
    directory: Path,
    *,
    include_cover: bool = False,
) -> dict | None:
    source = _video_from_items(manifest, store)
    if source is not None:
        try:
            info = _video_wallpaper(source, directory)
        except VideoError:
            raise
        profile.wallpaper = info
        fallback = directory / info["fallback"]
        if include_cover and fallback.is_file():
            shutil.copyfile(fallback, directory / "cover.jpg")
            profile.cover = "cover.jpg"
        return info

    source = _image_from_preview(manifest, store)
    if source is None:
        return None
    info = _image_wallpaper(source, directory)
    profile.wallpaper = info
    target = directory / info["file"]
    if include_cover and target.is_file():
        shutil.copyfile(target, directory / "cover.jpg")
        profile.cover = "cover.jpg"
    return info


def prepare_assets(
    profile: Profile,
    manifest,
    store: BlobStore,
    directory: Path,
) -> list[dict]:
    assets_dir = directory / "assets"
    found: dict[str, dict] = {}
    for item in manifest.items:
        source = item.source or ""
        prefix = next((value for value in ASSET_PREFIXES if source.startswith(value[0])), None)
        if prefix is None:
            continue
        prefix_path, kind = prefix
        rest = source[len(prefix_path) :]
        asset_name = rest.split("/", 1)[0].strip()
        key = f"{kind}:{asset_name}"
        if (
            not asset_name
            or asset_name in (".", "..")
            or key in found
            or not item.blob
            or item.kind != KIND_TREE
        ):
            continue
        if not safe_value(asset_name):
            continue
        archive = assets_dir / f"{kind}-{asset_name}.tar.gz"
        archive.parent.mkdir(parents=True, exist_ok=True)
        try:
            data = store.read(item.blob)
            if len(data) > MAX_EMBEDDED_ASSET * 2:
                continue
            archive.write_bytes(data)
        except OSError:
            continue
        if archive.stat().st_size > MAX_EMBEDDED_ASSET:
            archive.unlink(missing_ok=True)
            continue
        found[key] = {
            "kind": kind,
            "name": asset_name,
            "file": f"assets/{archive.name}",
            "target": source,
            "sha256": _sha(archive),
            "size": archive.stat().st_size,
            "format": "tar.gz",
            "license": "unknown",
        }
    return list(found.values())


def prepare_plugins(
    profile: Profile,
    manifest,
    store: BlobStore,
    directory: Path,
) -> list[dict]:
    plugins_dir = directory / "plugins"
    found: dict[str, dict] = {}
    for item in manifest.items:
        source = item.source or ""
        prefix = next((value for value in PLUGIN_PREFIXES if source.startswith(value[0])), None)
        if prefix is None:
            continue
        prefix_path, kind = prefix
        rest = source[len(prefix_path) :]
        plugin_id = rest.split("/", 1)[0].strip()
        if (
            not plugin_id
            or plugin_id in (".", "..")
            or plugin_id in found
            or not item.blob
            or item.kind != KIND_TREE
        ):
            continue
        if not safe_value(plugin_id):
            continue
        archive = plugins_dir / f"{plugin_id}.tar.gz"
        archive.parent.mkdir(parents=True, exist_ok=True)
        try:
            archive.write_bytes(store.read(item.blob))
        except OSError:
            continue
        found[plugin_id] = {
            "id": plugin_id,
            "name": plugin_id,
            "kind": kind,
            "file": f"plugins/{archive.name}",
            "target": source,
            "sha256": _sha(archive),
            "size": archive.stat().st_size,
            "format": "tar.gz",
            "license": "unknown",
        }
    return list(found.values())
