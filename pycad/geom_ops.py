"""
geom_ops.py
Pure geometry helper functions used by the Phase 2 editing tools
(Trim, Extend, Offset, Mirror, Array, Fillet, Chamfer).

Kept separate from geometry.py (which defines entity classes) so these
stay easy to unit test in isolation.
"""
import math
from collections import deque, defaultdict
from typing import Optional, List, Tuple
from .geometry import Point
from .tolerance import EPSILON


def sub(a: Point, b: Point) -> Tuple[float, float]:
    return (a.x - b.x, a.y - b.y)


def length(v: Tuple[float, float]) -> float:
    return math.hypot(v[0], v[1])


def normalize(v: Tuple[float, float]) -> Tuple[float, float]:
    l = length(v)
    if l < 1e-12:
        return (0.0, 0.0)
    return (v[0] / l, v[1] / l)


def dot(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return a[0] * b[0] + a[1] * b[1]


def line_line_intersection(p1: Point, p2: Point, p3: Point, p4: Point,
                            segment_only: bool = False) -> Optional[Point]:
    """Intersection of infinite lines (p1,p2) and (p3,p4). If segment_only,
    require the intersection to lie within both segments."""
    x1, y1, x2, y2 = p1.x, p1.y, p2.x, p2.y
    x3, y3, x4, y4 = p3.x, p3.y, p4.x, p4.y
    denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(denom) < 1e-12:
        return None  # parallel or coincident
    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
    u = ((x1 - x3) * (y1 - y2) - (y1 - y3) * (x1 - x2)) / denom
    if segment_only and not (0 <= t <= 1 and 0 <= u <= 1):
        return None
    ix = x1 + t * (x2 - x1)
    iy = y1 + t * (y2 - y1)
    return Point(ix, iy)


def circle_line_intersections(center: Point, radius: float, p1: Point, p2: Point) -> List[Point]:
    """Intersections of an infinite line (p1,p2) with a circle."""
    dx, dy = p2.x - p1.x, p2.y - p1.y
    fx, fy = p1.x - center.x, p1.y - center.y
    a = dx * dx + dy * dy
    if a < 1e-12:
        return []
    b = 2 * (fx * dx + fy * dy)
    c = fx * fx + fy * fy - radius * radius
    disc = b * b - 4 * a * c
    if disc < 0:
        return []
    disc_sqrt = math.sqrt(disc)
    t1 = (-b - disc_sqrt) / (2 * a)
    t2 = (-b + disc_sqrt) / (2 * a)
    pts = [Point(p1.x + t * dx, p1.y + t * dy) for t in (t1, t2)]
    return pts


def point_on_segment_param(p1: Point, p2: Point, pt: Point) -> float:
    """Parametric t such that pt = p1 + t*(p2-p1), assuming pt is collinear."""
    dx, dy = p2.x - p1.x, p2.y - p1.y
    if abs(dx) > abs(dy):
        return (pt.x - p1.x) / dx if abs(dx) > 1e-12 else 0.0
    return (pt.y - p1.y) / dy if abs(dy) > 1e-12 else 0.0


def reflect_point(pt: Point, a: Point, b: Point) -> Point:
    """Reflect pt across the infinite line through a,b."""
    dx, dy = b.x - a.x, b.y - a.y
    norm = dx * dx + dy * dy
    if norm < 1e-12:
        return Point(pt.x, pt.y)
    t = ((pt.x - a.x) * dx + (pt.y - a.y) * dy) / norm
    proj_x = a.x + t * dx
    proj_y = a.y + t * dy
    return Point(2 * proj_x - pt.x, 2 * proj_y - pt.y)


def rotate_point(pt: Point, center: Point, angle_deg: float) -> Point:
    a = math.radians(angle_deg)
    dx, dy = pt.x - center.x, pt.y - center.y
    cos_a, sin_a = math.cos(a), math.sin(a)
    return Point(center.x + dx * cos_a - dy * sin_a,
                 center.y + dx * sin_a + dy * cos_a)


def offset_line_points(p1: Point, p2: Point, distance: float, side_point: Point) -> Tuple[Point, Point]:
    """Return a new (p1,p2) pair offset perpendicular to the line, on the side
    that side_point is on, by `distance`."""
    dx, dy = p2.x - p1.x, p2.y - p1.y
    length_ = math.hypot(dx, dy)
    if length_ < 1e-12:
        return Point(p1.x, p1.y), Point(p2.x, p2.y)
    # perpendicular (rotate direction 90 deg)
    nx, ny = -dy / length_, dx / length_
    # determine sign: does (side_point - p1) . normal > 0 ?
    to_side = (side_point.x - p1.x, side_point.y - p1.y)
    sign = 1.0 if dot(to_side, (nx, ny)) >= 0 else -1.0
    ox, oy = nx * distance * sign, ny * distance * sign
    return Point(p1.x + ox, p1.y + oy), Point(p2.x + ox, p2.y + oy)


def angle_of(center: Point, p: Point) -> float:
    return math.degrees(math.atan2(p.y - center.y, p.x - center.x))


def point_segment_distance(p: Point, a: Point, b: Point) -> float:
    """Shortest distance from point p to the segment a-b."""
    dx, dy = b.x - a.x, b.y - a.y
    seg_len_sq = dx * dx + dy * dy
    if seg_len_sq < 1e-12:
        return p.distance_to(a)
    t = max(0.0, min(1.0, ((p.x - a.x) * dx + (p.y - a.y) * dy) / seg_len_sq))
    proj = Point(a.x + t * dx, a.y + t * dy)
    return p.distance_to(proj)


def angle_in_arc_range(angle: float, start: float, end: float) -> bool:
    """True if `angle` (degrees) lies on the CCW arc from start to end."""
    def norm(a):
        return a % 360.0
    a, s, e = norm(angle), norm(start), norm(end)
    if s <= e:
        return s <= a <= e
    return a >= s or a <= e


def distance_to_entity(click: Point, entity, tolerance=None) -> float:
    """Approximate world-space distance from click to an entity's outline.
    Used for pick-by-click in the Phase 2 editing tools."""
    from .geometry import PointEntity, LineEntity, CircleEntity, ArcEntity, EllipseEntity, RayEntity, XLineEntity, PolylineEntity, TextEntity
    if entity.kind == 'MLEADER':
        lines, fills, _ = entity.geometry()
        if any(point_in_polygon(click, poly) for poly in entity.label_polygons() + fills):
            return 0.0
        return min(point_segment_distance(click, a, b) for a, b in lines)
    if isinstance(entity, PointEntity):
        return click.distance_to(entity.point)
    if isinstance(entity, LineEntity):
        return point_segment_distance(click, entity.p1, entity.p2)
    if isinstance(entity, ArcEntity):
        d = click.distance_to(entity.center)
        ang = angle_of(entity.center, click)
        if angle_in_arc_range(ang, entity.start_angle, entity.end_angle):
            return abs(d - entity.radius)
        eps = entity.endpoints()
        return min(click.distance_to(p) for p in eps)
    if isinstance(entity, CircleEntity):
        return abs(click.distance_to(entity.center) - entity.radius)
    if isinstance(entity, EllipseEntity):
        pts = entity.sample_points(96)
        return min((point_segment_distance(click, a, b) for a, b in zip(pts, pts[1:] + pts[:1])), default=float("inf"))
    if isinstance(entity, (RayEntity, XLineEntity)):
        dx, dy = entity.p2.x - entity.p1.x, entity.p2.y - entity.p1.y
        length_sq = dx * dx + dy * dy
        if length_sq < 1e-12:
            return click.distance_to(entity.p1)
        t = ((click.x - entity.p1.x) * dx + (click.y - entity.p1.y) * dy) / length_sq
        if isinstance(entity, RayEntity) and not isinstance(entity, XLineEntity):
            t = max(0.0, t)
        projection = Point(entity.p1.x + t * dx, entity.p1.y + t * dy)
        return click.distance_to(projection)
    if isinstance(entity, PolylineEntity):
        if any(entity.bulges):
            from .precision import polyline_parts
            return max(0,min(distance_to_entity(click,part) for part in polyline_parts(entity))-entity.width/2)
        pts = entity.points + ([entity.points[0]] if entity.closed else [])
        return max(0,min((point_segment_distance(click, a, b) for a, b in zip(pts, pts[1:])), default=float("inf"))-entity.width/2)
    if isinstance(entity, TextEntity):
        return click.distance_to(entity.position)
    from .geometry import SplineEntity, HatchEntity, DimensionEntity, BlockReferenceEntity
    if isinstance(entity, BlockReferenceEntity):
        pending=[entity];best=float('inf')
        while pending:
            reference=pending.pop()
            if not isinstance(reference,BlockReferenceEntity):
                best=min(best,distance_to_entity(click,reference,tolerance));continue
            if reference.clip_boundary and not point_in_polygon(click,reference.clip_boundary):continue
            children=reference.resolved_entities
            if tolerance is not None and len(children)>64:
                from .spatial_index import SpatialIndex
                from .geometry import RayEntity,XLineEntity
                key=(id(children),len(children),reference.insertion_point.x,reference.insertion_point.y,
                     reference.scale,reference.rotation,reference.mirrored)
                if getattr(reference,'_pick_index_key',None)!=key:
                    reference._pick_index=SpatialIndex();reference._pick_index.rebuild(children)
                    reference._pick_unbounded=[e for e in children if isinstance(e,(RayEntity,XLineEntity))]
                    reference._pick_index_key=key
                children=reference._pick_index.query((click.x-tolerance,click.y-tolerance,click.x+tolerance,click.y+tolerance))
                ids={id(e) for e in children}
                children += [e for e in reference._pick_unbounded if id(e) not in ids]
            pending.extend(children)
        return best
    if isinstance(entity, SplineEntity):
        pts = entity._catmull_rom_samples()
        return max(0,min((point_segment_distance(click, a, b) for a, b in zip(pts, pts[1:])), default=float("inf"))-entity.width/2)
    if isinstance(entity, HatchEntity):
        from .hatching import render_loops
        loops = render_loops(entity)
        return 0.0 if sum(point_in_polygon(click, loop) for loop in loops) % 2 else float("inf")
    if isinstance(entity, DimensionEntity):
        if entity.kind == 'ORDINATE_DIMENSION':
            points = entity.leader_points()
            return min(point_segment_distance(click,a,b) for a,b in zip(points,points[1:]))
        if entity.kind == 'CURVED_DIMENSION':
            points = entity.arc_points()
            return min(point_segment_distance(click,a,b) for a,b in zip(points,points[1:]))
        a, b = entity.dimension_line_points()
        return min(point_segment_distance(click, a, b), point_segment_distance(click, entity.p1, a), point_segment_distance(click, entity.p2, b))
    return float("inf")


def circle_circle_intersections(c1: Point, r1: float, c2: Point, r2: float) -> List[Point]:
    """Intersection points of two circles (0, 1, or 2 results)."""
    d = c1.distance_to(c2)
    if d < EPSILON or d > r1 + r2 + EPSILON or d < abs(r1 - r2) - EPSILON:
        return []
    a = (r1 * r1 - r2 * r2 + d * d) / (2 * d)
    h_sq = r1 * r1 - a * a
    h = math.sqrt(max(h_sq, 0.0))
    xm = c1.x + a * (c2.x - c1.x) / d
    ym = c1.y + a * (c2.y - c1.y) / d
    if h < EPSILON:
        return [Point(xm, ym)]
    rx = -(c2.y - c1.y) * (h / d)
    ry = (c2.x - c1.x) * (h / d)
    return [Point(xm + rx, ym + ry), Point(xm - rx, ym - ry)]


def point_line_projection(p: Point, a: Point, b: Point) -> Point:
    """Foot of the perpendicular from p onto the infinite line through a,b."""
    dx, dy = b.x - a.x, b.y - a.y
    norm = dx * dx + dy * dy
    if norm < 1e-12:
        return Point(a.x, a.y)
    t = ((p.x - a.x) * dx + (p.y - a.y) * dy) / norm
    return Point(a.x + t * dx, a.y + t * dy)


def normalize_angle_diff(a1: float, a2: float) -> float:
    """Shortest signed difference a2-a1, normalized to (-180, 180]."""
    diff = (a2 - a1) % 360.0
    if diff > 180.0:
        diff -= 360.0
    return diff


def angle_distance(a: float, b: float) -> float:
    """Unsigned minimal angular distance between two angles in degrees."""
    return abs(normalize_angle_diff(a, b))


def bracket_range(low: float, high: float, value: float, cuts: List[float]) -> Tuple[float, float]:
    """Given a linear interval [low, high] and a set of cut positions inside it,
    return the (start, end) of the sub-interval immediately bracketing `value`.
    Used by Trim to find exactly which segment/arc-span to remove."""
    vals = sorted(set([low, high] + [c for c in cuts if low - EPSILON <= c <= high + EPSILON]))
    for i in range(len(vals) - 1):
        if vals[i] - EPSILON <= value <= vals[i + 1] + EPSILON:
            return vals[i], vals[i + 1]
    return low, high


def point_at_param(p1: Point, p2: Point, t: float) -> Point:
    return Point(p1.x + t * (p2.x - p1.x), p1.y + t * (p2.y - p1.y))



def pick_entity(entities, click: Point, tolerance: float, exclude=()):
    """Return the closest entity to `click` within `tolerance` world units, or None."""
    best, best_d = None, tolerance
    hatch_hit = None
    for e in entities:
        if e in exclude:
            continue
        d = distance_to_entity(click, e, tolerance)
        if e.kind == "HATCH":
            if d < tolerance: hatch_hit = e
        elif d < best_d:
            best, best_d = e, d
            if best_d==0.0:break  # No smaller outline distance exists; first tie still wins.
    return best if best is not None else hatch_hit


def circle_to_polygon(center: Point, radius: float, segments: int = 64) -> List[Point]:
    """Approximate a circle as a closed polygon, for hatch-boundary purposes."""
    pts = []
    for i in range(segments):
        a = 2 * math.pi * i / segments
        pts.append(Point(center.x + radius * math.cos(a), center.y + radius * math.sin(a)))
    return pts


def entity_to_segments(entity) -> List[Tuple[Point, Point]]:
    """Tessellate any entity into a list of straight (p1, p2) wall segments,
    for boundary-detection hatching (flood_fill_boundary) and anything else
    that needs a uniform 'this entity is a set of walls' view."""
    from .geometry import LineEntity, CircleEntity, ArcEntity, EllipseEntity, RayEntity, XLineEntity, PolylineEntity, SplineEntity
    segs: List[Tuple[Point, Point]] = []
    if isinstance(entity, LineEntity):
        segs.append((entity.p1, entity.p2))
    elif isinstance(entity, CircleEntity):
        pts = circle_to_polygon(entity.center, entity.radius, segments=64)
        pts.append(pts[0])
        segs.extend(zip(pts, pts[1:]))
    elif isinstance(entity, ArcEntity):
        n = 48
        span = (entity.end_angle - entity.start_angle) % 360.0
        pts = [Point(entity.center.x + entity.radius * math.cos(math.radians(entity.start_angle + span * i / n)),
                      entity.center.y + entity.radius * math.sin(math.radians(entity.start_angle + span * i / n)))
               for i in range(n + 1)]
        segs.extend(zip(pts, pts[1:]))
    elif isinstance(entity, EllipseEntity):
        pts = entity.sample_points(96)
        segs.extend(zip(pts, pts[1:] + pts[:1]))
    elif isinstance(entity, (RayEntity, XLineEntity)):
        # The viewport renderer clips construction lines.  For geometry tools,
        # their defining segment is the stable finite representation.
        segs.append((entity.p1, entity.p2))
    elif isinstance(entity, SplineEntity):
        pts = entity._catmull_rom_samples()
        segs.extend(zip(pts, pts[1:]))
    elif isinstance(entity, PolylineEntity):
        pts = entity.sample_points()
        if entity.closed and pts and pts[-1].distance_to(pts[0])>1e-9: pts.append(pts[0])
        segs.extend(zip(pts, pts[1:]))
    return segs


def _rasterize_segment(p1: Point, p2: Point, xmin: float, ymin: float, cell_w: float, cell_h: float,
                        resolution: int, walls: set):
    length_cells = max(abs((p2.x - p1.x) / cell_w), abs((p2.y - p1.y) / cell_h))
    steps = max(int(length_cells * 2), 1)
    for s in range(steps + 1):
        t = s / steps
        x = p1.x + (p2.x - p1.x) * t
        y = p1.y + (p2.y - p1.y) * t
        i = int((x - xmin) / cell_w)
        j = int((y - ymin) / cell_h)
        if 0 <= i < resolution and 0 <= j < resolution:
            walls.add((i, j))


def _simplify_collinear(points: List[Point]) -> List[Point]:
    """Merge consecutive polygon edges pointing the same direction, so a
    raster-traced (staircase) boundary along a long straight wall collapses
    to a couple of vertices instead of one per grid cell."""
    if len(points) < 3:
        return points
    result = []
    n = len(points)
    for i in range(n):
        prev, cur, nxt = points[i - 1], points[i], points[(i + 1) % n]
        d1 = (cur.x - prev.x, cur.y - prev.y)
        d2 = (nxt.x - cur.x, nxt.y - cur.y)
        cross = d1[0] * d2[1] - d1[1] * d2[0]
        if abs(cross) > 1e-9:
            result.append(cur)
    return result if len(result) >= 3 else points


def _point_to_segment_dist(p: Point, a: Point, b: Point) -> float:
    dx, dy = b.x - a.x, b.y - a.y
    if dx == 0 and dy == 0:
        return p.distance_to(a)
    t = max(0.0, min(1.0, ((p.x - a.x) * dx + (p.y - a.y) * dy) / (dx * dx + dy * dy)))
    return p.distance_to(Point(a.x + t * dx, a.y + t * dy))


def _dp_open(points: List[Point], tolerance: float) -> List[Point]:
    """Standard Douglas-Peucker simplification of an open polyline."""
    if len(points) < 3:
        return points
    start, end = points[0], points[-1]
    max_d, idx = -1.0, -1
    for i in range(1, len(points) - 1):
        d = _point_to_segment_dist(points[i], start, end)
        if d > max_d:
            max_d, idx = d, i
    if max_d > tolerance:
        left = _dp_open(points[:idx + 1], tolerance)
        right = _dp_open(points[idx:], tolerance)
        return left[:-1] + right
    return [start, end]


def simplify_closed_polygon(points: List[Point], tolerance: float) -> List[Point]:
    """Douglas-Peucker doesn't directly handle closed loops (it needs two
    distinct anchor points to measure deviation against) - split the loop
    at its two farthest-apart points into two open chains, simplify each,
    then merge back into a closed polygon. Used to smooth the staircase
    artifacts a grid-traced boundary leaves on diagonal/curved walls."""
    n = len(points)
    if n < 5:
        return points

    def dist2(a, b):
        return (a.x - b.x) ** 2 + (a.y - b.y) ** 2

    i1 = max(range(n), key=lambda i: dist2(points[0], points[i]))
    if i1 == 0:
        return points
    chain1 = points[0:i1 + 1]
    chain2 = points[i1:] + points[0:1]
    s1 = _dp_open(chain1, tolerance)
    s2 = _dp_open(chain2, tolerance)
    merged = s1[:-1] + s2[:-1]
    return merged if len(merged) >= 3 else points


def flood_fill_boundary(entities, click: Point, bbox: Tuple[float, float, float, float],
                         resolution: int = 300) -> Optional[List[Point]]:
    """Detect the boundary of the enclosed region containing `click`, formed
    by the walls of `entities` (tessellated via entity_to_segments), by
    rasterizing into a resolution x resolution grid over `bbox` and flood-
    filling from the click's cell. This is what makes Hatch work by
    clicking a point inside an area bounded by ANY mix of lines/arcs/
    circles/polylines - not just a single pre-existing closed shape.

    Returns a closed polygon (world-space Points, first point not repeated
    at the end) or None if: click is outside bbox, click lands on a wall,
    or the filled region reaches the raster edge (meaning it isn't actually
    enclosed within the searched area - e.g. a gap in the boundary, or the
    area is bigger than the current view since `bbox` is normally the
    visible viewport - see HatchTool)."""
    xmin, ymin, xmax, ymax = bbox
    w = max(xmax - xmin, 1e-9)
    h = max(ymax - ymin, 1e-9)
    cell_w = w / resolution
    cell_h = h / resolution

    if not (xmin <= click.x <= xmax and ymin <= click.y <= ymax):
        return None

    walls = set()
    for e in entities:
        for p1, p2 in entity_to_segments(e):
            _rasterize_segment(p1, p2, xmin, ymin, cell_w, cell_h, resolution, walls)

    si, sj = int((click.x - xmin) / cell_w), int((click.y - ymin) / cell_h)
    if not (0 <= si < resolution and 0 <= sj < resolution) or (si, sj) in walls:
        return None

    filled = set()
    dq = deque([(si, sj)])
    filled.add((si, sj))
    touched_edge = False
    while dq:
        i, j = dq.popleft()
        if i in (0, resolution - 1) or j in (0, resolution - 1):
            touched_edge = True
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ni, nj = i + di, j + dj
            if 0 <= ni < resolution and 0 <= nj < resolution:
                if (ni, nj) not in filled and (ni, nj) not in walls:
                    filled.add((ni, nj))
                    dq.append((ni, nj))
            else:
                touched_edge = True
    if touched_edge:
        return None

    edges: List[Tuple[Tuple[int, int], Tuple[int, int]]] = []
    for (i, j) in filled:
        if (i - 1, j) not in filled:
            edges.append(((i, j), (i, j + 1)))
        if (i + 1, j) not in filled:
            edges.append(((i + 1, j), (i + 1, j + 1)))
        if (i, j - 1) not in filled:
            edges.append(((i, j), (i + 1, j)))
        if (i, j + 1) not in filled:
            edges.append(((i, j + 1), (i + 1, j + 1)))
    if not edges:
        return None

    adj = defaultdict(list)
    for a, b in edges:
        adj[a].append(b)
        adj[b].append(a)

    start_v = edges[0][0]
    loop = [start_v]
    prev, cur = None, start_v
    visited_edges = set()
    while True:
        nxt = None
        for v in adj[cur]:
            e_key = frozenset((cur, v))
            if e_key not in visited_edges:
                nxt = v
                visited_edges.add(e_key)
                break
        if nxt is None:
            break
        loop.append(nxt)
        prev, cur = cur, nxt
        if cur == start_v:
            break
        if len(loop) > 4 * len(edges):
            break  # safety guard against a malformed/non-simple region

    def corner_to_world(corner):
        ci, cj = corner
        return Point(xmin + ci * cell_w, ymin + cj * cell_h)

    world_pts = [corner_to_world(c) for c in loop[:-1]]
    simplified = _simplify_collinear(world_pts)
    simplified = simplify_closed_polygon(simplified, tolerance=2.0 * max(cell_w, cell_h))
    return simplified if len(simplified) >= 3 else None


def point_in_polygon(point: Point, polygon: List[Point]) -> bool:
    """Standard ray-casting point-in-polygon test. Used for Xref/block
    clip-boundary tests - not a general-purpose geometry primitive elsewhere
    in the codebase, so it lives here rather than in geometry.py."""
    if len(polygon) < 3:
        return False
    inside = False
    n = len(polygon)
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i].x, polygon[i].y
        xj, yj = polygon[j].x, polygon[j].y
        if ((yi > point.y) != (yj > point.y)) and \
           (point.x < (xj - xi) * (point.y - yi) / (yj - yi + 1e-15) + xi):
            inside = not inside
        j = i
    return inside


