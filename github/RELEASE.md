# Publicar una versión

## Checklist

1. **Versión** en los tres lugares que tienen que coincidir:
   - `src/themevault/__init__.py` → `__version__`
   - `pyproject.toml` → `[project] version`
   - `src/themevault/ui/qml/Theme.qml` → `appVersion`
2. **CHANGELOG.md**: mover lo de `[Unreleased]` a `[X.Y.Z] - AAAA-MM-DD`.
3. **Capturas** (`docs/*.png`): regenerarlas para que muestren la versión nueva.
4. **Tests** en local: `python -m pytest -q`.
5. **Empaquetado**: construir el wheel y probarlo en un venv limpio.
6. Commit, `git tag -a vX.Y.Z -m "ThemeVault X.Y.Z"` y `git push origin vX.Y.Z`.
7. El workflow **Release** construye y publica los artefactos.
8. Verificar que el AppImage descargado arranca.
9. Anunciar (Discussions / redes) y **agradecer a quienes donan** en
   [ko-fi.com/tuxarchi](https://ko-fi.com/tuxarchi).

## Verificar el wheel

```bash
python -m build --wheel
python -m venv /tmp/tv-clean
/tmp/tv-clean/bin/pip install dist/themevault-X.Y.Z-py3-none-any.whl 'PySide6-Essentials' 'Pillow'
QT_QPA_PLATFORM=offscreen /tmp/tv-clean/bin/themevault-gui --screenshot /tmp/tv.png
```

Si la ventana no renderiza, faltan los archivos QML: revisá
`[tool.setuptools.package-data]` en `pyproject.toml`.

## AppImage

El AppImage **se construye en Ubuntu 22.04** (glibc 2.35), nunca en un sistema
más nuevo, para que corra en la mayor cantidad de distribuciones.

```bash
bash packaging/appimage/build.sh
# -> dist/ThemeVault-X.Y.Z-x86_64.AppImage
```

Qué hace el script:

1. Instala `pyinstaller` en el entorno de build.
2. Empaqueta la app con `packaging/appimage/ThemeVault.spec`
   (incluye los QML, los plugins de Qt y los módulos QML de QtQuick).
3. Arma el AppDir con `AppRun`, `.desktop` e icono.
4. Descarga `appimagetool` y genera el AppImage en `dist/`.

Prueba rápida:

```bash
./dist/ThemeVault-*.AppImage --version
QT_QPA_PLATFORM=offscreen ./dist/ThemeVault-*.AppImage --screenshot /tmp/app.png
```

El `AppRun` fuerza `QT_QUICK_BACKEND=software`: el bundle no siempre logra crear
un contexto OpenGL en Wayland y Qt aborta. No quites ese valor sin probar en
varias distros.

## GitHub Pages

El sitio vive en `docs/` y se publica desde `main` → `/docs` (rama y carpeta,
sin build). Cualquier push a `docs/` lo actualiza.

- `docs/index.html`, `docs/style.css`, `docs/.nojekyll`
- Capturas en `docs/*.png`

El preview social (`docs/assets/social.png`) se sube a mano en
*Settings → Social preview*.

## Apoyo

Si la versión sale bien, acordate de mencionar el Ko-fi en el anuncio:
[ko-fi.com/tuxarchi](https://ko-fi.com/tuxarchi).
