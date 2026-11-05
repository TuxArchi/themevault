"""Bundle de comunidad: wallpaper, plugins, keybinds seguros y video."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from themevault.model import Item, Manifest
from themevault.profile import build_profile, export_bundle, validate
from themevault.profile_apply import apply_profile
from themevault.store import BlobStore
from themevault.video import tools, transcode


@pytest.fixture()
def fake_home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_DATA_HOME", str(home / ".local" / "share"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    return home


def _backup(home: Path) -> tuple[BlobStore, Manifest]:
    build = home / "build"
    store = BlobStore(build)
    preview = build / "preview"
    preview.mkdir(parents=True)
    try:
        from PIL import Image
    except ImportError:
        pytest.skip("Pillow no esta instalado")
    Image.new("RGB", (640, 360), (30, 30, 40)).save(preview / "wallpaper.png")

    plugin = home / ".local" / "share" / "plasma" / "plasmoids" / "test-widget"
    plugin.mkdir(parents=True)
    (plugin / "metadata.json").write_text('{"KPlugin":{"Name":"Test"}}')
    (plugin / "contents").mkdir()
    (plugin / "contents" / "ui.qml").write_text("import QtQuick\nItem {}\n")
    blob, sha, size, _count = store.put_tree(plugin, arcname=plugin.name)
    items = [
        Item(
            kind="tree",
            category="layout",
            name=plugin.name,
            source="~/.local/share/plasma/plasmoids/test-widget",
            blob=blob,
            sha256=sha,
            size=size,
        )
    ]
    manifest = Manifest(
        id="copia",
        created="2026-01-01T00:00:00",
        host={
            "de": "kde",
            "themes": {"icons": "Papirus-Dark", "cursor": "Breeze", "gtk": "Adwaita"},
        },
        items=items,
        preview={"wallpaper": "preview/wallpaper.png", "palette": ["#1e1e2e"]},
        containers=[{"name": "Panel inferior", "kind": "panel", "size": 46, "widgets": 1}],
        widgets=[{"id": "test-widget", "name": "Test", "container": "Panel inferior"}],
        keybinds=[
            {"combo": "Super+Q", "dispatcher": "killactive", "arg": "", "script": ""},
            {"combo": "Super+X", "dispatcher": "exec", "arg": "~/privado.sh", "script": "~/privado.sh"},
        ],
    )
    return store, manifest


def test_build_profile_filtra_atajos_y_arma_layout(fake_home):
    store, manifest = _backup(fake_home)
    profile, _dropped = build_profile(
        manifest, store, name="Demo", author="yo", license="MIT"
    )
    assert profile.appearance["icon_theme"] == "Papirus-Dark"
    assert [entry["combo"] for entry in profile.keybinds] == ["Super+Q"]
    assert profile.layout["containers"][0]["name"] == "Panel inferior"
    assert profile.layout["widgets"][0]["id"] == "test-widget"


def test_export_bundle_incluye_wallpaper_y_plugin(fake_home):
    store, manifest = _backup(fake_home)
    profile, _ = build_profile(manifest, store, name="Demo", author="yo", license="MIT")
    out = fake_home / "perfil"
    export_bundle(profile, out, manifest=manifest, store=store, include_cover=True)

    assert (out / "wallpaper.jpg").is_file()
    assert (out / "cover.jpg").is_file()
    assert (out / "plugins" / "test-widget.tar.gz").is_file()
    data = json.loads((out / "profile.json").read_text())
    assert data["wallpaper"]["kind"] == "image"
    assert data["wallpaper"]["sha256"]
    assert data["plugins"][0]["target"].endswith("/test-widget")
    assert data["keybinds"][0]["combo"] == "Super+Q"
    assert len(data["keybinds"]) == 1
    assert validate(profile) == []


@pytest.mark.skipif(tools() is None, reason="ffmpeg/ffprobe no instalados")
def test_export_bundle_video_wallpaper(fake_home):
    store, manifest = _backup(fake_home)
    video = fake_home / "fondo.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=green:s=320x180:d=1",
            "-pix_fmt",
            "yuv420p",
            str(video),
        ],
        check=True,
    )
    blob, sha, size = store.put_bytes(
        f"exec-once = mpvpaper -o 'no-audio loop' '*' ~/fondo.mp4\n".encode()
    )
    manifest.items.append(
        Item(
            kind="file",
            category="config",
            name="hyprland.conf",
            source="~/.config/hypr/hyprland.conf",
            blob=blob,
            sha256=sha,
            size=size,
        )
    )
    profile, _ = build_profile(manifest, store, name="Demo video", author="yo", license="MIT")
    out = fake_home / "perfil-video"
    export_bundle(profile, out, manifest=manifest, store=store)

    assert (out / "wallpaper.mp4").is_file()
    assert (out / "wallpaper.jpg").is_file()
    data = json.loads((out / "profile.json").read_text())
    assert data["wallpaper"]["kind"] == "video"
    assert data["wallpaper"]["duration"] <= 10 * 60


def test_export_bundle_incluye_asset_personalizado(fake_home):
    store, manifest = _backup(fake_home)
    theme = fake_home / ".themes" / "MiTema"
    (theme / "gtk-3.0").mkdir(parents=True)
    (theme / "index.theme").write_text("Name=MiTema\n")
    (theme / "gtk-3.0" / "gtk.css").write_text("/* css */\n")
    blob, sha, size, _count = store.put_tree(theme, arcname=theme.name)
    manifest.items.append(
        Item(
            kind="tree",
            category="theme",
            name=theme.name,
            source="~/.themes/MiTema",
            blob=blob,
            sha256=sha,
            size=size,
        )
    )
    profile, _ = build_profile(manifest, store, name="Demo tema", author="yo", license="MIT")
    out = fake_home / "perfil-tema"
    export_bundle(profile, out, manifest=manifest, store=store)

    assert (out / "assets" / "theme-MiTema.tar.gz").is_file()
    data = json.loads((out / "profile.json").read_text())
    assert data["assets"][0]["target"] == "~/.themes/MiTema"
    report = apply_profile(profile, out, safety=False, apply_wallpaper=False)
    assert (fake_home / ".themes" / "MiTema" / "index.theme").is_file()
    assert "MiTema" in report["assets"]


def test_apply_profile_instala_plugin(fake_home):
    store, manifest = _backup(fake_home)
    profile, _ = build_profile(manifest, store, name="Demo", author="yo", license="MIT")
    out = fake_home / "perfil"
    export_bundle(profile, out, manifest=manifest, store=store)

    report = apply_profile(profile, out, safety=False, apply_wallpaper=False)
    target = fake_home / ".local" / "share" / "plasma" / "plasmoids" / "test-widget"
    assert target.is_dir()
    assert (target / "metadata.json").is_file()
    assert report["plugins"] == ["test-widget"]
    assert not report["failures"]


@pytest.mark.skipif(tools() is None, reason="ffmpeg/ffprobe no instalados")
def test_video_transcode_genera_mp4_y_frame(tmp_path):
    source = tmp_path / "entrada.mp4"
    proc = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=320x180:d=1",
            "-pix_fmt",
            "yuv420p",
            str(source),
        ],
        capture_output=True,
    )
    assert proc.returncode == 0, proc.stderr.decode()
    target = tmp_path / "wallpaper.mp4"
    info = transcode(source, target, max_bytes=5 * 1024 * 1024)
    assert target.is_file()
    assert (tmp_path / "wallpaper.jpg").is_file()
    assert info["width"] > 0
    assert target.stat().st_size <= 5 * 1024 * 1024
