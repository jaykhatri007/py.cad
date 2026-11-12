"""Persistent independent extrusion features and a software orthographic camera."""

import copy
import math
import uuid
from PyQt6.QtGui import QUndoCommand
from .geometry import Point, CircleEntity, PolylineEntity


class ExtrusionCommand(QUndoCommand):
    def __init__(self, document, after, description="3D extrusion"):
        super().__init__(description)
        self.doc = document
        self.before = copy.deepcopy(document.extrusions)
        self.after = copy.deepcopy(after)

    def redo(self):
        self.doc.extrusions = copy.deepcopy(self.after)

    def undo(self):
        self.doc.extrusions = copy.deepcopy(self.before)


def validate_feature(feature, layers):
    from .validation import finite, name

    if not isinstance(feature, dict) or set(feature) != {
        "id",
        "name",
        "layer",
        "height",
        "profile",
    }:
        raise ValueError("Invalid 3D feature record")
    name(feature["id"], "Feature ID")
    name(feature["name"], "Feature name")
    if feature["layer"] not in layers:
        raise ValueError("3D feature references a missing layer")
    finite(feature["height"], "Extrusion height")
    if feature["height"] == 0:
        raise ValueError("Extrusion height must be nonzero")
    profile = feature["profile"]
    if not isinstance(profile, dict):
        raise ValueError("Invalid extrusion profile")
    if profile.get("kind") == "CIRCLE" and set(profile) == {"kind", "center", "radius"}:
        if not isinstance(profile["center"], list) or len(profile["center"]) != 2:
            raise ValueError("Invalid circle center")
        for v in profile["center"]:
            finite(v, "Center")
        finite(profile["radius"], "Radius", True)
    elif profile.get("kind") == "POLYGON" and set(profile) == {"kind", "points"}:
        points = profile["points"]
        if not isinstance(points, list) or not 3 <= len(points) <= 2000:
            raise ValueError("Extrusion profile needs 3–2000 vertices")
        for p in points:
            if not isinstance(p, list) or len(p) != 2:
                raise ValueError("Invalid profile point")
            for v in p:
                finite(v, "Profile coordinate")
        # Reject degenerate/self-intersecting contours before storing a solid.
        from .geom_ops import line_line_intersection, point_segment_distance

        pts = [Point(*p) for p in points]
        edges = list(zip(pts, pts[1:] + pts[:1]))
        if any(a.distance_to(b) < 1e-9 for a, b in edges):
            raise ValueError("Profile contains a zero-length edge")
        area = (
            sum(
                (a.x - pts[0].x) * (b.y - pts[0].y)
                - (b.x - pts[0].x) * (a.y - pts[0].y)
                for a, b in edges
            )
            / 2
        )
        if abs(area) < 1e-9:
            raise ValueError("Profile has zero area")
        for i, (a, b) in enumerate(edges):
            for j in range(i + 1, len(edges)):
                if j == i + 1 or (i == 0 and j == len(edges) - 1):
                    continue
                c, d = edges[j]
                if (
                    line_line_intersection(a, b, c, d, segment_only=True) is not None
                    or min(
                        point_segment_distance(a, c, d),
                        point_segment_distance(b, c, d),
                        point_segment_distance(c, a, b),
                        point_segment_distance(d, a, b),
                    )
                    < 1e-9
                ):
                    raise ValueError(
                        "Self-intersecting extrusion profiles are not supported"
                    )
    else:
        raise ValueError("Unsupported extrusion profile")
    return feature


def create_extrusion(document, entity, height):
    if len(document.extrusions) >= 1000:
        raise ValueError("Maximum 1,000 saved extrusions per drawing")
    if document.layers.is_locked(entity.layer):
        raise ValueError("Unlock the profile layer before extruding")
    if isinstance(entity, CircleEntity):
        profile = dict(
            kind="CIRCLE",
            center=[entity.center.x, entity.center.y],
            radius=entity.radius,
        )
    elif isinstance(entity, PolylineEntity) and entity.closed:
        points = [[p.x, p.y] for p in entity.points]
        if len(points) > 3 and points[0] == points[-1]:
            points.pop()
        profile = dict(kind="POLYGON", points=points)
    else:
        raise ValueError("Select a circle, rectangle, or simple closed polyline")
    feature = dict(
        id=uuid.uuid4().hex,
        name=f"Extrusion {len(document.extrusions) + 1}",
        layer=entity.layer,
        height=height,
        profile=profile,
    )
    validate_feature(feature, document.layers.layers)
    document.undo_stack.push(
        ExtrusionCommand(document, document.extrusions + [feature])
    )
    return feature


