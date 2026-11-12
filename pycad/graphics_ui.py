"""Compact graphics settings and an exportable diagnostic report."""

import json
from pathlib import Path
from PyQt6.QtWidgets import (QApplication, QComboBox, QDialog, QDialogButtonBox,
                             QFileDialog, QFormLayout, QLabel, QMessageBox,
                             QPlainTextEdit, QPushButton, QVBoxLayout, QHBoxLayout,
                             QTableWidget, QTableWidgetItem, QHeaderView)
from .graphics import MODES, DRAWING_PATHS


class GraphicsDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.controller = window.graphics
        self.setWindowTitle("PY.cad Graphics · CPU / GPU")
        self.resize(650, 600)
        root = QVBoxLayout(self)
        form = QFormLayout()
        root.addLayout(form)
        self.mode = QComboBox()
        self.mode.setObjectName("graphics_mode")
        for key, label in MODES.items():
            self.mode.addItem(label, key)
        self.mode.setCurrentIndex(list(MODES).index(self.controller.mode))
        form.addRow("Graphics processor", self.mode)
        self.drawing_path=QComboBox()
        self.drawing_path.setObjectName('graphics_drawing_path')
        for key,label in DRAWING_PATHS.items():self.drawing_path.addItem(label,key)
        self.drawing_path.setCurrentIndex(list(DRAWING_PATHS).index(self.controller.drawing_path))
        form.addRow('2D drawing path',self.drawing_path)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setObjectName("graphics_status")
        form.addRow("Status", self.status)
        note = QLabel("GPU accelerates supported display painting through OpenGL; it does not move the entire CAD engine to the GPU. Auto/GPU tests the driver and falls back to CPU if unavailable. Cached drawing favors repeated selection; Direct drawing uses the selected renderer for 2D geometry/hatch paint commands. Calculations and file loading remain on CPU. Direct mode is not guaranteed to be faster.")
        note.setWordWrap(True)
        root.addWidget(note)
        self.processes=QTableWidget(0,2)
        self.processes.setObjectName('graphics_process_execution')
        self.processes.setHorizontalHeaderLabels(['Process','Current execution'])
        self.processes.verticalHeader().hide()
        self.processes.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.processes.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.processes.setFixedHeight(200)
        root.addWidget(self.processes)
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setMaximumHeight(120)
        self.details.setObjectName("graphics_diagnostics")
        root.addWidget(self.details, 1)
        row = QHBoxLayout()
        root.addLayout(row)
        for title, callback in (("Retry detection", self.retry), ("Copy report", self.copy_report), ("Save report…", self.save_report)):
            button = QPushButton(title)
            button.clicked.connect(callback)
            row.addWidget(button)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Apply | QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self.apply)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self.controller.changed.connect(self.refresh)
        self.refresh()

    def report_text(self):
        return json.dumps(self.controller.report(), indent=2, ensure_ascii=False) + "\n"

    def refresh(self):
        backend = "OpenGL" if self.controller.backend == "opengl" else "Software"
        self.status.setText(backend + " · " + self.controller.reason)
        rows=list(self.controller.process_execution().items())
        self.processes.setRowCount(len(rows))
        for row,(name,processor) in enumerate(rows):
            for column,text in enumerate((name,processor)):
                item=QTableWidgetItem(text);item.setToolTip(text);self.processes.setItem(row,column,item)
        self.details.setPlainText(self.report_text())

    def apply(self):
        self.controller.set_drawing_path(self.drawing_path.currentData())
        self.controller.set_mode(self.mode.currentData())

    def retry(self):
        self.controller.set_drawing_path(self.drawing_path.currentData())
        self.controller.set_mode(self.mode.currentData(), retry=True)

    def copy_report(self):
        QApplication.clipboard().setText(self.report_text())

    def save_report(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save graphics report", "PY.cad-graphics.json", "JSON report (*.json)")
        if path:
            try:
                Path(path).write_text(self.report_text(), encoding="utf-8")
            except OSError as ex:
                QMessageBox.warning(self, "Graphics report", str(ex))


def show_dialog(window):
    dialog = GraphicsDialog(window)
    try:
        dialog.exec()
    finally:
        dialog.deleteLater()
