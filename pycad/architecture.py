"""Straight parametric walls, hosted openings and associative room labels."""

import csv
import math
import uuid
from .geometry import (
    Point,
    LineEntity,
    PolylineEntity,
    ArcEntity,
    TextEntity,
    BlockDefinition,
    BlockReferenceEntity,
)
from .document import AddEntityCommand
from .feature_data import edit_table


def validate_table(table, payload):
    from .validation import finite, name

    kinds = {
        "wall": {"kind", "block", "length", "width", "height", "material"},
        "opening": {
            "kind",
            "block",
            "wall",
            "type",
            "station",
            "width",
            "height",
            "sill",
            "identifier",
        },
        "room": {"kind", "block", "source", "name", "number", "finish", "boundary"},
    }
    active = {r['data']['id'] for r in payload.get('entities', []) if isinstance(r, dict) and isinstance(r.get('data'), dict) and isinstance(r['data'].get('id'), str)} if payload else None
    for key, r in table.items():
        name(key, "Architectural object ID")
        if (
            not isinstance(r, dict)
            or r.get("kind") not in kinds
            or set(r) != kinds[r["kind"]]
        ):
            raise ValueError("Invalid architectural record")
        name(r["block"], "Architectural block")
        # Deleted source/object records stay dormant to support undo and relinking.
        if r["kind"] == "wall":
            for k in ("length", "width", "height"):
                finite(r[k], k, True)
            if not isinstance(r["material"], str) or len(r["material"]) > 1000:
                raise ValueError("Invalid wall material")
        elif r["kind"] == "opening":
            if r["type"] not in ("door", "window"):
                raise ValueError("Invalid opening type")
            name(r["wall"], "Host wall")
            name(r["identifier"], "Opening ID")
            for k in ("width", "height"):
                finite(r[k], k, True)
            for k in ("station", "sill"):
                finite(r[k], k)
            if r["station"] < 0 or r["sill"] < 0:
                raise ValueError("Opening station and sill cannot be negative")
            if active is not None and key not in active:
                continue
            host = table.get(r["wall"])
            if (
                host is None
                or host["kind"] != "wall"
                or r["station"] + r["width"] / 2 > host["length"] + 1e-9
                or r["station"] - r["width"] / 2 < 0
            ):
                raise ValueError("Opening lies outside its wall")
            if r["sill"] + r["height"] > host["height"] + 1e-9:
                raise ValueError("Opening lies above the wall head")
        else:
            for k in ("name", "number", "finish"):
                if not isinstance(r[k], str) or len(r[k]) > 1000:
                    raise ValueError("Invalid room data")
            name(r["source"], "Room boundary source")
            if (
                not isinstance(r["boundary"], list)
                or not 3 <= len(r["boundary"]) <= 2000
            ):
                raise ValueError("Invalid room boundary")
            for p in r["boundary"]:
                if not isinstance(p, list) or len(p) != 2:
                    raise ValueError("Invalid room point")
                for v in p:
                    finite(v, "Room point")


from PyQt6.QtGui import QUndoCommand


class BlockInstallCommand(QUndoCommand):
    def __init__(self, doc, block):
        super().__init__("Add block definition")
        self.doc = doc
        self.block = block
        self.before = doc.blocks.get(block.name)

    def redo(self):
        self.doc.blocks[self.block.name] = self.block

    def undo(self):
        if self.before is None:
            self.doc.blocks.pop(self.block.name, None)
        else:
            self.doc.blocks[self.block.name] = self.before


def _install(doc, name, entities, position=Point(0, 0), rotation=0):
    block = BlockDefinition(name, entities)
    doc.undo_stack.push(BlockInstallCommand(doc, block))
    insert = BlockReferenceEntity(
        name,
        Point(position.x, position.y),
        rotation=rotation,
        layer=doc.layers.current_layer,
    )
    doc.undo_stack.push(AddEntityCommand(doc, insert, "Architectural object"))
    return insert


def create_wall(doc, a, b, width=200, height=3000, material="Masonry"):
    from .validation import finite

    for value in (a.x, a.y, b.x, b.y):
        finite(value, "Wall coordinate")
    finite(width, "Wall width", True)
    finite(height, "Wall height", True)
    length = a.distance_to(b)
    if length <= width * 0.01:
        raise ValueError("Wall is too short")
    doc.undo_stack.beginMacro("Wall")
    try:
        name = "WALL_" + uuid.uuid4().hex[:10]
        insert = _install(
            doc, name, [], a, math.degrees(math.atan2(b.y - a.y, b.x - a.x))
        )
        edit_table(
            doc,
            "architecture",
            insert.id,
            dict(
                kind="wall",
                block=name,
                length=length,
                width=width,
                height=height,
                material=material,
            ),
            "Wall parameters",
        )
        if doc.extensions.get('levels'):
            from .building import current_level
            edit_table(doc, 'level_assignments', insert.id, {'level': current_level(doc)}, 'Wall level')
    finally:
        doc.undo_stack.endMacro()
    return insert


