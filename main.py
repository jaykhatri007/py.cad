#!/usr/bin/env python3
"""
PY.cad entry point.
Run with:  python main.py
"""
import sys
import os
from PyQt6.QtCore import QLockFile, QTimer
from PyQt6.QtWidgets import QApplication, QMessageBox
from pycad import applog, appsettings
from pycad.branding import app_icon
from pycad.identity import DISPLAY_NAME, LEGACY_APP_ID


def main():
    if len(sys.argv) in (5, 7) and sys.argv[1] == "--import-worker":
        from pycad.import_worker import run
        return run(*sys.argv[2:7])
    if len(sys.argv) in (2, 3) and sys.argv[1] == "--graphics-probe":
        from pycad.graphics_probe import run
        return run(sys.argv[2] if len(sys.argv) == 3 else None)
    import argparse
    parser = argparse.ArgumentParser(description="PY.cad desktop CAD")
    parser.add_argument("drawing", nargs="?")
    parser.add_argument("--graphics", choices=("auto", "hardware", "software"))
    args = parser.parse_args()
    if args.graphics:
        os.environ["PYCAD_GRAPHICS"] = args.graphics
    from pycad.graphics_surface import configure_surface_format
    configure_surface_format()
    applog.setup_logging()
    from pycad.windows_identity import set_process_identity, configure_application
    set_process_identity()  # Before QApplication or any Windows UI is created.
    app = QApplication([sys.argv[0]])
    configure_application(app)
    from pycad.async_display import shutdown as stop_display_workers
    app.aboutToQuit.connect(stop_display_workers)
    from pycad.document_lifecycle import dispose_documents
    app.aboutToQuit.connect(dispose_documents)
    lock = QLockFile(os.path.join(applog.APP_DIR, "instance.lock"))
    if not lock.tryLock(100):
        QMessageBox.information(None, "PY.cad already running", "Use the existing PY.cad window. A single session protects recovery files.")
        return 1
    applog.install_excepthook(app)
    from pycad.main_window import MainWindow
    window = MainWindow()
    window.show()
    if args.drawing and not appsettings.recovery_file_exists():
        QTimer.singleShot(0, lambda: window._open_path(args.drawing))
    sys.exit(app.exec())


if __name__ == "__main__":
    sys.exit(main())
