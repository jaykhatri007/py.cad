"""Validated native clipboard, point-driven paste and text find/replace."""

import copy
import json
import re
import uuid
from PyQt6.QtCore import QMimeData, QPointF
from PyQt6.QtGui import QUndoCommand
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QCheckBox,
    QPushButton,
    QLabel,
    QMessageBox,
)
from .tools import Tool
from .geometry import Point
from .document import SetAttrCommand, DeleteEntitiesCommand
from .native_io import document_to_dict, document_from_dict
from .ribbon_actions import selection_document
from .appearance import set_menubar

MIME = "application/x-pycad-selection+json"
MAX_BYTES = 32 * 1024 * 1024


def copy_clip(mw, cut=False, base=None):
    items = [
        e for e in mw.canvas.selected_entities if e in mw.document.editable_entities()
    ]
    selected = selection_document(mw.document, items)
    selected.underlays = []
    boxes = [e.bbox() for e in selected.entities]
    base = base or Point(min(b[0] for b in boxes), min(b[1] for b in boxes))
    value = dict(
        format="PyCAD clipboard",
        base=[base.x, base.y],
        drawing=document_to_dict(selected),
    )
    raw = json.dumps(value, ensure_ascii=False, allow_nan=False).encode()
    if len(raw) > MAX_BYTES:
        raise ValueError("Clipboard selection exceeds 32 MiB")
    mime = QMimeData()
    mime.setData(MIME, raw)
    mime.setText(f"PY.cad selection: {len(items)} objects")
    QApplication.clipboard().setMimeData(mime)
    if cut:
        mw.document.undo_stack.push(
            DeleteEntitiesCommand(mw.document, items, "Cut to clipboard")
        )
        mw.canvas.selected_entities = []


def unique(name, table):
    name = name[:100]
    result = name
    i = 1
    while result.casefold() in {n.casefold() for n in table}:
        result = f"{name}_{i}"
        i += 1
    return result


