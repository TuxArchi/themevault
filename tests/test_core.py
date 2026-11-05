"""Tests del core. No requieren escritorio: usan un HOME temporal."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from themevault.adapters.base import Collector
from themevault.adapters.kde import KdeAdapter
from themevault.backup import BackupEngine
from themevault.drivers import read_channel
from themevault.model import KIND_FILE, Manifest
from themevault.restore import build_plan
from themevault.store import BlobStore


@pytest.fixture()
def fake_home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_DATA_HOME", str(home / ".local" / "share"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    return home


def test_blob_store_dedupe(tmp_path):
    store = BlobStore(tmp_path / "backup")
    rel_a, sha_a, _ = store.put_bytes(b"hola")
    rel_b, sha_b, _ = store.put_bytes(b"hola")
    assert sha_a == sha_b
    assert rel_a == rel_b
    assert store.read(rel_a) == b"hola"


def test_tree_roundtrip_is_deterministic(tmp_path):
    source = tmp_path / "MiTema"
    (source / "gtk-3.0").mkdir(parents=True)
    (source / "index.theme").write_text("Name=MiTema\n")
    (source / "gtk-3.0" / "gtk.css").write_text("/* css */\n")

    store = BlobStore(tmp_path / "a")
    rel, sha, _, count = store.put_tree(source, arcname=source.name)
    assert count == 2

    # El mismo contenido en otra copia produce el mismo hash (dedupe real).
    other = BlobStore(tmp_path / "b")
    assert other.put_tree(source, arcname=source.name)[1] == sha

    target = tmp_path / "destino"
    store.extract_tree(rel, target)
    assert (target / "MiTema" / "index.theme").read_text().startswith("Name=MiTema")


def test_backup_and_restore_theme(fake_home):
    theme = fake_home / ".themes" / "MiTema"
    theme.mkdir(parents=True)
    (theme / "index.theme").write_text("Name=MiTema\n")

    engine = BackupEngine(fake_home / "vault")
    # En CI no hay escritorio: se fuerza el adaptador para no depender del host.
    manifest = engine.create(adapters=[KdeAdapter()], preview=False, label="test")
    assert isinstance(manifest, Manifest)
    assert any(item.kind != KIND_FILE for item in manifest.items)

    # se guarda el manifest en disco y se puede releer
    saved = json.loads((engine.backup_dir(manifest.id) / "manifest.json").read_text())
    assert saved["id"] == manifest.id

    # borramos el tema y restauramos
    import shutil

    shutil.rmtree(theme)
    store = engine.store(manifest.id)
    actions = build_plan(manifest, store, only={"theme"})
    assert all(a.status == "ok" for a in actions)

    from themevault.restore import apply_plan

    report = apply_plan(actions, store, safety=False)
    assert report.applied >= 1
    assert (theme / "index.theme").exists()


def test_restore_refuses_paths_outside_home(fake_home, tmp_path):
    from themevault.model import KIND_TREE, Item

    manifest = Manifest(
        id="x",
        created="2026-01-01T00:00:00",
        host={},
        items=[Item(kind=KIND_TREE, category="theme", name="evil", source="/usr/share/themes/evil")],
    )
    actions = build_plan(manifest, None)
    assert actions[0].status == "blocked"


def test_xfconf_channel_parsing(fake_home):
    channels = fake_home / ".config" / "xfce4" / "xfconf" / "xfconfd" / "xfconf-perchannel-xml"
    channels.mkdir(parents=True)
    (channels / "xsettings.xml").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<channel name="xsettings" version="1.0">
  <property name="Net" type="empty">
    <property name="ThemeName" type="string" value="Adwaita-dark"/>
    <property name="IconThemeName" type="string" value="Papirus"/>
  </property>
  <property name="Xft" type="empty">
    <property name="DPI" type="int" value="96"/>
  </property>
  <property name="Arreglo" type="array">
    <property type="int" value="1"/>
    <property type="int" value="2"/>
  </property>
</channel>
"""
    )
    props, skipped = read_channel("xsettings")
    paths = {p["prop"]: p for p in props}
    assert paths["/Net/ThemeName"]["value"] == "Adwaita-dark"
    assert paths["/Xft/DPI"]["type"] == "int"
    assert skipped == 1  # el array se omite pero se cuenta


def test_collector_skips_missing_paths(fake_home, tmp_path):
    store = BlobStore(tmp_path / "b")
    collector = Collector(store)
    assert collector.add_file("~/.no-existe/archivo.ini", "config") is None
    assert collector.items == []


def test_detecta_hyprland_por_su_config(fake_home, monkeypatch):
    from themevault.detect import detect_de

    for name in ("XDG_CURRENT_DESKTOP", "XDG_SESSION_DESKTOP", "DESKTOP_SESSION"):
        monkeypatch.delenv(name, raising=False)

    hypr = fake_home / ".config" / "hypr"
    hypr.mkdir(parents=True)
    (hypr / "hyprland.conf").write_text("$mainMod = SUPER\n")

    assert detect_de() == "hyprland"
