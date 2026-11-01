"""Tests de la portada compuesta (necesitan Pillow)."""

from __future__ import annotations

import pytest

pytest.importorskip("PIL")

from PIL import Image  # noqa: E402

from themevault import cover  # noqa: E402


def test_portada_con_wallpaper(tmp_path):
    wallpaper = tmp_path / "wall.jpg"
    Image.new("RGB", (800, 450), (40, 80, 160)).save(wallpaper)

    data = cover.build_cover(None, wallpaper, {}, tmp_path, palette=["#112233", "#445566"])
    assert data["cover"] == "preview/cover.png"
    assert (tmp_path / "preview" / "cover.png").is_file()

    with Image.open(tmp_path / "preview" / "cover.png") as img:
        assert img.size == cover.COVER_SIZE


def test_portada_sin_imagen(tmp_path):
    assert cover.build_cover(None, None, {}, tmp_path) == {}


def test_portada_ignora_captura_negra(tmp_path):
    negra = tmp_path / "desktop.png"
    Image.new("RGB", (640, 360), (0, 0, 0)).save(negra)
    wallpaper = tmp_path / "wall.jpg"
    Image.new("RGB", (640, 360), (200, 30, 30)).save(wallpaper)

    data = cover.build_cover(negra, wallpaper, {}, tmp_path)
    assert data["cover"]
    with Image.open(tmp_path / "preview" / "cover.png") as img:
        # el pixel central viene del wallpaper rojo, no de la captura negra
        r, g, b = img.convert("RGB").getpixel((400, 300))
    assert r > 120 and g < 90


def test_busqueda_de_iconos_en_tema_falso(tmp_path, monkeypatch):
    root = tmp_path / "icons"
    theme = root / "MiTema" / "places" / "48"
    theme.mkdir(parents=True)
    (theme / "folder.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg'/>")
    monkeypatch.setattr(cover, "ICON_ROOTS", (str(root),))

    found = cover.find_icon("MiTema", "places", ("folder", "inode-directory"))
    assert found is not None and found.name == "folder.svg"

    assert cover.find_icon("MiTema", "apps", ("no-existe",)) is None


def test_rasterizado_sin_rsvg(monkeypatch, tmp_path):
    svg = tmp_path / "x.svg"
    svg.write_text("<svg xmlns='http://www.w3.org/2000/svg'/>")
    monkeypatch.setattr(cover, "which", lambda *names: None)
    assert cover.rasterize(svg, 64) is None
