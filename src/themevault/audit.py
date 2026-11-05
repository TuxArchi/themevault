"""Auditoría de privacidad de una copia local.

Detecta imágenes personales, rutas absolutas, historial de dconf, comandos de
atajos y configuraciones de shells. No modifica la copia.
"""

from __future__ import annotations

import gzip
import io
import re
import tarfile
from pathlib import Path

from .model import KIND_DCONF, KIND_FILE, KIND_TREE, Manifest
from .profile import safe_keybind
from .store import BlobStore

HOME_PATH = re.compile(r"(?:/home/[^/\s\"'<>]+|/Users/[^/\s\"'<>]+|file://[^\s\"'<>]+)")
SECRET = re.compile(
    r"(?i)(token|password|passwd|secret|api[_-]?key|authorization|bearer|"
    r"ssh-|id_rsa|id_ed25519|\.ssh|\.env)"
)
HISTORY_KEYS = re.compile(
    r"(?i)(command-history|favorite-apps|last-selected|recent|history|"
    r"picture-uri|picture-filename|last-image|wallpaper)"
)
SHELL_PREFIXES = (
    "~/.config/noctalia",
    "~/.local/state/noctalia",
    "~/.config/DankMaterialShell",
    "~/.config/quickshell",
    "~/.config/ags",
)
APPLET_PREFIXES = (
    "~/.cinnamon/configs",
    "~/.local/share/plasma/plasmoids",
    "~/.local/share/gnome-shell/extensions",
    "~/.local/share/cinnamon",
    "~/.local/share/budgie-desktop",
)
PREVIEW_KEYS = ("screenshot", "wallpaper", "cover", "covers")


def _redact(value: str, store: BlobStore | None = None) -> str:
    text = str(value)
    if store is not None:
        try:
            root = str(store.root.parent)
            text = text.replace(root, "…")
        except Exception:
            pass
    text = re.sub(r"/home/[^/\s\"'<>]+", "~", text)
    text = re.sub(r"/Users/[^/\s\"'<>]+", "~", text)
    return text[:120]


def _scan_text(text: str) -> dict:
    return {
        "paths": HOME_PATH.findall(text),
        "secrets": SECRET.findall(text),
        "history": HISTORY_KEYS.findall(text),
    }


def _tree_texts(store: BlobStore, blob: str, limit: int = 400):
    try:
        raw = gzip.decompress(store.read(blob))
    except OSError:
        return
    try:
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as tar:
            for index, member in enumerate(tar.getmembers()):
                if index > limit or not member.isfile() or member.size > 1024 * 1024:
                    continue
                try:
                    data = tar.extractfile(member).read()
                except OSError:
                    continue
                if b"\x00" in data[:4096]:
                    continue
                try:
                    yield member.name, data.decode("utf-8", "replace")
                except UnicodeDecodeError:
                    continue
    except tarfile.TarError:
        return


def _finding(
    findings: list[dict],
    *,
    category: str,
    label: str,
    severity: str,
    count: int,
    examples: list[str],
) -> None:
    if count <= 0:
        return
    findings.append(
        {
            "category": category,
            "label": label,
            "severity": severity,
            "count": count,
            "examples": examples[:5],
        }
    )


