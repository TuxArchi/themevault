"""Portada de una copia.

Cuatro piezas:
  1. captura del escritorio *sin ventanas* (Show Desktop via D-Bus)
  2. recorte por monitor, para poder pasar de imagen en imagen
  3. el wallpaper activo, extraido de la configuracion del DE
  4. una portada compuesta y una paleta de colores

La idea es que siempre haya algo lindo que mostrar, incluso en una copia
vieja o hecha por SSH.
"""

from __future__ import annotations

import re
import shutil
import time
from pathlib import Path

from . import screens as screens_mod
from .cover import build_cover
from .widgets import container_summary, restore_hidden_panels, reveal_hidden_panels
from .detect import detect_session
from .util import run, which

IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp")

# Herramientas de captura por orden de preferencia y sesion.
SHOT_TOOLS: list[tuple[str, list[str]]] = [
    ("grim", ["grim", "{out}"]),
    ("gnome-screenshot", ["gnome-screenshot", "-f", "{out}"]),
    ("spectacle", ["spectacle", "-b", "-n", "-f", "-o", "{out}"]),
    ("xfce4-screenshooter", ["xfce4-screenshooter", "-f", "-s", "{out}"]),
    ("maim", ["maim", "{out}"]),
    ("scrot", ["scrot", "{out}"]),
    ("import", ["import", "-window", "root", "{out}"]),
]


def is_blank_image(path: Path | str, threshold: float = 4.0) -> bool:
    """True si la imagen es practicamente negra.

    En Wayland algunas herramientas "funcionan" pero devuelven una captura
    negra (spectacle sin portal, por ejemplo). Detectarlo evita portadas rotas.
    """
    try:
        from PIL import Image, ImageStat
    except ImportError:
        return False
    try:
        with Image.open(path) as img:
            small = img.convert("RGB").resize((64, 36))
            mean = ImageStat.Stat(small).mean
        return sum(mean) / 3.0 < threshold
    except Exception:
        return False


def screenshot_tool() -> str | None:
    for name, _ in SHOT_TOOLS:
        if which(name):
            return name
    return None


# ------------------------------------------------------------- modo escritorio


def _qdbus_tool() -> str | None:
    return which("qdbus6", "qdbus")


def _show_desktop() -> str:
    """Pide al escritorio que muestre solo el fondo. Devuelve el mecanismo."""
    tool = _qdbus_tool()
    if tool is not None:
        proc = run(
            [
                tool,
                "org.kde.kglobalaccel",
                "/component/kwin",
                "org.kde.kglobalaccel.Component.invokeShortcut",
                "Show Desktop",
            ],
            timeout=10,
        )
        if proc is not None and proc.returncode == 0:
            return "kde"

    if which("hyprctl") is not None:
        proc = run(
            ["hyprctl", "dispatch", "togglespecialworkspace", "themevault-capture"],
            timeout=10,
        )
        if proc is not None and proc.returncode == 0:
            return "hyprland"

    if which("wmctrl") is not None and detect_session() == "x11":
        proc = run(["wmctrl", "-k", "on"], timeout=10)
        if proc is not None and proc.returncode == 0:
            return "wmctrl"
    return ""


def _restore_windows(mechanism: str) -> None:
    if mechanism == "kde":
        tool = _qdbus_tool()
        if tool is not None:
            run(
                [
                    tool,
                    "org.kde.kglobalaccel",
                    "/component/kwin",
                    "org.kde.kglobalaccel.Component.invokeShortcut",
                    "Show Desktop",
                ],
                timeout=10,
            )
    elif mechanism == "hyprland":
        run(
            ["hyprctl", "dispatch", "togglespecialworkspace", "themevault-capture"],
            timeout=10,
        )
    elif mechanism == "wmctrl":
        run(["wmctrl", "-k", "off"], timeout=10)


