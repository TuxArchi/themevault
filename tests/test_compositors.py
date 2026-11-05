"""Compositores Wayland: niri, Sway, River, Wayfire y labwc."""

from __future__ import annotations

from pathlib import Path

import pytest

from themevault.adapters.base import Collector
from themevault.adapters.hyprland import HyprlandAdapter
from themevault.adapters.labwc import LabwcAdapter
from themevault.adapters.niri import NiriAdapter
from themevault.adapters.river import RiverAdapter
from themevault.adapters.sway import SwayAdapter
from themevault.adapters.wayfire import WayfireAdapter
from themevault.backup import BackupEngine
from themevault.keybinds import keybinds_from_items
from themevault.restore import apply_plan, build_plan
from themevault.store import BlobStore
from themevault import widgets

NIRI = """\
spawn-at-startup "waybar"
spawn-at-startup "swaybg" "-i" "~/niri-wall.png"
cursor {
    xcursor-theme "Breeze"
    xcursor-size 24
}
environment {
    XCURSOR_THEME "Breeze"
}
include "binds.kdl"
binds {
    Mod+Return { spawn "kitty"; }
    Mod+Q { close-window; }
    Mod+Shift+E { quit skip-confirmation=true; }
    Mod+WheelScrollDown cooldown-ms=150 { focus-workspace-down; }
}
"""

NIRI_BINDS = """\
binds {
    Mod+T { spawn "foot"; }
}
"""

SWAY = """\
set $mod Mod4
set $term kitty

include ~/.config/sway/config.d/*

bindsym $mod+Return exec $term
bindsym --release $mod+Shift+q kill
bindcode 36 exec $term
mode "resize" {
    bindsym $mod+Right resize grow width 10 px
    bindsym Return mode "default"
}

bar {
    position top
    height 30
    status_command i3status
}
output * bg ~/sway-wall.png fill
seat seat0 xcursor_theme Breeze 24
"""

RIVER = """\
#!/bin/sh
mod=Mod
riverctl map normal $mod+Return spawn kitty
riverctl map -repeat normal $mod+Q close
riverctl map-pointer normal $mod+BTN_LEFT move-view
riverctl xcursor-theme Breeze 24
swaybg -i ~/river-wall.png
"""

WAYFIRE = """\
[core]
xcursor_theme = Breeze
[command]
binding_terminal = <super> KEY_ENTER
command_terminal = kitty
[autostart]
bg = swaybg -i ~/wayfire-wall.png
"""

LABWC = """\
<labwc_config>
  <keyboard>
    <keybind key="W-Return">
      <action name="Execute"><command>kitty</command></action>
    </keybind>
    <keybind key="W-q"><action name="Close"/></keybind>
  </keyboard>
  <theme><cursorTheme>Breeze</cursorTheme></theme>
</labwc_config>
"""