def create_opening(
    doc,
    wall,
    station,
    width=900,
    height=2100,
    opening_type="door",
    identifier="D01",
    sill=0,
):
    records = doc.extensions.get("architecture", {})
    host = records.get(wall.id)
    if host is None or host["kind"] != "wall" or wall not in doc.editable_entities():
        raise ValueError("Select an editable architectural wall")
    record = dict(
        kind="opening",
        block="OPENING_" + uuid.uuid4().hex[:10],
        wall=wall.id,
        type=opening_type,
        station=station,
        width=width,
        height=height,
        sill=sill,
        identifier=identifier,
    )
    prospective = dict(records)
    prospective["pending"] = record
    validate_table(prospective, {"entities": [{"data": {"id": e.id}} for e in doc.entities] + [{"data": {"id": "pending"}}]})
    if height + sill > host["height"]:
        raise ValueError("Opening is higher than the wall")
    for opening_id, r in records.items():
        if (
            doc.find_by_id(opening_id)
            and r["kind"] == "opening"
            and r["wall"] == wall.id
            and abs(r["station"] - station) < (r["width"] + width) / 2 - 1e-9
        ):
            raise ValueError("Openings cannot overlap")
    doc.undo_stack.beginMacro("Door" if opening_type == "door" else "Window")
    try:
        insert = _install(doc, record["block"], [])
        edit_table(doc, "architecture", insert.id, record, "Opening parameters")
    finally:
        doc.undo_stack.endMacro()
    return insert


def create_room(doc, boundary, name="Room", number="101", finish="Paint"):
    if (
        not isinstance(boundary, PolylineEntity)
        or not boundary.closed
        or boundary not in doc.editable_entities()
    ):
        raise ValueError("Select one closed room boundary")
    pts = boundary.sample_points()
    if pts and pts[-1].distance_to(pts[0]) < 1e-9:
        pts = pts[:-1]
    if len(pts) > 2000:
        raise ValueError("Room boundary exceeds 2,000 sampled points")
    from .model3d import validate_feature

    validate_feature(
        dict(
            id="test",
            name="room",
            layer=boundary.layer,
            height=1,
            profile={"kind": "POLYGON", "points": [[p.x, p.y] for p in pts]},
        ),
        doc.layers.layers,
    )
    doc.undo_stack.beginMacro("Room label")
    try:
        block = "ROOM_" + uuid.uuid4().hex[:10]
        insert = _install(doc, block, [])
        record = dict(
            kind="room",
            block=block,
            source=boundary.id,
            name=name,
            number=number,
            finish=finish,
            boundary=[[p.x, p.y] for p in pts],
        )
        edit_table(doc, "architecture", insert.id, record, "Room data")
        if doc.extensions.get('levels'):
            from .building import level_for
            edit_table(doc, 'level_assignments', insert.id, {'level': level_for(doc,boundary.id)}, 'Room level')
    finally:
        doc.undo_stack.endMacro()
    return insert


def room_metrics(doc, record):
    from .precision import polyline_measure

    boundary = doc.find_by_id(record["source"])
    if isinstance(boundary, PolylineEntity) and boundary.closed:
        pts = boundary.sample_points()
        perimeter, area = polyline_measure(boundary)
    else:
        pts = [Point(*p) for p in record["boundary"]]
        perimeter, area = polyline_measure(PolylineEntity(pts, True))
    if pts and pts[-1].distance_to(pts[0]) < 1e-9:
        pts = pts[:-1]
    return pts, area, perimeter


