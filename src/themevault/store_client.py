"""Cliente de la tienda de widgets (KDE Store / OCS).

Usa el mismo proveedor que Plasma (`plasmoids.knsrc` ->
`https://api.kde-look.org/ocs/v1/`) y solo habla por red cuando el usuario
busca o instala algo.
"""

from __future__ import annotations

import json
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from . import widgets_install

API = "https://api.kde-look.org/ocs/v1"
USER_AGENT = "ThemeVault (+https://github.com/TuxArchi/themevault)"
TIMEOUT = 20
MAX_BYTES = 60 * 1024 * 1024
APPLET_TYPES = ("Plasma 6 Applets", "Plasma 6 Extensions", "Plasma Applets")


class StoreError(RuntimeError):
    pass


def _get_json(url: str, timeout: int = TIMEOUT) -> dict:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read(MAX_BYTES)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise StoreError(f"no se pudo conectar con la tienda: {exc}") from exc
    try:
        return json.loads(payload.decode("utf-8", "replace"))
    except ValueError as exc:
        raise StoreError("la tienda devolvio una respuesta inesperada") from exc


def _plain(text: str) -> str:
    """Saca el HTML que viene en las descripciones."""
    out = []
    inside = False
    for char in text:
        if char == "<":
            inside = True
        elif char == ">":
            inside = False
        elif not inside:
            out.append(char)
    return " ".join("".join(out).split())[:200]


def search(query: str, limit: int = 24) -> list[dict]:
    query = (query or "").strip()
    if not query:
        return []
    params = urllib.parse.urlencode(
        {"search": query, "pagesize": limit, "format": "json", "sort": "new"}
    )
    data = _get_json(f"{API}/content/data?{params}")

    found: list[dict] = []
    for raw in data.get("data", []):
        typename = str(raw.get("typename", ""))
        if not any(kind in typename for kind in APPLET_TYPES):
            continue
        found.append(
            {
                "id": raw.get("id"),
                "name": raw.get("name", ""),
                "author": raw.get("personid", ""),
                "downloads": raw.get("downloads", ""),
                "summary": _plain(str(raw.get("summary", ""))),
                "preview": raw.get("smallpreviewpic1") or raw.get("previewpic1") or "",
            }
        )
    return found


def details(item_id: int) -> dict:
    data = _get_json(f"{API}/content/data/{int(item_id)}?format=json")
    entries = data.get("data") or []
    if not entries:
        raise StoreError("el widget ya no esta disponible")
    raw = entries[0]
    url = raw.get("downloadlink1") or raw.get("downloadlink2") or ""
    if not url:
        raise StoreError("el widget no tiene un enlace de descarga")
    return {
        "id": raw.get("id"),
        "name": raw.get("name", ""),
        "url": url,
        "version": raw.get("version", ""),
    }


def download(url: str, destination: Path) -> Path:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=60) as response, open(destination, "wb") as fh:
            total = 0
            while True:
                chunk = response.read(256 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_BYTES:
                    raise StoreError("el paquete supera el tamano maximo permitido")
                fh.write(chunk)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise StoreError(f"fallo la descarga: {exc}") from exc
    return destination


def install(item_id: int) -> dict:
    info = details(item_id)
    with tempfile.TemporaryDirectory(prefix="themevault-store-") as tmp:
        archive = Path(tmp) / "widget.pkg"
        download(info["url"], archive)
        ok, message = widgets_install.install_archive(archive)
    if not ok:
        raise StoreError(message or "no se pudo instalar el widget")
    return {"id": info["id"], "name": info["name"], "version": info.get("version", "")}
