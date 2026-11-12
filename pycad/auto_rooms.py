"""Enclosed room detection from joined wall footprints; linked room boundaries."""

from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QPainterPath
from .wall_joining import frames, path_for
from .geometry import Point, PolylineEntity
from .document import AddEntityCommand
from .feature_data import edit_table


def validate_rooms(table, levels):
    from .validation import name, finite

    for key, r in table.items():
        name(key, "Automatic room")
        if (
            not isinstance(r, dict)
            or set(r) != {"walls", "boundary", "seed", "level"}
            or r["level"] not in levels
        ):
            raise ValueError("Invalid automatic room link")
        if not isinstance(r["walls"], list) or not 3 <= len(r["walls"]) <= 2000:
            raise ValueError("Automatic room needs 3–2000 source walls")
        for source in r["walls"]:
            name(source, "Room wall")
        name(r["boundary"], "Room boundary")
        if not isinstance(r["seed"], list) or len(r["seed"]) != 2:
            raise ValueError("Invalid room seed")
        for p in r["seed"]:
            finite(p, "Room seed")


def enclosed(doc, level=None, wall_ids=None):
    from .building import current_level, level_for
    from .building_geometry import polygon_area

    level = level or current_level(doc)
    candidates = {
        k: f
        for k, f in frames(doc).items()
        if level_for(doc, k) == level and (wall_ids is None or k in wall_ids)
    }
    union = QPainterPath()
    for f in candidates.values():
        union = union.united(path_for(f["polygon"]))
    loops = []
    for poly in union.toSubpathPolygons():
        pts = [[p.x(), p.y()] for p in poly]
        if pts and pts[0] == pts[-1]:
            pts.pop()
        # Qt's boolean path result can retain a collinear backtracking spike
        # at unequal-width T junctions. It has zero area but fails polygon
        # validation. Remove redundant vertices without changing enclosed area.
        extent = max((abs(v) for p in pts for v in p), default=1)
        tolerance = max(1e-9, extent * 1e-10)
        changed = True
        while changed and len(pts) > 3:
            changed = False
            for i, b in enumerate(pts):
                a, c = pts[i - 1], pts[(i + 1) % len(pts)]
                length = ((c[0] - a[0]) ** 2 + (c[1] - a[1]) ** 2) ** 0.5
                cross = abs(
                    (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
                )
                if length <= tolerance or cross <= tolerance * length:
                    pts.pop(i)
                    changed = True
                    break
        if len(pts) >= 3 and polygon_area(pts) > 1e-8:
            signed = sum(
                a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1])
            )
            loops.append((pts, signed))
    if not loops:
        return []
    outside = max(loops, key=lambda p: abs(p[1]))[1]
    return [pts for pts, signed in loops if signed * outside < 0]


def seed_for(points):
    path = path_for(points)
    # A triangle fan supplies interior points for concave rooms, too.
    for a, b, c in zip(points, points[1:] + points[:1], points[2:] + points[:2]):
        p = [(a[0] + b[0] + c[0]) / 3, (a[1] + b[1] + c[1]) / 3]
        if path.contains(QPointF(*p)):
            return p
    raise ValueError("Unable to locate a room interior")


def detect_rooms(doc, level=None, name="Room", finish="Paint"):
    from .building import current_level, level_for
    from .architecture import create_room

    level = level or current_level(doc)
    polygons = enclosed(doc, level)
    if not polygons:
        raise ValueError("No enclosed wall spaces found on this level")
    from .building_geometry import validate_profile

    for polygon in polygons:
        validate_profile(polygon)
    existing = [
        r["seed"]
        for key, r in doc.extensions.get("auto_rooms", {}).items()
        if doc.find_by_id(key) and r["level"] == level
    ]
    wall_ids = [k for k in frames(doc) if level_for(doc, k) == level]
    new = []
    doc.undo_stack.beginMacro("Detect linked rooms")
    try:
        for pts in polygons:
            if any(path_for(pts).contains(QPointF(*p)) for p in existing):
                continue
            boundary = PolylineEntity(
                [Point(*p) for p in pts], True, layer=doc.layers.current_layer
            )
            doc.undo_stack.push(
                AddEntityCommand(doc, boundary, "Automatic room boundary")
            )
            room = create_room(
                doc,
                boundary,
                name,
                str(101 + len(doc.extensions.get("auto_rooms", {}))),
                finish,
            )
            edit_table(
                doc,
                "auto_rooms",
                room.id,
                dict(
                    walls=wall_ids,
                    boundary=boundary.id,
                    seed=seed_for(pts),
                    level=level,
                ),
                "Link room to walls",
            )
            edit_table(
                doc, "level_assignments", room.id, {"level": level}, "Room level"
            )
            edit_table(
                doc,
                "level_assignments",
                boundary.id,
                {"level": level},
                "Room boundary level",
            )
            new.append(room)
    finally:
        doc.undo_stack.endMacro()
    return new


def sync_rooms(doc):
    doc.room_link_status = {}
    cache = {}
    for key, r in doc.extensions.get("auto_rooms", {}).items():
        if not doc.find_by_id(key):
            continue
        boundary = doc.find_by_id(r["boundary"])
        if not isinstance(boundary, PolylineEntity):
            doc.room_link_status[key] = "Stale room: boundary missing"
            continue
        scope = (r["level"], tuple(r["walls"]))
        if scope not in cache:
            cache[scope] = enclosed(doc, r["level"], r["walls"])
        polygons = cache[scope]
        match = next(
            (p for p in polygons if path_for(p).contains(QPointF(*r["seed"]))), None
        )
        if match is None:
            doc.room_link_status[key] = "Stale room: walls no longer enclose its seed"
            continue
        boundary.points = [Point(*p) for p in match]
        boundary.closed = True
        boundary.bulges = [0.0] * len(match)
        doc.room_link_status[key] = "Current"
