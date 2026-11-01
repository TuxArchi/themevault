"""Almacen de blobs con direccionamiento por contenido.

Cada copia es un directorio independiente (portable: se puede mover a un
pendrive sin base de datos). Dentro:

    manifest.json
    preview/        captura, wallpaper, paleta
    files/ab/cdef…  blobs: archivos sueltos y tar.gz de arboles

Los blobs se nombran por su sha256, asi que dos copias que comparten un tema
comparten bytes dentro de la misma copia y nunca guardan duplicados.
"""

from __future__ import annotations

import gzip
import io
import os
import tarfile
from pathlib import Path

from .util import sha256_bytes


class BlobStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.files_dir = self.root / "files"
        self.files_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ escritura

    def _rel(self, sha: str) -> str:
        return f"files/{sha[:2]}/{sha}"

    def put_bytes(self, data: bytes) -> tuple[str, str, int]:
        sha = sha256_bytes(data)
        rel = self._rel(sha)
        dest = self.root / rel
        if not dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp = dest.with_name(dest.name + ".tmp")
            tmp.write_bytes(data)
            os.replace(tmp, dest)
        return rel, sha, len(data)

    def put_file(self, path: Path) -> tuple[str, str, int]:
        return self.put_bytes(Path(path).read_bytes())

    def put_tree(self, path: Path, arcname: str) -> tuple[str, str, int, int]:
        """Empaqueta un directorio en tar.gz determinista.

        Se normalizan mtime/uid/gid para que el hash dependa solo del contenido:
        asi dos copias con el mismo tema deduplican de verdad.
        """
        path = Path(path)
        raw = io.BytesIO()
        count = 0
        with tarfile.open(fileobj=raw, mode="w") as tar:
            entries = sorted(path.rglob("*"), key=lambda p: str(p))
            for entry in entries:
                rel = entry.relative_to(path)
                info = tar.gettarinfo(str(entry), arcname=str(Path(arcname) / rel))
                info.mtime = 0
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                info.mode = 0o755 if entry.is_dir() else 0o644
                if info.isfile():
                    with open(entry, "rb") as fh:
                        tar.addfile(info, fh)
                    count += 1
                else:
                    tar.addfile(info)
        packed = gzip.compress(raw.getvalue(), compresslevel=6, mtime=0)
        rel_blob, sha, size = self.put_bytes(packed)
        return rel_blob, sha, size, count

    # ------------------------------------------------------------------ lectura

    def path_of(self, rel: str) -> Path:
        return self.root / rel

    def read(self, rel: str) -> bytes:
        return self.path_of(rel).read_bytes()

    def verify(self, rel: str, expected_sha: str) -> bool:
        try:
            return sha256_bytes(self.read(rel)) == expected_sha
        except OSError:
            return False

    def extract_tree(self, rel: str, dest: Path) -> int:
        """Extrae un arbol en `dest` (que se crea si no existe)."""
        dest = Path(dest)
        dest.mkdir(parents=True, exist_ok=True)
        data = gzip.decompress(self.read(rel))
        with tarfile.open(fileobj=io.BytesIO(data), mode="r") as tar:
            members = tar.getmembers()
            if hasattr(tarfile, "data_filter"):
                tar.extractall(dest, members=members, filter="data")
            else:  # Python < 3.12
                tar.extractall(dest, members=members)
            return sum(1 for m in members if m.isfile())

    # ------------------------------------------------------------------ espacio

    def stored_bytes(self) -> int:
        return sum(p.stat().st_size for p in self.files_dir.rglob("*") if p.is_file())
