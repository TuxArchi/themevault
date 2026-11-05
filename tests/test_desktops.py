"""Escritorios clásicos y COSMIC."""

from __future__ import annotations

from pathlib import Path

import pytest

from themevault.adapters.base import Collector
from themevault.adapters.budgie import BudgieAdapter
from themevault.adapters.cinnamon import CinnamonAdapter
from themevault.adapters.cosmic import CosmicAdapter
from themevault.adapters.i3 import I3Adapter
from themevault.adapters.lxqt import LxqtAdapter
from themevault.adapters.mate import MateAdapter
from themevault.adapters.openbox import OpenboxAdapter
from themevault.store import BlobStore

CINNAMON_DCONF = """\
[/]
custom-list=['custom0']
show-desklets=['<Super><Shift>s']

[custom-keybindings/custom0]
binding=['<Super>q']
command='kitty'
name='Terminal'

[wm]
close=['<Alt>F4']
maximize=['<Super>Up']
"""

MATE_DCONF = """\
[/]
run-command-1=['<Super>Return']

[custom0]
binding='<Control><Alt>t'
action='mate-terminal'
name='Terminal'
"""

BUDGIE_WM = """\
[/]
close=['<Alt>F4']
"""

BUDGIE_MEDIA = """\
[/]
custom-keybindings=['/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom0/']

[custom-keybindings/custom0/]
binding='<Super>q'
command='kitty'
name='Terminal'
"""

LXQT_KEYS = """\
[Control%2BAlt%2BT.1]
Comment=Terminal
Enabled=true
Exec=qterminal

[Print.2]
Comment=Captura
Enabled=false
Exec=screengrab, -f
"""

LXQT_MAIN = """\
[General]
icon_theme=Papirus-Dark
theme=kvantum
"""

I3_CONFIG = """\
set $mod Mod4
set $term kitty
include ~/.config/i3/config.d/*
bindsym $mod+Return exec $term
bindsym $mod+Shift+q kill
mode "resize" {
    bindsym $mod+Right resize grow width 10 px
}
exec --no-startup-id feh --bg-fill ~/i3-wall.png
"""

OPENBOX_XML = """\
<openbox_config>
  <keyboard>
    <keybind key="W-Return">
      <action name="Execute"><command>kitty</command></action>
    </keybind>
    <keybind key="W-q"><action name="Close"/></keybind>
  </keyboard>
  <theme><cursorTheme>Breeze</cursorTheme></theme>
</openbox_config>
"""

