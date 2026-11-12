"""
block_editor.py
A dialog for editing a BlockDefinition's contents in place. Opens the
block's entities in their own small canvas + toolbar; Save writes the
edited entities back into the live BlockDefinition and triggers
Document.sync_associative() so every place that block is inserted picks up
the change immediately - the same propagation Blocks & Xrefs already rely
on, now reachable from an actual editing UI instead of only from a script.

The editor exposes drawing and common modify/array tools, its own command
input and undo stack. Save preflights the changed definition and updates all
instances in one undoable change; Cancel discards the independent copies.
This is a static definition editor, without proprietary dynamic-block actions.
"""
import copy
from typing import Optional

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QToolBar, QLineEdit,
                              QLabel, QPushButton, QDialogButtonBox)
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt

from .document import Document, SetAttrCommand
from .canvas import CadCanvas, safe_event
from .tools import TOOL_REGISTRY, SelectTool

EDITOR_DRAW_TOOLS = [
    ("Select", "SELECT"), ("Line", "LINE"), ("Polyline", "PLINE"),
    ("Circle", "CIRCLE"), ("Arc", "ARC"), ("Rectangle", "RECTANGLE"),
    ("Spline", "SPLINE"), ("Text", "TEXT"), ("Hatch", "HATCH"),
]
EDITOR_MODIFY_TOOLS = [
    ("Copy", "COPY"), ("Rotate", "ROTATE"), ("Scale", "SCALE"),
    ("Trim", "TRIM"), ("Extend", "EXTEND"), ("Offset", "OFFSET"),
    ("Mirror", "MIRROR"), ("Fillet", "FILLET"), ("Chamfer", "CHAMFER"),
]
EDITOR_ARRAY_TOOLS = [
    ("Rect Array", "ARRAYRECT"), ("Polar Array", "ARRAYPOLAR"),
]


