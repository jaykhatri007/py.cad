"""Ribbon commands that operate on selections, files or document settings."""

import csv
import io
import json
import re
import tempfile
import zipfile
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QPushButton,
    QDockWidget,
    QWidget,
    QInputDialog,
    QFileDialog,
    QMessageBox,
)

from . import appsettings, dxf_io
from .document import SetAttrCommand
from .drafting_extras import table_geometry, entity_metrics
from .native_io import document_to_dict, document_from_dict, atomic_write
from .ribbon_catalog import PANELS, TOOLS
from .table_commands import LayerStateCommand


def selected(mw):
    return [
        e for e in mw.canvas.selected_entities if e in mw.document.editable_entities()
    ]


def layer_visibility(mw, mode):
    doc = mw.document
    names = {e.layer for e in selected(mw)}
    if mode in ("isolate", "off") and not names:
        raise ValueError("Select objects on the target layers first.")
    import copy

    layers = copy.deepcopy(doc.layers.layers)
    current = doc.layers.current_layer
    if mode == "restore":
        previous = getattr(doc, "isolation_visibility", None)
        if not previous:
            raise ValueError("No layer isolation has been recorded in this drawing.")
        for name, (visible, frozen) in previous.items():
            if name in layers:
                layers[name].update(visible=visible, frozen=frozen)
        old_current = getattr(doc, "isolation_current", current)
        if old_current in layers:
            current = old_current
    else:
        if mode == "isolate":
            doc.isolation_current = current
            doc.isolation_visibility = {
                n: (p["visible"], p.get("frozen", False)) for n, p in layers.items()
            }
            current = current if current in names else sorted(names)[0]
        for name, props in layers.items():
            if mode == "isolate":
                props["visible"] = name in names
            elif mode == "off" and name in names:
                props["visible"] = False
            elif mode == "on":
                props["visible"] = True
    doc.undo_stack.push(
        LayerStateCommand(doc, layers, current, "Layer " + mode)
    )
    mw.layer_panel.refresh()


def show_properties(mw):
    mw.properties_panel.show()
    mw.properties_panel.raise_()
    mw.properties_panel.refresh()


def lineweight(mw):
    from .layers import LINEWEIGHTS

    names = {e.layer for e in selected(mw)} or {mw.document.layers.current_layer}
    weights = [f"{w:.2f}" for w in LINEWEIGHTS]
    value, ok = QInputDialog.getItem(
        mw,
        "Layer lineweight",
        "Lineweight in mm for layers "
        + ", ".join(sorted(names))
        + " (affects all objects on these layers):",
        weights,
        weights.index("0.25"),
        False,
    )
    if ok:
        value = float(value)
        mw.document.undo_stack.beginMacro("Layer lineweight")
        for name in names:
            mw.document.edit_layer("lineweight", name, value)
        mw.document.undo_stack.endMacro()


def table_defaults():
    try:
        values = json.loads(
            appsettings.get_settings().value("tables/defaults", "[30,8,2.5]")
        )
        table_geometry([["Check"]], *values)
        return values
    except (ValueError, TypeError):
        return [30, 8, 2.5]


def table_style(mw):
    current = table_defaults()
    text, ok = QInputDialog.getText(
        mw,
        "Table defaults",
        "Cell width, cell height, text height (drawing units; new static tables):",
        text=",".join(map(str, current)),
    )
    if ok:
        values = [float(v) for v in text.split(",")]
        if len(values) != 3 or any(not 0 < v < 1e6 for v in values):
            raise ValueError("Enter three positive finite sizes below 1,000,000.")
        table_geometry([["Check"]], *values)
        appsettings.get_settings().setValue("tables/defaults", json.dumps(values))


def place_table(mw, rows=None):
    if rows is None:
        text, ok = QInputDialog.getMultiLineText(
            mw,
            "Create static table",
            "One row per line; separate cells with TAB or a comma. Edit later with Block Editor.",
            "Item,Quantity\nPart A,1\nPart B,2",
        )
        if not ok:
            return
        rows = list(
            csv.reader(io.StringIO(text), delimiter="\t" if "\t" in text else ",")
        )
    geometry = table_geometry(
        rows, *table_defaults(), layer=mw.document.layers.current_layer
    )
    mw.pending_table_geometry = geometry
    mw.set_tool("TABLEPLACE")


