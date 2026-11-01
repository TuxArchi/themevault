"""Deteccion de monitores y recorte de la captura por pantalla.

Una captura de dos monitores es una sola imagen ancha: sirve para guardar,
pero no para mostrar. Aca se detecta la geometria real y se parte en una
imagen por monitor para que la galeria pueda ir pasando de una a otra.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .util import run, which

_ANSI = re.compile(r"\x1b\[[0-9;]*m")


@dataclass
class Screen:
    name: str
    x: int
    y: int
    width: int
    height: int
    scale: float = 1.0


def _kscreen() -> list[Screen]:
    if which("kscreen-doctor") is None:
        return []
    proc = run(["kscreen-doctor", "-o"], timeout=10)
    if proc is None or proc.returncode != 0:
        return []

    text = _ANSI.sub("", proc.stdout.decode("utf-8", "replace"))
    found: list[dict] = []
    current: dict | None = None
    for raw in text.splitlines():
        line = raw.strip()
        header = re.match(r"Output:\s+\d+\s+(\S+)", line)
        if header:
            current = {"name": header.group(1), "enabled": False, "scale": 1.0}
            found.append(current)
            continue
        if current is None:
            continue
        if line == "enabled":
            current["enabled"] = True
        geometry = re.match(r"Geometry:\s+(-?\d+),(-?\d+)\s+(\d+)x(\d+)", line)
        if geometry:
            current["x"] = int(geometry.group(1))
            current["y"] = int(geometry.group(2))
            current["width"] = int(geometry.group(3))
            current["height"] = int(geometry.group(4))
        scale = re.match(r"Scale:\s+([\d.]+)", line)
        if scale:
            current["scale"] = float(scale.group(1))

    return [
        Screen(
            name=item["name"],
            x=item["x"],
            y=item["y"],
            width=item["width"],
            height=item["height"],
            scale=item.get("scale", 1.0),
        )
        for item in found
        if item.get("enabled") and item.get("width")
    ]


def _xrandr() -> list[Screen]:
    if which("xrandr") is None:
        return []
    proc = run(["xrandr", "--listmonitors"], timeout=10)
    if proc is None or proc.returncode != 0:
        return []

    screens: list[Screen] = []
    for line in proc.stdout.decode("utf-8", "replace").splitlines():
        match = re.match(
            r"\s*\d+:\s+\+?\*?(\S+)\s+(\d+)/\d+x(\d+)/\d+\+(-?\d+)\+(-?\d+)", line
        )
        if match:
            screens.append(
                Screen(
                    name=match.group(1),
                    width=int(match.group(2)),
                    height=int(match.group(3)),
                    x=int(match.group(4)),
                    y=int(match.group(5)),
                )
            )
    return screens


def detect() -> list[Screen]:
    """Monitores activos. Lista vacia si no se pueden detectar."""
    for probe in (_kscreen, _xrandr):
        try:
            found = probe()
        except Exception:
            found = []
        if found:
            return sorted(found, key=lambda s: (s.y, s.x))
    return []


def crop(image_path: Path, screens: list[Screen], out_dir: Path) -> list[tuple[Path, Screen]]:
    """Parte la captura en una imagen por monitor. Vacio si hay uno solo."""
    if len(screens) < 2:
        return []
    try:
        from PIL import Image
    except ImportError:
        return []

    image_path = Path(image_path)
    try:
        with Image.open(image_path) as raw:
            img = raw.convert("RGB")
            img.load()
    except Exception:
        return []

    min_x = min(s.x for s in screens)
    min_y = min(s.y for s in screens)
    span_x = max(s.x + s.width for s in screens) - min_x
    span_y = max(s.y + s.height for s in screens) - min_y
    if span_x <= 0 or span_y <= 0:
        return []

    kx = img.width / span_x
    ky = img.height / span_y

    out_dir.mkdir(parents=True, exist_ok=True)
    pieces: list[tuple[Path, Screen]] = []
    for index, screen in enumerate(screens, start=1):
        box = (
            max(0, round((screen.x - min_x) * kx)),
            max(0, round((screen.y - min_y) * ky)),
            min(img.width, round((screen.x - min_x + screen.width) * kx)),
            min(img.height, round((screen.y - min_y + screen.height) * ky)),
        )
        if box[2] <= box[0] or box[3] <= box[1]:
            continue
        piece = img.crop(box)
        path = out_dir / f"screen-{index}.jpg"
        piece.save(path, format="JPEG", quality=92, optimize=True)
        pieces.append((path, screen))
    return pieces


def _scale_for(image_size: tuple[int, int], screens: list[Screen]):
    min_x = min(s.x for s in screens)
    min_y = min(s.y for s in screens)
    span_x = max(s.x + s.width for s in screens) - min_x
    span_y = max(s.y + s.height for s in screens) - min_y
    if span_x <= 0 or span_y <= 0:
        return None
    return min_x, min_y, image_size[0] / span_x, image_size[1] / span_y


def crop_edge(
    image_path: Path,
    screens: list[Screen],
    screen_index: int,
    location: str,
    thickness: int | None,
    padding: int = 13,
    offset: int | None = None,
    length: int | None = None,
    point: tuple[int, int] | None = None,
):
    """Recorta la franja de la barra (borde inferior/superior/izq/der) de un monitor."""
    try:
        from PIL import Image
    except ImportError:
        return None

    try:
        with Image.open(image_path) as raw:
            img = raw.convert("RGB")
            img.load()
    except Exception:
        return None

    if not screens:
        screens = [Screen("Pantalla", 0, 0, img.width, img.height)]
    scale = _scale_for((img.width, img.height), screens)
    if scale is None:
        return None
    min_x, min_y, kx, ky = scale

    screen = screens[max(0, min(screen_index, len(screens) - 1))]
    x0 = (screen.x - min_x) * kx
    y0 = (screen.y - min_y) * ky
    width = screen.width * kx
    height = screen.height * ky

    strip = min(height, max(24.0, (thickness or 40) + padding * 2) * ky)
    where = (location or "").lower()

    # Xfce no guarda la orientacion como tal: se deduce del punto de anclaje.
    if not where and point is not None:
        px, py = point
        distances = {
            "top": abs(py - screen.y),
            "bottom": abs((screen.y + screen.height) - py),
            "left": abs(px - screen.x),
            "right": abs((screen.x + screen.width) - px),
        }
        where = min(distances, key=distances.get)

    # si la barra no ocupa todo el borde, recortar solo su tramo
    start = x0
    end = x0 + width
    vertical_start = y0
    vertical_end = y0 + height
    if length and offset is not None:
        start = x0 + offset * kx
        end = min(x0 + width, start + length * kx)
        vertical_start = y0 + offset * ky
        vertical_end = min(y0 + height, vertical_start + length * ky)
    margin = 6 * kx

    if where in ("superior", "top"):
        box = (max(x0, start - margin), y0, min(x0 + width, end + margin), y0 + strip)
    elif where in ("izquierda", "left"):
        box = (x0, max(y0, vertical_start - margin), x0 + strip, min(y0 + height, vertical_end + margin))
    elif where in ("derecha", "right"):
        box = (x0 + width - strip, max(y0, vertical_start - margin), x0 + width, min(y0 + height, vertical_end + margin))
    else:
        box = (max(x0, start - margin), y0 + height - strip, min(x0 + width, end + margin), y0 + height)

    box = (
        max(0, round(box[0])),
        max(0, round(box[1])),
        min(img.width, round(box[2])),
        min(img.height, round(box[3])),
    )
    if box[2] <= box[0] or box[3] <= box[1]:
        return None
    return img.crop(box)