def compute_hatch_lines(boundary: List[Point], angle_deg: float, spacing: float) -> List[Tuple[Point, Point]]:
    """Even-odd scanline hatch fill: returns line segments (in world space)
    that fill the interior of a closed polygon at the given angle/spacing."""
    if len(boundary) < 3 or spacing <= 0:
        return []
    theta = math.radians(-angle_deg)
    cos_t, sin_t = math.cos(theta), math.sin(theta)
    cos_inv, sin_inv = math.cos(-theta), math.sin(-theta)

    def rot(p: Point) -> Tuple[float, float]:
        return (p.x * cos_t - p.y * sin_t, p.x * sin_t + p.y * cos_t)

    def unrot(x: float, y: float) -> Point:
        return Point(x * cos_inv - y * sin_inv, x * sin_inv + y * cos_inv)

    pts_r = [rot(p) for p in boundary]
    edges = list(zip(pts_r, pts_r[1:] + [pts_r[0]]))
    ys = [p[1] for p in pts_r]
    y_min, y_max = min(ys), max(ys)

    segments = []
    y = y_min + spacing / 2.0
    guard = 0
    while y <= y_max and guard < 100000:
        guard += 1
        xs = []
        for (x1, y1), (x2, y2) in edges:
            if (y1 <= y < y2) or (y2 <= y < y1):
                t = (y - y1) / (y2 - y1)
                xs.append(x1 + t * (x2 - x1))
        xs.sort()
        for i in range(0, len(xs) - 1, 2):
            segments.append((unrot(xs[i], y), unrot(xs[i + 1], y)))
        y += spacing
    return segments