def extract_rows(mw):
    entities = selected(mw) or mw.document.visible_entities()
    rows = [["Type", "Layer", "Color", "Length", "Radius", "Area"]]
    for e in entities:
        metrics = entity_metrics(e)
        rows.append(
            [
                e.kind,
                e.layer,
                e.color,
                *[
                    f"{metrics[k]:.6f}" if k in metrics else ""
                    for k in ("length", "radius", "area")
                ],
            ]
        )
    return rows


def data_extraction(mw):
    path, _ = QFileDialog.getSaveFileName(
        mw, "Extract entity data", "entities.csv", "CSV (*.csv)"
    )
    if path:
        if not path.lower().endswith(".csv"):
            path += ".csv"
        output = io.StringIO(newline="")
        # Prevent drawing text/layer names becoming executable spreadsheet formulas.
        rows = [
            [
                "'" + v
                if isinstance(v, str) and v.startswith(("=", "+", "-", "@"))
                else v
                for v in row
            ]
            for row in extract_rows(mw)
        ]
        csv.writer(output).writerows(rows)
        atomic_write(
            path, lambda p: Path(p).write_text(output.getvalue(), encoding="utf-8-sig")
        )
        mw.command_history.appendPlainText("Extracted data: " + path)


def selection_document(doc, items):
    if not items:
        raise ValueError("Select model-space objects first.")
    payload = document_to_dict(doc)
    ids = {e.id for e in items}
    payload["entities"] = [e for e in payload["entities"] if e["data"]["id"] in ids]
    needed = set()

    def include(entities):
        for e in entities:
            if e["kind"] == "INSERT":
                name = e["data"]["block_name"]
                if name not in needed:
                    needed.add(name)
                    include(payload["blocks"][name]["entities"])

    include(payload["entities"])
    payload["blocks"] = {n: b for n, b in payload["blocks"].items() if n in needed}
    for e in payload["entities"]:
        if 'source_hole_ids' in e['data']:
            e['data']['source_hole_ids']=[ref if ref in ids else None for ref in e['data']['source_hole_ids']]
        for key in ("source_line_id", "source_entity_id", "source_arc_id"):
            if key in e["data"] and e["data"][key] not in ids:
                e["data"][key] = None
                if e['kind'] == 'ORDINATE_DIMENSION':
                    e['data']['source_anchor'] = None
        if e['kind'] == 'CURVED_DIMENSION' and not set(e['data'].get('source_line_ids', [])) <= ids:
            e['data']['source_line_ids'] = []
            e['data']['line_directions'] = []
    from .feature_interop import selection_extensions
    payload["extensions"]=selection_extensions(doc,ids,needed)
    payload.update(layouts={},extrusions=[],source_archive=None,source_filepath=None)
    payload["constraints"] = [c for c in payload.get("constraints",[]) if all(r["entity"] in ids for r in c["refs"])]
    return document_from_dict(payload)


def write_block(mw):
    doc = selection_document(mw.document, selected(mw))
    path, filter_ = QFileDialog.getSaveFileName(
        mw,
        "Write selected geometry",
        "selection.pycad",
        "PY.cad project (*.pycad);;DXF (*.dxf)",
    )
    if path:
        if not Path(path).suffix:
            path += ".dxf" if "DXF" in filter_ else ".pycad"
        if path.lower().endswith(".dxf"):
            warnings = dxf_io.export_warnings(doc)
            if (
                warnings
                and QMessageBox.warning(
                    mw,
                    "DXF export",
                    "\n".join(warnings),
                    QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Cancel,
                    QMessageBox.StandardButton.Cancel,
                )
                != QMessageBox.StandardButton.Save
            ):
                return
        dxf_io.export_any(doc, path)
        mw.command_history.appendPlainText("Wrote selection: " + path)


