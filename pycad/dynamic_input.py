"""Small in-viewport editors for exact point input, sharing the tool click path."""

import math
from PyQt6.QtCore import QEvent, QPoint, Qt
from PyQt6.QtWidgets import QFrame, QLabel, QLineEdit, QGridLayout
from .measurements import overlay_rect


def input_context(tool):
    if tool is None:
        return None
    points = tool.points
    if tool.name in ("LINE", "PLINE", "DIST", "RAY", "XLINE", "SPLINE") and points:
        return points[-1], "polar"
    if tool.name == "RECTANGLE" and points:
        return points[0], "rectangle"
    if tool.name == "CIRCLE" and points:
        return points[0], "radius"
    if tool.name == "ARC" and len(points) == 1:
        return points[0], "polar"
    if tool.name == "ELLIPSE" and points:
        return points[0], "radius" if len(points) > 1 else "polar"
    if tool.name in ("MOVE", "COPY") and tool.base_point is not None:
        return tool.base_point, "polar"
    if tool.name == "STRETCH" and len(points) == 3:
        return points[-1], "polar"
    return None


def constrained_point(base, raw, mode, values):
    dx, dy = raw[0] - base.x, raw[1] - base.y
    first, second = values
    if mode == "rectangle":
        if first is not None:
            dx = math.copysign(first, dx if dx else 1)
        if second is not None:
            dy = math.copysign(second, dy if dy else 1)
        return base.x + dx, base.y + dy
    distance = math.hypot(dx, dy) if first is None else first
    angle = (
        math.atan2(dy, dx)
        if second is None or mode == "radius"
        else math.radians(second % 360)
    )
    return base.x + distance * math.cos(angle), base.y + distance * math.sin(angle)