def audit_backup(manifest: Manifest, store: BlobStore | None) -> dict:
    findings: list[dict] = []
    preview = manifest.preview or {}

    images: list[str] = []
    for key in PREVIEW_KEYS:
        value = preview.get(key)
        if isinstance(value, list):
            images.extend(str(item) for item in value)
        elif value:
            images.append(str(value))
    for screen in preview.get("screens") or []:
        if screen.get("file"):
            images.append(str(screen["file"]))
    for panel in preview.get("panels") or []:
        if panel.get("file"):
            images.append(str(panel["file"]))
    _finding(
        findings,
        category="preview",
        label="Capturas y fondos guardados con la copia",
        severity="high",
        count=len(set(images)),
        examples=sorted({_redact(item, store) for item in images}),
    )

    path_examples: list[str] = []
    secret_examples: list[str] = []
    history_examples: list[str] = []
    shell_examples: list[str] = []
    applet_examples: list[str] = []
    path_count = secret_count = history_count = 0

    for item in manifest.items:
        source = item.source or item.name or ""
        if any(source.startswith(prefix) for prefix in SHELL_PREFIXES):
            shell_examples.append(source)
        if any(source.startswith(prefix) for prefix in APPLET_PREFIXES):
            applet_examples.append(source)
        if not item.blob:
            continue
        texts = []
        if item.kind in (KIND_FILE, KIND_DCONF):
            try:
                data = store.read(item.blob) if store is not None else b""
            except OSError:
                data = b""
            if data and b"\x00" not in data[:4096]:
                texts.append((source, data.decode("utf-8", "replace")))
        elif item.kind == KIND_TREE and store is not None:
            texts.extend(_tree_texts(store, item.blob))
        for label, text in texts:
            scan = _scan_text(text)
            path_count += len(scan["paths"])
            secret_count += len(scan["secrets"])
            history_count += len(scan["history"])
            if scan["paths"]:
                path_examples.append(f"{label}: {_redact(scan['paths'][0], store)}")
            if scan["secrets"]:
                secret_examples.append(f"{label}: {_redact(scan['secrets'][0], store)}")
            if scan["history"]:
                history_examples.append(f"{label}: {_redact(scan['history'][0], store)}")

    _finding(
        findings,
        category="paths",
        label="Rutas absolutas o file:// dentro de archivos",
        severity="high" if path_count else "low",
        count=path_count,
        examples=path_examples,
    )
    _finding(
        findings,
        category="secrets",
        label="Posibles tokens, contraseñas o claves",
        severity="high" if secret_count else "low",
        count=secret_count,
        examples=secret_examples,
    )
    _finding(
        findings,
        category="history",
        label="Claves de historial, favoritos o fondos en dconf",
        severity="high" if history_count else "low",
        count=history_count,
        examples=history_examples,
    )
    _finding(
        findings,
        category="shells",
        label="Configuraciones de shells (pueden tener cuentas o tokens)",
        severity="medium",
        count=len(shell_examples),
        examples=[_redact(item, store) for item in shell_examples],
    )
    _finding(
        findings,
        category="applets",
        label="Configuraciones de applets/widgets",
        severity="medium",
        count=len(applet_examples),
        examples=[_redact(item, store) for item in applet_examples],
    )

    from .profile_bundle import ASSET_PREFIXES, PLUGIN_PREFIXES

    extras = [
        item.source
        for item in manifest.items
        if item.source
        and (
            any(item.source.startswith(prefix) for prefix, _kind in PLUGIN_PREFIXES)
            or any(item.source.startswith(prefix) for prefix, _kind in ASSET_PREFIXES)
        )
    ]
    _finding(
        findings,
        category="extras",
        label="Plugins y assets que se compartirían con el perfil",
        severity="low",
        count=len(extras),
        examples=[_redact(item, store) for item in extras],
    )

    skipped = manifest.host.get("skipped") or []
    _finding(
        findings,
        category="skipped",
        label="Rutas de archivos omitidos durante el respaldo",
        severity="medium",
        count=len(skipped),
        examples=[_redact(entry.get("path", ""), store) for entry in skipped],
    )

    unsafe = [entry for entry in manifest.keybinds if not safe_keybind(entry)]
    _finding(
        findings,
        category="keybinds",
        label="Atajos con comandos, scripts o rutas",
        severity="medium",
        count=len(unsafe),
        examples=[
            _redact(
                f"{entry.get('combo', '')}: {entry.get('arg') or entry.get('script') or ''}",
                store,
            )
            for entry in unsafe
        ],
    )

    risk = "low"
    if any(f["severity"] == "high" and f["count"] for f in findings):
        risk = "high"
    elif any(f["severity"] == "medium" and f["count"] for f in findings):
        risk = "medium"

    return {
        "id": manifest.id,
        "risk": risk,
        "safe_to_share": risk == "low",
        "findings": [item for item in findings if item["count"]],
        "summary": {
            "high": sum(f["count"] for f in findings if f["severity"] == "high"),
            "medium": sum(f["count"] for f in findings if f["severity"] == "medium"),
        },
    }
