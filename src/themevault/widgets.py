"""Widgets, paneles y barras de tareas.

No se respalda nada nuevo: la colocacion vive en archivos que la copia ya
guarda (`appletsrc`, `plasmashellrc`, `xfce4-panel.xml`, dconf del shell).
Este modulo solo interpreta esa informacion para poder mostrarla y avisar
cuando un widget no existe en la maquina destino.
"""

from __future__ import annotations

import configparser
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from .model import KIND_DCONF, Item
from .util import expand, home, run, which

# --------------------------------------------------------------------- nombres

PLASMA_NAMES = {
    "org.kde.plasma.digitalclock": "Reloj digital",
    "org.kde.plasma.kickoff": "Lanzador de aplicaciones",
    "org.kde.plasma.kicker": "Lanzador de aplicaciones",
    "org.kde.plasma.kickerdash": "Lanzador de aplicaciones",
    "org.kde.plasma.icontasks": "Gestor de tareas",
    "org.kde.plasma.taskmanager": "Gestor de tareas",
    "org.kde.plasma.pager": "Paginador de escritorios",
    "org.kde.plasma.activitypager": "Paginador de actividades",
    "org.kde.plasma.systemtray": "Bandeja del sistema",
    "org.kde.plasma.showdesktop": "Mostrar escritorio",
    "org.kde.plasma.marginsseparator": "Separador de margenes",
    "org.kde.plasma.panelspacer": "Espaciador",
    "org.kde.plasma.weather": "Clima",
    "org.kde.plasma.volume": "Volumen",
    "org.kde.plasma.battery": "Bateria",
    "org.kde.plasma.networkmanagement": "Redes",
    "org.kde.plasma.notifications": "Notificaciones",
    "org.kde.plasma.clipboard": "Portapapeles",
    "org.kde.plasma.klipper": "Portapapeles",
    "org.kde.plasma.mediacontroller": "Control multimedia",
    "org.kde.plasma.notes": "Notas",
    "org.kde.plasma.calendar": "Calendario",
    "org.kde.plasma.colorpicker": "Selector de color",
    "org.kde.plasma.keyboardlayout": "Distribucion del teclado",
    "org.kde.plasma.lock_logout": "Bloquear / cerrar sesion",
    "org.kde.plasma.minimizeall": "Minimizar todo",
    "org.kde.plasma.systemmonitor": "Monitor del sistema",
    "org.kde.plasma.windowlist": "Lista de ventanas",
    "org.kde.plasma.userswitcher": "Cambio de usuario",
    "org.kde.plasma.quicklaunch": "Lanzamiento rapido",
    "org.kde.plasma.trash": "Papelera",
    "org.kde.plasma.vault": "Boveda",
    "org.kde.plasma.devicenotifier": "Dispositivos",
    "org.kde.plasma.brightness": "Brillo",
    "org.kde.plasma.mpris2": "Reproductor multimedia",
}

XFCE_NAMES = {
    "clock": "Reloj",
    "systray": "Bandeja del sistema",
    "launcher": "Lanzador",
    "tasklist": "Lista de tareas",
    "applicationsmenu": "Menu de aplicaciones",
    "workspace": "Areas de trabajo",
    "separator": "Separador",
    "pager": "Paginador",
    "showdesktop": "Mostrar escritorio",
    "windowbuttons": "Botones de ventana",
    "notification-plugin": "Notificaciones",
    "power-manager-plugin": "Energia",
    "pulseaudio": "Audio",
    "weather": "Clima",
    "screenshooter": "Captura de pantalla",
    "directorymenu": "Menu de carpetas",
    "actions": "Acciones",
    "removable": "Dispositivos",
    "smartbookmark": "Marcadores",
    "xfce4-clipman-plugin": "Portapapeles",
}

