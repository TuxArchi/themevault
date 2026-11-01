"""Tests del puente QML <-> core (sin abrir ventanas)."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QCoreApplication.instance() or QCoreApplication([])
    yield app


def run_and_wait(signal, action, timeout: int = 15000):
    """Dispara `action` y espera la primera emision de `signal`."""
    loop = QEventLoop()
    box: dict = {}

    def on(*args):
        box["args"] = args
        loop.quit()

    signal.connect(on)
    action()
    QTimer.singleShot(timeout, loop.quit)
    loop.exec()
    signal.disconnect(on)
    return box.get("args")


@pytest.fixture()
def backend(qapp, tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / ".themes" / "TemaFalso").mkdir(parents=True)
    (home / ".themes" / "TemaFalso" / "index.theme").write_text("Name=TemaFalso\n")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_DATA_HOME", str(home / ".local" / "share"))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))

    # El runner de CI no tiene escritorio: se fuerza KDE en el motor.
    from themevault.adapters.kde import KdeAdapter

    monkeypatch.setattr("themevault.backup.detected_adapters", lambda: [KdeAdapter()])

    from themevault.ui.bridge import Backend

    return Backend(tmp_path / "vault"), home


def test_backup_create_and_refresh(backend):
    back, _ = backend
    assert back.backupCount == 0

    args = run_and_wait(back.backupCreated, lambda: back.createBackup("prueba ui", "", False))
    assert args is not None, "no llego la señal backupCreated"
    info = args[0]
    assert info["id"]
    assert back.backupCount == 1


def test_plan_and_detail(backend):
    back, _ = backend
    (info,) = run_and_wait(back.backupCreated, lambda: back.createBackup("plan", "", False))
    backup_id = info["id"]

    (plan,) = run_and_wait(back.planReady, lambda: back.requestPlan(backup_id))
    assert plan["id"] == backup_id
    assert plan["deApplicable"] >= 1
    assert any(c["name"] == "theme" for c in plan["categories"])

    detail = back.detail(backup_id)
    assert detail["error"] == ""
    assert detail["title"] == "plan"
    assert detail["categories"]
    assert detail["sizeText"]


def test_restore_from_ui(backend):
    back, home = backend
    (info,) = run_and_wait(back.backupCreated, lambda: back.createBackup("restore", "", False))
    backup_id = info["id"]

    import shutil

    shutil.rmtree(home / ".themes" / "TemaFalso")

    categories = ["theme"]
    (result,) = run_and_wait(
        back.restoreFinished,
        lambda: back.applyRestore(backup_id, categories, False),
    )
    assert result["applied"] >= 1
    assert result["failures"] == []
    assert (home / ".themes" / "TemaFalso" / "index.theme").exists()


def test_failure_signal_on_missing_backup(backend):
    back, _ = backend
    args = run_and_wait(back.failed, lambda: back.requestPlan("no-existe"))
    assert args is not None
    assert args[0] == "plan"