class DynamicInput(QFrame):
    def __init__(self, window, viewport):
        super().__init__(viewport)
        self.mw, self.viewport = window, viewport
        self.active = False
        self.raw = None
        self.pointer = QPoint(0, 0)
        self.locks = [None, None]
        self.context = None
        self.setObjectName("dynamic_dimension_input")
        self.setStyleSheet("""
          QFrame#dynamic_dimension_input { background:#102d38; border:1px solid #54c4c0; border-radius:4px; }
          QLabel { color:#b8d9df; background:transparent; border:0; font-size:10px; }
          QLineEdit { color:#efffff; background:#10212e; border:1px solid #526d7c; border-radius:2px; padding:3px; font-size:12px; }
          QLineEdit:focus { border:1px solid #78ead5; }
        """)
        layout = QGridLayout(self)
        layout.setContentsMargins(7, 5, 7, 5)
        layout.setSpacing(4)
        self.labels = []
        self.fields = []
        for i in range(2):
            label = QLabel()
            field = QLineEdit()
            field.setMaxLength(48)
            field.setMinimumWidth(0)
            field.setObjectName("dynamic_distance" if i == 0 else "dynamic_angle")
            field.installEventFilter(self)
            field.textEdited.connect(lambda text, i=i: self.edited(i))
            layout.addWidget(label, 0, i)
            layout.addWidget(field, 1, i)
            self.labels.append(label)
            self.fields.append(field)
        self.hint = QLabel("Tab locks / next · Enter accepts · Esc cancels")
        layout.addWidget(self.hint, 2, 0, 1, 2)
        self.hide()
        viewport.installEventFilter(self)

    def available(self):
        return (
            self.mw.dynamic_action.isChecked()
            and self.mw.document.current_space == "Model"
            and self.mw.viewport_stack.currentWidget() is self.mw.canvas
            and input_context(self.mw.current_tool) is not None
        )

    def reset(self):
        self.active = False
        self.context = None
        self.locks = [None, None]
        for f in self.fields:
            f.clear()
        self.hide()

    def values(self, strict=False):
        values = list(self.locks)
        mode = self.context[1] if self.context else "polar"
        for i, f in enumerate(self.fields):
            if i == 1 and mode == "radius":
                values[i] = None
                continue
            if f.text().strip():
                try:
                    value = float(f.text())
                    if (
                        not math.isfinite(value)
                        or abs(value) > 1e12
                        or (i == 0 or mode == "rectangle")
                        and value <= 0
                    ):
                        raise ValueError()
                    values[i] = value
                except ValueError:
                    if strict:
                        raise ValueError(
                            "Use a positive finite length and a finite angle in degrees"
                        )
        return values

    def point(self, x, y):
        self.raw = (x, y)
        if not self.active or not self.context:
            return x, y
        if not self.available():
            self.reset()
            return x, y
        return constrained_point(self.context[0], self.raw, self.context[1], self.values())

    def begin(self, text=None):
        if not self.available():
            return False
        self.mw.dismiss_viewport_input(clear=True)
        self.context = input_context(self.mw.current_tool)
        self.active = True
        if self.raw is None:
            self.raw = self.mw.current_world_pos or self.context[0].as_tuple()
        if text is not None:
            self.fields[0].setText(text)
        self.refresh()
        self.fields[0].setFocus()
        self.fields[0].setCursorPosition(len(self.fields[0].text()))
        self.edited(0)
        return True

    def edited(self, index):
        self.locks[index] = None
        self.hint.setText("Tab locks / next · Enter accepts · Esc cancels")
        self.update_preview()

    def update_preview(self):
        if self.active and self.raw is not None:
            x, y = self.raw
            self.mw._on_mouse_moved(x, y, "")
            self.mw.canvas.viewport().update()
        self.refresh()

    def refresh(self):
        if not self.active:
            return
        if not self.available():
            self.reset()
            return
        base, mode = self.context
        raw = self.raw or base.as_tuple()
        dx, dy = raw[0] - base.x, raw[1] - base.y
        defaults = (
            (abs(dx), abs(dy))
            if mode == "rectangle"
            else (math.hypot(dx, dy), math.degrees(math.atan2(dy, dx)) % 360)
        )
        names = (
            ("Width", "Height")
            if mode == "rectangle"
            else (
                "Radius"
                if mode == "radius" or self.mw.current_tool.name == "ARC"
                else "Length",
                "Angle °",
            )
        )
        for i, (label, field) in enumerate(zip(self.labels, self.fields)):
            shown = i == 0 or mode != "radius"
            label.setVisible(shown)
            field.setVisible(shown)
            suffix = (
                " (" + self.mw.document.units + ")"
                if i == 0 or mode == "rectangle"
                else ""
            )
            label.setText(
                names[i] + suffix + (" · locked" if self.locks[i] is not None else "")
            )
            field.setPlaceholderText(f"{defaults[i]:.8g}")
        self.setFixedWidth(min(300, max(180, self.viewport.width() - 12)))
        self.adjustSize()
        rect = overlay_rect(self.pointer, self.size(), self.viewport.rect())
        if rect:
            self.setGeometry(rect)
        self.show()
        self.raise_()

    def validate(self):
        try:
            values = self.values(True)
            if self.context and self.raw:
                from .validation import finite

                for v in constrained_point(
                    self.context[0], self.raw, self.context[1], values
                ):
                    finite(v, "Coordinate")
            return True
        except ValueError as ex:
            self.hint.setText(str(ex))
            self.mw.statusBar().showMessage(str(ex), 5000)
            return False

    def accept_point(self, x=None, y=None):
        if x is not None:
            self.raw = (x, y)
        if not self.validate():
            return False
        raw = (x, y) if x is not None else self.raw
        if raw is None:
            return False
        point = constrained_point(
            self.context[0], raw, self.context[1], self.values(True)
        )
        self.reset()
        self.mw._on_world_clicked(*point, "", Qt.MouseButton.LeftButton.value)
        self.mw.focus_active_viewport()
        return True

    def route(self, event):
        if not self.available() or self.active:
            return False
        if event.modifiers() & (
            Qt.KeyboardModifier.ControlModifier
            | Qt.KeyboardModifier.AltModifier
            | Qt.KeyboardModifier.MetaModifier
        ):
            return False
        if event.key() == Qt.Key.Key_Tab:
            return self.begin()
        if event.text() and event.text() in "0123456789.+-":
            return self.begin(event.text())
        return False

    def eventFilter(self, obj, event):
        if not hasattr(self, 'viewport') or not hasattr(self, 'fields'):
            return False
        if obj is self.viewport:
            if event.type() == QEvent.Type.MouseMove:
                self.pointer = event.position().toPoint()
                self.refresh()
            elif event.type() == QEvent.Type.Resize:
                self.refresh()
            elif event.type() == QEvent.Type.Hide:
                self.reset()
        elif obj in self.fields and event.type() == QEvent.Type.KeyPress:
            i = self.fields.index(obj)
            if event.key() in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
                if self.validate():
                    self.locks[i] = self.values(True)[i]
                    self.fields[0 if self.context[1] == "radius" else 1 - i].setFocus()
                    self.fields[0 if self.context[1] == "radius" else 1 - i].selectAll()
                    self.refresh()
                return True
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
                if not event.isAutoRepeat():
                    self.accept_point()
                return True
            if event.key() == Qt.Key.Key_Escape:
                self.reset()
                self.mw.cancel_command()
                return True
            if event.key() == Qt.Key.Key_Backspace and not obj.text():
                self.locks[i] = None
                self.update_preview()
            if event.text() in (",", "<", "@"):
                # Hand coordinate syntax back to the established command editor.
                text = (
                    "@" if event.text() == "@" else self.fields[0].text() + event.text()
                )
                self.reset()
                self.mw.canvas.command_overlay.begin()
                self.mw.command_line.setText(text)
                self.mw.command_line.setFocus()
                return True
        return super().eventFilter(obj, event)
