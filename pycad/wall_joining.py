"""Mitered straight-wall footprints and exposed plan outlines.

The wall centre lines remain authoritative. Ordinary block geometry is derived
from their union, so drawing, Undo, PDF and DXF share the same joined outlines.
"""

import math
from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QPainterPath
from .geometry import Point, LineEntity, BlockReferenceEntity


def cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1])


def add(a, b, scale=1):
    return (a[0] + b[0] * scale, a[1] + b[1] * scale)


def distance(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def local_point(entity, point):
    theta = math.radians(entity.rotation)
    x, y = sub(point, entity.insertion_point.as_tuple())
    return Point(
        (x * math.cos(theta) + y * math.sin(theta)) / entity.scale,
        (-x * math.sin(theta) + y * math.cos(theta))
        / entity.scale
        * (-1 if entity.mirrored else 1),
    )


def world_point(entity, x, y):
    theta = math.radians(entity.rotation)
    x *= entity.scale
    y *= entity.scale * (-1 if entity.mirrored else 1)
    return (
        entity.insertion_point.x + x * math.cos(theta) - y * math.sin(theta),
        entity.insertion_point.y + x * math.sin(theta) + y * math.cos(theta),
    )


def projection(p, a, b):
    delta = sub(b, a)
    length2 = delta[0] ** 2 + delta[1] ** 2
    t = sum(x * y for x, y in zip(sub(p, a), delta)) / length2
    q = add(a, delta, min(1, max(0, t)))
    return t, distance(p, q)


def path_for(points):
    path = QPainterPath()
    path.setFillRule(Qt.FillRule.WindingFill)
    path.moveTo(*points[0])
    for p in points[1:]:
        path.lineTo(*p)
    path.closeSubpath()
    return path


def frames(doc):
    from .building import level_for
    result = {}
    for key, record in doc.extensions.get("architecture", {}).items():
        entity = doc.find_by_id(key)
        if record["kind"] != "wall" or not isinstance(entity, BlockReferenceEntity):
            continue
        a = world_point(entity, 0, 0)
        b = world_point(entity, record["length"], 0)
        length = distance(a, b)
        if length < 1e-12 or abs(entity.scale) < 1e-12:
            continue
        u = tuple(v / length for v in sub(b, a))
        n = (-u[1], u[0])
        h = record["width"] * abs(entity.scale) / 2
        result[key] = dict(
            entity=entity,
            record=record,
            a=a,
            b=b,
            u=u,
            n=n,
            h=h,
            polygon=[add(a, n, -h), add(b, n, -h), add(b, n, h), add(a, n, h)],
            neighbours=set(),
            level=level_for(doc, key),
        )
    if not result:
        return result
    tolerance = max(1e-8, min(f["h"] for f in result.values()) * 1e-6)
    for key, f in result.items():
        for end, corner_indices in [("a", (0, 3)), ("b", (1, 2))]:
            p = f[end]
            contacts = []
            for other_key, other in result.items():
                if key == other_key or f['level'] != other['level']:
                    continue
                t, gap = projection(p, other["a"], other["b"])
                if gap <= tolerance and -1e-9 <= t <= 1 + 1e-9:
                    f["neighbours"].add(other_key)
                    other["neighbours"].add(key)
                    contacts.append(other)
            if len(contacts) != 1:
                continue
            other = contacts[0]
            other_end = min(("a", "b"), key=lambda e: distance(p, other[e]))
            if distance(p, other[other_end]) > tolerance:
                # Stop a branch at the outside face of the through-wall. This
                # partitions T-junction solids without double-counting material.
                ray = f["u"] if end == "a" else tuple(-v for v in f["u"])
                den = cross(ray, other["u"])
                if abs(den) >= 0.05:
                    sign = 1 if sum(a * b for a, b in zip(ray, other["n"])) > 0 else -1
                    host_face = add(p, other["n"], sign * other["h"])
                    for index, side in zip(corner_indices, (-1, 1)):
                        q = add(p, f["n"], side * f["h"])
                        t = cross(sub(host_face, q), other["u"]) / den
                        if abs(t) <= 5 * max(f["h"], other["h"]):
                            f["polygon"][index] = add(q, ray, t)
                continue
            ray = f["u"] if end == "a" else tuple(-v for v in f["u"])
            other_ray = (
                other["u"] if other_end == "a" else tuple(-v for v in other["u"])
            )
            den = cross(ray, other_ray)
            if abs(den) < 0.05:
                continue
            other_n = (-other_ray[1], other_ray[0])
            for index, side in zip(corner_indices, (-1, 1)):
                ray_side = side * (1 if end == "a" else -1)
                q = add(p, f["n"], side * f["h"])
                r = add(other[other_end], other_n, -ray_side * other["h"])
                t = cross(sub(r, q), other_ray) / den
                if abs(t) <= 5 * max(f["h"], other["h"]):
                    f["polygon"][index] = add(q, ray, t)
    pairs = list(result.items())
    for i, (key, f) in enumerate(pairs):
        for other_key, other in pairs[i + 1 :]:
            if f['level'] != other['level']:
                continue
            d, v = sub(f["b"], f["a"]), sub(other["b"], other["a"])
            den = cross(d, v)
            if abs(den) > 1e-12:
                t = cross(sub(other["a"], f["a"]), v) / den
                u = cross(sub(other["a"], f["a"]), d) / den
                if 0 <= t <= 1 and 0 <= u <= 1:
                    f["neighbours"].add(other_key)
                    other["neighbours"].add(key)
    return result


def opening_path(doc, key, frame):
    path = path_for(frame["polygon"])
    for oid, opening in doc.extensions.get("architecture", {}).items():
        if (
            opening["kind"] != "opening"
            or opening["wall"] != key
            or not doc.find_by_id(oid)
        ):
            continue
        a = opening["station"] - opening["width"] / 2
        b = opening["station"] + opening["width"] / 2
        w = frame["record"]["width"]
        cut = [
            world_point(frame["entity"], x, y)
            for x, y in [(a, -w), (b, -w), (b, w), (a, w)]
        ]
        path = path.subtracted(path_for(cut))
    return path


def _segments(path):
    result = []
    for polygon in path.toSubpathPolygons():
        pts = [(p.x(), p.y()) for p in polygon]
        if pts and distance(pts[0], pts[-1]) > 1e-10:
            pts.append(pts[0])
        result.extend((a, b) for a, b in zip(pts, pts[1:]) if distance(a, b) > 1e-10)
    return result


def joined_outlines(doc, wall_frames=None):
    wall_frames = wall_frames if wall_frames is not None else frames(doc)
    levels = {f['level'] for f in wall_frames.values()}
    if len(levels) > 1:
        result = {}
        for level in levels:
            result.update(joined_outlines(doc, {k:f for k,f in wall_frames.items() if f['level']==level}))
        return result
    connected = {k: f for k, f in wall_frames.items() if f["neighbours"]}
    if not connected:
        return {}
    paths = {k: opening_path(doc, k, f) for k, f in connected.items()}
    edges = {k: _segments(p) for k, p in paths.items()}
    union = QPainterPath()
    for path in paths.values():
        union = union.united(path)
    epsilon = max(1e-8, min(f["h"] for f in connected.values()) * 1e-6)
    result = {k: [] for k in connected}
    emitted = set()
    all_edges = [edge for group in edges.values() for edge in group]
    for key, segments in edges.items():
        f = connected[key]
        for a, b in segments:
            delta = sub(b, a)
            length = distance(a, b)
            cuts = [0.0, 1.0]
            for c, d in all_edges:
                v = sub(d, c)
                den = cross(delta, v)
                if abs(den) > epsilon * 1e-3:
                    t, s = cross(sub(c, a), v) / den, cross(sub(c, a), delta) / den
                    if 0 < t < 1 and -1e-9 <= s <= 1 + 1e-9:
                        cuts.append(t)
                elif abs(cross(sub(c, a), delta)) <= epsilon * length:
                    for p in (c, d):
                        t = sum(x * y for x, y in zip(sub(p, a), delta)) / length**2
                        if 0 < t < 1:
                            cuts.append(t)
            cuts = sorted(set(round(t, 12) for t in cuts))
            normal = (-delta[1] / length, delta[0] / length)
            for t0, t1 in zip(cuts, cuts[1:]):
                if (t1 - t0) * length < epsilon:
                    continue
                mid = add(a, delta, (t0 + t1) / 2)
                inside = [
                    union.contains(QPointF(*add(mid, normal, sign * epsilon)))
                    for sign in (-1, 1)
                ]
                if inside[0] == inside[1]:
                    continue  # Interior seams have filled space on both sides.
                p, q = add(a, delta, t0), add(a, delta, t1)
                edge_key = tuple(
                    sorted(tuple(round(v / epsilon) for v in pt) for pt in (p, q))
                )
                if edge_key in emitted:
                    continue
                emitted.add(edge_key)
                result[key].append(
                    LineEntity(
                        local_point(f["entity"], p),
                        local_point(f["entity"], q),
                        layer=f["entity"].layer,
                    )
                )
    return result
