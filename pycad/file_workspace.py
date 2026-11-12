"""In-window File workspace and native drawing utilities."""

from collections import Counter
from pathlib import Path
from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QUndoCommand
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QVBoxLayout,
    QListWidget,
    QLabel,
    QPushButton,
    QScrollArea,
    QWidget,
    QFileDialog,
    QMessageBox,
    QDialog,
    QPlainTextEdit,
    QDialogButtonBox,
)
from . import appsettings
from .native_io import document_to_dict, document_from_dict, load_project, save_project

CATEGORIES = (
    "New",
    "Open",
    "Save",
    "Save As",
    "Import",
    "Export",
    "Publish",
    "Print",
    "Drawing Utilities",
    "Close",
)


def show_report(window, title, text):
    dialog = QDialog(window)
    dialog.setWindowTitle(title)
    dialog.resize(640, 460)
    layout = QVBoxLayout(dialog)
    content = QPlainTextEdit()
    content.setReadOnly(True)
    content.setPlainText(text)
    layout.addWidget(content)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    dialog.exec()


def audit_document(doc):
    """Validate the current native model without changing it or claiming repair."""
    document_from_dict(document_to_dict(doc))
    return (
        f"PASS — native drawing validation\n\n{len(doc.entities)} model objects\n"
        f"{len(doc.blocks)} block definitions\n{len(doc.layers.layers)} layers\n"
        f"{len(doc.constraints)} persistent constraints\n{len(doc.layouts)} layouts\n\n"
        "Checked native structure, supported geometry, references, styles, layers and constraint consistency.\n"
        "No drawing data was changed. External reference files, DWG internals and engineering validity are not audited."
    )


def audit(window):
    window._finish_pending_drag()
    try:
        text = audit_document(window.document)
    except (ValueError, TypeError, KeyError) as error:
        text = (
            "FAIL — "
            + str(error)
            + "\n\nNo automatic repair was attempted. Restore a valid backup or correct the reported data."
        )
    show_report(window, "Drawing Audit", text)


def status(window):
    doc = window.document
    counts = Counter(e.kind for e in doc.entities)
    text = (
        f"File: {doc.filepath or 'Untitled'}\nUnsaved changes: {'Yes' if doc.dirty else 'No'}\n"
        f"Drawing units: {doc.units}\nCurrent layer: {doc.layers.current_layer}\n"
        f"Objects: {len(doc.entities)}\nLayers: {len(doc.layers.layers)}\n"
        f"Blocks: {len(doc.blocks)}\nLayouts: {len(doc.layouts)}\n"
        f"Saved extrusions: {len(doc.extrusions)}\nConstraints: {len(doc.constraints)}\n\n"
        + "\n".join(f"{kind}: {count}" for kind, count in sorted(counts.items()))
    )
    show_report(window, "Drawing Status", text)


def purge_candidates(doc):
    # Retain referenced blocks recursively; external references remain attached.
    keep = {name for name, b in doc.blocks.items() if b.is_xref}
    pending = [e.block_name for e in doc.entities if e.kind == "INSERT"] + list(keep)
    visited = set()
    while pending:
        name = pending.pop()
        if name in visited:
            continue
        visited.add(name)
        keep.add(name)
        if name in doc.blocks:
            pending.extend(
                e.block_name for e in doc.blocks[name].entities if e.kind == "INSERT"
            )
    retained = doc.entities + [
        e for n, b in doc.blocks.items() if n in keep for e in b.entities
    ]
    layers = (
        {"0", doc.layers.current_layer}
        | {e.layer for e in retained}
        | {e["layer"] for e in doc.extrusions}
    )
    retained_attributes=[spec for name,block in doc.blocks.items() if name in keep for spec in block.attributes]
    layers.update(spec["layer"] for spec in retained_attributes)
    layers.update(solid["layer"] for solid in doc.extensions.get("solids",{}).values())
    if doc.cad_standard:
        layers.update(doc.cad_standard["layers"])
    styles = {"Standard", doc.current_dimstyle} | {
        e.style_name for e in retained if hasattr(e, 'style_name') and e.kind not in ('TEXT', 'MLEADER')
    }
    textstyles = {'Standard', doc.current_textstyle} | {e.style_name for e in retained if e.kind == 'TEXT'}
    textstyles.update(spec['style_name'] for spec in retained_attributes)
    mleaderstyles = {'Standard', doc.current_mleaderstyle} | {e.style_name for e in retained if e.kind == 'MLEADER'}
    return {
        "blocks": sorted(set(doc.blocks) - keep),
        "layers": sorted(set(doc.layers.layers) - layers),
        "styles": sorted(set(doc.dimstyles) - styles),
        "textstyles": sorted(set(doc.textstyles) - textstyles),
        "mleaderstyles": sorted(set(doc.mleaderstyles) - mleaderstyles),
    }


