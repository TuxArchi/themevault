"""Tests de la restauracion por pantalla sobre archivos temporales."""

from __future__ import annotations

from pathlib import Path

import pytest

from themevault import plasma_layout, screen_restore
from themevault.model import Item, Manifest
from themevault.store import BlobStore

from test_plasma_layout import LIVE, LIVE_SHELL, SAVED, SAVED_SHELL

APPLETSRC = "~/.config/plasma-org.kde.plasma.desktop-appletsrc"


def _manifest(store: BlobStore, screens: list[dict] | None = None) -> Manifest:
    blob, sha, size = store.put_bytes(SAVED.encode())
    item = Item(
        kind="file",
        category="layout",
        name="Layout de Plasma",
        source=APPLETSRC,
        blob=blob,
        sha256=sha,
        size=size,
    )
    shell_blob, shell_sha, shell_size = store.put_bytes(SAVED_SHELL.encode())
    shell = Item(
        kind="file",
        category="layout",
        name="plasmashellrc",
        source="~/.config/plasmashellrc",
        blob=shell_blob,
        sha256=shell_sha,
        size=shell_size,
    )
    return Manifest(
        id="20260101-000000-kde",
        created="2026-01-01T00:00:00",
        host={"de": "kde"},
        items=[item, shell],
        preview={"screens": screens or [{"index": 0, "name": "DP-3"}]},
    )


@pytest.fixture()
def entorno(tmp_path, monkeypatch):
    store = BlobStore(tmp_path / "backup")
    manifest = _manifest(store)
    live = tmp_path / "plasma-org.kde.plasma.desktop-appletsrc"
    live.write_text(LIVE)
    shell = tmp_path / "plasmashellrc"
    shell.write_text(LIVE_SHELL)
    monkeypatch.setattr(screen_restore, "live_path", lambda: live)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "share"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    return store, manifest, live


def test_aplica_y_guarda_respaldo(entorno):
    store, manifest, live = entorno
    result = screen_restore.apply(manifest, store, {0: 1}, restart=False)

    assert result["screens"] == 1
    assert result["replaced"] == ["11"]
    assert result["added"]
    assert result["restarted"] is False

    backup = live.with_suffix(".themevault.bak")
    assert backup.read_text() == LIVE

    nuevo = plasma_layout.parse_layout(live.read_text())
    assert "11" not in plasma_layout.containment_ids(nuevo)
    assert "10" in plasma_layout.containment_ids(nuevo)  # la otra pantalla sigue


def test_restaura_el_fondo_de_la_pantalla(entorno, monkeypatch, tmp_path):
    store, manifest, live = entorno
    image = tmp_path / "fondo.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n fake")
    blob, sha, size = store.put_bytes(image.read_bytes())
    manifest.preview["screens"][0]["wallpaper"] = blob
    manifest.preview["screens"][0]["wallpaper_name"] = "fondo.png"

    result = screen_restore.apply(manifest, store, {0: 1}, restart=False)
    assert result["wallpapers"]

    destino = Path(result["wallpapers"][0])
    assert destino.is_file()
    nuevo = plasma_layout.parse_layout(live.read_text())
    escritorio = next(
        cid
        for cid in plasma_layout.containment_ids(nuevo)
        if nuevo.get(f"Containments][{cid}", "lastScreen") == "1"
        and nuevo.get(f"Containments][{cid}", "plugin") == "org.kde.plasma.folder"
    )
    assert (
        nuevo.get(f"Containments][{escritorio}][Wallpaper][org.kde.image][General", "Image")
        == destino.as_uri()
    )


def test_restaura_la_geometria_del_panel(entorno):
    store, manifest, live = entorno
    screen_restore.apply(manifest, store, {0: 1}, restart=False)

    shell = (live.parent / "plasmashellrc").read_text()
    parser = plasma_layout.parse_layout(shell)
    assert not parser.has_section("PlasmaViews][Panel 11")
    nuevo = next(
        cid
        for cid in plasma_layout.containment_ids(plasma_layout.parse_layout(live.read_text()))
        if plasma_layout.parse_layout(live.read_text()).get(f"Containments][{cid}", "plugin")
        == "org.kde.panel"
        and plasma_layout.parse_layout(live.read_text()).get(f"Containments][{cid}", "lastScreen") == "1"
    )
    assert parser.get(f"PlasmaViews][Panel {nuevo}", "panelVisibility") == "2"
    assert parser.get(f"PlasmaViews][Panel {nuevo}][Defaults", "thickness") == "46"


def test_sin_mapeo_falla(entorno):
    store, manifest, _live = entorno
    with pytest.raises(RuntimeError):
        screen_restore.apply(manifest, store, {}, restart=False)


def test_revertir_vuelve_al_anterior(entorno):
    store, manifest, live = entorno
    screen_restore.apply(manifest, store, {0: 1}, restart=False)
    assert live.read_text() != LIVE
    assert screen_restore.revert() is True
    assert live.read_text() == LIVE


# ---------------------------------------------------------- widgets / tienda


def test_paquetes_del_respaldo(entorno):
    from themevault import widgets_install

    store, manifest, _live = entorno
    assert widgets_install.backup_packages(manifest) == {}


def test_tienda_filtra_por_tipo(monkeypatch):
    from themevault import store_client

    def fake_get(url, timeout=20):
        return {
            "data": [
                {"id": 1, "name": "Reloj", "typename": "Plasma 6 Applets", "personid": "x"},
                {"id": 2, "name": "Tema", "typename": "Plasma Themes", "personid": "y"},
            ]
        }

    monkeypatch.setattr(store_client, "_get_json", fake_get)
    found = store_client.search("reloj")
    assert [f["name"] for f in found] == ["Reloj"]


def test_tienda_sin_resultados(monkeypatch):
    from themevault import store_client

    monkeypatch.setattr(store_client, "_get_json", lambda url, timeout=20: {"data": []})
    assert store_client.search("nada") == []
    assert store_client.search("") == []


def test_detalle_sin_enlace(monkeypatch):
    from themevault import store_client

    monkeypatch.setattr(
        store_client, "_get_json", lambda url, timeout=20: {"data": [{"id": 1, "name": "x"}]}
    )
    with pytest.raises(store_client.StoreError):
        store_client.details(1)