WAYBAR_NAMES = {
    "clock": "Reloj",
    "battery": "Batería",
    "cpu": "CPU",
    "memory": "Memoria",
    "temperature": "Temperatura",
    "backlight": "Brillo",
    "network": "Red",
    "pulseaudio": "Audio",
    "wireplumber": "Audio",
    "tray": "Bandeja del sistema",
    "idle_inhibitor": "Inhibir reposo",
    "workspaces": "Áreas de trabajo",
    "hyprland/workspaces": "Áreas de trabajo",
    "hyprland/window": "Ventana",
    "hyprland/language": "Idioma",
    "hyprland/submap": "Submapa",
    "sway/workspaces": "Áreas de trabajo",
    "sway/window": "Ventana",
    "wlr/taskbar": "Barra de tareas",
    "mpd": "Reproductor",
    "mpris": "Reproductor",
    "custom/media": "Multimedia",
}

EXTENSION_PREFIXES = {
    "dash-to-dock": "Dash to Dock",
    "ubuntu-dock": "Ubuntu Dock",
    "dash-to-panel": "Dash to Panel",
    "appindicatorsupport": "Indicadores de aplicaciones",
    "user-theme": "Tema de usuario",
    "arcmenu": "ArcMenu",
    "blur-my-shell": "Blur my Shell",
    "clipboard-indicator": "Portapapeles",
    "just-perfection": "Just Perfection",
    "workspace-indicator": "Indicador de areas de trabajo",
}

# Ubicaciones de Plasma (Plasma::Types::Location)
PLASMA_LOCATION = {
    0: "flotante",
    1: "escritorio",
    2: "pantalla completa",
    3: "superior",
    4: "inferior",
    5: "izquierda",
    6: "derecha",
}

# Plasma::Types::Visibility
PLASMA_VISIBILITY = {
    0: "siempre visible",
    1: "ocultar automaticamente",
    2: "esquivar ventanas",
    3: "ocultar con ventanas",
    4: "dejar que las ventanas cubran",
}

PLASMOID_DIRS = (
    "~/.local/share/plasma/plasmoids",
    "/usr/share/plasma/plasmoids",
    "/usr/local/share/plasma/plasmoids",
)

APPLET_LIB_DIRS = (
    "/usr/lib/qt6/plugins/plasma/applets",
    "/usr/lib64/qt6/plugins/plasma/applets",
    "/usr/lib/x86_64-linux-gnu/qt6/plugins/plasma/applets",
    "/usr/local/lib/qt6/plugins/plasma/applets",
)

XFCE_PLUGIN_DIRS = (
    "/usr/lib/xfce4/panel/plugins",
    "/usr/lib64/xfce4/panel/plugins",
    "/usr/lib/x86_64-linux-gnu/xfce4/panel/plugins",
)

APPLETSRC = "plasma-org.kde.plasma.desktop-appletsrc"
PLASMASHELLRC = "plasmashellrc"
XFCE_PANEL_XML = "xfce4-panel.xml"


def _humanize(identifier: str) -> str:
    tail = identifier.rsplit(".", 1)[-1]
    tail = re.sub(r"[_-]+", " ", tail).strip()
    return tail[:1].upper() + tail[1:] if tail else identifier


def _ini(text: str) -> configparser.RawConfigParser:
    parser = configparser.RawConfigParser(strict=False)
    parser.optionxform = str  # respeta mayusculas (AppletOrder)
    parser.read_string(text)
    return parser


def _split_order(raw: str) -> list[str]:
    return [part.strip() for part in re.split(r"[;,]", raw or "") if part.strip()]


# ------------------------------------------------------------------------ KDE


def is_widget_installed(applet_id: str) -> bool:
    """Si el plugin existe ahora mismo en este sistema."""
    return _applet_installed(applet_id)


def _applet_installed(applet_id: str) -> bool:
    for raw in PLASMOID_DIRS:
        if (expand(raw) / applet_id).is_dir():
            return True
    for raw in APPLET_LIB_DIRS:
        base = Path(raw)
        if (base / f"{applet_id}.so").exists() or (base / applet_id).is_dir():
            return True
    return False


def _applet_name(applet_id: str) -> str:
    for raw in PLASMOID_DIRS:
        meta = expand(raw) / applet_id / "metadata.json"
        if not meta.is_file():
            continue
        try:
            data = json.loads(meta.read_text())
        except (OSError, ValueError):
            break
        plugin_info = data.get("KPlugin") or {}
        name = plugin_info.get("Name[es]") or plugin_info.get("Name")
        if name:
            return str(name)
        break
    return PLASMA_NAMES.get(applet_id, _humanize(applet_id))


