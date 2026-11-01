# -*- mode: python ; coding: utf-8 -*-
"""Empaquetado de ThemeVault con PyInstaller (onedir).

Se ejecuta desde `packaging/appimage/build.sh`. Incluye el paquete completo
(con `ui/qml`) y los modulos QML de Qt necesarios para dibujar la interfaz.
"""

import os

import PySide6
from PyInstaller.utils.hooks import collect_data_files

QT_QML = os.path.join(os.path.dirname(PySide6.__file__), "Qt", "qml")

datas = collect_data_files("themevault")
datas += [(QT_QML, "PySide6/Qt/qml")]

hiddenimports = [
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuickControls2",
    "PySide6.QtSvg",
    "PySide6.QtNetwork",
    "PySide6.QtDBus",
]

a = Analysis(
    ["launcher.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "unittest",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.Qt3DCore",
        "PySide6.QtMultimedia",
        "PySide6.QtCharts",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ThemeVault",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="ThemeVault",
)
