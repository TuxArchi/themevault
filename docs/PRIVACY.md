# Privacidad y perfiles compartidos

ThemeVault **no sube nada por su cuenta**. Una copia guardada vive en tu equipo
y solo sale de ahí si vos exportás un perfil y lo publicás a mano.

## Qué contiene un perfil

Un perfil no es una copia. Es una descripción del aspecto, generada con una
**lista blanca** de campos:

| Se comparte | Ejemplo |
|---|---|
| Nombre, autor, licencia, escritorio | `"Catppuccin Mocha"`, `@tuxarchi`, `CC-BY-SA-4.0`, `kde` |
| Nombres de tema | `icons: Papirus-Dark`, `cursor: Breeze` |
| Ajustes de apariencia | `ColorScheme=CatppuccinMocha`, `gtk-theme-name=Breeze` |
| Paleta | derivada del **esquema de color**, no del wallpaper |
| Portada | solo si la incluís explícitamente |

## Qué **nunca** se incluye

- Rutas absolutas, `~`, nombres de usuario o hostname.
- Archivos de la copia: temas, iconos, fuentes, wallpapers, `files/`.
- Atajos de teclado, comandos o texto de configuración de Hyprland.
- Nombres de archivos del escritorio, títulos de ventanas o historial de apps.
- UUIDs de actividad, geometrías de pantalla o configuración de layouts.
- Texto de widgets (notas, portapapeles, favoritos).
- La captura del escritorio: puede mostrar tu fondo y tus cosas. Solo se
  incluye si activás «incluir portada» y lo ves en la vista previa.

## Cómo se publica

1. Desde el detalle de una copia, **Compartir…** (o `themevault
   export-profile` en la terminal) genera `profile.json` (+ `cover.png` si lo
   pediste).
2. La app muestra **qué se comparte y qué se descarta** antes de exportar; la
   portada es un switch aparte.
3. **Vos revisás el archivo** antes de nada.
4. Lo enviás como pull request al repositorio de perfiles. `themevault
   publish-profile` valida, copia al clon y regenera el índice; con `--pr`
   abre el pull request (siempre con confirmación).
   El `author` tiene que ser **tu usuario de GitHub** y coincidir con la cuenta
   que abre el PR; el CI lo verifica y bloquea que se publique o edite un
   perfil ajeno.
5. Un validador automático rechaza rutas, binarios, campos desconocidos y
   tamaños excesivos; después lo revisa una persona.

Sin ese paso manual no hay publicación. La aplicación nunca abre una conexión
para subir datos.

Al abrir **Compartir…**, si tenés `gh` instalado, la app le pregunta cuál es tu
usuario para prellenar el campo (una consulta a `api.github.com`). No envía el
perfil ni ningún dato tuyo: la publicación sigue siendo manual.

## Qué guarda la app en tu equipo

| Ruta | Contenido |
|---|---|
| `~/.local/share/themevault/backups/` | tus copias (configuración y archivos) |
| `~/.cache/themevault/thumbs/` | miniaturas |
| `~/.cache/themevault/assets/` | iconos y cursores rasterizados |
| `~/.cache/themevault/community.json` | índice de perfiles (fase 2) |

Todo es local y se puede borrar sin afectar al sistema.

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

Los atajos de teclado se guardan en el manifest y se muestran en el detalle,
pero **no se incluyen en los perfiles compartidos**. Si un atajo apunta a un
script, el script queda fuera y se lista solo como dependencia externa.

La portada es opcional. En Hyprland la captura se hace en un workspace
especial temporal; en el resto de compositores puede incluir ventanas. El
fondo se copia únicamente dentro de `preview/` para generar la imagen. Con
`--no-preview` no se guarda ninguna imagen.

## Cómo revocar un perfil publicado

Abrí un PR o un issue en el repositorio de perfiles pidiendo la baja; el perfil
se elimina del índice y del repositorio. Las copias que ya hayan descargado
otras personas no se pueden recuperar, igual que cualquier archivo compartido.
