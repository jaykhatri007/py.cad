"""Persistent entity properties and native drawing standards workflows."""
from .linetypes import NAMES as LINETYPE_NAMES


import copy
import json
import math
from pathlib import Path
from urllib.parse import urlparse

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QDesktopServices, QUndoCommand
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QDialogButtonBox,
    QInputDialog,
    QFileDialog,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
)
from .document import SetAttrCommand
from .native_io import atomic_write
from .layers import LINEWEIGHTS


def editable_selection(mw):
    items = [
        e for e in mw.canvas.selected_entities if e in mw.document.editable_entities()
    ]
    if not items:
        raise ValueError("Select editable objects before starting this command")
    return items


def set_property(mw, items, attribute, value, label):
    mw.document.undo_stack.beginMacro(label)
    for e in items:
        mw.document.undo_stack.push(
            SetAttrCommand(
                mw.document, e, attribute, getattr(e, attribute), value, label
            )
        )
    mw.document.undo_stack.endMacro()
    mw.refresh_document_ui()


def transparency(mw):
    items = editable_selection(mw)
    value, ok = QInputDialog.getDouble(
        mw,
        "Object transparency",
        "Transparency percent (0 = opaque, 90 = mostly transparent):",
        items[0].transparency,
        0,
        90,
        1,
    )
    if ok:
        set_property(mw, items, "transparency", value, "Object transparency")


def valid_link(value):
    if not value:
        return True
    try:
        parsed = urlparse(value)
    except ValueError:
        return False
    return (
        len(value) <= 2048
        and parsed.scheme in ("http", "https")
        and bool(parsed.netloc)
        and not any(ord(c) < 32 for c in value)
    )


def hyperlink(mw):
    items = editable_selection(mw)
    dialog = QDialog(mw)
    dialog.setWindowTitle("Entity hyperlink")
    dialog.resize(560, 160)
    layout = QVBoxLayout(dialog)
    layout.addWidget(
        QLabel(
            f"Web URL for {len(items)} selected object(s). Clear the field to remove it."
        )
    )
    field = QLineEdit(items[0].hyperlink)
    field.setPlaceholderText("https://…")
    layout.addWidget(field)
    open_button = QPushButton("Open URL in browser")
    layout.addWidget(open_button)

    def update():
        open_button.setEnabled(bool(field.text()) and valid_link(field.text()))

    field.textChanged.connect(update)
    update()
    open_button.clicked.connect(
        lambda: (
            QDesktopServices.openUrl(QUrl(field.text()))
            if valid_link(field.text())
            else None
        )
    )
    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
    )

    def save():
        if not valid_link(field.text()):
            QMessageBox.warning(
                dialog, "Hyperlink", "Enter a valid HTTP or HTTPS web URL."
            )
            return
        dialog.accept()

    buttons.accepted.connect(save)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    if dialog.exec():
        set_property(mw, items, "hyperlink", field.text(), "Entity hyperlink")


class TranslateLayerCommand(QUndoCommand):
    def __init__(self, doc, source, target):
        super().__init__("Translate layer")
        if (
            source == target
            or source not in doc.layers.layers
            or target not in doc.layers.layers
        ):
            raise ValueError("Choose distinct existing source and target layers")
        self.doc = doc
        self.source = source
        self.target = target
        self.before = copy.deepcopy(doc.layers.layers)
        self.after = copy.deepcopy(self.before)
        if source != "0":
            del self.after[source]
        self.current = doc.layers.current_layer
        self.entities = [e for e in doc.entities if e.layer == source] + [
            e for b in doc.blocks.values() for e in b.entities if e.layer == source
        ]
        self.features=[e for e in doc.extrusions if e['layer']==source]
        self.attribute_specs=[spec for block in doc.blocks.values() for spec in block.attributes if spec['layer']==source]
        self.before_extensions=copy.deepcopy(doc.extensions)
        self.after_extensions=copy.deepcopy(doc.extensions)
        for solid in self.after_extensions.get('solids',{}).values():
            if solid['layer']==source: solid['layer']=target
        for overrides in self.after_extensions.get('viewport_overrides',{}).values():
            if source in overrides: overrides[target]=overrides.pop(source)
        for state in self.after_extensions.get('layer_states',{}).values():
            if source in state['layers']: state['layers'][target]=state['layers'].pop(source)
            if state['current']==source: state['current']=target

    def _apply(self, forward):
        self.doc.layers.layers = copy.deepcopy(self.after if forward else self.before)
        self.doc.layers.current_layer = (
            self.target if forward and self.current == self.source else self.current
        )
        for e in self.entities:
            e.layer = self.target if forward else self.source
        for e in self.features: e['layer']=self.target if forward else self.source
        for spec in self.attribute_specs: spec['layer']=self.target if forward else self.source
        self.doc.extensions=copy.deepcopy(self.after_extensions if forward else self.before_extensions)

    def redo(self):
        self._apply(True)

    def undo(self):
        self._apply(False)