def offset_polyline(points, closed, distance, side_point):
    """Miter offset for open paths and simple convex closed polygons.

Concave closed paths require topology splitting and are rejected explicitly.
This avoids returning the inverted/self-crossing shapes the old edge-by-edge
side test produced. The kernel roadmap includes full offset topology.
"""
    if len(points) < 2 or not math.isfinite(distance) or distance <= 0:
        raise ValueError("Offset needs a positive distance and at least two vertices")
    edges = list(zip(points, points[1:] + ([points[0]] if closed else [])))
    if any(a.distance_to(b) < 1e-9 for a,b in edges):
        raise ValueError("Remove zero-length segments before offsetting")
    if closed:
        turns=[]
        for i,b in enumerate(points):
            a,c=points[i-1],points[(i+1)%len(points)]
            turns.append((b.x-a.x)*(c.y-b.y)-(b.y-a.y)*(c.x-b.x))
        signs={1 if t>0 else -1 for t in turns if abs(t)>1e-9}
        if len(signs)!=1:
            raise ValueError("Only convex closed polyline offsets are supported in this build")
        orientation=next(iter(signs))
        sign=orientation if point_in_polygon(side_point,points) else -orientation
    else:
        a,b=min(edges,key=lambda ab:point_segment_distance(side_point,*ab))
        sign=1 if (b.x-a.x)*(side_point.y-a.y)-(b.y-a.y)*(side_point.x-a.x)>=0 else -1
    shifted=[]
    for a,b in edges:
        size=a.distance_to(b)
        dx=-(b.y-a.y)/size*distance*sign;dy=(b.x-a.x)/size*distance*sign
        shifted.append((Point(a.x+dx,a.y+dy),Point(b.x+dx,b.y+dy)))
    result=[] if closed else [shifted[0][0]]
    indices=range(len(shifted)) if closed else range(1,len(shifted))
    for i in indices:
        previous,current=shifted[i-1],shifted[i]
        joint=line_line_intersection(*previous,*current) or current[0]
        if joint.distance_to(points[i])>20*distance:
            raise ValueError("Offset miter is too long at an acute corner")
        result.append(joint)
    if not closed:
        result.append(shifted[-1][1])
    output_edges=list(zip(result,result[1:]+([result[0]] if closed else [])))
    for (a,b),(c,d) in zip(edges,output_edges):
        if (b.x-a.x)*(d.x-c.x)+(b.y-a.y)*(d.y-c.y)<=1e-9:
            raise ValueError("Offset distance collapses or reverses a segment")
    for i,edge in enumerate(output_edges):
        for j in range(i+2,len(output_edges)):
            if closed and i==0 and j==len(output_edges)-1:
                continue
            if line_line_intersection(*edge,*output_edges[j],segment_only=True):
                raise ValueError("Offset would intersect itself")
    return result