def _parse_plasmashellrc(text: str) -> dict[int, dict]:
    """{numero_de_panel: {thickness, floating, panelVisibility}}"""
    if not text.strip():
        return {}
    parser = _ini(text)
    panels: dict[int, dict] = {}
    for section in parser.sections():
        match = re.fullmatch(r"PlasmaViews\]\[Panel (\d+)$", section)
        if match:
            panels.setdefault(int(match.group(1)), {}).update(dict(parser.items(section)))
            continue
        match = re.fullmatch(r"PlasmaViews\]\[Panel (\d+)\]\[Defaults$", section)
        if match:
            panels.setdefault(int(match.group(1)), {}).update(dict(parser.items(section)))
    return panels


def parse_plasma(appletsrc: str, plasmashellrc: str = "") -> tuple[list[dict], list[dict]]:
    """Devuelve (contenedores, widgets) de Plasma 5/6."""
    parser = _ini(appletsrc)
    shell = _parse_plasmashellrc(plasmashellrc)

    # --- 1) contenedores crudos -------------------------------------------
    raw: list[dict] = []
    for section in parser.sections():
        match = re.fullmatch(r"Containments\]\[(\d+)$", section)
        if not match:
            continue
        containment_id = match.group(1)
        values = dict(parser.items(section))
        plugin = values.get("plugin", "")
        if plugin == "org.kde.panel":
            kind = "panel"
        elif plugin in ("org.kde.plasma.folder", "org.kde.desktopcontainment"):
            kind = "desktop"
        else:
            kind = "other"

        general = f"Containments][{containment_id}][General"
        order = []
        if parser.has_section(general):
            order = _split_order(dict(parser.items(general)).get("AppletOrder", ""))

        raw.append(
            {
                "id": containment_id,
                "kind": kind,
                "plugin": plugin,
                "values": values,
                "order": order,
                "extra": shell.get(int(containment_id), {}),
            }
        )

    # --- 2) nombres (y numeracion de escritorios) --------------------------
    desktops = [c for c in raw if c["kind"] == "desktop"]
    for index, container in enumerate(desktops, start=1):
        container["name"] = "Escritorio" if len(desktops) == 1 else f"Escritorio {index}"
        container["location"] = ""

    for container in raw:
        if "name" in container:
            continue
        location_code = _as_int(container["values"].get("location"))
        location = PLASMA_LOCATION.get(location_code, "")
        container["location"] = location
        if container["kind"] == "panel":
            container["name"] = f"Panel {location}".strip() if location else "Panel"
        else:
            container["name"] = _humanize(container["plugin"]) if container["plugin"] else (
                f"Contenedor {container['id']}"
            )

    names = {c["id"]: c["name"] for c in raw}

    # --- 3) widgets --------------------------------------------------------
    applets: dict[str, list[str]] = {}
    for section in parser.sections():
        match = re.fullmatch(r"Containments\]\[(\d+)\]\[Applets\]\[(\d+)$", section)
        if match:
            applets.setdefault(match.group(1), []).append(match.group(2))

    hidden: set[tuple[str, str]] = set()
    for section in parser.sections():
        match = re.fullmatch(
            r"Containments\]\[(\d+)\]\[Applets\]\[(\d+)\]\[Configuration\]\[General$",
            section,
        )
        if match:
            if dict(parser.items(section)).get("hidden", "").lower() in ("true", "1"):
                hidden.add((match.group(1), match.group(2)))

    widgets: list[dict] = []
    for container in raw:
        listed = container["order"] or sorted(applets.get(container["id"], []), key=int)
        for position, applet_id in enumerate(listed, start=1):
            if applet_id not in applets.get(container["id"], []):
                continue
            plugin = plugin_for(parser, container["id"], applet_id)
            if not plugin:
                continue
            widgets.append(
                {
                    "id": plugin,
                    "name": _applet_name(plugin),
                    "kind": "plasmoid",
                    "container": names[container["id"]],
                    "position": position,
                    "installed": _applet_installed(plugin),
                    "hidden": (container["id"], applet_id) in hidden,
                }
            )

    # --- 4) contenedores publicables --------------------------------------
    containers: list[dict] = []
    for container in raw:
        values = container["values"]
        extra = container["extra"]
        thickness = extra.get("thickness") or values.get("thickness")
        containers.append(
            {
                "id": container["id"],
                "kind": container["kind"],
                "name": container["name"],
                "location": container["location"],
                "screen": _as_int(values.get("lastScreen")) or 0,
                "size": _as_int(thickness),
                "floating": str(extra.get("floating", values.get("floating", ""))).lower()
                in ("1", "true"),
                "visibility": PLASMA_VISIBILITY.get(_as_int(extra.get("panelVisibility")), ""),
                "alignment": _alignment(values.get("alignment")),
                "length": _length_mode(values.get("lengthMode")),
                "order": container["order"],
                "widgets": sum(1 for w in widgets if w["container"] == container["name"]),
            }
        )

    containers.sort(key=lambda c: (c["kind"] != "panel", _safe_int(c["id"])))
    return containers, widgets


