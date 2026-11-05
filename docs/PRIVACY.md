# Privacidad y perfiles compartidos

ThemeVault **no sube nada por su cuenta**. Una copia guardada vive en tu equipo
y solo sale de ahí si vos exportás un perfil y lo publicás a mano.

## Dos cosas distintas

| | Copia local | Perfil / copia saneada |
|---|---|---|
| Dónde vive | `~/.local/share/themevault/backups/` | la carpeta que exportás |
| Qué contiene | **todo** lo necesario para restaurar, incluida la captura y las rutas | solo la lista blanca |
| Para qué sirve | restaurar tu escritorio | compartir o publicar |
| Datos personales | **puede tenerlos** | se eliminan o se omiten |

La copia local es **completa** por decisión de diseño. Antes de compartir una
carpeta cruda, la app te muestra qué contiene:

- `themevault audit <id>` o el botón **Auditar** en el detalle;
- `themevault export-sanitized <id>` genera una copia limpia sin tocar la
  original (sin imágenes, historial, shells, configuración privada de applets
  ni atajos inseguros).

## Qué contiene un perfil

Un perfil es un **bundle saneado**, generado con una **lista blanca** de
campos:

| Se comparte | Ejemplo |
|---|---|
| Nombre, autor, licencia, escritorio | `"Catppuccin Mocha"`, `@tuxarchi`, `CC-BY-SA-4.0`, `kde` |
| Nombres de tema | `icons: Papirus-Dark`, `cursor: Breeze` |
| Apariencia | colores, bordes, gaps, fuentes, temas |
| Fondo | imagen o video, **solo si lo activás** |
| Layout | paneles, posiciones y widgets aplicados |
| Atajos seguros | solo combinaciones sin rutas, URLs, secretos ni scripts |
| Plugins de terceros | código declarado, con hash y licencia |
| Paleta | derivada del esquema de color |
| Portada | generada desde el fondo, no desde una captura |

## Qué **nunca** se incluye

- Rutas absolutas, `~`, nombres de usuario o hostname.
- Captura del escritorio o ventanas abiertas.
- Historial de comandos, apps favoritas, tokens, cuentas o emails.
- Configuración interna de shells (Noctalia, DMS, Quickshell, AGS).
- Scripts personales, `exec`, autostart o reglas de ventanas.
- Atajos con rutas, URLs, secretos o scripts.
- Configuración privada de widgets (notas, calendarios, feeds).
- Archivos de temas/iconos/cursor salvo que se declaren explícitamente con
  licencia y hash.

## Cómo se publica

1. Desde el detalle de una copia, **Compartir…** (o `themevault
   export-profile` en la terminal) genera `profile.json`, el fondo, la portada
   y los plugins declarados.
2. La app muestra **qué se comparte y qué se descarta** antes de exportar;
   podés activar o desactivar fondo, plugins/assets, atajos y layout. La
   portada es un switch aparte y solo se genera desde el fondo.
3. Si el fondo es un video, se re-encodea con ffmpeg sin audio ni metadatos y
   se limita a 10 minutos / 50 MB.
4. **Vos revisás el archivo** antes de nada.
5. Lo enviás como pull request al repositorio de perfiles. `themevault
   publish-profile` valida, copia al clon y regenera el índice; con `--pr`
   abre el pull request (siempre con confirmación).
   El `author` tiene que ser **tu usuario de GitHub** y coincidir con la cuenta
   que abre el PR; el CI lo verifica y bloquea que se publique o edite un
   perfil ajeno.
6. Un validador automático rechaza rutas, scripts de instalación, campos
   desconocidos, hashes inválidos y tamaños excesivos. Los plugins/binarios
   declarados se revisan aparte y requieren confirmación al aplicarse.

Sin ese paso manual no hay publicación. La aplicación nunca abre una conexión
para subir datos.

Al abrir **Compartir…**, si tenés `gh` instalado, la app le pregunta cuál es tu
usuario para prellenar el campo (una consulta a `api.github.com`). No envía el
perfil ni ningún dato tuyo: la publicación sigue siendo manual.

## Qué guarda la app en tu equipo

| Ruta | Contenido |
|---|---|
| `~/.local/share/themevault/backups/` | tus copias (configuración y archivos) |
| `~/.local/share/themevault/wallpapers/` | fondos aplicados desde perfiles de comunidad |
| `~/.cache/themevault/thumbs/` | miniaturas |
| `~/.cache/themevault/assets/` | iconos y cursores rasterizados |
| `~/.cache/themevault/community.json` | índice de perfiles (fase 2) |

Todo es local y se puede borrar sin afectar al sistema. `themevault cache clean`
borra el índice de la comunidad y los clones temporales.

### Escritorios y compositores

Las copias de Hyprland, niri, Sway, River, Wayfire, labwc, Cinnamon, MATE,
Budgie, LXQt, i3, Openbox y COSMIC incluyen **solo configuración** de una lista
blanca: el archivo principal, sus includes dentro de `$HOME`, ajustes de
apariencia, atajos, Waybar, Noctalia, DankMaterialShell, Quickshell, AGS,
lanzadores, notificaciones, terminales y estilos Qt/GTK.

Nunca se copian como archivos restaurables:

- fotos, wallpapers, videos, audio ni PDFs;
- documentos, notas ni historiales;
- scripts (`*.sh`, `*.py`, `*.lua`, binarios), salvo los archivos de arranque
  oficiales de River (`init`), labwc (`autostart`) y Openbox (`autostart`);
- claves SSH/GPG, credenciales, `.env`, `authorized_keys` ni similares;
- archivos incluidos con `source` fuera de `$HOME` o en carpetas personales.

En GNOME, Cinnamon, MATE y Budgie la copia local puede arrastrar claves de
dconf con historial, favoritos o rutas. No son archivos restaurables, pero
quedan en el manifiesto: la auditoría las marca y la copia saneada las elimina.

Los atajos de teclado se guardan en la copia local (con el comando que
ejecutan) para poder restaurarlos. En los perfiles compartidos solo entran los
que no contienen rutas, URLs, secretos ni scripts; el resto se descarta y se
informa. Si un atajo apunta a un script, el script nunca se copia.

La portada de la copia local es opcional. En Hyprland la captura se hace en un
workspace especial temporal; en el resto de compositores puede incluir
ventanas. El fondo se copia únicamente dentro de `preview/` para generar la
imagen. Con `--no-preview` no se guarda ninguna imagen. La portada de un perfil
compartido se genera desde el fondo, nunca desde esa captura.

## Cómo revocar un perfil publicado

Abrí un PR o un issue en el repositorio de perfiles pidiendo la baja; el perfil
se elimina del índice y del repositorio. Las copias que ya hayan descargado
otras personas no se pueden recuperar, igual que cualquier archivo compartido.