COSMIC_SHORTCUTS = """\
{
    (
        modifiers: [Super, Shift],
        key: "Q",
        description: Some("cerrar"),
    ): Spawn("cosmic-term"),
    (
        modifiers: [Super],
        key: "Return",
    ): System(Terminal),
}
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
    for name in ("i3-wall.png", "openbox-wall.png", "cosmic-wall.png", "lxqt-wall.png"):
        (home / name).write_bytes(b"\x89PNG\r\n\x1a\n")

    lxqt = home / ".config" / "lxqt"
    lxqt.mkdir(parents=True)
    (lxqt / "lxqt.conf").write_text(LXQT_MAIN)
    (lxqt / "globalkeyshortcuts.conf").write_text(LXQT_KEYS)
    pcman = home / ".config" / "pcmanfm-qt" / "lxqt"
    pcman.mkdir(parents=True)
    (pcman / "settings.conf").write_text("[Wallpaper]\nwallpaper=~/lxqt-wall.png\n")

    i3 = home / ".config" / "i3"
    (i3 / "config.d").mkdir(parents=True)
    (i3 / "config").write_text(I3_CONFIG)
    (i3 / "config.d" / "extra").write_text("bindsym $mod+E exec thunar\n")

    openbox = home / ".config" / "openbox"
    openbox.mkdir(parents=True)
    (openbox / "rc.xml").write_text(OPENBOX_XML)
    (openbox / "autostart").write_text("#!/bin/sh\nfeh --bg-fill ~/openbox-wall.png\n")

    cosmic = home / ".config" / "cosmic"
    shortcuts = cosmic / "com.system76.CosmicSettings.Shortcuts" / "v1"
    shortcuts.mkdir(parents=True)
    (shortcuts / "custom").write_text(COSMIC_SHORTCUTS)
    background = cosmic / "com.system76.CosmicBackground" / "v1"
    background.mkdir(parents=True)
    (background / "all").write_text('(path: "~/cosmic-wall.png")\n')

    return home


def collect(adapter, home: Path) -> Collector:
    collector = Collector(BlobStore(home.parent / f"store-{adapter.id}"))
    adapter.collect(collector)
    return collector


def patch_dconf(monkeypatch, module, dumps: dict[str, str | None]):
    import sys

    target = sys.modules[module.__module__]
    monkeypatch.setattr(target, "dconf_available", lambda: True)

    def fake_dump(path):
        value = dumps.get(path)
        return value.encode() if value else None

    monkeypatch.setattr("themevault.drivers.dconf_dump", fake_dump)


def test_cinnamon_keybinds_y_dconf(fake_home, monkeypatch):
    patch_dconf(
        monkeypatch,
        CinnamonAdapter,
        {
            "/org/cinnamon/desktop/background/": None,
            "/org/cinnamon/desktop/interface/": None,
            "/org/cinnamon/desktop/wm/preferences/": None,
            "/org/cinnamon/theme/": None,
            "/org/cinnamon/desktop/keybindings/": CINNAMON_DCONF,
        },
    )
    collector = collect(CinnamonAdapter(), fake_home)
    keybinds = {entry["combo"]: entry for entry in collector.meta["keybinds"]}
    assert keybinds["<Super>q"]["dispatcher"] == "command"
    assert keybinds["<Super>q"]["arg"] == "kitty"
    assert keybinds["<Alt>F4"]["dispatcher"] == "close"
    assert keybinds["<Super><Shift>s"]["dispatcher"] == "show-desklets"


def test_mate_keybinds_y_marco(fake_home, monkeypatch):
    patch_dconf(
        monkeypatch,
        MateAdapter,
        {
            "/org/mate/desktop/interface/": None,
            "/org/mate/desktop/background/": None,
            "/org/mate/desktop/keybindings/": MATE_DCONF,
            "/org/mate/marco/window-keybindings/": "[/]\nclose=['<Alt>F4']\n",
            "/org/mate/marco/global-keybindings/": "[/]\nrun-command-1=['<Super>Return']\n",
        },
    )
    collector = collect(MateAdapter(), fake_home)
    keybinds = {entry["combo"]: entry for entry in collector.meta["keybinds"]}
    assert keybinds["<Control><Alt>t"]["arg"] == "mate-terminal"
    assert keybinds["<Super>Return"]["dispatcher"] == "run-command-1"


def test_budgie_keybinds_media_keys(fake_home, monkeypatch):
    patch_dconf(
        monkeypatch,
        BudgieAdapter,
        {
            "/org/gnome/desktop/interface/": None,
            "/org/gnome/desktop/background/": None,
            "/com/solus-project/budgie-panel/": None,
            "/org/budgie-desktop/": None,
            "/org/gnome/desktop/wm/keybindings/": BUDGIE_WM,
            "/org/gnome/settings-daemon/plugins/media-keys/": BUDGIE_MEDIA,
        },
    )
    collector = collect(BudgieAdapter(), fake_home)
    keybinds = {entry["combo"]: entry for entry in collector.meta["keybinds"]}
    assert keybinds["<Super>q"]["arg"] == "kitty"
    assert keybinds["<Alt>F4"]["dispatcher"] == "close"


def test_lxqt_shortcuts_tema_y_fondo(fake_home):
    adapter = LxqtAdapter()
    collector = collect(adapter, fake_home)
    keybinds = {(entry["combo"], entry["dispatcher"]): entry for entry in collector.meta["keybinds"]}
    assert keybinds[("Control+Alt+T", "exec")]["arg"] == "qterminal"
    assert keybinds[("Print", "exec")]["options"]["enabled"] is False
    assert adapter.themes()["icons"] == "Papirus-Dark"
    assert [path.name for path in adapter.preview_sources()] == ["lxqt-wall.png"]


def test_i3_keybinds_includes_y_fondo(fake_home):
    adapter = I3Adapter()
    collector = collect(adapter, fake_home)
    keybinds = {entry["combo"]: entry for entry in collector.meta["keybinds"]}
    assert keybinds["Mod4+Return"]["dispatcher"] == "exec"
    assert keybinds["Mod4+E"]["dispatcher"] == "exec"
    assert keybinds["Mod4+Right"]["mode"] == "resize"
    assert [path.name for path in adapter.preview_sources()] == ["i3-wall.png"]


def test_openbox_keybinds_y_autostart(fake_home):
    adapter = OpenboxAdapter()
    collector = collect(adapter, fake_home)
    keybinds = {entry["combo"]: entry for entry in collector.meta["keybinds"]}
    assert keybinds["Super+Return"]["dispatcher"] == "Execute"
    assert keybinds["Super+Return"]["arg"] == "kitty"
    assert keybinds["Super+q"]["dispatcher"] == "Close"
    assert [path.name for path in adapter.preview_sources()] == ["openbox-wall.png"]


def test_rebuild_de_atajos_dconf(fake_home, monkeypatch):
    from themevault.keybinds import keybinds_from_items

    patch_dconf(
        monkeypatch,
        CinnamonAdapter,
        {
            "/org/cinnamon/desktop/background/": None,
            "/org/cinnamon/desktop/interface/": None,
            "/org/cinnamon/desktop/wm/preferences/": None,
            "/org/cinnamon/theme/": None,
            "/org/cinnamon/desktop/keybindings/": CINNAMON_DCONF,
        },
    )
    collector = collect(CinnamonAdapter(), fake_home)
    rebuilt = keybinds_from_items(collector.items, collector.store)
    assert any(entry["combo"] == "<Super>q" for entry in rebuilt)


def test_rebuild_de_atajos_lxqt_y_cosmic(fake_home):
    from themevault.keybinds import keybinds_from_items

    lxqt = collect(LxqtAdapter(), fake_home)
    assert any(entry["combo"] == "Control+Alt+T" for entry in keybinds_from_items(lxqt.items, lxqt.store))

    cosmic = collect(CosmicAdapter(), fake_home)
    assert any(entry["combo"] == "Super+Shift+Q" for entry in keybinds_from_items(cosmic.items, cosmic.store))


def test_cosmic_shortcuts_y_fondo(fake_home):
    adapter = CosmicAdapter()
    collector = collect(adapter, fake_home)
    keybinds = {entry["combo"]: entry for entry in collector.meta["keybinds"]}
    assert keybinds["Super+Shift+Q"]["dispatcher"] == "Spawn"
    assert keybinds["Super+Shift+Q"]["arg"] == "cosmic-term"
    assert keybinds["Super+Shift+Q"]["description"] == "cerrar"
    assert keybinds["Super+Return"]["dispatcher"] == "System"
    assert [path.name for path in adapter.preview_sources()] == ["cosmic-wall.png"]