@pytest.fixture()
def fake_home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_DATA_HOME", str(home / ".local" / "share"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    for name in ("XDG_CURRENT_DESKTOP", "XDG_SESSION_DESKTOP", "DESKTOP_SESSION"):
        monkeypatch.delenv(name, raising=False)
    for name in ("niri-wall.png", "sway-wall.png", "river-wall.png", "wayfire-wall.png", "labwc-wall.png"):
        (home / name).write_bytes(b"\x89PNG\r\n\x1a\n")

    niri = home / ".config" / "niri"
    niri.mkdir(parents=True)
    (niri / "config.kdl").write_text(NIRI)
    (niri / "binds.kdl").write_text(NIRI_BINDS)

    sway = home / ".config" / "sway"
    (sway / "config.d").mkdir(parents=True)
    (sway / "config").write_text(SWAY)
    (sway / "config.d" / "extra").write_text("bindsym $mod+E exec thunar\n")

    river = home / ".config" / "river"
    river.mkdir(parents=True)
    (river / "init").write_text(RIVER)
    (river / "init").chmod(0o755)

    wayfire = home / ".config" / "wayfire"
    wayfire.mkdir(parents=True)
    (home / ".config" / "wayfire.ini").write_text(WAYFIRE)
    (home / ".config" / "wf-shell.ini").write_text("[panel]\nposition = bottom\n")

    labwc = home / ".config" / "labwc"
    labwc.mkdir(parents=True)
    (labwc / "rc.xml").write_text(LABWC)
    (labwc / "autostart").write_text("#!/bin/sh\nswaybg -i ~/labwc-wall.png\n")
    (labwc / "themerc").write_text("cursorTheme=Breeze\n")

    shells = home / ".config"
    (shells / "noctalia").mkdir()
    (shells / "noctalia" / "config.toml").write_text("[shell]\nlang = \"es\"\n")
    (shells / "DankMaterialShell").mkdir()
    (shells / "DankMaterialShell" / "settings.json").write_text('{"bar":{}}\n')
    (shells / "quickshell").mkdir()
    (shells / "quickshell" / "shell.qml").write_text("import Quickshell\nShellRoot {}\n")
    (shells / "ags").mkdir()
    (shells / "ags" / "app.ts").write_text("export const x = 1\n")

    personal = home / "Documents"
    personal.mkdir()
    (personal / "privado.conf").write_text("secreto\n")
    (home / ".ssh").mkdir()
    (home / ".ssh" / "id_ed25519").write_text("secreto\n")
    return home


def collect(adapter, home: Path) -> Collector:
    collector = Collector(BlobStore(home.parent / f"store-{adapter.id}"))
    adapter.collect(collector)
    return collector


def test_niri_binds_includes_y_temas(fake_home):
    collector = collect(NiriAdapter(), fake_home)
    keybinds = {entry["combo"]: entry for entry in collector.meta["keybinds"]}

    assert "Mod+Return" in keybinds
    assert keybinds["Mod+T"]["source"] == "~/.config/niri/binds.kdl"
    assert keybinds["Mod+Shift+E"]["dispatcher"] == "quit"
    assert keybinds["Mod+Shift+E"]["options"]["skip-confirmation"] == "true"
    assert keybinds["Mod+WheelScrollDown"]["options"]["cooldown-ms"] == "150"

    adapter = NiriAdapter()
    assert adapter.themes()["cursor"] == "Breeze"
    assert [path.name for path in adapter.preview_sources()] == ["niri-wall.png"]


def test_sway_binds_barra_y_temas(fake_home):
    collector = collect(SwayAdapter(), fake_home)
    keybinds = {entry["combo"]: entry for entry in collector.meta["keybinds"]}

    assert keybinds["Mod4+Return"]["dispatcher"] == "exec"
    assert keybinds["Mod4+Shift+q"]["flags"] == ["--release"]
    assert keybinds["Mod4+Right"]["mode"] == "resize"
    assert any(entry["combo"] == "Mod4+E" for entry in collector.meta["keybinds"])

    layout = widgets.from_items(collector.items, collector.store)
    assert layout["containers"][0]["name"] == "Barra de Sway"
    assert layout["containers"][0]["size"] == 30

    adapter = SwayAdapter()
    assert adapter.themes()["cursor"] == "Breeze"
    assert [path.name for path in adapter.preview_sources()] == ["sway-wall.png"]


def test_river_init_con_shebang_y_atajos(fake_home):
    collector = collect(RiverAdapter(), fake_home)
    assert "~/.config/river/init" in {item.source for item in collector.items}
    keybinds = {(entry["mode"], entry["combo"]): entry for entry in collector.meta["keybinds"]}

    assert keybinds[("normal", "Mod+Return")]["dispatcher"] == "spawn"
    assert keybinds[("normal", "Mod+Return")]["arg"] == "kitty"
    assert keybinds[("normal", "Mod+Q")]["flags"] == ["-repeat"]
    assert keybinds[("normal", "Mod+BTN_LEFT")]["kind"] == "river-map-pointer"

    adapter = RiverAdapter()
    assert adapter.themes()["cursor"] == "Breeze"
    assert [path.name for path in adapter.preview_sources()] == ["river-wall.png"]