def plugin_for(parser: configparser.RawConfigParser, containment: str, applet: str) -> str:
    section = f"Containments][{containment}][Applets][{applet}"
    if parser.has_section(section):
        return dict(parser.items(section)).get("plugin", "")
    return ""


def _as_int(value) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(str(value).strip())
    except ValueError:
        return None


def _safe_int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _alignment(raw) -> str:
    # Qt::Alignment: 1 = izquierda, 2 = derecha, 4/128 = centro
    code = _as_int(raw)
    return {1: "izquierda", 2: "derecha", 4: "centro", 128: "centro", 132: "centro"}.get(
        code, "centro"
    )


def _length_mode(raw) -> str:
    return {0: "completo", 1: "ajustado", 2: "personalizado"}.get(_as_int(raw), "completo")


# ----------------------------------------------------------------------- XFCE


def _prop(node: ET.Element, name: str) -> ET.Element | None:
    for child in node.findall("property"):
        if child.get("name") == name:
            return child
    return None


def parse_xfce(xml_text: str) -> tuple[list[dict], list[dict]]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return [], []

    plugins_node = _prop(root, "plugins")
    plugin_names: dict[str, str] = {}
    if plugins_node is not None:
        for child in plugins_node.findall("property"):
            if child.get("name", "").startswith("plugin-"):
                plugin_names[child.get("name")] = child.get("value", "")

    panels_node = _prop(root, "panels")
    containers: list[dict] = []
    widgets: list[dict] = []
    if panels_node is None:
        return [], []

    for panel in panels_node.findall("property"):
        panel_id = panel.get("name", "")
        if not panel_id.startswith("panel-"):
            continue
        props = {p.get("name"): p for p in panel.findall("property")}
        size = _as_int(props["size"].get("value")) if "size" in props else None
        name = f"Panel {panel_id.replace('panel-', '')}"

        ids_node = props.get("plugin-ids")
        ids: list[str] = []
        if ids_node is not None:
            ids = [p.get("value", "") for p in ids_node.findall("property")]

        for index, plugin_ref in enumerate(ids, start=1):
            plugin_id = plugin_names.get(f"plugin-{plugin_ref}", "")
            if not plugin_id:
                continue
            widgets.append(
                {
                    "id": plugin_id,
                    "name": XFCE_NAMES.get(plugin_id, _humanize(plugin_id)),
                    "kind": "xfce-plugin",
                    "container": name,
                    "position": index,
                    "installed": _xfce_installed(plugin_id),
                    "hidden": False,
                }
            )

        containers.append(
            {
                "id": panel_id,
                "kind": "panel",
                "name": name,
                "location": "",
                "position_raw": props["position"].get("value", "") if "position" in props else "",
                "size": size,
                "floating": False,
                "visibility": "ocultar automaticamente"
                if ("autohide" in props and props["autohide"].get("value") == "true")
                else "siempre visible",
                "alignment": "",
                "length": _xfce_length(props),
                "order": ids,
                "widgets": sum(1 for w in widgets if w["container"] == name),
            }
        )

    return containers, widgets


