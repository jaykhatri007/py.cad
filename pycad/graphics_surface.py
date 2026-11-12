"""Shared OpenGL paint surfaces; drawing geometry stays in the existing renderers."""

import logging
import time

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPainter, QSurfaceFormat
from PyQt6.QtOpenGL import QOpenGLFunctions_2_0
from PyQt6.QtOpenGLWidgets import QOpenGLWidget
from PyQt6.QtWidgets import QWidget

logger = logging.getLogger(__name__)


def configure_surface_format():
    """Call before QApplication. One compatible format serves every viewport."""
    fmt = QSurfaceFormat()
    fmt.setVersion(2, 0)
    fmt.setDepthBufferSize(24)
    fmt.setStencilBufferSize(8)
    fmt.setSamples(4)
    fmt.setSwapInterval(1)
    QSurfaceFormat.setDefaultFormat(fmt)


def context_details(context):
    if context is None or not context.isValid():
        raise RuntimeError("OpenGL context is invalid")
    functions = QOpenGLFunctions_2_0()
    if not functions.initializeOpenGLFunctions():
        raise RuntimeError("OpenGL 2.0 functions are unavailable")
    details = {}
    for key, enum in (("vendor", 0x1F00), ("renderer", 0x1F01), ("version", 0x1F02)):
        value = functions.glGetString(enum)
        if isinstance(value, bytes):
            value = value.decode("utf-8", "replace")
        if not value:
            raise RuntimeError("OpenGL driver returned an empty " + key)
        details[key] = str(value)[:512]
    fmt = context.format()
    details.update(samples=fmt.samples(), depth_bits=fmt.depthBufferSize(),
                   stencil_bits=fmt.stencilBufferSize())
    return details


class PaintSurface(QOpenGLWidget):
    """QPainter uses Qt's OpenGL2 paint engine on this surface.

    A Graphics View owns painting when draw is None. Model panes supply the
    same draw function as their raster path. No second copy of drawing logic.
    """

    started = pyqtSignal(object)
    ready = pyqtSignal(object, dict)
    failed = pyqtSignal(str)

    def __init__(self, parent=None, draw=None):
        super().__init__(parent)
        self.draw = draw
        self.retired = False
        self.details = {}
        self.frame_count = 0
        self.last_paint_ms = None
        self._first_frame = False
        self._watchdog = QTimer(self)
        self._watchdog.setSingleShot(True)
        self._watchdog.setInterval(5000)
        self._watchdog.timeout.connect(self._check_first_frame)
        self.frameSwapped.connect(self._frame_swapped)
        self.setUpdateBehavior(QOpenGLWidget.UpdateBehavior.NoPartialUpdate)
        self.setMouseTracking(True)

    def showEvent(self, event):
        if not self._first_frame and not self.retired:
            self.started.emit(self)
            self._watchdog.start()
        super().showEvent(event)

    def hideEvent(self, event):
        self._watchdog.stop()
        super().hideEvent(event)

    def initializeGL(self):
        try:
            self.details = context_details(self.context())
            self.context().aboutToBeDestroyed.connect(self._context_lost)
        except Exception as ex:
            self.failed.emit(str(ex))

    def paintGL(self):
        if self.retired or self.draw is None:
            return
        painter = QPainter(self)
        try:
            started = time.perf_counter()
            if not painter.isActive() or painter.paintEngine().type().name != "OpenGL2":
                raise RuntimeError("The OpenGL paint engine could not start")
            self.draw(painter)
            self.last_paint_ms = round((time.perf_counter() - started) * 1000, 3)
        except Exception:
            logger.exception("OpenGL model painting failed")
            self.failed.emit("OpenGL model painting failed; see the application log")
        finally:
            painter.end()

    def _frame_swapped(self):
        if self.retired:
            return
        self.frame_count += 1
        if not self._first_frame and self.isValid() and self.details:
            self._first_frame = True
            self._watchdog.stop()
            self.ready.emit(self, self.details)

    def _check_first_frame(self):
        if self.isVisible() and not self.retired and not self._first_frame:
            self.failed.emit("OpenGL did not present a frame within five seconds")

    def _context_lost(self):
        if not self.retired:
            self.failed.emit("An OpenGL viewport lost its graphics context")

    def retire(self):
        self.retired = True
        self._watchdog.stop()


def replace_canvas_viewport(canvas, surface):
    """Keep the canvas, tools, live input and child controls during a change."""
    old = canvas.viewport()
    children = old.findChildren(QWidget, options=Qt.FindChildOption.FindDirectChildrenOnly)
    visibility = [(child, not child.isHidden()) for child in children]
    if isinstance(old, PaintSurface):
        old.retire()
    for child, visible in visibility:
        if getattr(child, "viewport", None) is old:
            old.removeEventFilter(child)
            child.viewport = surface
            surface.installEventFilter(child)
        child.setParent(surface)
    canvas.setViewport(surface)
    surface.setMouseTracking(True)
    surface.setCursor(canvas.cursor())
    canvas.setViewportUpdateMode(canvas.ViewportUpdateMode.FullViewportUpdate)
    for child, visible in visibility:
        child.setVisible(visible)
        if hasattr(child, "reposition"):
            child.reposition()
    surface.update()