def prepare_paste(doc, raw, point):
    if len(raw) > MAX_BYTES:
        raise ValueError("Clipboard selection exceeds 32 MiB")
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeError) as ex:
        raise ValueError("Invalid PyCAD clipboard") from ex
    if (
        not isinstance(data, dict)
        or set(data) != {"format", "base", "drawing"}
        or data["format"] != "PyCAD clipboard"
    ):
        raise ValueError("Invalid PyCAD clipboard")
    from .validation import finite

    if not isinstance(data["base"], list) or len(data["base"]) != 2:
        raise ValueError("Invalid clipboard base")
    for value in [*data["base"], point.x, point.y]:
        finite(value, "Paste coordinate")
    imported = document_from_dict(data["drawing"])
    if imported.extrusions or imported.underlays or imported.layouts:
        raise ValueError("Clipboard supports selected 2D entities")
    factor = 1.0
    if imported.units != doc.units:
        from .unit_conversion import _scale_document
        from .units import UNIT_MM

        if "unitless" in (imported.units, doc.units):
            raise ValueError(
                "Assign drawing units before pasting across unitless/unitful drawings"
            )
        factor = UNIT_MM[imported.units] / UNIT_MM[doc.units]
        _scale_document(imported, doc.units, doc.unit_settings)
    payload = document_to_dict(imported)
    office_styles=payload.get("extensions",{}).get("office_linetypes",{})
    if office_styles:
        available=dict(doc.extensions.get("office_linetypes",{}))
        remapped={}
        for name,recipe in list(office_styles.items()):
            target=name
            if name in available and available[name]!=recipe:
                count=2
                while True:
                    suffix=f"_{count}"
                    target=name[:48-len(suffix)]+suffix
                    if target not in available and target not in office_styles:
                        break
                    count+=1
            remapped[name]=target
            available[target]={**recipe,"name":target}
        payload["extensions"]["office_linetypes"]={t:available[t] for t in remapped.values()}
        for layer in payload["layers"].values():
            if layer.get("linetype") in remapped:layer["linetype"]=remapped[layer["linetype"]]
        for record in payload["entities"]+[e for b in payload["blocks"].values() for e in b["entities"]]:
            data_record=record["data"]
            if data_record.get("linetype") in remapped:data_record["linetype"]=remapped[data_record["linetype"]]

    tables = {
        "layers": copy.deepcopy(doc.layers.layers),
        "dimstyles": copy.deepcopy(doc.dimstyles),
        "mleaderstyles": copy.deepcopy(doc.mleaderstyles),
        "textstyles": copy.deepcopy(doc.textstyles),
    }
    maps = {}
    for key in tables:
        maps[key] = {}
        for name, value in payload[key].items():
            if name in tables[key] and value == tables[key][name]:
                target = name
            else:
                target = unique(name, tables[key])
                tables[key][target] = copy.deepcopy(value)
            maps[key][name] = target
    block_names = dict(doc.blocks)
    for name in payload["blocks"]:
        target = unique(name, block_names)
        block_names[target] = None
        maps.setdefault("blocks", {})[name] = target
    all_records = payload["entities"] + [
        e for b in payload["blocks"].values() for e in b["entities"]
    ]
    ids = {r["data"]["id"]: uuid.uuid4().hex for r in all_records}
    for record in all_records:
        e = record["data"]
        e["id"] = ids[e["id"]]
        e["layer"] = maps["layers"][e["layer"]]
        kind = record["kind"]
        if kind == "INSERT":
            e["block_name"] = maps["blocks"][e["block_name"]]
        if "style_name" in e:
            table = (
                "mleaderstyles"
                if kind == "MLEADER"
                else "textstyles"
                if kind == "TEXT"
                else "dimstyles"
            )
            e["style_name"] = maps[table][e["style_name"]]
        for key in ("source_line_id", "source_arc_id", "source_entity_id"):
            if key in e and e[key] is not None:
                e[key] = ids.get(e[key])
        if 'source_hole_ids' in e:
            e['source_hole_ids']=[ids.get(ref) for ref in e['source_hole_ids']]
        if "source_line_ids" in e:
            e["source_line_ids"] = [ids[v] for v in e["source_line_ids"] if v in ids]
    for c in payload["constraints"]:
        c["id"] = uuid.uuid4().hex
        for ref in c["refs"]:
            ref["entity"] = ids[ref["entity"]]
        if c["kind"] == "fixed":
            dx, dy = (
                point.x - data["base"][0] * factor,
                point.y - data["base"][1] * factor,
            )
            n = 4 if len(c["fixed"]) == 4 else 2
            c["fixed"][:n] = [
                v + (dx if i % 2 == 0 else dy) for i, v in enumerate(c["fixed"][:n])
            ]
    from .feature_interop import remap_extensions
    payload["extensions"]=remap_extensions(payload.get("extensions",{}),ids,maps.get("blocks",{}))
    for block in payload["blocks"].values():
        for spec in block.get("attributes",[]):
            spec["layer"]=maps["layers"][spec["layer"]];spec["style_name"]=maps["textstyles"][spec["style_name"]]
    payload["blocks"] = {
        maps["blocks"][name]: {**b, "source_filepath": None}
        for name, b in payload["blocks"].items()
    }
    payload.update(tables)
    destination_styles=doc.extensions.get("office_linetypes",{})
    if destination_styles:
        payload["extensions"]["office_linetypes"]={**destination_styles,**payload["extensions"].get("office_linetypes",{})}
        payload["schema_version"]=18

    payload["current_layer"] = maps["layers"][payload["current_layer"]]
    for key in ("dimstyle", "mleaderstyle", "textstyle"):
        payload["current_" + key] = maps[key + "s"][payload["current_" + key]]
    # Move raw stored model entities, then restore links. Native preflight checks the combined model.
    constraints = payload["constraints"]
    payload["constraints"] = []
    imported = document_from_dict(payload)
    dx, dy = point.x - data["base"][0] * factor, point.y - data["base"][1] * factor
    for e in imported.entities:
        e.translate(dx, dy)
    imported.constraints = constraints
    imported.sync_associative()
    candidate = document_to_dict(doc)
    candidate.update(tables)
    candidate["blocks"].update(
        {name: b for name, b in document_to_dict(imported)["blocks"].items()}
    )
    candidate["entities"] += [r for r in document_to_dict(imported)["entities"]]
    candidate["constraints"] += constraints
    from .feature_interop import merge_extensions
    from .building import levels
    candidate["extensions"]=merge_extensions(doc.extensions,imported.extensions,levels(doc))
    candidate["schema_version"]=max(candidate["schema_version"],payload["schema_version"])
    document_from_dict(candidate)
    return imported, tables