def _xfce_length(props: dict) -> str:
    if "length" not in props:
        return "completo"
    value = props["length"].get("value", "")
    return "completo" if value in ("", "100") else f"{value}%"


def _xfce_installed(plugin_id: str) -> bool:
    for raw in XFCE_PLUGIN_DIRS:
        if (Path(raw) / f"{plugin_id}.so").exists():
            return True
    return (expand("~/.local/share/xfce4/panel/plugins") / plugin_id).is_dir()


# ---------------------------------------------------------------------- GNOME


def parse_gnome(dumps: dict[str, str]) -> tuple[list[dict], list[dict]]:
    """`dumps` = {ruta de dconf: volcado de texto}."""
    shell = dumps.get("/org/gnome/shell/", "")
    enabled = _gnome_list(shell, "enabled-extensions")

    containers: list[dict] = []
    widgets: list[dict] = []

    # La barra superior de GNOME siempre existe y no es configurable en tamaño;
    # se asume el alto tipico para poder recortarla de la captura.
    if shell.strip():
        containers.append(
            {
                "id": "shell",
                "kind": "panel",
                "name": "Barra superior",
                "location": "superior",
                "size": 40,
                "floating": False,
                "visibility": "siempre visible",
                "alignment": "centro",
                "length": "completo",
                "order": enabled,
                "widgets": len(enabled),
            }
        )

        for index, uuid in enumerate(enabled, start=1):
            widgets.append(
                {
                    "id": uuid,
                    "name": _extension_name(uuid),
                    "kind": "extension",
                    "container": "Barra superior",
                    "position": index,
                    "installed": (expand("~/.local/share/gnome-shell/extensions") / uuid).is_dir()
                    or (Path("/usr/share/gnome-shell/extensions") / uuid).is_dir(),
                    "hidden": False,
                }
            )

    dock_dump = dumps.get("/org/gnome/shell/extensions/dash-to-dock/", "")
    dock_kind = "dash-to-dock"
    if not dock_dump:
        dock_dump = dumps.get("/org/gnome/shell/extensions/ubuntu-dock/", "")
        dock_kind = "ubuntu-dock"
    if dock_dump:
        entries = dict(
            line.split("=", 1)
            for line in dock_dump.splitlines()
            if "=" in line and not line.startswith("[")
        )
        values = {key.strip(): value.strip().strip("'\"") for key, value in entries.items()}
        position = values.get("dock-position", "")

        settings = [
            {
                "label": "Posicion",
                "value": {
                    "LEFT": "izquierda",
                    "RIGHT": "derecha",
                    "BOTTOM": "inferior",
                    "TOP": "superior",
                }.get(position, position.lower() or "inferior"),
            }
        ]
        if values.get("dash-max-icon-size"):
            settings.append({"label": "Iconos", "value": f"{values['dash-max-icon-size']} px"})
        settings.append(
            {
                "label": "Auto-ocultar",
                "value": "si" if values.get("autohide") == "true" else "no",
            }
        )
        settings.append(
            {"label": "Fijo", "value": "si" if values.get("dock-fixed") == "true" else "no"}
        )

        containers.append(
            {
                "id": "dock",
                "kind": "dock",
                "name": "Dock",
                "location": {
                    "LEFT": "izquierda",
                    "RIGHT": "derecha",
                    "BOTTOM": "inferior",
                    "TOP": "superior",
                }.get(position, "inferior"),
                "size": _as_int(values.get("dash-max-icon-size", "")),
                "floating": values.get("dock-fixed") == "false",
                "visibility": "ocultar automaticamente"
                if values.get("autohide") == "true"
                else "siempre visible",
                "alignment": "centro",
                "length": "completo",
                "order": [],
                "widgets": 0,
                "settings": settings,
                "theme": dock_kind,
            }
        )

    return containers, widgets


