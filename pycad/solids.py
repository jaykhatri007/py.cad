"""Optional CadQuery B-rep operations, persisted solids and 2D projections."""

import base64
import hashlib
import io
import uuid
from .feature_data import edit_table


def kernel():
    try:
        import cadquery as cq

        return cq
    except ImportError as ex:
        raise ValueError(
            "Install requirements-3d.txt to enable the CadQuery solid kernel"
        ) from ex


def validate_solids(table, layers):
    from .validation import name, finite

    for key, r in table.items():
        if not isinstance(r, dict) or set(r) != {
            "name",
            "layer",
            "operation",
            "brep",
            "sha256",
            "vertices",
            "faces",
            "volume",
        }:
            raise ValueError("Invalid solid record")
        name(key, "Solid ID")
        name(r["name"], "Solid name")
        if r["layer"] not in layers or r["operation"] not in (
            "union",
            "subtract",
            "intersect",
            "revolve",
            "sweep",
            "extrude",
        ):
            raise ValueError("Invalid solid layer or operation")
        finite(r["volume"], "Solid volume", True)
        if not isinstance(r["brep"], str) or len(r["brep"]) > 24 * 1024 * 1024:
            raise ValueError("Solid B-rep exceeds 18 MiB")
        try:
            raw = base64.b64decode(r["brep"], validate=True)
        except Exception as ex:
            raise ValueError("Invalid solid encoding") from ex
        if hashlib.sha256(raw).hexdigest() != r["sha256"]:
            raise ValueError("Solid checksum mismatch")
        if (
            not isinstance(r["vertices"], list)
            or len(r["vertices"]) > 200000
            or not isinstance(r["faces"], list)
            or len(r["faces"]) > 300000
        ):
            raise ValueError("Solid mesh exceeds display budget")
        for p in r["vertices"]:
            if not isinstance(p, list) or len(p) != 3:
                raise ValueError("Invalid solid vertex")
            for v in p:
                finite(v, "Solid coordinate")
        for face in r["faces"]:
            if (
                not isinstance(face, list)
                or len(face) != 3
                or any(
                    type(i) is not int or not 0 <= i < len(r["vertices"]) for i in face
                )
            ):
                raise ValueError("Invalid solid triangle")


def shape_record(shape, name, layer, operation):
    if not shape.isValid() or not shape.Solids() or shape.Volume() <= 1e-12:
        raise ValueError("The operation produced no valid closed solid")
    stream = io.BytesIO()
    if not shape.exportBrep(stream):
        raise ValueError("Unable to serialize the solid")
    raw = stream.getvalue()
    bounds = shape.BoundingBox()
    extent = max(bounds.xlen, bounds.ylen, bounds.zlen, 1)
    vertices, faces = shape.tessellate(max(extent * 0.001, 1e-5))
    return dict(
        name=name,
        layer=layer,
        operation=operation,
        brep=base64.b64encode(raw).decode("ascii"),
        sha256=hashlib.sha256(raw).hexdigest(),
        vertices=[[v.x, v.y, v.z] for v in vertices],
        faces=[list(f) for f in faces],
        volume=shape.Volume(),
    )


def store_shape(doc, shape, operation, name=None, layer=None):
    key = uuid.uuid4().hex
    record = shape_record(
        shape,
        name
        or operation.title() + " " + str(len(doc.extensions.get("solids", {})) + 1),
        layer or doc.layers.current_layer,
        operation,
    )
    validate_solids({key: record}, doc.layers.layers)
    edit_table(doc, "solids", key, record, "3D " + operation)
    return key


def get_shape(doc, key):
    if (key in doc.extensions.get('wall_models', {}) or key in doc.extensions.get('building_models', {})) and not getattr(doc, '_syncing_connected', False):
        doc.sync_associative()
    status = getattr(doc, 'link_status', {}).get(key, 'Current')
    if status != 'Current':
        raise ValueError(status)
    table = doc.extensions.get("solids", {})
    if key in table:
        return kernel().Shape.importBrep(
            io.BytesIO(base64.b64decode(table[key]["brep"]))
        )
    for feature in doc.extrusions:
        if feature["id"] == key:
            from .model3d import profile_entity
            from .extrude3d import extrude_to_solid

            return extrude_to_solid(profile_entity(feature), feature["height"]).val()
    raise ValueError("Solid or saved extrusion does not exist")


def boolean(doc, keys, operation):
    if (
        operation not in ("union", "subtract", "intersect")
        or len(keys) < 2
        or len(set(keys)) != len(keys)
    ):
        raise ValueError(
            "Choose at least two different solids; first is the subtraction base"
        )
    shapes = [get_shape(doc, k) for k in keys]
    shape = shapes[0]
    for other in shapes[1:]:
        shape = {
            "union": shape.fuse,
            "subtract": shape.cut,
            "intersect": shape.intersect,
        }[operation](other)
    # Keep source solids so callers can revise them or undo independently.
    return store_shape(doc, shape, operation)


