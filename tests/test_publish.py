"""Tests de la publicación de perfiles (sin red ni gh)."""

from __future__ import annotations

import json
from pathlib import Path

from themevault import publish

PERFIL = {
    "schema": 1,
    "id": "demo-kde",
    "name": "Demo",
    "author": "yo",
    "license": "MIT",
    "desktop": "kde",
    "description": "",
    "created": "2026-11-01",
    "preview": {"cover": "", "palette": ["#101010"]},
    "requires": {"icons": "Papirus-Dark"},
    "settings": [
        {
            "backend": "ini",
            "file": "kdeglobals",
            "group": "General",
            "key": "ColorScheme",
            "value": "DemoScheme",
        }
    ],
}


def _bundle(base: Path, data: dict | None = None, files: dict[str, bytes] | None = None) -> Path:
    folder = base / (data or PERFIL)["id"]
    folder.mkdir(parents=True)
    (folder / "profile.json").write_text(json.dumps(data or PERFIL), encoding="utf-8")
    for name, content in (files or {}).items():
        (folder / name).write_bytes(content)
    return folder


def test_load_acepta_un_perfil_valido(tmp_path):
    folder = _bundle(tmp_path)
    profile, problems = publish.load(folder)

    assert problems == []
    assert profile is not None and profile.id == "demo-kde"


def test_load_exige_que_la_carpeta_se_llame_como_el_id(tmp_path):
    folder = _bundle(tmp_path)
    otra = folder.rename(tmp_path / "otra-carpeta")

    _, problems = publish.load(otra)
    assert any("debe llamarse" in p for p in problems)


def test_load_rechaza_archivos_extra(tmp_path):
    folder = _bundle(tmp_path)
    (folder / "notas.txt").write_text("privado")

    _, problems = publish.load(folder)
    assert any("no permitidos" in p for p in problems)


def test_load_rechaza_valores_con_rutas(tmp_path):
    data = dict(PERFIL)
    data["settings"] = [
        {"backend": "ini", "file": "kdeglobals", "group": "G", "key": "k",
         "value": "/home/alguien/privado"}
    ]
    folder = _bundle(tmp_path, data=data)

    _, problems = publish.load(folder)
    assert any("sospechoso" in p for p in problems)


def test_load_valida_la_portada(tmp_path):
    data = dict(PERFIL, preview={"cover": "cover.png", "palette": []})
    folder = _bundle(tmp_path, data=data, files={"cover.png": b"no soy png"})

    _, problems = publish.load(folder)
    assert any("no es un PNG" in p for p in problems)


def test_stage_copia_y_reemplaza(tmp_path):
    repo = tmp_path / "repo"
    (repo / "profiles").mkdir(parents=True)
    folder = _bundle(tmp_path / "exportado")

    target = publish.stage(repo, folder)
    assert (target / "profile.json").is_file()
    assert target.name == "demo-kde"

    (target / "viejo.png").write_bytes(b"x")
    publish.stage(repo, folder)
    assert not (target / "viejo.png").exists()


def test_rebuild_index_corre_el_script_del_repo(tmp_path):
    repo = tmp_path / "repo"
    (repo / "profiles" / "demo-kde").mkdir(parents=True)
    (repo / "tools").mkdir()
    (repo / "tools" / "build_index.py").write_text(
        "import json, pathlib\n"
        "root = pathlib.Path(__file__).resolve().parents[1]\n"
        "ids = sorted(p.name for p in (root / 'profiles').iterdir() if p.is_dir())\n"
        "(root / 'index.json').write_text(json.dumps({'schema': 1, 'profiles': [{'id': i} for i in ids]}))\n"
        "print('indice con', len(ids), 'perfiles')\n"
    )

    summary = publish.rebuild_index(repo)

    assert "indice con 1" in summary
    assert publish.index_ids(repo) == {"demo-kde"}


def test_index_ids_sin_indice(tmp_path):
    assert publish.index_ids(tmp_path) == set()
