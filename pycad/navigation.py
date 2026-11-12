"""Small, in-canvas camera controls shared by drafting and model viewports."""

from PyQt6.QtCore import Qt, QEvent, QPointF, QRectF, QSize, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap, QPolygonF
from PyQt6.QtWidgets import QWidget, QFrame, QBoxLayout, QToolButton, QComboBox

from .model3d import Camera, dot


def navigation_icon(name):
    pixmap = QPixmap(24, 24)
    pixmap.fill(Qt.GlobalColor.transparent)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    from .appearance import colors
    p.setPen(QPen(QColor(colors()['ui_icon']), 1.6))
    if name == "orbit":
        p.drawEllipse(QRectF(3, 7, 18, 10))
        p.drawEllipse(QRectF(7, 3, 10, 18))
        p.drawLine(18, 5, 20, 9)
        p.drawLine(20, 9, 16, 9)
    elif name == "pan":
        p.drawLine(3, 12, 21, 12)
        p.drawLine(12, 3, 12, 21)
        for x, y, dx, dy in [(3, 12, 3, 0), (21, 12, -3, 0),
                              (12, 3, 0, 3), (12, 21, 0, -3)]:
            p.drawLine(x, y, x + dx + dy, y + dy + dx)
            p.drawLine(x, y, x + dx - dy, y + dy - dx)
    elif name in ("+", "−"):
        p.drawEllipse(QRectF(3, 3, 13, 13))
        p.drawLine(15, 15, 21, 21)
        p.drawLine(6, 9, 13, 9)
        if name == "+":
            p.drawLine(10, 6, 10, 13)
    elif name == "fit":
        for x, y, dx, dy in [(3, 3, 6, 6), (21, 3, -6, 6),
                              (3, 21, 6, -6), (21, 21, -6, -6)]:
            p.drawLine(x, y, x + dx, y)
            p.drawLine(x, y, x, y + dy)
        p.drawRect(8, 8, 8, 8)
    else:
        p.drawPolygon(QPolygonF([QPointF(3, 8), QPointF(12, 3), QPointF(21, 8),
                                QPointF(21, 17), QPointF(12, 22), QPointF(3, 17)]))
        p.drawLine(3, 8, 12, 13)
        p.drawLine(21, 8, 12, 13)
        p.drawLine(12, 13, 12, 22)
    p.end()
    return QIcon(pixmap)


class OrientationCube(QWidget):
    """Original orthographic cube: click a face to align, drag to orbit."""

    view_requested = pyqtSignal(str)
    orbit_requested = pyqtSignal(float, float)

    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("orientation_cube")
        self.setFixedSize(88, 88)
        self.setToolTip("Click a face for its view • Drag to orbit • Double-click for isometric")
        self.setAccessibleName("Viewport orientation cube")
        self.camera = Camera("Top")
        self.faces = []
        self.last = None
        self.pressed = None
        self.dragged = False
        self.defer_orbit = False
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        font = p.font()
        font.setPixelSize(9)
        font.setBold(True)
        p.setFont(font)
        from .appearance import colors
        ui = colors(self)
        definitions = [
            ("Top", (0, 0, 1), [(-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)]),
            ("Bottom", (0, 0,-1), [(-1,-1,-1),(-1,1,-1),(1,1,-1),(1,-1,-1)]),
            ("Front", (0,-1,0), [(-1,-1,-1),(1,-1,-1),(1,-1,1),(-1,-1,1)]),
            ("Back", (0,1,0), [(-1,1,-1),(-1,1,1),(1,1,1),(1,1,-1)]),
            ("Left", (-1,0,0), [(-1,-1,-1),(-1,-1,1),(-1,1,1),(-1,1,-1)]),
            ("Right", (1,0,0), [(1,-1,-1),(1,1,-1),(1,1,1),(1,-1,1)]),
        ]
        self.faces = []
        for name, normal, vertices in definitions:
            facing = dot(normal, self.camera.back)
            if facing <= 0.001:
                continue
            polygon = QPolygonF([QPointF(44 + dot(v, self.camera.right) * 22,
                                         43 - dot(v, self.camera.up) * 22) for v in vertices])
            self.faces.append((polygon, name))
            p.setPen(QPen(QColor(ui['ui_border']), 1))
            p.setBrush(QColor(ui['ui_nav_face']) if name in ("Top", "Bottom") else QColor(ui['ui_nav_face_alt']))
            p.drawPolygon(polygon)
            if facing > 0.22:
                font.setPixelSize(9 if facing > 0.8 else 7)
                p.setFont(font)
                p.setPen(QColor(ui['ui_nav_text']))
                p.drawText(polygon.boundingRect(), Qt.AlignmentFlag.AlignCenter, name.upper())
        p.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.last = self.pressed = event.position()
            self.dragged = False
            event.accept()

    def mouseMoveEvent(self, event):
        if self.last is None:
            return
        if (event.position() - self.pressed).manhattanLength() > 3:
            self.dragged = True
        if self.dragged and not self.defer_orbit:
            delta = event.position() - self.last
            self.orbit_requested.emit(delta.x(), delta.y())
        self.last = event.position()

    def mouseReleaseEvent(self, event):
        if self.last is not None and self.dragged and self.defer_orbit:
            delta = event.position() - self.pressed
            self.orbit_requested.emit(delta.x(), delta.y())
        if self.last is not None and not self.dragged:
            for polygon, name in self.faces:
                if polygon.containsPoint(event.position(), Qt.FillRule.OddEvenFill):
                    self.view_requested.emit(name)
                    break
        self.last = self.pressed = None

    def mouseDoubleClickEvent(self, event):
        self.last = self.pressed = None
        self.view_requested.emit("Isometric")


