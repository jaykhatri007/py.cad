"""Declarative proposals, native command recording and explicit Python plugins."""

import copy
import importlib.util
import json
import re
import uuid
from pathlib import Path
from .native_io import (
    document_to_dict,
    document_from_dict,
    entity_to_dict,
    entity_from_dict,
)
from .document import (
    AddEntityCommand,
    DeleteEntitiesCommand,
    SetAttrCommand,
    TranslateEntitiesCommand,
)
from .geometry import Point, LineEntity, CircleEntity, RectangleEntity
from .feature_data import edit_table

MAX_ACTIONS = 1000
OPS = {"line", "circle", "rectangle", "move", "copy", "delete", "add", "update", "room"}
from .drafting_actions import OPS as BUILDING_OPS
OPS |= BUILDING_OPS


def validate_actions(actions):
    from .validation import finite, name

    if not isinstance(actions, list) or not 1 <= len(actions) <= MAX_ACTIONS:
        raise ValueError("A proposal needs 1–1,000 actions")
    for action in actions:
        if not isinstance(action, dict) or action.get("op") not in OPS:
            raise ValueError("Unknown proposal action")
        op = action["op"]
        if op in BUILDING_OPS:
            from .drafting_actions import validate
            validate(action)
            continue
        fields = {
            "line": {"op", "start", "end"},
            "circle": {"op", "center", "radius"},
            "rectangle": {"op", "start", "end"},
            "move": {"op", "ids", "dx", "dy"},
            "copy": {"op", "ids", "dx", "dy"},
            "delete": {"op", "ids"},
            "add": {"op", "entity"},
            "update": {"op", "id", "entity"},
            "room": {
                "op",
                "start",
                "width",
                "depth",
                "wall_width",
                "name",
                "number",
                "finish",
            },
        }[op]
        if set(action) != fields:
            raise ValueError("Invalid " + op + " action fields")
        for key in ("start", "end", "center"):
            if key in action:
                if not isinstance(action[key], list) or len(action[key]) != 2:
                    raise ValueError("Coordinates must be [x,y]")
                for v in action[key]:
                    finite(v, "Proposal coordinate")
        for key in ("radius", "width", "depth", "wall_width", "dx", "dy"):
            if key in action:
                finite(action[key], key, key not in ("dx", "dy"))
        if op in ("move", "copy", "delete"):
            if (
                not isinstance(action["ids"], list)
                or not 1 <= len(action["ids"]) <= 100000
            ):
                raise ValueError("Choose target IDs")
            for key in action["ids"]:
                name(key, "Target ID")
        if op == "room":
            for k in ("name", "number", "finish"):
                name(action[k], k)
        if op in ("add", "update"):
            record = action["entity"]
            if not isinstance(record, dict) or set(record) != {"kind", "data"}:
                raise ValueError("Invalid recorded entity")
            # Full native validation occurs against the actual proposal drawing.
            entity_from_dict(record)
            if op == "update":
                name(action["id"], "Recorded target ID")
    return actions


def validate_macros(table):
    for name, value in table.items():
        if not isinstance(value, dict) or set(value) != {"actions"}:
            raise ValueError("Invalid macro definition")
        validate_actions(value["actions"])


