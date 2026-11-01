"""Tests del parser de paneles y widgets."""

from __future__ import annotations

from pathlib import Path

import pytest

from themevault import widgets

APPLETSRC = """[Containments][1]
activityId=abc
formfactor=0
lastScreen=0
location=0
plugin=org.kde.plasma.folder

[Containments][3]
formfactor=2
immutability=1
lastScreen=0
location=4
plugin=org.kde.panel

[Containments][3][General]
AppletOrder=4;5;23

[Containments][3][Applets][4]
immutability=1
plugin=org.kde.plasma.kickoff

[Containments][3][Applets][5]
immutability=1
plugin=org.kde.plasma.icontasks

[Containments][3][Applets][23]
immutability=1
plugin=org.kde.plasma.digitalclock

[Containments][3][Applets][23][Configuration][General]
hidden=true
"""

PLASMASHELLRC = """[PlasmaViews][Panel 3]
floating=1
panelVisibility=2

[PlasmaViews][Panel 3][Defaults]
thickness=46
"""

XFCE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<channel name="xfce4-panel" version="1.0">
  <property name="panels" type="array">
    <property name="panel-1" type="empty">
      <property name="position" type="string" value="p=6;x=960;y=1066"/>
      <property name="length" type="uint" value="100"/>
      <property name="size" type="uint" value="30"/>
      <property name="autohide" type="bool" value="true"/>
      <property name="plugin-ids" type="array">
        <property type="int" value="1"/>
        <property type="int" value="2"/>
      </property>
    </property>
  </property>
  <property name="plugins" type="empty">
    <property name="plugin-1" type="string" value="applicationsmenu"/>
    <property name="plugin-2" type="string" value="clock"/>
  </property>
