"""Validated building profiles, roof surfaces and actual solid geometry."""

import math
from .wall_joining import path_for, world_point


def polygon_area(points):
    return (
        abs(
            sum(
                a[0] * b[1] - b[0] * a[1]
                for a, b in zip(points, points[1:] + points[:1])
            )
        )
        / 2
    )


def validate_profile(points, holes=()):
    from .model3d import validate_feature

    def check(ring):
        validate_feature(
            dict(
                id="profile",
                name="Profile",
                layer="0",
                height=1,
                profile=dict(kind="POLYGON", points=ring),
            ),
            {"0": {}},
        )

    check(points)
    if not isinstance(holes, (list, tuple)) or len(holes) > 100:
        raise ValueError("A profile supports at most 100 holes")
    outer = path_for(points)
    paths = []
    for hole in holes:
        check(hole)
        path = path_for(hole)
        if not outer.contains(path):
            raise ValueError("Holes must lie strictly inside the boundary")
        if any(not path.intersected(previous).isEmpty() for previous in paths):
            raise ValueError("Profile holes must not overlap")
        paths.append(path)


def roof_rectangle(points):
    if len(points) != 4:
        raise ValueError("Roof tools require a rectangular boundary")
    xs = sorted(set(p[0] for p in points))
    ys = sorted(set(p[1] for p in points))
    if (
        len(xs) != 2
        or len(ys) != 2
        or {tuple(p) for p in points} != {(x, y) for x in xs for y in ys}
    ):
        raise ValueError(
            "Roof boundary must be axis-aligned before placing/rotating the object"
        )
    return xs[0], ys[0], xs[1], ys[1]


def roof_surfaces(record):
    x0, y0, x1, y1 = roof_rectangle(record["profile"])
    o = record["overhang"]
    x0, y0, x1, y1 = x0 - o, y0 - o, x1 + o, y1 + o
    slope = math.tan(math.radians(record["slope"]))
    kind = record["roof_type"]
    a, b, c, d = [x0, y0, 0], [x1, y0, 0], [x1, y1, 0], [x0, y1, 0]
    if kind == "Flat":
        return [[a, b, c, d]]
    if kind == "Shed":
        c[2] = d[2] = (y1 - y0) * slope
        return [[a, b, c, d]]
    if x1 - x0 >= y1 - y0:
        rise = (y1 - y0) / 2 * slope
        r0 = [x0, (y0 + y1) / 2, rise]
        r1 = [x1, (y0 + y1) / 2, rise]
        if kind == "Hip":
            r0[0] += (y1 - y0) / 2
            r1[0] -= (y1 - y0) / 2
        faces = [[a, b, r1, r0], [d, r0, r1, c]]
        if kind == "Hip":
            faces += [[a, r0, d], [b, c, r1]]
    else:
        rise = (x1 - x0) / 2 * slope
        r0 = [(x0 + x1) / 2, y0, rise]
        r1 = [(x0 + x1) / 2, y1, rise]
        if kind == "Hip":
            r0[1] += (x1 - x0) / 2
            r1[1] -= (x1 - x0) / 2
        faces = [[a, r0, r1, d], [b, c, r1, r0]]
        if kind == "Hip":
            faces += [[a, b, r0], [d, r1, c]]
    # Square hip roofs have a point ridge; remove repeated vertices.
    result = []
    for face in faces:
        clean = []
        for p in face:
            if p not in clean:
                clean.append(p)
        if len(clean) >= 3:
            result.append(clean)
    return result


def roof_area(record):
    area = 0
    for face in roof_surfaces(record):
        a = face[0]
        for b, c in zip(face[1:-1], face[2:]):
            u = [b[i] - a[i] for i in range(3)]
            v = [c[i] - a[i] for i in range(3)]
            cross = [
                u[1] * v[2] - u[2] * v[1],
                u[2] * v[0] - u[0] * v[2],
                u[0] * v[1] - u[1] * v[0],
            ]
            area += math.sqrt(sum(x * x for x in cross)) / 2
    return area


