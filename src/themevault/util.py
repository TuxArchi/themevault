"""Utilidades comunes: rutas XDG, hashing, ejecucion de comandos."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from pathlib import Path

APP_NAME = "themevault"


def home() -> Path:
    return Path(os.path.expanduser("~"))


def expand(path: str | Path) -> Path:
    """Expande ~ y variables de entorno en una ruta."""
    p = str(path)
    if p.startswith("~"):
        p = str(home()) + p[1:]
    return Path(os.path.expandvars(p))


def xdg_data_home() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME") or home() / ".local" / "share")


def xdg_config_home() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME") or home() / ".config")


def default_root() -> Path:
    """Directorio donde viven las copias de seguridad."""
    return Path(os.environ.get("THEMEVAULT_ROOT") or xdg_data_home() / APP_NAME)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def which(*names: str) -> str | None:
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    return None


def run(
    cmd: list[str],
    *,
    input_bytes: bytes | None = None,
    timeout: int = 30,
    check: bool = False,
) -> subprocess.CompletedProcess | None:
    """Ejecuta un comando. Devuelve None si no existe, falla o expira."""
    try:
        proc = subprocess.run(cmd, input=input_bytes, capture_output=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if check and proc.returncode != 0:
        err = proc.stderr.decode("utf-8", "replace").strip()
        raise RuntimeError(f"{cmd[0]} fallo: {err or proc.returncode}")
    return proc


def human_size(num: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num < 1024 or unit == "TB":
            return f"{num:.0f} {unit}" if unit == "B" else f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} TB"


def to_portable(path: str | Path) -> str:
    """Convierte una ruta absoluta en ~/... para que la copia sea portable."""
    p = str(path)
    root = str(home())
    if p == root:
        return "~"
    if p.startswith(root + "/"):
        return "~" + p[len(root):]
    return p


def from_portable(path: str) -> Path:
    return expand(path)


def is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False