def sync_architecture(doc):
    records = doc.extensions.get("architecture", {})
    for key, r in records.items():
        insert = doc.find_by_id(key)
        block = doc.blocks.get(r["block"])
        if not isinstance(insert, BlockReferenceEntity) or block is None:
            continue
        layer = insert.layer
        if r["kind"] == "wall":
            w = r["width"]
            intervals = []
            for oid, o in records.items():
                if o["kind"] == "opening" and o["wall"] == key and doc.find_by_id(oid):
                    intervals.append(
                        (o["station"] - o["width"] / 2, o["station"] + o["width"] / 2)
                    )
            parts = []
            start = 0
            for a, b in sorted(intervals) + [(r["length"], r["length"])]:
                if a > start + 1e-9:
                    parts.append(
                        PolylineEntity(
                            [
                                Point(start, -w / 2),
                                Point(a, -w / 2),
                                Point(a, w / 2),
                                Point(start, w / 2),
                            ],
                            True,
                            layer=layer,
                        )
                    )
                start = max(start, b)
            block.entities = parts
        elif r["kind"] == "opening":
            host = doc.find_by_id(r["wall"])
            h = records.get(r["wall"])
            if not isinstance(host, BlockReferenceEntity) or h is None:
                continue
            theta = math.radians(host.rotation)
            station = r["station"] * host.scale
            insert.insertion_point = Point(
                host.insertion_point.x + station * math.cos(theta),
                host.insertion_point.y + station * math.sin(theta),
            )
            insert.rotation = host.rotation
            insert.scale = host.scale
            insert.mirrored = host.mirrored
            w = r["width"]
            thickness = h["width"]
            parts = []
            if r["type"] == "door":
                hinge = Point(-w / 2, thickness / 2)
                parts = [
                    LineEntity(hinge, Point(-w / 2, w + thickness / 2), layer=layer),
                    ArcEntity(hinge, w, 0, 90, layer=layer),
                ]
            else:
                parts = [
                    PolylineEntity(
                        [
                            Point(-w / 2, -thickness / 2),
                            Point(w / 2, -thickness / 2),
                            Point(w / 2, thickness / 2),
                            Point(-w / 2, thickness / 2),
                        ],
                        True,
                        layer=layer,
                    ),
                    LineEntity(Point(-w / 2, 0), Point(w / 2, 0), layer=layer),
                ]
            label = TextEntity(
                Point(-w / 2, -thickness * 0.7),
                r["identifier"],
                height=max(w * 0.06, 1),
                layer=layer,
            )
            block.entities = parts + [label]
        else:
            pts, area, perimeter = room_metrics(doc, r)
            if not pts:
                continue
            x = sum(p.x for p in pts) / len(pts)
            y = sum(p.y for p in pts) / len(pts)
            insert.insertion_point = Point(x, y)
            insert.rotation = 0
            insert.scale = 1
            extent = max(
                max(p.x for p in pts) - min(p.x for p in pts),
                max(p.y for p in pts) - min(p.y for p in pts),
            )
            height = max(extent * 0.025, 0.1)
            from .units import UNIT_MM

            sqm = area * (UNIT_MM[doc.units] / 1000) ** 2
            area_text = (
                f"{area:.2f} units²" if doc.units == "unitless" else f"{sqm:.2f} m²"
            )
            block.entities = [
                TextEntity(
                    Point(-height * 3, 0),
                    r["number"]
                    + " · "
                    + r["name"]
                    + "\n"
                    + area_text
                    + "\n"
                    + r["finish"],
                    height=height,
                    layer=layer,
                )
            ]

        for i, child in enumerate(block.entities):
            child.id = uuid.uuid5(uuid.NAMESPACE_URL, key + "/" + str(i)).hex

    from .wall_joining import joined_outlines
    for key, parts in joined_outlines(doc).items():
        block = doc.blocks[records[key]['block']]
        block.entities = parts
        for i, child in enumerate(parts):
            child.id = uuid.uuid5(uuid.NAMESPACE_URL, key + '/join/' + str(i)).hex


def finish_rows(doc):
    result = []
    from .units import UNIT_MM

    for key, r in doc.extensions.get("architecture", {}).items():
        if not doc.find_by_id(key) or r["kind"] != "room":
            continue
        _, area, perimeter = room_metrics(doc, r)
        factor = UNIT_MM[doc.units] / 1000
        result.append(
            {
                "Number": r["number"],
                "Room": r["name"],
                "Finish": r["finish"],
                "Area": area if doc.units == "unitless" else area * factor * factor,
                "Perimeter": perimeter
                if doc.units == "unitless"
                else perimeter * factor,
                "Units": "drawing units" if doc.units == "unitless" else "m / m²",
            }
        )
    return result


def export_finishes(doc, path):
    from .native_io import atomic_write

    def write(filename):
        with open(filename, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=["Number", "Room", "Finish", "Area", "Perimeter", "Units"]
            )
            writer.writeheader()
            writer.writerows(finish_rows(doc))

    atomic_write(path, write)