def _gnome_list(text: str, key: str) -> list[str]:
    match = re.search(rf"^{key}=(.*)$", text, re.MULTILINE)
    if not match:
        return []
    return re.findall(r"'([^']+)'", match.group(1))


def _extension_name(uuid: str) -> str:
    tail = uuid.split("@")[0]
    for prefix, name in EXTENSION_PREFIXES.items():
        if tail.startswith(prefix):
            return name
    return _humanize(tail)


# ---------------------------------------------------------------------- WAYBAR


def _strip_jsonc(text: str) -> str:
    """Quita comentarios y comas finales de un JSONC de Waybar."""
    output: list[str] = []
    index = 0
    in_string = False
    escaped = False
    length = len(text)

    while index < length:
        char = text[index]
        if in_string:
            output.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue

        if char == '"':
            in_string = True
            output.append(char)
            index += 1
            continue
        if char == "/" and index + 1 < length and text[index + 1] == "/":
            while index < length and text[index] not in "\r\n":
                index += 1
            continue
        if char == "/" and index + 1 < length and text[index + 1] == "*":
            index += 2
            while index + 1 < length and not (text[index] == "*" and text[index + 1] == "/"):
                index += 1
            index += 2
            continue

        output.append(char)
        index += 1

    return re.sub(r",\s*([}\]])", r"\1", "".join(output))


def _waybar_name(module: str) -> str:
    if module in WAYBAR_NAMES:
        return WAYBAR_NAMES[module]
    if module.startswith("custom/"):
        return "Personalizado: " + _humanize(module.split("/", 1)[1])
    if module.startswith("group/"):
        return "Grupo: " + _humanize(module.split("/", 1)[1])
    if module.startswith("hyprland/"):
        return _humanize(module.split("/", 1)[1])
    return _humanize(module)


def parse_waybar(text: str) -> tuple[list[dict], list[dict]]:
    """Devuelve (contenedores, widgets) de una configuración de Waybar."""
    try:
        data = json.loads(_strip_jsonc(text))
    except (ValueError, TypeError):
        return [], []
    if isinstance(data, list):
        data = next((item for item in data if isinstance(item, dict)), {})
    if not isinstance(data, dict):
        return [], []

    positions = {
        "top": "superior",
        "bottom": "inferior",
        "left": "izquierda",
        "right": "derecha",
    }
    raw_position = str(data.get("position") or "top").lower()
    location = positions.get(raw_position, "superior")
    height = _as_int(data.get("height"))
    width = _as_int(data.get("width"))
    size = width if raw_position in ("left", "right") else height

    modules: list[str] = []
    for key in ("modules-left", "modules-center", "modules-right"):
        values = data.get(key) or []
        if isinstance(values, list):
            for value in values:
                module = str(value).strip()
                if module and module not in modules:
                    modules.append(module)

    widgets: list[dict] = []
    for position, module in enumerate(modules, start=1):
        widgets.append(
            {
                "id": module,
                "name": _waybar_name(module),
                "kind": "waybar-module",
                "container": "Waybar",
                "position": position,
                "installed": True,
                "hidden": False,
            }
        )

    settings: list[dict] = [{"label": "Posición", "value": location}]
    if data.get("layer"):
        settings.append({"label": "Capa", "value": str(data["layer"])})
    if data.get("spacing") is not None:
        settings.append({"label": "Separación", "value": f"{data['spacing']} px"})
    if data.get("margin"):
        settings.append({"label": "Margen", "value": str(data["margin"])})

    containers = [
        {
            "id": "waybar",
            "kind": "panel",
            "name": "Waybar",
            "location": location,
            "screen": 0,
            "size": size,
            "floating": False,
            "visibility": "siempre visible",
            "alignment": "centro",
            "length": "completo",
            "order": modules,
            "widgets": len(widgets),
            "settings": settings,
            "theme": "waybar",
        }
    ]
    return containers, widgets


# ----------------------------------------------------------------------- SWAY