def profile_entity(feature):
    p = feature["profile"]
    if p["kind"] == "CIRCLE":
        return CircleEntity(Point(*p["center"]), p["radius"], layer=feature["layer"])
    return PolylineEntity(
        [Point(*v) for v in p["points"]], closed=True, layer=feature["layer"]
    )


def feature_mesh(feature):
    p = feature["profile"]
    if p["kind"] == "CIRCLE":
        cx, cy = p["center"]
        r = p["radius"]
        ring = [
            (cx + r * math.cos(i * math.tau / 72), cy + r * math.sin(i * math.tau / 72))
            for i in range(72)
        ]
    else:
        ring = list(p["points"])
    area = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(ring, ring[1:] + ring[:1]))
    if area < 0:
        ring = list(reversed(ring))
    vertices = [(x, y, z) for z in (0, feature["height"]) for x, y in ring]
    n = len(ring)
    faces = [list(range(n - 1, -1, -1)), list(range(n, 2 * n))]
    faces += [[i, (i + 1) % n, (i + 1) % n + n, i + n] for i in range(n)]
    if feature["height"] < 0:
        faces = [list(reversed(face)) for face in faces]
    return vertices, faces


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def unit(v):
    length = math.sqrt(dot(v, v))
    return tuple(x / length for x in v)


class Camera:
    """Right/up/back orthonormal basis; roll is retained during free orbit."""

    PRESETS = {
        "Top": ((1, 0, 0), (0, 1, 0)),
        "Bottom": ((-1, 0, 0), (0, 1, 0)),
        "Front": ((1, 0, 0), (0, 0, 1)),
        "Back": ((-1, 0, 0), (0, 0, 1)),
        "Right": ((0, 1, 0), (0, 0, 1)),
        "Left": ((0, -1, 0), (0, 0, 1)),
        "Isometric": (
            (0.70710678, 0.70710678, 0),
            (-0.40824829, 0.40824829, 0.81649658),
        ),
    }

    def __init__(self, preset="Isometric"):
        self.center = (0, 0, 0)
        self.scale = 1.0
        self.pan = (0.0, 0.0)
        self.set_view(preset)

    def set_view(self, name):
        self.right, self.up = map(unit, self.PRESETS[name])
        self.back = unit(cross(self.right, self.up))
        self.name = name
        self.pan = (0, 0)

    def project(self, point):
        delta = tuple(p - c for p, c in zip(point, self.center))
        return dot(delta, self.right), dot(delta, self.up), dot(delta, self.back)

    def orbit(self, dx, dy):
        def rotate(v, axis, angle):
            c, s = math.cos(angle), math.sin(angle)
            cv = cross(axis, v)
            d = dot(axis, v)
            return tuple(v[i] * c + cv[i] * s + axis[i] * d * (1 - c) for i in range(3))

        for axis, angle in ((self.up, -dx * 0.008), (self.right, -dy * 0.008)):
            self.right = rotate(self.right, axis, angle)
            self.up = rotate(self.up, axis, angle)
        self.right = unit(self.right)
        self.back = unit(cross(self.right, self.up))
        self.up = unit(cross(self.back, self.right))
        self.name = "Free orbit"

    def fit(self, points, width, height):
        if not points:
            points = [(-50, -50, -50), (50, 50, 50)]
        self.center = tuple(
            (min(p[i] for p in points) + max(p[i] for p in points)) / 2
            for i in range(3)
        )
        projected = [self.project(p) for p in points]
        # Center the projected bounds too: asymmetric models need not project
        # symmetrically around the center of their world-space bounding box.
        mid = [(min(p[i] for p in projected) + max(p[i] for p in projected)) / 2
               for i in (0, 1)]
        self.center = tuple(self.center[i] + mid[0] * self.right[i] + mid[1] * self.up[i]
                            for i in range(3))
        extent = max(
            max(p[i] for p in points) - min(p[i] for p in points) for i in range(3)
        )
        w = max(
            max(p[0] for p in projected) - min(p[0] for p in projected),
            extent * 0.01,
            1e-6,
        )
        h = max(
            max(p[1] for p in projected) - min(p[1] for p in projected),
            extent * 0.01,
            1e-6,
        )
        self.scale = max(1e-10, min(max(width - 60, 1) / w, max(height - 70, 1) / h))
        self.pan = (0, 0)
