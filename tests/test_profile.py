"""Tests de perfiles compartibles: redaccion, validacion y aplicación."""

from __future__ import annotations

import configparser
import json
from pathlib import Path

from themevault import profile as profile_mod
from themevault.model import Manifest
from themevault.restore import build_plan
from themevault.store import BlobStore

PERSONAL = "archi"
HOME = f"/home/{PERSONAL}"

KDEGLOBALS = f"""[General]
ColorScheme=CatppuccinMocha
LastUsedPath={HOME}/Documentos/privado
font=Noto Sans,10,-1,5,50,0,0,0,0,0

[Icons]
Theme=Papirus-Dark

[KDE]
ShowMediaControls=true
"""

DCONF = """[org/gnome/desktop/interface]
gtk-theme='Adwaita-dark'
icon-theme='Papirus'
cursor-theme='Breeze'
color-scheme='prefer-dark'
font-name='Noto Sans 11'
last-selected='file:///home/archi/secreto'
"""


def _manifest(store: BlobStore) -> Manifest:
    from themevault.model import Item

    items = []
    blob, sha, size = store.put_bytes(KDEGLOBALS.encode())
    items.append(
        Item(
            kind="file",
            category="theme",
            name="kdeglobals",
            source="~/.config/kdeglobals",
            blob=blob,
            sha256=sha,
            size=size,
        )
    )
    blob, sha, size = store.put_bytes(DCONF.encode())
    items.append(
        Item(
            kind="dconf",
            category="theme",
            name="Apariencia GNOME",
            backend="dconf",
            data={"path": "/org/gnome/desktop/interface/"},
            blob=blob,
            sha256=sha,
            size=size,
        )
    )
    return Manifest(
        id="copia",
        created="2026-01-01T00:00:00",
        host={
            "de": "kde",
            "themes": {"icons": "Papirus-Dark", "cursor": "Breeze", "plasma": "breeze"},
        },
        items=items,
        preview={"palette": ["#112233", "#445566"]},
    )


def test_exporta_solo_lo_permitido(tmp_path):
    store = BlobStore(tmp_path / "backup")
    manifest = _manifest(store)

    perfil, dropped = profile_mod.build_profile(
        manifest,
        store,
        name="Catppuccin Mocha",
        author="tuxarchi",
        license="CC-BY-SA-4.0",
        description="tema oscuro",
    )

    assert perfil.id == "catppuccin-mocha"
    assert perfil.desktop == "kde"
    assert perfil.requires["icons"] == "Papirus-Dark"

    claves = {(s["file"], s["group"], s["key"]) for s in perfil.settings}
    assert ("kdeglobals", "General", "ColorScheme") in claves
    assert ("kdeglobals", "Icons", "Theme") in claves
    # claves fuera de la lista blanca no viajan
    assert not any("LastUsedPath" in c for c in claves)
    assert not any("ShowMediaControls" in c for c in claves)

    texto = json.dumps(perfil.to_dict(), ensure_ascii=False)
    assert PERSONAL not in texto.replace("tuxarchi", "")
    assert "/home/" not in texto
    assert "Documentos" not in texto
    assert "secreto" not in texto
    assert dropped


def test_no_comparte_la_captura_por_defecto(tmp_path):
    store = BlobStore(tmp_path / "backup")
    manifest = _manifest(store)
    perfil, dropped = profile_mod.build_profile(
        manifest, store, name="X", author="a", license="MIT"
    )
    assert perfil.cover == ""
    assert any("captura" in note for note in dropped)