class BlockEditorDialog(QDialog):
    def __init__(self, parent, block_name: str, block_def):
        super().__init__(parent)
        self.setWindowTitle(f"Edit Block - {block_name}")
        self.resize(900, 650)
        self.block_name = block_name
        self.block_def = block_def

        # Work on a throwaway Document holding clones of the block's
        # entities - Cancel just discards it, Save writes the edited list
        # back into the live BlockDefinition.
        self.document = Document()
        self.document.entities = copy.deepcopy(block_def.entities)
        if parent is not None and hasattr(parent, "document"):
            self.document.dimstyles = copy.deepcopy(parent.document.dimstyles)
            self.document.current_dimstyle = parent.document.current_dimstyle
            self.document.mleaderstyles = copy.deepcopy(parent.document.mleaderstyles)
            self.document.current_mleaderstyle = parent.document.current_mleaderstyle
            self.document.textstyles = copy.deepcopy(parent.document.textstyles)
            self.document.current_textstyle = parent.document.current_textstyle
            self.document.layers = copy.deepcopy(parent.document.layers)
            self.document.blocks = copy.deepcopy(parent.document.blocks)
        self.document.undo_stack.indexChanged.connect(self._refresh_canvas)

        self.current_world_pos = None
        self.current_tool = None

        layout = QVBoxLayout(self)
        toolbar = QToolBar()
        for label, tool_name in EDITOR_DRAW_TOOLS:
            action = QAction(label, self)
            action.triggered.connect(lambda checked, t=tool_name: self.set_tool(t))
            toolbar.addAction(action)
        toolbar.addSeparator()
        for label, tool_name in EDITOR_MODIFY_TOOLS:
            action = QAction(label, self)
            action.triggered.connect(lambda checked, t=tool_name: self.set_tool(t))
            toolbar.addAction(action)
        toolbar.addSeparator()
        for label, tool_name in EDITOR_ARRAY_TOOLS:
            action = QAction(label, self)
            action.triggered.connect(lambda checked, t=tool_name: self.set_tool(t))
            toolbar.addAction(action)
        toolbar.addSeparator()
        undo_action = QAction("Undo", self)
        undo_action.triggered.connect(self.document.undo_stack.undo)
        toolbar.addAction(undo_action)
        redo_action = QAction("Redo", self)
        redo_action.triggered.connect(self.document.undo_stack.redo)
        toolbar.addAction(redo_action)
        zoom_action = QAction("Zoom Extents", self)
        zoom_action.triggered.connect(lambda: self.canvas.zoom_extents())
        toolbar.addAction(zoom_action)
        layout.addWidget(toolbar)

        self.canvas = CadCanvas(self.document)
        layout.addWidget(self.canvas, stretch=1)

        cmd_row = QHBoxLayout()
        cmd_row.addWidget(QLabel("Command:"))
        self.command_line = QLineEdit()
        self.command_line.returnPressed.connect(self._on_command_entered)
        cmd_row.addWidget(self.command_line)
        layout.addLayout(cmd_row)

        self.status_label = QLabel("Ready")
        layout.addWidget(self.status_label)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save |
                                    QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.canvas.world_mouse_moved.connect(self._on_mouse_moved)
        self.canvas.world_clicked.connect(self._on_world_clicked)
        self.canvas.key_pressed.connect(self._on_key_pressed)

        self.set_tool("SELECT")
        self.canvas.zoom_extents()

    @safe_event
    def _refresh_canvas(self, *_args):
        self.canvas.viewport().update()

    def set_tool(self, tool_name: str, *, hatch_configured=False):
        if tool_name == 'HATCH' and not hatch_configured:
            from .hatch_ui import create_hatch
            create_hatch(self)
            return
        tool_cls = TOOL_REGISTRY.get(tool_name)
        if not tool_cls:
            return
        self.current_tool = tool_cls(self)
        self.canvas.set_active_tool(self.current_tool)
        # Tools that operate on the current selection (Mirror, Copy, Rotate,
        # Scale, Arrays) need it preserved - same fix as MainWindow.set_tool.
        selection_dependent = {"MIRROR", "ARRAYRECT", "ARRAYPOLAR", "COPY", "ROTATE", "SCALE"}
        if tool_name != "SELECT" and tool_name not in selection_dependent:
            self.canvas.selected_entities = []
        self._update_status()

    def tool_finished(self):
        self.set_tool("SELECT")

    def _update_status(self):
        if self.current_tool:
            self.status_label.setText(self.current_tool.status_prompt())

    @safe_event
    def _on_mouse_moved(self, x, y, snap_kind):
        self.current_world_pos = (x, y)
        if self.current_tool:
            self.current_tool.on_move(x, y, snap_kind)

    @safe_event
    def _on_world_clicked(self, x, y, snap_kind, button):
        if self.current_tool:
            self.current_tool.on_click(x, y, snap_kind, button)
        self._update_status()

    @safe_event
    def _on_key_pressed(self, key):
        if self.current_tool:
            self.current_tool.on_key(key)
        self._update_status()

    @safe_event
    def _on_command_entered(self):
        text = self.command_line.text()
        self.command_line.clear()
        if not text.strip():
            if self.current_tool:
                self.current_tool.on_text_input("")
            return
        upper = text.strip().upper()
        if upper in TOOL_REGISTRY and (self.current_tool is None or isinstance(self.current_tool, SelectTool)):
            self.set_tool(upper)
        elif self.current_tool is not None:
            self.current_tool.on_text_input(text)
        self._update_status()

    def accept(self):
        finish = getattr(self.current_tool, "finish_drag", None)
        if finish:
            finish()
        parent = self.parent()
        if parent is not None and hasattr(parent, "document"):
            from .geometry import BlockDefinition
            from .block_budget import check_expansion
            blocks = dict(parent.document.blocks)
            candidate = copy.copy(self.block_def)
            candidate.entities = self.document.entities
            blocks[self.block_name] = candidate
            try:
                check_expansion(blocks,parent.document.entities)
                from .native_io import document_to_dict,entity_to_dict
                from .validation import validate_payload
                payload=document_to_dict(parent.document)
                payload['blocks'][self.block_name]['entities']=[entity_to_dict(e) for e in self.document.entities]
                validate_payload(payload)
            except ValueError as ex:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(self,'Edit Block',str(ex))
                return
            parent.document.undo_stack.push(SetAttrCommand(parent.document, self.block_def,
                "entities", self.block_def.entities, self.document.entities, "Edit block"))
        else:
            self.block_def.entities = copy.deepcopy(self.document.entities)
        super().accept()
