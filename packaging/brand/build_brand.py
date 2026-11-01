#!/usr/bin/env python3
"""Genera los assets de marca: iconos PNG/ICO, banner y social preview.

Requiere Pillow y `rsvg-convert` (librsvg2-bin). Se corre a mano cuando cambia
la paleta o el icono:

    python packaging/brand/build_brand.py

No forma parte del build de la app: los PNG resultantes se versionan.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "docs" / "assets"
ICON = ASSETS / "icon.svg"
SCREENSHOT = ROOT / "docs" / "detalle.png"
BANNER = ASSETS / "banner.png"
SOCIAL = ASSETS / "social.png"

SIZES = (16, 24, 32, 48, 64, 128, 180, 192, 256, 512, 1024)

BG_TOP = (9, 24, 28)
BG_BOTTOM = (5, 12, 15)
ACCENT = (45, 212, 191)
ACCENT_2 = (8, 145, 178)
TEXT = (233, 242, 241)
DIM = (155, 179, 176)
FAINT = (106, 133, 130)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    style = "Bold" if bold else "Regular"
    try:
        path = subprocess.check_output(
            ["fc-match", "-f", "%{file}", f"Noto Sans:style={style}"], text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    return ImageFont.truetype(path, size)


def rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, size[0] - 1, size[1] - 1), radius=radius, fill=255
    )
    return mask


def vertical_gradient(width: int, height: int) -> Image.Image:
    strip = Image.new("RGB", (1, height))
    pixels = strip.load()
    for y in range(height):
        t = y / max(1, height - 1)
        pixels[0, y] = tuple(
            round(BG_TOP[i] + (BG_BOTTOM[i] - BG_TOP[i]) * t) for i in range(3)
        )
    return strip.resize((width, height))


def glow(size: tuple[int, int], center: tuple[int, int], radius: int,
         color: tuple[int, int, int] = ACCENT, alpha: int = 90) -> Image.Image:
    layer = Image.new("RGB", size, (0, 0, 0))
    draw = ImageDraw.Draw(layer)
    x, y = center
    draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color)
    layer = layer.filter(ImageFilter.GaussianBlur(radius * 0.55))
    return layer.point(lambda v: int(v * alpha / 255))


def screen_card(width: int, radius: int = 16) -> Image.Image:
    shot = Image.open(SCREENSHOT).convert("RGB")
    # El detalle es una pagina larga: se usa la parte de arriba, que es la que
    # se lee a tamano de banner.
    shot = shot.crop((0, 0, shot.width, min(shot.height, shot.width * 840 // 1280)))
    height = round(width * shot.height / shot.width)
    shot = shot.resize((width, height), Image.LANCZOS)

    card = Image.new("RGBA", (width + 2, height + 2), (0, 0, 0, 0))
    card.paste(shot, (1, 1))
    mask = rounded_mask((width + 2, height + 2), radius)
    card.putalpha(mask)

    border = Image.new("RGBA", card.size, (0, 0, 0, 0))
    ImageDraw.Draw(border).rounded_rectangle(
        (0, 0, card.size[0] - 1, card.size[1] - 1),
        radius=radius,
        outline=(42, 74, 80, 255),
        width=1,
    )
    card.alpha_composite(border)
    return card


def chip(draw: ImageDraw.ImageDraw, x: int, y: int, text: str,
         size: int, pad_x: int = 14, pad_y: int = 7) -> int:
    f = font(size, bold=True)
    left, top, right, bottom = draw.textbbox((0, 0), text, font=f)
    width = right - left + pad_x * 2
    height = bottom - top + pad_y * 2
    draw.rounded_rectangle(
        (x, y, x + width, y + height), radius=height // 2,
        fill=(18, 38, 43), outline=(30, 58, 64), width=1,
    )
    draw.text((x + pad_x, y + pad_y - top), text, font=f, fill=(215, 245, 239))
    return width


def compose(path: Path, size: tuple[int, int], scale: float,
            card_ratio: float) -> None:
    width, height = size
    image = vertical_gradient(width, height)

    overlay = glow((width, height), (int(width * 0.8), int(height * 0.15)),
                   int(height * 0.9), alpha=70)
    image = Image.blend(image, overlay, 0.55)
    overlay = glow((width, height), (int(width * 0.15), int(height * 1.05)),
                   int(height * 0.7), color=ACCENT_2, alpha=45)
    image = Image.blend(image, overlay, 0.35)

    draw = ImageDraw.Draw(image)

    margin = round(width * 0.055)
    icon_size = round(104 * scale)
    icon = Image.open(ASSETS / "icon-512.png").convert("RGBA").resize(
        (icon_size, icon_size), Image.LANCZOS
    )
    content_h = icon_size + round((34 + 25 + 44 + 17 + 40 + 32 + 58 + 22) * scale)
    icon_y = max(round(height * 0.1), (height - content_h) // 2)
    image.paste(icon, (margin, icon_y), icon)

    word = font(round(60 * scale), bold=True)
    baseline = icon_y + round(icon_size * 0.12)
    draw.text((margin + icon_size + round(24 * scale), baseline),
              "ThemeVault", font=word, fill=TEXT)

    tagline = font(round(25 * scale))
    draw.text((margin, icon_y + icon_size + round(34 * scale)),
              "Respaldo y restauración de tu escritorio Linux.",
              font=tagline, fill=TEXT)

    small = font(round(17 * scale))
    draw.text((margin, icon_y + icon_size + round(78 * scale)),
              "temas · iconos · cursores · fuentes · fondos · widgets · barras",
              font=small, fill=DIM)

    chips = ["KDE Plasma", "GNOME", "Xfce", "GPL-3.0"]
    x = margin
    y = icon_y + icon_size + round(118 * scale)
    for text in chips:
        x += chip(draw, x, y, text, round(15 * scale)) + round(8 * scale)

    url = font(round(18 * scale), bold=True)
    draw.text((margin, y + round(58 * scale)),
              "github.com/TuxArchi/themevault", font=url, fill=ACCENT)

    card_width = round(width * card_ratio)
    card = screen_card(card_width)
    card_x = width - margin - card.size[0]
    card_y = (height - card.size[1]) // 2

    shadow = Image.new("RGBA", (card.size[0] + 80, card.size[1] + 80), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        (40, 40, shadow.size[0] - 40, shadow.size[1] - 40), radius=18, fill=(0, 0, 0, 190)
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(26))
    image.paste(shadow, (card_x - 40 + 6, card_y - 40 + 14), shadow)

    halo = Image.new("RGBA", (card.size[0] + 120, card.size[1] + 120), (0, 0, 0, 0))
    ImageDraw.Draw(halo).rounded_rectangle(
        (60, 60, halo.size[0] - 60, halo.size[1] - 60), radius=20, fill=(45, 212, 191, 70)
    )
    halo = halo.filter(ImageFilter.GaussianBlur(34))
    image.paste(halo, (card_x - 60, card_y - 60), halo)

    image.paste(card, (card_x, card_y), card)

    if path == BANNER:
        draw.rectangle((0, height - 6, width, height), fill=(19, 78, 80))

    image.convert("RGB").save(path, optimize=True)
    print(f"{path.relative_to(ROOT)}  {width}x{height}")


def main() -> int:
    try:
        subprocess.run(["rsvg-convert", "--version"], check=True,
                       capture_output=True)
    except (OSError, subprocess.CalledProcessError):
        print("Falta rsvg-convert (librsvg2-bin).", file=sys.stderr)
        return 2

    for size in SIZES:
        subprocess.run(
            ["rsvg-convert", "-w", str(size), "-h", str(size),
             str(ICON), "-o", str(ASSETS / f"icon-{size}.png")],
            check=True,
        )
    (ASSETS / "icon-180.png").replace(ASSETS / "apple-touch-icon.png")

    Image.open(ASSETS / "icon-512.png").save(
        ASSETS / "favicon.ico",
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64)],
    )
    print("docs/assets/favicon.ico")

    compose(BANNER, (1600, 600), 1.0, 0.39)
    compose(SOCIAL, (1280, 640), 0.95, 0.44)
    return 0


if __name__ == "__main__":
    sys.exit(main())
