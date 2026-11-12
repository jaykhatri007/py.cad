"""Named whole-object text formatting and a compact style manager."""

import copy
import math
from PyQt6.QtGui import QUndoCommand, QPainter, QFontMetricsF
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QHBoxLayout,
    QComboBox,
    QFontComboBox,
    QDoubleSpinBox,
    QCheckBox,
    QPushButton,
    QInputDialog,
    QLabel,
    QMessageBox,
    QDialogButtonBox,
    QWidget,
)
from .geometry import TextEntity
from .document import SetAttrCommand

DEFAULT_STYLE = dict(
    font_family="Sans Serif",
    height=2.5,
    width_factor=1.0,
    bold=False,
    italic=False,
    oblique=0.0,
)


def validate_style(style):
    if not isinstance(style, dict) or set(style) != set(DEFAULT_STYLE):
        raise ValueError("Invalid text style fields")
    if (
        not isinstance(style["font_family"], str)
        or not 1 <= len(style["font_family"]) <= 80
        or any(ord(c) < 32 for c in style["font_family"])
    ):
        raise ValueError("Invalid font family")
    for k in ("height", "width_factor", "oblique"):
        if type(style[k]) not in (int, float) or not math.isfinite(style[k]):
            raise ValueError("Text style numbers must be finite")
    if (
        not 0 < style["height"] <= 1e6
        or not 0.1 <= style["width_factor"] <= 10
        or not -60 <= style["oblique"] <= 60
    ):
        raise ValueError(
            "Text height, width factor or oblique angle is outside the supported range"
        )
    if any(type(style[k]) is not bool for k in ("bold", "italic")):
        raise ValueError("Font flags must be boolean")
    return style


def style_for(doc, e):
    return doc.textstyles.get(e.style_name, DEFAULT_STYLE)


class StyleCommand(QUndoCommand):
    def __init__(self, doc, styles, current):
        super().__init__("Text style")
        self.doc = doc
        self.before = copy.deepcopy(doc.textstyles), doc.current_textstyle
        self.after = copy.deepcopy(styles), current

    def apply(self, state):
        self.doc.textstyles, self.doc.current_textstyle = copy.deepcopy(state)

    def redo(self):
        self.apply(self.after)

    def undo(self):
        self.apply(self.before)


def edit_style(doc, operation, name, value=None):
    from .validation import name as validate_name

    validate_name(name, "Text style name")
    styles = copy.deepcopy(doc.textstyles)
    current = doc.current_textstyle
    if operation == "add":
        if len(styles) >= 1000 or any(n.casefold() == name.casefold() for n in styles):
            raise ValueError("Style name must be unique; use at most 1,000 styles")
        styles[name] = copy.deepcopy(validate_style(value or styles[current]))
    elif name not in styles:
        raise ValueError("Text style is missing")
    elif operation == "modify":
        styles[name] = copy.deepcopy(validate_style(value))
    elif operation == "current":
        current = name
    elif operation == "delete":
        all_entities = doc.entities + [
            e for b in doc.blocks.values() for e in b.entities
        ]
        if (
            name == "Standard"
            or name == current
            or any(e.kind == "TEXT" and e.style_name == name for e in all_entities)
            or any(spec["style_name"]==name for block in doc.blocks.values() for spec in block.attributes)
        ):
            raise ValueError(
                "Standard, current and referenced styles cannot be deleted"
            )
        del styles[name]
    else:
        raise ValueError("Unknown style operation")
    from .validation import finite

    for e in doc.entities + [e for b in doc.blocks.values() for e in b.entities]:
        if e.kind == "TEXT":
            candidate = e.clone()
            candidate._text_style = styles[e.style_name]
            for coordinate in candidate.bbox():
                finite(coordinate, "Text extent")
    if styles != doc.textstyles or current != doc.current_textstyle:
        doc.undo_stack.push(StyleCommand(doc, styles, current))


