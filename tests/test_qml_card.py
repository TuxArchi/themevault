"""Test de los botones ‹ › de la tarjeta de la galeria.

Carga `BackupCard.qml` en una ventana real (offscreen) y hace clic con QTest
sobre las flechas, para verificar el cableado completo y no solo la logica.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QObject, QPoint, QPointF, Qt, QUrl  # noqa: E402
from PySide6.QtQuick import QQuickItem, QQuickView  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402

QML = Path(__file__).resolve().parents[1] / "src" / "themevault" / "ui" / "qml" / "BackupCard.qml"


@pytest.fixture()
def card(qapp):
    view = QQuickView()
    view.setSource(QUrl.fromLocalFile(str(QML)))
    assert view.errors() == [], [e.toString() for e in view.errors()]
    view.resize(480, 380)
    view.show()
    item = view.rootObject()
    assert item is not None
    item.setWidth(480)
    item.setHeight(380)
    item.setProperty("covers", ["file:///tmp/a.png", "file:///tmp/b.png"])
    QTest.qWait(60)
    yield view, item
    view.close()


def _click(view: QQuickView, item, name: str) -> None:
    arrow = item.findChild(QObject, name)
    assert arrow is not None, f"no existe {name}"
    center = QPointF(arrow.property("width") / 2, arrow.property("height") / 2)
    scene = arrow.mapToScene(center)
    QTest.mouseClick(view, Qt.LeftButton, Qt.NoModifier, QPoint(int(scene.x()), int(scene.y())))


def test_flechas_cambian_de_portada(card):
    view, item = card
    assert item.property("coverIndex") == 0

    _click(view, item, "nextArrow")
    assert item.property("coverIndex") == 1

    _click(view, item, "nextArrow")
    assert item.property("coverIndex") == 0, "deberia volver al inicio"

    _click(view, item, "prevArrow")
    assert item.property("coverIndex") == 1, "hacia atras tiene que dar la vuelta"


def test_sin_segunda_portada_no_cambia(card):
    view, item = card
    item.setProperty("covers", ["file:///tmp/a.png"])
    QTest.qWait(30)
    _click(view, item, "nextArrow")
    assert item.property("coverIndex") == 0
