"""
main_window.py
Top-level application window: menu bar, toolbars, command-line input (AutoCAD-style),
status bar with coordinate readout, and a docked layers panel.
"""
import logging
import os
from typing import Optional, Tuple
from PyQt6.QtWidgets import (QMainWindow, QToolBar, QDockWidget, QListWidget,
                              QListWidgetItem, QLineEdit, QLabel, QStatusBar, QVBoxLayout,
                              QWidget, QPushButton, QHBoxLayout, QFileDialog, QMessageBox, QMenu, QToolButton, QSizePolicy,
                              QColorDialog, QInputDialog, QCheckBox, QComboBox, QTabBar, QPlainTextEdit, QApplication, QStackedWidget, QGridLayout, QScrollArea)
from PyQt6.QtGui import QAction, QKeySequence, QColor, QPainter, QPageLayout, QPalette, QPixmap, QIcon
from PyQt6.QtCore import Qt, QTimer, QPointF, QEvent, QSize
from PyQt6.QtPrintSupport import QPrinter, QPrintDialog

from .document import Document
from .canvas import CadCanvas, safe_event
from .tools import TOOL_REGISTRY, SelectTool
from .drafting_extras import EXTRA_TOOLS
from .ribbon_catalog import TOOLS as RIBBON_TOOLS
from . import ribbon_actions
from . import constraint_ui
from . import project_tools
from . import file_workspace
from . import underlays
from .precision_tools import PRECISION_TOOLS
from .mleader_tools import MLEADER_TOOLS
from . import mleader_ui
from . import appearance
from . import edit_commands, textstyles, collaboration
TOOL_REGISTRY.update(EXTRA_TOOLS)
TOOL_REGISTRY.update(MLEADER_TOOLS)
TOOL_REGISTRY.update(edit_commands.EDIT_TOOLS)
TOOL_REGISTRY.update(constraint_ui.CONSTRAINT_TOOLS)
TOOL_REGISTRY.update(PRECISION_TOOLS)
from . import dxf_io
from . import extrude3d
from . import applog
from . import appsettings
from . import branding
from .console import PythonConsole
from .block_editor import BlockEditorDialog
from ._version import __version__
from .workspace_ui import STYLE, make_ribbon, PropertiesPanel
from .zoom_tool import ZoomTool
TOOL_REGISTRY["ZOOM"] = ZoomTool
from .native_io import save_project

logger = logging.getLogger(__name__)

COMMAND_ALIASES = {
    'X':'EXPLODE', 'ISO':'ISOLATEOBJECTS', 'UNISO':'UNISOLATEOBJECTS',
    'CUT':'CUTCLIP', 'PASTE':'PASTECLIP', 'TEXTSTYLE':'STYLE', 'THEME':'OPTIONS', 'DIMLINEAR':'DIMHORIZONTAL',
    "PEDIT": "POLYEDITOR", "L": "LINE", "C": "CIRCLE", "PL": "PLINE", "REC": "RECTANGLE", "M": "MOVE",
    "CO": "COPY", "RO": "ROTATE", "SC": "SCALE", "TR": "TRIM", "EX": "EXTEND",
    "O": "OFFSET", "F": "FILLET", "H": "HATCH", "MI": "MIRROR", "DI": "DIST",
    "Z": "ZOOM", "AA": "AREA", "PO": "POINT", "EL": "ELLIPSE", "XL": "XLINE",
    "S": "STRETCH", "MT": "MTEXT", "ML": "MLEADER", "ZE": "ZOOMEXTENTS",
    "ZW": "ZOOMWINDOW", "LI": "LAYISO", "DC": "DIMCONTINUE", "DB": "DIMBASELINE",
}


class CommandLineEdit(QLineEdit):
    """The bottom command line - type command names or coordinate values, AutoCAD-style."""
    def __init__(self):
        super().__init__()
        self.history = []
        self.history_index = 0

    def event(self, event):
        if event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Tab:
            if self.window().command_matches(self.text()):
                self.keyPressEvent(event)
                return True
        return super().event(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.clear()
            self.window().cancel_command()
            event.accept()
            return
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) or (
            event.key() == Qt.Key.Key_Space and not self.window().command_accepts_spaces()
            and not event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)
        ):
            if not event.isAutoRepeat():
                self.returnPressed.emit()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Tab:
            matches = self.window().command_matches(self.text())
            if matches:
                self.setText(matches[0])
            event.accept()
            return
        if event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down) and self.history:
            self.history_index = max(0, min(len(self.history), self.history_index + (-1 if event.key() == Qt.Key.Key_Up else 1)))
            self.setText(self.history[self.history_index] if self.history_index < len(self.history) else "")
            return
        super().keyPressEvent(event)


