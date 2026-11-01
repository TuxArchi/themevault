"""Arranque de la interfaz grafica."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .. import __version__

QML_DIR = Path(__file__).parent / "qml"


def _pick_font(app) -> None:
    from PySide6.QtGui import QFont, QFontDatabase

    families = set(QFontDatabase.families())
    for candidate in ("Inter", "Noto Sans", "Cantarell", "DejaVu Sans", "Liberation Sans"):
        if candidate in families:
            app.setFont(QFont(candidate, 10))
            return


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="themevault-gui",
        description="ThemeVault - interfaz grafica",
    )
    parser.add_argument(
        "--version", action="version", version=f"themevault {__version__}"
    )
    parser.add_argument("--root", type=Path, default=None, help="directorio de copias")
    parser.add_argument("--backup", default="", help="abrir directamente el detalle de una copia")
    parser.add_argument("--page", choices=("gallery", "system"), default="gallery")
    parser.add_argument(
        "--action",
        choices=("none", "restore", "new"),
        default="none",
        help="abrir directamente un dialogo (util para capturas y pruebas)",
    )
    parser.add_argument("--screenshot", type=Path, default=None, help="capturar la ventana y salir")
    parser.add_argument("--size", default="", help="tamano de ventana para la captura (ej. 1280x1100)")
    args = parser.parse_args(argv)

    try:
        from PySide6.QtCore import QTimer, QUrl
        from PySide6.QtGui import QGuiApplication
        from PySide6.QtQml import QQmlApplicationEngine
    except ImportError:
        print("Falta PySide6. Instala con: pip install 'themevault[gui]'", file=sys.stderr)
        return 2

    os.environ.setdefault("QT_QUICK_CONTROLS_STYLE", "Basic")

    app = QGuiApplication(sys.argv[:1])
    app.setApplicationName("ThemeVault")
    app.setApplicationDisplayName("ThemeVault")
    app.setOrganizationName("ThemeVault")
    app.setDesktopFileName("themevault")
    _pick_font(app)

    icon = QML_DIR / "themevault.svg"
    if icon.exists():
        from PySide6.QtGui import QIcon

        app.setWindowIcon(QIcon(str(icon)))

    from .bridge import Backend

    backend = Backend(args.root)

    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("backend", backend)
    engine.rootContext().setContextProperty("initialBackup", args.backup)
    engine.rootContext().setContextProperty("initialPage", args.page)
    engine.rootContext().setContextProperty("initialAction", args.action)

    main_qml = QML_DIR / "Main.qml"
    if not main_qml.exists():
        print(f"No se encontro la interfaz en {main_qml}", file=sys.stderr)
        return 2

    engine.load(QUrl.fromLocalFile(str(main_qml)))
    if not engine.rootObjects():
        print("La interfaz no pudo cargarse (revisa los errores de QML arriba).", file=sys.stderr)
        return 1

    if args.size:
        try:
            width, height = (int(part) for part in args.size.lower().split("x", 1))
            engine.rootObjects()[0].resize(width, height)
        except (ValueError, IndexError):
            print(f"tamano invalido: {args.size}", file=sys.stderr)

    if args.screenshot:
        target = args.screenshot

        def grab() -> None:
            try:
                import shiboken6
                from PySide6.QtQuick import QQuickWindow

                root = engine.rootObjects()[0]
                window = shiboken6.wrapInstance(shiboken6.getCppPointer(root)[0], QQuickWindow)
                image = window.grabWindow()
                if image.isNull():
                    print("no se pudo capturar la ventana", file=sys.stderr)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    image.save(str(target))
                    print(f"captura {image.width()}x{image.height()} -> {target}")
            except Exception as exc:  # pragma: no cover - solo debug
                print(f"captura fallida: {exc}", file=sys.stderr)
            app.exit(0)

        QTimer.singleShot(1900, grab)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