def execute_actions(doc, actions):
    validate_actions(actions)
    id_map = {}
    for action in actions:
        if action["op"] == "add":
            id_map[action["entity"]["data"]["id"]] = uuid.uuid4().hex
    for a in actions:
        op = a["op"]
        if op in BUILDING_OPS:
            from .drafting_actions import execute
            execute(doc, a, id_map)
            continue
        style = dict(layer=doc.layers.current_layer, linetype=doc.current_linetype)
        if op in ("line", "rectangle"):
            entity = (LineEntity if op == "line" else RectangleEntity)(
                Point(*a["start"]), Point(*a["end"]), **style
            )
            doc.undo_stack.push(AddEntityCommand(doc, entity, "Assisted " + op))
        elif op == "circle":
            doc.undo_stack.push(
                AddEntityCommand(
                    doc,
                    CircleEntity(Point(*a["center"]), a["radius"], **style),
                    "Assisted circle",
                )
            )
        elif op=='copy':
            from .precision_edit import guard
            entities=[doc.find_by_id(k) for k in a['ids']]
            if any(e is None for e in entities):raise ValueError('Copy target is missing')
            guard(doc,entities)
            if any(e.kind not in ('LINE','ARC','CIRCLE','LWPOLYLINE','RECTANGLE','ELLIPSE','TEXT','POINT') for e in entities):raise ValueError('Assisted array supports primitive geometry')
            for e in entities:
                clone=e.clone();clone.translate(a['dx'],a['dy']);doc.undo_stack.push(AddEntityCommand(doc,clone,'Assisted copy'))
        elif op in ("move", "delete"):
            entities = [doc.find_by_id(id_map.get(k, k)) for k in a["ids"]]
            if any(e is None or e not in doc.editable_entities() for e in entities):
                raise ValueError("A target is missing, hidden or locked")
            doc.undo_stack.push(
                TranslateEntitiesCommand(
                    doc, entities, a["dx"], a["dy"], "Assisted move"
                )
                if op == "move"
                else DeleteEntitiesCommand(doc, entities, "Assisted delete")
            )
        elif op in ("add", "update"):
            record = copy.deepcopy(a["entity"])
            record["data"]["id"] = id_map.get(
                record["data"]["id"], record["data"]["id"]
            )
            data = record["data"]
            for key in ("source_entity_id", "source_arc_id", "source_line_id"):
                if key in data:
                    data[key] = id_map.get(data[key], data[key])
            if "source_line_ids" in data:
                data["source_line_ids"] = [
                    id_map.get(k, k) for k in data["source_line_ids"]
                ]
            entity = entity_from_dict(record)
            if op == "add":
                doc.undo_stack.push(AddEntityCommand(doc, entity, "Replay geometry"))
            else:
                target = doc.find_by_id(id_map.get(a["id"], a["id"]))
                if (
                    target is None
                    or target.kind != entity.kind
                    or target not in doc.editable_entities()
                ):
                    raise ValueError("Recorded edit target is missing or locked")
                for field, value in vars(entity).items():
                    if field in (
                        "id",
                        "selected",
                        "resolved_entities",
                        "_text_style",
                        "_mleader_style",
                    ):
                        continue
                    doc.undo_stack.push(
                        SetAttrCommand(
                            doc,
                            target,
                            field,
                            getattr(target, field),
                            value,
                            "Replay edit",
                        )
                    )
        elif op == "room":
            from .architecture import create_wall, create_room

            x, y = a["start"]
            w, h = a["width"], a["depth"]
            corners = [
                Point(x, y),
                Point(x + w, y),
                Point(x + w, y + h),
                Point(x, y + h),
            ]
            for start, end in zip(corners, corners[1:] + corners[:1]):
                from .building import levels, current_level
                create_wall(doc, start, end, a["wall_width"], levels(doc)[current_level(doc)]['height'])
            boundary = RectangleEntity(corners[0], corners[2], **style)
            doc.undo_stack.push(AddEntityCommand(doc, boundary, "Room boundary"))
            create_room(doc, boundary, a["name"], a["number"], a["finish"])
    doc.sync_associative()
    from .validation import validate_payload

    validate_payload(document_to_dict(doc))


def prepare_proposal(doc, actions):
    clone = document_from_dict(document_to_dict(doc))
    execute_actions(clone, actions)
    clone.mark_saved()
    return clone


def apply_proposal(doc, actions):
    # All structural, layer, reference and constraint checks finish before mutation.
    prepare_proposal(doc, actions)
    start = doc.undo_stack.index()
    doc.undo_stack.beginMacro("Apply reviewed proposal")
    try:
        execute_actions(doc, actions)
    except Exception:
        doc.undo_stack.endMacro()
        if doc.undo_stack.index() > start:
            doc.undo_stack.undo()
        raise
    else:
        doc.undo_stack.endMacro()


