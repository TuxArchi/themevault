# Historial de cambios

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).
El proyecto usa [Versionado Semántico](https://semver.org/lang/es/).

## [0.1.0] - 2026-11-01

Primer lanzamiento público.

### Agregado

- **Core**: copias autocontenidas con `manifest.json`, blobs direccionados por
  SHA-256 y árboles empaquetados en `tar.gz` determinista (dedupe real entre
  copias del mismo tema).
- **Adaptadores**: KDE Plasma 6, GNOME y Xfce.
  - KDE: `kdeglobals`, `kwinrc`, `plasmashellrc`, layout de Plasma
    (`appletsrc`), esquemas de color, temas de Plasma, Aurorae y Kvantum.
  - GNOME: ramas de dconf (apariencia, fondo, shell, extensiones, dock
    `dash-to-dock`/`ubuntu-dock`, tema del shell) y extensiones instaladas.
  - Xfce: propiedades de `xfconf` con tipos, XML de canales y `xfce4-panel.xml`.
- **Restauración segura**: plan previo, `--dry-run`, restauración selectiva por
  categoría, punto de retorno automático y bloqueo de cualquier ruta fuera de
  `$HOME`.
- **Avisos**: temas, iconos y widgets que la copia referencia y el sistema
  destino no tiene.
- **Portada compuesta**: captura del escritorio *sin ventanas* (Show Desktop
  por D-Bus), recorte por monitor, una portada por pantalla, muestra del cursor
  (SVG de Plasma o Xcursor), muestra de iconos y paleta.
- **Multi-monitor**: detección de monitores (`kscreen-doctor` / `xrandr`),
  recortes por pantalla y selector ‹ › en la galería y en el detalle.
- **Widgets y paneles**: lista de widgets colocados, en el orden real
  (`AppletOrder`), con geometría del panel (tamaño, posición, flotante, modo de
  ocultado, largo personalizado y monitor), y tira recortada de cada barra. Las
  barras auto-ocultas se destapan un instante para poder capturarlas.
- **Interfaz gráfica** (Qt6/QML): galería de portadas, detalle con muestra del
  tema, restauración guiada y vista del sistema.
- **CLI**: `detect`, `backup`, `list`, `show`, `restore`, `delete`, `verify`,
  `rebuild`, `path` y `ui`.

### Notas

- Requiere Python 3.10 o superior.
- La captura de pantalla depende del compositor: en Wayland algunas
  herramientas devuelven una imagen negra y se detecta para usar el wallpaper.
- No se copian los temas de `/usr/share`: se registra su nombre para avisar si
  faltan en la máquina destino.

[0.1.0]: https://github.com/TuxArchi/themevault/releases/tag/v0.1.0