def parse_sway_bar(text: str) -> tuple[list[dict], list[dict]]:
    from .sway import parse_bar

    containers: list[dict] = []
    for index, raw in enumerate(parse_bar(text), start=1):
        location = {
            "top": "superior",
            "bottom": "inferior",
            "left": "izquierda",
            "right": "derecha",
        }.get(str(raw.get("position") or "bottom").lower(), "inferior")
        settings = [
            {"label": "Posición", "value": location},
            {"label": "Modo", "value": str(raw.get("mode") or "dock")},
        ]
        if raw.get("status_command"):
            settings.append({"label": "Estado", "value": str(raw["status_command"])})
        containers.append(
            {
                "id": f"sway-bar-{index}",
                "kind": "panel",
                "name": "Barra de Sway" if index == 1 else f"Barra de Sway {index}",
                "location": location,
                "screen": 0,
                "size": raw.get("height"),
                "floating": False,
                "visibility": "ocultar automaticamente"
                if str(raw.get("mode") or "").lower() == "hide"
                else "siempre visible",
                "alignment": "centro",
                "length": "completo",
                "order": [],
                "widgets": 0,
                "settings": settings,
            }
        )
    return containers, []


# ------------------------------------------------------------------ agregador


def from_items(items: list[Item], store) -> dict:
    """Deriva contenedores y widgets de los blobs que ya tiene la copia."""
    containers: list[dict] = []
    widgets: list[dict] = []
    dumps: dict[str, str] = {}

    def read(item: Item) -> str:
        try:
            return store.read(item.blob).decode("utf-8", "replace")
        except (OSError, UnicodeDecodeError):
            return ""

    appletsrc = plasmashellrc = xfce_panel = waybar_config = sway_config = ""
    for item in items:
        if not item.blob:
            continue
        source = item.source or ""
        if item.kind == KIND_DCONF:
            path = (item.data or {}).get("path")
            if path:
                dumps[path] = read(item)
            continue
        if source.endswith(APPLETSRC):
            appletsrc = read(item)
        elif source.endswith("/" + PLASMASHELLRC):
            plasmashellrc = read(item)
        elif source.endswith(XFCE_PANEL_XML):
            xfce_panel = read(item)
        elif source.endswith("/waybar/config") or source.endswith("/waybar/config.jsonc"):
            waybar_config = read(item)
        elif (item.meta or {}).get("waybar_config"):
            waybar_config = read(item)
        elif source.endswith("/sway/config"):
            sway_config = read(item)

    if appletsrc:
        containers, widgets = parse_plasma(appletsrc, plasmashellrc)
    elif xfce_panel:
        containers, widgets = parse_xfce(xfce_panel)
    elif waybar_config:
        containers, widgets = parse_waybar(waybar_config)
    elif sway_config:
        containers, widgets = parse_sway_bar(sway_config)
    elif dumps:
        containers, widgets = parse_gnome(dumps)

    return {"containers": containers, "widgets": widgets}


def missing(widgets: list[dict]) -> list[str]:
    return [w["name"] for w in widgets if not w.get("installed", True)]


def container_summary(container: dict) -> str:
    """Texto corto con la geometria: '46 px · flotante · esquivar ventanas · 7 widgets'."""
    parts: list[str] = []
    for item in container.get("settings") or []:
        parts.append(f"{item.get('label', '')}: {item.get('value', '')}".strip(": "))
    if container.get("size"):
        parts.append(f"{container['size']} px")
    if container.get("floating"):
        parts.append("flotante")
    if container.get("visibility"):
        parts.append(container["visibility"])
    count = container.get("widgets", 0)
    if count:
        parts.append(f"{count} widget" + ("" if count == 1 else "s"))
    return " · ".join(parts)


def grouped(containers: list[dict], widgets: list[dict]) -> list[dict]:
    """Contenedores con sus widgets adentro, listos para la vista."""
    out: list[dict] = []
    for container in containers:
        entry = dict(container)
        entry["summary"] = container_summary(container)
        entry["items"] = [w for w in widgets if w.get("container") == container.get("name")]
        if not entry["items"] and not entry.get("settings"):
            continue  # un escritorio vacio no aporta nada
        out.append(entry)

    known = {c.get("name") for c in containers}
    orphans = [w for w in widgets if w.get("container") not in known]
    if orphans:
        out.append(
            {
                "id": "otros",
                "kind": "other",
                "name": "Otros",
                "location": "",
                "size": None,
                "floating": False,
                "visibility": "",
                "alignment": "",
                "length": "",
                "order": [],
                "widgets": len(orphans),
                "summary": container_summary({"widgets": len(orphans)}),
                "items": orphans,
            }
        )
    return out


