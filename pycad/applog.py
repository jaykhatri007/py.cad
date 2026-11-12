"""
applog.py
Centralized logging setup. Every module should do `logging.getLogger(__name__)`
rather than printing - prints vanish once the app is packaged as a windowed
executable (no visible console), while these logs always land in a file.
"""
import logging
import os
import sys
import traceback
from logging.handlers import RotatingFileHandler

APP_DIR = os.path.abspath(os.path.expanduser(os.environ.get("PYCAD_DATA_DIR") or os.path.join("~", ".pycad")))
LOG_DIR = os.path.join(APP_DIR, "logs")
LOG_PATH = os.path.join(LOG_DIR, "pycad.log")


def setup_logging(level=logging.INFO) -> str:
    """Configure the root logger. Returns the log file path (useful for an
    'Open Log File' menu action or for telling the user where to look)."""
    os.makedirs(LOG_DIR, exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S")

    file_handler = RotatingFileHandler(LOG_PATH, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    # Avoid duplicate handlers if setup_logging() is ever called twice (e.g. in tests)
    root.handlers.clear()
    root.addHandler(file_handler)
    root.addHandler(console_handler)

    # Third-party libraries (ezdxf especially) log a lot of routine INFO
    # noise on every save/load - keep our own log readable by raising their
    # bar to WARNING, while PY.cad's own modules stay at `level`.
    for noisy in ("ezdxf",):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logging.getLogger(__name__).info("=== PY.cad starting (log: %s) ===", LOG_PATH)
    return LOG_PATH


def install_excepthook(app=None):
    """Catch anything that slips past individual try/except blocks (e.g. an
    exception raised outside any Qt event handler) so the person sees a
    dialog and a log entry instead of a silent terminal crash."""
    logger = logging.getLogger("pycad.uncaught")

    def _hook(exc_type, exc_value, exc_tb):
        logger.critical("Uncaught exception:\n%s",
                         "".join(traceback.format_exception(exc_type, exc_value, exc_tb)))
        try:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(None, "PY.cad - Unexpected Error",
                                  f"Something went wrong:\n\n{exc_value}\n\n"
                                  f"Details were written to:\n{LOG_PATH}\n\n"
                                  "PY.cad will try to keep running, but consider "
                                  "saving your work under a new file name.")
        except Exception:
            pass  # if even the error dialog fails, we've already logged it

    sys.excepthook = _hook