def apply_style(mw, name):
    items = [
        e
        for e in mw.canvas.selected_entities
        if e.kind == "TEXT" and e in mw.document.editable_entities()
    ]
    if not items:
        raise ValueError("Select visible, unlocked text first")
    if name not in mw.document.textstyles:
        raise ValueError("Text style is missing")
    from .validation import finite

    for e in items:
        candidate = e.clone()
        candidate._text_style = mw.document.textstyles[name]
        for coordinate in candidate.bbox():
            finite(coordinate, "Text bounds")
    mw.document.undo_stack.beginMacro("Apply text style")
    for e in items:
        if e.style_name != name:
            mw.document.undo_stack.push(
                SetAttrCommand(mw.document, e, "style_name", e.style_name, name)
            )
    mw.document.undo_stack.endMacro()


class TextStylePreview(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.width_factor, self.oblique = 1.0, 0.0
        self.setMinimumHeight(48)
        self.setToolTip("Font and whole-text formatting preview, fitted to this panel")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(self.palette().color(self.foregroundRole()))
        font = self.font()
        painter.setFont(font)
        text = "Aa 123 — Room finish"
        width = QFontMetricsF(font).horizontalAdvance(text) * self.width_factor
        fit = min(1.0, (self.width() - 24) / max(width + 30, 1))
        painter.translate(12, self.height() / 2 + 8 * fit)
        painter.scale(fit, fit)
        painter.shear(-math.tan(math.radians(self.oblique)), 0)
        painter.scale(self.width_factor, 1)
        painter.drawText(QPointF(0, 0), text)
        painter.end()


class TextStyleManager(QDialog):
    def __init__(self, mw):
        super().__init__(mw)
        self.mw, self.doc = mw, mw.document
        self.setWindowTitle("Text styles")
        self.resize(480, 340)
        root = QVBoxLayout(self)
        form = QFormLayout()
        root.addLayout(form)
        self.names = QComboBox()
        self.names.addItems(self.doc.textstyles)
        form.addRow("Style", self.names)
        self.font = QFontComboBox()
        form.addRow("Font family", self.font)
        self.height = QDoubleSpinBox()
        self.height.setDecimals(9)
        self.height.setRange(0.000000001, 1e6)
        form.addRow("Default height (new text)", self.height)
        self.width = QDoubleSpinBox()
        self.width.setRange(0.1, 10)
        self.width.setDecimals(3)
        form.addRow("Width factor", self.width)
        self.oblique = QDoubleSpinBox()
        self.oblique.setRange(-60, 60)
        form.addRow("Oblique angle", self.oblique)
        self.bold = QCheckBox("Bold")
        self.italic = QCheckBox("Italic")
        form.addRow(self.bold, self.italic)
        self.preview = TextStylePreview()
        root.addWidget(self.preview)
        self.current = QLabel()
        self.current.setTextFormat(Qt.TextFormat.PlainText)
        root.addWidget(self.current)
        row = QHBoxLayout()
        root.addLayout(row)
        for label, callback in (
            ("New…", self.add),
            ("Save", self.save),
            ("Current", self.set_current),
            ("Delete", self.delete),
            ("Apply selected", self.apply_selected),
        ):
            b = QPushButton(label)
            b.clicked.connect(lambda checked=False, cb=callback: self.perform(cb))
            row.addWidget(b)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.accept)
        root.addWidget(buttons)
        self.names.currentTextChanged.connect(self.load)
        self.font.currentFontChanged.connect(self.update_preview)
        self.bold.toggled.connect(self.update_preview)
        self.italic.toggled.connect(self.update_preview)
        self.width.valueChanged.connect(self.update_preview)
        self.oblique.valueChanged.connect(self.update_preview)
        self.names.setCurrentText(self.doc.current_textstyle)
        self.load(self.names.currentText())

    def load(self, name):
        from PyQt6.QtGui import QFont

        s = self.doc.textstyles[name]
        self.font.setCurrentFont(QFont(s["font_family"]))
        self.height.setValue(s["height"])
        self.width.setValue(s["width_factor"])
        self.oblique.setValue(s["oblique"])
        self.bold.setChecked(s["bold"])
        self.italic.setChecked(s["italic"])
        self.current.setText("Current: " + self.doc.current_textstyle)
        self.update_preview()

    def values(self):
        return dict(
            font_family=self.font.currentFont().family(),
            height=self.height.value(),
            width_factor=self.width.value(),
            oblique=self.oblique.value(),
            bold=self.bold.isChecked(),
            italic=self.italic.isChecked(),
        )

    def update_preview(self, *args):
        font = self.font.currentFont()
        font.setPixelSize(23)
        font.setBold(self.bold.isChecked())
        font.setItalic(self.italic.isChecked())
        self.preview.setFont(font)
        self.preview.width_factor, self.preview.oblique = (
            self.width.value(),
            self.oblique.value(),
        )
        self.preview.update()

    def perform(self, cb):
        try:
            cb()
        except ValueError as ex:
            QMessageBox.warning(self, "Text style", str(ex))

    def add(self):
        name, ok = QInputDialog.getText(self, "New text style", "Name:")
        if ok:
            edit_style(self.doc, "add", name.strip(), self.values())
            self.names.addItem(name.strip())
            self.names.setCurrentText(name.strip())

    def save(self):
        edit_style(self.doc, "modify", self.names.currentText(), self.values())

    def set_current(self):
        edit_style(self.doc, "current", self.names.currentText())
        self.load(self.names.currentText())

    def delete(self):
        edit_style(self.doc, "delete", self.names.currentText())
        self.names.removeItem(self.names.currentIndex())

    def apply_selected(self):
        apply_style(self.mw, self.names.currentText())