# ------------------------------------------------- geometria real (Plasma vivo)


def plasma_live() -> dict[str, dict]:
    """Geometria exacta de las barras segun plasmashell.

    El .config dice donde esta la barra, pero no cuanto mide si el usuario la
    personalizo. Este script devuelve location/offset/length/lengthMode.
    """
    tool = which("qdbus6", "qdbus")
    if tool is None:
        return {}

    script = (
        "var ps=panels();"
        "for (var i=0;i<ps.length;i++){var p=ps[i];"
        "print('#'+p.id+'|'+p.location+'|'+p.height+'|'+p.offset+'|'+p.length+'|'"
        "+p.lengthMode+'|'+p.floating+'|'+p.screen+'|'+p.hiding);}"
    )
    proc = run(
        [
            tool,
            "org.kde.plasmashell",
            "/PlasmaShell",
            "org.kde.PlasmaShell.evaluateScript",
            script,
        ],
        timeout=10,
    )
    if proc is None or proc.returncode != 0:
        return {}

    found: dict[str, dict] = {}
    for chunk in proc.stdout.decode("utf-8", "replace").split("#"):
        parts = chunk.strip().split("|")
        if len(parts) < 9:
            continue
        panel_id, location, height, offset, length, length_mode, floating, screen, hiding = parts[:9]
        found[panel_id] = {
            "location": location,
            "size": _as_int(height),
            "offset": _as_int(offset),
            "length": _as_int(length),
            "length_mode": length_mode,
            "floating": str(floating).lower() in ("true", "1"),
            "screen": _as_int(screen) or 0,
            "hiding": hiding,
        }
    return found


def _script(*lines: str) -> str:
    return "".join(lines)


def reveal_hidden_panels() -> list[int]:
    """Destapa las barras en auto-ocultar para poder capturarlas.

    Devuelve los ids que se modificaron, para volver a ocultarlas despues.
    """
    tool = which("qdbus6", "qdbus")
    if tool is None:
        return []

    script = _script(
        "var ps=panels(); var out=[];",
        "for (var i=0;i<ps.length;i++){var p=ps[i];",
        "if (p.hiding=='autohide'){ out.push(p.id); p.hiding='none'; }}",
        "print(out.join(','));",
    )
    proc = run(
        [tool, "org.kde.plasmashell", "/PlasmaShell",
         "org.kde.PlasmaShell.evaluateScript", script],
        timeout=10,
    )
    if proc is None or proc.returncode != 0:
        return []
    raw = proc.stdout.decode("utf-8", "replace").strip()
    return [int(part) for part in raw.split(",") if part.strip().isdigit()]


def restore_hidden_panels(ids: list[int]) -> None:
    if not ids:
        return
    tool = which("qdbus6", "qdbus")
    if tool is None:
        return
    listing = ",".join(str(int(i)) for i in ids if isinstance(i, int))
    if not listing:
        return
    script = _script(
        f"var ids=[{listing}]; var ps=panels();",
        "for (var i=0;i<ps.length;i++){var p=ps[i];",
        "if (ids.indexOf(p.id)>=0){ p.hiding='autohide'; }}",
    )
    run(
        [tool, "org.kde.plasmashell", "/PlasmaShell",
         "org.kde.PlasmaShell.evaluateScript", script],
        timeout=10,
    )


def enrich_containers(containers: list[dict]) -> list[dict]:
    """Completa los contenedores con la geometria real del shell."""
    live = plasma_live()
    if not live:
        return containers
    for container in containers:
        found = live.get(str(container.get("id")))
        if not found:
            continue
        for key, value in found.items():
            if value not in (None, ""):
                container[key] = value
    return containers
