"""Filtros de privacidad para archivos de configuración.

Hyprland y su ecosistema viven en archivos de texto dentro de ``~/.config``.
Este módulo define una lista blanca estricta: solo se respaldan archivos de
configuración conocidos. Nunca fotos, wallpapers, documentos, notas, scripts,
claves privadas ni historiales.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

from .util import expand, home, is_within

MAX_CONFIG_BYTES = 512 * 1024

# Extensiones que pueden contener configuración de escritorio.
CONFIG_SUFFIXES = {
    ".conf",
    ".ini",
    ".json",
    ".jsonc",
    ".toml",
    ".yaml",
    ".yml",
    ".css",
    ".rasi",
    ".kvconfig",
    ".colors",
    ".theme",
    ".xml",
    ".kdl",
}

# Nombres sin extensión que también son configuración.
CONFIG_NAMES = {
    "config",
    "config.jsonc",
    "style.css",
    "dunstrc",
    "hyprland.conf",
    "hyprpaper.conf",
    "hyprlock.conf",
    "hypridle.conf",
    "hyprsunset.conf",
    "config.kdl",
    "kitty.conf",
    "alacritty.toml",
    "foot.ini",
    "qt5ct.conf",
    "qt6ct.conf",
    "kvantum.kvconfig",
}

MEDIA_SUFFIXES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".bmp",
    ".svg",
    ".ico",
    ".tif",
    ".tiff",
    ".avif",
    ".heic",
    ".mp4",
    ".mkv",
    ".webm",
    ".mov",
    ".avi",
    ".mp3",
    ".flac",
    ".ogg",
    ".wav",
    ".m4a",
    ".pdf",
    ".psd",
    ".zip",
    ".tar",
    ".gz",
    ".bz2",
    ".xz",
    ".7z",
    ".rar",
    ".db",
    ".sqlite",
    ".sqlite3",
}

SENSITIVE_NAMES = {
    ".env",
    ".netrc",
    ".git-credentials",
    ".npmrc",
    ".pypirc",
    "authorized_keys",
    "known_hosts",
    "id_rsa",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    "credentials",
    "passwd",
    "shadow",
}

SENSITIVE_SUFFIXES = {
    ".pem",
    ".key",
    ".crt",
    ".csr",
    ".p12",
    ".pfx",
    ".gpg",
    ".kdbx",
    ".ovpn",
}

# Nombres de carpetas personales. Se comparan contra cada parte de la ruta
# relativa al home, sin distinguir mayúsculas/minúsculas.
PERSONAL_DIRS = {
    "documents",
    "documentos",
    "downloads",
    "descargas",
    "pictures",
    "imagenes",
    "imágenes",
    "photos",
    "fotos",
    "videos",
    "vídeos",
    "music",
    "musica",
    "música",
    "desktop",
    "escritorio",
    "public",
    "público",
    "templates",
    "plantillas",
    ".ssh",
    ".gnupg",
    ".password-store",
    "keyrings",
    ".mozilla",
    ".thunderbird",
    ".config/google-chrome",
    ".config/chromium",
    ".config/brave-browser",
}

# Carpetas que no aportan configuración y pueden contener archivos enormes.
SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".cache",
    "__pycache__",
    "node_modules",
    "target",
    "dist",
    "build",
    ".venv",
    "venv",
    "scripts",
    "script",
    "wallpapers",
    "wallpaper",
    "backgrounds",
    "assets",
    "images",
    "img",
    "icons",
    "screenshots",
    "capturas",
    "backups",
    "backup",
}

_PRIVATE_KEY_MARKERS = (
    b"-----BEGIN PRIVATE KEY-----",
    b"-----BEGIN RSA PRIVATE KEY-----",
    b"-----BEGIN OPENSSH PRIVATE KEY-----",
    b"-----BEGIN EC PRIVATE KEY-----",
    b"-----BEGIN DSA PRIVATE KEY-----",
    b"-----BEGIN PGP PRIVATE KEY BLOCK-----",
)


def _relative_parts(path: Path) -> tuple[str, ...]:
    try:
        relative = path.resolve().relative_to(home().resolve())
    except (OSError, ValueError):
        return ()
    return tuple(part.lower() for part in relative.parts)


def is_personal_path(path: Path) -> bool:
    """True si la ruta está dentro de una carpeta personal conocida."""
    parts = _relative_parts(Path(path))
    if not parts:
        return False
    joined = "/".join(parts)
    for name in PERSONAL_DIRS:
        if "/" in name:
            if joined == name or joined.startswith(name + "/"):
                return True
        elif name in parts:
            return True
    return False


def _name_allowed(
    name: str,
    allowed_names: set[str],
    allowed_suffixes: set[str],
    allow_any_name: bool = False,
    allow_no_extension: bool = False,
) -> bool:
    lower = name.lower()
    suffix = Path(lower).suffix
    if allow_any_name:
        return True
    if allow_no_extension and not suffix:
        return True
    if not allowed_names and not allowed_suffixes:
        return lower in CONFIG_NAMES or suffix in CONFIG_SUFFIXES
    return lower in allowed_names or suffix in allowed_suffixes


def read_config_text(
    path: Path | str,
    *,
    allowed_names: set[str] | frozenset[str] = frozenset(),
    allowed_suffixes: set[str] | frozenset[str] = frozenset(),
    allow_any_name: bool = False,
    allow_no_extension: bool = False,
    allow_shebang: bool = False,
) -> tuple[str | None, str]:
    """Devuelve (texto, "") si el archivo es configuración segura.

    Si no lo es, devuelve (None, motivo) para que el adaptador lo informe en
    ``host.skipped`` sin copiarlo.
    """
    candidate = Path(path)
    if not candidate.is_file():
        return None, "no es un archivo regular"

    name = candidate.name.lower()
    suffix = candidate.suffix.lower()
    if name in SENSITIVE_NAMES or suffix in SENSITIVE_SUFFIXES:
        return None, "posible archivo sensible (credenciales o clave)"
    if suffix in MEDIA_SUFFIXES:
        return None, "archivo multimedia (no se respalda)"
    if is_personal_path(candidate):
        return None, "ruta personal (no se respalda)"
    if not _name_allowed(
        name,
        set(allowed_names),
        set(allowed_suffixes),
        allow_any_name=allow_any_name,
        allow_no_extension=allow_no_extension,
    ):
        return None, "extensión o nombre no permitido"

    try:
        size = candidate.stat().st_size
    except OSError as exc:
        return None, f"no se pudo leer: {exc}"
    if size > MAX_CONFIG_BYTES:
        return None, f"demasiado grande para configuración ({size // 1024} KB)"

    try:
        data = candidate.read_bytes()
    except OSError as exc:
        return None, f"no se pudo leer: {exc}"
    if b"\x00" in data:
        return None, "archivo binario"
    for marker in _PRIVATE_KEY_MARKERS:
        if marker in data:
            return None, "posible clave privada"

    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None, "no es texto UTF-8"
    if text.startswith("#!") and not allow_shebang:
        return None, "parece un script (no se respalda)"

    return text, ""


def iter_config_files(
    root: Path | str,
    *,
    allowed_names: set[str] | frozenset[str] = frozenset(),
    allowed_suffixes: set[str] | frozenset[str] = frozenset(),
    allow_any_name: bool = False,
    allow_no_extension: bool = False,
    allow_shebang: bool = False,
    skip_dirs: tuple[str, ...] = (),
) -> Iterator[tuple[Path, str]]:
    """Recorre ``root`` y devuelve ``(ruta, motivo)``.

    ``motivo`` vacío significa que el archivo se puede respaldar. Los
    directorios personales, scripts y archivos multimedia se informan una sola
    vez para no llenar el manifest de ruido.
    """
    base = expand(root)
    if not base.exists():
        return

    visited: set[Path] = set()

    def walk(directory: Path) -> Iterator[tuple[Path, str]]:
        try:
            resolved_dir = directory.resolve()
        except OSError:
            yield directory, "no se pudo resolver la ruta"
            return
        if resolved_dir in visited:
            return
        if not is_within(resolved_dir, home()):
            yield directory, "directorio fuera del home"
            return
        visited.add(resolved_dir)

        try:
            entries = sorted(directory.iterdir(), key=lambda item: item.name)
        except OSError as exc:
            yield directory, f"no se pudo leer: {exc}"
            return

        for entry in entries:
            name = entry.name
            if name.startswith("."):
                continue

            if entry.is_symlink():
                try:
                    target = entry.resolve()
                except OSError:
                    yield entry, "symlink inválido"
                    continue
                if not is_within(target, home()):
                    yield entry, "symlink fuera del home"
                    continue
                if target.is_dir():
                    yield from walk(target)
                elif target.is_file():
                    text, reason = read_config_text(
                        target,
                        allowed_names=allowed_names,
                        allowed_suffixes=allowed_suffixes,
                        allow_any_name=allow_any_name,
                        allow_no_extension=allow_no_extension,
                        allow_shebang=allow_shebang,
                    )
                    yield target, reason
                continue

            if entry.is_dir():
                if name.lower() in SKIP_DIRS:
                    yield entry, "carpeta omitida por privacidad"
                    continue
                if name.lower() in {item.lower() for item in skip_dirs}:
                    continue
                yield from walk(entry)
            elif entry.is_file():
                _text, reason = read_config_text(
                    entry,
                    allowed_names=allowed_names,
                    allowed_suffixes=allowed_suffixes,
                    allow_any_name=allow_any_name,
                    allow_no_extension=allow_no_extension,
                    allow_shebang=allow_shebang,
                )
                yield entry, reason

    yield from walk(base)
