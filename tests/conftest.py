"""
conftest.py
A single QApplication for the whole test session (Qt only allows one per
process) plus a fresh MainWindow per test that needs the full app.
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


@pytest.fixture
def main_window(qapp, tmp_path, monkeypatch):
    """A fresh MainWindow, with QSettings redirected to a throwaway location
    so tests never read or write the real user's ~/.pycad or registry/plist."""
    from PyQt6.QtCore import QSettings
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path))
    import pycad.appsettings as settings
    monkeypatch.setattr(settings, "get_settings", lambda: QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat))
    monkeypatch.setattr(settings, "RECOVERY_PATH", str(tmp_path / "recovery.pycad"))
    from pycad.main_window import MainWindow
    window = MainWindow()
    window.resize(900, 600)
    window.show()
    qapp.processEvents()
    yield window
    window.cancel_command()
    for session in window.drawing_tabs.sessions: session["doc"].mark_saved()
    window.close()
    window.deleteLater()
    qapp.processEvents()