def review_proposal(mw, actions, title="Review proposed changes"):
    from PyQt6.QtWidgets import (
        QDialog,
        QVBoxLayout,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QPlainTextEdit,
    )
    from .canvas import CadCanvas

    proposed = prepare_proposal(mw.document, actions)
    from .proposal_review import impact_report
    impact=impact_report(mw.document,proposed)
    fingerprint = document_to_dict(mw.document)
    d = QDialog(mw)
    d.setWindowTitle(title)
    d.resize(850, 560)
    root = QVBoxLayout(d)
    root.addWidget(
        QLabel(
            f"{len(actions)} actions · {len(mw.document.entities)} → {len(proposed.entities)} model objects · Apply creates one Undo step"
        )
    )
    preview = CadCanvas(proposed)
    root.addWidget(preview, 1)
    lines=[f"Added: {impact['added']} · Removed: {impact['removed']} · Changed: {impact['changed']} · Units: {impact['units']}"]
    quantities=impact.get('quantities')
    if quantities:
        lines.append(f"Priced subtotal: {quantities['currency']} {quantities['priced_subtotal_before']:,.2f} → {quantities['priced_subtotal_after']:,.2f}")
        lines.append(f"After changes: {quantities['unpriced_after']} unpriced items, {quantities['unmeasured_after']} unmeasured objects")
    else:lines.append(impact.get('quantities_unavailable','Quantities unavailable'))
    lines.append(impact['note'])
    lines.append('Exact proposed actions:\n'+json.dumps(actions,indent=2,ensure_ascii=False))
    details = QPlainTextEdit('\n'.join(lines))
    details.setReadOnly(True)
    details.setMaximumHeight(110)
    root.addWidget(details)
    bar = QHBoxLayout()
    root.addLayout(bar)
    before = QPushButton("Show original")
    before.setCheckable(True)

    def toggle(value):
        preview.document = mw.document if value else proposed
        preview.zoom_extents()
        preview.viewport().update()

    before.toggled.connect(toggle)
    bar.addWidget(before)
    from .production import comparison_overlay
    overlay_cache=[]
    changes=QPushButton('Show changes overlay')
    def show_changes():
        if not overlay_cache:overlay_cache.append(comparison_overlay(mw.document,proposed)[0])
        before.setChecked(False);preview.document=overlay_cache[0];preview.zoom_extents();preview.viewport().update()
    changes.clicked.connect(show_changes);bar.addWidget(changes)
    def export_plan():
        from PyQt6.QtWidgets import QFileDialog
        from .native_io import atomic_write
        path,_=QFileDialog.getSaveFileName(d,'Export reviewed plan','drafting-plan.json','JSON (*.json)')
        if path:atomic_write(path,lambda p:Path(p).write_text(json.dumps(dict(format='PY.cad drafting plan 1',actions=actions,impact=impact),indent=2),encoding='utf-8'))
    export=QPushButton('Export plan');export.clicked.connect(export_plan);bar.addWidget(export)
    bar.addStretch()
    apply = QPushButton("Apply changes")
    apply.clicked.connect(d.accept)
    bar.addWidget(apply)
    cancel = QPushButton("Cancel")
    cancel.clicked.connect(d.reject)
    bar.addWidget(cancel)
    from PyQt6.QtCore import QTimer

    QTimer.singleShot(0, preview.zoom_extents)
    if d.exec() == QDialog.DialogCode.Accepted:
        if document_to_dict(mw.document) != fingerprint:
            raise ValueError(
                "Drawing changed while the proposal was being reviewed; review again"
            )
        apply_proposal(mw.document, actions)
        mw.refresh_document_ui()
        return True
    return False


class Recorder:
    """Records committed primitive geometry edits, rather than transient mouse motion."""

    def __init__(self, mw):
        self.mw = mw
        self.doc = mw.document
        self.actions = []
        self.before = {e.id: entity_to_dict(e) for e in self.doc.entities}
        self.skipped = 0
        self.doc.undo_stack.indexChanged.connect(self.capture)

    def capture(self, *_):
        after = {e.id: entity_to_dict(e) for e in self.doc.entities}
        supported = {
            "LINE",
            "CIRCLE",
            "ARC",
            "POINT",
            "ELLIPSE",
            "LWPOLYLINE",
            "RECTANGLE",
            "SPLINE",
            "TEXT",
        }
        for key, record in after.items():
            if record["kind"] not in supported:
                if self.before.get(key) != record:
                    self.skipped += 1
                continue
            if key not in self.before:
                self.actions.append({"op": "add", "entity": record})
            elif self.before[key] != record:
                self.actions.append({"op": "update", "id": key, "entity": record})
        deleted = [
            k
            for k, r in self.before.items()
            if k not in after and r["kind"] in supported
        ]
        if deleted:
            self.actions.append({"op": "delete", "ids": deleted})
        self.before = after

    def stop(self):
        self.doc.undo_stack.indexChanged.disconnect(self.capture)
        return self.actions


