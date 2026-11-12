"""Precise curve editing and exact line/arc topology operations."""

import math
from .geometry import (
    Point,
    PolylineEntity,
    SplineEntity,
    HatchEntity,
    LineEntity,
    CircleEntity,
)
from .document import SetAttrCommand, AddEntityCommand, DeleteEntitiesCommand


def edit_curve(mw):
    from PyQt6.QtWidgets import QInputDialog

    items = mw.canvas.selected_entities
    if len(items) != 1 or items[0] not in mw.document.editable_entities():
        raise ValueError("Select one editable polyline or spline")
    e = items[0]
    doc = mw.document
    if isinstance(e, PolylineEntity):
        text, ok = QInputDialog.getText(
            mw,
            "Circular polyline segments",
            "Bulge per vertex (comma-separated); 0=line, 1=semicircle, tan(angle/4)=arc",
            text=",".join(str(v) for v in e.bulges),
        )
        if not ok:
            return
        values = [float(v) for v in text.split(",")]
        from .precision import validate_bulges

        validate_bulges(e.points, values, e.closed)
        doc.undo_stack.push(
            SetAttrCommand(doc, e, "bulges", e.bulges, values, "Edit circular segments")
        )
    elif isinstance(e, SplineEntity):
        text, ok = QInputDialog.getMultiLineText(
            mw,
            "B-spline controls",
            "Mode: fit or nurbs. NURBS uses stored vertices as control points. Optional knots and positive weights.",
            f"mode={e.curve_mode}\ndegree={e.degree}\nweights="
            + ",".join(str(v) for v in e.weights)
            + "\nknots="
            + ",".join(str(v) for v in e.knots),
        )
        if not ok:
            return
        values = {k: v for k, v in (line.split("=", 1) for line in text.splitlines())}
        if set(values) != {"mode", "degree", "weights", "knots"}:
            raise ValueError("Use the four displayed fields")
        degree = int(values["degree"])
        weights = [float(v) for v in values["weights"].split(",") if v.strip()]
        knots = [float(v) for v in values["knots"].split(",") if v.strip()]
        candidate = SplineEntity(
            e.points,
            e.closed,
            degree=degree,
            weights=weights,
            knots=knots,
            curve_mode=values["mode"],
        )
        doc.undo_stack.beginMacro("Edit B-spline")
        for k in ("degree", "knots", "weights", "curve_mode"):
            doc.undo_stack.push(
                SetAttrCommand(
                    doc, e, k, getattr(e, k), getattr(candidate, k), "Edit B-spline"
                )
            )
        doc.undo_stack.endMacro()
    else:
        raise ValueError("Select a polyline or spline")


def hatch_with_islands(mw):
    from .hatch_ui import create_hatch
    return create_hatch(mw)


def _support_intersections(a, b):
    from .geom_ops import (
        line_line_intersection,
        circle_line_intersections,
        circle_circle_intersections,
    )

    if isinstance(a, LineEntity) and isinstance(b, LineEntity):
        p = line_line_intersection(a.p1, a.p2, b.p1, b.p2)
        return [p] if p else []
    if isinstance(a, LineEntity):
        return circle_line_intersections(b.center, b.radius, a.p1, a.p2)
    if isinstance(b, LineEntity):
        return circle_line_intersections(a.center, a.radius, b.p1, b.p2)
    return circle_circle_intersections(a.center, a.radius, b.center, b.radius)