</channel>
"""


@pytest.fixture()
def aislado(monkeypatch, tmp_path):
    """Sin widgets instalados: evita depender de la maquina que corre el test."""
    monkeypatch.setattr(widgets, "PLASMOID_DIRS", (str(tmp_path / "plasmoids"),))
    monkeypatch.setattr(widgets, "APPLET_LIB_DIRS", (str(tmp_path / "applets"),))
    monkeypatch.setattr(widgets, "XFCE_PLUGIN_DIRS", (str(tmp_path / "xfce"),))
    return tmp_path


def test_plasma_panel_y_orden(aislado):
    containers, items = widgets.parse_plasma(APPLETSRC, PLASMASHELLRC)

    assert len(containers) == 2
    panel = containers[0]
    assert panel["kind"] == "panel"
    assert panel["name"] == "Panel inferior"
    assert panel["location"] == "inferior"
    assert panel["size"] == 46
    assert panel["floating"] is True
    assert panel["visibility"] == "esquivar ventanas"
    assert panel["widgets"] == 3

    # AppletOrder manda sobre el orden numerico (4, 5, 23)
    assert [w["id"] for w in items] == [
        "org.kde.plasma.kickoff",
        "org.kde.plasma.icontasks",
        "org.kde.plasma.digitalclock",
    ]
    assert [w["position"] for w in items] == [1, 2, 3]
    assert all(w["container"] == "Panel inferior" for w in items)

    # Sin instalacion presente, se marca como faltante
    assert all(w["installed"] is False for w in items)


def test_plasma_widget_oculto(aislado):
    _, items = widgets.parse_plasma(APPLETSRC, PLASMASHELLRC)
    reloj = next(w for w in items if "digitalclock" in w["id"])
    assert reloj["hidden"] is True


def test_plasma_sin_plasmashellrc(aislado):
    containers, _ = widgets.parse_plasma(APPLETSRC, "")
    panel = containers[0]
    assert panel["size"] is None
    assert panel["widgets"] == 3


def test_widget_instalado(aislado):
    applets = aislado / "applets"
    applets.mkdir()
    (applets / "org.kde.plasma.digitalclock.so").write_bytes(b"\x00")
    containers, items = widgets.parse_plasma(APPLETSRC, PLASMASHELLRC)
    reloj = next(w for w in items if "digitalclock" in w["id"])
    assert reloj["installed"] is True
    assert reloj["name"] == "Reloj digital"


def test_xfce_panel(aislado):
    containers, items = widgets.parse_xfce(XFCE_XML)
    assert len(containers) == 1
    panel = containers[0]
    assert panel["size"] == 30
    assert panel["visibility"] == "ocultar automaticamente"
    assert panel["widgets"] == 2
    assert [w["id"] for w in items] == ["applicationsmenu", "clock"]
    assert items[1]["name"] == "Reloj"


def test_resumen_y_agrupado():
    containers = [
        {"name": "Panel inferior", "size": 46, "floating": True, "visibility": "esquivar ventanas", "widgets": 2}
    ]
    items = [
        {"name": "Reloj", "container": "Panel inferior", "installed": True},
        {"name": "Tareas", "container": "Panel inferior", "installed": True},
    ]
    summary = widgets.container_summary(containers[0])
    assert "46 px" in summary and "flotante" in summary and "2 widgets" in summary

    agrupado = widgets.grouped(containers, items)
    assert agrupado[0]["items"] == items
    assert agrupado[0]["summary"] == summary


def test_containers_vacios_se_descartan():
    containers = [{"name": "Escritorio", "widgets": 0}]
    assert widgets.grouped(containers, []) == []


def test_from_items(tmp_path):
    """Deriva los widgets del appletsrc ya guardado en una copia."""
    from themevault.model import KIND_FILE, Item
    from themevault.store import BlobStore

    store = BlobStore(tmp_path)
    blob, sha, size = store.put_bytes(APPLETSRC.encode())
    item = Item(
        kind=KIND_FILE,
        category="config",
        name="Layout de Plasma",
        source="~/.config/plasma-org.kde.plasma.desktop-appletsrc",
        blob=blob,
        sha256=sha,
        size=size,
    )
    data = widgets.from_items([item], store)
    assert len(data["containers"]) == 2
    assert len(data["widgets"]) == 3


def test_reveal_paneles_autoocultos(monkeypatch):
    import subprocess

    monkeypatch.setattr(widgets, "which", lambda *names: "/usr/bin/qdbus6")
    monkeypatch.setattr(
        widgets,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args=[], returncode=0, stdout=b"3,7"),
    )
    assert widgets.reveal_hidden_panels() == [3, 7]


def test_restore_paneles(monkeypatch):
    import subprocess

    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(args=[], returncode=0, stdout=b"")

    monkeypatch.setattr(widgets, "which", lambda *names: "/usr/bin/qdbus6")
    monkeypatch.setattr(widgets, "run", fake_run)

    widgets.restore_hidden_panels([3, 7])
    assert calls and "ids=[3,7]" in calls[0][-1]


def test_reveal_sin_qdbus(monkeypatch):
    monkeypatch.setattr(widgets, "which", lambda *names: None)
    assert widgets.reveal_hidden_panels() == []


def test_gnome_barra_dock_y_extensiones(aislado):
    dumps = {
        "/org/gnome/shell/": "enabled-extensions=['dash-to-dock@micxgx.gmail.com', 'user-theme@gnome-shell-extensions.gcampax.github.com']\n",
        "/org/gnome/shell/extensions/dash-to-dock/": (
            "dock-position='LEFT'\n"
            "dash-max-icon-size=56\n"
            "autohide=false\n"
            "dock-fixed=true\n"
        ),
    }
    containers, items = widgets.parse_gnome(dumps)

    barra = containers[0]
    assert barra["kind"] == "panel"
    assert barra["name"] == "Barra superior"
    assert barra["location"] == "superior"
    assert barra["widgets"] == 2

    assert [w["name"] for w in items] == ["Dash to Dock", "Tema de usuario"]
    assert all(w["container"] == "Barra superior" for w in items)

    dock = containers[1]
    assert dock["kind"] == "dock"
    assert dock["location"] == "izquierda"
    assert dock["size"] == 56
    ajustes = {s["label"]: s["value"] for s in dock["settings"]}
    assert ajustes["Posicion"] == "izquierda"
    assert ajustes["Iconos"] == "56 px"
    assert ajustes["Auto-ocultar"] == "no"


def test_gnome_sin_extensiones(aislado):
    containers, items = widgets.parse_gnome({"/org/gnome/shell/": "enabled-extensions=[]\n"})
    assert containers and containers[0]["widgets"] == 0
    assert items == []
