"""Diagnose the active PY.cad interpreter; optional GUI check uses private prefs."""

import argparse
import json
import os
from pathlib import Path
import platform
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--gui", action="store_true", help="Open and close a real native Qt window"
    )
    parser.add_argument(
        "--offscreen",
        action="store_true",
        help="Use headless Qt; this does not verify your desktop compositor",
    )
    args = parser.parse_args()
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    report = dict(
        python=sys.version.split()[0],
        executable=sys.executable,
        platform=platform.platform(),
        desktop_test="not requested",
    )
    failures = []
    try:
        import ezdxf
        import numpy
        from PyQt6.QtCore import PYQT_VERSION_STR, qVersion

        report.update(
            ezdxf=ezdxf.__version__,
            numpy=numpy.__version__,
            pyqt=PYQT_VERSION_STR,
            qt=qVersion(),
        )
    except ImportError as ex:
        failures.append("Core dependencies: " + str(ex))
    try:
        import cadquery as cq

        shape = cq.Workplane("XY").box(10, 10, 10).val()
        assert shape.isValid() and abs(shape.Volume() - 1000) < 1e-6
        report["optional_3d"] = "passed; CadQuery " + cq.__version__
    except Exception as ex:
        report["optional_3d"] = "unavailable: " + str(ex)
    if args.gui or args.offscreen:
        if args.offscreen:
            os.environ["QT_QPA_PLATFORM"] = "offscreen"
        with tempfile.TemporaryDirectory(prefix="pycad-environment-") as directory:
            os.environ["PYCAD_DATA_DIR"] = directory
            from PyQt6.QtWidgets import QApplication
            from PyQt6.QtCore import QTimer
            from pycad.main_window import MainWindow

            app = QApplication([])
            w = MainWindow()
            w.resize(1000, 700)
            w.show()

            def finish():
                report["desktop_test"] = "passed; Qt platform " + app.platformName()
                report["window_size"] = [w.width(), w.height()]
                w.close()

            QTimer.singleShot(1000, finish)
            app.exec()
    report["failures"] = failures
    print(json.dumps(report, indent=2))
    return bool(failures)


if __name__ == "__main__":
    raise SystemExit(main())