def offset_curved(poly, distance, side_point):
    from .precision import arc_data, segment_point
    from .geom_ops import point_in_polygon

    if not math.isfinite(distance) or distance <= 0:
        raise ValueError("Offset distance must be positive")
    edges = list(
        zip(poly.points, poly.points[1:] + ([poly.points[0]] if poly.closed else []))
    )
    data = [arc_data(a, b, poly.bulges[i]) for i, (a, b) in enumerate(edges)]
    index = min(
        range(len(edges)),
        key=lambda i: side_point.distance_to(
            segment_point(*edges[i], poly.bulges[i], 0.5)
        ),
    )
    a, b = edges[index]
    m = segment_point(a, b, poly.bulges[index], 0.5)
    tangent = (b.x - a.x, b.y - a.y)
    if data[index]:
        c, _, _, sweep = data[index]
        sign = 1 if sweep > 0 else -1
        tangent = (-(m.y - c.y) * sign, (m.x - c.x) * sign)
    side = (
        1
        if tangent[0] * (side_point.y - m.y) - tangent[1] * (side_point.x - m.x) >= 0
        else -1
    )
    if poly.closed:
        samples = poly.sample_points()
        signed_area = 0
        for (a, b), arc in zip(edges, data):
            signed_area += (a.x * b.y - b.x * a.y) / 2
            if arc:
                signed_area += arc[1] ** 2 * (arc[3] - math.sin(arc[3])) / 2
        orientation = 1 if signed_area > 0 else -1
        side = orientation if point_in_polygon(side_point, samples) else -orientation
    offset = []
    starts = []
    ends = []
    for (a, b), arc in zip(edges, data):
        if arc:
            c, r, start, sweep = arc
            new_r = r - side * distance * (1 if sweep > 0 else -1)
            if new_r <= 1e-9:
                raise ValueError("Offset collapses a circular segment")
            start_p = Point(
                c.x + new_r * math.cos(start), c.y + new_r * math.sin(start)
            )
            end_p = Point(
                c.x + new_r * math.cos(start + sweep),
                c.y + new_r * math.sin(start + sweep),
            )
            offset.append(CircleEntity(c, new_r))
            starts.append(start_p)
            ends.append(end_p)
        else:
            length = a.distance_to(b)
            if length < 1e-9:
                raise ValueError("Remove zero-length segments")
            dx = -(b.y - a.y) * side * distance / length
            dy = (b.x - a.x) * side * distance / length
            start_p = Point(a.x + dx, a.y + dy)
            end_p = Point(b.x + dx, b.y + dy)
            offset.append(LineEntity(start_p, end_p))
            starts.append(start_p)
            ends.append(end_p)
    for i in range(len(offset) if poly.closed else len(offset) - 1):
        j = (i + 1) % len(offset)
        candidates = _support_intersections(offset[i], offset[j])
        if not candidates:
            if ends[i].distance_to(starts[j]) < 1e-7:
                joint = ends[i]
            else:
                raise ValueError("Offset has a gap; these supports cannot be joined")
        else:
            joint = min(
                candidates,
                key=lambda p: p.distance_to(ends[i]) + p.distance_to(starts[j]),
            )
        if joint.distance_to(poly.points[j]) > 20 * distance:
            raise ValueError("Offset joint exceeds the miter limit")
        ends[i] = starts[j] = joint
    pts = list(starts) + ([] if poly.closed else [ends[-1]])
    bulges = []
    for i, arc in enumerate(data):
        if arc:
            c = offset[i].center
            angle0 = math.atan2(starts[i].y - c.y, starts[i].x - c.x)
            angle1 = math.atan2(ends[i].y - c.y, ends[i].x - c.x)
            sweep = (
                (angle1 - angle0) % math.tau
                if arc[3] > 0
                else -((angle0 - angle1) % math.tau)
            )
            if abs(sweep) < 1e-9 or abs(sweep) > math.tau - 1e-9:
                raise ValueError("Offset circular segment collapsed")
            bulges.append(math.tan(sweep / 4))
        else:
            a, b = edges[i]
            if (b.x - a.x) * (ends[i].x - starts[i].x) + (b.y - a.y) * (
                ends[i].y - starts[i].y
            ) <= 1e-9:
                raise ValueError("Offset reverses a segment")
            bulges.append(0)
    if not poly.closed:
        bulges.append(0)
    result = PolylineEntity(pts, poly.closed, bulges=bulges, width=poly.width, **poly.style_kwargs())
    # Reject topology splits/self crossings rather than returning corrupt loops.
    from .precision import polyline_parts
    from .geom_ops import angle_in_arc_range, point_on_segment_param

    parts = polyline_parts(result)

    def on(part, p):
        if isinstance(part, LineEntity):
            return -1e-9 <= point_on_segment_param(part.p1, part.p2, p) <= 1 + 1e-9
        return angle_in_arc_range(
            math.degrees(math.atan2(p.y - part.center.y, p.x - part.center.x)),
            part.start_angle,
            part.end_angle,
        )

    for i, part in enumerate(parts):
        for j in range(i + 2, len(parts)):
            if poly.closed and i == 0 and j == len(parts) - 1:
                continue
            if any(
                on(part, p) and on(parts[j], p)
                for p in _support_intersections(part, parts[j])
            ):
                raise ValueError("Offset would intersect itself")
    return result


def trim_polyline(tool, target, click):
    """Split at exact curve parameters, remove the picked interval, preserve bulges."""
    from .precision import arc_data, segment_point, polyline_parts
    from .geom_ops import distance_to_entity, point_on_segment_param, bracket_range

    parts = polyline_parts(target)
    index = min(range(len(parts)), key=lambda i: distance_to_entity(click, parts[i]))
    edges = list(
        zip(
            target.points,
            target.points[1:] + ([target.points[0]] if target.closed else []),
        )
    )
    a, b = edges[index]
    bulge = target.bulges[index]
    arc = arc_data(a, b, bulge)
    if arc:
        c, r, start, sweep = arc
        raw = tool._circle_boundary_intersections(c, r)

        def param(p):
            angle = math.atan2(p.y - c.y, p.x - c.x)
            return (
                ((angle - start) % math.tau) / sweep
                if sweep > 0
                else -((start - angle) % math.tau) / sweep
            )
    else:
        raw = tool._line_boundary_intersections(a, b)

        def param(p):
            return point_on_segment_param(a, b, p)

    cuts = [t for t in (param(p) for p in raw) if 1e-9 < t < 1 - 1e-9]
    if not cuts:
        return
    low, high = bracket_range(0, 1, param(click), cuts)
    segments = []
    for i, (p, q) in enumerate(edges):
        if i != index:
            segments.append((p, q, target.bulges[i]))
        else:
            if low > 1e-9:
                segments.append(
                    (
                        p,
                        segment_point(a, b, bulge, low),
                        math.tan(arc[3] * low / 4) if arc else 0,
                    )
                )
            segments.append(None)
            if high < 1 - 1e-9:
                segments.append(
                    (
                        segment_point(a, b, bulge, high),
                        q,
                        math.tan(arc[3] * (1 - high) / 4) if arc else 0,
                    )
                )
    split = segments.index(None)
    groups = [segments[:split], segments[split + 1 :]]
    if target.closed:
        groups = [groups[1] + groups[0]]
    replacements = []
    for group in groups:
        if not group:
            continue
        points = [s[0] for s in group] + [group[-1][1]]
        values = [s[2] for s in group] + [0]
        replacements.append(
            PolylineEntity(points, False, bulges=values, width=target.width, **target.style_kwargs())
        )
    doc = tool.document
    doc.undo_stack.beginMacro("Trim curved polyline")
    doc.undo_stack.push(DeleteEntitiesCommand(doc, [target], "Trim source"))
    for e in replacements:
        doc.undo_stack.push(AddEntityCommand(doc, e, "Trim result"))
    doc.undo_stack.endMacro()
