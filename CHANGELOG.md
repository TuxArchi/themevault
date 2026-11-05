# Historial de cambios

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).
El proyecto usa [Versionado Semántico](https://semver.org/lang/es/).

## [0.5.0] - 2026-11-04

### Agregado

- **Soporte de Hyprland**: adaptador propio para `hyprland.conf` y sus
  `source` dentro del home, con lista blanca de archivos de configuración.
- **Atajos de teclado**: se interpretan variables, `bind*`, `unbind` y
  `submap`; se guardan en el manifest y se muestran en el detalle y la CLI.
- **Waybar**: se interpreta como barra/panel con sus módulos y se recorta su
  franja en la portada.
- **Ecosistema Hyprland**: Waybar, wofi/rofi, swaync/mako/dunst, terminales,
  qt5ct/qt6ct, Kvantum y esquemas de color.
- **Privacidad**: las copias de Hyprland no incluyen fotos, wallpapers,
  documentos, notas, scripts, claves ni historiales. Los includes externos se
  informan como omitidos.
- `--no-preview` ahora no guarda ninguna imagen: ni captura ni fondo.
- Captura de Hyprland en un workspace especial temporal para no fotografiar
  ventanas abiertas.
- Detección de monitores con `hyprctl monitors -j`.

### Cambiado

- Los archivos sueltos restaurados conservan su modo original.
- `Manifest` incluye `keybinds` de forma opcional y compatible con copias
  anteriores.

## [0.4.1] - 2026-11-01

### Cambiado

- **Nueva identidad visual**: icono de capturas apiladas, paleta turquesa
  (`#2dd4bf` → `#0891b2`) y banner para el README.
- La app usa los nuevos colores de acento (botones con texto oscuro para
  mantener el contraste) y las capturas de la documentación se regeneraron.
- Sitio: `og:image` y `og:url` absolutos, `twitter:card`, favicon `.ico`,
  `apple-touch-icon` y manifest; el icono reemplaza a la «T» del nav.

### Agregado

- `packaging/brand/build_brand.py`: genera iconos PNG/ICO, banner y social
  preview desde `docs/assets/icon.svg`.
- Iconos PNG 16→1024 y `favicon.ico`; el AppImage instala 128/256/512 en
  `hicolor` además del SVG.

## [0.4.0] - 2026-11-01

### Agregado

- **Autor verificado**: `author` es el usuario de GitHub (sin `@`), validado en
  la app, el CLI y el CI. El formulario lo prellena si `gh` está autenticado y
  avisa (sin bloquear) si no coincide.
- `publish-profile` consulta `gh api user` y aborta si el autor no es la cuenta
  de esta máquina; `--allow-author` permite las importaciones de maintainers.
- La comunidad muestra `@autor` con enlace a su perfil de GitHub.
- Repositorio de perfiles: `tools/check_author.py`, job `author` requerido,
  `MAINTAINERS`, `CODEOWNERS`, plantilla de PR y `main` protegida con los checks
  `profiles` y `author`.

### Cambiado

- Un id pertenece a quien lo publicó primero: el CI rechaza altas duplicadas y
  cambios de autor (apropiarse o transferir un perfil ajeno).
- Los validadores del CI se ejecutan desde la rama base, así un PR no puede
  editar las reglas para auto-habilitarse.

## [0.3.0] - 2026-11-01

### Agregado

- **Compartir desde la app**: botón en el detalle de una copia con nombre,
  autor, licencia y descripción. Antes de exportar muestra qué se comparte
  (ajustes, requisitos, paleta) y qué queda afuera; la portada es opcional y
  advierte que puede mostrar el fondo.
- **Aviso de id repetido**: si ya hay un perfil con ese id en la comunidad,
  sugiere uno alternativo con el autor.
- La exportación deja `<carpeta>/<id>/profile.json` listo para el repositorio,
  en lugar de una carpeta `profile-<id>` que había que renombrar.
- **`themevault publish-profile`**: valida con las mismas reglas que el CI,
  copia el perfil a un clon del repositorio, regenera `index.json` y deja los
  comandos de git; con `--pr` crea la rama, la sube y abre el pull request
  (pide confirmación).

### Corregido

- `export-profile --with-cover` no copiaba la portada: buscaba el archivo un
  directorio arriba de la copia.

## [0.2.1] - 2026-11-01

### Corregido

- **Descargas dentro del AppImage**: el OpenSSL del bundle busca los
  certificados en rutas de Debian (`/usr/lib/ssl`) que no existen en otras
  distribuciones, así que la comunidad y la tienda fallaban con
  `certificate verify failed`. Ahora se usa el almacén de CA del sistema
  (`net.ssl_context`), y `AppRun` define `SSL_CERT_FILE` si hace falta.
- La tienda de widgets tenía el mismo problema al descargar un paquete.

## [0.2.0] - 2026-11-01

### Agregado

- **Sección Comunidad** en la app: grilla de perfiles con portada, búsqueda,
  filtros por escritorio y detalle con los requisitos de cada uno.
- **Aplicar un perfil** usa el mismo motor de restauración (plan, punto de
  retorno y rollback); al terminar avisa si falta instalar algún tema.
- Cliente del índice con **caché de 24 h** y verificación del **sha256** de
  cada perfil antes de usarlo.
- Repositorio separado
  [themevault-profiles](https://github.com/TuxArchi/themevault-profiles) con
  `index.json` generado y validador de CI (esquema, rutas, tamaños).

### Notas

- Los temas e iconos no viajan en el perfil: se instalan aparte (distro o
  tienda).
- Si el índice recién cambió, el CDN de GitHub puede tardar unos minutos en
  servirlo; «Actualizar» fuerza la recarga.

## [0.1.6] - 2026-11-01

### Agregado

- **Perfiles compartibles** (fase 1 de la comunidad): `themevault export-profile`
  genera un `profile.json` a partir de una copia usando una lista blanca de
  campos.
  - Descarta rutas, historial, nombres de archivos, textos de widgets y la
    captura del escritorio (esta solo con `--with-cover`).
  - La paleta sale del **esquema de color**, nunca del wallpaper.
  - Validación de id, licencia, escritorio, valores y backends.
- **Backends `ini` y `dconf`** en el motor de ajustes: `kwriteconfig6` y
  `dconf write`, con edición directa del INI como respaldo. Necesarios para
  aplicar perfiles (y útiles para futuros ajustes finos).
- `docs/PRIVACY.md`: qué se comparte, qué no y cómo revocar un perfil.

### Notas

- La sección «Comunidad» dentro de la app y el repositorio de perfiles llegan
  en la próxima versión.

## [0.1.5] - 2026-11-01

### Agregado

- **Widgets de terceros en el respaldo**: se guardan los que instalaste en tu
  usuario (`~/.local/share/plasma/plasmoids`).
- **Instalación desde la copia**: el diálogo de restauración detecta los widgets
  que faltan y ofrece instalarlos con `kpackagetool6` (KPackage), con botón
  individual y «instalar todos». También `themevault install-widgets <id>`.
- **Tienda de widgets**: buscador integrado sobre store.kde.org usando el mismo
  proveedor que Plasma (`api.kde-look.org`), con resultados, metadatos y
  descarga + instalación desde la app. CLI: `themevault widgets search|install`.
- **Aviso de resolución**: al restaurar una pantalla en un monitor con otra
  resolución se indica que las posiciones de iconos se reacomodan.

### Notas

- La aplicación usa la red **solo** cuando buscás o instalás desde la tienda.
- Instalar un widget es ejecutar código de terceros: la app lo advierte y lo
  deja en la carpeta del usuario.

## [0.1.4] - 2026-11-01

### Corregido

- **El restore por pantalla dejaba la barra con el tamaño y el comportamiento
  por defecto.** La geometría del panel (`thickness`, `floating`,
  `panelVisibility`) no vive en el `appletsrc` sino en `plasmashellrc`,
  indexada por número de panel, y no se estaba mezclando. Ahora se copia
  renumerada al id nuevo, con su propio `.bak`, y `themevault revert-layout`
  devuelve los dos archivos.

### Notas

- Los colores e iconos son globales: en modo «por pantalla» hay que restaurar
  también *Temas* e *Iconos* si se busca el aspecto completo.

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

[0.5.0]: https://github.com/TuxArchi/themevault/releases/tag/v0.5.0
[0.4.1]: https://github.com/TuxArchi/themevault/releases/tag/v0.4.1
[0.4.0]: https://github.com/TuxArchi/themevault/releases/tag/v0.4.0
[0.3.0]: https://github.com/TuxArchi/themevault/releases/tag/v0.3.0
[0.2.1]: https://github.com/TuxArchi/themevault/releases/tag/v0.2.1
[0.2.0]: https://github.com/TuxArchi/themevault/releases/tag/v0.2.0
[0.1.6]: https://github.com/TuxArchi/themevault/releases/tag/v0.1.6
[0.1.5]: https://github.com/TuxArchi/themevault/releases/tag/v0.1.5
[0.1.4]: https://github.com/TuxArchi/themevault/releases/tag/v0.1.4
[0.1.3]: https://github.com/TuxArchi/themevault/releases/tag/v0.1.3
[0.1.2]: https://github.com/TuxArchi/themevault/releases/tag/v0.1.2
[0.1.1]: https://github.com/TuxArchi/themevault/releases/tag/v0.1.1
[0.1.0]: https://github.com/TuxArchi/themevault/releases/tag/v0.1.0
