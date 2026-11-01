"""Miniaturas cacheadas para la galeria.

Generar las miniaturas en Python (Pillow) en vez de recortar en QML tiene tres
ventajas: esquinas redondeadas perfectas sin shaders, imagenes de 640 px en vez
de capturas 4K, y cache en disco para que la galeria abra instantaneo.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

THUMB_SIZE = (720, 405)   # 16:9
HERO_SIZE = (1600, 900)
THUMB_RADIUS = 30
HERO_RADIUS = 34


def cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or str(Path(os.path.expanduser("~")) / ".cache")
    path = Path(base) / "themevault" / "thumbs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _key(source: Path, size: tuple[int, int], radius: int, top_only: bool) -> str:
    try:
        stat = source.stat()
        stamp = f"{stat.st_mtime_ns}-{stat.st_size}"
    except OSError:
        stamp = "0"
    raw = f"{source}|{stamp}|{size}|{radius}|{top_only}"
    return hashlib.sha1(raw.encode()).hexdigest()[:20]


def make_thumbnail(
    source: Path,
    *,
    size: tuple[int, int] = THUMB_SIZE,
    radius: int = THUMB_RADIUS,
    top_only: bool = True,
) -> Path | None:
    """Devuelve la ruta de una miniatura PNG con esquinas redondeadas."""
    try:
        from PIL import Image, ImageDraw, ImageOps
    except ImportError:
        return None
    source = Path(source)
    if not source.is_file():
        return None

    target = cache_dir() / f"{_key(source, size, radius, top_only)}.png"
    if target.exists() and target.stat().st_size > 0:
        return target

    try:
        with Image.open(source) as img:
            img = img.convert("RGB")
            fitted = ImageOps.fit(img, size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.42))
    except Exception:
        return None

    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    if top_only:
        draw.rounded_rectangle((0, 0, size[0] + radius, size[1] + radius), radius=radius, fill=255)
    else:
        draw.rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius=radius, fill=255)

    fitted.putalpha(mask)
    tmp = target.with_suffix(".tmp")
    try:
        fitted.save(tmp, format="PNG", optimize=True)
        os.replace(tmp, target)
    except Exception:
        return None
    return target
