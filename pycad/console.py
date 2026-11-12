"""
console.py
A dockable Python console: a code input box, a Run button, and a read-only
output log. Code runs with `api` (a ScriptAPI bound to the current document),
`doc` (the raw Document), and the core geometry classes already in scope.

This is intentionally a plain `exec()` in an in-process namespace - there's
no sandboxing. A person can already run arbitrary Python via Claude Code or
a terminal, so this console's threat model is "convenience for the person
already running the app," not "safe to hand to an untrusted script."
"""
import contextlib
import io
import traceback

from PyQt6.QtWidgets import QDockWidget, QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit, QPushButton, QLabel
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtCore import Qt

from .geometry import Point, LineEntity, CircleEntity, ArcEntity, PolylineEntity, RectangleEntity, TextEntity
from .scripting import ScriptAPI


class PythonConsole(QDockWidget):
    def __init__(self, main_window):
        super().__init__("Python Console")
        self.setObjectName("python_console_dock")
        self.mw = main_window
        self.api = ScriptAPI(main_window)

        container = QWidget()
        layout = QVBoxLayout(container)

        layout.addWidget(QLabel("api.line/circle/rectangle/polyline/text/arc(...) - "
                                 "everything goes through undo. Ctrl+Enter to run."))

        self.input_edit = QPlainTextEdit()
        self.input_edit.setPlaceholderText(
            "for i in range(5):\n    api.circle(i*10, 0, 3)\napi.zoom_extents()")
        self.input_edit.setFixedHeight(90)
        layout.addWidget(self.input_edit)

        btn_row = QHBoxLayout()
        run_btn = QPushButton("Run (Ctrl+Enter)")
        clear_btn = QPushButton("Clear Output")
        run_btn.clicked.connect(self.run_code)
        clear_btn.clicked.connect(lambda: self.output_edit.clear())
        btn_row.addWidget(run_btn)
        btn_row.addWidget(clear_btn)
        layout.addLayout(btn_row)

        self.output_edit = QPlainTextEdit()
        self.output_edit.setReadOnly(True)
        layout.addWidget(self.output_edit)

        self.setWidget(container)

        shortcut = QShortcut(QKeySequence("Ctrl+Return"), self.input_edit)
        shortcut.activated.connect(self.run_code)

    def run_code(self):
        code = self.input_edit.toPlainText()
        if not code.strip():
            return
        namespace = {
            "api": self.api,
            "doc": self.mw.document,
            "Point": Point,
            "LineEntity": LineEntity,
            "CircleEntity": CircleEntity,
            "ArcEntity": ArcEntity,
            "PolylineEntity": PolylineEntity,
            "RectangleEntity": RectangleEntity,
            "TextEntity": TextEntity,
        }
        out = io.StringIO()
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
                exec(code, namespace)
            self.mw.canvas.viewport().update()
        except Exception:
            out.write(traceback.format_exc())
        text = out.getvalue()
        if text:
            self.output_edit.appendPlainText(text)
        else:
            self.output_edit.appendPlainText(">>> ran OK")
