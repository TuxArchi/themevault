"""Comunidad: índice de perfiles y descarga.

El índice es un único JSON del repositorio `themevault-profiles`; se cachea
24 h. Cada `profile.json` se verifica contra el sha256 publicado antes de
usarse.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

from .net import ssl_context
from .profile import Profile, validate

REPO = "https://raw.githubusercontent.com/TuxArchi/themevault-profiles/main"
INDEX_URL = f"{REPO}/index.json"
RAW = f"{REPO}/profiles"

USER_AGENT = "ThemeVault (+https://github.com/TuxArchi/themevault)"
TIMEOUT = 20
MAX_BYTES = 2 * 1024 * 1024
CACHE_TTL = 24 * 3600


class CommunityError(RuntimeError):
    pass


def cache_file() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    folder = Path(base) / "themevault"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "community.json"


def cover_url(entry: dict) -> str:
    cover = entry.get("cover") or ""
    if not cover:
        return ""
    return f"{RAW}/{entry['id']}/{cover}"


def _fetch(url: str, limit: int = MAX_BYTES) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT, context=ssl_context()) as response:
            data = response.read(limit + 1)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise CommunityError(f"no se pudo conectar: {exc}") from exc
    if len(data) > limit:
        raise CommunityError("la respuesta es demasiado grande")
    return data


def _read_cache() -> dict | None:
    path = cache_file()
    if not path.is_file():
        return None
    try:
        if time.time() - path.stat().st_mtime > CACHE_TTL:
            return None
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _write_cache(payload: dict) -> None:
    try:
        cache_file().write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def fetch_index(force: bool = False) -> list[dict]:
    if not force:
        cached = _read_cache()
        if cached is not None:
            return list(cached.get("profiles") or [])

    raw = _fetch(INDEX_URL)
    try:
        payload = json.loads(raw.decode("utf-8", "replace"))
    except ValueError as exc:
        raise CommunityError("el indice de la comunidad no es JSON valido") from exc

    if payload.get("schema") != 1:
        raise CommunityError("version de indice no soportada")
    profiles = payload.get("profiles") or []
    if not isinstance(profiles, list):
        raise CommunityError("indice con formato inesperado")

    _write_cache(payload)
    return profiles


def fetch_profile(entry: dict) -> Profile:
    """Descarga y verifica un perfil del indice."""
    profile_id = str(entry.get("id", ""))
    if not profile_id:
        raise CommunityError("perfil sin id")

    raw = _fetch(f"{RAW}/{profile_id}/profile.json")
    expected = str(entry.get("sha256", ""))
    if expected and hashlib.sha256(raw).hexdigest() != expected:
        raise CommunityError("el perfil no coincide con el indice (hash distinto)")

    try:
        data = json.loads(raw.decode("utf-8", "replace"))
    except ValueError as exc:
        raise CommunityError("el perfil no es JSON valido") from exc

    profile = Profile.from_dict(data)
    if profile.id != profile_id:
        raise CommunityError("el id del perfil no coincide con el indice")
    problems = validate(profile)
    if problems:
        raise CommunityError("perfil invalido: " + "; ".join(problems))
    return profile


def filter_profiles(entries: list[dict], query: str = "", desktop: str = "") -> list[dict]:
    text = (query or "").strip().lower()
    out: list[dict] = []
    for entry in entries:
        if desktop and entry.get("desktop") != desktop:
            continue
        if text:
            haystack = " ".join(
                str(entry.get(key, "")) for key in ("name", "author", "description", "id")
            ).lower()
            if text not in haystack:
                continue
        out.append(entry)
    return out