def xrefs(mw):
    from .xref import reference_path

    dialog = QDialog(mw)
    dialog.setWindowTitle("External References — DXF")
    dialog.setObjectName("xref_manager")
    dialog.resize(750, 330)
    layout = QVBoxLayout(dialog)
    table = QTableWidget(0, 3)
    table.setHorizontalHeaderLabels(["Reference", "Source", "Status"])
    table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    for name, block in mw.document.blocks.items():
        if not block.is_xref:
            continue
        row = table.rowCount()
        table.insertRow(row)
        try:
            status = "Available" if reference_path(mw.document, block.source_filepath).is_file() else "Missing — cached geometry retained"
        except ValueError:
            status = "Windows path — Relink selected"
        for col, text in enumerate(
            (
                name,
                block.source_filepath,
                status,
            )
        ):
            table.setItem(row, col, QTableWidgetItem(text))
    layout.addWidget(table)
    label = QLabel(
        "DXF references are cached. Relink moved Windows files to their Ubuntu location. Saved drawings store relinked paths relative to the drawing; preserve the folder structure when moving it."
    )
    label.setWordWrap(True)
    layout.addWidget(label)
    reload = QPushButton("Reload selected")

    def run(source=None):
        row = table.currentRow()
        if row < 0:
            return
        name = table.item(row, 0).text()
        try:
            warnings = mw.document.reload_xref(name, source=source)
            table.item(row, 1).setText(mw.document.blocks[name].source_filepath)
            table.item(row, 2).setText(
                "Reloaded" + (": " + "; ".join(warnings) if warnings else "")
            )
            mw.refresh_document_ui()
        except Exception as ex:
            table.item(row, 2).setText(str(ex))

    reload.clicked.connect(lambda: run())
    layout.addWidget(reload)
    relink = QPushButton("Relink selected…")
    relink.setObjectName("xref_relink")
    def choose_source():
        if table.currentRow() < 0:
            return
        path, _ = QFileDialog.getOpenFileName(dialog, "Locate reference DXF", appsettings.get_last_directory(), "DXF drawings (*.dxf *.DXF)")
        if path:
            run(source=path)
    relink.clicked.connect(choose_source)
    layout.addWidget(relink)
    dialog.exec()
    dialog.setParent(None)
    dialog.deleteLater()


def load_aliases():
    try:
        result = json.loads(appsettings.get_settings().value("commands/aliases", "{}"))
        if not isinstance(result, dict):
            return {}
        return {
            k: v
            for k, v in result.items()
            if isinstance(k, str)
            and isinstance(v, str)
            and re.fullmatch(r"[A-Z][A-Z0-9_]{0,19}", k)
            and re.fullmatch(r"[A-Z][A-Z0-9_]{0,39}", v)
        }
    except (ValueError, TypeError):
        return {}


def edit_aliases(mw):
    aliases = getattr(mw, "user_aliases", {})
    text, ok = QInputDialog.getMultiLineText(
        mw,
        "Edit command aliases",
        "One ALIAS=COMMAND per line. Existing command names are reserved. Built-in aliases remain unless overridden here.",
        "\n".join(k + "=" + v for k, v in sorted(aliases.items())),
    )
    if not ok:
        return
    result = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        parts = line.strip().upper().split("=")
        if len(parts) != 2:
            raise ValueError("Use ALIAS=COMMAND on each line.")
        alias, command = [v.strip() for v in parts]
        if (
            not re.fullmatch(r"[A-Z][A-Z0-9_]{0,19}", alias)
            or alias in mw.canonical_commands
            or alias in result
        ):
            raise ValueError("Invalid, duplicate or reserved alias: " + alias)
        if command not in mw.canonical_commands:
            raise ValueError("Choose an available command: " + command)
        result[alias] = command
    mw.user_aliases = result
    appsettings.get_settings().setValue("commands/aliases", json.dumps(result))
    mw.command_names = sorted(mw.canonical_commands | set(result))


def tool_palette(mw, measurements=False):
    dock = getattr(mw, "tool_palette_dock", None)
    if dock is None:
        dock = QDockWidget("Tool palette / coverage", mw)
        dock.setObjectName("tool_palette_dock")
        box = QWidget()
        layout = QVBoxLayout(box)
        search = QLineEdit()
        search.setPlaceholderText("Search tools, commands, tabs or support status…")
        layout.addWidget(search)
        table = QTableWidget(0, 4)
        table.setHorizontalHeaderLabels(
            ["Tool / Command", "Location", "Status", "Scope"]
        )
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        seen = set()
        for tab, panel, _, items in PANELS:
            for item in items:
                if item.command in seen:
                    continue
                seen.add(item.command)
                row = table.rowCount()
                table.insertRow(row)
                for col, text in enumerate(
                    (
                        item.label + " / " + item.command,
                        tab + " / " + panel,
                        item.status,
                        item.detail or "Available in PY.cad",
                    )
                ):
                    cell = QTableWidgetItem(text)
                    cell.setToolTip(text)
                    table.setItem(row, col, cell)
                table.item(row, 0).setData(Qt.ItemDataRole.UserRole, item.command)
        layout.addWidget(table)
        detail = QLabel(
            "Double-click an available tool to start it. Planned tools are listed for reference."
        )
        detail.setWordWrap(True)
        layout.addWidget(detail)

        def select_row():
            row = table.currentRow()
            if row >= 0:
                detail.setText(table.item(row, 3).text())

        table.itemSelectionChanged.connect(select_row)

        def activate(row, col):
            command = table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            if TOOLS[command].status != "planned":
                mw.run_ribbon_command(command)

        table.cellDoubleClicked.connect(activate)

        def filter_rows(text):
            for row in range(table.rowCount()):
                table.setRowHidden(
                    row,
                    text.lower()
                    not in " ".join(
                        table.item(row, c).text() for c in range(4)
                    ).lower(),
                )

        search.textChanged.connect(filter_rows)
        dock.setWidget(box)
        mw.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)
        mw.tool_palette_dock = dock
        dock.search = search
    dock.search.setText("Home / Utilities" if measurements else "")
    dock.show()
    dock.raise_()


