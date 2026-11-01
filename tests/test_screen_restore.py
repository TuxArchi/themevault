"""Tests de la restauracion por pantalla sobre archivos temporales."""

from __future__ import annotations

from pathlib import Path

import pytest

from themevault import plasma_layout, screen_restore
from themevault.model import Item, Manifest
from themevault.store import BlobStore

from test_plasma_layout import LIVE, SAVED

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
    return Manifest(
        id="20260101-000000-kde",
        created="2026-01-01T00:00:00",
        host={"de": "kde"},
        items=[item],
        preview={"screens": screens or [{"index": 0, "name": "DP-3"}]},
    )


@pytest.fixture()
def entorno(tmp_path, monkeypatch):
    store = BlobStore(tmp_path / "backup")
    manifest = _manifest(store)
    live = tmp_path / "plasma-org.kde.plasma.desktop-appletsrc"
    live.write_text(LIVE)
    monkeypatch.setattr(screen_restore, "live_path", lambda: live)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "share"))
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
