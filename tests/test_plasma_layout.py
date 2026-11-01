"""Tests de la mezcla del layout de Plasma (restore por pantalla)."""

from __future__ import annotations

import configparser

from themevault import plasma_layout

SAVED = """[General]
Version=2

[Containments][1]
activityId=aaa
formfactor=0
lastScreen=0
plugin=org.kde.plasma.folder

[Containments][1][Wallpaper][org.kde.image][General]
Image=file:///home/viejo/fondo.png

[Containments][1][General]
positions={"1920x1080":["1","17"]}

[Containments][3]
activityId=aaa
formfactor=2
lastScreen=0
location=3
plugin=org.kde.panel

[Containments][3][General]
AppletOrder=4;5

[Containments][3][Applets][4]
plugin=org.kde.plasma.digitalclock

[Containments][3][Applets][5]
plugin=org.kde.plasma.systemtray

[Containments][3][Applets][5][Configuration][General]
SystrayContainmentId=6

[Containments][6]
activityId=aaa
formfactor=2
lastScreen=0
plugin=org.kde.plasma.private.systemtray

[Containments][7]
activityId=aaa
formfactor=0
lastScreen=1
plugin=org.kde.plasma.folder
"""

LIVE = """[General]
Version=2

[Containments][10]
activityId=bbb
formfactor=2
lastScreen=0
location=3
plugin=org.kde.panel

[Containments][10][General]
AppletOrder=20

[Containments][10][Applets][20]
plugin=org.kde.plasma.digitalclock

[Containments][11]
activityId=bbb
formfactor=0
lastScreen=1
plugin=org.kde.plasma.folder

[Containments][11][General]
positions={"viejo":"1"}
"""


def _parse(text: str) -> configparser.RawConfigParser:
    parser = configparser.RawConfigParser(strict=False)
    parser.optionxform = str
    parser.read_string(text)
    return parser


def test_agrupa_por_pantalla():
    grouped = plasma_layout.by_screen(_parse(SAVED))
    assert sorted(grouped[0]) == ["1", "3", "6"]
    assert grouped[1] == ["7"]


def test_mezcla_reemplaza_y_renumera():
    nuevo, report = plasma_layout.merge(SAVED, LIVE, {0: 1}, activity_id="bbb")
    parser = _parse(nuevo)

    # la pantalla 1 del sistema vivo fue reemplazada
    assert "11" in report.replaced
    assert "11" not in plasma_layout.containment_ids(parser)

    # la pantalla 0 viva no se toco
    assert "10" in plasma_layout.containment_ids(parser)

    # lo agregado quedo en la pantalla destino y con la actividad actual
    ids = plasma_layout.containment_ids(parser)
    nuevos = [cid for cid in ids if cid not in ("10",)]
    assert len(nuevos) == 3  # escritorio + panel + bandeja de la pantalla 0
    for cid in nuevos:
        assert parser.get(f"Containments][{cid}", "lastScreen") == "1"
        assert parser.get(f"Containments][{cid}", "activityId") == "bbb"

    # el orden de applets se reescribio
    panel = next(cid for cid in nuevos if parser.get(f"Containments][{cid}", "plugin") == "org.kde.panel")
    order = parser.get(f"Containments][{panel}][General", "AppletOrder")
    applets = plasma_layout.applets_of(parser, panel)
    assert order == ";".join(applets)
    assert set(order.split(";")) == set(applets)

    # la referencia de la bandeja apunta al containment nuevo
    tray = next(
        cid
        for cid in nuevos
        if parser.get(f"Containments][{cid}", "plugin") == "org.kde.plasma.private.systemtray"
    )
    systray = next(
        aid
        for aid in plasma_layout.applets_of(parser, panel)
        if parser.get(f"Containments][{panel}][Applets][{aid}", "plugin")
        == "org.kde.plasma.systemtray"
    )
    value = parser.get(
        f"Containments][{panel}][Applets][{systray}][Configuration][General",
        "SystrayContainmentId",
    )
    assert value == tray


def test_no_toca_globales_y_conserva_wallpaper():
    nuevo, _ = plasma_layout.merge(SAVED, LIVE, {0: 1})
    parser = _parse(nuevo)
    assert parser.get("General", "Version") == "2"
    escritorio = next(
        cid
        for cid in plasma_layout.containment_ids(parser)
        if parser.get(f"Containments][{cid}", "plugin") == "org.kde.plasma.folder"
        and parser.get(f"Containments][{cid}", "lastScreen") == "1"
    )
    image = parser.get(
        f"Containments][{escritorio}][Wallpaper][org.kde.image][General", "Image"
    )
    assert image == "file:///home/viejo/fondo.png"


def test_pantalla_inexistente_avisa():
    _, report = plasma_layout.merge(SAVED, LIVE, {5: 0})
    assert report.warnings


def test_sin_mapeo_no_cambia_nada():
    nuevo, _ = plasma_layout.merge(SAVED, LIVE, {})
    assert _parse(nuevo).sections() == _parse(LIVE).sections()


def test_wallpapers_por_pantalla(tmp_path):
    fondo = tmp_path / "fondo.png"
    fondo.write_bytes(b"x")
    texto = SAVED.replace("/home/viejo/fondo.png", str(fondo))
    found = plasma_layout.wallpapers_by_screen(_parse(texto))
    assert found[0] == str(fondo)


def test_reescribe_wallpaper_de_la_pantalla():
    texto = LIVE.replace(
        "[Containments][11]\n",
        "[Containments][11]\n",
    ) + """
[Containments][11][Wallpaper][org.kde.image][General]
Image=file:///viejo.png
"""
    nuevo = plasma_layout.rewrite_wallpaper(texto, 1, "file:///nuevo.png")
    parser = _parse(nuevo)
    assert (
        parser.get("Containments][11][Wallpaper][org.kde.image][General", "Image")
        == "file:///nuevo.png"
    )
