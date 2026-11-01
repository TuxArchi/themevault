# Privacidad y perfiles compartidos

ThemeVault **no sube nada por su cuenta**. Una copia guardada vive en tu equipo
y solo sale de ahí si vos exportás un perfil y lo publicás a mano.

## Qué contiene un perfil

Un perfil no es una copia. Es una descripción del aspecto, generada con una
**lista blanca** de campos:

| Se comparte | Ejemplo |
|---|---|
| Nombre, autor, licencia, escritorio | `"Catppuccin Mocha"`, `CC-BY-SA-4.0`, `kde` |
| Nombres de tema | `icons: Papirus-Dark`, `cursor: Breeze` |
| Ajustes de apariencia | `ColorScheme=CatppuccinMocha`, `gtk-theme-name=Breeze` |
| Paleta | derivada del **esquema de color**, no del wallpaper |
| Portada | solo si la incluís explícitamente |

## Qué **nunca** se incluye

- Rutas absolutas, `~`, nombres de usuario o hostname.
- Archivos de la copia: temas, iconos, fuentes, wallpapers, `files/`.
- Nombres de archivos del escritorio, títulos de ventanas o historial de apps.
- UUIDs de actividad, geometrías de pantalla o configuración de layouts.
- Texto de widgets (notas, portapapeles, favoritos).
- La captura del escritorio: puede mostrar tu fondo y tus cosas. Solo se
  incluye si activás «incluir portada» y lo ves en la vista previa.

## Cómo se publica

1. La app genera `profile.json` (+ `cover.png` si lo pediste).
2. **Vos revisás el archivo** antes de nada.
3. Lo enviás como pull request al repositorio de perfiles.
4. Un validador automático rechaza rutas, binarios, campos desconocidos y
   tamaños excesivos; después lo revisa una persona.

Sin ese paso manual no hay publicación. La aplicación nunca abre una conexión
para subir datos.

## Qué guarda la app en tu equipo

| Ruta | Contenido |
|---|---|
| `~/.local/share/themevault/backups/` | tus copias (configuración y archivos) |
| `~/.cache/themevault/thumbs/` | miniaturas |
| `~/.cache/themevault/assets/` | iconos y cursores rasterizados |
| `~/.cache/themevault/community.json` | índice de perfiles (fase 2) |

Todo es local y se puede borrar sin afectar al sistema.

## Cómo revocar un perfil publicado

Abrí un PR o un issue en el repositorio de perfiles pidiendo la baja; el perfil
se elimina del índice y del repositorio. Las copias que ya hayan descargado
otras personas no se pueden recuperar, igual que cualquier archivo compartido.
