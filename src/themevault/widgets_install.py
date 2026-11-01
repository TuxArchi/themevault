"""Instalacion de widgets de Plasma (KPackage).

Dos origenes:

  * el respaldo: el paquete del widget viaja como arbol dentro de la copia;
  * la tienda: se descarga el paquete y se instala con la misma herramienta.

En ambos casos se usa `kpackagetool6 --type Plasma/Applet`, el servicio oficial
de KPackage; nada se escribe a mano.
"""

from __future__ import annotations

import tarfile
import tempfile
import zipfile
from pathlib import Path

from .model import Manifest
from .store import BlobStore
from .util import run, which
from .widgets import is_widget_installed

PLASMOIDS = "~/.local/share/plasma/plasmoids"


def packagetool() -> str | None:
    return which("kpackagetool6", "kpackagetool5")


def backup_packages(manifest: Manifest) -> dict[str, object]:
    """{id del widget: item del respaldo} para los widgets de usuario."""
    found: dict[str, object] = {}
    for item in manifest.items:
        source = (item.source or "").rstrip("/")
        if "/plasma/plasmoids/" not in source:
            continue
        found[source.split("/")[-1]] = item
    return found


def missing_from_backup(manifest: Manifest) -> list[dict]:
    """Widgets que el sistema no tiene, marcando si la copia trae el paquete."""
    packages = backup_packages(manifest)
    out: list[dict] = []
    for widget in manifest.widgets:
        plugin = widget.get("id", "")
        if not plugin or is_widget_installed(plugin):
            continue
        out.append(
            {
                "id": plugin,
                "name": widget.get("name", plugin),
                "inBackup": plugin in packages,
            }
        )
    return out


def _install_path(tool: str, path: Path) -> tuple[bool, str]:
    proc = run([tool, "--type", "Plasma/Applet", "--install", str(path)], timeout=180)
    if proc is not None and proc.returncode == 0:
        return True, ""
    # ya existe: actualizar
    proc = run([tool, "--type", "Plasma/Applet", "--upgrade", str(path)], timeout=180)
    if proc is not None and proc.returncode == 0:
        return True, ""
    detail = ""
    if proc is not None:
        detail = (proc.stderr or proc.stdout).decode("utf-8", "replace").strip()
    return False, detail or "kpackagetool fallo"


def install_from_backup(
    manifest: Manifest,
    store: BlobStore,
    ids: list[str] | None = None,
) -> dict:
    tool = packagetool()
    if tool is None:
        raise RuntimeError("kpackagetool6 no esta instalado en este sistema")

    packages = backup_packages(manifest)
    targets = [i for i in (ids or list(packages)) if i in packages]
    if not targets:
        raise RuntimeError("la copia no incluye paquetes de widgets para instalar")

    installed: list[dict] = []
    failed: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="themevault-widget-") as tmp:
        base = Path(tmp)
        for plugin in targets:
            item = packages[plugin]
            store.extract_tree(item.blob, base)
            candidate = base / plugin
            if not candidate.is_dir():
                candidate = base  # arbol con otra forma
            ok, message = _install_path(tool, candidate)
            entry = {"id": plugin, "name": plugin, "message": message}
            (installed if ok else failed).append(entry)
    return {"installed": installed, "failed": failed}


def _extract(archive: Path, destination: Path) -> bool:
    """Descomprime zip/tar. KPackage solo acepta carpetas o formatos conocidos."""
    try:
        with open(archive, "rb") as handle:
            magic = handle.read(4)
        if magic[:2] == b"PK":
            with zipfile.ZipFile(archive) as bundle:
                bundle.extractall(destination)
            return True
        if magic[:2] == b"\x1f\x8b" or magic[:3] == b"BZh":
            with tarfile.open(archive) as bundle:
                if hasattr(tarfile, "data_filter"):
                    bundle.extractall(destination, filter="data")
                else:
                    bundle.extractall(destination)
            return True
    except (zipfile.BadZipFile, tarfile.TarError, OSError):
        return False
    return False


def _package_root(folder: Path) -> Path | None:
    if (folder / "metadata.json").is_file():
        return folder
    children = [p for p in folder.iterdir() if p.is_dir()]
    if len(children) == 1 and (children[0] / "metadata.json").is_file():
        return children[0]
    for child in children:
        if (child / "metadata.json").is_file():
            return child
    return None


def install_archive(path: str | Path) -> tuple[bool, str]:
    """Instala un paquete descargado (zip/tar) con KPackage."""
    tool = packagetool()
    if tool is None:
        return False, "kpackagetool6 no esta instalado"

    with tempfile.TemporaryDirectory(prefix="themevault-pkg-") as tmp:
        root = Path(tmp)
        if not _extract(Path(path), root):
            return False, "el archivo descargado no es un paquete valido"
        candidate = _package_root(root)
        if candidate is None:
            return False, "el paquete no tiene metadata.json"
        return _install_path(tool, candidate)
