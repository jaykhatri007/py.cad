"""Dimension-style and layer-property dialogs backed by undoable document edits."""

from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QColor, QUndoCommand, QPainter, QPen, QPolygonF
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QListWidget,
    QLineEdit,
    QTabWidget,
    QWidget,
    QFormLayout,
    QDoubleSpinBox,
    QSpinBox,
    QComboBox,
    QCheckBox,
    QMessageBox,
    QInputDialog,
    QTableWidget,
    QTableWidgetItem,
    QAbstractItemView,
    QColorDialog,
    QHeaderView,
)
from .dimstyles import dimension_label, dimension_geometry, DEFAULT_STYLE
from .geometry import DimensionEntity, Point


class DimensionPreview(QWidget):
    def __init__(self):
        super().__init__()
        self.style = dict(DEFAULT_STYLE)
        self.setMinimumHeight(130)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#111a25"))
        style = self.style
        span = max(100 * style["scale"], 1234.5678)
        sample = DimensionEntity(
            Point(0, 0), Point(span, 0), Point(span / 2, span * 0.15)
        )
        label_sample = DimensionEntity(
            Point(0, 0), Point(1234.5678, 0), Point(600, 150)
        )
        lines, fills, anchor, height = dimension_geometry(sample, style)
        zoom = min(
            (self.width() - 100) / span, (self.height() - 40) / (span * 0.3 + height)
        )

        def screen(p):
            return QPointF(50 + p.x * zoom, self.height() - 30 - p.y * zoom)

        painter.setPen(
            QPen(
                QColor("#79d5ef")
                if style["color"] == "BYLAYER"
                else QColor(style["color"]),
                1.2,
            )
        )
        for a, b in lines:
            painter.drawLine(screen(a), screen(b))
        painter.setBrush(painter.pen().color())
        for triangle in fills:
            painter.drawPolygon(QPolygonF([screen(p) for p in triangle]))
        font = painter.font()
        font.setPixelSize(max(10, min(28, round(height * zoom))))
        painter.setFont(font)
        label = dimension_label(label_sample, style)
        pos = screen(anchor)
        pos.setX(pos.x() - painter.fontMetrics().horizontalAdvance(label) / 2)
        painter.drawText(pos, label)
        painter.setPen(QColor("#6c8398"))
        painter.drawText(12, 18, "LIVE STYLE PREVIEW")
        painter.end()


class AssignStyleCommand(QUndoCommand):
    def __init__(self, document, entities, name):
        super().__init__("Apply dimension style")
        self.targets = [
            e
            for e in entities
            if isinstance(e, DimensionEntity) and not document.layers.is_locked(e.layer)
        ]
        self.before = [e.style_name for e in self.targets]
        self.name = name

    def redo(self):
        for entity in self.targets:
            entity.style_name = self.name

    def undo(self):
        for entity, name in zip(self.targets, self.before):
            entity.style_name = name


