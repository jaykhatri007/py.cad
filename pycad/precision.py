"""Exact circular polyline segments, B-splines and even/odd hatch islands."""

import math
from .geometry import Point


def validate_bulges(points, bulges, closed):
    from .validation import finite

    if len(bulges) != len(points):
        raise ValueError("One bulge is required per vertex")
    for i, b in enumerate(bulges):
        finite(b, "Bulge")
        if abs(b) > 1e6:
            raise ValueError("Bulge magnitude must be at most 1,000,000")
        if (
            b
            and i < len(points) - (0 if closed else 1)
            and points[i].distance_to(points[(i + 1) % len(points)]) < 1e-9
        ):
            raise ValueError("An arc needs two different endpoints")
    if not closed and bulges and bulges[-1]:
        raise ValueError("The last open-path bulge must be zero")


def arc_data(a, b, bulge):
    chord = a.distance_to(b)
    if chord < 1e-12 or abs(bulge) < 1e-12:
        return None
    cx = (a.x + b.x) / 2 - (b.y - a.y) * (1 - bulge * bulge) / (4 * bulge)
    cy = (a.y + b.y) / 2 + (b.x - a.x) * (1 - bulge * bulge) / (4 * bulge)
    center = Point(cx, cy)
    return (
        center,
        center.distance_to(a),
        math.atan2(a.y - cy, a.x - cx),
        4 * math.atan(bulge),
    )


def segment_point(a, b, bulge, t):
    data = arc_data(a, b, bulge)
    if data is None:
        return Point(a.x + (b.x - a.x) * t, a.y + (b.y - a.y) * t)
    c, r, start, sweep = data
    angle = start + sweep * t
    return Point(c.x + r * math.cos(angle), c.y + r * math.sin(angle))


def polyline_parts(poly):
    from .geometry import LineEntity, ArcEntity

    parts = []
    for i, (a, b) in enumerate(
        zip(poly.points, poly.points[1:] + ([poly.points[0]] if poly.closed else []))
    ):
        data = arc_data(a, b, poly.bulges[i])
        if data:
            c, r, start, sweep = data
            if sweep < 0:
                start, sweep = start + sweep, -sweep
            parts.append(
                ArcEntity(
                    c,
                    r,
                    math.degrees(start),
                    math.degrees(start + sweep),
                    **poly.style_kwargs(),
                )
            )
        else:
            parts.append(
                LineEntity(Point(a.x, a.y), Point(b.x, b.y), **poly.style_kwargs())
            )
    return parts


def polyline_samples(poly, tolerance=None):
    result = []
    for i, (a, b) in enumerate(
        zip(poly.points, poly.points[1:] + ([poly.points[0]] if poly.closed else []))
    ):
        data = arc_data(a, b, poly.bulges[i])
        n = 1
        if data:
            _, r, _, sweep = data
            tol = tolerance or max(r * 1e-4, 1e-8)
            step = 2 * math.acos(max(-1, min(1, 1 - tol / r)))
            n = min(4096, max(2, math.ceil(abs(sweep) / max(step, 1e-4))))
        result.extend(segment_point(a, b, poly.bulges[i], j / n) for j in range(n))
    if poly.points:
        result.append(poly.points[0] if poly.closed else poly.points[-1])
    return result


def polyline_bounds(poly):
    points = list(poly.points)
    for i, (a, b) in enumerate(
        zip(poly.points, poly.points[1:] + ([poly.points[0]] if poly.closed else []))
    ):
        data = arc_data(a, b, poly.bulges[i])
        if not data:
            continue
        c, r, start, sweep = data
        for angle in (0, math.pi / 2, math.pi, math.pi * 1.5):
            t = (
                ((angle - start) % math.tau) / sweep
                if sweep > 0
                else -((start - angle) % math.tau) / sweep
            )
            if 0 <= t <= 1:
                points.append(
                    Point(c.x + r * math.cos(angle), c.y + r * math.sin(angle))
                )
    return (
        min(p.x for p in points),
        min(p.y for p in points),
        max(p.x for p in points),
        max(p.y for p in points),
    )


def polyline_measure(poly):
    length = area = 0
    for i, (a, b) in enumerate(
        zip(poly.points, poly.points[1:] + ([poly.points[0]] if poly.closed else []))
    ):
        data = arc_data(a, b, poly.bulges[i])
        area += (a.x * b.y - b.x * a.y) / 2
        if data:
            _, r, _, sweep = data
            length += r * abs(sweep)
            area += r * r * (sweep - math.sin(sweep)) / 2
        else:
            length += a.distance_to(b)
    return length, abs(area) if poly.closed else 0


def spline_curve(spline):
    from ezdxf.math import BSpline, global_bspline_interpolation
    from .validation import finite

    if len(spline.points) < 2:
        raise ValueError("A spline needs at least two points")
    if type(spline.degree) is not int or not 1 <= spline.degree <= min(
        5, len(spline.points) - 1
    ):
        raise ValueError("Spline degree must be 1–5 and below the point count")
    pts = [(p.x, p.y, 0) for p in spline.points]
    if spline.curve_mode == "fit":
        if spline.knots or spline.weights:
            raise ValueError("Fit splines do not store control knots or weights")
        if spline.closed and pts[-1] != pts[0]:
            pts.append(pts[0])
        return global_bspline_interpolation(pts, degree=spline.degree)
    if spline.curve_mode != "nurbs":
        raise ValueError("Spline mode must be fit or nurbs")
    if spline.knots:
        if len(spline.knots) != len(pts) + spline.degree + 1:
            raise ValueError("Invalid knot count")
        for k in spline.knots:
            finite(k, "Knot")
        if sorted(spline.knots) != spline.knots or spline.knots[-1] <= spline.knots[0]:
            raise ValueError("Knots must increase over a nonzero interval")
    if spline.weights:
        if len(spline.weights) != len(pts):
            raise ValueError("One weight is required per control point")
        for w in spline.weights:
            finite(w, "Weight", True)
    return BSpline(
        pts,
        order=spline.degree + 1,
        knots=spline.knots or None,
        weights=spline.weights or None,
    )


