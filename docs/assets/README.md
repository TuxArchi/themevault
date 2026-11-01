# Assets de marca

| Archivo | Uso |
|---|---|
| `icon.svg` | Maestro 512×512 (también `src/themevault/ui/qml/themevault.svg`) |
| `icon-16.png` … `icon-1024.png` | Iconos por tamaño para el sitio, el AppImage y el escritorio |
| `favicon.ico` | 16/24/32/48/64 |
| `apple-touch-icon.png` | 180×180 |
| `banner.png` | 1600×600, cabecera del README |
| `social.png` | 1280×640, Open Graph y social preview de GitHub |

Se regeneran desde el SVG maestro y las capturas:

```bash
python packaging/brand/build_brand.py
```

Necesita `rsvg-convert` (librsvg2-bin) y Pillow. Si cambia la paleta, primero
actualizá `src/themevault/ui/qml/Theme.qml` y `docs/style.css`, regenerá las
capturas y recién después este script.

El social preview del repositorio se sube a mano en *Settings → Social preview*:
la API de GitHub no permite cambiarlo.