def layer_translate(mw):
    names = list(mw.document.layers.names())
    if len(names) < 2:
        raise ValueError("Create a target layer before translating")
    source, ok = QInputDialog.getItem(
        mw,
        "Layer translator",
        "Source layer (objects will adopt target layer properties):",
        names,
        0,
        False,
    )
    if not ok:
        return
    targets = [n for n in names if n != source]
    target, ok = QInputDialog.getItem(
        mw, "Layer translator", "Target layer:", targets, 0, False
    )
    if ok:
        mw.document.undo_stack.push(TranslateLayerCommand(mw.document, source, target))
        mw.layer_panel.refresh()
        mw.refresh_document_ui()


def capture_standard(doc):
    return {
        "format": "PyCAD-Standards-1",
        "units": doc.units,
        "layers": {
            n: {k: p[k] for k in ("color", "linetype", "lineweight")}
            for n, p in doc.layers.layers.items()
        },
    }


def validate_standard(standard):
    from .validation import name, color

    if standard is None:
        return
    if (
        not isinstance(standard, dict)
        or set(standard) != {"format", "units", "layers"}
        or standard["format"] != "PyCAD-Standards-1"
    ):
        raise ValueError(
            "Expected a PyCAD-Standards-1 JSON profile; DWS files are not supported"
        )
    if standard["units"] not in ("mm", "cm", "m", "in", "ft", "unitless"):
        raise ValueError("Invalid standard units")
    layers = standard["layers"]
    if (
        not isinstance(layers, dict)
        or not 1 <= len(layers) <= 10000
        or "0" not in layers
    ):
        raise ValueError("Invalid standards layers")
    if len({n.casefold() for n in layers}) != len(layers):
        raise ValueError("Duplicate standard layer names")
    for n, p in layers.items():
        name(n, "Standard layer")
        if not isinstance(p, dict) or set(p) != {"color", "linetype", "lineweight"}:
            raise ValueError("Invalid layer standard fields")
        color(p["color"], False)
        if p["linetype"] not in LINETYPE_NAMES:
            raise ValueError("Unsupported standard linetype")
        if (
            type(p["lineweight"]) not in (int, float)
            or not math.isfinite(p["lineweight"])
            or p["lineweight"] not in LINEWEIGHTS
        ):
            raise ValueError("Invalid standard lineweight")


def check_standard(doc):
    standard = doc.cad_standard
    if standard is None:
        raise ValueError(
            "Configure or load a native standards profile with STANDARDS first"
        )
    validate_standard(standard)
    issues = []
    if doc.units != standard["units"]:
        issues.append(("Drawing units", "Drawing", doc.units, standard["units"]))
    for n, p in doc.layers.layers.items():
        if n not in standard["layers"]:
            issues.append(("Extra layer", n, "Present", "Not in standard"))
            continue
        for key, expected in standard["layers"][n].items():
            if p.get(key) != expected:
                issues.append((key, n, str(p.get(key)), str(expected)))
    for n in standard["layers"]:
        if n not in doc.layers.layers:
            issues.append(("Missing layer", n, "Absent", "Required"))
    return issues


