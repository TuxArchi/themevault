"""Portada compuesta: escritorio + muestra del cursor + muestra de iconos.

Todo se genera en Python (Pillow) en el momento del respaldo:

    +--------------------------------+--------------+
    |                                |   [cursor]   |
    |     escritorio (como se ve)    |   [o] [o]    |
    |                                |--------------|
    |                                |  [][][]      |
    |                                |  [][][]      |
    +--------------------------------+--------------+

Los SVG se rasterizan con `rsvg-convert` (Breeze, Papirus, Adwaita, etc.).
Los cursores de Plasma 6 son SVG en `cursors_scalable/`; los de temas viejos
son Xcursor binario y se decodifican aca mismo.
"""

from __future__ import annotations

import hashlib
import json
import os
import struct
from pathlib import Path

from .util import expand, run, which

COVER_SIZE = (1280, 720)
PANEL_WIDTH = 288
DESKTOP_WIDTH = COVER_SIZE[0] - PANEL_WIDTH

PANEL_BG = (18, 18, 26)
SEPARATOR = (35, 35, 48)
TILE_BG = (26, 26, 38)

ICON_ROOTS = (
    "~/.local/share/icons",
    "~/.icons",
    "/usr/share/icons",
    "/usr/local/share/icons",
)

ICON_SIZES = ("96", "128", "64", "48", "scalable", "32", "22")

# (categoria, nombres candidatos) en orden de preferencia
ICON_CANDIDATES = (
    ("places", ("folder", "folder-blue", "inode-directory", "folder-red")),
    ("places", ("user-home", "user-home-symbolic", "folder-home", "start-here")),
    ("apps", ("system-run", "utilities-terminal", "utilities-system-monitor")),
    ("apps", ("web-browser", "internet-web-browser", "org.gnome.Epiphany", "firefox")),
    ("mimetypes", ("text-x-generic", "text-plain", "application-x-generic")),
    ("apps", ("preferences-system", "settings", "preferences-desktop")),
    ("mimetypes", ("video-x-generic", "video-mp4", "applications-multimedia")),
    ("mimetypes", ("audio-x-generic", "audio-mpeg", "audio-volume-high")),
    ("mimetypes", ("image-x-generic", "image-png", "camera-photo")),
)

CURSOR_CANDIDATES = (
    ("left_ptr", ("left_ptr", "default", "arrow", "top_left_arrow")),
    ("pointer", ("pointer", "hand2", "hand1")),
    ("wait", ("wait", "watch", "progress")),
)


# ------------------------------------------------------------------- utilidades


def cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or str(expand("~") / ".cache")
    path = Path(base) / "themevault" / "assets"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _stamp(path: Path) -> str:
    try:
        stat = path.stat()
        return f"{stat.st_mtime_ns}-{stat.st_size}"
    except OSError:
        return "0"


def rasterize(source: Path, size: int) -> Path | None:
    """SVG -> PNG (rsvg-convert) o PNG -> tamano normalizado. Cacheado."""
    source = Path(source)
    if not source.is_file():
        return None
    key = hashlib.sha1(f"{source}|{_stamp(source)}|{size}".encode()).hexdigest()[:20]
    target = cache_dir() / f"{key}.png"
    if target.exists() and target.stat().st_size > 0:
        return target

    if source.suffix.lower() == ".svg":
        tool = which("rsvg-convert")
        if tool is None:
            return None
        proc = run([tool, "-w", str(size), "-h", str(size), str(source), "-o", str(target)])
        if proc is None or proc.returncode != 0 or not target.exists():
            return None
        return target

    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        with Image.open(source) as img:
            img = img.convert("RGBA")
            img.thumbnail((size, size), Image.LANCZOS)
            img.save(target)
    except Exception:
        return None
    return target


# ---------------------------------------------------------------------- iconos


def _theme_candidates(theme: str) -> list[str]:
    """Tema activo y su cadena de herencia (Inherits=)."""
    names = [theme] if theme else []
    for root in ICON_ROOTS:
        index = expand(root) / theme / "index.theme"
        if not index.is_file():
            continue
        try:
            for line in index.read_text(errors="replace").splitlines():
                if line.strip().startswith("Inherits"):
                    value = line.split("=", 1)[1]
                    names.extend(part.strip() for part in value.split(",") if part.strip())
                    break
        except OSError:
            pass
        break
    names.append("hicolor")
    seen: list[str] = []
    for name in names:
        if name and name not in seen:
            seen.append(name)
    return seen


def find_icon(theme: str, category: str, names: tuple[str, ...]) -> Path | None:
    categories = [category]
    for extra in ("places", "apps", "applications", "mimetypes", "devices", "status"):
        if extra not in categories:
            categories.append(extra)
    for theme_name in _theme_candidates(theme):
        for root in ICON_ROOTS:
            base = expand(root) / theme_name
            if not base.is_dir():
                continue
            for cat in categories:
                for size in ICON_SIZES:
                    for name in names:
                        for ext in (".svg", ".png"):
                            candidate = base / cat / size / f"{name}{ext}"
                            if candidate.is_file():
                                return candidate
    return None


