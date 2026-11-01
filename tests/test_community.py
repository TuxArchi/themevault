"""Tests del cliente de la comunidad (sin red real)."""

from __future__ import annotations

import hashlib
import json

import pytest

from themevault import community

PROFILE = {
    "schema": 1,
    "id": "demo-kde",
    "name": "Demo",
    "author": "yo",
    "license": "MIT",
    "desktop": "kde",
    "description": "",
    "created": "2026-11-01",
    "preview": {"cover": "", "palette": ["#101010"]},
    "requires": {"icons": "Papirus-Dark"},
    "settings": [],
}


def _payload(profile: dict) -> bytes:
    return json.dumps(profile).encode()


def test_indice_y_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    calls: list[str] = []

    def fake_fetch(url, limit=0):
        calls.append(url)
        return json.dumps({"schema": 1, "profiles": [{"id": "demo-kde"}]}).encode()

    monkeypatch.setattr(community, "_fetch", fake_fetch)

    assert community.fetch_index() == [{"id": "demo-kde"}]
    assert community.fetch_index() == [{"id": "demo-kde"}]
    assert len(calls) == 1, "la segunda lectura deberia salir del cache"

    community.fetch_index(force=True)
    assert len(calls) == 2


def test_perfil_verifica_sha256(monkeypatch):
    raw = _payload(PROFILE)
    entry = {"id": "demo-kde", "sha256": hashlib.sha256(raw).hexdigest()}
    monkeypatch.setattr(community, "_fetch", lambda url, limit=0: raw)

    perfil = community.fetch_profile(entry)
    assert perfil.id == "demo-kde"
    assert perfil.requires["icons"] == "Papirus-Dark"

    entry["sha256"] = "0" * 64
    with pytest.raises(community.CommunityError):
        community.fetch_profile(entry)


def test_perfil_invalido_se_rechaza(monkeypatch):
    malo = dict(PROFILE, settings=[
        {"backend": "ini", "file": "kdeglobals", "group": "G", "key": "k", "value": "/home/x/privado"}
    ])
    raw = _payload(malo)
    entry = {"id": "demo-kde", "sha256": hashlib.sha256(raw).hexdigest()}
    monkeypatch.setattr(community, "_fetch", lambda url, limit=0: raw)

    with pytest.raises(community.CommunityError):
        community.fetch_profile(entry)


def test_filtros_por_escritorio_y_texto():
    entries = [
        {"id": "a", "name": "Catppuccin", "author": "ana", "desktop": "kde", "description": ""},
        {"id": "b", "name": "Nord", "author": "luis", "desktop": "kde", "description": ""},
        {"id": "c", "name": "Adwaita", "author": "ana", "desktop": "gnome", "description": ""},
    ]
    assert [e["id"] for e in community.filter_profiles(entries, desktop="kde")] == ["a", "b"]
    assert [e["id"] for e in community.filter_profiles(entries, "ana")] == ["a", "c"]
    assert [e["id"] for e in community.filter_profiles(entries, "nord")] == ["b"]
    assert len(community.filter_profiles(entries)) == 3


def test_cover_url():
    assert community.cover_url({"id": "x", "cover": "cover.png"}).endswith("/profiles/x/cover.png")
    assert community.cover_url({"id": "x", "cover": ""}) == ""
