#!/usr/bin/env bash
# Construye dist/ThemeVault-<version>-x86_64.AppImage
#
# Pensado para correr en Ubuntu 22.04 (glibc 2.35): un AppImage armado en una
# distribucion mas nueva no arranca en las demas.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
cd "$ROOT"

VERSION="$(python - <<'PY'
import pathlib, re
text = pathlib.Path("pyproject.toml").read_text()
print(re.search(r'^version = "([^"]+)"', text, re.MULTILINE).group(1))
PY
)"

echo "== ThemeVault $VERSION =="
echo "python: $(python --version)"

python -m pip install -q --upgrade pyinstaller

# PyInstaller necesita el paquete instalado (no solo el checkout) para poder
# colectar el codigo y los archivos QML.
if ! python -c "import themevault" >/dev/null 2>&1; then
  echo "== instalando themevault =="
  python -m pip install -q .
fi

rm -rf build/pyinstaller dist/AppDir
mkdir -p build/pyinstaller dist

echo "== PyInstaller =="
pyinstaller \
  --noconfirm \
  --clean \
  --distpath build/pyinstaller/dist \
  --workpath build/pyinstaller/work \
  "$HERE/ThemeVault.spec"

APPDIR="dist/AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin" \
         "$APPDIR/usr/share/applications" \
         "$APPDIR/usr/share/icons/hicolor/scalable/apps"

cp -r build/pyinstaller/dist/ThemeVault/. "$APPDIR/usr/bin/"

sed "s/@@VERSION@@/${VERSION}/" "$HERE/ThemeVault.desktop" > "$APPDIR/ThemeVault.desktop"
install -m 644 "$APPDIR/ThemeVault.desktop" "$APPDIR/usr/share/applications/ThemeVault.desktop"
install -m 644 src/themevault/ui/qml/themevault.svg "$APPDIR/themevault.svg"
install -m 644 src/themevault/ui/qml/themevault.svg \
  "$APPDIR/usr/share/icons/hicolor/scalable/apps/themevault.svg"
for size in 128 256 512; do
  install -Dm644 "docs/assets/icon-${size}.png" \
    "$APPDIR/usr/share/icons/hicolor/${size}x${size}/apps/themevault.png"
done
install -m 755 "$HERE/AppRun" "$APPDIR/AppRun"

TOOL="${APPIMAGETOOL:-/tmp/appimagetool}"
if [ ! -x "$TOOL" ]; then
  echo "== descargando appimagetool =="
  curl -fsSL \
    "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage" \
    -o "$TOOL"
  chmod +x "$TOOL"
fi

echo "== empaquetando AppImage =="
ARCH=x86_64 "$TOOL" --appimage-extract-and-run --no-appstream \
  "$APPDIR" "dist/ThemeVault-${VERSION}-x86_64.AppImage"

ls -la "dist/ThemeVault-${VERSION}-x86_64.AppImage"
echo "ok"
