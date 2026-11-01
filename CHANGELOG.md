# Historial de cambios

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).
El proyecto usa [Versionado Semántico](https://semver.org/lang/es/).

## [0.1.3] - 2026-11-01

### Agregado

- **Restaurar por pantalla (KDE Plasma)**: en el diálogo de restauración podés
  elegir qué pantalla de la copia va en qué monitor del equipo actual.
  - Mezcla el `appletsrc`: renombra containments y applets para no chocar,
    reescribe `AppletOrder` y `SystrayContainmentId`, actualiza `lastScreen` y
    la actividad vigente, y reemplaza solo lo que hoy vive en la pantalla
    destino. El resto del layout no se toca.
  - Restaura el **archivo de fondo** de cada pantalla, copiándolo a
    `~/.local/share/wallpapers/themevault/` y reescribiendo la ruta.
  - Guarda un `.bak` del layout y reinicia `plasmashell`; si no vuelve a
    levantar, revierte solo.
- `themevault revert-layout` para volver al layout anterior.
- Las pantallas del respaldo guardan sus `containments` y su fondo.

## [0.1.2] - 2026-11-01

### Corregido

- **El AppImage no capturaba el escritorio, ni los monitores, ni las barras.**
  PyInstaller deja `LD_LIBRARY_PATH` apuntando a su Qt y los procesos hijos
  (`spectacle`, `kscreen-doctor`, `qdbus6`) heredaban esa variable y abortaban
  al cargar los plugins del sistema. Ahora `util.run()` los ejecuta con un
  entorno limpio. Como consecuencia vuelven los recortes por monitor (y las
  flechas ‹ ›) y la tira de la barra de tareas.
- La captura reintenta hasta 3 veces y, si falla, guarda el motivo en
  `preview.capture_error` en lugar de quedar en silencio.
- El selector de monitor del detalle ya no muestra un contador duplicado y
  vuelve a incluir el nombre de la pantalla.

### Agregado

- `preview.screens[]` guarda, por pantalla, `custom`, `panels`, `widgets` y un
  `summary` («Panel inferior · 7 widgets», «Escritorio»).
- Se recortan todas las pantallas que Plasma administra; un monitor sin paneles
  se etiqueta como «Escritorio» en vez de descartarse.
- `themevault-gui --backup-now` crea una copia al arrancar (pruebas y CI).
- Test con clic real sobre las flechas de la tarjeta.

## [0.1.1] - 2026-11-01

### Corregido

- **El AppImage abortaba al iniciar** en sesiones donde el bundle no logra crear
  un contexto OpenGL (por ejemplo KDE Wayland con ciertos drivers): Qt moría con
  `EGL not available` → `Failed to initialize graphics backend`. Ahora el
  AppImage usa el renderizador por software, que funciona con cualquier driver.
  La aceleración sigue disponible con `QT_QUICK_BACKEND=opengl`.
- El `.desktop` interno del AppImage ahora lleva la versión real en
  `X-AppImage-Version`.

### Infraestructura

- La verificación del AppImage en CI ya no usa `offscreen`: arranca la
  aplicación en un X11 virtual (`xvfb-run`) y comprueba que el backend por
  defecto no dependa de la GPU.

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

[0.1.3]: https://github.com/TuxArchi/themevault/releases/tag/v0.1.3
[0.1.2]: https://github.com/TuxArchi/themevault/releases/tag/v0.1.2
[0.1.1]: https://github.com/TuxArchi/themevault/releases/tag/v0.1.1
[0.1.0]: https://github.com/TuxArchi/themevault/releases/tag/v0.1.0