def profile_wire(entity, z=0):
    cq = kernel()
    from .geometry import CircleEntity, PolylineEntity
    from .precision import segment_point

    if isinstance(entity, CircleEntity):
        return cq.Wire.makeCircle(
            entity.radius,
            cq.Vector(entity.center.x, entity.center.y, z),
            cq.Vector(0, 0, 1),
        )
    if not isinstance(entity, PolylineEntity) or not entity.closed:
        raise ValueError("Select a circle or closed polyline")
    edges = []
    for i, (a, b) in enumerate(
        zip(entity.points, entity.points[1:] + entity.points[:1])
    ):
        start = cq.Vector(a.x, a.y, z)
        end = cq.Vector(b.x, b.y, z)
        if entity.bulges[i]:
            m = segment_point(a, b, entity.bulges[i], 0.5)
            edges.append(cq.Edge.makeThreePointArc(start, cq.Vector(m.x, m.y, z), end))
        else:
            edges.append(cq.Edge.makeLine(start, end))
    wire = cq.Wire.assembleEdges(edges)
    if not wire.isValid():
        raise ValueError("Profile wire is invalid")
    return wire


def revolve(doc, entity, axis="Y", angle=360, axis_origin=(0, 0)):
    from .validation import finite

    finite(angle, "Revolve angle", True)
    if axis not in ("X", "Y") or angle > 360:
        raise ValueError("Choose X/Y axis and an angle at most 360°")
    for v in axis_origin:
        finite(v, "Axis origin")
    x, y = axis_origin
    end = (x + 1, y, 0) if axis == "X" else (x, y + 1, 0)
    shape = kernel().Solid.revolve(profile_wire(entity), [], angle, (x, y, 0), end)
    return store_shape(doc, shape, "revolve", layer=entity.layer)


def sweep(doc, path, radius):
    from .geometry import LineEntity, PolylineEntity, SplineEntity
    from .validation import finite

    cq = kernel()
    finite(radius, "Sweep radius", True)
    if isinstance(path, LineEntity):
        points = [path.p1, path.p2]
    elif isinstance(path, (PolylineEntity, SplineEntity)) and not path.closed:
        points = (
            path.sample_points()
            if isinstance(path, PolylineEntity)
            else path._catmull_rom_samples(32)
        )
    else:
        raise ValueError("Select an open line, polyline or spline path")
    pts = [cq.Vector(p.x, p.y, 0) for p in points]
    if any(a.sub(b).Length < 1e-9 for a, b in zip(pts, pts[1:])):
        raise ValueError("Sweep path contains a zero-length edge")
    if isinstance(path, SplineEntity):
        edge = cq.Edge.makeSpline(pts)
        wire = cq.Wire.assembleEdges([edge])
    elif isinstance(path, PolylineEntity) and any(path.bulges):
        from .precision import segment_point

        edges = []
        for i, (a, b) in enumerate(zip(points, points[1:])):
            edges.append(
                cq.Edge.makeLine(cq.Vector(a.x, a.y, 0), cq.Vector(b.x, b.y, 0))
            )
        # Use the original exact arcs instead of their display samples.
        edges = []
        for i, (a, b) in enumerate(zip(path.points, path.points[1:])):
            if path.bulges[i]:
                m = segment_point(a, b, path.bulges[i], 0.5)
                edges.append(
                    cq.Edge.makeThreePointArc(
                        cq.Vector(a.x, a.y, 0),
                        cq.Vector(m.x, m.y, 0),
                        cq.Vector(b.x, b.y, 0),
                    )
                )
            else:
                edges.append(
                    cq.Edge.makeLine(cq.Vector(a.x, a.y, 0), cq.Vector(b.x, b.y, 0))
                )
        wire = cq.Wire.assembleEdges(edges)
    else:
        wire = cq.Wire.makePolygon(pts)
    first = wire.Edges()[0]
    origin = first.startPoint()
    tangent = first.tangentAt(0)
    profile = cq.Wire.makeCircle(radius, origin, tangent)
    shape = cq.Solid.sweep(
        profile, [], wire, makeSolid=True, isFrenet=False, transitionMode="round"
    )
    return store_shape(doc, shape, "sweep", layer=path.layer)


def section_paths(doc, key, axis="Z", offset=0):
    from .validation import finite

    cq = kernel()
    finite(offset, "Section offset")
    if axis not in ("X", "Y", "Z"):
        raise ValueError("Section axis must be X, Y or Z")
    shape = get_shape(doc, key)
    bounds = shape.BoundingBox()
    size = max(bounds.xlen, bounds.ylen, bounds.zlen, 1) * 4
    normals = {"X": (1, 0, 0), "Y": (0, 1, 0), "Z": (0, 0, 1)}
    origin = {"X": (offset, 0, 0), "Y": (0, offset, 0), "Z": (0, 0, offset)}[axis]
    plane = cq.Face.makePlane(size, size, cq.Vector(*origin), cq.Vector(*normals[axis]))
    cut = shape.intersect(plane)
    return _edge_paths(cut, axis)