class PurgeCommand(QUndoCommand):
    def __init__(self, doc, candidates):
        super().__init__("Purge unused definitions")
        self.doc = doc
        self.before = (dict(doc.blocks), dict(doc.layers.layers), dict(doc.dimstyles), dict(doc.textstyles), dict(doc.mleaderstyles))
        self.after = tuple(
            {key: value for key, value in table.items() if key not in candidates[kind]}
            for table, kind in zip(self.before, ("blocks", "layers", "styles", "textstyles", "mleaderstyles"))
        )

    def apply(self, tables):
        self.doc.blocks, self.doc.layers.layers, self.doc.dimstyles, self.doc.textstyles, self.doc.mleaderstyles = [
            dict(t) for t in tables
        ]

    def redo(self):
        self.apply(self.after)

    def undo(self):
        self.apply(self.before)


def purge(window):
    window._finish_pending_drag()
    doc = window.document
    candidates = purge_candidates(doc)
    if not any(candidates.values()):
        QMessageBox.information(
            window,
            "Purge",
            "No unused local blocks, layers or annotation styles to remove.",
        )
        return
    lines = [
        f"{key.title()} ({len(names)}): "
        + ", ".join(names[:20])
        + ("…" if len(names) > 20 else "")
        for key, names in candidates.items()
        if names
    ]
    if (
        QMessageBox.question(
            window,
            "Purge unused definitions",
            "\n".join(lines)
            + "\n\nRemove these unused definitions? This can be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        == QMessageBox.StandardButton.Yes
    ):
        doc.undo_stack.push(PurgeCommand(doc, candidates))
        window.refresh_document_ui()


def absolute_references(doc, origin):
    for block in doc.blocks.values():
        if block.source_filepath and not Path(block.source_filepath).is_absolute():
            block.source_filepath = str(
                (Path(origin).resolve().parent / block.source_filepath).resolve()
            )


def load_as_new(window, path, recovered=False):
    try:
        doc = load_project(path)
        absolute_references(doc, path)
        doc.filepath = None
        doc._force_dirty = recovered
        window.drawing_tabs.add_document(doc)
        if not recovered:
            doc.mark_saved()
        window.refresh_document_ui()
        window.command_history.appendPlainText(
            (
                "Recovered validated native backup: "
                if recovered
                else "New drawing from template: "
            )
            + str(path)
        )
        return True
    except (OSError, ValueError) as error:
        QMessageBox.warning(window, "Cannot load native drawing", str(error))
        return False


def from_template(window):
    path, _ = QFileDialog.getOpenFileName(
        window,
        "New from native template",
        appsettings.get_last_directory(),
        "PY.cad template (*.pycadt);;PY.cad drawing (*.pycad)",
    )
    if path:
        return load_as_new(window, path)
    return False


def save_template(window):
    window._finish_pending_drag()
    path, _ = QFileDialog.getSaveFileName(
        window,
        "Save native drawing template",
        "drawing-template.pycadt",
        "PY.cad template (*.pycadt)",
    )
    if not path:
        return False
    if not path.lower().endswith(".pycadt"):
        path += ".pycadt"
    doc = document_from_dict(document_to_dict(window.document))
    absolute_references(
        doc, window.document.filepath or str(Path.cwd() / "drawing.pycad")
    )
    save_project(doc, path)
    window.command_history.appendPlainText(
        "Template saved with geometry, units, layers, styles and layouts: " + path
    )
    return True


def recover(window):
    path, _ = QFileDialog.getOpenFileName(
        window,
        "Recover validated native drawing or backup",
        appsettings.get_last_directory(),
        "PY.cad / backup (*.pycad *.pycad.bak *.pycadt *.pycadt.bak);;Backup (*.bak)",
    )
    if path:
        return load_as_new(window, path, True)
    return False


def import_drawing(window, extension):
    path, _ = QFileDialog.getOpenFileName(
        window,
        "Open " + extension.upper() + " drawing",
        appsettings.get_last_directory(),
        extension.upper() + " (*." + extension + ")",
    )
    if path:
        return window._open_path(path)
    return False


def export_drawing(window, extension):
    path, _ = QFileDialog.getSaveFileName(
        window,
        "Export " + extension.upper(),
        "drawing." + extension,
        extension.upper() + " (*." + extension + ")",
    )
    if path:
        if not path.lower().endswith("." + extension):
            path += "." + extension
        return window._save_to_path(path)
    return False


def entries(window):
    run = lambda name: lambda: window.run_ribbon_command(name)
    pending = "Not yet implemented in this build."
    return {
        "New": [
            ("Drawing", "Start a blank native drawing. Ctrl+N", window.new_file),
            (
                "Drawing from template",
                "Use a .pycadt template or .pycad drawing as a new document.",
                lambda: from_template(window),
            ),
            (
                "Layout / sheet",
                "Add a paper-space layout to the current drawing.",
                run("NEWLAYOUT"),
            ),
            (
                "Sheet set",
                "Manage layouts, title blocks, viewport scales and combined PDF publishing.",
                run("SHEETSET"),
            ),
        ],
        "Open": [
            (
                "Drawing",
                "Open .pycad, DXF or DWG (LibreDWG reader included on Windows/Linux x64). Ctrl+O",
                window.open_file,
            ),
            (
                "DWF / DWFx",
                pending + " These are publishing formats, not native PY.cad drawings.",
                None,
            ),
            ("Sheet set", "Open the current drawing sheet manager.", run("SHEETSET")),
        ]
        + [
            (Path(p).name, p, lambda path=p: window.open_recent_file(path))
            for p in appsettings.get_recent_files()
        ],
        "Save": [
            ("Save drawing", "Save the native .pycad drawing. Ctrl+S", window.save_file)
        ],
        "Save As": [
            (
                "Drawing",
                "Save a new native drawing or supported DXF/DWG interchange file. Ctrl+Shift+S",
                window.save_file_as,
            ),
            (
                "Drawing template",
                "Save a reusable PY.cad .pycadt template, including current geometry. Not Autodesk DWT.",
                lambda: save_template(window),
            ),
            (
                "DXF",
                "Export supported 2D drawing geometry.",
                lambda: export_drawing(window, "dxf"),
            ),
            (
                "DWG",
                "Export through a separately installed ODA File Converter.",
                lambda: export_drawing(window, "dwg"),
            ),
        ],
        "Import": [
            (
                "DXF drawing",
                "Open as the current drawing; unsaved changes are checked first.",
                lambda: import_drawing(window, "dxf"),
            ),
            (
                "DWG drawing",
                "Open using the external ODA converter.",
                lambda: import_drawing(window, "dwg"),
            ),
            (
                "Attach DXF reference",
                "Attach supported DXF content to the current drawing.",
                run("DXFATTACH"),
            ),
            ('PDF underlay', 'Attach one PDF page as an embedded raster reference; calibrate its scale for tracing.', run('PDFATTACH')),
            ('Image underlay', 'Attach a PNG/JPEG or other supported raster image.', run('IMAGEATTACH')),
            ('Manage underlays', 'Placement, rotation, opacity, lock, visibility and two-point calibration.', run('UNDERLAYS')),
        ]
        + [
            (name, pending + " Use supported DXF geometry where possible.", None)
            for name in ("PDF to editable geometry", "DGN", "IFC", "STL", "Point cloud")
        ],
        "Export": [
            (
                "PDF",
                "Export a vector plot of model space or the active layout.",
                run("EXPORTPDF"),
            ),
            (
                "DXF",
                "Export the supported 2D subset.",
                lambda: export_drawing(window, "dxf"),
            ),
            (
                "DWG",
                "Requires the ODA converter; unsupported native features are reported.",
                lambda: export_drawing(window, "dwg"),
            ),
            (
                "STEP / STL solid",
                "Export a saved extrusion or B-rep solid with optional CadQuery.",
                run("SOLIDTOOLS"),
            ),
        ]
        + [(name, pending, None) for name in ("DWF", "DWFx", "FBX", "3D DWF")],
        "Publish": [
            ('Drawing sheet set PDF','Publish checked layouts to one ordered vector PDF.',run('PUBLISH')),
            ('Shared view', 'Save a portable read-only 2D HTML view with pan, zoom and print.', run('SHAREDVIEWS')),
            ('Cloud files', 'Upload/download using your configured WebDAV server.', run('CLOUD')),
            (
                "Share package (eTransmit)",
                "Create a local ZIP with the native drawing and direct DXF references.",
                run("ETRANSMIT"),
            ),
            (
                "Email",
                pending + " Save a share package and attach it in your email app.",
                None,
            ),
            (
                "Send to 3D print service",
                pending
                + " Export STL for manual submission; no service upload is connected.",
                None,
            ),
        ],
        "Print": [
            ("Plot / PDF", "Create a vector PDF. Ctrl+P", window.print_to_pdf),
            ("Plot preview", "Preview the PDF before exporting.", run("PLOTPREVIEW")),
            (
                "Page setup",
                "Configure a layout's paper size and orientation.",
                run("PAGESETUP"),
            ),
            (
                "Batch plot",
                "Export model/layout PDF sheets into a ZIP.",
                run("BATCHPLOT"),
            ),
        ],
        "Drawing Utilities": [
            (
                "Audit",
                "Validate native objects, references, tables and constraints without changing them.",
                lambda: audit(window),
            ),
            (
                "Recover",
                "Open a valid native backup as an unsaved drawing; corrupt/DWG repair is not available.",
                lambda: recover(window),
            ),
            (
                "Purge",
                "Remove unused local blocks, layers and dimension styles with preview and undo.",
                lambda: purge(window),
            ),
            (
                "Units",
                "Drawing units, length/angle display and precision.",
                window.units_dialog,
            ),
            (
                "Status",
                "Inspect document contents and save state.",
                lambda: status(window),
            ),
        ],
        "Close": [
            (
                "Close drawing",
                "Check unsaved changes and return to a blank drawing.",
                lambda:window.drawing_tabs.close_drawing(window.drawing_tabs.active),
            ),
            (
                "Exit PY.cad",
                "Check unsaved changes and close the application. Ctrl+Q",
                window.close,
            ),
        ],
    }


class FileWorkspace(QFrame):
    """A child panel, not a detached application window."""

    def __init__(self, window):
        super().__init__(window)
        self.mw = window
        self.setObjectName("file_workspace")
        self.setStyleSheet("""
            QFrame#file_workspace { background:#18212d; border-top:1px solid #3c5367; }
            QListWidget { background:#121c27; border:0; font-size:12px; }
            QListWidget::item { padding:7px 9px; border-left:3px solid transparent; }
            QListWidget::item:selected { background:#254657; border-left:3px solid #72d5eb; }
            QPushButton[fileAction="true"] { text-align:left; padding:7px 10px; background:#253343; border:1px solid #40566b; font-size:12px; }
            QPushButton[fileAction="true"]:hover { background:#304c61; border-color:#69bfd9; }
            QPushButton[fileAction="true"]:disabled { background:#1b2732; color:#7f91a3; border-color:#344353; }
            QLabel[fileDescription="true"] { color:#abc0ce; padding:0 14px 10px 14px; }
        """)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(9, 8, 9, 9)
        heading = QHBoxLayout()
        back = QPushButton("Close File")
        back.setObjectName("file_back")
        back.clicked.connect(self.dismiss)
        heading.addWidget(back)
        heading.addStretch()
        self.filename = QLabel()
        heading.addWidget(self.filename)
        outer.addLayout(heading)
        body = QHBoxLayout()
        self.categories = QListWidget()
        self.categories.setObjectName("file_categories")
        self.categories.addItems(CATEGORIES)
        self.categories.setFixedWidth(145)
        self.categories.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body.addWidget(self.categories)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        body.addWidget(self.scroll, 1)
        outer.addLayout(body, 1)
        self.detail = QLabel('Choose a drawing action.')
        self.detail.setWordWrap(True)
        self.detail.setTextFormat(Qt.TextFormat.PlainText)
        self.detail.setMinimumHeight(32)
        self.detail.setMaximumHeight(48)
        outer.addWidget(self.detail)
        self.categories.currentRowChanged.connect(self.select_category)
        window.installEventFilter(self)
        self.hide()

    def open(self):
        self.mw.cancel_command()
        from .appearance import style_children, settings
        style_children(self, settings())
        from .appearance import colors
        self.categories.setStyleSheet('QListWidget::item:selected {color:'+colors(self)['ui_selected_text']+';}')
        self.resize_to_window()
        self.filename.setText(
            Path(self.mw.document.filepath).name
            if self.mw.document.filepath
            else "Untitled drawing"
        )
        self.select_category(max(0, self.categories.currentRow()))
        self.categories.setCurrentRow(max(0, self.categories.currentRow()))
        self.show()
        self.raise_()
        self.categories.setFocus()

    def resize_to_window(self):
        top = self.mw.menuBar().height()
        self.setGeometry(8, top+4, min(650, self.mw.width()-16), min(490, max(1, self.mw.height()-top-20)))

    def dismiss(self):
        self.hide()
        self.mw.focus_active_viewport()

    def select_category(self, index):
        category = CATEGORIES[max(0, index)]
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(9, 3, 9, 9)
        layout.setSpacing(6)
        title = QLabel(category)
        title.setStyleSheet("font-size:16px; font-weight:bold; padding-bottom:5px;")
        layout.addWidget(title)
        for i, (label, detail, callback) in enumerate(entries(self.mw)[category]):
            button = QPushButton(
                label + ("  ·  Unavailable" if callback is None else "")
            )
            button.setObjectName(
                "file_action_" + category.lower().replace(" ", "_") + "_" + str(i)
            )
            button.setProperty("fileAction", True)
            button.setEnabled(callback is not None)
            button.setToolTip(detail)
            button.setAccessibleName(label + ". " + detail)
            if callback:
                button.clicked.connect(
                    lambda checked=False, fn=callback: self.invoke(fn)
                )
            button.setProperty('fileDetail', detail)
            button.installEventFilter(self)
            layout.addWidget(button)
        layout.addStretch()
        old = self.scroll.takeWidget()
        if old:
            old.deleteLater()
        self.scroll.setWidget(content)

    def invoke(self, callback):
        self.dismiss()
        try:
            callback()
        except (OSError, ValueError) as error:
            QMessageBox.warning(self.mw, "File action", str(error))

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.dismiss()
            event.accept()
            return
        super().keyPressEvent(event)

    def eventFilter(self, obj, event):
        if not hasattr(self, 'mw'):
            return False
        if event.type() == QEvent.Type.Resize and obj is self.mw and self.isVisible():
            self.resize_to_window()
        if event.type() in (QEvent.Type.Enter, QEvent.Type.FocusIn) and obj.property('fileDetail'):
            self.detail.setText(obj.property('fileDetail'))
        return super().eventFilter(obj, event)


def commands(window):
    return {
        "AUDIT": lambda: audit(window),
        "RECOVER": lambda: recover(window),
        "PURGE": lambda: purge(window),
        "STATUS": lambda: status(window),
        "SAVETEMPLATE": lambda: save_template(window),
        "NEWTEMPLATE": lambda: from_template(window),
        "CLOSE": lambda:window.drawing_tabs.close_drawing(window.drawing_tabs.active),
        "FILE": window.show_file_workspace,
    }
