"""Cursor-adjacent command feedback backed by the normal editable command line.

One QLineEdit owns text, clipboard, IME and history. Viewport overlays mirror that
input without taking mouse focus or creating a popup window over the drawing.
"""

from PyQt6.QtCore import QEvent, QPoint, Qt
from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout


class ViewportCommandPrompt(QFrame):
    def __init__(self, window, viewport):
        super().__init__(viewport)
        self.mw = window
        self.viewport = viewport
        self.pointer = QPoint(viewport.width() // 2, viewport.height() // 2)
        self.setObjectName("viewport_command_prompt")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setStyleSheet("""
            QFrame#viewport_command_prompt { background:#172637; border:1px solid #5bbcdf; border-radius:4px; }
            QLabel { background:transparent; border:0; padding:0; color:#abc5d9; font-size:10px; }
            QLabel#dynamic_command_text { background:#0e1823; color:#f0f7fc; border:1px solid #405c73;
                padding:4px 6px; font-family:Consolas,monospace; font-size:13px; }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(7, 5, 7, 5)
        layout.setSpacing(4)
        self.prompt = QLabel()
        self.entry = QLabel()
        self.entry.setObjectName("dynamic_command_text")
        self.hint = QLabel()
        for label in (self.prompt, self.entry, self.hint):
            label.setTextFormat(Qt.TextFormat.PlainText)
            layout.addWidget(label)
        self.setFixedHeight(80)
        self.hide()
        viewport.installEventFilter(self)
        window.command_line.textChanged.connect(self.refresh)
        window.command_line.cursorPositionChanged.connect(self.refresh)

    def begin(self):
        old = self.mw.command_overlay
        if old is not None and old is not self:
            old.hide()
        self.mw.command_overlay = self
        self.refresh()

    def refresh(self, *_args):
        if self.mw.command_overlay is not self:
            return
        editor = self.mw.command_line
        if not editor.text() or not self.viewport.isVisible():
            self.hide()
            return
        self.setFixedWidth(max(100, min(310, self.viewport.width() - 16)))
        available = self.width() - 16
        prompt = self.mw.current_tool.status_prompt() if self.mw.current_tool else "Command"
        if getattr(self.mw.current_tool, "name", "SELECT") == "SELECT":
            prompt = "Command"
        self.prompt.setText(self.prompt.fontMetrics().elidedText(prompt, Qt.TextElideMode.ElideRight, available))
        pos = editor.cursorPosition()
        text = editor.text()[:pos] + "│" + editor.text()[pos:]
        self.entry.setText(self.entry.fontMetrics().elidedText(text, Qt.TextElideMode.ElideLeft, available - 14))
        matches = self.mw.command_matches(editor.text())
        if matches == [editor.text().upper()]:
            matches = []
        hint = "  ·  ".join(matches[:3]) if matches else (
            "Enter accepts • Space adds text" if self.mw.command_accepts_spaces()
            else "Enter / Space accepts • Esc cancels"
        )
        self.hint.setText(self.hint.fontMetrics().elidedText(hint, Qt.TextElideMode.ElideRight, available))
        self.reposition()
        self.show()
        self.raise_()

    def reposition(self):
        x, y = self.pointer.x() + 18, self.pointer.y() + 22
        if x + self.width() > self.viewport.width() - 8:
            x = self.pointer.x() - self.width() - 18
        if y + self.height() > self.viewport.height() - 8:
            y = self.pointer.y() - self.height() - 12
        self.move(max(4, min(x, self.viewport.width() - self.width() - 4)),
                  max(4, min(y, self.viewport.height() - self.height() - 4)))

    def eventFilter(self, obj, event):
        if not hasattr(self, 'viewport'):
            return False
        if obj is self.viewport:
            if event.type() == QEvent.Type.MouseMove:
                self.pointer = event.position().toPoint()
                if self.isVisible():
                    self.reposition()
            elif event.type() == QEvent.Type.Resize:
                self.refresh()
            elif event.type() in (QEvent.Type.MouseButtonPress, QEvent.Type.Hide):
                if self.mw.command_overlay is self:
                    self.mw.dismiss_viewport_input(clear=event.type() == QEvent.Type.MouseButtonPress)
        return super().eventFilter(obj, event)
