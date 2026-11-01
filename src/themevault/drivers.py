"""Drivers para backends que no son archivos: dconf y xfconf.

Ninguno de los dos se puede copiar "a mano": dconf es un binario compilado y
xfconf vive en XML que el demonio reescribe. Por eso se habla con sus CLIs
(o se parsea el XML en el caso de xfconf, que ademas nos da los tipos).
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from .util import expand, run, which

# ----------------------------------------------------------------------- dconf


def dconf_available() -> bool:
    return which("dconf") is not None


def dconf_dump(path: str) -> bytes | None:
    proc = run(["dconf", "dump", path])
    if proc is None or proc.returncode != 0:
        return None
    return proc.stdout


def dconf_load(path: str, data: bytes) -> tuple[bool, str]:
    proc = run(["dconf", "load", path], input_bytes=data)
    if proc is None:
        return False, "dconf no esta instalado"
    if proc.returncode != 0:
        return False, proc.stderr.decode("utf-8", "replace").strip()
    return True, ""


def gsettings_get(schema: str, key: str) -> str | None:
    proc = run(["gsettings", "get", schema, key])
    if proc is None or proc.returncode != 0:
        return None
    return proc.stdout.decode("utf-8", "replace").strip()


# ---------------------------------------------------------------------- xfconf

XFCHANNEL_DIRS = (
    "~/.config/xfce4/xfconf/xfconfd/xfconf-perchannel-xml",
    "~/.config/xfce4/xfconf/xfconf-perchannel-xml",
)

# Tipos escalares que xfconf-query sabe asignar con -t
_SCALAR_TYPES = {"string", "int", "uint", "int64", "uint64", "double", "bool", "uchar"}


def xfconf_available() -> bool:
    return which("xfconf-query") is not None


def channel_file(channel: str) -> Path | None:
    for raw in XFCHANNEL_DIRS:
        candidate = expand(raw) / f"{channel}.xml"
        if candidate.exists():
            return candidate
    return None


def read_channel(channel: str) -> tuple[list[dict], int]:
    """Devuelve las propiedades escalares de un canal y cuantas se omitieron.

    xfconf no tiene un "dump" plano utilizable: se parsea el XML, que trae
    name/type/value por propiedad y refleja los valores actuales.
    """
    path = channel_file(channel)
    if path is None:
        return [], 0
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError):
        return [], 0

    props: list[dict] = []
    skipped = 0

    def walk(node: ET.Element, prefix: str) -> None:
        nonlocal skipped
        for child in node.findall("property"):
            name = child.get("name") or ""
            prop_path = f"{prefix}/{name}" if prefix else f"/{name}"
            ptype = (child.get("type") or "empty").strip()
            if ptype == "array":
                skipped += 1  # arrays: fuera de alcance por ahora
                continue
            if ptype == "empty" or child.findall("property"):
                walk(child, prop_path)
                continue
            value = child.get("value")
            if ptype in _SCALAR_TYPES and value is not None:
                props.append(
                    {
                        "channel": channel,
                        "prop": prop_path,
                        "type": ptype,
                        "value": value,
                    }
                )
            else:
                skipped += 1  # arrays y tipos exóticos: fuera de alcance por ahora

    walk(root, "")
    return props, skipped


def set_prop(channel: str, prop: str, ptype: str, value: str) -> tuple[bool, str]:
    base = ["xfconf-query", "-c", channel, "-p", prop, "-t", ptype, "-s", value]
    proc = run(base)
    if proc is not None and proc.returncode == 0:
        return True, ""
    proc = run(base + ["-n"])  # -n: crear si no existe
    if proc is not None and proc.returncode == 0:
        return True, ""
    detail = proc.stderr.decode("utf-8", "replace").strip() if proc else "sin salida"
    return False, detail or "xfconf-query fallo"


def xfconf_read_raw(channel: str) -> bytes | None:
    path = channel_file(channel)
    if path is None:
        return None
    try:
        return path.read_bytes()
    except OSError:
        return None
