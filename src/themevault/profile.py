"""Perfiles compartibles de la comunidad.

Un perfil NO es una copia: es la descripcion del aspecto, sin archivos de tema,
sin rutas y sin datos personales. Se comparte como `profile.json` (+ portada) y
se aplica con el mismo motor de restauracion.

Regla de oro: lo que no este en la lista blanca de campos, no se exporta.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .model import KIND_SETTING, Manifest, Item
from .store import BlobStore
from .util import is_within

SCHEMA = 1

DESKTOPS = (
    "kde",
    "gnome",
    "xfce",
    "hyprland",
    "cinnamon",
    "mate",
    "budgie",
    "lxqt",
    "other",
)

LICENSES = (
    "CC0-1.0",
    "CC-BY-4.0",
    "CC-BY-SA-4.0",
    "MIT",
    "GPL-3.0-or-later",
)

# Claves que si se comparten (lista blanca).
KDE_KEYS: tuple[tuple[str, str, str], ...] = (
    ("kdeglobals", "General", "ColorScheme"),
    ("kdeglobals", "Icons", "Theme"),
    ("kdeglobals", "General", "font"),
    ("kdeglobals", "General", "menuFont"),
    ("kdeglobals", "General", "toolBarFont"),
    ("kdeglobals", "General", "fixed"),
    ("plasmarc", "Theme", "name"),
    ("kcminputrc", "Mouse", "cursorTheme"),
    ("kwinrc", "org.kde.kdecoration2", "theme"),
)

GTK_KEYS: tuple[tuple[str, str], ...] = (
    ("~/.config/gtk-3.0/settings.ini", "gtk-theme-name"),
    ("~/.config/gtk-4.0/settings.ini", "gtk-theme-name"),
)

GNOME_KEYS = (
    "gtk-theme",
    "icon-theme",
    "cursor-theme",
    "color-scheme",
    "font-name",
    "document-font-name",
    "monospace-font-name",
    "text-scaling-factor",
)

XFCE_PROPS = (
    "/Net/ThemeName",
    "/Net/IconThemeName",
    "/Gtk/CursorThemeName",
    "/Gtk/FontName",
    "/Xft/DPI",
)

# Nunca se comparte nada que huela a ruta, usuario o historial.
_UNSAFE = re.compile(r"(^[/~])|(file:)|(\.\./)|([A-Za-z]:\\\\)")
_SLUG = re.compile(r"[^a-z0-9-]+")
# Usuario de GitHub: 1-39, alfanumerico y guiones (sin guion al principio,
# al final ni repetido). Es la identidad verificable al abrir el PR.
_HANDLE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}$")


def slug(text: str) -> str:
    """Id publicable: minusculas, numeros y guiones (3-64 caracteres)."""
    normal = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    value = _SLUG.sub("-", normal.lower()).strip("-")[:48]
    if len(value) < 3:
        value = (value + "-style").strip("-")
    return value or "perfil"


# Compatibilidad con versiones anteriores del modulo.
_slug = slug


def is_handle(value: str) -> bool:
    """True si `value` es un usuario de GitHub válido."""
    return bool(_HANDLE.fullmatch((value or "").strip()))


def safe_value(value: str) -> bool:
    """True si el valor no revela rutas ni datos locales."""
    text = value.strip()
    if not text or len(text) > 200:
        return False
    return not _UNSAFE.search(text)


@dataclass
class Profile:
    id: str
    name: str
    author: str
    license: str
    desktop: str
    description: str = ""
    palette: list[str] = field(default_factory=list)
    cover: str = ""
    requires: dict = field(default_factory=dict)
    settings: list[dict] = field(default_factory=list)
    schema: int = SCHEMA
    created: str = ""

    def to_dict(self) -> dict:
        return {
            "schema": self.schema,
            "id": self.id,
            "name": self.name,
            "author": self.author,
            "license": self.license,
            "desktop": self.desktop,
            "description": self.description,
            "created": self.created or datetime.now().date().isoformat(),
            "preview": {"cover": self.cover, "palette": self.palette},
            "requires": self.requires,
            "settings": self.settings,
        }

    @classmethod
    def from_dict(cls, raw: dict) -> "Profile":
        preview = raw.get("preview") or {}
        return cls(
            id=str(raw.get("id", "")),
            name=str(raw.get("name", "")),
            author=str(raw.get("author", "")),
            license=str(raw.get("license", "")),
            desktop=str(raw.get("desktop", "")),
            description=str(raw.get("description", "")),
            palette=list(preview.get("palette") or []),
            cover=str(preview.get("cover") or ""),
            requires=dict(raw.get("requires") or {}),
            settings=list(raw.get("settings") or []),
            schema=int(raw.get("schema", SCHEMA)),
            created=str(raw.get("created", "")),
        )


# ------------------------------------------------------------------ validacion


def validate(profile: Profile) -> list[str]:
    """Lista de problemas. Vacia = perfil publicable."""
    problems: list[str] = []

    if profile.schema != SCHEMA:
        problems.append(f"schema desconocido: {profile.schema}")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,63}", profile.id or ""):
        problems.append("id invalido (minusculas, numeros y guiones, 3-64)")
    if not profile.name.strip():
        problems.append("falta el nombre")
    if not profile.author.strip():
        problems.append("falta el autor")
    elif not is_handle(profile.author):
        problems.append(
            "autor inválido: usá tu usuario de GitHub (sin @, sin espacios)"
        )
    if profile.license not in LICENSES:
        problems.append(f"licencia no permitida: {profile.license}")
    if profile.desktop not in DESKTOPS:
        problems.append(f"escritorio desconocido: {profile.desktop}")

    for key in profile.requires:
        if key not in ("plasma_style", "color_scheme", "icons", "cursor", "gtk", "packages"):
            problems.append(f"campo desconocido en requires: {key}")

    for setting in profile.settings:
        backend = setting.get("backend")
        if backend not in ("ini", "dconf", "xfconf"):
            problems.append(f"backend desconocido: {backend}")
            continue
        value = str(setting.get("value", ""))
        if not safe_value(value):
            problems.append(f"valor sospechoso en {setting.get('key', setting.get('prop', '?'))}")

    for color in profile.palette:
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
            problems.append(f"color invalido: {color}")

    if len(profile.settings) > 80:
        problems.append("demasiados ajustes")

    return problems


# ------------------------------------------------------------------ exportar


def _text_of(store: BlobStore, manifest: Manifest, suffix: str) -> str:
    for item in manifest.items:
        if (item.source or "").endswith(suffix) and item.blob:
            try:
                return store.read(item.blob).decode("utf-8", "replace")
            except OSError:
                return ""
    return ""


def _parse_ini(text: str):
    import configparser

    parser = configparser.RawConfigParser(strict=False)
    parser.optionxform = str
    try:
        parser.read_string(text)
    except Exception:
        return None
    return parser


def _kde_settings(store: BlobStore, manifest: Manifest) -> list[dict]:
    settings: list[dict] = []
    for filename, group, key in KDE_KEYS:
        text = _text_of(store, manifest, "/" + filename)
        parser = _parse_ini(text) if text else None
        if parser is None or not parser.has_option(group, key):
            continue
        value = str(parser.get(group, key)).strip()
        if not safe_value(value):
            continue
        settings.append(
            {"backend": "ini", "file": filename, "group": group, "key": key, "value": value}
        )

    for path, key in GTK_KEYS:
        text = _text_of(store, manifest, path)
        parser = _parse_ini(text) if text else None
        if parser is None or not parser.has_option("Settings", key):
            continue
        value = str(parser.get("Settings", key)).strip()
        if safe_value(value):
            settings.append(
                {
                    "backend": "ini",
                    "file": path.rsplit("/", 2)[-2] + "/settings.ini",
                    "group": "Settings",
                    "key": key,
                    "value": value,
                }
            )
    return settings


def _dconf_settings(store: BlobStore, manifest: Manifest) -> list[dict]:
    settings: list[dict] = []
    for item in manifest.items:
        if item.kind != "dconf" or not item.blob:
            continue
        path = (item.data or {}).get("path", "")
        if path != "/org/gnome/desktop/interface/":
            continue
        try:
            text = store.read(item.blob).decode("utf-8", "replace")
        except OSError:
            continue
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("[") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            if key.strip() not in GNOME_KEYS:
                continue
            value = value.strip()
            if safe_value(value.strip("'\"")):
                settings.append(
                    {
                        "backend": "dconf",
                        "path": path,
                        "key": key.strip(),
                        "value": value,
                    }
                )
    return settings


def _xfce_settings(manifest: Manifest) -> list[dict]:
    settings: list[dict] = []
    for item in manifest.items:
        if item.kind != KIND_SETTING or item.backend != "xfconf":
            continue
        data = item.data or {}
        if data.get("channel") != "xsettings" or data.get("prop") not in XFCE_PROPS:
            continue
        value = str(data.get("value", ""))
        if safe_value(value):
            settings.append(
                {
                    "backend": "xfconf",
                    "channel": "xsettings",
                    "prop": data["prop"],
                    "type": data.get("type", "string"),
                    "value": value,
                }
            )
    return settings


def _palette_from_colors(store: BlobStore, manifest: Manifest, scheme: str) -> list[str]:
    """Colores del esquema de color del tema (nunca del wallpaper)."""
    if not scheme:
        return []
    suffix = f"/color-schemes/{scheme}.colors"
    text = _text_of(store, manifest, suffix)
    if not text:
        return []
    parser = _parse_ini(text)
    if parser is None:
        return []

    palette: list[str] = []
    for section, key in (
        ("Colors:Window", "BackgroundNormal"),
        ("Colors:View", "BackgroundNormal"),
        ("Colors:Button", "BackgroundNormal"),
        ("Colors:Selection", "BackgroundNormal"),
        ("Colors:Window", "ForegroundNormal"),
    ):
        if not parser.has_option(section, key):
            continue
        raw = str(parser.get(section, key)).strip()
        parts = raw.split(",")
        if len(parts) != 3:
            continue
        try:
            r, g, b = (max(0, min(255, int(p))) for p in parts)
        except ValueError:
            continue
        color = f"#{r:02x}{g:02x}{b:02x}"
        if color not in palette:
            palette.append(color)
    return palette[:6]


def build_profile(
    manifest: Manifest,
    store: BlobStore,
    *,
    name: str,
    author: str,
    license: str,
    description: str = "",
    include_cover: bool = False,
) -> tuple[Profile, list[str]]:
    """Devuelve (perfil, cosas que se descartaron por privacidad)."""
    dropped: list[str] = []
    themes = manifest.host.get("themes") or {}

    requires: dict = {}
    for source, target in (
        ("plasma", "plasma_style"),
        ("color_scheme", "color_scheme"),
        ("icons", "icons"),
        ("cursor", "cursor"),
        ("gtk", "gtk"),
    ):
        value = themes.get(source)
        if value and safe_value(value):
            requires[target] = value

    desktop = manifest.de if manifest.de in DESKTOPS else "other"

    if desktop == "kde":
        settings = _kde_settings(store, manifest)
    elif desktop == "gnome":
        settings = _dconf_settings(store, manifest)
    elif desktop == "xfce":
        settings = _xfce_settings(manifest)
    else:
        settings = []

    # nunca compartimos el historial de otras categorias
    descartados = len(manifest.items) - len(settings)
    if descartados > 0:
        dropped.append(f"{descartados} elementos de la copia no se comparten (archivos, rutas, historial)")

    palette = _palette_from_colors(store, manifest, str(requires.get("color_scheme", "")))

    profile = Profile(
        id=slug(name),
        name=name.strip(),
        author=author.strip(),
        license=license,
        desktop=desktop,
        description=description.strip(),
        palette=palette,
        cover="cover.png" if include_cover else "",
        requires=requires,
        settings=settings,
        created=datetime.now().date().isoformat(),
    )
    if not include_cover:
        dropped.append("la captura del escritorio no se comparte (puede tener tu fondo)")
    return profile, dropped


def default_export_dir() -> Path:
    """Carpeta visible donde la GUI deja los perfiles listos para publicar."""
    return Path.home() / "themevault-perfiles"


def output_dir(base: Path | None, profile: Profile) -> Path:
    """`<base>/<id>`: la carpeta tiene que llamarse igual que el id."""
    root = Path(base).expanduser() if base else default_export_dir()
    return root / profile.id


def export_bundle(
    profile: Profile,
    directory: Path,
    *,
    manifest: Manifest | None = None,
    store: BlobStore | None = None,
) -> Path:
    """Escribe profile.json (+ cover.png si se pidio) en `directory`."""
    problems = validate(profile)
    if problems:
        raise ValueError("perfil invalido: " + "; ".join(problems))

    directory.mkdir(parents=True, exist_ok=True)
    (directory / "profile.json").write_text(
        json.dumps(profile.to_dict(), indent=2, ensure_ascii=False)
    )

    if profile.cover and manifest is not None and store is not None:
        preview = manifest.preview or {}
        rel = str(preview.get("cover") or preview.get("screenshot") or "")
        base = store.root
        source = (base / rel) if rel else None
        if (
            source is not None
            and not Path(rel).is_absolute()
            and ".." not in Path(rel).parts
            and is_within(source, base)
            and source.is_file()
        ):
            (directory / "cover.png").write_bytes(source.read_bytes())
    return directory / "profile.json"


# ------------------------------------------------------------------- aplicar


def to_manifest(profile: Profile) -> Manifest:
    """Manifiesto sintetico para reutilizar el motor de restauracion."""
    items = [
        Item(
            kind=KIND_SETTING,
            category="theme",
            name=f"{setting.get('file', setting.get('path', setting.get('channel', '')))} {setting.get('key', setting.get('prop', ''))}",
            backend=setting["backend"],
            data=setting,
        )
        for setting in profile.settings
    ]
    return Manifest(
        id=f"profile-{profile.id}",
        created=datetime.now().astimezone().isoformat(timespec="seconds"),
        host={
            "de": profile.desktop,
            "themes": profile.requires,
            "distro": {"pretty": "Perfil de la comunidad"},
        },
        items=items,
        label=profile.name,
        notes=profile.description,
        preview={"palette": profile.palette},
    )