def validate_entity_extras(kind, e):
    from .validation import finite, point, name
    from .hatching import EXTRA_FIELDS

    fields = {
        "LWPOLYLINE": {"bulges"},
        "RECTANGLE": {"bulges"},
        "SPLINE": {"degree", "knots", "weights", "curve_mode"},
        "TEXT": {"rich_html", "wrap_width"},
        "HATCH": {"holes"} | EXTRA_FIELDS,
        "INSERT": {"attributes"},
    }.get(kind, set())
    if kind in ("LWPOLYLINE", "RECTANGLE") and "bulges" in e:
        if not isinstance(e["bulges"], list):
            raise ValueError("Bulges must be a list")
        pts = [Point(*p["point"]) for p in e["points"]]
        validate_bulges(pts, e["bulges"], e["closed"])
        from .geometry import PolylineEntity

        for value in PolylineEntity(pts, e["closed"], e["bulges"]).bbox():
            finite(value, "Curve extent")
    if kind == "SPLINE" and fields & set(e):
        from .geometry import SplineEntity

        SplineEntity(
            [Point(*p["point"]) for p in e["points"]],
            e["closed"],
            degree=e.get("degree", 3),
            knots=e.get("knots"),
            weights=e.get("weights"),
            curve_mode=e.get("curve_mode", "fit"),
        )
    if kind == "TEXT":
        finite(e.get("wrap_width", 0), "Text width")
        if e.get("wrap_width", 0) < 0:
            raise ValueError("Text width must not be negative")
        from .annotations_plus import validate_html

        validate_html(e.get("rich_html", ""))
    if kind == "INSERT":
        attrs = e.get("attributes", {})
        if not isinstance(attrs, dict) or len(attrs) > 256:
            raise ValueError("Invalid insert attributes")
        for k, v in attrs.items():
            name(k, "Attribute tag")
            if not isinstance(v, str) or len(v) > 10000:
                raise ValueError("Invalid attribute value")
    if kind == "HATCH":
        from .hatching import validate_options
        validate_options(e)
        holes = e.get("holes", [])
        if not isinstance(holes, list):
            raise ValueError("Invalid hatch islands")
        for hole in holes:
            if not isinstance(hole, list) or len(hole) < 3:
                raise ValueError("Invalid island polygon")
            for p in hole:
                point(p)
        if e.get("boundary_mode", "strict") == "strict":
            validate_holes(
                [Point(*p["point"]) for p in e["boundary"]],
                [[Point(*p["point"]) for p in hole] for hole in holes],
            )
    return fields


def validate_holes(boundary, holes):
    from .geom_ops import point_in_polygon, line_line_intersection

    def edges(pts):
        return list(zip(pts, pts[1:] + pts[:1]))

    outer = edges(boundary)
    previous = []
    for hole in holes:
        if not all(point_in_polygon(p, boundary) for p in hole):
            raise ValueError("An island must be inside its outer boundary")
        he = edges(hole)
        if any(
            line_line_intersection(a, b, c, d, True) for a, b in outer for c, d in he
        ):
            raise ValueError("An island touches or crosses the outer boundary")
        for other in previous:
            if (
                any(
                    line_line_intersection(a, b, c, d, True)
                    for a, b in edges(other)
                    for c, d in he
                )
            ):
                raise ValueError("Hatch islands must not cross or touch")
        previous.append(hole)


def draw_hatch(canvas, painter, hatch):
    from .hatching import paint
    return paint(canvas, painter, hatch)


def display_hatch_lines(canvas, hatch):
    """Visible hatch rows only; Qt clips these strokes to the polygon/islands."""
    from .geometry import Point
    angle = math.radians(hatch.angle)
    c, s = math.cos(angle), math.sin(angle)

    def rotate(p):
        return (p.x*c + p.y*s, -p.x*s + p.y*c)

    def unrotate(x, y):
        return Point(x*c-y*s, x*s+y*c)

    # Derive the inverse of the active transform. Paper-space viewports replace
    # world_to_screen while screen_to_world still describes the outer sheet.
    origin = canvas.world_to_screen(0, 0)
    px, py = canvas.world_to_screen(1, 0), canvas.world_to_screen(0, 1)
    ax, ay = px.x()-origin.x(), px.y()-origin.y()
    bx, by = py.x()-origin.x(), py.y()-origin.y()
    det = ax*by-ay*bx
    if not math.isfinite(det) or abs(det) < 1e-24:
        return
    def inverse(x, y):
        dx, dy = x-origin.x(), y-origin.y()
        return Point((dx*by-dy*bx)/det, (ax*dy-ay*dx)/det)
    corners = [inverse(x, y) for x, y in
               ((0, 0), (canvas.viewport().width(), 0),
                (0, canvas.viewport().height()),
                (canvas.viewport().width(), canvas.viewport().height()))]
    bounds = [rotate(p) for p in corners]
    xs, ys = zip(*bounds)
    base = min(rotate(p)[1] for p in hatch.boundary) + hatch.spacing/2
    start = math.ceil((min(ys)-base)/hatch.spacing)
    stop = math.floor((max(ys)-base)/hatch.spacing)
    # The pixel-density branch normally yields < 1,000 lines. This final cap
    # also protects unusual transforms or extremely large viewport dimensions.
    for i in range(start, min(stop+1, start+2048)):
        y = base + i*hatch.spacing
        yield unrotate(min(xs), y), unrotate(max(xs), y)