# -------------------------------------------------------------------- cursores


def _xcursor_image(path: Path) -> Path | None:
    """Decodifica un Xcursor binario y devuelve un PNG con la imagen mas grande."""
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if len(data) < 16 or data[:4] != b"Xcur":
        return None
    try:
        _, _, ntoc = struct.unpack_from("<III", data, 4)
        best: tuple[int, int, int] | None = None
        for index in range(ntoc):
            offset = 16 + index * 12
            ctype, subtype, position = struct.unpack_from("<III", data, offset)
            if ctype != 0xFFFD0002:  # imagen
                continue
            if position + 36 > len(data):
                continue
            header, _type, _sub, _ver, width, height, _xhot, _yhot, _delay = struct.unpack_from(
                "<IIIIIIIII", data, position
            )
            if best is None or subtype > best[0]:
                best = (subtype, position, header)
        if best is None:
            return None
        _, position, header = best
        payload = data[position + header :]
        if payload[:8] == b"\x89PNG\r\n\x1a\n":
            key = hashlib.sha1(f"{path}|{_stamp(path)}|png".encode()).hexdigest()[:20]
            target = cache_dir() / f"{key}.png"
            target.write_bytes(payload)
            return target
        _, _, _, _, width, height, _, _, _ = struct.unpack_from("<IIIIIIIII", data, position)
        size = width * height * 4
        if len(payload) < size:
            return None
        from PIL import Image

        img = Image.frombytes("RGBA", (width, height), payload[:size], "raw", "BGRA")
        key = hashlib.sha1(f"{path}|{_stamp(path)}|raw".encode()).hexdigest()[:20]
        target = cache_dir() / f"{key}.png"
        img.save(target)
        return target
    except (struct.error, OSError, ValueError):
        return None


def find_cursor(theme: str, names: tuple[str, ...]) -> Path | None:
    """Devuelve un PNG (posiblemente cacheado) con el cursor dibujado."""
    for theme_name in _theme_candidates(theme):
        for root in ICON_ROOTS:
            base = expand(root) / theme_name
            if not base.is_dir():
                continue
            # Plasma 6: SVG escalable con metadata.json
            scalable = base / "cursors_scalable"
            if scalable.is_dir():
                for name in names:
                    folder = scalable / name
                    if not folder.is_dir():
                        continue
                    meta = folder / "metadata.json"
                    try:
                        entries = json.loads(meta.read_text()) if meta.is_file() else []
                    except (OSError, ValueError):
                        entries = []
                    for entry in entries:
                        filename = entry.get("filename")
                        if filename and (folder / filename).is_file():
                            return rasterize(folder / filename, 128)
            # Xcursor clasico
            cursors = base / "cursors"
            if cursors.is_dir():
                for name in names:
                    candidate = cursors / name
                    if not candidate.exists():
                        continue
                    resolved = candidate.resolve()
                    if resolved.is_file() and resolved.suffix.lower() == ".png":
                        return rasterize(resolved, 128)
                    decoded = _xcursor_image(resolved)
                    if decoded is not None:
                        return rasterize(decoded, 128)
            # Algunos temas traen una hoja de muestra
            preview = base / "preview.png"
            if preview.is_file():
                return rasterize(preview, 128)
    return None


# ------------------------------------------------------------------ composicion


def _rounded_tile(size: tuple[int, int], radius: int, color: tuple[int, int, int]):
    from PIL import Image, ImageDraw

    tile = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(tile)
    draw.rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius=radius, fill=(*color, 255))
    return tile