def _edge_paths(shape, axis):
    from .geometry import Point, PolylineEntity

    axes = {"Z": (0, 1), "Y": (0, 2), "X": (1, 2)}[axis]
    result = []
    for edge in shape.Edges():
        samples = (
            edge.sample(64)[0]
            if edge.geomType() != "LINE"
            else [edge.startPoint(), edge.endPoint()]
        )
        pts = [Point(tuple(v)[axes[0]], tuple(v)[axes[1]]) for v in samples]
        if len(pts) >= 2:
            result.append(PolylineEntity(pts, closed=False))
    return result


def elevation_paths(doc, key, view="Front"):
    if view not in ("Top", "Front", "Right"):
        raise ValueError("Choose Top, Front or Right")
    return _edge_paths(
        get_shape(doc, key), {"Top": "Z", "Front": "Y", "Right": "X"}[view]
    )


def place_view(doc, paths, key, view, position=(0, 0), linked=True):
    from .geometry import BlockDefinition, BlockReferenceEntity, Point
    from .document import AddEntityCommand
    from .architecture import BlockInstallCommand

    if not paths:
        raise ValueError("No edges intersect the section plane")
    from .validation import finite
    if len(position) != 2:
        raise ValueError('View position needs x,y')
    for v in position: finite(v, 'View position')
    link = None
    if linked:
        from .connected_models import view_signature
        import re
        section = re.fullmatch(r'Section ([XYZ])=([-+0-9.eE]+)', view)
        if not section and view not in ('Top', 'Front', 'Right'):
            raise ValueError('Linked view must be Top/Front/Right or Section X/Y/Z=offset')
        link = dict(source=key, type='section' if section else 'elevation',
                    axis=section.group(1) if section else {'Top':'Z','Front':'Y','Right':'X'}[view],
                    offset=float(section.group(2)) if section else 0,
                    view='Front' if section else view, fingerprint='0'*64)
        link['fingerprint'] = view_signature(doc, link)
    name = "VIEW_" + uuid.uuid4().hex[:10]
    block = BlockDefinition(name, paths)
    doc.undo_stack.beginMacro("Generated " + view)
    try:
        doc.undo_stack.push(BlockInstallCommand(doc, block))
        insert = BlockReferenceEntity(
            name, Point(*position), layer=doc.layers.current_layer
        )
        doc.undo_stack.push(AddEntityCommand(doc, insert, "Generated view"))
        edit_table(
            doc,
            "views",
            insert.id,
            dict(source=key, view=view, block=name),
            "View source",
        )
        if link:
            for i, path in enumerate(paths):
                path.id = uuid.uuid5(uuid.NAMESPACE_URL, insert.id + '/view/' + str(i)).hex
                path.layer = insert.layer
            edit_table(doc, 'view_links', insert.id, link, 'Link generated view')

    finally:
        doc.undo_stack.endMacro()
    return insert


def export_solid(doc, key, path):
    from .native_io import atomic_write

    shape = get_shape(doc, key)
    cq = kernel()
    atomic_write(path, lambda filename: cq.exporters.export(shape, filename))