class DimensionStyleManager(QDialog):
    def __init__(self, mw):
        super().__init__(mw)
        self.mw = mw
        self.doc = mw.document
        self.setWindowTitle("Dimension Style Manager")
        self.resize(820, 610)
        root = QVBoxLayout(self)
        self.current = QLabel()
        root.addWidget(self.current)
        row = QHBoxLayout()
        root.addLayout(row, 1)
        left = QVBoxLayout()
        row.addLayout(left)
        self.styles = QListWidget()
        self.styles.setMinimumWidth(190)
        left.addWidget(self.styles)
        for text, callback in [
            ("New from selected…", self.new_style),
            ("Set current", self.set_current),
            ("Delete", self.delete_style),
            ("Apply to selected dimensions", self.apply_selected),
        ]:
            button = QPushButton(text)
            button.clicked.connect(callback)
            left.addWidget(button)
        self.tabs = QTabWidget()
        row.addWidget(self.tabs, 1)
        self.fields = {}
        for title, keys in [
            ("Lines", ["extension_offset", "extension_beyond"]),
            ("Symbols && arrows", ["arrow_type", "arrow_size"]),
            ("Text", ["text_height", "text_gap", "color"]),
            (
                "Units && scale",
                ["precision", "prefix", "suffix", "suppress_zeros", "scale"],
            ),
        ]:
            page = QWidget()
            form = QFormLayout(page)
            for key in keys:
                if key == "precision":
                    widget = QSpinBox()
                    widget.setRange(0, 8)
                elif key == "arrow_type":
                    widget = QComboBox()
                    widget.addItems(["Closed", "Open", "Tick"])
                elif key == "suppress_zeros":
                    widget = QCheckBox("Remove trailing decimal zeros")
                elif key in ("prefix", "suffix", "color"):
                    widget = QLineEdit()
                    widget.setMaxLength(64)
                else:
                    widget = QDoubleSpinBox()
                    widget.setDecimals(4)
                    widget.setRange(
                        0.0001 if key in ("text_height", "arrow_size", "scale") else 0,
                        1e6,
                    )
                widget.setObjectName("dimstyle_" + key)
                self.fields[key] = widget
                form.addRow(key.replace("_", " ").capitalize(), widget)
                signal = (
                    widget.valueChanged
                    if isinstance(widget, (QSpinBox, QDoubleSpinBox))
                    else widget.currentTextChanged
                    if isinstance(widget, QComboBox)
                    else widget.toggled
                    if isinstance(widget, QCheckBox)
                    else widget.textChanged
                )
                signal.connect(self.update_preview)
            self.tabs.addTab(page, title)
        self.preview = DimensionPreview()
        root.addWidget(self.preview)
        root.addWidget(
            QLabel(
                "Sizes are in drawing units × scale. Saved changes update all dimensions using this style."
            )
        )
        row = QHBoxLayout()
        root.addLayout(row)
        row.addStretch()
        save = QPushButton("Save style changes")
        save.clicked.connect(self.save_style)
        row.addWidget(save)
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        row.addWidget(close)
        self.styles.currentTextChanged.connect(self.load_style)
        self.refresh()

    def selected(self):
        item = self.styles.currentItem()
        return item.text() if item else "Standard"

    def refresh(self, selected=None):
        selected = selected or self.selected()
        self.styles.blockSignals(True)
        self.styles.clear()
        self.styles.addItems(self.doc.dimstyles)
        matches = self.styles.findItems(selected, Qt.MatchFlag.MatchExactly)
        self.styles.setCurrentItem(matches[0] if matches else self.styles.item(0))
        self.styles.blockSignals(False)
        self.current.setText("Current dimension style: " + self.doc.current_dimstyle)
        self.load_style(self.selected())

    def load_style(self, name):
        style = self.doc.dimstyles.get(name, DEFAULT_STYLE)
        for key, widget in self.fields.items():
            value = style[key]
            if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                widget.setValue(value)
            elif isinstance(widget, QComboBox):
                widget.setCurrentText(value)
            elif isinstance(widget, QCheckBox):
                widget.setChecked(value)
            else:
                widget.setText(value)
        self.update_preview()

    def values(self):
        result = {}
        for key, widget in self.fields.items():
            if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                result[key] = widget.value()
            elif isinstance(widget, QComboBox):
                result[key] = widget.currentText()
            elif isinstance(widget, QCheckBox):
                result[key] = widget.isChecked()
            else:
                result[key] = widget.text()
        return result

    def update_preview(self, *args):
        if len(self.fields) != len(DEFAULT_STYLE) or not hasattr(self, "preview"):
            return
        values = self.values()
        self.preview.style = values
        self.preview.update()

    def perform(self, operation, name, value=None):
        try:
            self.doc.edit_dimstyle(operation, name, value)
        except ValueError as ex:
            QMessageBox.warning(self, "Dimension style", str(ex))
            return False
        self.refresh(name)
        self.mw.refresh_document_ui()
        return True

    def new_style(self):
        name, ok = QInputDialog.getText(self, "New dimension style", "Name:")
        if ok:
            self.perform("add", name.strip(), self.values())

    def set_current(self):
        self.perform("current", self.selected())

    def delete_style(self):
        self.perform("delete", self.selected())

    def save_style(self):
        self.perform("modify", self.selected(), self.values())

    def apply_selected(self):
        command = AssignStyleCommand(
            self.doc, self.mw.canvas.selected_entities, self.selected()
        )
        if not command.targets:
            QMessageBox.information(
                self, "Apply style", "Select editable dimensions in the drawing first."
            )
            return
        self.doc.undo_stack.push(command)
        self.mw.refresh_document_ui()


