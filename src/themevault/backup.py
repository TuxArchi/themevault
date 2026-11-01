"""Motor de respaldo: orquesta adaptadores y escribe la copia en disco."""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from pathlib import Path

from .adapters import Adapter, Collector, detected_adapters
from .detect import detect_host
from .model import Manifest
from .preview import build_preview
from .store import BlobStore
from .util import default_root, human_size
from .widgets import enrich_containers
from .widgets import from_items as widgets_from_items


def current_themes() -> dict[str, str]:
    """Temas activos ahora mismo (para regenerar portadas viejas)."""
    return _merge_themes(detected_adapters())


def _merge_themes(adapters: list[Adapter]) -> dict[str, str]:
    """Junta los nombres de tema activos que reporta cada adaptador."""
    themes: dict[str, str] = {}
    for adapter in adapters:
        try:
            found = adapter.themes()
        except Exception:
            continue
        for key, value in found.items():
            if value and key not in themes:
                themes[key] = value
    return themes


class BackupEngine:
    def __init__(self, root: Path | None = None):
        self.root = Path(root) if root else default_root()
        self.backups_dir = self.root / "backups"

    # ------------------------------------------------------------------ crear

    def create(
        self,
        *,
        adapters: list[Adapter] | None = None,
        label: str = "",
        notes: str = "",
        preview: bool = True,
    ) -> Manifest:
        chosen = adapters if adapters is not None else detected_adapters()
        if not chosen:
            raise RuntimeError(
                "No se detecto ningun entorno soportado. "
                "Usa --adapter <gnome|kde|xfce> para forzarlo."
            )

        host = detect_host()
        host["adapters"] = [adapter.id for adapter in chosen]

        backup_id = self._new_id(host["de"])
        self.backups_dir.mkdir(parents=True, exist_ok=True)
        staging = self.backups_dir / f".staging-{backup_id}"
        if staging.exists():
            shutil.rmtree(staging)
        staging.mkdir(parents=True)

        try:
            store = BlobStore(staging)
            collector = Collector(store)
            for adapter in chosen:
                adapter.collect(collector)

            host["skipped"] = [{"path": path, "reason": reason} for path, reason in collector.skipped]
            host["themes"] = _merge_themes(chosen)

            layout = widgets_from_items(collector.items, store)
            layout["containers"] = enrich_containers(layout["containers"])

            manifest = Manifest(
                id=backup_id,
                created=datetime.now().astimezone().isoformat(timespec="seconds"),
                host=host,
                items=collector.items,
                containers=layout["containers"],
                widgets=layout["widgets"],
                label=label,
                notes=notes,
            )
            manifest.preview = build_preview(
                staging,
                chosen,
                enabled=preview,
                themes=host["themes"],
                containers=layout["containers"],
            )
            self._write_manifest(staging, manifest)

            final = self.backups_dir / backup_id
            os.replace(staging, final)
        except BaseException:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        return manifest

    # ----------------------------------------------------------------- listar

    def ids(self) -> list[str]:
        if not self.backups_dir.is_dir():
            return []
        return sorted(
            (entry.name for entry in self.backups_dir.iterdir() if entry.is_dir() and not entry.name.startswith(".")),
            reverse=True,
        )

    def load(self, backup_id: str) -> Manifest:
        path = self.backup_dir(backup_id) / "manifest.json"
        if not path.exists():
            raise FileNotFoundError(f"No existe la copia '{backup_id}'")
        return Manifest.from_dict(json.loads(path.read_text()))

    def load_all(self) -> list[Manifest]:
        out: list[Manifest] = []
        for backup_id in self.ids():
            try:
                out.append(self.load(backup_id))
            except (OSError, ValueError, KeyError):
                continue
        return out

    def latest(self) -> Manifest | None:
        ids = self.ids()
        return self.load(ids[0]) if ids else None

    def resolve(self, prefix: str) -> Manifest:
        """Acepta un id completo o un prefijo unico (comodo en la CLI)."""
        if (self.backups_dir / prefix).is_dir():
            return self.load(prefix)
        matches = [i for i in self.ids() if i.startswith(prefix)]
        if not matches:
            raise FileNotFoundError(f"No hay copias que empiecen con '{prefix}'")
        if len(matches) > 1:
            raise ValueError(f"Prefijo ambiguo, candidatos: {', '.join(matches)}")
        return self.load(matches[0])

    # --------------------------------------------------------------- consultar

    def backup_dir(self, backup_id: str) -> Path:
        return self.backups_dir / backup_id

    def store(self, backup_id: str) -> BlobStore:
        return BlobStore(self.backup_dir(backup_id))

    def verify(self, backup_id: str) -> list[str]:
        """Verifica los hashes de una copia. Devuelve la lista de problemas."""
        manifest = self.load(backup_id)
        store = self.store(backup_id)
        problems: list[str] = []
        for item in manifest.items:
            if not item.blob:
                continue
            if not store.path_of(item.blob).exists():
                problems.append(f"falta el blob de {item.name}")
            elif not store.verify(item.blob, item.sha256):
                problems.append(f"hash invalido en {item.name}")
        return problems

    def save(self, manifest: Manifest) -> None:
        """Reescribe el manifest de una copia (usado por `rebuild`)."""
        self._write_manifest(self.backup_dir(manifest.id), manifest)

    def delete(self, backup_id: str) -> None:
        target = self.backup_dir(backup_id)
        if not target.is_dir():
            raise FileNotFoundError(f"No existe la copia '{backup_id}'")
        shutil.rmtree(target)

    def summary(self) -> str:
        ids = self.ids()
        total = sum(self._dir_size(self.backups_dir / i) for i in ids)
        plural = "copia" if len(ids) == 1 else "copias"
        return f"{len(ids)} {plural}, {human_size(total)}"

    # --------------------------------------------------------------- internos

    def _new_id(self, de: str) -> str:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        base = f"{stamp}-{de}"
        candidate = base
        counter = 2
        while (self.backups_dir / candidate).exists():
            candidate = f"{base}-{counter}"
            counter += 1
        return candidate

    @staticmethod
    def _write_manifest(directory: Path, manifest: Manifest) -> None:
        tmp = directory / "manifest.json.tmp"
        tmp.write_text(json.dumps(manifest.to_dict(), indent=2, ensure_ascii=False))
        os.replace(tmp, directory / "manifest.json")

    @staticmethod
    def _dir_size(path: Path) -> int:
        return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