def take_screenshot(out: Path, attempts: int = 3) -> tuple[bool, str]:
    """Captura el escritorio sin ventanas. Devuelve (ok, motivo del fallo)."""
    session = detect_session()
    if screenshot_tool() is None:
        return False, "no hay ninguna herramienta de captura instalada"

    if session == "wayland":
        order = [t for t in SHOT_TOOLS if t[0] in ("grim", "gnome-screenshot", "spectacle")]
    elif session == "x11":
        order = [t for t in SHOT_TOOLS if t[0] in ("maim", "scrot", "import", "gnome-screenshot")]
    else:
        order = list(SHOT_TOOLS)

    out.parent.mkdir(parents=True, exist_ok=True)

    mechanism = _show_desktop()
    if mechanism:
        time.sleep(0.7)  # que termine la animacion de minimizar

    revealed = reveal_hidden_panels()
    if revealed:
        time.sleep(0.6)

    reason = "sin intentos"
    try:
        for attempt in range(attempts):
            for name, template in order:
                if not which(name):
                    continue
                reason = f"{name}: no genero archivo"
                cmd = [part.format(out=str(out)) for part in template]
                run(cmd, timeout=25)
                if not out.exists() or out.stat().st_size == 0:
                    continue
                if not is_blank_image(out):
                    return True, ""
                out.unlink(missing_ok=True)
                reason = f"{name}: devolvio una imagen negra"
            if attempt < attempts - 1:
                time.sleep(0.7 * (attempt + 1))
        return False, reason
    finally:
        restore_hidden_panels(revealed)
        if mechanism:
            _restore_windows(mechanism)
            time.sleep(0.2)


def pick_wallpaper(candidates: list[Path], out_dir: Path) -> Path | None:
    for candidate in candidates:
        if candidate.is_file() and candidate.suffix.lower() in IMAGE_EXTS:
            dest = out_dir / f"wallpaper{candidate.suffix.lower()}"
            try:
                shutil.copyfile(candidate, dest)
            except OSError:
                continue
            if dest.stat().st_size > 0:
                return dest
    return None


# ---------------------------------------------------------------------- paleta

_HEX_RE = re.compile(r"#([0-9a-fA-F]{6})")


def _palette_with_pillow(image: Path, count: int) -> list[str]:
    try:
        from PIL import Image  # type: ignore
    except ImportError:
        return []
    with Image.open(image) as img:
        img = img.convert("RGB")
        img.thumbnail((96, 96))
        quant = img.quantize(colors=count)
        histogram = sorted(quant.getcolors() or [], reverse=True)
        palette = quant.getpalette() or []
    colors: list[str] = []
    for _, index in histogram:
        base = index * 3
        if base + 2 >= len(palette):
            continue
        r, g, b = palette[base : base + 3]
        hex_color = f"#{r:02x}{g:02x}{b:02x}"
        if hex_color not in colors:
            colors.append(hex_color)
        if len(colors) >= count:
            break
    return colors


def _palette_with_imagemagick(image: Path, count: int) -> list[str]:
    tool = which("magick", "convert")
    if tool is None:
        return []
    proc = run([tool, str(image), "-resize", "96x96", "-colors", str(count), "-unique-colors", "txt:-"])
    if proc is None or proc.returncode != 0:
        return []
    colors: list[str] = []
    for match in _HEX_RE.finditer(proc.stdout.decode("utf-8", "replace")):
        color = "#" + match.group(1).lower()
        if color not in colors:
            colors.append(color)
        if len(colors) >= count:
            break
    return colors


def build_palette(image: Path | None, count: int = 5) -> list[str]:
    if image is None or not image.exists():
        return []
    return _palette_with_pillow(image, count) or _palette_with_imagemagick(image, count)


# ------------------------------------------------------------------ ensamblado


def _crop_panels(shot: Path, containers: list[dict], preview_dir: Path) -> list[dict]:
    """Recorta cada barra de tareas desde la captura del escritorio."""
    panels = [c for c in containers if c.get("kind") == "panel"]
    if not panels or not shot.exists():
        return []

    screens = screens_mod.detect()
    out_dir = preview_dir / "panels"
    out_dir.mkdir(parents=True, exist_ok=True)

    found: list[dict] = []
    for index, panel in enumerate(panels, start=1):
        custom_length = panel.get("length_mode") not in (None, "", "fill")
        point = None
        if panel.get("position_x") is not None and panel.get("position_y") is not None:
            point = (int(panel["position_x"]), int(panel["position_y"]))
        piece = screens_mod.crop_edge(
            shot,
            screens,
            int(panel.get("screen") or 0),
            panel.get("location", ""),
            panel.get("size"),
            offset=panel.get("offset") if custom_length else None,
            length=panel.get("length") if custom_length else None,
            point=point,
        )
        if piece is None:
            continue
        path = out_dir / f"panel-{index}.png"
        try:
            piece.save(path, format="PNG", optimize=True)
        except OSError:
            continue
        found.append(
            {
                "file": f"preview/panels/{path.name}",
                "name": panel.get("name", f"Panel {index}"),
                "screen": int(panel.get("screen") or 0),
                "summary": container_summary(panel),
                "width": piece.width,
                "height": piece.height,
            }
        )
    return found


