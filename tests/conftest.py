"""Fixtures compartidas.

Una sola QGuiApplication para toda la sesion: los tests de QML necesitan una y
los del puente usan QCoreApplication, que es su clase base.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtGui import QGuiApplication  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def qapp():
    app = QGuiApplication.instance() or QGuiApplication([])
    yield app
