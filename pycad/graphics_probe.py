"""Isolated, bounded two-frame OpenGL/QPainter readback test.

Driver crashes and startup hangs here cannot take down the drawing process.
Run with python -m pycad.graphics_probe; stdout contains one JSON result.
"""

import json
import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from PyQt6.QtWidgets import QApplication
from .graphics_surface import configure_surface_format, context_details


def run(report_path=None):
    configure_surface_format()
    app = QApplication.instance() or QApplication([sys.argv[0]])
    result = {"format": 1, "render_test_passed": False, "platform": app.platformName()}
    completed = False

    def publish():
        payload = json.dumps(result, ensure_ascii=True)
        if report_path is not None:
            path = Path(report_path)
            temporary = path.with_suffix(".tmp")
            temporary.write_text(payload, encoding="utf-8")
            temporary.replace(path)
        if sys.stdout is not None:
            print(payload, flush=True)

    def finish(reason=None):
        nonlocal completed
        if completed:
            return
        completed = True
        if reason:
            result["reason"] = str(reason)[:512]
        publish()
        app.exit(0 if result["render_test_passed"] else 1)

    if app.platformName() in ("offscreen", "minimal", "vnc"):
        # Qt does not support QOpenGLWidget composition on these plugins.
        result["reason"] = "This Qt display plugin does not support OpenGL widgets"
        publish()
        return 1

    class Probe(QOpenGLWidget):
        def __init__(self):
            super().__init__()
            self.phase = 0
            self.frames = 0
            self.setWindowTitle("PY.cad graphics check")
            self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
            self.resize(96, 96)
            self.frameSwapped.connect(lambda: QTimer.singleShot(0, self.check_pixels))

        def initializeGL(self):
            try:
                result.update(context_details(self.context()))
            except Exception as ex:
                QTimer.singleShot(0, lambda reason=str(ex): finish(reason))

        def paintGL(self):
            painter = QPainter(self)
            try:
                if not painter.isActive():
                    raise RuntimeError("QPainter did not start")
                result["paint_engine"] = painter.paintEngine().type().name
                painter.fillRect(self.rect(), QColor("#17324d"))
                painter.fillRect(16, 16, 64, 64, QColor("#4bc6ab" if self.phase == 0 else "#d2844b"))
                self.frames += 1
            except Exception as ex:
                QTimer.singleShot(0, lambda reason=str(ex): finish(reason))
            finally:
                painter.end()

        def check_pixels(self):
            if completed:
                return
            try:
                if not self.isValid() or not all(result.get(k) for k in ("vendor", "renderer", "version")):
                    raise RuntimeError("A valid OpenGL driver context was not created")
                image = self.grabFramebuffer()
                if image.isNull():
                    raise RuntimeError("OpenGL framebuffer readback was empty")
                expected = QColor("#4bc6ab" if self.phase == 0 else "#d2844b")
                actual = image.pixelColor(image.width() // 2, image.height() // 2)
                if any(abs(a - b) > 3 for a, b in zip(actual.getRgb(), expected.getRgb())):
                    raise RuntimeError("OpenGL framebuffer pixels did not match the test drawing")
                if result.get("paint_engine") != "OpenGL2":
                    raise RuntimeError("Qt did not use its OpenGL2 paint engine")
                if self.phase == 0:
                    self.phase = 1
                    self.update()
                else:
                    result.update(render_test_passed=True, frames_tested=2, reason="Two OpenGL frames passed pixel readback")
                    finish()
            except Exception as ex:
                finish(ex)

    widget = Probe()
    QTimer.singleShot(10000, lambda: finish("OpenGL probe timed out"))
    widget.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(run(sys.argv[1] if len(sys.argv) == 2 else None))