class PasteCommand(QUndoCommand):
    def __init__(self, doc, imported, tables):
        super().__init__("Paste objects")
        self.doc, self.items = doc, list(imported.entities)
        self.before = dict(
            layers=copy.deepcopy(doc.layers.layers),
            blocks=dict(doc.blocks),
            dimstyles=copy.deepcopy(doc.dimstyles),
            mleaderstyles=copy.deepcopy(doc.mleaderstyles),
            textstyles=copy.deepcopy(doc.textstyles),
            constraints=copy.deepcopy(doc.constraints),
            extensions=copy.deepcopy(doc.extensions),
        )
        self.after = {
            **tables,
            "blocks": {**doc.blocks, **imported.blocks},
            "constraints": copy.deepcopy(doc.constraints + imported.constraints),
            "extensions": __import__("pycad.feature_interop",fromlist=["merge_extensions"]).merge_extensions(doc.extensions,imported.extensions,__import__("pycad.building",fromlist=["levels"]).levels(doc)),
        }

    def apply(self, state):
        self.doc.layers.layers = copy.deepcopy(state["layers"])
        self.doc.blocks = dict(state["blocks"])
        for k in ("dimstyles", "mleaderstyles", "textstyles", "constraints", "extensions"):
            setattr(self.doc, k, copy.deepcopy(state[k]))

    def redo(self):
        self.apply(self.after)
        self.doc.entities.extend(self.items)

    def undo(self):
        self.doc.entities[:] = [e for e in self.doc.entities if e not in self.items]
        self.apply(self.before)


class PasteTool(Tool):
    name = "PASTECLIP"
    prompt = "PASTECLIP: Pick insertion point (native PyCAD clipboard)"

    def __init__(self, mw):
        super().__init__(mw)
        mime = QApplication.clipboard().mimeData()
        if not mime or not mime.hasFormat(MIME):
            raise ValueError("Clipboard has no native PY.cad selection")
        self.raw = bytes(mime.data(MIME))

    def on_click(self, x, y, snap_kind, button):
        if button != 1:
            return
        imported, tables = prepare_paste(self.document, self.raw, Point(x, y))
        command = PasteCommand(self.document, imported, tables)
        self.document.undo_stack.push(command)
        self.mw.canvas.selected_entities = command.items
        self.finish()

    def on_text_input(self, text):
        p = self.parse_point(text)
        if p is None:
            raise ValueError("Enter x,y")
        self.on_click(p.x, p.y, "", 1)


class MenuBarTool(Tool):
    name = "MENUBAR"
    prompt = "MENUBAR: Enter 1 to show classic menus or 0 to hide"

    def on_text_input(self, text):
        if text not in ("0", "1"):
            raise ValueError("MENUBAR accepts 0 or 1")
        set_menubar(self.mw, int(text))
        self.finish()


def find_matches(doc, query, case=False, hidden=False):
    if not query:
        return []
    key = query if case else query.casefold()
    return [
        e
        for e in doc.entities
        if e.kind in ("TEXT", "MLEADER")
        and (hidden or doc.layers.is_visible(e.layer))
        and key in (e.text if case else e.text.casefold())
    ]