def _paste_centered(canvas, source: Path, box) -> None:
    from PIL import Image

    x, y, w, h = box
    with Image.open(source) as raw:
        icon = raw.convert("RGBA")
    icon.thumbnail((w, h), Image.LANCZOS)
    canvas.alpha_composite(icon, (x + (w - icon.width) // 2, y + (h - icon.height) // 2))


def _blank(path: Path | None) -> bool:
    if path is None or not path.is_file():
        return True
    from .preview import is_blank_image  # import diferido: preview importa este modulo

    return is_blank_image(path)


def build_cover(
    desktop: Path | None,
    wallpaper: Path | None,
    themes: dict[str, str] | None,
    out_dir: Path,
    palette: list[str] | None = None,
    cover_name: str = "cover.png",
    export_assets: bool = True,
) -> dict:
    """Genera preview/cover.png. Devuelve {} si no hay nada que mostrar."""
    try:
        from PIL import Image, ImageFilter, ImageOps
    except ImportError:
        return {}

    themes = themes or {}
    base_path: Path | None = None
    for candidate in (desktop, wallpaper):
        if not _blank(candidate):
            base_path = candidate
            break
    if base_path is None:
        return {}

    try:
        with Image.open(base_path) as img:
            base = img.convert("RGB")
            base.load()
    except Exception:
        return {}

    width, height = COVER_SIZE
    canvas = Image.new("RGB", (width, height), (10, 10, 15))

    # Fondo: la misma imagen muy desenfocada y oscurecida (sirve para ultrawide).
    backdrop = ImageOps.fit(base, (DESKTOP_WIDTH, height), method=Image.LANCZOS)
    backdrop = backdrop.filter(ImageFilter.GaussianBlur(26))
    backdrop = Image.blend(backdrop, Image.new("RGB", backdrop.size, (10, 10, 15)), 0.45)
    canvas.paste(backdrop, (0, 0))

    # Imagen nitida, contenida (no recorta un segundo monitor).
    fitted = ImageOps.contain(base, (DESKTOP_WIDTH - 36, height - 36), Image.LANCZOS)
    canvas.paste(fitted, ((DESKTOP_WIDTH - fitted.width) // 2, (height - fitted.height) // 2))

    # Panel derecho
    canvas.paste(Image.new("RGB", (PANEL_WIDTH, height), PANEL_BG), (DESKTOP_WIDTH, 0))
    canvas.paste(
        Image.new("RGB", (1, height), SEPARATOR), (DESKTOP_WIDTH, 0)
    )

    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    icons: list[str] = []
    samples: dict = {}

    # --- cursores -----------------------------------------------------------
    cursor_theme = themes.get("cursor", "")
    big = find_cursor(cursor_theme, CURSOR_CANDIDATES[0][1])
    small = []
    for _, aliases in CURSOR_CANDIDATES[1:]:
        found = find_cursor(cursor_theme, aliases)
        if found is not None:
            small.append(found)

    big_size = 104
    big_x = DESKTOP_WIDTH + (PANEL_WIDTH - big_size) // 2
    y = 54
    if big is not None:
        overlay.alpha_composite(_rounded_tile((big_size, big_size), 22, TILE_BG), (big_x, y))
        _paste_centered(overlay, big, (big_x, y, big_size, big_size))
        if export_assets:
            samples["cursor"] = _export(big, out_dir, "cursor")
        y += big_size + 16

    if small:
        total = len(small[:2]) * 56 + (len(small[:2]) - 1) * 8
        sx = DESKTOP_WIDTH + (PANEL_WIDTH - total) // 2
        for index, small_icon in enumerate(small[:2]):
            fx = sx + index * 64
            overlay.alpha_composite(_rounded_tile((56, 56), 15, TILE_BG), (fx, y))
            _paste_centered(overlay, small_icon, (fx, y, 56, 56))

    # --- iconos -------------------------------------------------------------
    tile, gap = 60, 14
    grid_w = 3 * tile + 2 * gap
    grid_x = DESKTOP_WIDTH + (PANEL_WIDTH - grid_w) // 2
    grid_y = 286
    icon_theme = themes.get("icons", "")
    for index, (category, names) in enumerate(ICON_CANDIDATES):
        source = find_icon(icon_theme, category, names)
        if source is None:
            continue
        rendered = rasterize(source, 128)
        if rendered is None:
            continue
        col, row = index % 3, index // 3
        fx = grid_x + col * (tile + gap)
        fy = grid_y + row * (tile + gap)
        overlay.alpha_composite(_rounded_tile((tile, tile), 16, TILE_BG), (fx, fy))
        _paste_centered(overlay, rendered, (fx, fy, tile, tile))
        if export_assets:
            icons.append(_export(rendered, out_dir, f"icon-{index}"))

    # --- paleta -------------------------------------------------------------
    if palette:
        chip_w, chip_h, chip_gap = 36, 16, 8
        colors = palette[:5]
        total = len(colors) * chip_w + (len(colors) - 1) * chip_gap
        px = DESKTOP_WIDTH + (PANEL_WIDTH - total) // 2
        py = 600
        for index, hex_color in enumerate(colors):
            try:
                rgb = tuple(int(hex_color.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4))
            except (ValueError, IndexError):
                continue
            overlay.alpha_composite(
                _rounded_tile((chip_w, chip_h), 8, rgb),
                (px + index * (chip_w + chip_gap), py),
            )

    canvas = canvas.convert("RGBA")
    canvas.alpha_composite(overlay)
    canvas = canvas.convert("RGB")

    preview_dir = out_dir / "preview"
    preview_dir.mkdir(parents=True, exist_ok=True)
    cover_path = preview_dir / cover_name
    canvas.save(cover_path, format="PNG", optimize=True)

    return {
        "cover": f"preview/{cover_name}",
        "themes": {k: v for k, v in themes.items() if v},
        "samples": {
            "cursor": samples.get("cursor", ""),
            "icons": icons,
        },
    }


def _export(source: Path, out_dir: Path, name: str) -> str:
    """Copia una muestra renderizada junto a la copia (para mostrarla suelta)."""
    assets = out_dir / "preview" / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    target = assets / f"{name}.png"
    try:
        target.write_bytes(Path(source).read_bytes())
    except OSError:
        return ""
    return f"preview/assets/{name}.png"
