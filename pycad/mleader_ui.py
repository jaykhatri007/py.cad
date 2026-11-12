"""Named multileader styles with a live geometry preview."""

from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QColor, QPainter, QPen, QPolygonF
from PyQt6.QtWidgets import (
    QDialog,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QListWidget,
    QDoubleSpinBox,
    QComboBox,
    QLineEdit,
    QPushButton,
    QInputDialog,
    QMessageBox,
)
from .geometry import Point
from .mleaders import MultileaderEntity, DEFAULT_STYLE, validate_style, edit_style
from .mleader_tools import edit_text, apply_style


class StylePreview(QWidget):
    def __init__(self, manager):
        super().__init__(manager)
        self.manager = manager
        self.setMinimumSize(360, 190)

    def paintEvent(self, event):
        painter = QPainter(self)
        try:
            painter.fillRect(self.rect(), QColor("#171d28"))
            style = self.manager.values()
            validate_style(style)
            h = style["text_height"] * style["scale"]
            e = MultileaderEntity(
                Point(9 * h, 4 * h),
                "ROOM TAG\nFinish note",
                [
                    [Point(0, 0), Point(4 * h, 4 * h)],
                    [Point(h, 7 * h), Point(4 * h, 5 * h)],
                ],
            )
            e._mleader_style = style
            x0, y0, x1, y1 = e.bbox()
            zoom = min(
                (self.width() - 30) / max(x1 - x0, 1e-9),
                (self.height() - 30) / max(y1 - y0, 1e-9),
            )

            def screen(p):
                return QPointF(
                    15 + (p.x - x0) * zoom, self.height() - 15 - (p.y - y0) * zoom
                )

            color = QColor("#ecd27e" if style["color"] == "BYLAYER" else style["color"])
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(QPen(color, 1.4))
            lines, fills, labels = e.geometry()
            for a, b in lines:
                painter.drawLine(screen(a), screen(b))
            painter.setBrush(color)
            for poly in fills:
                painter.drawPolygon(QPolygonF([screen(p) for p in poly]))
            for text, pos, height, rotation in labels:
                painter.save()
                font = painter.font()
                font.setPixelSize(max(1, min(10000, round(height * zoom))))
                painter.setFont(font)
                painter.translate(screen(pos))
                painter.rotate(-rotation)
                painter.drawText(QPointF(0, 0), text)
                painter.restore()
        except ValueError:
            painter.setPen(QColor("#e8bcc2"))
            painter.drawText(
                self.rect(), Qt.AlignmentFlag.AlignCenter, "Enter valid style values"
            )
        finally:
            painter.end()


class MultileaderStyleManager(QDialog):
    def __init__(self, mw):
        super().__init__(mw)
        self.mw, self.doc = mw, mw.document
        self.setWindowTitle("Multileader styles")
        self.resize(680, 500)
        layout = QVBoxLayout(self)
        self.current_label = QLabel()
        layout.addWidget(self.current_label)
        row = QHBoxLayout()
        layout.addLayout(row)
        self.names = QListWidget()
        self.names.setMaximumWidth(185)
        row.addWidget(self.names)
        right = QVBoxLayout()
        row.addLayout(right)
        form = QFormLayout()
        right.addLayout(form)
        self.fields = {}
        for key, label in (
            ("text_height", "Text height"),
            ("arrow_size", "Arrow size"),
            ("landing_length", "Landing length"),
            ("text_gap", "Text gap"),
            ("scale", "Annotation scale"),
        ):
            field = QDoubleSpinBox()
            field.setDecimals(6)
            field.setRange(0.000001 if key in ("text_height", "scale") else 0, 1e6)
            field.valueChanged.connect(lambda *_: self.preview.update())
            self.fields[key] = field
            form.addRow(label, field)
        self.arrow = QComboBox()
        self.arrow.addItems(["Closed", "Open", "None"])
        self.arrow.currentTextChanged.connect(lambda *_: self.preview.update())
        form.addRow("Arrow type", self.arrow)
        self.color = QLineEdit()
        self.color.setPlaceholderText("BYLAYER or #RRGGBB")
        self.color.textChanged.connect(lambda *_: self.preview.update())
        form.addRow("Color", self.color)
        self.preview = StylePreview(self)
        right.addWidget(self.preview)
        note = QLabel(
            "Sizes use drawing units. Scale is dimensionless. Saving a style updates all annotations using it."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        buttons = QHBoxLayout()
        layout.addLayout(buttons)
        for label, callback in (
            ("New…", self.add),
            ("Save changes", self.save),
            ("Set current", self.set_current),
            ("Delete", self.delete),
            ("Apply to selected", self.apply),
        ):
            button = QPushButton(label)
            button.clicked.connect(lambda checked=False, cb=callback: self.perform(cb))
            buttons.addWidget(button)
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        layout.addWidget(close)
        self.names.currentTextChanged.connect(self.load)
        self.refresh(self.doc.current_mleaderstyle)

    def values(self):
        return {
            **{k: field.value() for k, field in self.fields.items()},
            "arrow_type": self.arrow.currentText(),
            "color": self.color.text().strip(),
        }

    def refresh(self, name):
        self.current_label.setText(
            "Current: " + self.doc.current_mleaderstyle + " · " + self.doc.units
        )
        self.names.blockSignals(True)
        self.names.clear()
        self.names.addItems(sorted(self.doc.mleaderstyles, key=str.casefold))
        self.names.setCurrentRow(
            list(sorted(self.doc.mleaderstyles, key=str.casefold)).index(name)
        )
        self.names.blockSignals(False)
        self.load(name)

    def load(self, name):
        style = self.doc.mleaderstyles.get(name, DEFAULT_STYLE)
        for key, field in self.fields.items():
            field.setValue(style[key])
        self.arrow.setCurrentText(style["arrow_type"])
        self.color.setText(style["color"])
        self.preview.update()

    def perform(self, callback):
        try:
            callback()
        except ValueError as ex:
            QMessageBox.warning(self, "Multileader style", str(ex))

    def add(self):
        name, accepted = QInputDialog.getText(self, "New multileader style", "Name:")
        if accepted:
            edit_style(self.doc, "add", name.strip(), self.values())
            self.refresh(name.strip())

    def save(self):
        edit_style(self.doc, "modify", self.names.currentItem().text(), self.values())

    def set_current(self):
        name = self.names.currentItem().text()
        edit_style(self.doc, "current", name)
        self.refresh(name)

    def delete(self):
        edit_style(self.doc, "delete", self.names.currentItem().text())
        self.refresh(self.doc.current_mleaderstyle)

    def apply(self):
        apply_style(self.mw, self.names.currentItem().text())


def style_manager(mw):
    dialog = MultileaderStyleManager(mw)
    try:
        dialog.exec()
    finally:
        dialog.setParent(None)
        dialog.deleteLater()


def commands(mw):
    return {
        "MLEADERSTYLE": lambda: style_manager(mw),
        "MLEADEREDIT": lambda: edit_text(mw),
    }