class ViewportNavigation(QFrame):
    """A 36px rail with sibling overlays; every control stays inside its canvas."""

    view_requested = pyqtSignal(str)
    mode_requested = pyqtSignal(str)
    zoom_requested = pyqtSignal(float)
    fit_requested = pyqtSignal()
    draft_requested = pyqtSignal()
    layout_requested = pyqtSignal(bool)
    orbit_requested = pyqtSignal(float, float)

    def __init__(self, viewport):
        super().__init__(viewport)
        self.viewport = viewport
        self.setObjectName("viewport_navigation")
        self.setStyleSheet("""
            QFrame#viewport_navigation { background: #202e3d; border: 1px solid #486074; border-radius: 5px; }
            QToolButton { background: transparent; border: 1px solid transparent; padding: 0; border-radius: 3px; }
            QToolButton:hover { background: #355670; border-color: #73b7d1; }
            QToolButton:checked { background: #176b8f; border-color: #66c9ec; }
        """)
        self.box = QBoxLayout(QBoxLayout.Direction.TopToBottom, self)
        self.box.setContentsMargins(3, 3, 3, 3)
        self.box.setSpacing(2)
        self.orbit_button = self._button("orbit", "Orbit — drag to rotate the model")
        self.pan_button = self._button("pan", "Pan — drag to move the view")
        for button, mode in [(self.orbit_button, "orbit"), (self.pan_button, "pan")]:
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, m=mode: self.set_mode(m))
        self.zoom_in_button = self._button("+", "Zoom in")
        self.zoom_out_button = self._button("−", "Zoom out")
        self.zoom_in_button.clicked.connect(lambda: self.zoom_requested.emit(1.25))
        self.zoom_out_button.clicked.connect(lambda: self.zoom_requested.emit(1 / 1.25))
        self.fit_button = self._button("fit", "Fit the drawing or model")
        self.fit_button.clicked.connect(self.fit_requested)
        self.home_button = self._button("home", "Isometric view")
        self.home_button.clicked.connect(lambda: self.view_requested.emit("Isometric"))
        self.view_selector = QComboBox(viewport)
        self.view_selector.setObjectName("navigation_standard_view")
        self.view_selector.setAccessibleName("Viewport angle and layout")
        self.view_selector.setToolTip("Standard views, free orbit and viewport layout")
        self.view_selector.addItems(["2D drafting", *Camera.PRESETS, "Free orbit", "Single view", "Four views"])
        self.view_selector.setFixedSize(146, 26)
        self.view_selector.setStyleSheet("QComboBox { background:#192635; color:#d9e7f3; border:1px solid #40586e; padding:2px 6px; font-size:11px; }")
        # activated allows selecting the already-current view to realign it.
        self.view_selector.textActivated.connect(self._select_view)
        self.cube = OrientationCube(viewport)
        self.cube.view_requested.connect(self.view_requested)
        self.cube.orbit_requested.connect(self.orbit_requested)
        viewport.installEventFilter(self)
        self.reposition()

    def _button(self, name, tooltip):
        button = QToolButton(self)
        button.setText(name)
        button.setIcon(navigation_icon(name))
        button.setProperty('navigationIcon', name)
        button.setIconSize(QSize(22, 22))
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        button.setFixedSize(28, 28)
        button.setToolTip(tooltip)
        button.setAccessibleName(tooltip)
        self.box.addWidget(button)
        return button

    def _select_view(self, name):
        if name == "2D drafting":
            self.draft_requested.emit()
        elif name in ("Single view", "Four views"):
            self.layout_requested.emit(name == "Four views")
        elif name == "Free orbit":
            self.set_mode("orbit")
        else:
            self.view_requested.emit(name)

    def set_mode(self, mode):
        self.orbit_button.setChecked(mode == "orbit")
        self.pan_button.setChecked(mode == "pan")
        self.mode_requested.emit(mode)

    def sync(self, camera, mode, drafting=False):
        self.cube.camera = camera
        self.cube.update()
        self.view_selector.setCurrentText("2D drafting" if drafting else camera.name)
        self.orbit_button.setChecked(mode == "orbit")
        self.pan_button.setChecked(mode == "pan")

    def eventFilter(self, obj, event):
        if obj is self.viewport and event.type() in (QEvent.Type.Resize, QEvent.Type.Show):
            self.reposition()
        return super().eventFilter(obj, event)

    def reposition(self):
        w, h = self.viewport.width(), self.viewport.height()
        self.cube.move(max(0, w - 96), 36 if w < 260 else 5)
        self.view_selector.move(8, 8)
        # Short tiled panes use a horizontal rail to keep all six actions visible.
        horizontal = h < 300
        self.box.setDirection(QBoxLayout.Direction.LeftToRight if horizontal else QBoxLayout.Direction.TopToBottom)
        self.setFixedSize(184 if horizontal else 36, 36 if horizontal else 184)
        self.move(max(0, w - self.width() - 8), max(36, h - 44) if horizontal else 98)
        for widget in (self, self.cube, self.view_selector):
            widget.show()
            widget.raise_()
