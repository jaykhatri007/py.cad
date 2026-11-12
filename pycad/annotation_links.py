"""Bounded annotation source geometry; failed links retain their last snapshot."""

import math
from .geometry import Point, LineEntity, ArcEntity, CircleEntity, PointEntity


def line_angle_geometry(first, second, directions=(1, 1)):
    """Intersection of the infinite supporting lines and their directed rays."""
    if first.kind != "LINE" or second.kind != "LINE" or first is second:
        raise ValueError("Choose two different LINE entities")
    vectors = []
    for line in (first, second):
        dx, dy = line.p2.x - line.p1.x, line.p2.y - line.p1.y
        length = math.hypot(dx, dy)
        if length <= 1e-12:
            raise ValueError("An angular source line has zero length")
        vectors.append((dx / length, dy / length, length))
    ax, ay, _ = vectors[0]
    bx, by, _ = vectors[1]
    cross = ax * by - ay * bx
    if abs(cross) <= 1e-10:
        raise ValueError("Lines are parallel or too nearly parallel to dimension")
    dx, dy = second.p1.x - first.p1.x, second.p1.y - first.p1.y
    distance = (dx * by - dy * bx) / cross
    center = Point(first.p1.x + distance * ax, first.p1.y + distance * ay)
    rays = [
        Point(center.x + sign * x * length, center.y + sign * y * length)
        for (x, y, length), sign in zip(vectors, directions)
    ]
    if any(
        not math.isfinite(v) or abs(v) > 1e12
        for p in (center, *rays)
        for v in p.as_tuple()
    ):
        raise ValueError(
            "Angular intersection is outside the supported coordinate range"
        )
    return center, *rays


def line_angle_sector(first, second, location):
    """Choose one of the four adjacent sectors using the dimension placement."""
    center, p1, p2 = line_angle_geometry(first, second)
    if center.distance_to(location) <= 1e-12:
        raise ValueError("Place the dimension arc away from the intersection")
    rays = []
    for line, point in ((first, p1), (second, p2)):
        angle = math.atan2(point.y - center.y, point.x - center.x) % math.tau
        rays.extend(((angle, line, 1), ((angle + math.pi) % math.tau, line, -1)))
    rays.sort(key=lambda r: r[0])
    placement = math.atan2(location.y - center.y, location.x - center.x) % math.tau
    for index, start in enumerate(rays):
        end = rays[(index + 1) % 4]
        if (placement - start[0]) % math.tau < (end[0] - start[0]) % math.tau:
            lines, signs = (start[1], end[1]), (start[2], end[2])
            return (
                *line_angle_geometry(*lines, signs),
                [l.id for l in lines],
                list(signs),
            )
    raise ValueError("Place the dimension inside an angle sector")


def anchor_point(entity, anchor):
    """Resolve an endpoint, point or circular center in model space."""
    if type(entity) is LineEntity and anchor in ("p1", "p2"):
        return getattr(entity, anchor)
    if isinstance(entity, PointEntity) and anchor == "point":
        return entity.point
    if isinstance(entity, (CircleEntity, ArcEntity)) and anchor == "center":
        return entity.center
    raise ValueError("Source anchor is missing or unsupported")


def pick_anchor(document, point, tolerance):
    choices = []
    for entity in document.visible_entities():
        anchors = (
            ("p1", "p2")
            if type(entity) is LineEntity
            else (
                ("point",)
                if isinstance(entity, PointEntity)
                else (
                    ("center",) if isinstance(entity, (CircleEntity, ArcEntity)) else ()
                )
            )
        )
        for anchor in anchors:
            p = anchor_point(entity, anchor)
            distance = point.distance_to(p)
            if distance <= tolerance:
                choices.append((distance, entity.id, anchor, p))
    if not choices:
        return None
    _, source, anchor, p = min(choices, key=lambda c: c[0])
    return Point(p.x, p.y), source, anchor
