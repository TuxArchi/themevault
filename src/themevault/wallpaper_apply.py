"""Aplicación de wallpapers de perfiles de comunidad."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .util import child_env, expand, run, which

WAYLAND_DESKTOPS = {
    "hyprland",
    "niri",
    "sway",
    "river",
    "wayfire",
    "labwc",
    "cosmic",
}


def _copy_to_store(source: Path, profile_id: str) -> Path:
    folder = expand("~/.local/share/themevault/wallpapers")
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{profile_id}{source.suffix.lower() or '.jpg'}"
    shutil.copyfile(source, target)
    return target


def _spawn(cmd: list[str]) -> bool:
    try:
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            env=child_env(),
        )
        return True
    except OSError:
        return False


def _gsettings(schema: str, key: str, value: str) -> bool:
    if which("gsettings") is None:
        return False
    proc = run(["gsettings", "set", schema, key, value], timeout=20)
    return proc is not None and proc.returncode == 0


def _apply_gtk_like(path: Path, desktop: str) -> bool:
    uri = f"file://{path}"
    settings = {
        "gnome": (
            ("org.gnome.desktop.background", "picture-uri"),
            ("org.gnome.desktop.background", "picture-uri-dark"),
        ),
        "budgie": (
            ("org.gnome.desktop.background", "picture-uri"),
            ("org.gnome.desktop.background", "picture-uri-dark"),
        ),
        "cinnamon": (
            ("org.cinnamon.desktop.background", "picture-uri"),
            ("org.cinnamon.desktop.background", "picture-uri-dark"),
        ),
        "mate": (("org.mate.background", "picture-filename"),),
    }.get(desktop, ())
    applied = False
    for schema, key in settings:
        applied = _gsettings(schema, key, uri) or applied
    return applied


def _apply_kde(path: Path) -> bool:
    tool = which("plasma-apply-wallpaperimage")
    if tool is None:
        return False
    proc = run([tool, str(path)], timeout=30)
    return proc is not None and proc.returncode == 0


def _apply_xfce(path: Path) -> bool:
    tool = which("xfconf-query")
    if tool is None:
        return False
    listing = run([tool, "-c", "xfce4-desktop", "-l"], timeout=20)
    if listing is None or listing.returncode != 0:
        return False
    applied = False
    for prop in listing.stdout.decode("utf-8", "replace").splitlines():
        if not prop.endswith("/last-image"):
            continue
        proc = run(
            [tool, "-c", "xfce4-desktop", "-p", prop, "-s", str(path)],
            timeout=20,
        )
        applied = (proc is not None and proc.returncode == 0) or applied
    return applied


def _apply_sway(path: Path) -> bool:
    tool = which("swaymsg")
    if tool is None:
        return False
    proc = run([tool, "output", "*", "bg", str(path), "fill"], timeout=20)
    return proc is not None and proc.returncode == 0


def _apply_x11(path: Path) -> bool:
    tool = which("feh", "nitrogen")
    if tool is None:
        return False
    if Path(tool).name == "feh":
        proc = run([tool, "--bg-fill", str(path)], timeout=20)
    else:
        proc = run([tool, "--set-zoom-fill", str(path)], timeout=20)
    return proc is not None and proc.returncode == 0


def _apply_hyprpaper(path: Path) -> bool:
    tool = which("hyprctl")
    if tool is None:
        return False
    run([tool, "hyprpaper", "preload", str(path)], timeout=20)
    proc = run([tool, "hyprpaper", "wallpaper", f",{path}"], timeout=20)
    return proc is not None and proc.returncode == 0


def _apply_mpvpaper(path: Path) -> bool:
    tool = which("mpvpaper")
    if tool is None:
        return False
    return _spawn([tool, "-o", "no-audio loop", "*", str(path)])


def _apply_image(path: Path, desktop: str) -> bool:
    if desktop in ("gnome", "cinnamon", "mate", "budgie"):
        return _apply_gtk_like(path, desktop)
    if desktop == "kde":
        return _apply_kde(path)
    if desktop == "xfce":
        return _apply_xfce(path)
    if desktop == "sway":
        return _apply_sway(path)
    if desktop == "hyprland":
        return _apply_hyprpaper(path) or _apply_x11(path)
    if desktop in ("i3", "openbox"):
        return _apply_x11(path)
    if desktop == "lxqt":
        tool = which("pcmanfm-qt")
        if tool is not None:
            proc = run([tool, "--set-wallpaper", str(path)], timeout=20)
            if proc is not None and proc.returncode == 0:
                return True
        return _apply_x11(path)
    if desktop == "cosmic":
        tool = which("cosmic-bg")
        if tool is not None:
            proc = run([tool, "-i", str(path)], timeout=20)
            if proc is not None and proc.returncode == 0:
                return True
    if desktop in WAYLAND_DESKTOPS and which("swaybg") is not None:
        return _spawn(["swaybg", "-i", str(path)])
    return False


def apply(
    wallpaper: dict,
    bundle_dir: Path,
    *,
    profile_id: str,
    desktop: str,
) -> dict:
    """Aplica imagen o video. Si no se puede, intenta el frame estático."""
    if not wallpaper:
        return {"applied": False, "fallback": False, "message": "el perfil no trae fondo"}
    file = Path(bundle_dir) / str(wallpaper.get("file", ""))
    if not file.is_file():
        return {"applied": False, "fallback": False, "message": "falta el archivo de fondo"}

    kind = str(wallpaper.get("kind", "image"))
    if kind == "video":
        video_target = _copy_to_store(file, profile_id)
        if desktop in WAYLAND_DESKTOPS and _apply_mpvpaper(video_target):
            return {
                "applied": True,
                "fallback": False,
                "message": "video aplicado con mpvpaper",
                "path": str(video_target),
            }
        fallback = Path(bundle_dir) / str(wallpaper.get("fallback", ""))
        if fallback.is_file():
            target = _copy_to_store(fallback, profile_id)
            applied = _apply_image(target, desktop)
            return {
                "applied": applied,
                "fallback": True,
                "message": (
                    "video no aplicable en este entorno; se usó el frame estático"
                    if applied
                    else "video no aplicable; frame estático guardado en " + str(target)
                ),
            }
        return {
            "applied": False,
            "fallback": False,
            "message": "no hay mpvpaper ni frame estático disponible",
        }

    target = _copy_to_store(file, profile_id)
    applied = _apply_image(target, desktop)
    return {
        "applied": applied,
        "fallback": False,
        "message": "" if applied else "fondo guardado en " + str(target),
    }