def test_wayfire_bindings_y_wf_shell(fake_home):
    collector = collect(WayfireAdapter(), fake_home)
    keybinds = {entry["combo"]: entry for entry in collector.meta["keybinds"]}

    assert keybinds["<super> KEY_ENTER"]["dispatcher"] == "exec"
    assert keybinds["<super> KEY_ENTER"]["arg"] == "kitty"
    assert "~/.config/wf-shell.ini" in {item.source for item in collector.items}

    adapter = WayfireAdapter()
    assert adapter.themes()["cursor"] == "Breeze"
    assert [path.name for path in adapter.preview_sources()] == ["wayfire-wall.png"]


def test_labwc_xml_y_autostart(fake_home):
    collector = collect(LabwcAdapter(), fake_home)
    keybinds = {entry["combo"]: entry for entry in collector.meta["keybinds"]}

    assert keybinds["Super+Return"]["dispatcher"] == "Execute"
    assert keybinds["Super+Return"]["arg"] == "kitty"
    assert keybinds["Super+q"]["dispatcher"] == "Close"
    assert "~/.config/labwc/autostart" in {item.source for item in collector.items}

    adapter = LabwcAdapter()
    assert adapter.themes()["cursor"] == "Breeze"
    assert [path.name for path in adapter.preview_sources()] == ["labwc-wall.png"]


def test_shells_se_comparten_entre_compositores(fake_home):
    for adapter in (HyprlandAdapter(), NiriAdapter(), SwayAdapter()):
        collector = collect(adapter, fake_home)
        sources = {item.source for item in collector.items}
        assert "~/.config/noctalia/config.toml" in sources
        assert "~/.config/DankMaterialShell/settings.json" in sources
        assert "~/.config/quickshell/shell.qml" in sources
        assert "~/.config/ags/app.ts" in sources


def test_privacidad_no_incluye_archivos_personales(fake_home):
    collector = collect(NiriAdapter(), fake_home)
    sources = {item.source for item in collector.items}
    assert "~/Documents/privado.conf" not in sources
    assert "~/.ssh/id_ed25519" not in sources
    assert not any("Documents" in source for source in sources)


def test_perfil_niri_no_exporta_atajos(fake_home):
    import json

    from themevault.profile import build_profile

    engine = BackupEngine(fake_home / "vault")
    manifest = engine.create(adapters=[NiriAdapter()], preview=False)
    store = engine.store(manifest.id)
    profile, dropped = build_profile(
        manifest, store, name="Mi Niri", author="yo", license="MIT"
    )

    text = json.dumps(profile.to_dict(), ensure_ascii=False)
    assert profile.desktop == "niri"
    assert profile.settings == []
    assert "keybinds" not in text
    assert "Mod+Return" not in text
    assert "config.kdl" not in text
    assert dropped


def test_backup_restore_niri_y_rebuild_de_atajos(fake_home):
    engine = BackupEngine(fake_home / "vault")
    manifest = engine.create(adapters=[NiriAdapter()], preview=False, label="niri")

    assert manifest.de == "niri"
    assert manifest.keybinds
    assert any(item.source == "~/.config/niri/config.kdl" for item in manifest.items)

    main = fake_home / ".config" / "niri" / "config.kdl"
    main.write_text("# modificado\n")

    store = engine.store(manifest.id)
    actions = build_plan(manifest, store, only={"layout"})
    report = apply_plan(actions, store, safety=False)
    assert report.failures == []
    assert "Mod+Return" in main.read_text()

    rebuilt = keybinds_from_items(manifest.items, store)
    assert any(entry["combo"] == "Mod+Return" for entry in rebuilt)