def toggle_recording(mw):
    from PyQt6.QtWidgets import QInputDialog

    recorder = getattr(mw, "action_recorder", None)
    if recorder is None:
        mw.action_recorder = Recorder(mw)
        mw.command_history.appendPlainText(
            "Recording primitive geometry commands. ACTRECORD again stops and saves; blocks, architecture, styles and file commands are excluded."
        )
        return
    actions = recorder.stop()
    mw.action_recorder = None
    if not actions:
        mw.command_history.appendPlainText("No supported edits were recorded.")
        return
    name, ok = QInputDialog.getText(mw, "Save macro", "Macro name")
    if ok and name.strip():
        edit_table(
            recorder.doc,
            "macros",
            name.strip(),
            {"actions": actions},
            "Save action macro",
        )
    if recorder.skipped:
        mw.command_history.appendPlainText(
            f"{recorder.skipped} unsupported changes were excluded from the macro."
        )


def macro_dialog(mw):
    from PyQt6.QtWidgets import (
        QDialog,
        QVBoxLayout,
        QHBoxLayout,
        QListWidget,
        QPushButton,
        QFileDialog,
        QMessageBox,
    )

    d = QDialog(mw)
    d.setWindowTitle("Action macros")
    d.resize(450, 300)
    root = QVBoxLayout(d)
    items = QListWidget()
    root.addWidget(items)
    bar = QHBoxLayout()
    root.addLayout(bar)

    def refresh():
        items.clear()
        items.addItems(mw.document.extensions.get("macros", {}))

    def run():
        item = items.currentItem()
        if item:
            review_proposal(
                mw,
                mw.document.extensions["macros"][item.text()]["actions"],
                "Review macro: " + item.text(),
            )

    def import_():
        path, _ = QFileDialog.getOpenFileName(d, "Import macro", "", "JSON (*.json)")
        if not path:
            return
        try:
            if Path(path).stat().st_size > 8 * 1024 * 1024:
                raise ValueError("Macro exceeds 8 MiB")
            value = json.loads(Path(path).read_text())
            validate_macros(value)
            for name, macro in value.items():
                edit_table(mw.document, "macros", name, macro, "Import macro")
            refresh()
        except ValueError as ex:
            QMessageBox.warning(d, "Macro", str(ex))

    def export():
        item = items.currentItem()
        if not item:
            return
        path, _ = QFileDialog.getSaveFileName(
            d, "Export macro", item.text() + ".json", "JSON (*.json)"
        )
        if path:
            from .native_io import atomic_write

            value = {item.text(): mw.document.extensions["macros"][item.text()]}
            atomic_write(
                path, lambda f: Path(f).write_text(json.dumps(value, indent=2))
            )

    for label, fn in [
        ("Review / Run", run),
        ("Import", import_),
        ("Export", export),
        ("Close", d.accept),
    ]:
        b = QPushButton(label)
        b.clicked.connect(
            __import__("pycad.feature_helpers", fromlist=["safe_action"]).safe_action(
                d, fn
            )
        )
        bar.addWidget(b)
    refresh()
    d.exec()


def parse_instruction(text, selected_ids=()):
    """Local offline assistant. Structured JSON permits every supported action."""
    text = text.strip()
    if text.startswith("["):
        return validate_actions(json.loads(text))
    number = r"([-+]?\d+(?:\.\d+)?)"
    match = re.fullmatch(
        r"(?:draw |create )?(circle)\s+"
        + number
        + r"\s+at\s+"
        + number
        + r"\s*,\s*"
        + number,
        text,
        re.I,
    )
    if match:
        _, radius, x, y = match.groups()
        return [
            {"op": "circle", "center": [float(x), float(y)], "radius": float(radius)}
        ]
    match = re.fullmatch(
        r"(?:draw |create )?(rectangle|room)\s+"
        + number
        + r"\s*[x×,]\s*"
        + number
        + r"(?:\s+at\s+"
        + number
        + r"\s*,\s*"
        + number
        + r")?",
        text,
        re.I,
    )
    if match:
        kind, w, h, x, y = match.groups()
        w, h = float(w), float(h)
        x, y = float(x or 0), float(y or 0)
        if kind.lower() == "rectangle":
            return [{"op": "rectangle", "start": [x, y], "end": [x + w, y + h]}]
        return [
            {
                "op": "room",
                "start": [x, y],
                "width": w,
                "depth": h,
                "wall_width": min(w, h) * 0.05,
                "name": "Room",
                "number": "101",
                "finish": "Paint",
            }
        ]
    match = re.fullmatch(
        r"move (?:selection|selected)\s+by\s+" + number + r"\s*,\s*" + number,
        text,
        re.I,
    )
    if match:
        return validate_actions(
            [
                {
                    "op": "move",
                    "ids": list(selected_ids),
                    "dx": float(match[1]),
                    "dy": float(match[2]),
                }
            ]
        )
    match = re.fullmatch(
        r"(?:draw |create )?line from\s+"
        + number
        + r"\s*,\s*"
        + number
        + r"\s+to\s+"
        + number
        + r"\s*,\s*"
        + number,
        text,
        re.I,
    )
    if match:
        return [
            {
                "op": "line",
                "start": [float(match[1]), float(match[2])],
                "end": [float(match[3]), float(match[4])],
            }
        ]
    raise ValueError(
        "Use: rectangle 6000x4000 at 0,0; room 6000x4000; circle 100 at 0,0; line from 0,0 to 100,100; move selection by 10,20; or a JSON action list."
    )