def pan(mw):
    if (
        mw.model_workspace is not None
        and mw.viewport_stack.currentWidget() is mw.model_workspace
    ):
        mw.model_workspace.active.set_navigation_mode("pan")
    else:
        mw._draft_navigation_mode("pan")


def realtime_zoom(mw):
    mw.show_drafting()
    mw.cancel_command()
    mw.canvas.navigation_zoom = True
    mw.canvas.setCursor(Qt.CursorShape.SizeVerCursor)
    mw.command_history.appendPlainText(
        "ZOOM REALTIME: Hold the left button and drag up/down. Esc ends."
    )


def visual_style(mw, style):
    if style == "Wireframe":
        mw.show_drafting()
    else:
        four = bool(
            mw.model_workspace and mw.model_workspace.layout_mode.currentIndex() == 0
        )
        mw.open_model_workspace(four=four)
        mw.model_workspace.visual.setCurrentText(style)


def command_line(mw):
    dock = mw.findChild(QDockWidget, "command_line_dock")
    dock.setVisible(not dock.isVisible())


def page_setup(mw):
    layout = mw.document.layouts.get(mw.document.current_space)
    if layout is None:
        raise ValueError(
            "Switch to a paper layout first, or create one with NEWLAYOUT."
        )
    value, ok = QInputDialog.getText(
        mw,
        "Page setup",
        "Width,height in millimetres (existing viewport positions stay unchanged):",
        text=f"{layout.page_width},{layout.page_height}",
    )
    if not ok:
        return
    values = [float(v) for v in value.split(",")]
    if len(values) != 2 or any(not 10 <= v <= 5000 for v in values):
        raise ValueError("Enter width,height, each from 10 to 5000 mm.")
    mw.document.undo_stack.beginMacro("Page setup")
    for attr, new in zip(("page_width", "page_height"), values):
        mw.document.undo_stack.push(
            SetAttrCommand(
                mw.document, layout, attr, getattr(layout, attr), new, "Page setup"
            )
        )
    mw.document.undo_stack.endMacro()
    mw.canvas.zoom_extents()


def plot_preview(mw):
    from PyQt6.QtPdf import QPdfDocument
    from PyQt6.QtPdfWidgets import QPdfView
    from .plotting import export_pdf

    with tempfile.TemporaryDirectory(prefix="pycad-preview-") as temp:
        path = str(Path(temp) / "preview.pdf")
        export_pdf(mw.document, path, mw.document.current_space)
        dialog = QDialog(mw)
        dialog.setWindowTitle("Plot preview — " + mw.document.current_space)
        dialog.resize(850, 650)
        layout = QVBoxLayout(dialog)
        view = QPdfView(dialog)
        pdf = QPdfDocument(dialog)
        pdf.load(path)
        view.setDocument(pdf)
        view.setZoomMode(QPdfView.ZoomMode.FitInView)
        layout.addWidget(view)
        dialog.exec()
        pdf.close()


def batch_plot(mw):
    from .plotting import export_pdf

    path, _ = QFileDialog.getSaveFileName(
        mw, "Batch PDF plot — all paper layouts", "plots.zip", "ZIP archive (*.zip)"
    )
    if not path:
        return
    if not path.lower().endswith(".zip"):
        path += ".zip"
    spaces = list(mw.document.layouts) or ["Model"]
    with tempfile.TemporaryDirectory(prefix="pycad-plots-") as temp:
        files = []
        for i, space in enumerate(spaces, 1):
            filename = f"{i:02d}_" + re.sub(r"[^A-Za-z0-9_.-]", "_", space) + ".pdf"
            file = Path(temp) / filename
            export_pdf(mw.document, str(file), space)
            files.append(file)

        def write(output):
            with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
                for file in files:
                    archive.write(file, file.name)

        atomic_write(path, write)
    mw.command_history.appendPlainText(f"Exported {len(spaces)} PDF sheets: {path}")