def stair_parts(r):
    n, w, t, h = r["steps"], r["width"], r["tread"], r["height"]
    step_height = h / n
    steps = []
    landings = []
    rails = []
    n1 = n if r["layout"] == "Straight" else n // 2

    def rect(x0, y0, x1, y1):
        return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]

    for i in range(n1):
        steps.append((rect(0, i * t, w, (i + 1) * t), (i + 1) * step_height))
    rails += [
        ([0, 0, step_height], [0, n1 * t, n1 * step_height]),
        ([w, 0, step_height], [w, n1 * t, n1 * step_height]),
    ]
    if r["layout"] == "L":
        l = max(r["landing"], w)
        landings.append((rect(0, n1 * t, w, n1 * t + l), n1 * step_height))
        for i in range(n - n1):
            steps.append(
                (
                    rect(w + i * t, n1 * t + l - w, w + (i + 1) * t, n1 * t + l),
                    (n1 + i + 1) * step_height,
                )
            )
        rails += [
            (
                [w, n1 * t + l - w, (n1 + 1) * step_height],
                [w + (n - n1) * t, n1 * t + l - w, h],
            ),
            (
                [w, n1 * t + l, (n1 + 1) * step_height],
                [w + (n - n1) * t, n1 * t + l, h],
            ),
        ]
    elif r["layout"] == "U":
        l = r["landing"]
        landings.append((rect(0, n1 * t, 2 * w + l, n1 * t + w), n1 * step_height))
        for i in range(n - n1):
            steps.append(
                (
                    rect(w + l, n1 * t - (i + 1) * t, 2 * w + l, n1 * t - i * t),
                    (n1 + i + 1) * step_height,
                )
            )
        rails += [
            (
                [w + l, n1 * t, (n1 + 1) * step_height],
                [w + l, n1 * t - (n - n1) * t, h],
            ),
            (
                [2 * w + l, n1 * t, (n1 + 1) * step_height],
                [2 * w + l, n1 * t - (n - n1) * t, h],
            ),
        ]
    return dict(steps=steps, landings=landings, rails=rails)


def make_shape(doc, key):
    from .solids import kernel
    from .building import elevation

    cq = kernel()
    r = doc.extensions["building_elements"][key]
    entity = doc.find_by_id(key)
    scale = abs(entity.scale)
    z0 = elevation(doc, key)

    def vector(p, z=0):
        x, y = world_point(entity, p[0], p[1])
        return cq.Vector(x, y, z0 + (r.get("elevation", 0) + z) * scale)

    def wire(points, z=0):
        return cq.Wire.makePolygon([vector(p, z) for p in points], close=True)

    if r["kind"] in ("slab", "ceiling"):
        return cq.Solid.extrudeLinear(
            wire(r["profile"]),
            [wire(hole) for hole in r["holes"]],
            (0, 0, r["thickness"] * scale),
        )
    pieces = []
    if r["kind"] == "roof":
        for face in roof_surfaces(r):
            ring = cq.Wire.makePolygon([vector(p, p[2]) for p in face], close=True)
            pieces.append(
                cq.Solid.extrudeLinear(ring, [], (0, 0, r["thickness"] * scale))
            )
    else:
        parts = stair_parts(r)
        for poly, height in parts["steps"] + parts["landings"]:
            pieces.append(
                cq.Solid.extrudeLinear(wire(poly), [], (0, 0, height * scale))
            )
        if r["rails"]:
            from .units import UNIT_MM

            radius = min(r["width"] * 0.02, 25 / UNIT_MM.get(doc.units, 1)) * scale
            for a, b in parts["rails"]:
                # Each flight has a sloped handrail and two end posts.
                aa = vector(a, a[2] + r["rail_height"])
                bb = vector(b, b[2] + r["rail_height"])
                direction = bb - aa
                if direction.Length > 1e-9:
                    pieces.append(
                        cq.Solid.makeCylinder(
                            radius, direction.Length, aa, direction.normalized()
                        )
                    )
                for p in (a, b):
                    pieces.append(
                        cq.Solid.makeCylinder(
                            radius,
                            r["rail_height"] * scale,
                            vector(p, p[2]),
                            cq.Vector(0, 0, 1),
                        )
                    )
    return cq.Compound.makeCompound(pieces)