def standards_report(mw):
    issues = check_standard(mw.document)
    dialog = QDialog(mw)
    dialog.setWindowTitle("Drawing standards check — native profile")
    dialog.resize(700, 410)
    layout = QVBoxLayout(dialog)
    note = QLabel(
        f"{len(issues)} issue(s). Checks units, layer names, colors, linetypes and lineweights. No DWS compatibility."
    )
    note.setWordWrap(True)
    layout.addWidget(note)
    table = QTableWidget(len(issues), 4)
    table.setHorizontalHeaderLabels(["Check", "Object", "Actual", "Expected"])
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    for r, values in enumerate(issues):
        for c, text in enumerate(values):
            table.setItem(r, c, QTableWidgetItem(text))
    layout.addWidget(table)
    close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    close.rejected.connect(dialog.reject)
    layout.addWidget(close)
    dialog.exec()


def standards_manager(mw):
    dialog = QDialog(mw)
    dialog.setWindowTitle("Configure drawing standards — PY.cad JSON")
    dialog.resize(570, 230)
    layout = QVBoxLayout(dialog)
    label = QLabel(
        "Native standards profiles are saved with the drawing. Autodesk DWS profiles are not supported."
    )
    label.setWordWrap(True)
    layout.addWidget(label)
    state = QLabel()
    layout.addWidget(state)

    def status():
        state.setText(
            "No profile configured"
            if mw.document.cad_standard is None
            else f"Active profile: {len(mw.document.cad_standard['layers'])} layers; units {mw.document.cad_standard['units']}"
        )

    def assign(value):
        validate_standard(value)
        mw.document.undo_stack.push(
            SetAttrCommand(
                mw.document,
                mw.document,
                "cad_standard",
                mw.document.cad_standard,
                value,
                "Drawing standards",
            )
        )
        status()

    capture = QPushButton("Capture current units and layers")
    capture.clicked.connect(lambda: assign(capture_standard(mw.document)))
    layout.addWidget(capture)
    row = QHBoxLayout()
    load = QPushButton("Load JSON…")
    save = QPushButton("Save JSON…")
    check = QPushButton("Check drawing")
    row.addWidget(load)
    row.addWidget(save)
    row.addWidget(check)
    layout.addLayout(row)

    def load_profile():
        path, _ = QFileDialog.getOpenFileName(
            dialog, "Load native standards", "", "PY.cad standards (*.json)"
        )
        if not path:
            return
        try:
            if Path(path).stat().st_size > 2 * 1024 * 1024:
                raise ValueError("Standards profile exceeds 2 MiB")
            assign(json.loads(Path(path).read_text(encoding="utf-8")))
        except (ValueError, OSError) as ex:
            QMessageBox.warning(dialog, "Standards", str(ex))

    def save_profile():
        if mw.document.cad_standard is None:
            state.setText("Capture or load a profile first")
            return
        path, _ = QFileDialog.getSaveFileName(
            dialog, "Save native standards", "drawing-standards.json", "JSON (*.json)"
        )
        if path:
            if not path.lower().endswith(".json"):
                path += ".json"
            try:
                atomic_write(
                    path,
                    lambda p: Path(p).write_text(
                        json.dumps(mw.document.cad_standard, indent=2), encoding="utf-8"
                    ),
                )
            except OSError as ex:
                QMessageBox.warning(dialog, "Standards", str(ex))

    def check_profile():
        try:
            standards_report(mw)
        except ValueError as ex:
            state.setText(str(ex))

    load.clicked.connect(load_profile)
    save.clicked.connect(save_profile)
    check.clicked.connect(check_profile)
    close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    close.rejected.connect(dialog.reject)
    layout.addWidget(close)
    status()
    dialog.exec()


def commands(mw):
    return {
        "TRANSPARENCY": lambda: transparency(mw),
        "HYPERLINK": lambda: hyperlink(mw),
        "LAYTRANS": lambda: layer_translate(mw),
        "CHECKSTANDARDS": lambda: standards_report(mw),
        "CONFIGURESTANDARDS": lambda: standards_manager(mw),
        "STANDARDS": lambda: standards_manager(mw),
    }