def transmittal(doc, path):
    from .xref import reference_path
    payload = document_to_dict(doc)
    refs = []
    for name, block in payload["blocks"].items():
        if not block["source_filepath"]:
            continue
        source = reference_path(doc, block["source_filepath"])
        if not source.is_file():
            raise ValueError("Missing reference: " + str(source))
        member = f"references/{len(refs) + 1:03d}_" + re.sub(
            r"[^A-Za-z0-9_.-]", "_", source.name
        )
        block["source_filepath"] = member
        refs.append((name, source, member))
    manifest = {
        "format": "PyCAD transmittal",
        "drawing": "drawing.pycad",
        "references": [{"block": n, "file": m} for n, s, m in refs],
        "note": "Direct DXF references only. Cached nested block geometry is included in the drawing; nested external file dependencies are not collected.",
    }

    def write(output):
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                "drawing.pycad",
                json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False),
            )
            archive.writestr("manifest.json", json.dumps(manifest, indent=2))
            for _, source, member in refs:
                archive.write(source, member)

    atomic_write(path, write)


def etransmit(mw):
    path, _ = QFileDialog.getSaveFileName(
        mw,
        "Create local transmittal package",
        "drawing-transmittal.zip",
        "ZIP archive (*.zip)",
    )
    if path:
        if not path.lower().endswith(".zip"):
            path += ".zip"
        transmittal(mw.document, path)
        mw.command_history.appendPlainText("Local transmittal created: " + path)


def export_dxf(mw):
    path, _ = QFileDialog.getSaveFileName(
        mw, "Export 2D DXF", "drawing.dxf", "DXF (*.dxf)"
    )
    if path:
        mw._save_to_path(path if path.lower().endswith(".dxf") else path + ".dxf")


def commands(mw):
    from .object_commands import commands as object_commands
    return {
        **object_commands(mw),
        "LAYISO": lambda: layer_visibility(mw, "isolate"),
        "LAYOFF": lambda: layer_visibility(mw, "off"),
        "LAYON": lambda: layer_visibility(mw, "on"),
        "LAYUNISO": lambda: layer_visibility(mw, "restore"),
        "BEDIT": mw.edit_block_dialog,
        "COLOR": mw.properties_panel.choose_color,
        "LINETYPE": lambda: __import__('pycad.linetype_ui',fromlist=['show']).show(mw),
        "LWEIGHT": lambda: lineweight(mw),
        "PROPERTIES": lambda: show_properties(mw),
        "TABLE": lambda: place_table(mw),
        "TABLESTYLE": lambda: table_style(mw),
        "WBLOCK": lambda: write_block(mw),
        "XREF": lambda: xrefs(mw),
        "DXFATTACH": mw.attach_xref,
        "DATAEXTRACTION": lambda: data_extraction(mw),
        "DATATABLE": lambda: place_table(mw, extract_rows(mw)),
        "ALIASEDIT": lambda: edit_aliases(mw),
        "TOOLCOVERAGE": lambda: tool_palette(mw),
        "TOOLPALETTES": lambda: tool_palette(mw),
        "MEASUREGEOM": lambda: tool_palette(mw, True),
        "PAN": lambda: pan(mw),
        "ZOOMEXTENTS": mw.fit_active,
        "ZOOMREALTIME": lambda: realtime_zoom(mw),
        "NAVWHEEL": lambda: (
            mw.draft_navigation.show()
            if mw.viewport_stack.currentWidget() is mw.canvas
            else mw.model_workspace.active.navigation.show()
        ),
        "NEWLAYOUT": mw.new_layout_dialog,
        "2DWIREFRAME": lambda: visual_style(mw, "Wireframe"),
        "SHADED": lambda: visual_style(mw, "Shaded with edges"),
        "XRAY": lambda: visual_style(mw, "X-Ray"),
        "COMMANDLINE": lambda: command_line(mw),
        "PLOT": mw.print_to_pdf,
        "EXPORTPDF": mw.print_to_pdf,
        "PLOTPREVIEW": lambda: plot_preview(mw),
        "PAGESETUP": lambda: page_setup(mw),
        "BATCHPLOT": lambda: batch_plot(mw),
        "EXPORTDXF": lambda: export_dxf(mw),
        "EXPORTSTL": mw.extrude_selected,
        "ETRANSMIT": lambda: etransmit(mw),
    }