def _custom_screens(containers: list[dict], count: int) -> set[int]:
    """Indices de pantallas que Plasma administra (panel, dock o escritorio).

    Un escritorio con su fondo y sus iconos ya es parte de la personalizacion
    de esa pantalla; solo se descartan monitores que Plasma no gestiona.
    """
    found: set[int] = set()
    for container in containers:
        index = int(container.get("screen") or 0)
        if 0 <= index < count:
            found.add(index)
    return found


def _screen_summary(containers: list[dict], index: int) -> tuple[str, list[str], int]:
    panels = [
        c.get("name", "Panel")
        for c in containers
        if c.get("kind") in ("panel", "dock") and int(c.get("screen") or 0) == index
    ]
    widgets = sum(int(c.get("widgets") or 0) for c in containers if int(c.get("screen") or 0) == index)
    parts = []
    if panels:
        parts.append(" y ".join(panels))
    if widgets:
        parts.append(f"{widgets} widgets")
    if not parts:
        parts.append("Escritorio")
    return " · ".join(parts), panels, widgets


def build_preview(
    backup_dir: Path,
    adapters,
    *,
    enabled: bool = True,
    themes: dict[str, str] | None = None,
    containers: list[dict] | None = None,
) -> dict:
    """Genera preview/ dentro de la copia y devuelve la seccion del manifest."""
    preview_dir = backup_dir / "preview"
    preview_dir.mkdir(parents=True, exist_ok=True)
    info: dict = {"palette": []}

    shot = preview_dir / "desktop.png"
    captured = False
    if enabled:
        captured, capture_error = take_screenshot(shot)
        if captured:
            info["screenshot"] = "preview/desktop.png"
        else:
            info["capture_error"] = capture_error

    # --- un recorte por monitor -------------------------------------------
    pieces: list[tuple[Path, screens_mod.Screen]] = []
    if captured:
        try:
            pieces = screens_mod.crop(shot, screens_mod.detect(), preview_dir / "screens")
        except Exception:
            pieces = []
    selected: set[int] = set()
    if len(pieces) > 1:
        selected = _custom_screens(containers or [], len(pieces)) or set(range(len(pieces)))
        entries = []
        for index, (piece, screen) in enumerate(pieces):
            summary, panels, widgets = _screen_summary(containers or [], index)
            if index not in selected:
                continue
            entries.append(
                {
                    "index": index,
                    "name": screen.name,
                    "file": f"preview/screens/{piece.name}",
                    "width": screen.width,
                    "height": screen.height,
                    "custom": bool(panels or widgets),
                    "panels": panels,
                    "widgets": widgets,
                    "summary": summary,
                }
            )
        info["screens"] = entries

    if captured and containers:
        panels = _crop_panels(shot, containers, preview_dir)
        if panels:
            info["panels"] = panels

    # Sin portada no se copia ninguna imagen personal (ni captura ni fondo).
    wallpaper = None
    if enabled:
        candidates: list[Path] = []
        for adapter in adapters:
            try:
                candidates.extend(adapter.preview_sources())
            except Exception:  # un DE raro nunca debe romper el backup
                continue

        wallpaper = pick_wallpaper(candidates, preview_dir)
        if wallpaper is not None:
            info["wallpaper"] = f"preview/{wallpaper.name}"

    source = wallpaper or (shot if captured else None)
    info["palette"] = build_palette(source)

    # --- portada compuesta (una por monitor si hay varios) ----------------
    covers: list[str] = []
    samples: dict = {}
    cover_themes: dict = {}
    if len(pieces) > 1:
        chosen = [(i, piece) for i, (piece, _screen) in enumerate(pieces) if i in selected]
        for rank, (_index, piece) in enumerate(chosen, start=1):
            data = build_cover(
                None,
                piece,
                themes or {},
                backup_dir,
                palette=info["palette"],
                cover_name=f"cover-{rank}.png",
                export_assets=(rank == 1),
            )
            if not data:
                continue
            covers.append(data["cover"])
            if not samples:
                samples = data.get("samples") or {}
            if not cover_themes:
                cover_themes = data.get("themes") or {}
    else:
        data = build_cover(
            shot if captured else None,
            wallpaper,
            themes or {},
            backup_dir,
            palette=info["palette"],
        )
        if data:
            covers = [data["cover"]]
            samples = data.get("samples") or {}
            cover_themes = data.get("themes") or {}

    if covers:
        info["covers"] = covers
        info["cover"] = covers[0]
    if samples:
        info["samples"] = samples
    if cover_themes:
        info["themes"] = cover_themes

    return info