def architecture_dialog(mw):
    from PyQt6.QtWidgets import (
        QDialog,
        QVBoxLayout,
        QHBoxLayout,
        QTableWidget,
        QTableWidgetItem,
        QPushButton,
        QInputDialog,
        QFileDialog,
        QMessageBox,
    )

    d = QDialog(mw)
    d.setWindowTitle("Architectural objects")
    d.resize(650, 400)
    root = QVBoxLayout(d)
    table = QTableWidget()
    root.addWidget(table)
    table.setColumnCount(5)
    table.setHorizontalHeaderLabels(
        ["Kind", "ID / Name", "Size / Area", "Height / Finish", "Layer"]
    )
    bar = QHBoxLayout()
    root.addLayout(bar)

    def refresh():
        records = [
            (key, r)
            for key, r in mw.document.extensions.get("architecture", {}).items()
            if mw.document.find_by_id(key)
        ]
        table.setRowCount(len(records))
        d.records = records
        for i, (key, r) in enumerate(records):
            e = mw.document.find_by_id(key)
            values = [
                r["kind"],
                r.get("identifier", r.get("name", r["block"])),
                r.get(
                    "width",
                    room_metrics(mw.document, r)[1] if r["kind"] == "room" else "",
                ),
                r.get("finish", r.get("height", "")),
                e.layer,
            ]
            for j, value in enumerate(values):
                table.setItem(i, j, QTableWidgetItem(str(value)))
        table.resizeColumnsToContents()

    def edit():
        i = table.currentRow()
        if i < 0:
            return
        key, r = d.records[i]
        after = dict(r)
        fields = {
            "wall": ["length", "width", "height", "material"],
            "opening": ["identifier", "station", "width", "height", "sill"],
            "room": ["number", "name", "finish"],
        }[r["kind"]]
        # One compact key=value editor keeps every persisted parameter accessible.
        text = "\n".join(f"{k}={r[k]}" for k in fields)
        value, ok = QInputDialog.getMultiLineText(
            d, "Edit object", "Parameters (one key=value per line)", text
        )
        if not ok:
            return
        try:
            for line in value.splitlines():
                k, v = line.split("=", 1)
                if k not in fields:
                    raise ValueError("Unknown parameter " + k)
                after[k] = float(v) if type(r[k]) in (int, float) else v
            prospective = dict(mw.document.extensions["architecture"])
            prospective[key] = after
            from .native_io import document_to_dict
            validate_table(prospective, document_to_dict(mw.document))
            edit_table(
                mw.document, "architecture", key, after, "Architectural parameters"
            )
            refresh()
        except ValueError as ex:
            QMessageBox.warning(d, "Parameters", str(ex))

    def export():
        path, _ = QFileDialog.getSaveFileName(
            d, "Finish schedule", "finish-schedule.csv", "CSV (*.csv)"
        )
        if path:
            export_finishes(mw.document, path)

    for label, fn in [
        ("Edit parameters", edit),
        ("Refresh", refresh),
        ("Finish CSV", export),
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


def create_from_selection(mw, kind):
    from PyQt6.QtWidgets import QInputDialog

    doc = mw.document
    items = mw.canvas.selected_entities
    if kind == "wall":
        from .architecture_tools import WallTool

        width, ok = QInputDialog.getDouble(
            mw, "Wall", "Wall width (drawing units)", 200, 0.001, 1e9, 3
        )
        if not ok:
            return
        height, ok = QInputDialog.getDouble(
            mw, "Wall", "Wall height", 3000, 0.001, 1e9, 3
        )
        if not ok:
            return
        lines = [
            e
            for e in items
            if isinstance(e, LineEntity) and e in doc.editable_entities()
        ]
        if lines:
            doc.undo_stack.beginMacro("Walls from lines")
            for line in lines:
                create_wall(doc, line.p1, line.p2, width, height)
            doc.undo_stack.endMacro()
        else:
            mw.cancel_command()
            mw.current_tool = WallTool(mw, width, height)
            mw.canvas.set_active_tool(mw.current_tool)
    elif kind == "room":
        if len(items) != 1:
            raise ValueError("Select a closed polyline or rectangle")
        name, ok = QInputDialog.getText(mw, "Room", "Room name")
        if not ok:
            return
        number, ok = QInputDialog.getText(mw, "Room", "Room number", text="101")
        if not ok:
            return
        finish, ok = QInputDialog.getText(mw, "Room", "Finish", text="Paint")
        if ok:
            create_room(doc, items[0], name, number, finish)
    else:
        from .architecture_tools import OpeningTool

        width, ok = QInputDialog.getDouble(
            mw,
            kind.title(),
            "Opening width",
            900 if kind == "door" else 1200,
            0.001,
            1e9,
            3,
        )
        if not ok:
            return
        identifier, ok = QInputDialog.getText(
            mw, kind.title(), "Identifier", text="D01" if kind == "door" else "W01"
        )
        if ok:
            mw.cancel_command()
            mw.current_tool = OpeningTool(mw, kind, width, identifier)
            mw.canvas.set_active_tool(mw.current_tool)
    mw.update_status()
    mw.canvas.viewport().update()


def build_wall_solids(doc, wall_ids=None):
    """Generate or update live wall models, retaining stable model/source IDs."""
    from .connected_models import build_models
    return build_models(doc, wall_ids)


def walls_to_3d(mw):
    ids = [e.id for e in mw.canvas.selected_entities]
    build_wall_solids(mw.document, ids or None)
    mw.open_model_workspace()
