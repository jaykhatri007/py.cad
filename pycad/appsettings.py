"""
appsettings.py
QSettings-backed persistence (window geometry, recent files, last directory)
plus the fixed path used for crash-recovery autosaves.
"""
import os
from PyQt6.QtCore import QSettings

from .applog import APP_DIR

ORG_NAME = "PyCAD"
APP_NAME = "PyCAD"
MAX_RECENT_FILES = 8

RECOVERY_PATH = os.path.join(APP_DIR, "recovery.pycad")
CLEAN_EXIT_MARKER = os.path.join(APP_DIR, "clean_exit")


def get_settings() -> QSettings:
    if os.environ.get("PYCAD_DATA_DIR"):
        return QSettings(os.path.join(APP_DIR, "settings.ini"), QSettings.Format.IniFormat)
    return QSettings(ORG_NAME, APP_NAME)


def save_window_geometry(window):
    s = get_settings()
    s.setValue("window/geometry", window.saveGeometry())
    s.setValue("window/state", window.saveState())


def restore_window_geometry(window) -> bool:
    s = get_settings()
    geometry = s.value("window/geometry")
    state = s.value("window/state")
    if geometry is not None:
        window.restoreGeometry(geometry)
    if state is not None:
        window.restoreState(state)
    return geometry is not None


def get_last_directory() -> str:
    return get_settings().value("files/last_directory", os.path.expanduser("~"))


def set_last_directory(path: str):
    directory = path if os.path.isdir(path) else os.path.dirname(os.path.abspath(path))
    if directory:
        get_settings().setValue("files/last_directory", directory)


def get_recent_files() -> list:
    files = get_settings().value("files/recent", [])
    if isinstance(files, str):  # QSettings can collapse a 1-item list to a bare string
        files = [files]
    return [f for f in files if os.path.exists(f)]


def add_recent_file(path: str):
    files = get_recent_files()
    if path in files:
        files.remove(path)
    files.insert(0, path)
    get_settings().setValue("files/recent", files[:MAX_RECENT_FILES])


def mark_clean_exit():
    """Called on a normal, deliberate shutdown - clears the recovery file
    and its marker so the next launch doesn't offer to recover from it."""
    for p in (RECOVERY_PATH, CLEAN_EXIT_MARKER):
        try:
            if os.path.exists(p):
                os.remove(p)
        except OSError:
            pass


def recovery_file_exists() -> bool:
    return os.path.exists(RECOVERY_PATH)