def test_validacion_rechaza_rutas_y_licencias(tmp_path):
    store = BlobStore(tmp_path / "backup")
    manifest = _manifest(store)
    perfil, _ = profile_mod.build_profile(
        manifest, store, name="X", author="a", license="MIT"
    )
    assert profile_mod.validate(perfil) == []

    malo = profile_mod.Profile(
        id="x", name="X", author="a", license="WTFPL", desktop="kde"
    )
    problemas = profile_mod.validate(malo)
    assert any("licencia" in p for p in problemas)
    assert any("id" in p for p in problemas)

    con_ruta = profile_mod.Profile(
        id="bien", name="X", author="a", license="MIT", desktop="kde",
        settings=[{"backend": "ini", "file": "kdeglobals", "group": "G", "key": "k", "value": "/home/x/secreto"}],
    )
    assert any("sospechoso" in p for p in profile_mod.validate(con_ruta))


def test_export_bundle_escribe_json(tmp_path):
    store = BlobStore(tmp_path / "backup")
    manifest = _manifest(store)
    perfil, _ = profile_mod.build_profile(
        manifest, store, name="Mi Tema", author="yo", license="MIT"
    )
    out = tmp_path / "salida"
    destino = profile_mod.export_bundle(perfil, out, manifest=manifest, store=store)

    assert destino == out / "profile.json"
    data = json.loads(destino.read_text())
    assert data["id"] == "mi-tema"
    assert data["settings"]
    assert (out / "profile.json").stat().st_size > 0


def test_profile_a_manifest(tmp_path):
    store = BlobStore(tmp_path / "backup")
    manifest = _manifest(store)
    perfil, _ = profile_mod.build_profile(
        manifest, store, name="Mi Tema", author="yo", license="MIT"
    )
    sintetico = profile_mod.to_manifest(perfil)
    assert sintetico.items
    assert all(item.kind == "setting" for item in sintetico.items)

    acciones = build_plan(sintetico, None)
    assert len(acciones) == len(perfil.settings)
    assert all(a.status in ("ok", "blocked") for a in acciones)


def test_slug_con_acentos():
    assert profile_mod._slug("Catppuccin Invierno") == "catppuccin-invierno"
    assert profile_mod._slug("Ñandú Azul") == "nandu-azul"


COLORS = """[Colors:Window]
BackgroundNormal=30,30,46
ForegroundNormal=205,214,244

[Colors:View]
BackgroundNormal=24,24,37

[Colors:Button]
BackgroundNormal=49,50,68

[Colors:Selection]
BackgroundNormal=137,180,250
"""


def test_paleta_desde_el_esquema_no_del_wallpaper(tmp_path):
    from themevault.model import Item

    store = BlobStore(tmp_path / "backup")
    manifest = _manifest(store)

    blob, sha, size = store.put_bytes(COLORS.encode())
    manifest.items.append(
        Item(
            kind="file",
            category="colorscheme",
            name="Catppuccin.colors",
            source="~/.local/share/color-schemes/Catppuccin.colors",
            blob=blob,
            sha256=sha,
            size=size,
        )
    )
    manifest.host["themes"]["color_scheme"] = "Catppuccin"
    # una paleta "personal" que NO debe usarse
    manifest.preview["palette"] = ["#ff0000"]

    perfil, _ = profile_mod.build_profile(
        manifest, store, name="Catppuccin", author="yo", license="MIT"
    )

    assert perfil.palette == ["#1e1e2e", "#181825", "#313244", "#89b4fa", "#cdd6f4"]
    assert "#ff0000" not in perfil.palette
    assert perfil.requires["color_scheme"] == "Catppuccin"


