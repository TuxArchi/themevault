"""Perfiles compartibles de la comunidad.

Un perfil es un bundle saneado: apariencia, fondo, layout, atajos seguros y
plugins declarados. No incluye historial, tokens, configuracion interna de
shells, capturas del escritorio ni rutas personales.

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
    "niri",
    "sway",
    "river",
    "wayfire",
    "labwc",
    "cinnamon",
    "mate",
    "budgie",
    "lxqt",
    "i3",
    "openbox",
    "cosmic",
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


_SECRET_TEXT = re.compile(
    r"(?i)(token|password|passwd|secret|api[_-]?key|authorization|bearer|"
    r"ssh-|id_rsa|id_ed25519|\.ssh|\.env|file://|https?://|@[^ ]+\.[^ ]+)"
)
_KEYBIND_PATH = re.compile(r"(^|[\s\"'])(~|/|\$HOME|\.\/|\.\./)")


def safe_keybind(entry: dict) -> bool:
    """True si el atajo no contiene rutas, URLs, secretos ni scripts."""
    if entry.get("script"):
        return False
    text = " ".join(
        str(entry.get(key, ""))
        for key in ("arg", "description", "dispatcher")
    )
    if _KEYBIND_PATH.search(text) or _SECRET_TEXT.search(text):
        return False
    return safe_value(str(entry.get("combo", "")))


def safe_keybinds(entries: list[dict]) -> list[dict]:
    out: list[dict] = []
    for entry in entries:
        if not safe_keybind(entry):
            continue
        out.append(
            {
                "combo": str(entry.get("combo", "")),
                "dispatcher": str(entry.get("dispatcher", "")),
                "arg": str(entry.get("arg", "")),
                "mode": str(entry.get("mode", "")),
                "format": str(entry.get("format", "")),
                "kind": str(entry.get("kind", "")),
                "description": str(entry.get("description", "")),
                "safe": True,
            }
        )
    return out


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
    wallpaper: dict = field(default_factory=dict)
    appearance: dict = field(default_factory=dict)
    layout: dict = field(default_factory=dict)
    keybinds: list[dict] = field(default_factory=list)
    plugins: list[dict] = field(default_factory=list)
    assets: list[dict] = field(default_factory=list)
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
            "wallpaper": self.wallpaper,
            "appearance": self.appearance,
            "layout": self.layout,
            "keybinds": self.keybinds,
            "plugins": self.plugins,
            "assets": self.assets,
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
            wallpaper=dict(raw.get("wallpaper") or {}),
            appearance=dict(raw.get("appearance") or {}),
            layout=dict(raw.get("layout") or {}),
            keybinds=list(raw.get("keybinds") or []),
            plugins=list(raw.get("plugins") or []),
            assets=list(raw.get("assets") or []),
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

    # Wallpaper y recursos embebidos.
    wallpaper = profile.wallpaper or {}
    if wallpaper:
        kind = str(wallpaper.get("kind", ""))
        if kind not in ("image", "video"):
            problems.append("wallpaper: tipo inválido")
        for key in ("file", "fallback"):
            value = str(wallpaper.get(key, "") or "")
            if value and not _safe_bundle_path(value):
                problems.append(f"wallpaper: ruta inválida en {key}")
        if not re.fullmatch(r"[0-9a-f]{64}", str(wallpaper.get("sha256", ""))):
            problems.append("wallpaper: falta sha256 válido")
        try:
            if int(wallpaper.get("size") or 0) > 60 * 1024 * 1024:
                problems.append("wallpaper: archivo demasiado grande")
        except (TypeError, ValueError):
            problems.append("wallpaper: tamaño inválido")
        if kind == "video":
            try:
                if float(wallpaper.get("duration") or 0) > 10 * 60:
                    problems.append("wallpaper: video demasiado largo")
            except (TypeError, ValueError):
                problems.append("wallpaper: duración inválida")

    for plugin in profile.plugins:
        if not isinstance(plugin, dict):
            problems.append("plugin inválido")
            continue
        file = str(plugin.get("file", "") or "")
        target = str(plugin.get("target", "") or "")
        if not _safe_bundle_path(file) or Path(file).parts[0] != "plugins":
            problems.append(f"plugin: archivo inválido {file or '(vacío)'}")
        if not file.endswith((".tar.gz", ".zip")):
            problems.append("plugin: formato no permitido")
        if not target.startswith("~/"):
            problems.append(f"plugin: destino fuera del home {target or '(vacío)'}")
        if ".." in Path(target).parts:
            problems.append("plugin: destino con ..")
        if not re.fullmatch(r"[0-9a-f]{64}", str(plugin.get("sha256", ""))):
            problems.append("plugin: falta sha256 válido")

    for asset in profile.assets:
        if not isinstance(asset, dict):
            problems.append("asset inválido")
            continue
        file = str(asset.get("file", "") or "")
        url = str(asset.get("url", "") or "")
        if file:
            if not _safe_bundle_path(file) or Path(file).parts[0] != "assets":
                problems.append("asset: archivo inválido")
            if not file.endswith((".tar.gz", ".zip")):
                problems.append("asset: formato no permitido")
            target = str(asset.get("target", "") or "")
            if not target.startswith("~/"):
                problems.append("asset: destino fuera del home")
        if url and not (
            url.startswith("https://github.com/")
            or url.startswith("https://raw.githubusercontent.com/")
            or url.startswith("https://objects.githubusercontent.com/")
            or url.startswith("https://codeload.github.com/")
        ):
            problems.append("asset: URL no permitida")
        if not file and not url:
            problems.append("asset: falta archivo o URL")
        if not re.fullmatch(r"[0-9a-f]{64}", str(asset.get("sha256", ""))):
            problems.append("asset: falta sha256 válido")

    for entry in profile.keybinds:
        if not isinstance(entry, dict) or not safe_keybind(entry):
            problems.append("atajo inseguro en el perfil")

    if profile.description and (
        not safe_value(profile.description) or _SECRET_TEXT.search(profile.description)
    ):
        problems.append("descripción con ruta o dato sospechoso")
    if profile.name and not safe_value(profile.name):
        problems.append("nombre con ruta o dato sospechoso")

    return problems


def _safe_bundle_path(value: str) -> bool:
    path = Path(str(value or ""))
    if not path.parts or path.is_absolute() or ".." in path.parts:
        return False
    if path.parts[0] in ("plugins", "assets"):
        return len(path.parts) >= 2
    return path.name in (
        "wallpaper.jpg",
        "wallpaper.jpeg",
        "wallpaper.png",
        "wallpaper.webp",
        "wallpaper.mp4",
        "cover.jpg",
        "cover.png",
    )


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

    appearance = {
        "icon_theme": str(themes.get("icons", "") or requires.get("icons", "")),
        "cursor_theme": str(themes.get("cursor", "") or requires.get("cursor", "")),
        "gtk_theme": str(themes.get("gtk", "") or requires.get("gtk", "")),
        "color_scheme": str(themes.get("color_scheme", "") or requires.get("color_scheme", "")),
        "plasma_style": str(themes.get("plasma", "") or requires.get("plasma_style", "")),
    }
    appearance = {key: value for key, value in appearance.items() if value}
    keybinds = safe_keybinds(manifest.keybinds)
    layout = _safe_layout(manifest.containers, manifest.widgets)

    # nunca compartimos el historial de otras categorias
    descartados = len(manifest.items) - len(settings)
    if descartados > 0:
        dropped.append(f"{descartados} elementos de la copia no se comparten (archivos, rutas, historial)")
    if manifest.keybinds and not keybinds:
        dropped.append("los atajos se omitieron por contener rutas, comandos o datos personales")
    elif len(keybinds) < len(manifest.keybinds):
        dropped.append(f"{len(manifest.keybinds) - len(keybinds)} atajos se omitieron por privacidad")

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
        appearance=appearance,
        layout=layout,
        keybinds=keybinds,
        created=datetime.now().date().isoformat(),
    )
    if not include_cover:
        dropped.append("la captura del escritorio no se comparte (puede tener tu fondo)")
    return profile, dropped


def _safe_layout(containers: list[dict], widgets: list[dict]) -> dict:
    safe_containers = []
    for container in containers:
        safe_containers.append(
            {
                key: container.get(key)
                for key in (
                    "id",
                    "kind",
                    "name",
                    "location",
                    "screen",
                    "size",
                    "floating",
                    "visibility",
                    "alignment",
                    "length",
                    "order",
                    "widgets",
                )
                if container.get(key) not in (None, "", [])
            }
        )
    safe_widgets = []
    for widget in widgets:
        safe_widgets.append(
            {
                key: widget.get(key)
                for key in (
                    "id",
                    "name",
                    "kind",
                    "container",
                    "position",
                    "installed",
                    "hidden",
                )
                if widget.get(key) not in (None, "")
            }
        )
    return {"containers": safe_containers, "widgets": safe_widgets}


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
    include_wallpaper: bool = True,
    include_plugins: bool = True,
    include_cover: bool | None = None,
) -> Path:
    """Escribe profile.json + wallpaper + plugins en `directory`."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    if include_cover is None:
        include_cover = bool(profile.cover)

    if manifest is not None and store is not None:
        from .profile_bundle import prepare_assets, prepare_plugins, prepare_wallpaper

        if include_wallpaper:
            prepare_wallpaper(
                profile,
                manifest,
                store,
                directory,
                include_cover=include_cover,
            )
        if include_plugins:
            profile.plugins = prepare_plugins(profile, manifest, store, directory)
            profile.assets = prepare_assets(profile, manifest, store, directory)
        if include_cover and not profile.wallpaper:
            # Nunca usar una captura del escritorio como portada.
            profile.cover = ""

    problems = validate(profile)
    if problems:
        raise ValueError("perfil invalido: " + "; ".join(problems))

    (directory / "profile.json").write_text(
        json.dumps(profile.to_dict(), indent=2, ensure_ascii=False)
    )

    cover_name = profile.cover
    if cover_name and manifest is not None and store is not None:
        target = directory / cover_name
        if target.is_file():
            return directory / "profile.json"
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
            target.write_bytes(source.read_bytes())
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