def manager(mw):
    dialog = TextStyleManager(mw)
    try:
        dialog.exec()
    finally:
        dialog.setParent(None)
        dialog.deleteLater()


def make_text(doc, position, text, **kwargs):
    name = doc.current_textstyle
    return TextEntity(
        position, text, height=doc.textstyles[name]["height"], style_name=name, **kwargs
    )


def edit_text(mw):
    from PyQt6.QtWidgets import QPlainTextEdit

    selected = [
        e
        for e in mw.canvas.selected_entities
        if e.kind == "TEXT" and e in mw.document.editable_entities()
    ]
    if len(selected) != 1:
        raise ValueError("Select one visible, unlocked text object first")
    entity = selected[0]
    dialog = QDialog(mw)
    dialog.setWindowTitle("Edit text / formatting")
    dialog.resize(500, 360)
    root = QVBoxLayout(dialog)
    editor = QPlainTextEdit(entity.text)
    root.addWidget(editor)
    form = QFormLayout()
    root.addLayout(form)
    style = QComboBox()
    style.addItems(mw.document.textstyles)
    style.setCurrentText(entity.style_name)
    form.addRow("Style", style)
    height = QDoubleSpinBox()
    height.setDecimals(9)
    height.setRange(0.000000001, 1e6)
    height.setValue(entity.height)
    form.addRow("Height", height)
    rotation = QDoubleSpinBox()
    rotation.setRange(-360000, 360000)
    rotation.setDecimals(4)
    rotation.setValue(entity.rotation)
    form.addRow("Rotation", rotation)
    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
    )
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    root.addWidget(buttons)
    try:
        if dialog.exec() == QDialog.DialogCode.Accepted:
            from .native_io import document_to_dict, entity_to_dict, document_from_dict

            candidate = entity.clone()
            candidate.id = entity.id
            candidate.text = editor.toPlainText()
            if candidate.text!=entity.text: candidate.rich_html=""
            candidate.height = height.value()
            candidate.rotation = rotation.value()
            candidate.style_name = style.currentText()
            payload = document_to_dict(mw.document)
            payload["entities"] = [
                entity_to_dict(candidate) if e["data"]["id"] == entity.id else e
                for e in payload["entities"]
            ]
            document_from_dict(payload)
            changes = [
                k
                for k in ("text", "height", "rotation", "style_name", "rich_html")
                if getattr(entity, k) != getattr(candidate, k)
            ]
            if changes:
                mw.document.undo_stack.beginMacro("Edit text / formatting")
                for k in changes:
                    mw.document.undo_stack.push(
                        SetAttrCommand(
                            mw.document,
                            entity,
                            k,
                            getattr(entity, k),
                            getattr(candidate, k),
                        )
                    )
                mw.document.undo_stack.endMacro()
    finally:
        dialog.setParent(None)
        dialog.deleteLater()
