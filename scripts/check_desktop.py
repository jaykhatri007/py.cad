"""Actual Qt window/native/PDF smoke check, run by start.sh --check."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PyQt6.QtCore import qVersion
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QOffscreenSurface, QOpenGLContext
from pycad.main_window import MainWindow
from pycad.native_io import save_project, load_project, document_to_dict
from pycad.underlays import _open_pdf
from pycad import applog
from pycad._version import __version__
from pycad.geometry import Point, RectangleEntity
from pycad.model3d import create_extrusion


def main():
    app = QApplication([])
    window = MainWindow()
    window.resize(1280, 820)
    window.show()
    app.processEvents()
    window._open_path(str(ROOT / 'examples/precision_drafting.pycad'), confirm=False)
    app.processEvents()
    assert window.document.underlays
    output = Path(applog.APP_DIR)
    output.mkdir(parents=True, exist_ok=True)
    save_project(window.document, output / 'smoke.pycad')
    assert document_to_dict(load_project(output / 'smoke.pycad')) == document_to_dict(window.document)
    pdf = _open_pdf(ROOT / 'examples/studio_plan.pdf')
    assert pdf.pageCount() > 0
    pdf.close()
    create_extrusion(window.document, RectangleEntity(Point(0, 0), Point(80, 60)), 40)
    window.open_model_workspace(four=True)
    app.processEvents()
    assert sum(v.isVisible() for v in window.model_workspace.views) == 4
    view = window.model_workspace.active
    before = view.camera.project((20, 30, 40))
    view.rotate_camera(25, 12)
    assert view.camera.project((20, 30, 40)) != before
    app.processEvents()
    window.show_drafting()
    surface = QOffscreenSurface()
    surface.create()
    context = QOpenGLContext()
    gl = context.create() and context.makeCurrent(surface)
    if gl:
        context.doneCurrent()
    window.document.mark_saved()
    window.close()
    app.processEvents()
    print(json.dumps({'PY.cad': __version__, 'Qt': qVersion(), 'platform': app.platformName(),
        'window_native_pdf': 'passed', 'embedded_four_views_orbit': 'passed', 'OpenGL_context': bool(gl),
        'note': 'Context creation is not a hardware rendering certification.'}))


if __name__ == '__main__':
    main()