class LayerPanel(QDockWidget):
    def __init__(self, main_window):
        super().__init__("Layers")
        self.setObjectName("layer_panel_dock")
        self.mw = main_window
        container = QWidget()
        layout = QVBoxLayout(container)
        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        btn_row = QGridLayout()
        add_btn = QPushButton("Add")
        rename_btn = QPushButton("Rename")
        color_btn = QPushButton("Color")
        del_btn = QPushButton("Delete")
        current_btn = QPushButton("Current")
        lock_btn = QPushButton("Lock")
        lock_btn.setToolTip('Lock / Unlock selected layer')
        lock_btn.clicked.connect(self.toggle_lock)
        add_btn.clicked.connect(self.add_layer)
        rename_btn.clicked.connect(self.rename_layer)
        color_btn.clicked.connect(self.change_color)
        del_btn.clicked.connect(self.delete_layer)
        current_btn.clicked.connect(self.set_current)
        for i, b in enumerate((add_btn, rename_btn, current_btn, color_btn, del_btn, lock_btn)):
            btn_row.addWidget(b, i // 3, i % 3)
        layout.addLayout(btn_row)
        manager_btn = QPushButton("Manage layers…")
        manager_btn.clicked.connect(self.mw.layer_properties_manager)
        layout.addWidget(manager_btn)

        self.setWidget(container)
        self.list_widget.itemChanged.connect(self.on_item_changed)
        self.refresh()

    def refresh(self):
        self.list_widget.blockSignals(True)
        self.list_widget.clear()
        doc = self.mw.document
        for name in doc.layers.names():
            props = doc.layers.layers[name]
            label = f"{name}" + ("  (current)" if name == doc.layers.current_layer else "")
            label += "  [locked]" if props["locked"] else ""
            label += "  [frozen]" if props.get("frozen", False) else ""
            item = QListWidgetItem(label)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if props["visible"] else Qt.CheckState.Unchecked)
            swatch = QPixmap(12, 12)
            swatch.fill(QColor(props['color']))
            item.setIcon(QIcon(swatch))
            item.setData(Qt.ItemDataRole.UserRole, name)
            self.list_widget.addItem(item)
        self.list_widget.blockSignals(False)

    def on_item_changed(self, item: QListWidgetItem):
        name = item.data(Qt.ItemDataRole.UserRole)
        visible = item.checkState() == Qt.CheckState.Checked
        try:
            self.mw.document.edit_layer("visible", name, visible)
        except ValueError:
            self.refresh()
            return
        self.mw.refresh_document_ui()

    def toggle_lock(self):
        name = self._selected_layer()
        if name:
            layers = self.mw.document.layers
            try:
                self.mw.document.edit_layer("locked", name, not layers.is_locked(name))
            except ValueError:
                return
            self.refresh()
            self.mw.refresh_document_ui()

    def _selected_layer(self) -> Optional[str]:
        item = self.list_widget.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def add_layer(self):
        name, ok = QInputDialog.getText(self, "New Layer", "Layer name:")
        if ok and name:
            try:
                self.mw.document.edit_layer("add", name.strip(), "#FFFFFF")
            except ValueError as ex:
                QMessageBox.warning(self, "New Layer", str(ex))
                return
            self.refresh()
            self.mw.refresh_document_ui()

    def rename_layer(self):
        name = self._selected_layer()
        if not name:
            return
        new_name, ok = QInputDialog.getText(self, "Rename Layer", "New layer name:")
        if ok and new_name:
            try:
                self.mw.document.edit_layer("rename", name, new_name.strip())
            except ValueError as ex:
                QMessageBox.warning(self, "Rename Layer", str(ex))
                return
            self.refresh()
            self.mw.refresh_document_ui()

    def delete_layer(self):
        name = self._selected_layer()
        if name:
            doc = self.mw.document
            if name == "0" or any(e.layer == name for e in doc.entities) or any(e.layer == name for b in doc.blocks.values() for e in b.entities):
                QMessageBox.warning(self, "Layer in use", "Layer 0 and layers containing entities cannot be deleted.")
                return
            try:
                self.mw.document.edit_layer("delete", name)
            except ValueError as ex:
                QMessageBox.warning(self, "Delete Layer", str(ex))
                return
            self.refresh()
            self.mw.refresh_document_ui()

    def set_current(self):
        name = self._selected_layer()
        if name:
            try:
                self.mw.document.edit_layer("current", name)
            except ValueError:
                return
            self.refresh()
            self.mw.refresh_document_ui()

    def change_color(self):
        name = self._selected_layer()
        if name:
            color = QColorDialog.getColor()
            if color.isValid():
                try:
                    self.mw.document.edit_layer("color", name, color.name())
                except ValueError as ex:
                    QMessageBox.warning(self, "Layer Color", str(ex))
                    return
                self.refresh()
                self.mw.refresh_document_ui()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setStyleSheet(STYLE)
        self.setWindowTitle("PY.cad - Untitled.pycad")
        self.setWindowIcon(branding.app_icon())
        self.resize(1400, 900)

        self.document = Document()
        self.canvas = CadCanvas(self.document)
        self.model_workspace = None
        self.model_dock = None
        self.command_overlay = None
        self.last_command = ""

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        self.space_tabs = QTabBar()
        self.space_tabs.setExpanding(False)
        self.space_tabs.addTab("Model")
        self.space_tabs.currentChanged.connect(self._on_space_tab_changed)
        self.viewport_stack = QStackedWidget()
        self.viewport_stack.addWidget(self.canvas)
        from .document_tabs import DrawingTabs
        self.drawing_tabs=DrawingTabs(self)
        container_layout.addWidget(self.drawing_tabs)
        container_layout.addWidget(self.viewport_stack, 1)
        container_layout.addWidget(self.space_tabs)
        self.setCentralWidget(container)

        self.current_world_pos: Optional[Tuple[float, float]] = None
        self.current_tool = None

        self._build_menus()
        self._build_toolbar()
        self._build_command_line()
        self._build_status_bar()
        self._build_layer_panel()
        self._build_python_console()
        self._build_autosave()
        from .shortcut_reference import initialize
        initialize(self)
        self._connect_canvas()
        self.properties_panel = PropertiesPanel(self)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.properties_panel)
        self.tabifyDockWidget(self.layer_panel, self.properties_panel)
        self.layer_panel.raise_()
        self.resizeDocks([self.layer_panel], [250], Qt.Orientation.Horizontal)
        from .layers_plus import install_auto_hide
        install_auto_hide(self)
        self._install_drafting_navigation()
        self._connect_document()

        self.set_tool("SELECT")
        appsettings.restore_window_geometry(self)
        appearance.set_menubar(self, appsettings.get_settings().value('interface/menubar', 1, type=int))
        self.snap_action.setChecked(self.canvas.snap_enabled)
        appearance.apply(self)
        self._refresh_recent_files_menu()
        from .feature_ui import install
        install(self)
        from .graphics import GraphicsController
        self.graphics = GraphicsController(self)
        self.graphics.changed.connect(self._sync_graphics_actions)
        self._sync_graphics_actions()
        QTimer.singleShot(0, self.graphics.start)
        # deferred so the window is fully shown before a modal recovery prompt pops up
        QTimer.singleShot(0, self._offer_recovery_if_present)

    # ------------------------------------------------------------------ menus
    def _build_menus(self):
        menubar = self.menuBar()

        self.recent_files_menu = QMenu("Open Recent", self)
        self.file_shortcuts = []
        for title, callback, shortcut in (("New", self.new_file, "Ctrl+N"), ("Open...", self.open_file, "Ctrl+O"),
                ("Save", self.save_file, "Ctrl+S"), ("Save As...", self.save_file_as, "Ctrl+Shift+S"),
                ("Plot / PDF", self.print_to_pdf, "Ctrl+P"), ("Exit", self.close, "Ctrl+Q")):
            action = QAction(title, self)
            action.setShortcut(shortcut)
            action.triggered.connect(lambda checked=False, fn=callback: self._file_shortcut(fn))
            self.addAction(action)
            self.file_shortcuts.append(action)

        edit_menu = menubar.addMenu("&Edit")
        self.undo_action = self._add_action(edit_menu, "Undo", self.undo, "Ctrl+Z")
        self.redo_action = self._add_action(edit_menu, "Redo", self.redo, "Ctrl+Y")
        edit_menu.addSeparator()
        self._add_action(edit_menu, "Delete Selected", self.delete_selected, "Del")
        for label,command,key in (('Cut','CUTCLIP','Ctrl+X'),('Copy to Clipboard','COPYCLIP','Ctrl+C'),
                                  ('Paste','PASTECLIP','Ctrl+V'),('Find / Replace…','FIND','Ctrl+F')):
            self._add_action(edit_menu,label,lambda checked=False,c=command:self.run_ribbon_command(c),key)

        insert_menu = menubar.addMenu('&Insert')
        for label,command in (('Create Block…','BLOCK'),('Insert Block…','INSERT'),('Xref Manager…','XREF'),('Raster Image…','IMAGEATTACH'),('PDF Underlay…','PDFATTACH')):
            self._add_action(insert_menu,label,lambda checked=False,c=command:self.run_ribbon_command(c))
        format_menu = menubar.addMenu('F&ormat')
        self._add_action(format_menu,'Linetypes…',lambda:self.run_ribbon_command('LINETYPE'))
        for label,command in (('Layers…','LAYER'),('Text Styles…','STYLE'),('Dimension Styles…','DIMSTYLE'),('Multileader Styles…','MLEADERSTYLE'),('Units…','UNITS')):
            self._add_action(format_menu,label,lambda checked=False,c=command:self.run_ribbon_command(c))
        parametric_menu = menubar.addMenu('&Parametric')
        for label,command in (('Coincident','GCCOINCIDENT'),('Parallel','GCPARALLEL'),('Perpendicular','GCPERPENDICULAR'),('Tangent','GCTANGENT'),('Constraint Manager…','CONSTRAINTSETTINGS')):
            self._add_action(parametric_menu,label,lambda checked=False,c=command:self.run_ribbon_command(c))
        collaborate_menu = menubar.addMenu('Co&llaborate')
        for label,command in (('Shared View…','SHAREDVIEWS'),('Cloud Files…','CLOUD'),('Compare Drawing…','COMPARE')):
            self._add_action(collaborate_menu,label,lambda checked=False,c=command:self.run_ribbon_command(c))

        draw_menu = menubar.addMenu("&Draw")
        self._add_action(draw_menu, "Line", lambda: self.set_tool("LINE"), "L")
        self._add_action(draw_menu, "Point", lambda: self.set_tool("POINT"))
        self._add_action(draw_menu, "Polyline", lambda: self.set_tool("PLINE"), "P")
        self._add_action(draw_menu, "Circle", lambda: self.set_tool("CIRCLE"), "C")
        self._add_action(draw_menu, "Arc", lambda: self.set_tool("ARC"), "A")
        self._add_action(draw_menu, "Ellipse", lambda: self.set_tool("ELLIPSE"))
        self._add_action(draw_menu, "Ray", lambda: self.set_tool("RAY"))
        self._add_action(draw_menu, "Construction Line", lambda: self.set_tool("XLINE"))
        self._add_action(draw_menu, "Rectangle", lambda: self.set_tool("RECTANGLE"), "R")
        self._add_action(draw_menu, "Spline", lambda: self.set_tool("SPLINE"))
        self._add_action(draw_menu, "Text", lambda: self.set_tool("TEXT"))
        from . import hatch_ui
        self._add_action(draw_menu, "Hatch and fill…", lambda: hatch_ui.create_hatch(self), "H")
        self._add_action(draw_menu, "Edit hatch…", lambda: hatch_ui.edit_hatch(self))
        self._add_action(draw_menu, "Recreate hatch boundary", lambda: hatch_ui.recreate_boundary(self))
        self._add_action(draw_menu, "Send selected hatches to back", lambda: hatch_ui.send_to_back(self))

        dim_menu = menubar.addMenu("D&imension")
        self._add_action(dim_menu, "Dimension Style Manager…", self.dimension_style_manager)
        self._add_action(dim_menu, "Multileader Style Manager…", lambda: self.run_ribbon_command('MLEADERSTYLE'))
        self._add_action(dim_menu, "Edit Multileader Text…", lambda: self.run_ribbon_command('MLEADEREDIT'))
        dim_menu.addSeparator()
        self._add_action(dim_menu, "Aligned", lambda: self.set_tool("DIMALIGNED"))
        self._add_action(dim_menu, "Horizontal", lambda: self.set_tool("DIMHORIZONTAL"))
        self._add_action(dim_menu, "Vertical", lambda: self.set_tool("DIMVERTICAL"))
        self._add_action(dim_menu, 'Leader', lambda: self.set_tool('LEADER'))
        self._add_action(dim_menu, 'Multileader', lambda: self.set_tool('MLEADER'))
        self._add_action(dim_menu, "Radius", lambda: self.set_tool("DIMRADIUS"))
        self._add_action(dim_menu, "Diameter", lambda: self.set_tool("DIMDIAMETER"))
        self._add_action(dim_menu, "Angular", lambda: self.set_tool("DIMANGULAR"))
        self._add_action(dim_menu, "Arc length", lambda: self.set_tool("DIMARC"))
        self._add_action(dim_menu, "Ordinate (X / Y)", lambda: self.set_tool("DIMORDINATE"))

        measure_menu = menubar.addMenu("Measu&re")
        self._add_action(measure_menu, "Distance", lambda: self.set_tool("DIST"), "DI")
        self._add_action(measure_menu, "Area", lambda: self.set_tool("AREA"))

        modify_menu = menubar.addMenu("&Modify")
        self._add_action(modify_menu, "Move", lambda: self.set_tool("MOVE"))
        self._add_action(modify_menu, "Copy", lambda: self.set_tool("COPY"))
        self._add_action(modify_menu, "Rotate", lambda: self.set_tool("ROTATE"))
        self._add_action(modify_menu, "Scale", lambda: self.set_tool("SCALE"))
        modify_menu.addSeparator()
        self._add_action(modify_menu, "Trim", lambda: self.set_tool("TRIM"), "T")
        self._add_action(modify_menu, "Extend", lambda: self.set_tool("EXTEND"))
        self._add_action(modify_menu, "Offset", lambda: self.set_tool("OFFSET"), "O")
        self._add_action(modify_menu, "Mirror", lambda: self.set_tool("MIRROR"))
        self._add_action(modify_menu, "Fillet", lambda: self.set_tool("FILLET"), "F")
        self._add_action(modify_menu, "Chamfer", lambda: self.set_tool("CHAMFER"))
        modify_menu.addSeparator()
        self._add_action(modify_menu, "Rectangular Array", lambda: self.set_tool("ARRAYRECT"))
        self._add_action(modify_menu, "Polar Array", lambda: self.set_tool("ARRAYPOLAR"))

        view_menu = menubar.addMenu("&View")
        self._add_action(view_menu, "3D Workspace / Four Views", self.open_model_workspace)
        for title in ("Top", "Bottom", "Front", "Back", "Left", "Right", "Isometric"):
            self._add_action(view_menu, title + " View", lambda checked=False, t=title: self.open_model_workspace(t, False))
        self._add_action(view_menu, "Free Orbit", self.start_orbit)
        self._add_action(view_menu, "2D Drafting", self.show_drafting)
        view_menu.addSeparator()
        self._add_action(view_menu, "Zoom Extents", self.fit_active, "Ctrl+0")
        for label, command in (('Pan','PAN'),('Zoom Window','ZOOMWINDOW'),('Viewports','VPORTS')):
            self._add_action(view_menu,label,lambda checked=False,c=command:self.run_ribbon_command(c))
        visual_styles = view_menu.addMenu('Visual Styles')
        for label, command in (('Wireframe','2DWIREFRAME'),('Shaded','SHADED'),('X-ray','XRAY'),('Conceptual','CONCEPTUAL'),('Realistic','REALISTIC')):
            self._add_action(visual_styles,label,lambda checked=False,c=command:self.run_ribbon_command(c))
        self.grid_action = self._add_action(view_menu, "Toggle Grid", self.toggle_grid, "F7", checkable=True)
        self.grid_action.setChecked(True)
        self.snap_action = self._add_action(view_menu, "Toggle Snap", self.toggle_snap, "F3", checkable=True)
        self.snap_action.setChecked(True)
        self.ortho_action = self._add_action(view_menu, "Toggle Ortho", self.toggle_ortho, "F8", checkable=True)
        self.ortho_action.setChecked(False)
        self.dynamic_action = self._add_action(view_menu, "Dynamic Input", self.toggle_measurements, "F12", checkable=True)
        self.dynamic_action.setChecked(appsettings.get_settings().value("drafting/live_measurements", True, type=bool))
        self.cursor_dimensions_action = self._add_action(view_menu, "Cursor Dimensions", self.toggle_cursor_dimensions, checkable=True)
        self.cursor_dimensions_action.setChecked(appsettings.get_settings().value("drafting/cursor_dimensions", True, type=bool))
        self.cursor_dimensions_action.setToolTip("Show live sizes beside the cursor, independently of F12 numeric input")
        self.history_action = self._add_action(view_menu, "Command History", self.toggle_command_history, "F2", checkable=True)
        self.history_action.setChecked(appsettings.get_settings().value("command/history_expanded", False, type=bool))
        view_menu.addSeparator()
        graphics_menu = view_menu.addMenu("Graphics · CPU / GPU")
        self.graphics_actions = {}
        from .graphics import MODES
        for mode, title in MODES.items():
            action = self._add_action(graphics_menu, title, lambda checked=False, m=mode: self.graphics.set_mode(m), checkable=True)
            self.graphics_actions[mode] = action
        self.gl_render_action = self.graphics_actions["hardware"]
        graphics_menu.addSeparator()
        self._add_action(graphics_menu, "Settings and diagnostics…", self.graphics_dialog)

        threed_menu = menubar.addMenu("&3D")
        self._add_action(threed_menu, "Extrude to Model…", self.extrude_to_model)
        self._add_action(threed_menu, "Model Workspace…", self.open_model_workspace)
        self._add_action(threed_menu, "Extrude Selected to STEP/STL...", self.extrude_selected)

        blocks_menu = menubar.addMenu("Bl&ocks")
        self._add_action(blocks_menu, "Create Block...", lambda: self.set_tool("BLOCK"))
        self._add_action(blocks_menu, "Insert Block...", self.insert_block_dialog)
        self._add_action(blocks_menu, "Edit Block...", self.edit_block_dialog)
        blocks_menu.addSeparator()
        self._add_action(blocks_menu, "Attach Xref...", self.attach_xref)
        self._add_action(blocks_menu, "Reload All Xrefs", self.reload_all_xrefs)
        self._add_action(blocks_menu, "Bind selected Xref to drawing", lambda:self.run_ribbon_command("BIND"))
        self._add_action(blocks_menu, "Bind missing cached Xrefs", lambda:self.run_ribbon_command("BINDMISSING"))
        self._add_action(blocks_menu, "Clip Reference (XCLIP)", lambda: self.set_tool("XCLIP"))

        layout_menu = menubar.addMenu("&Layout")
        self._add_action(layout_menu, "New Layout...", self.new_layout_dialog)
        self._add_action(layout_menu, "Rename Current Layout...", self.rename_layout_dialog)
        self._add_action(layout_menu, "Delete Current Layout", self.delete_layout)
        self._add_action(layout_menu, "Add Viewport", lambda: self.set_tool("ADDVIEWPORT"))
        self._add_action(layout_menu, "Viewport Scale...", self.viewport_scale_dialog)

        workflow_menu=menubar.addMenu('Workflow')
        from .workflow_ui import commands as workflow_commands
        for label,callback in workflow_commands(self).items():
            self._add_action(workflow_menu,label.title(),callback)
        from .pro_ui import commands as pro_commands
        for label,callback in pro_commands(self).items():self._add_action(workflow_menu,label.title(),callback)
        from .productivity_ui import commands as productivity_commands
        for label,callback in productivity_commands(self).items():self._add_action(workflow_menu,label.title(),callback)
        from .efficiency_ui import commands as efficiency_commands
        for label,callback in efficiency_commands(self).items():self._add_action(workflow_menu,label.title(),callback)
        self._add_action(workflow_menu,'Command palette…',efficiency_commands(self)['COMMANDPALETTE'],'Ctrl+Shift+P')
        from .production_ui import commands as production_commands
        for label,callback in production_commands(self).items():self._add_action(workflow_menu,label.title(),callback)
        from .editing_ui import commands as editing_commands
        for label,callback in editing_commands(self).items():self._add_action(workflow_menu,label.title(),callback)
        from .office_ui import commands as office_commands
        office_menu=menubar.addMenu("Office &Drafting")
        for label, command in zip(("Shared block library…","Parametric door…","PDF review…","Project sheet set…","Custom linetype…"),office_commands(self)):
            self._add_action(office_menu,label,lambda command=command:self.run_ribbon_command(command))
        from .coordination_ui import commands as coordination_commands
        for label,callback in coordination_commands(self).items():self._add_action(workflow_menu,label.title(),callback)
        from .drafting_ui import commands as drafting_commands
        self._add_action(workflow_menu,'Drafting tools…',drafting_commands(self)['DRAFTINGTOOLS'])
        tools_menu = menubar.addMenu("&Tools")
        self._add_action(tools_menu, "Layer Properties Manager…", self.layer_properties_manager)
        self._add_action(tools_menu, "Drawing Units...", self.units_dialog)
        self._add_action(tools_menu, "Python Console", self.toggle_python_console, "Ctrl+`")
        self._add_action(tools_menu, 'Options / Theme…', lambda: self.run_ribbon_command('OPTIONS'))
        self._add_action(tools_menu, 'Object Snap Settings…', lambda: self.run_ribbon_command('OSNAP'))
        self._add_action(tools_menu, 'Tool Palettes…', lambda: self.run_ribbon_command('TOOLPALETTES'))
        self._add_action(tools_menu, 'Properties…', lambda: self.run_ribbon_command('PROPERTIES'))

        help_menu = menubar.addMenu("&Help")
        self._add_action(help_menu, "About PY.cad", self.show_about)
        self._add_action(help_menu, "Licenses and Legal", self.show_legal)
        self._add_action(help_menu, "DWG support", self.show_dwg_support)

    def _add_action(self, menu, text, slot, shortcut=None, checkable=False) -> QAction:
        action = QAction(text, self)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        if checkable:
            action.setCheckable(True)
        # Bare-letter global shortcuts steal text from editors. Commands and
        # aliases are handled by the command line instead.
        if shortcut and len(shortcut) == 1:
            action.setShortcut(QKeySequence())
        action.triggered.connect(slot)
        menu.addAction(action)
        return action

    # ------------------------------------------------------------------ toolbar
    def _build_toolbar(self):
        menubar = self.menuBar()
        menubar.setNativeMenuBar(False)
        file_button = QToolButton(menubar)
        file_button.setIcon(branding.app_icon())
        file_button.setIconSize(QSize(44, 44))
        file_button.setFixedSize(48, 48)
        file_button.setStyleSheet("QToolButton { padding:0; border:0; }")
        file_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        file_button.setAccessibleName("PY.cad application menu")
        file_button.setToolTip("Application menu (Alt+F): New, Open, Save, Export and Print")
        file_button.setObjectName("quick_file_button")
        file_button.clicked.connect(self.show_file_workspace)
        menubar.setCornerWidget(file_button, Qt.Corner.TopLeftCorner)
        menubar.setMinimumHeight(48)
        self.application_menu_action = QAction(self)
        self.application_menu_action.setShortcut(QKeySequence("Alt+F"))
        self.application_menu_action.triggered.connect(self.show_file_workspace)
        self.addAction(self.application_menu_action)

        self.home_drafting_controls = QWidget(self)
        self.home_drafting_controls.setObjectName("home_drafting_controls")
        controls = QVBoxLayout(self.home_drafting_controls)
        controls.setContentsMargins(5, 0, 5, 0)
        controls.setSpacing(0)
        self.workspace_label = QLabel("DRAFTING")
        self.workspace_label.setObjectName("brand")
        self.workspace_label.setStyleSheet("font-size:12px; padding:2px; font-weight:bold;")
        controls.addWidget(self.workspace_label)
        line_row = QHBoxLayout()
        line_row.setSpacing(2)
        self.linetype_combo = QComboBox()
        self.linetype_combo.setAccessibleName("Current drawing linetype")
        self.linetype_combo.setToolTip("Current linetype")
        from .linetypes import populate_combo
        populate_combo(self.linetype_combo, bylayer=True)
        self.linetype_combo.setFixedWidth(190)
        self.linetype_combo.setFixedHeight(26)
        self.linetype_combo.currentTextChanged.connect(self._on_linetype_changed)
        line_row.addWidget(self.linetype_combo)
        library_button = QToolButton()
        library_button.setText("…")
        library_button.setToolTip("Linetype library and scale")
        library_button.setAccessibleName("Linetype library and scale")
        library_button.clicked.connect(lambda: self.run_ribbon_command("LINETYPE"))
        line_row.addWidget(library_button)
        controls.addLayout(line_row)
        self.ribbon = make_ribbon(self)
        self.centralWidget().layout().insertWidget(0, self.ribbon)

    def show_dwg_support(self):
        from .dwg_settings import show_settings
        return show_settings(self)

    def _on_linetype_changed(self, text: str):
        self.document.current_linetype = text

    # ------------------------------------------------------------------ command line
    def _build_command_line(self):
        dock = QDockWidget("Command Line", self)
        self.command_dock = dock
        dock.setObjectName("command_line_dock")
        dock.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        dock.setTitleBarWidget(QWidget())
        container = QWidget()
        container.setObjectName('command_bar')
        layout = QVBoxLayout(container)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.setSpacing(3)
        self.command_history = QPlainTextEdit()
        self.command_history.setObjectName('command_history')
        self.command_history.setReadOnly(True)
        self.command_history.setMaximumBlockCount(500)
        self.command_history.setFixedHeight(64)
        self.command_history.setVisible(self.history_action.isChecked())
        self.command_history.setPlainText(f"PY.cad {__version__} · Model space ready. Type a command, or choose a ribbon tool.")
        layout.addWidget(self.command_history)
        self.command_options_label = QLabel()
        self.command_options_label.setObjectName("command_options")
        self.command_options_label.setTextFormat(Qt.TextFormat.RichText)
        self.command_options_label.setTextInteractionFlags(Qt.TextInteractionFlag.LinksAccessibleByMouse | Qt.TextInteractionFlag.LinksAccessibleByKeyboard)
        self.command_options_label.setToolTip("Type the highlighted shortcut, then Enter/Space, or click an option. Esc cancels.")
        self.command_options_label.linkActivated.connect(self.trigger_command_option)
        self.command_options_scroll = QScrollArea()
        self.command_options_scroll.setObjectName("command_options_row")
        self.command_options_scroll.setWidget(self.command_options_label)
        self.command_options_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.command_options_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.command_options_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.command_options_scroll.setFixedHeight(28)
        self.command_options_scroll.setStyleSheet("QScrollBar:horizontal {height:5px;}")
        self.command_options_scroll.hide()
        layout.addWidget(self.command_options_scroll)
        row = QHBoxLayout()
        self.command_prompt_label = QLabel("Command:")
        self.command_prompt_label.setObjectName('command_prompt')
        self.command_line = CommandLineEdit()
        self.command_line.setObjectName('command_line')
        self.command_line.setMinimumHeight(25)
        self.command_line.returnPressed.connect(self._on_command_entered)
        QApplication.instance().focusChanged.connect(self._command_focus_changed)
        self.command_line.setPlaceholderText("Type a command here or in the viewport")
        self.command_names = sorted(set(TOOL_REGISTRY) | {
            "PEDIT", "CURSORDIMS", "DIMSTYLE", "D", "LAYER", "LA", "EXTRUDE", "VPORTS", "3DORBIT", "PLAN",
            "TOP", "BOTTOM", "LEFT", "RIGHT", "FRONT", "BACK", "ISOMETRIC", "UNDO", "U",
            "REDO", "SAVE", "QSAVE", "NEW", "OPEN", "REGEN", "REGENALL", "REDRAW", "REFRESH", "ZOOM", "Z", "ERASE", "E", "UNITS", "DYNMODE",
            "AUDIT", "RECOVER", "PURGE", "STATUS", "SAVETEMPLATE", "NEWTEMPLATE", "CLOSE", "FILE",
            "OFFICEBLOCKS", "PARAMETRICDOOR", "PDFREVIEW", "PROJECTSHEETS", "LINETYPEDESIGN", "UNDERLAYS", "IMAGEATTACH", "PDFATTACH", "GRAPHICS", "GRAPHICSCONFIG", "GRAPHICSINFO", "PROCESSOR", "PROCESSING", "CPU", "GPU", "DWGSETTINGS", "COORDINATION", "SHAREDPROPERTIES", "BLOCKLIBRARY", "REFCOORD", "PROJECTSTANDARDS", "TUTORIALS", "RELEASECHECKS", "EDITING", "SELECTFILTER", "ADVGRIPS", "BOUNDARYREPAIR", "DRAFTINGAIDS", "WORKSPACEPRESETS", "DRAWINGHEALTH", "TRACKPOINT", "CLEARTRACKING", "PRODUCTION", "SHEETSETS", "DRAWCOMPARE", "PUBLISHPREVIEW", "ANNOTATIONTOOLS", "ARCHDRAFT", "BOQTRACE", "AIPREVIEW", "EFFICIENCY", "IMPORTCACHE", "RECOVERYCENTER", "SELECTCYCLE", "COMMANDPALETTE", "CLEANUPPREVIEW", "BATCHDRAWINGS", "REFDIAGNOSTICS", "PERFDASHBOARD", "DRAWINGTOOLS", "HATCHAREAS", "PDFIMPORT", "DRAWTABLE", "STANDARDSCHECK", "SURVEY", "BLOCKPARAMETERS", "BOQOVERLAY", "AIEXPLAIN", "PROWORKFLOW", "REGIONALCACHE", "GPUBUFFERS", "ASSOCIATIONS", "BLOCKVARIANTS", "REVISIONS", "VIEWPORTPLUS", "ARCHREVIEW", "BOQCHANGES", "ROOMPLANNER", "PROJECTPACKAGE", "WORKFLOW", "DIAGNOSTICS", "PERFORMANCE", "DWGREPORT", "PRECISIONEDIT", "XREFMANAGER", "BIND", "BINDMISSING", "SHEETLIBRARY", "RECOVERYHISTORY", "TAKEOFFRULES", "AIDRAFT", "JOIN", "BREAKAT", "HATCHEDIT", "HATCHSETTINGS", "HATCHBOUNDARY", "HATCHTOBACK", "LINETYPE", "LTSCALE",
        })
        from .drafting_ui import commands as drafting_commands
        self.command_names = sorted(set(self.command_names)|set(drafting_commands(self)))
        self.canonical_commands = set(self.command_names) | {key for key,item in RIBBON_TOOLS.items() if item.status != "planned"}
        self.user_aliases = ribbon_actions.load_aliases()
        self.user_aliases = {key:value for key,value in self.user_aliases.items() if key not in self.canonical_commands and value in self.canonical_commands}
        self.command_names = sorted(self.canonical_commands | set(self.user_aliases))
        row.addWidget(self.command_prompt_label)
        row.addWidget(self.command_line)
        self.history_button = QToolButton()
        self.history_button.setObjectName("command_history_toggle")
        self.history_button.setText("▾" if self.history_action.isChecked() else "▴")
        self.history_button.setToolTip("Show / hide command history (F2)")
        self.history_button.setAccessibleName("Toggle command history")
        self.history_button.setFixedSize(26, 25)
        self.history_button.clicked.connect(self.history_action.trigger)
        self.command_history.textChanged.connect(self._command_history_changed)
        row.addWidget(self.history_button)
        layout.addLayout(row)
        dock.setWidget(container)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dock)
        self._collapsed_command_height = max(29, dock.sizeHint().height() - (67 if self.history_action.isChecked() else 0))
        if self.history_action.isChecked():
            dock.setMaximumHeight(110)
        else:
            dock.setFixedHeight(self._collapsed_command_height)

    def render_command_options(self):
        if not hasattr(self, "command_options_label"):
            return
        from .command_options import options, markup
        choices = options(self)
        visible = bool(choices)
        changed = self.command_options_scroll.isHidden() == visible
        self.command_options_label.setText(markup(choices, self.palette().color(QPalette.ColorRole.Window).lightness() < 128, appearance.colors(self)))
        self.command_options_label.setAccessibleName("Command options: " + "; ".join(o.label + " (" + o.key + ")" + (" unavailable" if not o.enabled else "") for o in choices))
        self.command_options_label.adjustSize()
        self.command_options_scroll.setVisible(visible)
        if changed:
            self._resize_command_dock()

    def _resize_command_dock(self):
        extra = 31 if not self.command_options_scroll.isHidden() else 0
        expanded = self.history_action.isChecked()
        self.command_dock.setMinimumHeight(0)
        self.command_dock.setMaximumHeight(110 + extra if expanded else self._collapsed_command_height + extra)
        if not expanded:
            self.command_dock.setFixedHeight(self._collapsed_command_height + extra)
        self.resizeDocks([self.command_dock], [103 + extra if expanded else self._collapsed_command_height + extra], Qt.Orientation.Vertical)

    def trigger_command_option(self, key):
        from .command_options import options
        choice = next((o for o in options(self) if o.key == key and o.enabled), None)
        if choice is None:
            return
        if key == "ESC":
            self.cancel_command()
            return
        self.command_line.setText("" if key == "ENTER" else key)
        self._on_command_entered()

    def toggle_command_history(self):
        expanded = self.history_action.isChecked()
        self.command_history.setVisible(expanded)
        self.history_button.setText("▾" if expanded else "▴")
        self._resize_command_dock()
        self.command_dock.show()
        if expanded:
            self.command_history.verticalScrollBar().setValue(self.command_history.verticalScrollBar().maximum())
        appsettings.get_settings().setValue("command/history_expanded", expanded)

    def _command_history_changed(self):
        if not self.history_action.isChecked():
            self.history_button.setText("•")
        last = self.command_history.document().lastBlock().text()
        if last.startswith(("Input error:", "Command failed:", "Constraint conflict:", "Unknown command:")):
            self.statusBar().showMessage(last + "  (F2 for history)", 8000)

    def show_file_workspace(self):
        if not hasattr(self, "file_workspace"):
            self.file_workspace = file_workspace.FileWorkspace(self)
        if self.file_workspace.isVisible():
            self.file_workspace.dismiss()
        else:
            self.file_workspace.open()

    def _file_shortcut(self, callback):
        if hasattr(self, "file_workspace"):
            self.file_workspace.hide()
        callback()

    def command_accepts_spaces(self):
        tool = self.current_tool
        name = getattr(tool, "name", "SELECT")
        return (
            name == "TEXT" and tool.insertion_point is not None
            or name == "BLOCK" and tool.base_point is not None
            or name == "INSERT" and not tool.block_name
        )

    def command_matches(self, prefix):
        if not prefix.strip():
            return []
        if not isinstance(self.current_tool, SelectTool):
            if self.command_accepts_spaces():
                return []
            from .command_options import options
            return [o.label for o in options(self) if o.enabled and (o.label.upper().startswith(prefix.strip().upper()) or o.key == prefix.strip().upper())]
        prefix = prefix.strip().upper()
        matches = [name for name in self.command_names if name.startswith(prefix)]
        alias = self.user_aliases.get(prefix, COMMAND_ALIASES.get(prefix))
        if alias:
            matches = [alias] + [name for name in matches if name != alias]
        return matches

    def dismiss_viewport_input(self, clear=False):
        overlay = self.command_overlay
        self.command_overlay = None
        if overlay is not None:
            overlay.hide()
        if clear and hasattr(self, "command_line"):
            self.command_line.clear()

    def _command_focus_changed(self, previous, current):
        if self.command_overlay is not None and current is not self.command_line:
            self.dismiss_viewport_input(clear=current is not None)

    def focus_active_viewport(self):
        if self.model_workspace is not None and self.viewport_stack.currentWidget() is self.model_workspace:
            self.model_workspace.active.setFocus()
        else:
            self.canvas.setFocus()

    def route_viewport_key(self, view, event):
        """Start keyboard input from either canvas, preserving native text editing."""
        if event.key() == Qt.Key.Key_Escape and self.current_tool is not None and not isinstance(self.current_tool, SelectTool):
            self.cancel_command()
            event.accept()
            return True
        if (view is self.canvas and event.key()==Qt.Key.Key_Tab and isinstance(self.current_tool,SelectTool)
                and not self.command_line.text() and not event.modifiers() & (Qt.KeyboardModifier.ControlModifier|Qt.KeyboardModifier.AltModifier|Qt.KeyboardModifier.MetaModifier)):
            from .selection_cycle import cycle
            cycle(self,bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier));event.accept();return True
        dynamic = getattr(self.canvas, 'dynamic_input', None)
        if view is self.canvas and dynamic is not None and dynamic.route(event):
            event.accept()
            return True
        if event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier | Qt.KeyboardModifier.MetaModifier):
            return False
        submit = event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) or (
            event.key() == Qt.Key.Key_Space and not self.command_accepts_spaces()
        )
        printable = bool(event.text() and event.text().isprintable())
        if not submit and not printable:
            return False
        if hasattr(view, "workspace"):
            view.workspace.activate(view)
        if submit:
            if not event.isAutoRepeat():
                self._on_command_entered()
        else:
            self.findChild(QDockWidget, "command_line_dock").show()
            view.command_overlay.begin()
            self.command_line.setFocus()
            self.command_line.insert(event.text())
        event.accept()
        return True

    def _on_command_entered(self):
        input_only = not isinstance(self.current_tool, SelectTool)
        text = self.command_line.text()
        if not self.command_accepts_spaces():
            text = text.strip()
        if not text and isinstance(self.current_tool, SelectTool):
            text = self.last_command
        self.dismiss_viewport_input()
        self.command_line.clear()
        if text:
            self.command_line.history.append(text)
            self.command_line.history_index = len(self.command_line.history)
            self.command_history.appendPlainText("> " + text)
        upper = self.user_aliases.get(text.upper(), COMMAND_ALIASES.get(text.upper(), text.upper()))
        try:
            if isinstance(self.current_tool, SelectTool):
                commands = {"UNDO":self.undo,"U":self.undo,"REDO":self.redo,"SAVE":self.save_file,
                            "QSAVE":self.save_file,"NEW":self.new_file,"OPEN":self.open_file,
                            "ZOOM":self.fit_active,"Z":self.fit_active,
                            "DIMSTYLE":self.dimension_style_manager,"D":self.dimension_style_manager,
                            "LAYER":self.layer_properties_manager,"LA":self.layer_properties_manager,
                            "VPORTS":self.open_model_workspace,"3DORBIT":self.start_orbit,"PLAN":self.show_drafting,
                            "EXTRUDE":self.extrude_to_model,
                            **{name.upper():lambda t=name:self.open_model_workspace(t,False) for name in ("Top","Bottom","Front","Back","Left","Right","Isometric")},
                            "ERASE":self.delete_selected,"E":self.delete_selected,"UNITS":self.units_dialog,
                            "CURSORDIMS":self.cursor_dimensions_action.trigger, "DYNMODE":self.dynamic_action.trigger}
                commands.update(ribbon_actions.commands(self))
                from .linetype_ui import show as show_linetypes
                commands.update({'LINETYPE':lambda:show_linetypes(self),'LTSCALE':lambda:show_linetypes(self)})
                commands.update(constraint_ui.commands(self))
                commands.update(project_tools.commands(self))
                commands.update(file_workspace.commands(self))
                commands.update(underlays.commands(self))
                commands.update(mleader_ui.commands(self))
                commands.update(appearance.commands(self))
                from .workflow_ui import commands as workflow_commands
                commands.update(workflow_commands(self))
                from .pro_ui import commands as pro_commands
                commands.update(pro_commands(self))
                from .productivity_ui import commands as productivity_commands
                commands.update(productivity_commands(self))
                from .efficiency_ui import commands as efficiency_commands
                commands.update(efficiency_commands(self))
                from .production_ui import commands as production_commands
                commands.update(production_commands(self))
                from .editing_ui import commands as editing_commands
                commands.update(editing_commands(self))
                from .coordination_ui import commands as coordination_commands
                commands.update(coordination_commands(self))
                from .office_ui import commands as office_commands
                commands.update(office_commands(self))
                from .drafting_ui import commands as drafting_commands
                commands.update(drafting_commands(self))
                from .persistent_scene import regenerate
                commands.update({name:lambda:regenerate(self.canvas) for name in ("RE","REGEN","REGENALL","REDRAW","REFRESH")})
                commands["DWGSETTINGS"] = self.show_dwg_support
                commands.update({key: self.graphics_dialog for key in ("GRAPHICS", "GRAPHICSCONFIG", "GRAPHICSINFO", "PROCESSOR", "PROCESSING")})
                commands.update({'CPU':lambda:self.graphics.set_mode('software'),
                                 'GPU':lambda:self.graphics.set_mode('hardware')})
                commands.update(edit_commands.commands(self))
                from . import hatch_ui
                commands.update({'HATCHEDIT':lambda:hatch_ui.edit_hatch(self),
                                 'HATCHSETTINGS':lambda:hatch_ui.create_hatch(self),
                                 'HATCHBOUNDARY':lambda:hatch_ui.recreate_boundary(self),
                                 'HATCHTOBACK':lambda:hatch_ui.send_to_back(self)})
                commands.update(collaboration.commands(self))
                from .feature_ui import commands as feature_commands
                commands.update(feature_commands(self))
                commands.update({'STYLE':lambda:textstyles.manager(self),'TEXTEDIT':lambda:textstyles.edit_text(self)})
                if upper in TOOL_REGISTRY:
                    self.set_tool(upper)
                elif upper in commands:
                    commands[upper]()
                    self.last_command = upper
                elif upper in RIBBON_TOOLS and RIBBON_TOOLS[upper].status == "planned":
                    self.command_history.appendPlainText("Not implemented: " + RIBBON_TOOLS[upper].detail)
                elif text:
                    self.command_history.appendPlainText("Unknown command: " + text)
            elif self.current_tool:
                from .command_options import resolve
                choice = resolve(self, text)
                if choice:
                    if not choice.enabled:
                        raise ValueError(choice.label + " is not available at this step")
                    if choice.key == "ESC":
                        self.cancel_command()
                        return
                    text = "" if choice.key == "ENTER" else choice.key
                    if hasattr(self.canvas, "dynamic_input"):
                        self.canvas.dynamic_input.reset()
                # TEXT input remains literal. Other tools reject NaN/Inf/overflow.
                import re, math
                if self.current_tool.name != "TEXT" and any(not math.isfinite(float(v)) for v in re.findall(r"(?i)(?<![a-z])[-+]?(?:nan|inf(?:inity)?|\d+(?:\.\d*)?(?:e[-+]?\d+)?)", text)):
                    raise ValueError("Use finite numeric values")
                if text:
                    self.current_tool.on_text_input(text)
                else:
                    self.current_tool.on_key(Qt.Key.Key_Return)
        except (ValueError, OverflowError) as ex:
            self.last_command_failure=str(ex)
            self.command_history.appendPlainText("Input error: " + str(ex))
        except Exception as ex:
            self.last_command_failure=str(ex)
            logger.exception("Command failed")
            self.command_history.appendPlainText("Command failed: " + str(ex))
        self.update_status()
        self.refresh_document_ui(_ui_only=input_only or upper in TOOL_REGISTRY or upper in ("RE","REGEN","REGENALL","REDRAW","REFRESH"))
        self.focus_active_viewport()

    def cancel_command(self):
        self.dismiss_viewport_input(clear=True)
        cancel = getattr(self.current_tool, "cancel_drag", None)
        if cancel:
            cancel()
        self.set_tool("SELECT")
        self.focus_active_viewport()

    def run_ribbon_command(self, command):
        """All ribbon actions share viewport command routing and history."""
        if command.upper() == "CURSORDIMS":
            self.command_history.appendPlainText("> " + command)
            self.cursor_dimensions_action.trigger()
            return
        self.cancel_command()
        self.command_line.setText(command)
        self._on_command_entered()

    # ------------------------------------------------------------------ status bar
    def _build_status_bar(self):
        sb = QStatusBar()
        self.setStatusBar(sb)
        self.coord_label = QLabel("X: 0.00  Y: 0.00")
        self.snap_label = QLabel("")
        self.tool_label = QLabel("Ready")
        self.tool_label.setMinimumWidth(0)
        self.tool_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        sb.addWidget(self.tool_label, 3)
        sb.addPermanentWidget(self.snap_label)
        sb.addPermanentWidget(self.coord_label)
        for label, action in (("GRID F7",self.grid_action),("OSNAP F3",self.snap_action),("ORTHO F8",self.ortho_action),("DYN F12",self.dynamic_action)):
            button=QPushButton(label); button.setCheckable(True); button.setChecked(action.isChecked())
            button.clicked.connect(lambda checked=False, a=action:a.trigger())
            action.toggled.connect(button.setChecked)
            sb.addPermanentWidget(button)
        self.units_button = QPushButton(self.document.units)
        self.units_button.setObjectName("drawing_units_button")
        self.units_button.setToolTip("Drawing Units Manager (UNITS)")
        self.units_button.clicked.connect(self.units_dialog)
        sb.addPermanentWidget(self.units_button)
        self.graphics_button = QPushButton("CPU")
        self.graphics_button.setObjectName("graphics_button")
        self.graphics_button.setMaximumWidth(100)
        self.graphics_button.clicked.connect(self.graphics_dialog)
        sb.addPermanentWidget(self.graphics_button)
        self.coord_label.setMaximumWidth(290)

    def _build_layer_panel(self):
        self.layer_panel = LayerPanel(self)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.layer_panel)

    def _build_python_console(self):
        self.python_console = PythonConsole(self)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self.python_console)
        self.python_console.hide()  # opt-in via Tools menu, not shown by default

    def toggle_python_console(self):
        self.python_console.setVisible(not self.python_console.isVisible())

    def dimension_style_manager(self):
        from .managers import DimensionStyleManager
        dialog = DimensionStyleManager(self)
        dialog.exec()
        dialog.deleteLater()

    def layer_properties_manager(self):
        from .managers import LayerPropertiesManager
        dialog = LayerPropertiesManager(self)
        dialog.exec()
        dialog.deleteLater()

    def _install_drafting_navigation(self):
        from .navigation import ViewportNavigation
        from .model3d import Camera
        self.draft_camera = Camera("Top")
        self.draft_navigation = ViewportNavigation(self.canvas.viewport())
        self.draft_navigation.cube.defer_orbit = True
        self.draft_navigation.sync(self.draft_camera, "select", drafting=True)
        self.draft_navigation.view_requested.connect(lambda name: self.open_model_workspace(name, False))
        self.draft_navigation.mode_requested.connect(self._draft_navigation_mode)
        self.draft_navigation.zoom_requested.connect(self.zoom_active)
        self.draft_navigation.fit_requested.connect(self.fit_active)
        self.draft_navigation.draft_requested.connect(self.show_drafting)
        self.draft_navigation.layout_requested.connect(lambda four: self.open_model_workspace(four=four))
        self.draft_navigation.orbit_requested.connect(self._orbit_from_drafting)

    def _draft_navigation_mode(self, mode):
        if mode == "orbit":
            self.start_orbit()
            return
        self.cancel_command()
        self.canvas.navigation_pan = True
        self.canvas.setCursor(Qt.CursorShape.OpenHandCursor)
        self.draft_navigation.sync(self.draft_camera, "pan", drafting=True)
        self.canvas.setFocus()

    def _orbit_from_drafting(self, dx, dy):
        self.open_model_workspace("Top", False)
        self.model_workspace.active.rotate_camera(dx, dy)

    def open_model_workspace(self, preset=None, four=True):
        """Display persistent model panes in the central viewport, never a dialog."""
        from .view3d import ModelWorkspace
        if not isinstance(preset, str):
            preset = None  # QAction supplies a checked boolean.
        self._finish_pending_drag()
        self.cancel_command()
        if self.document.current_space != "Model":
            self.space_tabs.setCurrentIndex(0)
        if self.model_workspace is None:
            self.model_workspace = ModelWorkspace(self, preset or "Isometric", four)
            self.model_workspace.draft_requested.connect(self.show_drafting)
            self.viewport_stack.addWidget(self.model_workspace)
            self.model_dock = QDockWidget("Model browser", self)
            self.model_dock.setObjectName("model_browser_dock")
            self.model_dock.setWidget(self.model_workspace.feature_panel)
            self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.model_dock)
            self.tabifyDockWidget(self.layer_panel, self.model_dock)
        workspace = self.model_workspace
        appearance.style_children(workspace, appearance.settings())
        self.viewport_stack.setCurrentWidget(workspace)
        workspace.layout_mode.setCurrentIndex(0 if four else 1)
        workspace.refresh()
        if preset is not None:
            workspace.change_view(preset)
        self.model_dock.show()
        self.model_dock.raise_()
        workspace.active.setFocus()
        self.workspace_label.setText("MODEL VIEWS")
        self.tool_label.setText("Orbit: left-drag • Pan: middle-drag • Wheel: zoom • Esc: drafting")

    def start_orbit(self, *_args):
        four = self.model_workspace is not None and self.model_workspace.layout_mode.currentIndex() == 0
        self.open_model_workspace(four=four)
        self.model_workspace.change_view("Free orbit")

    def show_drafting(self):
        self.viewport_stack.setCurrentWidget(self.canvas)
        if self.model_dock is not None:
            self.model_dock.hide()
        self.canvas.navigation_pan = False
        self.canvas._panning = False
        self.canvas.setCursor(Qt.CursorShape.CrossCursor)
        if hasattr(self, "draft_navigation"):
            self.draft_navigation.sync(self.draft_camera, "select", drafting=True)
        self.workspace_label.setText("DRAFTING")
        self.update_status()
        self.canvas.setFocus()

    def fit_active(self):
        if self.model_workspace is not None and self.viewport_stack.currentWidget() is self.model_workspace:
            self.model_workspace.active.fit()
        else:
            self.canvas.zoom_extents()

    def zoom_active(self, factor):
        if self.model_workspace is not None and self.viewport_stack.currentWidget() is self.model_workspace:
            self.model_workspace.active.zoom_camera(factor)
        else:
            self.canvas.zoom = max(0.05, min(5000, self.canvas.zoom * factor))
            self.canvas.viewport().update()

    def _dispose_model_workspace(self):
        if self.model_workspace is None:
            return
        self.show_drafting()
        self.model_workspace.disconnect_document()
        self.viewport_stack.removeWidget(self.model_workspace)
        self.model_workspace.deleteLater()
        self.removeDockWidget(self.model_dock)
        self.model_dock.deleteLater()
        self.model_workspace = self.model_dock = None

    def extrude_to_model(self):
        selected = self.canvas.selected_entities
        if len(selected) != 1:
            QMessageBox.information(self,'Extrude','Select one closed circle, rectangle or polyline first.')
            return
        height,ok = QInputDialog.getDouble(self,'Extrude to model','Height in drawing units:',100,-1e9,1e9,4)
        if not ok:return
        try:
            from .model3d import create_extrusion
            create_extrusion(self.document,selected[0],height)
        except ValueError as ex:
            QMessageBox.warning(self,'Extrude',str(ex));return
        self.open_model_workspace()

    def extrude_selected(self):
        selected = self.canvas.selected_entities
        if len(selected) != 1:
            QMessageBox.information(self, "Extrude to STEP/STL",
                                     "Select exactly one closed profile first "
                                     "(a circle, rectangle, or closed polyline).")
            return
        entity = selected[0]
        if not extrude3d.is_extrudable(entity):
            QMessageBox.warning(self, "Extrude to STEP/STL",
                                 "That entity can't be extruded - only circles and "
                                 "closed polylines/rectangles are supported.")
            return
        height, ok = QInputDialog.getDouble(self, "Extrude", "Extrude height:", 10.0, -100000.0, 100000.0, 3)
        if not ok:
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export 3D Solid", "solid.step",
                                               "STEP Files (*.step *.stp);;STL Files (*.stl)")
        if not path:
            return
        try:
            extrude3d.extrude_and_export(entity, height, path)
            QMessageBox.information(self, "Extrude to STEP/STL", f"Exported 3D solid to:\n{path}")
        except extrude3d.ExtrudeError as ex:
            QMessageBox.critical(self, "Extrude Failed", str(ex))
        except ImportError:
            QMessageBox.critical(self, "Extrude Failed",
                                  "The 'cadquery' package isn't installed.\n"
                                  "Install it with:  pip install cadquery")

    # ------------------------------------------------------------------ blocks / xrefs
    def edit_block_dialog(self, name=None):
        names = list(self.document.blocks.keys())
        if not names:
            QMessageBox.information(self, "Edit Block", "No blocks are defined yet.")
            return
        if name is None:
            selected = self.canvas.selected_entities
            name = selected[0].block_name if len(selected) == 1 and selected[0].kind == "INSERT" else None
        if name not in self.document.blocks:
            name, ok = QInputDialog.getItem(self, "Edit Block", "Block:", names, 0, False)
            if not ok:
                return
        block_def = self.document.blocks[name]
        if block_def.is_xref:
            from .xref_manager import source_missing,bind
            if source_missing(self.document,name):
                try:bind(self.document,[name],missing_only=True)
                except (ValueError,OSError) as ex:
                    QMessageBox.warning(self,'Edit Block',str(ex));return
                self.refresh_document_ui()
        if block_def.is_xref:
            QMessageBox.information(self, "Edit Block",
                                     "This is an Xref (sourced from an external file) - "
                                     "edit the source and Reload, or use BIND to make its cached geometry local and editable.")
            return
        dialog = BlockEditorDialog(self, name, block_def)
        if dialog.exec():
            self.document.sync_associative()
            self.canvas.viewport().update()

    def insert_block_dialog(self):
        names = list(self.document.blocks.keys())
        if not names:
            QMessageBox.information(self, "Insert Block", "No blocks are defined yet - "
                                     "use Blocks -> Create Block... first.")
            return
        name, ok = QInputDialog.getItem(self, "Insert Block", "Block:", names, 0, False)
        if not ok:
            return
        self.set_tool("INSERT")
        self.current_tool.preset_block_name = name
        self.current_tool.block_name = name
        self.update_status()

    def attach_xref(self):
        start_dir = appsettings.get_last_directory()
        path, _ = QFileDialog.getOpenFileName(self, "Attach Xref", start_dir, "CAD references (*.dxf *.dwg)")
        if not path:
            return
        try:
            from .xref_manager import attach_gui
            name=attach_gui(self,path)
            if name is None:return
        except Exception as ex:
            QMessageBox.critical(self,'Attach reference failed',str(ex));return
        appsettings.set_last_directory(path)
        self.set_tool("INSERT")
        self.current_tool.preset_block_name = name
        self.current_tool.block_name = name
        self.update_status()

    def reload_all_xrefs(self):
        count = 0
        for name, block_def in self.document.blocks.items():
            if block_def.is_xref:
                self.document.reload_xref(name)
                count += 1
        self.canvas.viewport().update()
        QMessageBox.information(self, "Reload Xrefs", f"Reloaded {count} xref(s).")

    # ------------------------------------------------------------------ layouts
    def new_layout_dialog(self):
        name, ok = QInputDialog.getText(self, "New Layout", "Layout name:", text=f"Layout{len(self.document.layouts) + 1}")
        if not ok or not name:
            return
        if name == "Model" or name in self.document.layouts:
            QMessageBox.warning(self, "New Layout", f"'{name}' already exists.")
            return
        try:
            self.document.create_layout(name)
        except ValueError as ex:
            QMessageBox.warning(self, "New Layout", str(ex))
            return
        self._sync_space_tabs()
        self.space_tabs.setCurrentIndex(next(i for i in range(self.space_tabs.count()) if self.space_tabs.tabText(i) == name))

    def _on_space_tab_changed(self, index: int):
        name = self.space_tabs.tabText(index)
        self.document.current_space = name
        if name != "Model":
            self.show_drafting()
            self.set_tool("SELECT")  # layouts are view-only for now (see README)
        self.canvas.zoom_extents()

    def rename_layout_dialog(self):
        name = self.document.current_space
        if name == "Model" or name not in self.document.layouts:
            QMessageBox.information(self, "Rename Layout", "Switch to a paper-space layout first.")
            return
        new_name, ok = QInputDialog.getText(self, "Rename Layout", "New layout name:", text=name)
        if not ok or not new_name:
            return
        try:
            self.document.edit_layout(name, new_name)
        except ValueError as ex:
            QMessageBox.warning(self, "Rename Layout", str(ex))
            return
        self._sync_space_tabs()
        self.space_tabs.setCurrentIndex(next(i for i in range(self.space_tabs.count()) if self.space_tabs.tabText(i) == new_name))

    def delete_layout(self):
        name = self.document.current_space
        if name == "Model" or name not in self.document.layouts:
            QMessageBox.information(self, "Delete Layout", "Switch to a paper-space layout first.")
            return
        reply = QMessageBox.question(self, "Delete Layout", f"Delete layout '{name}'?")
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.document.edit_layout(name)
        self._sync_space_tabs()
        self.space_tabs.setCurrentIndex(0)

    # ------------------------------------------------------------------ canvas wiring
    def _connect_canvas(self):
        from .command_input import ViewportCommandPrompt
        from .measurements import MeasurementOverlay
        from .dynamic_input import DynamicInput
        self.canvas.command_overlay = ViewportCommandPrompt(self, self.canvas.viewport())
        self.canvas.measurement_overlay = MeasurementOverlay(self, self.canvas.viewport())
        self.canvas.dynamic_input = DynamicInput(self, self.canvas.viewport())
        self.canvas.world_mouse_moved.connect(self._on_mouse_moved)
        self.canvas.world_clicked.connect(self._on_world_clicked)
        self.canvas.key_pressed.connect(self._on_key_pressed)

    @safe_event
    def _on_mouse_moved(self, x, y, snap_kind):
        dynamic = getattr(self.canvas, 'dynamic_input', None)
        if dynamic is not None:
            original = (x,y)
            x,y = dynamic.point(x,y)
            if (x,y) != original:
                snap_kind = 'Input lock'
                self.canvas._snap_point = None
        self.current_world_pos = (x, y)
        self.update_coordinate_readout()
        self.snap_label.setText(snap_kind)
        if self.current_tool:
            self.current_tool.on_move(x, y, snap_kind)
        self.refresh_measurements()

    @safe_event
    def _on_world_clicked(self, x, y, snap_kind, button):
        dynamic = getattr(self.canvas, 'dynamic_input', None)
        if dynamic is not None and dynamic.active and button == Qt.MouseButton.LeftButton.value:
            dynamic.accept_point(x,y)
            return
        self.current_world_pos = (x, y)
        if self.current_tool:
            try:
                self.current_tool.on_click(x, y, snap_kind, button)
            except ValueError as ex:
                self.command_history.appendPlainText("Input error: " + str(ex))
            self.update_status()
            self.refresh_selection_ui()

    @safe_event
    def _on_key_pressed(self, key):
        if key == Qt.Key.Key_Escape and (getattr(self.canvas, "navigation_pan", False) or getattr(self.canvas, "navigation_zoom", False)):
            self.cancel_command()
            return
        if self.current_tool:
            self.current_tool.on_key(key)

    # ------------------------------------------------------------------ tool management
    def set_tool(self, tool_name: str, *, hatch_configured=False):
        if tool_name == 'HATCH' and not hatch_configured:
            if self.document.current_space != 'Model':
                self.command_history.appendPlainText('Switch to Model space to hatch geometry.')
                return
            from .hatch_ui import create_hatch
            create_hatch(self)
            return
        if hasattr(self.canvas, 'dynamic_input'):
            self.canvas.dynamic_input.reset()
        self.dismiss_viewport_input(clear=True)
        if tool_name not in ('SELECT','MENUBAR','ZOOM'):
            self.show_drafting()
        self.canvas.navigation_pan = False
        self.canvas.navigation_zoom = False
        self.canvas._zoom_drag = None
        self.canvas._panning = False
        self.canvas.setCursor(Qt.CursorShape.CrossCursor)
        if hasattr(self, "draft_navigation"):
            self.draft_navigation.sync(self.draft_camera, "select", drafting=True)
        if self.document.current_space != "Model" and tool_name not in ("SELECT", "ADDVIEWPORT", 'MENUBAR', "ZOOM"):
            self.command_history.appendPlainText("Switch to Model space to draw or edit geometry.")
            return
        old_tool = self.current_tool
        if isinstance(old_tool, SelectTool):
            old_tool.cancel_drag()
        tool_cls = TOOL_REGISTRY.get(tool_name)
        if not tool_cls:
            return
        self.current_tool = tool_cls(self)
        if tool_name != "SELECT":
            self.last_command = tool_name
        self.canvas.set_active_tool(self.current_tool)
        # Tools that operate on the current selection (Mirror, Array) need it preserved;
        # pure draw tools should start with a clean selection.
        selection_dependent = {"ZOOM", "MOVE", "MIRROR", "ARRAYRECT", "ARRAYPOLAR", "COPY", "ROTATE", "SCALE", "BLOCK", "XCLIP", "LAYMCH", "MLEADERADD", "MLEADERREMOVE"}
        if tool_name != "SELECT" and tool_name not in selection_dependent:
            self.canvas.selected_entities = []
        editable_ids = {id(e) for e in self.document.editable_entities()}
        self.canvas.selected_entities = [e for e in self.canvas.selected_entities if id(e) in editable_ids]
        self.update_status()
        self.canvas.viewport().update()
        self.focus_active_viewport()
        self.refresh_measurements()

    def refresh_measurements(self):
        if hasattr(self.canvas, 'dynamic_input'):
            self.canvas.dynamic_input.refresh()
        overlay = getattr(self.canvas, "measurement_overlay", None)
        if overlay is not None:
            overlay.refresh()

    def update_coordinate_readout(self):
        if self.current_world_pos is not None:
            from .units import format_length
            units = self.document.units if self.document.current_space == "Model" else "mm"
            x, y = [format_length(v, units, self.document.unit_settings, False) for v in self.current_world_pos]
            text = f"X: {x}  Y: {y}"
            self.coord_label.setToolTip(text)
            self.coord_label.setText(self.coord_label.fontMetrics().elidedText(text, Qt.TextElideMode.ElideRight, 280))

    def toggle_cursor_dimensions(self):
        appsettings.get_settings().setValue("drafting/cursor_dimensions", self.cursor_dimensions_action.isChecked())
        self.refresh_measurements()

    def toggle_measurements(self):
        if hasattr(self.canvas, 'dynamic_input') and not self.dynamic_action.isChecked():
            self.canvas.dynamic_input.reset()
            self.focus_active_viewport()
        appsettings.get_settings().setValue("drafting/live_measurements", self.dynamic_action.isChecked())
        self.refresh_measurements()

    def tool_finished(self):
        # after a draw command finishes, return to Select tool (AutoCAD behavior)
        self.set_tool("SELECT")

    def update_status(self):
        self.render_command_options()
        if getattr(self.canvas, "navigation_zoom", False):
            self.tool_label.setText("ZOOM Realtime: Drag up/down to zoom; Esc to finish")
            self.command_prompt_label.setText("ZOOM:")
            return
        if self.model_workspace is not None and self.viewport_stack.currentWidget() is self.model_workspace:
            self.tool_label.setText(self.current_tool.status_prompt() if self.current_tool and self.current_tool.name != "SELECT" else "Orbit: left-drag • Pan: middle-drag • Wheel: zoom • Esc: drafting")
            self.command_prompt_label.setText(self.current_tool.name + ":" if self.current_tool and self.current_tool.name != "SELECT" else "Command:")
            return
        if self.current_tool:
            self.tool_label.setText(self.current_tool.status_prompt())
            self.command_prompt_label.setText(self.current_tool.name + ":")

    # ------------------------------------------------------------------ edit ops
    def undo(self):
        if hasattr(self.canvas, 'dynamic_input'):
            self.canvas.dynamic_input.reset()
        if isinstance(self.current_tool, SelectTool):
            self.current_tool.cancel_drag()
        self.document.undo_stack.undo()
        self.canvas.viewport().update()

    def redo(self):
        if hasattr(self.canvas, 'dynamic_input'):
            self.canvas.dynamic_input.reset()
        if isinstance(self.current_tool, SelectTool):
            self.current_tool.cancel_drag()
        self.document.undo_stack.redo()
        self.canvas.viewport().update()

    def delete_selected(self):
        if isinstance(self.current_tool, SelectTool):
            self.current_tool.on_key(Qt.Key.Key_Delete)
            self.canvas.viewport().update()

    def toggle_grid(self):
        self.canvas.grid_enabled = self.grid_action.isChecked()
        self.canvas.viewport().update()

    def toggle_snap(self):
        self.canvas.snap_enabled = self.snap_action.isChecked()

    def toggle_ortho(self):
        self.canvas.ortho_enabled = self.ortho_action.isChecked()

    def toggle_gl_rendering(self):
        use_gl = self.gl_render_action.isChecked()
        self.switch_renderer("opengl" if use_gl else "software")

    def switch_renderer(self, backend: str):
        """Compatibility entry point; retain the existing canvas and live tool."""
        self.graphics.set_mode("hardware" if backend == "opengl" else "software")

    def graphics_dialog(self):
        from .graphics_ui import show_dialog
        show_dialog(self)

    def _sync_graphics_actions(self):
        for mode, action in self.graphics_actions.items():
            action.setChecked(mode == self.graphics.mode)
        text = "GPU…" if self.graphics.process is not None else "GPU / OpenGL" if self.graphics.backend == "opengl" else "CPU / GPU"
        self.graphics_button.setText(text)
        self.graphics_button.setToolTip("Active renderer: " + self.graphics.backend + " · " + self.graphics.reason + "\nChoose CPU / GPU and Cached / Direct drawing. Calculations and imports remain on CPU.")

    def _connect_document(self):
        self.document.undo_stack.indexChanged.connect(self.refresh_document_ui)
        self.document.undo_stack.rejected.connect(self._constraint_edit_rejected)

    def _constraint_edit_rejected(self, message):
        self.command_history.appendPlainText("Constraint conflict: " + message)
        self.statusBar().showMessage("Edit rejected by constraints. See command history.", 8000)
        self.refresh_document_ui()

    def refresh_selection_ui(self):
        self.canvas.selected_entities = [e for e in self.canvas.selected_entities if self.document.is_editable(e)]
        self.properties_panel.refresh()
        self.refresh_measurements()
        self.canvas.viewport().update()

    @safe_event
    def refresh_document_ui(self, *_args, _ui_only=False):
        from .edit_journal import active, revision, invalidate
        fast = active(self.document)
        if not _ui_only:
            self.document.render_revision += 1
            if fast: revision(self.document)
            else: invalidate(self.document)
        if fast and not _ui_only:
            from .efficiency import schedule_recovery
            schedule_recovery(self)
            self.undo_action.setEnabled(self.document.undo_stack.canUndo())
            self.redo_action.setEnabled(self.document.undo_stack.canRedo())
            self.canvas.viewport().update()
            timer = self.__dict__.get('_drafting_ui_timer')
            if timer is None:
                from PyQt6.QtCore import QTimer
                timer = QTimer(self)
                timer.setSingleShot(True)
                timer.timeout.connect(self._refresh_drafting_panels)
                self._drafting_ui_timer = timer
            timer.start(120)
            return
        from .efficiency import schedule_recovery
        schedule_recovery(self)
        if hasattr(self,"drawing_tabs"): self.drawing_tabs.refresh()
        self._sync_space_tabs()
        self.canvas.selected_entities = [e for e in self.canvas.selected_entities if self.document.is_editable(e)]
        self.canvas.viewport().update()
        if hasattr(self, "properties_panel"):
            self.properties_panel.refresh()
        if hasattr(self, 'drafting_chat'):
            self.drafting_chat.refresh_session()
        if hasattr(self, "layer_panel"):
            self.layer_panel.refresh()
        name = os.path.basename(self.document.filepath) if self.document.filepath else "Untitled.pycad"
        from .document_tabs import modified_for_ui
        self.setWindowTitle(f"PY.cad {__version__} — {name}" + (" *" if modified_for_ui(self.document) else ""))
        self.undo_action.setEnabled(self.document.undo_stack.canUndo())
        self.redo_action.setEnabled(self.document.undo_stack.canRedo())
        if hasattr(self, "units_button"):
            self.units_button.setText(self.document.units)
        self.update_coordinate_readout()
        self.refresh_measurements()

    def _refresh_drafting_panels(self):
        self.refresh_document_ui(_ui_only=True)

    def _sync_space_tabs(self):
        """Keep the Model/Paper Space tab bar in sync with undoable layout edits."""
        if not hasattr(self, "space_tabs"):
            return
        current = self.document.current_space
        names = ["Model", *self.document.layouts.keys()]
        existing = [self.space_tabs.tabText(i) for i in range(self.space_tabs.count())]
        if existing == names:
            return
        self.space_tabs.blockSignals(True)
        while self.space_tabs.count():
            self.space_tabs.removeTab(0)
        for name in names:
            self.space_tabs.addTab(name)
        index = names.index(current) if current in names else 0
        self.space_tabs.setCurrentIndex(index)
        self.document.current_space = names[index]
        self.space_tabs.blockSignals(False)

    def _replace_document(self, document):
        if hasattr(self,"drawing_tabs"): self.drawing_tabs.replace_active(document)
        self.cancel_command()
        self._dispose_model_workspace()
        try:
            self.document.undo_stack.indexChanged.disconnect(self.refresh_document_ui)
            self.document.undo_stack.rejected.disconnect(self._constraint_edit_rejected)
        except TypeError:
            pass
        self.document = document
        self.canvas.document = document
        self.canvas.selected_entities = []
        self.canvas.selected_viewport = None
        self.canvas.rubber_band_start = self.canvas.rubber_band_end = None
        self.current_world_pos = None
        self.current_tool = None
        self.space_tabs.blockSignals(True)
        while self.space_tabs.count():
            self.space_tabs.removeTab(0)
        self.space_tabs.addTab("Model")
        for name in document.layouts:
            self.space_tabs.addTab(name)
        document.current_space = "Model"
        self.space_tabs.setCurrentIndex(0)
        self.space_tabs.blockSignals(False)
        self.linetype_combo.setCurrentText(document.current_linetype)
        self.layer_panel.refresh()
        self._connect_document()
        self.set_tool("SELECT")
        self.canvas.zoom_extents()
        self.refresh_document_ui()

    def _confirm_save_changes(self):
        if not self.document.dirty:
            return True
        reply = QMessageBox.warning(self, "Unsaved drawing", "Save changes before continuing?",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save)
        if reply == QMessageBox.StandardButton.Cancel:
            return False
        if reply == QMessageBox.StandardButton.Save:
            return bool(self.save_file())
        return True

    def new_file(self):
        template=appsettings.get_settings().value('templates/default','')
        if template:
            try:
                from .drafting import open_template
                doc=open_template(template)
            except (OSError,ValueError,TypeError) as exc:
                QMessageBox.warning(self,'Default template unavailable',str(exc)+'\nA blank drawing will be opened.');doc=Document()
        else:doc=Document()
        self.drawing_tabs.add_document(doc)
        return True

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Drawing", appsettings.get_last_directory(),
            "CAD Drawings (*.pycad *.dxf *.dwg);;PY.cad Project (*.pycad);;DXF (*.dxf);;DWG (*.dwg)")
        return self._open_path(path) if path else False

    def _open_path(self, path, confirm=True):
        import time
        from .drawing_diagnostics import record
        _open_started=time.perf_counter()
        record('open.start',path)
        for i,session in enumerate(self.drawing_tabs.sessions):
            if session['doc'].filepath and os.path.abspath(session['doc'].filepath)==os.path.abspath(path):
                self.drawing_tabs.setCurrentIndex(i)
                return True
        try:
            if str(path).lower().endswith(('.dxf', '.dwg')):
                from .import_ui import load_dxf
                if str(path).lower().endswith(".dwg"):
                    from .dwg_ui import load_dwg
                    document = load_dwg(self, path)
                else:
                    document = load_dxf(self, path)
                if document is None:
                    self.statusBar().showMessage("Drawing opening cancelled; current drawing unchanged", 5000)
                    return False
            else:
                document = dxf_io.import_any(path)
            record('open.ready',path,seconds=time.perf_counter()-_open_started,entities=len(document.entities),notices=list(document.import_warnings))
            self.drawing_tabs.add_document(document)
            if document.import_warnings:
                report = QMessageBox(QMessageBox.Icon.Warning, "Import report",
                    f"Opened with {len(document.import_warnings)} import notices. Some content is unsupported or approximated.\n\nSave to a new file to protect the source drawing.",
                    QMessageBox.StandardButton.Ok, self)
                details = "\n".join(document.import_warnings[:200])
                if len(document.import_warnings) > 200:
                    details += "\nAdditional notices are retained in the drawing's import report."
                report.setDetailedText(details)
                report.setWindowModality(Qt.WindowModality.NonModal)
                self._import_report = report
                report.show()
                self.command_history.appendPlainText("Import report: " + details)
            appsettings.set_last_directory(path)
            appsettings.add_recent_file(path)
            self._refresh_recent_files_menu()
            return True
        except dxf_io.DWGSupportError as ex:
            record("open.failed",path,error=str(ex),seconds=time.perf_counter()-_open_started)
            QMessageBox.warning(self, "DWG Support Not Available", str(ex))
            return False
        except Exception as ex:
            record("open.failed",path,error=str(ex),seconds=time.perf_counter()-_open_started)
            logger.exception("Failed to open %s", path)
            QMessageBox.critical(self, "Open Failed", str(ex))
            return False

    def open_recent_file(self, path):
        return self._open_path(path)

    def save_file(self):
        self._finish_pending_drag()
        if self.document.filepath and self.document.filepath.lower().endswith(".pycad"):
            return self._save_to_path(self.document.filepath)
        return self.save_file_as()

    def save_file_as(self):
        path, file_filter = QFileDialog.getSaveFileName(self, "Save Drawing",
            os.path.join(appsettings.get_last_directory(), "drawing.pycad"),
            "PY.cad Project (*.pycad);;DXF Files (*.dxf);;DWG Files (*.dwg)")
        if not path:
            return False
        if not os.path.splitext(path)[1]:
            path += ".dwg" if "DWG" in file_filter else ".dxf" if "DXF" in file_filter else ".pycad"
        return self._save_to_path(path)

    def _finish_pending_drag(self):
        finish = getattr(self.current_tool, "finish_drag", None)
        if finish:
            finish()

    def _save_to_path(self, path):
        self._finish_pending_drag()
        try:
            if not path.lower().endswith(".pycad"):
                warnings = dxf_io.export_warnings(self.document)
                if path.lower().endswith('.dwg'):
                    warnings.insert(0, 'DWG export creates a supported 2D drawing copy. Bundled LibreDWG writes R2000 DWG, using a DXF bridge; modern/proxy objects and unsupported source content are not preserved. Keep your original DWG and an editable .pycad master.')
                if warnings:
                    reply = QMessageBox.warning(self, "Interchange export", "\n".join(warnings)+
                        "\n\nContinue exporting? Use .pycad to retain the editable project.",
                        QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel)
                    if reply != QMessageBox.StandardButton.Save:
                        return False
            dxf_io.export_any(self.document, path)
            if path.lower().endswith(".pycad"):
                self.document.filepath = path
                self.document.mark_saved()
                from .efficiency import reconcile_saved_recovery
                reconcile_saved_recovery(self)
            else:
                self.command_history.appendPlainText("Exported interchange drawing. Save a .pycad project to retain all editable data.")
            appsettings.set_last_directory(path)
            appsettings.add_recent_file(path)
            self._refresh_recent_files_menu()
            self.refresh_document_ui()
            return path.lower().endswith(".pycad") or not self.document.dirty
        except dxf_io.DWGSupportError as ex:
            QMessageBox.warning(self, "DWG Support Not Available", str(ex))
            return False
        except Exception as ex:
            logger.exception("Failed to save %s", path)
            QMessageBox.critical(self, "Save Failed", str(ex))
            return False

    def print_to_pdf(self):
        path, _ = QFileDialog.getSaveFileName(self, "Vector PDF Plot", appsettings.get_last_directory(), "PDF (*.pdf)")
        if not path:
            return
        if not path.lower().endswith(".pdf"):
            path += ".pdf"
        ratio = None
        if self.document.current_space == "Model":
            choice, ok = QInputDialog.getItem(self, "Plot scale", "A4 landscape / 10 mm margin:",
                ["Fit extents", "1:1", "1:10", "1:20", "1:50", "1:100", "1:200"], 0, False)
            if not ok:
                return
            if choice != "Fit extents":
                ratio = float(choice.split(":")[1])
        try:
            from .plotting import export_pdf
            export_pdf(self.document, path, self.document.current_space, ratio)
            self.command_history.appendPlainText("Vector PDF saved: " + path)
        except Exception as ex:
            QMessageBox.critical(self, "Plot failed", str(ex))

    def viewport_scale_dialog(self):
        viewport = self.canvas.selected_viewport
        if self.document.current_space == "Model" or viewport is None:
            QMessageBox.information(self, "Viewport scale", "Select a viewport on a Layout tab first.")
            return
        denominator, ok = QInputDialog.getDouble(self, "Viewport scale", "Paper/model ratio 1 :", 100, 0.001, 1000000, 3)
        if ok:
            from .document import SetAttrCommand
            factor = {"mm":1,"cm":10,"m":1000,"in":25.4,"ft":304.8,"unitless":1}[self.document.units]
            self.document.undo_stack.push(SetAttrCommand(self.document, viewport, "scale", viewport.scale, factor/denominator, "Viewport scale"))

    def units_dialog(self):
        from .units import units_dialog
        units_dialog(self)

    def _refresh_recent_files_menu(self):
        self.recent_files_menu.clear()
        recent = appsettings.get_recent_files()
        if not recent:
            empty_action = QAction("(no recent files)", self)
            empty_action.setEnabled(False)
            self.recent_files_menu.addAction(empty_action)
            return
        for path in recent:
            action = QAction(path, self)
            action.triggered.connect(lambda checked, p=path: self.open_recent_file(p))
            self.recent_files_menu.addAction(action)

    # ------------------------------------------------------------------ autosave / recovery
    def _build_autosave(self):
        self.autosave_timer = QTimer(self)
        self.autosave_timer.setInterval(max(15000,min(86400000,int(float(appsettings.get_settings().value('recovery/interval_minutes',1))*60000))))
        self.autosave_timer.timeout.connect(self._do_autosave)
        self.autosave_timer.start()
        self._recovery_debounce=QTimer(self);self._recovery_debounce.setSingleShot(True);self._recovery_debounce.timeout.connect(self._do_autosave)

    def _do_autosave(self):
        if isinstance(self.current_tool, SelectTool) and (
            self.current_tool.dragging_entity or self.current_tool.grip_entity is not None
        ):
            return  # A drag is a preview until committed through the constraint solver.
        if not any(s['doc'].dirty for s in self.drawing_tabs.sessions): return
        try:
            from .document_tabs import save_recovery
            save_recovery(self)
            from .recovery_history import archive_autosave
            archive_autosave(self)
            logger.info("Autosaved recovery snapshot (%d entities)", len(self.document.entities))
        except Exception:
            logger.exception("Autosave failed")

    def _offer_recovery_if_present(self):
        from .efficiency import recover_startup
        if recover_startup(self):return
        if not appsettings.recovery_file_exists():
            return
        reply = QMessageBox.question(
            self, "Recover Unsaved Work?",
            "PY.cad found a recovery snapshot from a previous session that didn't "
            "close normally. Would you like to open it?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            from .document_tabs import load_recovery_tabs
            try: restored=load_recovery_tabs(self)
            except (ValueError,OSError) as ex:
                self.command_history.appendPlainText('Tab recovery failed: '+str(ex));restored=False
            if restored:
                from .document_tabs import clear_recovery_tabs
                clear_recovery_tabs();appsettings.mark_clean_exit();return
            if not self._open_path(appsettings.RECOVERY_PATH,confirm=False): return
            self.document._force_dirty = True
            self.document.filepath = None  # recovered content is unsaved until the person saves it
            self.setWindowTitle("PY.cad - Untitled.dxf (recovered)")
        from .document_tabs import clear_recovery_tabs
        clear_recovery_tabs()
        appsettings.mark_clean_exit()  # either way, don't ask again for this snapshot

    def closeEvent(self, event):
        self._finish_pending_drag()
        if not self.drawing_tabs.confirm_all():
            event.ignore()
            return
        self.autosave_timer.stop()
        self._recovery_debounce.stop()
        self.graphics.shutdown()
        self.layer_hide_timer.stop()
        if getattr(self,"action_recorder",None): self.action_recorder.stop();self.action_recorder=None
        if hasattr(self, 'file_workspace'):
            self.removeEventFilter(self.file_workspace)
        try:
            QApplication.instance().focusChanged.disconnect(self._command_focus_changed)
        except (TypeError, RuntimeError):
            pass
        try:
            self.document.undo_stack.indexChanged.disconnect(self.refresh_document_ui)
        except (TypeError, RuntimeError):
            pass
        appsettings.save_window_geometry(self)
        from .document_tabs import clear_recovery_tabs
        clear_recovery_tabs()
        appsettings.mark_clean_exit()
        self._dispose_model_workspace()
        super().closeEvent(event)

    def show_about(self):
        branding.AboutDialog(self).exec()

    def show_legal(self):
        branding.AboutDialog(self, legal=True).exec()
