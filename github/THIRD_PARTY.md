# Componentes de terceros

ThemeVault es GPL-3.0-or-later. El AppImage incluye componentes con sus propias
licencias:

| Componente | Licencia | Uso |
| ---------- | -------- | --- |
| [Qt 6](https://www.qt.io/) | LGPL-3.0 | Base de la interfaz (vía PySide6) |
| [PySide6](https://doc.qt.io/qtforpython/) | LGPL-3.0 | Enlaces oficiales de Qt para Python |
| [Pillow](https://python-pillow.org/) | HPND | Miniaturas, portada y paleta |
| [librsvg](https://wiki.gnome.org/Projects/LibRsvg) (`rsvg-convert`) | LGPL-3.0 | Rasterizado de iconos y cursores SVG |
| Iconos de Breeze / Papirus / Adwaita | Licencias de cada tema | Solo se leen del sistema, no se redistribuyen |

## Notas sobre LGPL y el AppImage

El AppImage empaqueta Qt y PySide6 sin modificarlos. Para cumplir con la LGPL:

- No se modifica el código de Qt ni de PySide6.
- Las bibliotecas viajan como archivos separados dentro del AppDir (no
  reempaquetadas en un binario opaco), por lo que pueden reemplazarse.
- El código fuente de ThemeVault está disponible en este repositorio; el de Qt y
  PySide6, en sus repositorios oficiales.

## Marcas

KDE, Plasma, GNOME y Xfce son marcas de sus respectivos proyectos. ThemeVault no
está afiliado ni respaldado por ellos.

## Apoyo

Si el proyecto te resulta útil, podés invitarme un café:
[ko-fi.com/tuxarchi](https://ko-fi.com/tuxarchi).
