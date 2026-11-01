"""Deteccion de monitores y recorte por pantalla."""

from __future__ import annotations

import subprocess

import pytest

from themevault import screens


def fake_run(stdout: str, code: int = 0):
    def _run(*args, **kwargs):
        return subprocess.CompletedProcess(args=[], returncode=code, stdout=stdout.encode())

    return _run


KSCREEN = """
Output: 1 HDMI-A-1 0000-0000
\tenabled
\tconnected
\tpriority 2
\tGeometry: 1920,0 1920x1080
\tScale: 1

Output: 2 DP-3 1111-1111
\tenabled
\tconnected
\tGeometry: 0,0 1920x1080
\tScale: 1
"""

XRANDR = """Monitors: 2
 0: +*DP-3 1920/344x1080/194+0+0  DP-3
 1: +HDMI-A-1 1920/509x1080/286+1920+0  HDMI-A-1
"""


def test_kscreen(monkeypatch):
    monkeypatch.setattr(screens, "which", lambda *names: "/usr/bin/kscreen-doctor")
    monkeypatch.setattr(screens, "run", fake_run(KSCREEN.replace("\t", "\x1b[01;32m\t")))

    found = screens.detect()
    assert [s.name for s in found] == ["DP-3", "HDMI-A-1"]  # ordenado por x
    assert found[0].x == 0 and found[1].x == 1920
    assert found[0].width == 1920 and found[0].height == 1080


def test_xrandr(monkeypatch):
    monkeypatch.setattr(screens, "which", lambda *names: None if "kscreen" in names else "/usr/bin/xrandr")
    monkeypatch.setattr(screens, "run", fake_run(XRANDR))

    found = screens.detect()
    assert [s.name for s in found] == ["DP-3", "HDMI-A-1"]
    assert found[1].x == 1920


def test_sin_herramientas(monkeypatch):
    monkeypatch.setattr(screens, "which", lambda *names: None)
    assert screens.detect() == []


def test_recorte_por_monitor(tmp_path):
    pytest.importorskip("PIL")
    from PIL import Image

    full = tmp_path / "desktop.png"
    Image.new("RGB", (3840, 1080), (30, 60, 90)).save(full)

    monitores = [
        screens.Screen(name="DP-3", x=0, y=0, width=1920, height=1080),
        screens.Screen(name="HDMI-A-1", x=1920, y=0, width=1920, height=1080),
    ]
    pieces = screens.crop(full, monitores, tmp_path / "screens")
    assert len(pieces) == 2

    for piece, _screen in pieces:
        with Image.open(piece) as img:
            assert img.size == (1920, 1080)


def test_recorte_un_solo_monitor(tmp_path):
    pytest.importorskip("PIL")
    from PIL import Image

    full = tmp_path / "desktop.png"
    Image.new("RGB", (1920, 1080), (1, 2, 3)).save(full)
    assert screens.crop(full, [screens.Screen("DP-3", 0, 0, 1920, 1080)], tmp_path) == []


def test_recorte_de_barra_de_tareas(tmp_path):
    pytest.importorskip("PIL")
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (3840, 1080), (8, 8, 16))
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 1034, 1919, 1079), fill=(200, 30, 30))  # barra en el monitor A
    path = tmp_path / "desktop.png"
    img.save(path)

    monitores = [
        screens.Screen(name="A", x=0, y=0, width=1920, height=1080),
        screens.Screen(name="B", x=1920, y=0, width=1920, height=1080),
    ]

    barra = screens.crop_edge(path, monitores, 0, "inferior", 46, padding=13)
    assert barra is not None
    assert barra.size == (1920, 72)
    r, g, b = barra.getpixel((960, 60))
    assert r > 150 and g < 90  # tomo la barra, no el fondo

    # el monitor B no tiene barra: el recorte deberia ser el fondo oscuro
    otra = screens.crop_edge(path, monitores, 1, "inferior", 46, padding=13)
    assert otra is not None
    r2, g2, b2 = otra.getpixel((960, 40))
    assert r2 < 60 and g2 < 60


def test_barra_de_largo_personalizado(tmp_path):
    """Una barra que no ocupa todo el borde se recorta solo en su tramo."""
    pytest.importorskip("PIL")
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (3840, 1080), (8, 8, 16))
    draw = ImageDraw.Draw(img)
    draw.rectangle((600, 1034, 1313, 1079), fill=(200, 30, 30))  # 714 px centrada
    path = tmp_path / "desktop.png"
    img.save(path)

    monitores = [
        screens.Screen(name="A", x=0, y=0, width=1920, height=1080),
        screens.Screen(name="B", x=1920, y=0, width=1920, height=1080),
    ]

    barra = screens.crop_edge(path, monitores, 0, "inferior", 46, offset=600, length=714)
    assert barra is not None
    assert barra.width < 800  # no se lleva todo el ancho
    r, g, b = barra.getpixel((barra.width // 2, barra.height - 10))
    assert r > 150 and g < 90

    completa = screens.crop_edge(path, monitores, 0, "inferior", 46)
    assert completa.width == 1920


def test_xfce_infiere_orientacion(tmp_path):
    """Xfce no dice la orientacion: se deduce del punto de anclaje."""
    pytest.importorskip("PIL")
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (1920, 1080), (9, 9, 14))
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, 1919, 71), fill=(220, 40, 40))      # barra arriba
    draw.rectangle((0, 1008, 1919, 1079), fill=(40, 220, 40))  # barra abajo
    path = tmp_path / "desktop.png"
    img.save(path)

    monitores = [screens.Screen("A", 0, 0, 1920, 1080)]

    arriba = screens.crop_edge(path, monitores, 0, "", 30, point=(960, 12))
    assert arriba is not None
    r, g, b = arriba.getpixel((960, 5))
    assert r > 150 and g < 90

    abajo = screens.crop_edge(path, monitores, 0, "", 30, point=(960, 1068))
    r2, g2, b2 = abajo.getpixel((960, abajo.height - 5))
    assert g2 > 150 and r2 < 90