class LayerPropertiesManager(QDialog):
    HEADERS = [
        "Current",
        "Name",
        "On",
        "Freeze",
        "Lock",
        "Color",
        "Linetype",
        "Weight (mm)",
        "Plot",
    ]

    def __init__(self, mw):
        super().__init__(mw)
        self.mw = mw
        self.doc = mw.document
        self.setWindowTitle("Layer Properties Manager")
        self.resize(740, 390)
        self.setMinimumSize(610, 310)
        root = QVBoxLayout(self)
        root.setContentsMargins(9, 9, 9, 9)
        root.setSpacing(6)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Filter layers by name…")
        filter_row=QHBoxLayout();filter_row.addWidget(self.search)
        self.property_filter=QComboBox();self.property_filter.addItems(["All","Visible","Hidden","Locked","Unlocked","Plot","No plot","Dashed"]);filter_row.addWidget(self.property_filter)
        states=QPushButton("States…");states.clicked.connect(lambda:__import__("pycad.layers_plus",fromlist=["state_dialog"]).state_dialog(mw));filter_row.addWidget(states)
        root.addLayout(filter_row)
        self.table = QTableWidget(0, len(self.HEADERS))
        self.table.setStyleSheet('QHeaderView::section { padding:3px; font-size:11px; } QComboBox { padding:1px; font-size:11px; }')
        self.table.setHorizontalHeaderLabels(['', 'Layer', 'On', 'Frz', 'Lock', 'Color', 'Type', 'mm', 'Plot'])
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(29)
        self.table.horizontalHeader().setFixedHeight(28)
        for column, label in enumerate(self.HEADERS):
            self.table.horizontalHeaderItem(column).setToolTip(label)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        for column, width in enumerate((30, 150, 34, 34, 39, 44, 116, 64, 37)):
            self.table.setColumnWidth(column, width)
        self.table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.Stretch
        )
        root.addWidget(self.table, 1)
        row = QHBoxLayout()
        root.addLayout(row)
        for text, callback in [
            ("New…", self.new_layer),
            ("Rename…", self.rename_layer),
            ("Delete", lambda: self.edit("delete")),
            ("Set current", lambda: self.edit("current")),
            ("Isolate", self.isolate),
            ("Show all", self.show_all),
            ("Close", self.accept),
        ]:
            button = QPushButton(text)
            button.clicked.connect(callback)
            row.addWidget(button)
        self.status = QLabel(
            "Layer 0 and layers containing drawing or 3D geometry cannot be deleted. Changes are undoable."
        )
        self.status.setWordWrap(True)
        self.status.setStyleSheet('font-size:10px;')
        root.addWidget(self.status)
        self.search.textChanged.connect(self.filter_rows)
        self.property_filter.currentTextChanged.connect(self.filter_rows)
        self.refresh()

    def selected(self):
        row = self.table.currentRow()
        return self.table.item(row, 1).text() if row >= 0 else None

    def refresh(self, selected=None):
        selected = selected or self.selected() or self.doc.layers.current_layer
        self.table.setRowCount(0)
        for row, (name, props) in enumerate(self.doc.layers.layers.items()):
            self.table.insertRow(row)
            self.table.setItem(
                row,
                0,
                QTableWidgetItem("●" if name == self.doc.layers.current_layer else ""),
            )
            self.table.setItem(row, 1, QTableWidgetItem(name))
            for column, key in (
                (2, "visible"),
                (3, "frozen"),
                (4, "locked"),
                (8, "plot"),
            ):
                widget = QCheckBox()
                widget.setChecked(props.get(key, key in ("visible", "plot")))
                widget.toggled.connect(
                    lambda value, n=name, k=key: self.edit(k, value, n)
                )
                self.table.setCellWidget(row, column, widget)
            color = QPushButton('')
            color.setToolTip(props['color']+' — select color')
            color.setStyleSheet('background:'+props['color']+';border:2px solid #738293;padding:0;')
            color.clicked.connect(lambda checked=False, n=name: self.choose_color(n))
            self.table.setCellWidget(row, 5, color)
            lt = QComboBox()
            from .linetypes import populate_combo
            populate_combo(lt)
            lt.addItems(sorted(self.doc.extensions.get("office_linetypes",{})))
            lt.setCurrentText(props.get("linetype", "CONTINUOUS"))
            lt.currentTextChanged.connect(
                lambda value, n=name: self.edit("linetype", value, n)
            )
            self.table.setCellWidget(row, 6, lt)
            from .layers import LINEWEIGHTS

            weight = QComboBox()
            weight.addItems([f"{v:.2f}" for v in LINEWEIGHTS])
            weight.setCurrentText(f"{props.get('lineweight', 0.25):.2f}")
            weight.currentTextChanged.connect(
                lambda value, n=name: self.edit("lineweight", float(value), n)
            )
            self.table.setCellWidget(row, 7, weight)
            if name == selected:
                self.table.selectRow(row)
        self.filter_rows()

    def filter_rows(self, *args):
        query = self.search.text().casefold()
        for row in range(self.table.rowCount()):
            self.table.setRowHidden(
                row, query not in self.table.item(row, 1).text().casefold() or not __import__("pycad.layers_plus",fromlist=["matches"]).matches(self.doc.layers.layers[self.table.item(row,1).text()],self.property_filter.currentText())
            )

    def edit(self, operation, value=None, name=None):
        name = name or self.selected()
        if name is None:
            return
        try:
            self.doc.edit_layer(operation, name, value)
        except ValueError as ex:
            QMessageBox.warning(self, "Layer properties", str(ex))
        self.mw.layer_panel.refresh()
        self.mw.refresh_document_ui()
        # Defer rebuilding cell editors until the originating Qt signal unwinds.
        from PyQt6.QtCore import QTimer

        QTimer.singleShot(
            0, lambda: self.refresh(value if operation == "rename" else name)
        )

    def new_layer(self):
        name, ok = QInputDialog.getText(self, "New layer", "Name:")
        if ok:
            self.edit("add", "#FFFFFF", name.strip())

    def rename_layer(self):
        old = self.selected()
        if not old:
            return
        name, ok = QInputDialog.getText(self, "Rename layer", "Name:", text=old)
        if ok:
            self.edit("rename", name.strip(), old)

    def choose_color(self, name):
        value = QColorDialog.getColor(
            QColor(self.doc.layers.layers[name]["color"]), self
        )
        if value.isValid():
            self.edit("color", value.name(), name)

    def isolate(self):
        selected = self.selected()
        if not selected:
            return
        self.doc.undo_stack.beginMacro("Isolate layer")
        try:
            self.doc.edit_layer("frozen", selected, False)
            for name in self.doc.layers.names():
                self.doc.edit_layer("visible", name, name == selected)
        finally:
            self.doc.undo_stack.endMacro()
        self.mw.layer_panel.refresh()
        self.refresh()

    def show_all(self):
        self.doc.undo_stack.beginMacro("Show all layers")
        try:
            for name in self.doc.layers.names():
                self.doc.edit_layer("visible", name, True)
                self.doc.edit_layer("frozen", name, False)
        finally:
            self.doc.undo_stack.endMacro()
        self.mw.layer_panel.refresh()
        self.refresh()
