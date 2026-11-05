"""Publicación de perfiles en el repositorio de la comunidad.

El flujo es deliberadamente manual en el último paso: esta capa valida el
perfil con las mismas reglas que el CI del repositorio, lo copia a un clon
local, regenera `index.json` y deja listos los comandos de git. Solo sube algo
si se pide explícitamente (`--pr`) y se confirma.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from .profile import Profile, safe_value, validate

REPO_URL = "https://github.com/TuxArchi/themevault-profiles.git"

ALLOWED_FILES = {
    "profile.json",
    "cover.png",
    "cover.jpg",
    "wallpaper.jpg",
    "wallpaper.jpeg",
    "wallpaper.png",
    "wallpaper.webp",
    "wallpaper.mp4",
    "plugins",
    "assets",
}
MAX_PROFILE = 256 * 1024
MAX_COVER = 3 * 1024 * 1024
MAX_WALLPAPER = 60 * 1024 * 1024
MAX_PLUGIN = 25 * 1024 * 1024
PNG = b"\x89PNG\r\n\x1a\n"


class PublishError(RuntimeError):
    pass


def default_repo() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "themevault" / "profiles-repo"


def load(folder: Path) -> tuple[Profile | None, list[str]]:
    """Lee y valida una carpeta exportada. Lista vacía = publicable."""
    folder = Path(folder).expanduser()
    problems: list[str] = []
    path = folder / "profile.json"

    if not folder.is_dir():
        return None, [f"{folder}: no es una carpeta"]
    if not path.is_file():
        return None, [f"{folder}: falta profile.json"]
    if path.stat().st_size > MAX_PROFILE:
        return None, ["profile.json es demasiado grande"]

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, [f"profile.json inválido: {exc}"]

    try:
        profile = Profile.from_dict(data)
    except (KeyError, TypeError, ValueError) as exc:
        return None, [f"profile.json inválido: {exc}"]

    problems.extend(validate(profile))

    if profile.id != folder.name:
        problems.append(
            f"la carpeta debe llamarse «{profile.id}» (ahora se llama «{folder.name}»)"
        )

    extra = {p.name for p in folder.iterdir()} - ALLOWED_FILES
    if extra:
        problems.append("archivos no permitidos: " + ", ".join(sorted(extra)))

    if profile.cover:
        if profile.cover not in ("cover.png", "cover.jpg"):
            problems.append("la portada debe llamarse cover.png o cover.jpg")
        file = folder / profile.cover
        if not file.is_file():
            problems.append("falta la portada")
        elif file.stat().st_size > MAX_COVER:
            problems.append("la portada supera 3 MB")
        elif profile.cover == "cover.png" and file.read_bytes()[:8] != PNG:
            problems.append("cover.png no es un PNG válido")

    wallpaper = profile.wallpaper or {}
    for key in ("file", "fallback"):
        name = str(wallpaper.get(key, "") or "")
        if not name:
            continue
        file = folder / name
        if ".." in Path(name).parts or Path(name).is_absolute():
            problems.append(f"wallpaper: archivo inválido {name}")
        elif not file.is_file():
            problems.append(f"falta el archivo de wallpaper {name}")
        elif file.stat().st_size > MAX_WALLPAPER:
            problems.append("el wallpaper supera 60 MB")

    for plugin in profile.plugins:
        name = str(plugin.get("file", "") or "")
        file = folder / name
        if ".." in Path(name).parts or Path(name).is_absolute():
            problems.append(f"plugin: archivo inválido {name}")
        elif not file.is_file():
            problems.append(f"falta el archivo del plugin {name}")
        elif file.stat().st_size > MAX_PLUGIN:
            problems.append("un plugin supera 25 MB")

    for asset in profile.assets:
        name = str(asset.get("file", "") or "")
        if not name:
            continue
        file = folder / name
        if ".." in Path(name).parts or Path(name).is_absolute():
            problems.append(f"asset: archivo inválido {name}")
        elif not file.is_file():
            problems.append(f"falta el archivo del asset {name}")
        elif file.stat().st_size > MAX_PLUGIN:
            problems.append("un asset supera 25 MB")

    for setting in profile.settings:
        backend = str(setting.get("backend", ""))
        if backend == "ini":
            name = str(setting.get("file", ""))
            if not name or name.startswith(("/", "~")) or ".." in name:
                problems.append(f"archivo ini inválido: {name or '(vacío)'}")
            if not (setting.get("group") and setting.get("key")):
                problems.append("ajuste ini incompleto")
        elif backend == "dconf":
            if not str(setting.get("path", "")).startswith("/") or not setting.get("key"):
                problems.append("ajuste dconf incompleto")
        elif backend == "xfconf":
            if not (setting.get("channel") and setting.get("prop")):
                problems.append("ajuste xfconf incompleto")

    # El validador del repositorio también exige valores sin rutas.
    for setting in profile.settings:
        value = str(setting.get("value", ""))
        if value and not safe_value(value):
            problems.append(f"valor sospechoso en {setting.get('key', setting.get('prop', '?'))}")

    return profile, problems


def gh_user() -> str:
    """Usuario autenticado en gh. Cadena vacía si no hay gh o no hay sesión."""
    gh = shutil.which("gh")
    if not gh:
        return ""
    try:
        proc = _run([gh, "api", "user", "--jq", ".login"], timeout=20)
    except PublishError:
        return ""
    if proc.returncode != 0:
        return ""
    return (proc.stdout or "").strip()


def author_mismatch(profile: Profile) -> str:
    """Avisa si el autor del perfil no es el usuario de gh de esta máquina."""
    user = gh_user()
    if user and user.lower() != profile.author.strip().lower():
        return f"gh está autenticado como @{user} y el perfil dice @{profile.author}"
    return ""


def clone(destination: Path) -> Path:
    """Clona el repositorio de perfiles (solo si todavía no existe)."""
    destination = Path(destination).expanduser()
    if destination.exists():
        raise PublishError(f"{destination} ya existe")
    destination.parent.mkdir(parents=True, exist_ok=True)
    proc = _run(["git", "clone", "--depth", "1", REPO_URL, str(destination)])
    if proc.returncode != 0:
        raise PublishError(_output(proc))
    return destination


def index_ids(repo: Path) -> set[str]:
    path = Path(repo) / "index.json"
    if not path.is_file():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()
    return {str(entry.get("id", "")) for entry in data.get("profiles") or []}


def stage(repo: Path, folder: Path) -> Path:
    """Copia el perfil a `<repo>/profiles/<id>` pisando la versión anterior."""
    repo = Path(repo).expanduser()
    folder = Path(folder).expanduser()
    target = repo / "profiles" / folder.name

    if not (repo / "profiles").is_dir():
        raise PublishError(f"{repo} no parece el repositorio de perfiles")

    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)

    for name in sorted(ALLOWED_FILES):
        source = folder / name
        if source.is_file():
            shutil.copy2(source, target / name)
        elif source.is_dir() and name in ("plugins", "assets"):
            shutil.copytree(source, target / name)
    return target


def rebuild_index(repo: Path) -> str:
    """Corre tools/build_index.py del repositorio."""
    repo = Path(repo).expanduser()
    script = repo / "tools" / "build_index.py"
    if not script.is_file():
        raise PublishError(f"falta {script}")

    proc = _run([sys.executable, str(script)], cwd=repo, timeout=180)
    if proc.returncode != 0:
        raise PublishError(_output(proc).strip() or "el índice no se pudo regenerar")
    return _output(proc).strip()


def prepare_branch(repo: Path, profile_id: str, branch: str) -> str:
    """Crea la rama, agrega el perfil y el índice, y hace el commit local."""
    repo = Path(repo).expanduser()
    if not _is_repo(repo):
        raise PublishError(f"{repo} no es un repositorio git")

    exists = _run(
        ["git", "rev-parse", "--verify", "--quiet", branch], cwd=repo
    )
    if exists.returncode == 0:
        raise PublishError(f"la rama {branch} ya existe")

    for command in (
        ["git", "checkout", "-b", branch],
        ["git", "add", "--", f"profiles/{profile_id}", "index.json"],
        ["git", "commit", "-m", f"perfil: {profile_id}"],
    ):
        proc = _run(command, cwd=repo)
        if proc.returncode != 0:
            raise PublishError(_output(proc).strip() or f"falló: {' '.join(command)}")
    return branch


def push_branch(repo: Path, branch: str) -> None:
    proc = _run(["git", "push", "-u", "origin", branch], cwd=Path(repo))
    if proc.returncode != 0:
        raise PublishError(_output(proc).strip() or "no se pudo subir la rama")


def open_pr(repo: Path, profile: Profile) -> str:
    """Abre el PR con gh y devuelve la URL."""
    gh = shutil.which("gh")
    if not gh:
        raise PublishError("falta gh (GitHub CLI) para abrir el PR")

    body = (
        f"Perfil **{profile.name}** de {profile.author} ({profile.desktop}).\n\n"
        f"- id: `{profile.id}`\n"
        f"- licencia: {profile.license}\n"
        f"- ajustes: {len(profile.settings)}\n"
        f"- portada: {'sí' if profile.cover else 'no'}\n\n"
        "Generado con `themevault export-profile` y validado por `publish-profile`."
    )
    proc = _run(
        [gh, "pr", "create", "--title", f"perfil: {profile.id}", "--body", body],
        cwd=Path(repo),
    )
    if proc.returncode != 0:
        raise PublishError(_output(proc).strip() or "gh no pudo abrir el PR")
    lines = [line for line in _output(proc).strip().splitlines() if line.strip()]
    return lines[-1] if lines else ""


def _is_repo(repo: Path) -> bool:
    proc = _run(["git", "rev-parse", "--is-inside-work-tree"], cwd=repo)
    return proc.returncode == 0 and proc.stdout.strip() == "true"


def _run(
    command: list[str], cwd: Path | None = None, timeout: int = 120
) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise PublishError(f"no se pudo ejecutar {command[0]}: {exc}") from exc


def _output(proc: subprocess.CompletedProcess) -> str:
    return (proc.stdout or "") + (proc.stderr or "")
