"""Transcodificación de video wallpapers para perfiles de comunidad.

El video se re-encodea a MP4 H.264 sin audio ni metadatos, con un límite de
tamaño. No se ejecuta ningún contenido del video: solo se valida y procesa con
ffmpeg/ffprobe.
"""

from __future__ import annotations

import json
from pathlib import Path

from .util import run, which

MAX_VIDEO_BYTES = 50 * 1024 * 1024
MAX_VIDEO_SECONDS = 10 * 60
VIDEO_SUFFIXES = (".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v", ".gif")


class VideoError(RuntimeError):
    pass


def tools() -> tuple[str, str] | None:
    ffmpeg = which("ffmpeg")
    ffprobe = which("ffprobe")
    if ffmpeg is None or ffprobe is None:
        return None
    return ffmpeg, ffprobe


def install_hint() -> str:
    """Comando de instalación según la distro, para mostrar al usuario."""
    release: dict[str, str] = {}
    path = Path("/etc/os-release")
    if path.is_file():
        for line in path.read_text(errors="replace").splitlines():
            if "=" in line:
                key, _, value = line.partition("=")
                release[key.strip()] = value.strip().strip('"').strip("'")
    family = f"{release.get('ID', '')} {release.get('ID_LIKE', '')}".lower()
    if "arch" in family:
        return "sudo pacman -S ffmpeg"
    if "debian" in family or "ubuntu" in family:
        return "sudo apt install ffmpeg"
    if "fedora" in family or "rhel" in family:
        return "sudo dnf install ffmpeg"
    if "suse" in family:
        return "sudo zypper install ffmpeg"
    return "instalá ffmpeg con el gestor de paquetes de tu distribución"


def probe(path: Path) -> dict:
    found = tools()
    if found is None:
        raise VideoError(
            "ffmpeg/ffprobe no están instalados. " + install_hint()
        )
    _ffmpeg, ffprobe = found
    proc = run(
        [
            ffprobe,
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ],
        timeout=30,
    )
    if proc is None or proc.returncode != 0:
        raise VideoError("no se pudo leer el video con ffprobe")
    try:
        data = json.loads(proc.stdout.decode("utf-8", "replace"))
    except ValueError as exc:
        raise VideoError("ffprobe devolvió datos inválidos") from exc

    video = next(
        (stream for stream in data.get("streams", []) if stream.get("codec_type") == "video"),
        None,
    )
    if video is None:
        raise VideoError("el archivo no tiene una pista de video")
    duration = 0.0
    for source in (video.get("duration"), (data.get("format") or {}).get("duration")):
        try:
            duration = float(source)
            break
        except (TypeError, ValueError):
            continue
    width = int(video.get("width") or 0)
    height = int(video.get("height") or 0)
    if not width or not height:
        raise VideoError("no se pudo determinar el tamaño del video")
    return {
        "width": width,
        "height": height,
        "duration": duration,
        "codec": str(video.get("codec_name") or ""),
        "has_audio": any(
            stream.get("codec_type") == "audio" for stream in data.get("streams", [])
        ),
    }


def extract_frame(source: Path, target: Path) -> None:
    found = tools()
    if found is None:
        raise VideoError("ffmpeg/ffprobe no están instalados. " + install_hint())
    ffmpeg, _ffprobe = found
    proc = run(
        [
            ffmpeg,
            "-y",
            "-ss",
            "0",
            "-i",
            str(source),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(target),
        ],
        timeout=120,
    )
    if proc is None or proc.returncode != 0 or not target.is_file():
        raise VideoError("no se pudo extraer el frame de portada del video")


def _target_bitrate(max_bytes: int, duration: float) -> int:
    if duration <= 0:
        duration = 1.0
    # Margen para el contenedor y variaciones de bitrate.
    bitrate = int(max_bytes * 8 * 0.90 / duration)
    return max(250_000, min(8_000_000, bitrate))


def _max_width(duration: float) -> int:
    if duration <= 120:
        return 1920
    if duration <= 300:
        return 1280
    return 960


def transcode(
    source: Path,
    target: Path,
    *,
    max_bytes: int = MAX_VIDEO_BYTES,
    max_duration: float = MAX_VIDEO_SECONDS,
) -> dict:
    """Re-encodea a MP4 H.264 sin audio, ajustando calidad al límite."""
    found = tools()
    if found is None:
        raise VideoError(
            "ffmpeg/ffprobe no están instalados. " + install_hint()
        )
    ffmpeg, _ffprobe = found
    source = Path(source)
    target = Path(target)
    if not source.is_file():
        raise VideoError("el video de origen no existe")
    info = probe(source)
    duration = min(float(info["duration"] or max_duration), max_duration)
    if duration <= 0:
        raise VideoError("el video no tiene una duración válida")

    attempts = []
    for width in (_max_width(duration), 1280, 960, 640):
        if width not in attempts:
            attempts.append(width)

    last_error = ""
    for width in attempts:
        bitrate = _target_bitrate(max_bytes, duration)
        target.parent.mkdir(parents=True, exist_ok=True)
        proc = run(
            [
                ffmpeg,
                "-y",
                "-i",
                str(source),
                "-t",
                f"{duration:.3f}",
                "-an",
                "-sn",
                "-map_metadata",
                "-1",
                "-vf",
                f"scale={width}:-2:force_original_aspect_ratio=decrease",
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-pix_fmt",
                "yuv420p",
                "-b:v",
                str(bitrate),
                "-maxrate",
                str(bitrate),
                "-bufsize",
                str(bitrate * 2),
                "-movflags",
                "+faststart",
                str(target),
            ],
            timeout=1800,
        )
        if proc is None or proc.returncode != 0 or not target.is_file():
            last_error = "ffmpeg falló al transcribir el video"
            target.unlink(missing_ok=True)
            continue
        size = target.stat().st_size
        if size <= max_bytes:
            frame = target.with_name("wallpaper.jpg")
            extract_frame(target, frame)
            try:
                final = probe(target)
                final_width = int(final["width"])
                final_height = int(final["height"])
            except (VideoError, OSError, KeyError):
                final_width = width
                final_height = round(width * info["height"] / max(1, info["width"]))
            return {
                "width": final_width,
                "height": final_height,
                "duration": duration,
                "size": size,
                "source_width": info["width"],
                "source_height": info["height"],
                "source_codec": info["codec"],
            }
        target.unlink(missing_ok=True)
        last_error = f"el video supera {max_bytes // 1024 // 1024} MB incluso bajando la calidad"

    raise VideoError(last_error or "no se pudo comprimir el video")


def is_video(path: Path | str) -> bool:
    candidate = Path(path)
    if candidate.suffix.lower() not in VIDEO_SUFFIXES:
        return False
    try:
        info = probe(candidate)
    except (VideoError, OSError):
        return False
    return bool(info.get("width") and info.get("height"))
