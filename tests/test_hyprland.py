"""Soporte de Hyprland: respaldo, atajos, Waybar y privacidad."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from themevault.adapters.base import Collector
from themevault.adapters.hyprland import HyprlandAdapter
from themevault.backup import BackupEngine
from themevault.model import KIND_FILE, Manifest
from themevault.restore import apply_plan, build_plan
from themevault.store import BlobStore
from themevault import widgets

HYPRLAND = """\
$mainMod = SUPER
$terminal = kitty

env = XCURSOR_THEME, Adwaita
env = GTK_THEME, Catppuccin-Dark

general {
    gaps_in = 5
}

bind = $mainMod, Return, exec, $terminal
bind = $mainMod SHIFT, Q, killactive, # cerrar ventana
bindm = $mainMod, mouse:272, movewindow
binde = $mainMod, left, movefocus, l

submap = resize
bind = , right, resizeactive, 10 0
submap = reset

source = ~/.config/hypr/conf/binds.conf
source = ./conf/linked.conf
source = ~/dotfiles/hypr/extra.conf
source = ~/Documents/privado.conf
source = ~/scripts/atajo.sh
"""

BINDS = """\
$bindsMod = ALT
bind = $bindsMod, E, exec, ~/.local/bin/editor
unbind = $mainMod, Return
"""

EXTRA = """\
bind = $mainMod, B, exec, firefox
"""

HYPRPAPER = """\
preload = ~/Pictures/wall.png
wallpaper = , ~/Pictures/wall.png
"""

WAYBAR = """\
{
  // barra superior
  "position": "top",
  "height": 34,
  "layer": "top",
  "spacing": 4,
  "modules-left": ["hyprland/workspaces", "custom/launcher"],
  "modules-center": ["clock"],
  "modules-right": ["network", "battery",],
}
"""

GTK = """\
[Settings]
gtk-theme-name=Adwaita
gtk-icon-theme-name=Papirus-Dark
gtk-cursor-theme-name=Breeze
"""


@pytest.fixture()
def fake_home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_DATA_HOME", str(home / ".local" / "share"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))

    hypr = home / ".config" / "hypr"
    (hypr / "conf").mkdir(parents=True)
    (hypr / "scripts").mkdir()
    (hypr / "wallpapers").mkdir()
    (hypr / "hyprland.conf").write_text(HYPRLAND)
    (hypr / "conf" / "binds.conf").write_text(BINDS)
    (hypr / "hyprpaper.conf").write_text(HYPRPAPER)
    (hypr / "notas.txt").write_text("no respaldar")
    (hypr / "foto.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (hypr / "scripts" / "privado.sh").write_text("#!/bin/sh\necho privado\n")
    (hypr / "wallpapers" / "fondo.jpg").write_bytes(b"foto")

    dotfiles = home / "dotfiles" / "hypr"
    dotfiles.mkdir(parents=True)
    (dotfiles / "extra.conf").write_text(EXTRA)
    (dotfiles / "linked.conf").write_text("bind = $mainMod, L, exec, kitty\n")
    (hypr / "conf" / "linked.conf").symlink_to(dotfiles / "linked.conf")

    documents = home / "Documents"
    documents.mkdir()
    (documents / "privado.conf").write_text("bind = SUPER, X, exec, secreto\n")

    scripts = home / "scripts"
    scripts.mkdir()
    (scripts / "atajo.sh").write_text("#!/bin/sh\necho atajo\n")

    binary = home / ".local" / "bin"
    binary.mkdir(parents=True)
    editor = binary / "editor"
    editor.write_text("#!/bin/sh\n")
    editor.chmod(0o755)

    pictures = home / "Pictures"
    pictures.mkdir()
    (pictures / "wall.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (pictures / "foto.jpg").write_bytes(b"foto")

    (home / ".ssh").mkdir()
    (home / ".ssh" / "id_ed25519").write_text("no respaldar")

    gtk = home / ".config" / "gtk-3.0"
    gtk.mkdir(parents=True)
    (gtk / "settings.ini").write_text(GTK)

    waybar = home / ".config" / "waybar"
    waybar.mkdir(parents=True)
    (waybar / "config").write_text(WAYBAR)
    (waybar / "style.css").write_text("#waybar { color: #fff; }\n")
    (waybar / "scripts").mkdir()
    (waybar / "scripts" / "foo.sh").write_text("#!/bin/sh\n")

    kitty = home / ".config" / "kitty"
    kitty.mkdir(parents=True)
    (kitty / "kitty.conf").write_text("font_family Fira Code\n")
    (kitty / "theme.sh").write_text("#!/bin/sh\n")

    return home


def collect(home: Path) -> Collector:
    store = BlobStore(home.parent / "store")
    collector = Collector(store)
    HyprlandAdapter().collect(collector)
    return collector


def sources(collector: Collector) -> set[str]:
    return {item.source for item in collector.items}


def test_solo_respalda_configuracion_segura(fake_home):
    collector = collect(fake_home)
    found = sources(collector)

    assert "~/.config/hypr/hyprland.conf" in found
    assert "~/.config/hypr/conf/binds.conf" in found
    assert "~/.config/hypr/hyprpaper.conf" in found
    assert "~/.config/waybar/config" in found
    assert "~/.config/waybar/style.css" in found
    assert "~/.config/kitty/kitty.conf" in found
    assert "~/dotfiles/hypr/extra.conf" in found
    assert "~/dotfiles/hypr/linked.conf" in found
    assert "~/.config/hypr/conf/linked.conf" not in found

    # Nada personal, multimedia ni scripts.
    for source in found:
        assert "Pictures" not in source
        assert "Documents" not in source
        assert ".ssh" not in source
        assert "/scripts/" not in source
        assert not source.endswith((".png", ".jpg", ".sh", ".txt"))

    skipped = " ".join(reason for _path, reason in collector.skipped)
    assert "ruta personal" in skipped
    assert "carpeta omitida por privacidad" in skipped
    assert "archivo multimedia" in skipped
    assert "extensión o nombre no permitido" in skipped


def test_parsea_atajos_con_variables_submapas_y_unbind(fake_home):
    collector = collect(fake_home)
    keybinds = collector.meta["keybinds"]
    combos = {entry["combo"]: entry for entry in keybinds}

    assert "SUPER + Return" not in combos  # lo elimina el unbind del include
    cerrar = combos["SUPER SHIFT + Q"]
    assert cerrar["dispatcher"] == "killactive"
    assert cerrar["description"] == "cerrar ventana"
    assert combos["ALT + E"]["dispatcher"] == "exec"
    assert combos["ALT + E"]["script"] == "~/.local/bin/editor"
    assert combos["ALT + E"]["source"] == "~/.config/hypr/conf/binds.conf"
    assert combos["SUPER + L"]["source"] == "~/dotfiles/hypr/linked.conf"

    mouse = combos["SUPER + mouse:272"]
    assert mouse["kind"] == "bindm"
    assert mouse["flags"] == "m"

    focus = combos["SUPER + left"]
    assert focus["kind"] == "binde"
    assert focus["flags"] == "e"

    resize = combos["right"]
    assert resize["submap"] == "resize"
    assert resize["dispatcher"] == "resizeactive"


def test_temas_y_wallpaper(fake_home):
    adapter = HyprlandAdapter()
    themes = adapter.themes()
    assert themes["icons"] == "Papirus-Dark"
    assert themes["cursor"] == "Adwaita"
    assert themes["gtk"] == "Catppuccin-Dark"

    found = adapter.preview_sources()
    assert [path.name for path in found] == ["wall.png"]


def test_waybar_se_interpreta_como_panel():
    containers, modules = widgets.parse_waybar(WAYBAR)

    assert len(containers) == 1
    bar = containers[0]
    assert bar["name"] == "Waybar"
    assert bar["location"] == "superior"
    assert bar["size"] == 34
    assert bar["widgets"] == 5
    assert [item["id"] for item in modules] == [
        "hyprland/workspaces",
        "custom/launcher",
        "clock",
        "network",
        "battery",
    ]
    assert modules[0]["name"] == "Áreas de trabajo"
    assert modules[1]["name"] == "Personalizado: Launcher"


def test_waybar_desde_los_items_de_la_copia(fake_home):
    collector = collect(fake_home)
    layout = widgets.from_items(collector.items, collector.store)

    assert layout["containers"][0]["name"] == "Waybar"
    assert layout["containers"][0]["size"] == 34
    assert layout["widgets"][0]["name"] == "Áreas de trabajo"


def test_backup_sin_imagenes_y_restore(fake_home):
    engine = BackupEngine(fake_home / "vault")
    manifest = engine.create(adapters=[HyprlandAdapter()], preview=False, label="hypr")

    assert isinstance(manifest, Manifest)
    assert manifest.de == "hyprland"
    assert manifest.keybinds
    assert "wallpaper" not in manifest.preview
    preview_files = [
        path
        for path in (engine.backup_dir(manifest.id) / "preview").rglob("*")
        if path.is_file()
    ]
    assert preview_files == []
    assert all(item.kind == KIND_FILE for item in manifest.items if item.source.endswith(".conf"))

    # El script del atajo se lista como dependencia, pero no se copia.
    assert not any("editor" in item.source for item in manifest.items)
    assert any(entry.get("script") == "~/.local/bin/editor" for entry in manifest.keybinds)

    # Restaurar layout recupera la configuración y los atajos.
    main = fake_home / ".config" / "hypr" / "hyprland.conf"
    main.write_text("# modificado\n")
    store = engine.store(manifest.id)
    actions = build_plan(manifest, store, only={"layout"})
    report = apply_plan(actions, store, safety=False)
    assert report.failures == []
    assert "$mainMod = SUPER" in main.read_text()

    # Los archivos personales siguen fuera de la copia.
    for item in manifest.items:
        assert "Pictures" not in item.source
        assert "Documents" not in item.source
        assert ".ssh" not in item.source


def test_captura_usa_workspace_especial(monkeypatch):
    import subprocess

    from themevault import preview

    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(args=[], returncode=0, stdout=b"")

    monkeypatch.setattr(
        preview,
        "which",
        lambda *names: "/usr/bin/hyprctl" if "hyprctl" in names else None,
    )
    monkeypatch.setattr(preview, "run", fake_run)

    mechanism = preview._show_desktop()
    assert mechanism == "hyprland"
    assert calls[0][:4] == ["hyprctl", "dispatch", "togglespecialworkspace", "themevault-capture"]

    preview._restore_windows(mechanism)
    assert calls[-1][:4] == ["hyprctl", "dispatch", "togglespecialworkspace", "themevault-capture"]


def test_manifest_roundtrip_de_atajos():
    manifest = Manifest(
        id="x",
        created="2026-01-01T00:00:00",
        host={"de": "hyprland"},
        keybinds=[{"combo": "SUPER + Q", "dispatcher": "killactive"}],
    )
    raw = manifest.to_dict()
    assert raw["keybinds"][0]["combo"] == "SUPER + Q"
    again = Manifest.from_dict(raw)
    assert again.keybinds == manifest.keybinds


def test_perfil_hyprland_no_exporta_atajos(fake_home):
    from themevault.profile import build_profile

    engine = BackupEngine(fake_home / "vault")
    manifest = engine.create(adapters=[HyprlandAdapter()], preview=False)
    store = engine.store(manifest.id)
    profile, dropped = build_profile(
        manifest, store, name="Mi Hypr", author="yo", license="MIT"
    )

    text = json.dumps(profile.to_dict(), ensure_ascii=False)
    assert profile.desktop == "hyprland"
    assert profile.settings == []
    assert "keybinds" not in text
    assert "hyprland.conf" not in text
    assert "killactive" not in text
    assert dropped