def replace_text(mw, query, replacement, case=False, hidden=False):
    if not query:
        raise ValueError("Enter search text")
    items = [
        e
        for e in find_matches(mw.document, query, case, hidden)
        if e in mw.document.editable_entities()
    ]
    changes = []
    for e in items:
        text = re.sub(
            re.escape(query),
            lambda _: replacement,
            e.text,
            flags=0 if case else re.IGNORECASE,
        )
        if e.kind == "MLEADER":
            from .mleaders import validate_entity

            candidate = e.clone()
            candidate.text = text
            validate_entity(mw.document, candidate)
        elif len(text) > 100000:
            raise ValueError("Text exceeds native limit")
        if e.kind == "TEXT":
            from .validation import finite

            candidate = e.clone()
            candidate.text = text
            for coordinate in candidate.bbox():
                finite(coordinate, "Text bounds")
        if text != e.text:
            changes.append((e, text))
    if changes:
        mw.document.undo_stack.beginMacro("Replace text")
        for e, text in changes:
            mw.document.undo_stack.push(SetAttrCommand(mw.document,e,"text",e.text,text))
            if e.kind=='TEXT' and e.rich_html:
                mw.document.undo_stack.push(SetAttrCommand(mw.document,e,'rich_html',e.rich_html,'','Replace formatted text'))
        mw.document.undo_stack.endMacro()
    return len(changes)


class FindDialog(QDialog):
    def __init__(self, mw):
        super().__init__(mw)
        self.mw = mw
        self.matches = []
        self.setWindowTitle("Find / Replace annotation text")
        self.resize(510, 380)
        root = QVBoxLayout(self)
        self.query = QLineEdit()
        self.query.setPlaceholderText("Find text…")
        root.addWidget(self.query)
        self.replacement = QLineEdit()
        self.replacement.setPlaceholderText("Replacement text")
        root.addWidget(self.replacement)
        row = QHBoxLayout()
        root.addLayout(row)
        self.case = QCheckBox("Match case")
        self.hidden = QCheckBox("Include hidden layers")
        row.addWidget(self.case)
        row.addWidget(self.hidden)
        self.results = QListWidget()
        root.addWidget(self.results)
        self.status = QLabel()
        root.addWidget(self.status)
        row = QHBoxLayout()
        root.addLayout(row)
        for label, fn in (
            ("Find", self.search),
            ("Replace all editable", self.replace),
            ("Close", self.accept),
        ):
            b = QPushButton(label)
            b.clicked.connect(fn)
            row.addWidget(b)
        self.query.textChanged.connect(self.search)
        self.case.toggled.connect(self.search)
        self.hidden.toggled.connect(self.search)
        self.results.itemDoubleClicked.connect(self.jump)

    def search(self, *args):
        self.matches = find_matches(
            self.mw.document,
            self.query.text(),
            self.case.isChecked(),
            self.hidden.isChecked(),
        )
        self.results.clear()
        self.results.addItems(
            [
                f"{e.kind} · {e.layer} · {e.text[:120].replace(chr(10), ' / ')}"
                for e in self.matches
            ]
        )
        self.status.setText(
            f"{len(self.matches)} matches. Double-click to locate; replacement skips hidden/locked layers."
        )

    def jump(self, item):
        e = self.matches[self.results.row(item)]
        x0, y0, x1, y1 = e.bbox()
        self.mw.canvas.pan_offset = QPointF((x0 + x1) / 2, (y0 + y1) / 2)
        self.mw.canvas.selected_entities = (
            [e] if e in self.mw.document.editable_entities() else []
        )
        self.mw.refresh_document_ui()

    def replace(self):
        try:
            count = replace_text(
                self.mw,
                self.query.text(),
                self.replacement.text(),
                self.case.isChecked(),
                self.hidden.isChecked(),
            )
            self.search()
            self.status.setText(
                f"Replaced text in {count} editable objects. Undo restores them."
            )
        except ValueError as ex:
            QMessageBox.warning(self, "Replace text", str(ex))


def find_dialog(mw):
    d = FindDialog(mw)
    try:
        d.exec()
    finally:
        d.setParent(None)
        d.deleteLater()


EDIT_TOOLS = {"PASTECLIP": PasteTool, "MENUBAR": MenuBarTool}


def commands(mw):
    return {
        "COPYCLIP": lambda: copy_clip(mw),
        "CUTCLIP": lambda: copy_clip(mw, True),
        "FIND": lambda: find_dialog(mw),
    }