def solid_dialog(mw):
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import (
        QDialog,
        QVBoxLayout,
        QHBoxLayout,
        QListWidget,
        QListWidgetItem,
        QAbstractItemView,
        QPushButton,
        QInputDialog,
        QFileDialog,
        QMessageBox,
        QLabel,
    )

    doc = mw.document
    d = QDialog(mw)
    d.setWindowTitle("Solid model tools")
    d.resize(560, 380)
    root = QVBoxLayout(d)
    root.addWidget(
        QLabel(
            "Choose solids in order. The first selected item is the subtraction base. Sources are retained."
        )
    )
    items = QListWidget()
    items.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
    root.addWidget(items)

    def refresh():
        items.clear()
        for key, name in [(f["id"], f["name"]) for f in doc.extrusions] + [
            (k, r["name"] + " · " + r["operation"])
            for k, r in doc.extensions.get("solids", {}).items()
        ]:
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, key)
            items.addItem(item)

    def selected():
        return [
            items.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(items.count())
            if items.item(i).isSelected()
        ]

    def operate(op):
        try:
            keys = selected()
            if op in ("union", "subtract", "intersect"):
                boolean(doc, keys, op)
            elif op == "delete":
                if not keys:
                    raise ValueError("Select a saved solid")
                doc.undo_stack.beginMacro("Delete solids")
                for key in keys:
                    if key in doc.extensions.get("solids", {}):
                        edit_table(doc, "solids", key, None, "Delete solid")
                    else:
                        from .model3d import ExtrusionCommand

                        doc.undo_stack.push(
                            ExtrusionCommand(
                                doc,
                                [f for f in doc.extrusions if f["id"] != key],
                                "Delete extrusion",
                            )
                        )
                doc.undo_stack.endMacro()
            elif op == "export":
                if len(keys) != 1:
                    raise ValueError("Select one solid")
                path, _ = QFileDialog.getSaveFileName(
                    d, "Export solid", "solid.step", "STEP (*.step);;STL (*.stl)"
                )
                if path:
                    export_solid(doc, keys[0], path)
            elif op == 'detach':
                if not keys: raise ValueError('Select a linked wall model')
                doc.undo_stack.beginMacro('Detach wall models')
                for key in keys:
                    edit_table(doc, 'wall_models', key, None, 'Detach wall model')
                doc.undo_stack.endMacro()
            else:
                if len(keys) != 1:
                    raise ValueError("Select one solid or extrusion")
                if op == "section":
                    axis, ok = QInputDialog.getItem(
                        d, "Section", "Normal axis", ["Z", "Y", "X"], editable=False
                    )
                    if not ok:
                        return
                    offset, ok = QInputDialog.getDouble(
                        d, "Section", "Plane position", 0, -1e9, 1e9, 3
                    )
                    if not ok:
                        return
                    paths = section_paths(doc, keys[0], axis, offset)
                    view = f"Section {axis}={offset:g}"
                else:
                    view, ok = QInputDialog.getItem(
                        d,
                        "Elevation",
                        "View",
                        ["Front", "Right", "Top"],
                        editable=False,
                    )
                    if not ok:
                        return
                    paths = elevation_paths(doc, keys[0], view)
                text, ok = QInputDialog.getText(
                    d, "Place view", "Insertion point x,y", text="0,0"
                )
                if ok:
                    place_view(
                        doc, paths, keys[0], view, tuple(map(float, text.split(",")))
                    )
            refresh()
            mw.refresh_document_ui()
        except Exception as ex:
            QMessageBox.warning(d, "Solid operation", str(ex))

    for labels in [
        [("Union", "union"), ("Subtract", "subtract"), ("Intersect", "intersect")],
        [
            ("Section", "section"),
            ("Elevation", "elevation"),
            ("Export", "export"),
            ("Delete", "delete"),
            ("Detach", "detach"),
        ],
    ]:
        bar = QHBoxLayout()
        root.addLayout(bar)
        for label, op in labels:
            b = QPushButton(label)
            b.clicked.connect(lambda _, o=op: operate(o))
            bar.addWidget(b)
    b = QPushButton("Open 3D views")
    b.clicked.connect(lambda: (d.accept(), mw.open_model_workspace()))
    root.addWidget(b)
    refresh()
    d.exec()


def profile_operation(mw, op):
    from PyQt6.QtWidgets import QInputDialog

    items = mw.canvas.selected_entities
    if len(items) != 1 or items[0] not in mw.document.editable_entities():
        raise ValueError("Select one editable profile or path")
    if op == "revolve":
        axis, ok = QInputDialog.getItem(
            mw, "Revolve", "Axis through origin", ["Y", "X"], editable=False
        )
        if not ok:
            return
        angle, ok = QInputDialog.getDouble(
            mw, "Revolve", "Angle (degrees)", 360, 0.001, 360, 3
        )
        if ok:
            revolve(mw.document, items[0], axis, angle)
    else:
        radius, ok = QInputDialog.getDouble(
            mw, "Sweep", "Circular section radius", 10, 0.001, 1e9, 3
        )
        if ok:
            sweep(mw.document, items[0], radius)
    mw.open_model_workspace()


def mesh_boundary_wires(record):
    """Suppress coplanar triangle diagonals in the shaded software display."""
    from .model3d import cross, dot, unit

    vertices = record["vertices"]
    adjacent = {}
    for face in record["faces"]:
        pts = [vertices[i] for i in face]
        normal = cross(
            tuple(pts[1][i] - pts[0][i] for i in range(3)),
            tuple(pts[2][i] - pts[0][i] for i in range(3)),
        )
        if dot(normal, normal) < 1e-20:
            continue
        normal = unit(normal)
        for a, b in zip(pts, pts[1:] + pts[:1]):
            key = tuple(sorted(tuple(round(v, 7) for v in p) for p in (a, b)))
            entry = adjacent.setdefault(key, {"a": a, "b": b, "normals": []})
            entry["normals"].append(normal)
    result = []
    for entry in adjacent.values():
        normals = entry["normals"]
        if len(normals) == 1 or any(
            abs(dot(normals[0], other)) < 0.985 for other in normals[1:]
        ):
            result.append((entry["a"], entry["b"]))
    return result