def assistant_dialog(mw):
    from PyQt6.QtWidgets import (
        QDialog,
        QVBoxLayout,
        QLabel,
        QPlainTextEdit,
        QPushButton,
        QMessageBox,
    )

    d = QDialog(mw)
    d.setWindowTitle("Drawing assistant · local proposals")
    d.resize(560, 330)
    root = QVBoxLayout(d)
    root.addWidget(
        QLabel(
            "Offline instructions or JSON actions. Every change is previewed before Apply.\nExamples: room 6000x4000; rectangle 100x50 at 0,0; circle 25 at 40,40"
        )
    )
    text = QPlainTextEdit()
    root.addWidget(text)
    button = QPushButton("Build and review proposal")
    root.addWidget(button)

    def review():
        try:
            actions = parse_instruction(
                text.toPlainText(), [e.id for e in mw.canvas.selected_entities]
            )
            review_proposal(mw, actions)
        except ValueError as ex:
            QMessageBox.warning(d, "Proposal", str(ex))

    button.clicked.connect(review)
    d.exec()


class PluginAPI:
    """Trusted Python plugins register commands; proposals use the same review path."""

    def __init__(self, mw):
        self.window = mw

    def register_command(self, name, callback):
        name = name.strip().upper()
        if not re.fullmatch("[A-Z][A-Z0-9_]{1,39}", name) or not callable(callback):
            raise ValueError("Invalid plugin command")
        if name in self.window.canonical_commands:
            raise ValueError("Command already exists")
        self.window.plugin_commands[name] = callback
        self.window.canonical_commands.add(name)
        self.window.command_names = sorted(
            self.window.canonical_commands | set(self.window.user_aliases)
        )

    def propose(self, actions, title="Python plugin proposal"):
        return review_proposal(self.window, actions, title)

    @property
    def selection(self):
        return [e.id for e in self.window.canvas.selected_entities]


def load_plugin(mw, path):
    path = Path(path).resolve()
    if path.suffix.lower() != ".py" or path.stat().st_size > 1024 * 1024:
        raise ValueError("Choose a Python plugin at most 1 MiB")
    mw.plugin_commands = getattr(mw, "plugin_commands", {})
    spec = importlib.util.spec_from_file_location(
        "pycad_plugin_" + uuid.uuid4().hex, path
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    register = getattr(module, "register", None)
    if not callable(register):
        raise ValueError("Plugin must define register(api)")
    register(PluginAPI(mw))
    mw.loaded_plugins = getattr(mw, "loaded_plugins", []) + [module]
    return module


def plugin_dialog(mw):
    from PyQt6.QtWidgets import QFileDialog, QMessageBox

    path, _ = QFileDialog.getOpenFileName(
        mw, "Load a trusted Python plugin", "", "Python (*.py)"
    )
    if not path:
        return
    if (
        QMessageBox.question(
            mw,
            "Run Python plugin",
            "This local plugin executes Python with your user permissions. Load "
            + Path(path).name
            + "?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        != QMessageBox.StandardButton.Yes
    ):
        return
    load_plugin(mw, path)
    mw.command_history.appendPlainText("Loaded Python plugin: " + Path(path).name)
