"""Material definitions, embedded textures and small visual previews."""

import base64
from pathlib import Path
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPixmap, QPainter, QBrush, QImage
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QHBoxLayout,
    QComboBox,
    QLineEdit,
    QPushButton,
    QLabel,
    QDoubleSpinBox,
    QColorDialog,
    QFileDialog,
)
from . import materials
from .building_ui import button


def dialog(mw):
    d = QDialog(mw)
    d.setWindowTitle("Materials / Appearance")
    d.resize(430, 330)
    root = QVBoxLayout(d)
    form = QFormLayout()
    choices = QComboBox()
    choices.addItems(
        sorted(
            set(materials.DEFAULTS) | set(mw.document.extensions.get("materials", {}))
        )
    )
    name = QLineEdit()
    color = QPushButton()
    opacity = QDoubleSpinBox()
    opacity.setRange(0, 1)
    opacity.setSingleStep(0.05)
    pattern = QComboBox()
    pattern.addItems(["Solid", "Brick", "Wood", "Tile"])
    texture = QPushButton("Choose texture…")
    preview = QLabel()
    preview.setMinimumHeight(85)
    preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
    form.addRow("Preset / Saved", choices)
    form.addRow("Material name", name)
    form.addRow("Surface color", color)
    form.addRow("Opacity", opacity)
    form.addRow("Pattern", pattern)
    form.addRow("Embedded image", texture)
    root.addLayout(form)
    root.addWidget(preview)
    state = {"color": "#abb0b4", "texture": ""}

    def render():
        pixmap = QPixmap(220, 80)
        pixmap.fill(QColor("#384047"))
        painter = QPainter(pixmap)
        c = QColor(state["color"])
        c.setAlphaF(opacity.value())
        if state["texture"]:
            brush = QBrush(
                QPixmap.fromImage(
                    QImage.fromData(base64.b64decode(state["texture"])).scaled(80, 80)
                )
            )
        else:
            styles = {
                "Solid": Qt.BrushStyle.SolidPattern,
                "Brick": Qt.BrushStyle.CrossPattern,
                "Wood": Qt.BrushStyle.BDiagPattern,
                "Tile": Qt.BrushStyle.DiagCrossPattern,
            }
            brush = QBrush(c, styles[pattern.currentText()])
        painter.fillRect(5, 5, 210, 70, brush)
        painter.end()
        preview.setPixmap(pixmap)
        color.setText(state["color"])

    def load():
        key = choices.currentText()
        r = mw.document.extensions.get("materials", {}).get(
            key, materials.DEFAULTS.get(key)
        )
        name.setText(key)
        state.update(color=r["color"], texture=r["texture"])
        opacity.setValue(r["opacity"])
        pattern.setCurrentText(r["pattern"])
        render()

    def choose_color():
        c = QColorDialog.getColor(QColor(state["color"]), d)
        if c.isValid():
            state["color"] = c.name()
            render()

    def choose_texture():
        path, _ = QFileDialog.getOpenFileName(
            d, "Embedded surface texture", "", "Images (*.png *.jpg *.jpeg *.bmp)"
        )
        if path:
            raw = Path(path).read_bytes()
            if len(raw) > 1024 * 1024:
                raise ValueError("Choose a texture below 1 MiB")
            value = base64.b64encode(raw).decode()
            materials.validate_materials(
                {
                    "materials": {
                        "preview": dict(
                            color=state["color"],
                            opacity=opacity.value(),
                            pattern=pattern.currentText(),
                            texture=value,
                        )
                    }
                }
            )
            state["texture"] = value
            render()

    from .feature_helpers import safe_action

    color.clicked.connect(choose_color)
    texture.clicked.connect(safe_action(d, choose_texture))
    choices.currentIndexChanged.connect(load)
    opacity.valueChanged.connect(render)
    pattern.currentIndexChanged.connect(render)

    def save():
        materials.save_material(
            mw.document,
            name.text(),
            state["color"],
            opacity.value(),
            pattern.currentText(),
            state["texture"],
        )
        mw.refresh_document_ui()

    def assign():
        ids = [e.id for e in mw.canvas.selected_entities]
        if not ids or any(
            e not in mw.document.editable_entities()
            for e in mw.canvas.selected_entities
        ):
            raise ValueError("Select editable objects to assign this material")
        mw.document.undo_stack.beginMacro("Material appearance and assignment")
        try:
            save()
            materials.assign(mw.document, ids, name.text())
        finally:
            mw.document.undo_stack.endMacro()
        mw.refresh_document_ui()

    bar = QHBoxLayout()
    root.addLayout(bar)
    button(bar, "Save material", save, d)
    button(bar, "Assign selection", assign, d)
    button(bar, "Clear texture", lambda: (state.update(texture=""), render()), d)
    button(bar, "Close", d.accept, d)
    load()
    d.exec()