def test_aplicar_perfil_ini_escribe_en_config(tmp_path, monkeypatch):
    from themevault.profile import Profile, to_manifest
    from themevault.restore import apply_plan, build_plan

    config = tmp_path / "config"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config))
    # Forzar la ruta de escritura propia: en KDE existe kwriteconfig y el
    # formato del archivo cambia, lo que no debe alterar el resultado.
    monkeypatch.setattr("themevault.restore.which", lambda *names: None)

    perfil = Profile(
        id="demo-kde",
        name="Demo",
        author="yo",
        license="MIT",
        desktop="kde",
        settings=[
            {"backend": "ini", "file": "kdeglobals", "group": "General",
             "key": "ColorScheme", "value": "DemoScheme"},
            {"backend": "ini", "file": "kdeglobals", "group": "Icons",
             "key": "Theme", "value": "Papirus-Dark"},
        ],
    )
    assert profile_mod.validate(perfil) == []

    acciones = build_plan(to_manifest(perfil), None)
    assert all(a.status == "ok" for a in acciones), [a.message for a in acciones]

    report = apply_plan(acciones, None, safety=False)
    assert report.failed() == 0 if hasattr(report, "failed") else True
    assert report.applied == 2

    parser = configparser.RawConfigParser()
    parser.optionxform = str
    assert parser.read(config / "kdeglobals")
    assert parser.get("General", "ColorScheme") == "DemoScheme"
    assert parser.get("Icons", "Theme") == "Papirus-Dark"


def test_export_bundle_incluye_portada(tmp_path):
    from themevault.profile import Profile, export_bundle

    backup = tmp_path / "copia"
    store = BlobStore(backup)
    (backup / "preview").mkdir()
    imagen = b"\x89PNG\r\n\x1a\n" + b"datos"
    (backup / "preview" / "cover.png").write_bytes(imagen)
    (backup / "preview" / "wallpaper.png").write_bytes(imagen)

    manifest = Manifest(
        id="copia",
        created="2026-11-01T10:00:00",
        host={"de": "kde"},
        preview={"cover": "preview/cover.png", "wallpaper": "preview/wallpaper.png"},
    )
    perfil = Profile(
        id="demo",
        name="Demo",
        author="yo",
        license="MIT",
        desktop="kde",
        cover="cover.png",
    )

    out = tmp_path / "salida"
    export_bundle(perfil, out, manifest=manifest, store=store)

    assert (out / "profile.json").is_file()
    assert (out / "cover.jpg").read_bytes() == imagen


def test_export_bundle_ignora_portada_fuera_de_la_copia(tmp_path):
    from themevault.profile import Profile, export_bundle

    (tmp_path / "secreto.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    backup = tmp_path / "copia"
    store = BlobStore(backup)

    manifest = Manifest(
        id="copia",
        created="2026-11-01T10:00:00",
        host={"de": "kde"},
        preview={"cover": "../../secreto.png"},
    )
    perfil = Profile(
        id="demo",
        name="Demo",
        author="yo",
        license="MIT",
        desktop="kde",
        cover="cover.png",
    )

    out = tmp_path / "salida"
    export_bundle(perfil, out, manifest=manifest, store=store)
    assert not (out / "cover.png").exists()


def test_output_dir_se_llama_como_el_id(tmp_path):
    from themevault.profile import Profile, output_dir

    perfil = Profile(id="mi-estilo", name="Mi estilo", author="yo", license="MIT", desktop="kde")
    assert output_dir(tmp_path, perfil) == tmp_path / "mi-estilo"


def test_handle_de_github():
    for bueno in ("TuxArchi", "a", "tux-archi", "user123"):
        assert profile_mod.is_handle(bueno), bueno

    for malo in ("", "Tux Archi", "@tux", "tux_archi", "-tux", "tux-",
                 "tux--archi", "x" * 40, "Linus Torvalds", "yo@ejemplo.com"):
        assert not profile_mod.is_handle(malo), malo


def test_validate_rechaza_autor_que_no_es_handle():
    perfil = profile_mod.Profile(
        id="demo-kde",
        name="Demo",
        author="Linus Torvalds",
        license="MIT",
        desktop="kde",
    )
    problemas = profile_mod.validate(perfil)
    assert any("autor inválido" in p for p in problemas), problemas


def test_cli_export_profile_rechaza_autor_invalido(tmp_path, capsys):
    from themevault.cli import main

    code = main([
        "export-profile", "cualquiera",
        "--root", str(tmp_path),
        "--author", "Linus Torvalds",
    ])

    assert code == 2
    assert "usuario de GitHub" in capsys.readouterr().out
