"""Auditoría y exportación saneada de copias."""

from __future__ import annotations

import json
from pathlib import Path

from themevault.audit import audit_backup
from themevault.model import Item, Manifest
from themevault.sanitize import sanitized_copy
from themevault.store import BlobStore


def _manifest(tmp_path: Path) -> tuple[BlobStore, Manifest]:
    store = BlobStore(tmp_path / "copia")
    (store.root / "preview").mkdir(parents=True)
    (store.root / "preview" / "wallpaper.jpg").write_bytes(b"\xff\xd8\xff")

    dconf = """[/]
command-history=['ssh root@10.0.0.5']
picture-uri='file:///home/ana/foto.jpg'
"""
    blob, sha, size = store.put_bytes(dconf.encode())
    dconf_item = Item(
        kind="dconf",
        category="config",
        name="Shell",
        backend="dconf",
        data={"path": "/org/gnome/shell/"},
        blob=blob,
        sha256=sha,
        size=size,
    )
    shell_blob, shell_sha, shell_size = store.put_bytes(b'weather = "Casa"\n')
    shell_item = Item(
        kind="file",
        category="shell",
        name="config.toml",
        source="~/.config/noctalia/config.toml",
        blob=shell_blob,
        sha256=shell_sha,
        size=shell_size,
    )
    manifest = Manifest(
        id="copia",
        created="2026-01-01T00:00:00",
        host={
            "de": "gnome",
            "skipped": [{"path": "~/Documents/privado.kdl", "reason": "ruta personal"}],
        },
        items=[dconf_item, shell_item],
        preview={"wallpaper": "preview/wallpaper.jpg", "palette": ["#111111"]},
        keybinds=[
            {"combo": "Super+Q", "dispatcher": "killactive", "arg": ""},
            {"combo": "Super+X", "dispatcher": "exec", "arg": "~/privado.sh", "script": "~/privado.sh"},
        ],
    )
    return store, manifest


def test_auditoria_detecta_datos_personales(tmp_path):
    store, manifest = _manifest(tmp_path)
    report = audit_backup(manifest, store)

    assert report["risk"] == "high"
    assert not report["safe_to_share"]
    categories = {finding["category"] for finding in report["findings"]}
    assert {"preview", "paths", "history", "shells", "skipped", "keybinds"} <= categories


def test_copia_saneada_elimina_lo_personal(tmp_path):
    store, manifest = _manifest(tmp_path)
    destination = tmp_path / "saneada"
    new, report = sanitized_copy(manifest, store, destination, include_wallpaper=False)

    assert not any(item.source.startswith("~/.config/noctalia") for item in new.items)
    assert new.host.get("sanitized") is True
    assert new.host.get("skipped") == []
    assert new.preview.get("wallpaper") is None
    assert [entry["combo"] for entry in new.keybinds] == ["Super+Q"]
    assert report["removed"]

    # La copia original no cambia.
    original = store.read(manifest.items[0].blob).decode()
    assert "command-history" in original
    saved = json.loads((destination / "manifest.json").read_text())
    assert saved["host"]["sanitized"] is True
