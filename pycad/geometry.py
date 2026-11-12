"""
geometry.py
Core geometric entity classes for PyCAD.
All coordinates are in "world" (drawing) units, stored as floats.
"""
from __future__ import annotations
import math
import uuid
from dataclasses import dataclass, field
from typing import List, Tuple, Optional

from .tolerance import EPSILON


def _new_id() -> str:
    return uuid.uuid4().hex


def _reflect_pt(pt: "Point", a: "Point", b: "Point") -> "Point":
    dx, dy = b.x - a.x, b.y - a.y
    norm = dx * dx + dy * dy
    if norm < 1e-12:
        return Point(pt.x, pt.y)
    t = ((pt.x - a.x) * dx + (pt.y - a.y) * dy) / norm
    proj_x, proj_y = a.x + t * dx, a.y + t * dy
    return Point(2 * proj_x - pt.x, 2 * proj_y - pt.y)


def _rotate_pt(pt: "Point", center: "Point", angle_deg: float) -> "Point":
    a = math.radians(angle_deg)
    dx, dy = pt.x - center.x, pt.y - center.y
    cos_a, sin_a = math.cos(a), math.sin(a)
    return Point(center.x + dx * cos_a - dy * sin_a, center.y + dx * sin_a + dy * cos_a)


def _scale_pt(pt: "Point", center: "Point", factor: float) -> "Point":
    return Point(center.x + (pt.x - center.x) * factor, center.y + (pt.y - center.y) * factor)


@dataclass
class Point:
    x: float
    y: float

    def as_tuple(self) -> Tuple[float, float]:
        return (self.x, self.y)

    def distance_to(self, other: "Point") -> float:
        return math.hypot(self.x - other.x, self.y - other.y)


class Entity:
    """Base class for all drawable CAD entities."""

    kind: str = "entity"

    def __init__(self, layer: str = "0", color: str = "BYLAYER", linetype: str = "CONTINUOUS", transparency: float = 0.0, hyperlink: str = ""):
        self.id = _new_id()
        self.layer = layer
        self.color = color
        self.linetype = linetype
        self.transparency = transparency
        self.hyperlink = hyperlink
        self.selected = False

    def style_kwargs(self):
        return dict(layer=self.layer,color=self.color,linetype=self.linetype,transparency=self.transparency,hyperlink=self.hyperlink)

    def bbox(self) -> Tuple[float, float, float, float]:
        """Return (min_x, min_y, max_x, max_y)."""
        raise NotImplementedError

    def endpoints(self) -> List[Point]:
        """Snap-able endpoint candidates."""
        return []

    def midpoints(self) -> List[Point]:
        return []

    def center_points(self) -> List[Point]:
        return []

    def translate(self, dx: float, dy: float) -> None:
        raise NotImplementedError

    def to_dict(self) -> dict:
        raise NotImplementedError

    def clone(self) -> "Entity":
        """Return a deep, independent copy with a fresh id (used by Mirror/Array/Copy)."""
        raise NotImplementedError

    def reflect_across(self, a: "Point", b: "Point") -> None:
        """Mirror this entity across the infinite line through a,b, in place."""
        raise NotImplementedError

    def rotate_around(self, center: "Point", angle_deg: float) -> None:
        """Rotate this entity about center by angle_deg (CCW), in place."""
        raise NotImplementedError

    def scale_from(self, center: "Point", factor: float) -> None:
        """Uniformly scale this entity about center by factor, in place."""
        raise NotImplementedError

    def grip_points(self) -> List[Tuple[str, "Point"]]:
        """(grip_id, point) pairs for interactive editing - dragging one
        reshapes just that part of the entity (e.g. one line endpoint, one
        polyline vertex), unlike a whole-entity move. The returned Point
        objects are the entity's actual live attributes where possible
        (dragging one directly edits the entity), not copies - callers that
        need to detect "which real point is this" (SelectTool's grip drag)
        rely on that. Entities with nothing sensible to grip-edit return []."""
        return []


class LineEntity(Entity):
    kind = "LINE"

    def __init__(self, p1: Point, p2: Point, **kwargs):
        super().__init__(**kwargs)
        self.p1 = p1
        self.p2 = p2

    def bbox(self):
        return (min(self.p1.x, self.p2.x), min(self.p1.y, self.p2.y),
                max(self.p1.x, self.p2.x), max(self.p1.y, self.p2.y))

    def endpoints(self):
        return [self.p1, self.p2]

    def midpoints(self):
        return [Point((self.p1.x + self.p2.x) / 2, (self.p1.y + self.p2.y) / 2)]

    def translate(self, dx, dy):
        self.p1.x += dx; self.p1.y += dy
        self.p2.x += dx; self.p2.y += dy

    def length(self) -> float:
        return self.p1.distance_to(self.p2)

    def to_dict(self):
        return {"kind": self.kind, "p1": self.p1.as_tuple(), "p2": self.p2.as_tuple(),
                "layer": self.layer, "color": self.color}

    def clone(self):
        return LineEntity(Point(self.p1.x, self.p1.y), Point(self.p2.x, self.p2.y),
                           **self.style_kwargs())

    def reflect_across(self, a, b):
        self.p1 = _reflect_pt(self.p1, a, b)
        self.p2 = _reflect_pt(self.p2, a, b)

    def rotate_around(self, center, angle_deg):
        self.p1 = _rotate_pt(self.p1, center, angle_deg)
        self.p2 = _rotate_pt(self.p2, center, angle_deg)

    def scale_from(self, center, factor):
        self.p1 = _scale_pt(self.p1, center, factor)
        self.p2 = _scale_pt(self.p2, center, factor)

    def grip_points(self):
        return [("p1", self.p1), ("p2", self.p2)]


class CircleEntity(Entity):
    kind = "CIRCLE"

    def __init__(self, center: Point, radius: float, **kwargs):
        super().__init__(**kwargs)
        self.center = center
        self.radius = radius

    def bbox(self):
        c, r = self.center, self.radius
        return (c.x - r, c.y - r, c.x + r, c.y + r)

    def center_points(self):
        return [self.center]

    def translate(self, dx, dy):
        self.center.x += dx
        self.center.y += dy

    def to_dict(self):
        return {"kind": self.kind, "center": self.center.as_tuple(), "radius": self.radius,
                "layer": self.layer, "color": self.color}

    def clone(self):
        return CircleEntity(Point(self.center.x, self.center.y), self.radius,
                             **self.style_kwargs())

    def reflect_across(self, a, b):
        self.center = _reflect_pt(self.center, a, b)

    def rotate_around(self, center, angle_deg):
        self.center = _rotate_pt(self.center, center, angle_deg)

    def scale_from(self, center, factor):
        self.center = _scale_pt(self.center, center, factor)
        self.radius *= abs(factor)

    def grip_points(self):
        return [("center", self.center), ("radius", Point(self.center.x + self.radius, self.center.y))]


class ArcEntity(Entity):
    kind = "ARC"

    def __init__(self, center: Point, radius: float, start_angle: float, end_angle: float, **kwargs):
        """Angles in degrees, CCW from +X axis (AutoCAD convention)."""
        super().__init__(**kwargs)
        self.center = center
        self.radius = radius
        self.start_angle = start_angle
        self.end_angle = end_angle

    def bbox(self):
        c, r = self.center, self.radius
        return (c.x - r, c.y - r, c.x + r, c.y + r)

    def endpoints(self):
        sa, ea = math.radians(self.start_angle), math.radians(self.end_angle)
        c, r = self.center, self.radius
        p1 = Point(c.x + r * math.cos(sa), c.y + r * math.sin(sa))
        p2 = Point(c.x + r * math.cos(ea), c.y + r * math.sin(ea))
        return [p1, p2]

    def center_points(self):
        return [self.center]

    def translate(self, dx, dy):
        self.center.x += dx
        self.center.y += dy

    def to_dict(self):
        return {"kind": self.kind, "center": self.center.as_tuple(), "radius": self.radius,
                "start_angle": self.start_angle, "end_angle": self.end_angle,
                "layer": self.layer, "color": self.color}

    def clone(self):
        return ArcEntity(Point(self.center.x, self.center.y), self.radius,
                          self.start_angle, self.end_angle, **self.style_kwargs())

    def reflect_across(self, a, b):
        line_angle = math.degrees(math.atan2(b.y - a.y, b.x - a.x))
        new_start = 2 * line_angle - self.end_angle
        new_end = 2 * line_angle - self.start_angle
        self.center = _reflect_pt(self.center, a, b)
        self.start_angle, self.end_angle = new_start, new_end

    def rotate_around(self, center, angle_deg):
        self.center = _rotate_pt(self.center, center, angle_deg)
        self.start_angle += angle_deg
        self.end_angle += angle_deg

    def scale_from(self, center, factor):
        self.center = _scale_pt(self.center, center, factor)
        self.radius *= abs(factor)
        if factor < 0:
            self.start_angle += 180
            self.end_angle += 180

    def grip_points(self):
        p1, p2 = self.endpoints()
        return [("center", self.center), ("start", p1), ("end", p2)]


class PointEntity(Entity):
    """A CAD point marker with a persistent world-space coordinate."""
    kind = "POINT"

    def __init__(self, point: Point, **kwargs):
        super().__init__(**kwargs)
        self.point = point

    def bbox(self):
        return (self.point.x, self.point.y, self.point.x, self.point.y)

    def endpoints(self):
        return [self.point]

    def center_points(self):
        return [self.point]

    def translate(self, dx, dy):
        self.point.x += dx
        self.point.y += dy

    def to_dict(self):
        return {"kind": self.kind, "point": self.point.as_tuple(),
                "layer": self.layer, "color": self.color}

    def clone(self):
        return PointEntity(Point(self.point.x, self.point.y), **self.style_kwargs())

    def reflect_across(self, a, b):
        self.point = _reflect_pt(self.point, a, b)

    def rotate_around(self, center, angle_deg):
        self.point = _rotate_pt(self.point, center, angle_deg)

    def scale_from(self, center, factor):
        self.point = _scale_pt(self.point, center, factor)

    def grip_points(self):
        return [("point", self.point)]


class EllipseEntity(Entity):
    """Rotated ellipse represented by center, axis radii and rotation."""
    kind = "ELLIPSE"

    def __init__(self, center: Point, major_radius: float, minor_radius: float,
                 rotation: float = 0.0, **kwargs):
        super().__init__(**kwargs)
        if not all(math.isfinite(v) and v > 0 for v in (major_radius, minor_radius)):
            raise ValueError("Ellipse radii must be finite and positive")
        self.center = center
        self.major_radius = major_radius
        self.minor_radius = minor_radius
        self.rotation = rotation

    def _axis_point(self, radius, angle_deg):
        angle = math.radians(self.rotation + angle_deg)
        return Point(self.center.x + radius * math.cos(angle),
                     self.center.y + radius * math.sin(angle))

    def sample_points(self, segments=96):
        angle = math.radians(self.rotation)
        cos_angle, sin_angle = math.cos(angle), math.sin(angle)
        return [
            Point(
                self.center.x + self.major_radius * cos_angle * math.cos(2 * math.pi * i / segments)
                - self.minor_radius * sin_angle * math.sin(2 * math.pi * i / segments),
                self.center.y + self.major_radius * sin_angle * math.cos(2 * math.pi * i / segments)
                + self.minor_radius * cos_angle * math.sin(2 * math.pi * i / segments),
            )
            for i in range(segments)
        ]

    def bbox(self):
        angle = math.radians(self.rotation)
        half_x = math.hypot(self.major_radius * math.cos(angle), self.minor_radius * math.sin(angle))
        half_y = math.hypot(self.major_radius * math.sin(angle), self.minor_radius * math.cos(angle))
        return (self.center.x - half_x, self.center.y - half_y,
                self.center.x + half_x, self.center.y + half_y)

    def endpoints(self):
        return [self._axis_point(self.major_radius, 0), self._axis_point(self.major_radius, 180)]

    def midpoints(self):
        return [self._axis_point(self.minor_radius, 90), self._axis_point(self.minor_radius, 270)]

    def center_points(self):
        return [self.center]

    def translate(self, dx, dy):
        self.center.x += dx
        self.center.y += dy

    def to_dict(self):
        return {"kind": self.kind, "center": self.center.as_tuple(),
                "major_radius": self.major_radius, "minor_radius": self.minor_radius,
                "rotation": self.rotation, "layer": self.layer, "color": self.color}

    def clone(self):
        return EllipseEntity(Point(self.center.x, self.center.y), self.major_radius,
                             self.minor_radius, self.rotation, **self.style_kwargs())

    def reflect_across(self, a, b):
        axis_angle = math.degrees(math.atan2(b.y - a.y, b.x - a.x))
        self.center = _reflect_pt(self.center, a, b)
        self.rotation = 2 * axis_angle - self.rotation

    def rotate_around(self, center, angle_deg):
        self.center = _rotate_pt(self.center, center, angle_deg)
        self.rotation += angle_deg

    def scale_from(self, center, factor):
        self.center = _scale_pt(self.center, center, factor)
        self.major_radius *= abs(factor)
        self.minor_radius *= abs(factor)

    def grip_points(self):
        return [("center", self.center), ("major", self._axis_point(self.major_radius, 0)),
                ("minor", self._axis_point(self.minor_radius, 90))]


class RayEntity(Entity):
    """A half-infinite construction line from p1 through p2."""
    kind = "RAY"

    def __init__(self, p1: Point, p2: Point, **kwargs):
        super().__init__(**kwargs)
        if p1.distance_to(p2) < 1e-12:
            raise ValueError("Ray direction must be non-zero")
        self.p1 = p1
        self.p2 = p2

    def bbox(self):
        return (min(self.p1.x, self.p2.x), min(self.p1.y, self.p2.y),
                max(self.p1.x, self.p2.x), max(self.p1.y, self.p2.y))

    def endpoints(self):
        return [self.p1, self.p2]

    def translate(self, dx, dy):
        self.p1.x += dx; self.p1.y += dy
        self.p2.x += dx; self.p2.y += dy

    def to_dict(self):
        return {"kind": self.kind, "p1": self.p1.as_tuple(), "p2": self.p2.as_tuple(),
                "layer": self.layer, "color": self.color}

    def clone(self):
        return RayEntity(Point(self.p1.x, self.p1.y), Point(self.p2.x, self.p2.y),
                         **self.style_kwargs())

    def reflect_across(self, a, b):
        self.p1 = _reflect_pt(self.p1, a, b); self.p2 = _reflect_pt(self.p2, a, b)

    def rotate_around(self, center, angle_deg):
        self.p1 = _rotate_pt(self.p1, center, angle_deg); self.p2 = _rotate_pt(self.p2, center, angle_deg)

    def scale_from(self, center, factor):
        self.p1 = _scale_pt(self.p1, center, factor); self.p2 = _scale_pt(self.p2, center, factor)

    def grip_points(self):
        return [("base", self.p1), ("direction", self.p2)]


class XLineEntity(RayEntity):
    """A construction line extending infinitely in both directions."""
    kind = "XLINE"


class PolylineEntity(Entity):
    kind = "LWPOLYLINE"

    def __init__(self, points: List[Point], closed: bool = False, bulges=None, width=0.0, **kwargs):
        super().__init__(**kwargs)
        self.points = points
        self.closed = closed
        if type(width) not in (int,float) or not math.isfinite(width) or width<0:raise ValueError('Polyline width must be finite and nonnegative')
        self.width = float(width)
        self.bulges = list(bulges) if bulges is not None else [0.0]*len(points)
        from .precision import validate_bulges
        validate_bulges(self.points, self.bulges, self.closed)

    def sample_points(self, tolerance=None):
        from .precision import polyline_samples
        return polyline_samples(self, tolerance)

    def bbox(self):
        from .precision import polyline_bounds
        x1,y1,x2,y2=polyline_bounds(self);w=self.width/2
        return x1-w,y1-w,x2+w,y2+w

    def _vertex_bbox(self):
        xs = [p.x for p in self.points]
        ys = [p.y for p in self.points]
        return (min(xs), min(ys), max(xs), max(ys))

    def endpoints(self):
        return list(self.points)

    def midpoints(self):
        from .precision import segment_point
        return [segment_point(a,b,self.bulges[i],0.5) for i,(a,b) in enumerate(zip(self.points,self.points[1:]+([self.points[0]] if self.closed else [])))]

    def translate(self, dx, dy):
        for p in self.points:
            p.x += dx
            p.y += dy

    def to_dict(self):
        return {"kind": self.kind, "points": [p.as_tuple() for p in self.points],
                "closed": self.closed, "layer": self.layer, "color": self.color}

    def clone(self):
        return PolylineEntity([Point(p.x, p.y) for p in self.points], closed=self.closed, bulges=self.bulges, width=self.width,
                               **self.style_kwargs())

    def reflect_across(self, a, b):
        self.points = [_reflect_pt(p, a, b) for p in self.points]
        self.bulges = [-v for v in self.bulges]

    def rotate_around(self, center, angle_deg):
        self.points = [_rotate_pt(p, center, angle_deg) for p in self.points]

    def scale_from(self, center, factor):
        self.points = [_scale_pt(p, center, factor) for p in self.points]
        self.width *= abs(factor)

    def grip_points(self):
        return [(f"pt{i}", p) for i, p in enumerate(self.points)]


class RectangleEntity(PolylineEntity):
    """Convenience constructor - stored internally as a closed polyline."""
    kind = "RECTANGLE"

    def __init__(self, p1: Point, p2: Point, **kwargs):
        pts = [Point(p1.x, p1.y), Point(p2.x, p1.y), Point(p2.x, p2.y), Point(p1.x, p2.y)]
        super().__init__(pts, closed=True, **kwargs)


class TextEntity(Entity):
    kind = "TEXT"

    def __init__(self, position: Point, text: str, height: float = 2.5, rotation: float = 0.0, style_name='Standard', wrap_width=0.0, rich_html='', **kwargs):
        super().__init__(**kwargs)
        self.position = position
        self.text = text
        self.height = height
        self.rotation = rotation
        self.style_name = style_name
        self.wrap_width = wrap_width
        self.rich_html = rich_html
        self._text_style = dict(font_family='Sans Serif', height=2.5, width_factor=1.0, bold=False, italic=False, oblique=0.0)

    def bbox(self):
        lines = self.text.split("\n")
        w = self.height * max(1, *(len(line) for line in lines)) * self._text_style['width_factor']
        if self.wrap_width > 0:
            chars = max(1, int(self.wrap_width/(self.height*self._text_style["width_factor"])))
            count = sum(max(1, math.ceil(len(line)/chars)) for line in lines)
            w = self.wrap_width
        else: count = len(lines)
        bottom = -(count-1)*self.height*1.4
        corners = [Point(x,y) for x,y in ((0,bottom),(w,bottom),(w,self.height),(0,self.height))]
        shear = math.tan(math.radians(self._text_style['oblique']))
        corners = [Point(p.x+shear*p.y,p.y) for p in corners]
        corners = [_rotate_pt(p,Point(0,0),self.rotation) for p in corners]
        return (self.position.x+min(p.x for p in corners),self.position.y+min(p.y for p in corners),
                self.position.x+max(p.x for p in corners),self.position.y+max(p.y for p in corners))

    def endpoints(self):
        return [self.position]

    def translate(self, dx, dy):
        self.position.x += dx
        self.position.y += dy

    def to_dict(self):
        return {"kind": self.kind, "position": self.position.as_tuple(), "text": self.text,
                "height": self.height, "layer": self.layer, "color": self.color}

    def clone(self):
        result = TextEntity(Point(self.position.x, self.position.y), self.text,
                           height=self.height, rotation=self.rotation, style_name=self.style_name, wrap_width=self.wrap_width, rich_html=self.rich_html, **self.style_kwargs())
        result._text_style = dict(self._text_style)
        return result

    def reflect_across(self, a, b):
        self.position = _reflect_pt(self.position, a, b)
        self.rotation = 2 * math.degrees(math.atan2(b.y-a.y, b.x-a.x)) - self.rotation

    def rotate_around(self, center, angle_deg):
        self.position = _rotate_pt(self.position, center, angle_deg)
        self.rotation += angle_deg

    def scale_from(self, center, factor):
        self.position = _scale_pt(self.position, center, factor)
        self.height *= abs(factor)
        self.wrap_width *= abs(factor)


class DimensionEntity(Entity):
    """A linear dimension: measures the distance between p1 and p2, with the
    dimension line placed through dim_point. `dim_style` selects how the
    dimension line is oriented: 'aligned' (parallel to p1-p2), 'horizontal',
    or 'vertical'. If `source_line_id` is set, the document keeps p1/p2 in
    sync with that line's live endpoints (see Document.sync_associative) -
    p1/p2 are still real fields so the dimension works even if the source
    is later deleted (it just stops updating, "detaching" from the source)."""
    kind = "DIMENSION"

    def __init__(self, p1: Point, p2: Point, dim_point: Point, dim_style: str = "aligned",
                 text_override: Optional[str] = None, source_line_id: Optional[str] = None, style_name: str = "Standard", **kwargs):
        super().__init__(**kwargs)
        self.p1 = p1
        self.p2 = p2
        self.dim_point = dim_point
        self.dim_style = dim_style
        self.text_override = text_override
        self.source_line_id = source_line_id
        self.style_name = style_name

    def measurement(self) -> float:
        if self.dim_style == "horizontal":
            return abs(self.p2.x - self.p1.x)
        if self.dim_style == "vertical":
            return abs(self.p2.y - self.p1.y)
        if self.dim_style == "diameter":
            return 2 * self.p1.distance_to(self.p2)
        # "aligned" and "radius" both measure the straight p1-p2 distance
        return self.p1.distance_to(self.p2)

    def label_text(self) -> str:
        """The text actually shown on the dimension - adds the R/⌀ prefix
        radius and diameter dimensions use, on top of whatever measurement()
        or an explicit text_override provides."""
        if self.text_override:
            return self.text_override
        if self.dim_style == "radius":
            return f"R{self.measurement():.2f}"
        if self.dim_style == "diameter":
            return f"\u2300{self.measurement():.2f}"
        return f"{self.measurement():.2f}"

    def dimension_line_points(self) -> Tuple[Point, Point]:
        """Returns (dl1, dl2): the two ends of the dimension line itself
        (i.e. p1/p2 projected out to the offset the user picked). For
        radius/diameter, this is just the leader from the circle's edge
        (p2) out to wherever the label was placed (dim_point) - there's no
        separate offset step the way linear dimensions have."""
        if self.dim_style in ("radius", "diameter"):
            return Point(self.p2.x, self.p2.y), Point(self.dim_point.x, self.dim_point.y)
        if self.dim_style == "horizontal":
            y = self.dim_point.y
            return Point(self.p1.x, y), Point(self.p2.x, y)
        if self.dim_style == "vertical":
            x = self.dim_point.x
            return Point(x, self.p1.y), Point(x, self.p2.y)
        # aligned
        dx, dy = self.p2.x - self.p1.x, self.p2.y - self.p1.y
        seg_len = math.hypot(dx, dy)
        if seg_len < EPSILON:
            return Point(self.p1.x, self.p1.y), Point(self.p2.x, self.p2.y)
        nx, ny = -dy / seg_len, dx / seg_len
        offset = (self.dim_point.x - self.p1.x) * nx + (self.dim_point.y - self.p1.y) * ny
        return (Point(self.p1.x + nx * offset, self.p1.y + ny * offset),
                Point(self.p2.x + nx * offset, self.p2.y + ny * offset))

    def bbox(self):
        dl1, dl2 = self.dimension_line_points()
        xs = [self.p1.x, self.p2.x, dl1.x, dl2.x]
        ys = [self.p1.y, self.p2.y, dl1.y, dl2.y]
        return (min(xs), min(ys), max(xs), max(ys))

    def endpoints(self):
        dl1, dl2 = self.dimension_line_points()
        return [self.p1, self.p2, dl1, dl2]

    def translate(self, dx, dy):
        self.p1.x += dx; self.p1.y += dy
        self.p2.x += dx; self.p2.y += dy
        self.dim_point.x += dx; self.dim_point.y += dy

    def to_dict(self):
        return {"kind": self.kind, "p1": self.p1.as_tuple(), "p2": self.p2.as_tuple(),
                "dim_point": self.dim_point.as_tuple(), "dim_style": self.dim_style,
                "measurement": self.measurement(), "layer": self.layer, "color": self.color}

    def clone(self):
        # Note: source_line_id is intentionally dropped - a mirrored/arrayed
        # copy is a new dimension in a new place; keeping the old link would
        # snap it back to the original source's position on the next sync.
        return DimensionEntity(Point(self.p1.x, self.p1.y), Point(self.p2.x, self.p2.y),
                                Point(self.dim_point.x, self.dim_point.y), dim_style=self.dim_style,
                                text_override=self.text_override, style_name=self.style_name, **self.style_kwargs())

    def reflect_across(self, a, b):
        self.p1 = _reflect_pt(self.p1, a, b)
        self.p2 = _reflect_pt(self.p2, a, b)
        self.dim_point = _reflect_pt(self.dim_point, a, b)

    def rotate_around(self, center, angle_deg):
        self.p1 = _rotate_pt(self.p1, center, angle_deg)
        self.p2 = _rotate_pt(self.p2, center, angle_deg)
        self.dim_point = _rotate_pt(self.dim_point, center, angle_deg)

    def scale_from(self, center, factor):
        self.p1 = _scale_pt(self.p1, center, factor)
        self.p2 = _scale_pt(self.p2, center, factor)
        self.dim_point = _scale_pt(self.dim_point, center, factor)


class HatchEntity(Entity):
    """Polygon fill with PAT line families, solid/gradient and nested islands.

    Optional source IDs keep selected closed-object outlines linked. Custom
    definitions are stored with the entity, independent of local PAT files.
    """
    kind = "HATCH"

    def __init__(self, boundary: List[Point], pattern: str = "LINES", angle: float = 45.0,
                 spacing: float = 5.0, source_entity_id: Optional[str] = None, holes=None,
                 pattern_scale=1.0, origin=None, double=False, island_style='normal',
                 pattern_definition=None, background_color=None, gradient_color='#0088ff',
                 source_hole_ids=None, boundary_mode='strict', loop_flags=None, **kwargs):
        super().__init__(**kwargs)
        self.boundary = boundary
        self.holes = holes or []
        self.pattern = pattern
        self.angle = angle
        self.spacing = spacing
        self.source_entity_id = source_entity_id
        self.pattern_scale = pattern_scale
        self.origin = origin or Point(0, 0)
        self.double = double
        self.island_style = island_style
        self.pattern_definition = pattern_definition or []
        self.background_color = background_color
        self.gradient_color = gradient_color
        self.source_hole_ids = source_hole_ids or []
        self.boundary_mode = boundary_mode
        self.loop_flags = list(loop_flags or [])
        from .hatching import validate_options
        validate_options(vars(self))

    def bbox(self):
        points = self.boundary + [p for loop in self.holes for p in loop]
        xs = [p.x for p in points]
        ys = [p.y for p in points]
        return (min(xs), min(ys), max(xs), max(ys))

    def endpoints(self):
        return list(self.boundary)

    def translate(self, dx, dy):
        for p in self.boundary + [p for hole in self.holes for p in hole]:
            p.x += dx
            p.y += dy
        self.origin = Point(self.origin.x+dx, self.origin.y+dy)

    def to_dict(self):
        return {"kind": self.kind, "boundary": [p.as_tuple() for p in self.boundary],
                "pattern": self.pattern, "angle": self.angle, "spacing": self.spacing,
                "layer": self.layer, "color": self.color}

    def clone(self):
        import copy
        clone = copy.deepcopy(self)
        clone.id = _new_id()
        clone.selected = False
        clone.source_entity_id = None
        clone.source_hole_ids = []
        return clone

    def reflect_across(self, a, b):
        self.boundary = [_reflect_pt(p, a, b) for p in self.boundary]
        self.holes = [[_reflect_pt(p,a,b) for p in hole] for hole in self.holes]
        # Mirror every family, including oblique offsets and dash phase.
        if self.pattern not in ('SOLID', 'GRADIENT_LINEAR', 'GRADIENT_RADIAL', 'GRADIENT_CONICAL'):
            from .hatching import definitions
            rows = definitions(self)
            reflected = []
            for angle, base, offset, dashes in rows:
                p = _reflect_pt(Point(*base), a, b)
                q = _reflect_pt(Point(base[0]+offset[0],base[1]+offset[1]),a,b)
                direction = _reflect_pt(Point(base[0]+math.cos(math.radians(angle)),base[1]+math.sin(math.radians(angle))),a,b)
                reflected.append([math.degrees(math.atan2(direction.y-p.y,direction.x-p.x)),p.as_tuple(),(q.x-p.x,q.y-p.y),dashes])
            self.pattern_definition=reflected; self.pattern='MIRRORED'; self.angle=0
            self.pattern_scale=1; self.origin=Point(0,0); self.double=False
        else:
            self.origin = _reflect_pt(self.origin,a,b)
            self.angle = 2*math.degrees(math.atan2(b.y-a.y,b.x-a.x))-self.angle

    def rotate_around(self, center, angle_deg):
        self.boundary = [_rotate_pt(p, center, angle_deg) for p in self.boundary]
        self.holes = [[_rotate_pt(p,center,angle_deg) for p in hole] for hole in self.holes]
        self.angle += angle_deg
        self.origin = _rotate_pt(self.origin, center, angle_deg)

    def scale_from(self, center, factor):
        self.boundary = [_scale_pt(p, center, factor) for p in self.boundary]
        self.holes = [[_scale_pt(p,center,factor) for p in hole] for hole in self.holes]
        self.pattern_scale *= abs(factor)
        self.origin = _scale_pt(self.origin,center,factor)
        if factor < 0: self.angle += 180


class SplineEntity(Entity):
    """True interpolating B-spline or rational control-point NURBS curve.

    Native records preserve degree, knot vectors and weights. Display sampling
    shares the same mathematical construction as the DXF curve exporter.
    """
    kind = "SPLINE"

    def __init__(self, points: List[Point], closed: bool = False, degree=3, knots=None, weights=None, curve_mode="fit", **kwargs):
        super().__init__(**kwargs)
        self.points = points
        self.closed = closed
        self.degree = min(degree, len(points)-1)
        self.knots = list(knots or [])
        self.weights = list(weights or [])
        self.curve_mode = curve_mode
        from .precision import spline_curve
        spline_curve(self)

    def _catmull_rom_samples(self, segments_per_span: int = 16) -> List[Point]:
        """Compatibility sampling entry point; uses the true stored B-spline."""
        from .precision import spline_curve
        curve = spline_curve(self)
        count = min(8192,max(32,(len(self.points)-1)*segments_per_span))
        parameters=list(curve.params(count))
        if self.curve_mode=='fit':
            pts=self.points+([self.points[0]] if self.closed else [])
            distances=[a.distance_to(b) for a,b in zip(pts,pts[1:])];total=sum(distances)
            if total>0:
                accumulated=0;parameters.append(0)
                for d in distances: accumulated+=d;parameters.append(accumulated/total)
        return [Point(p.x,p.y) for p in curve.points(sorted(set(parameters)))]

    def _legacy_catmull_samples(self, segments_per_span=16):
        pts = self.points
        if len(pts) < 2:
            return list(pts)
        if self.closed:
            ring = [pts[-1]] + pts + [pts[0], pts[1]]
        else:
            ring = [pts[0]] + pts + [pts[-1]]
        out = []
        span_count = len(pts) if self.closed else len(pts) - 1
        for i in range(span_count):
            p0, p1, p2, p3 = ring[i], ring[i + 1], ring[i + 2], ring[i + 3]
            for s in range(segments_per_span):
                t = s / segments_per_span
                t2, t3 = t * t, t * t * t
                x = 0.5 * ((2 * p1.x) + (-p0.x + p2.x) * t +
                           (2 * p0.x - 5 * p1.x + 4 * p2.x - p3.x) * t2 +
                           (-p0.x + 3 * p1.x - 3 * p2.x + p3.x) * t3)
                y = 0.5 * ((2 * p1.y) + (-p0.y + p2.y) * t +
                           (2 * p0.y - 5 * p1.y + 4 * p2.y - p3.y) * t2 +
                           (-p0.y + 3 * p1.y - 3 * p2.y + p3.y) * t3)
                out.append(Point(x, y))
        out.append(Point(pts[0].x, pts[0].y) if self.closed else Point(pts[-1].x, pts[-1].y))
        return out

    def bbox(self):
        samples = self._catmull_rom_samples(32)
        xs = [p.x for p in samples]
        ys = [p.y for p in samples]
        return (min(xs), min(ys), max(xs), max(ys))

    def endpoints(self):
        return list(self.points)

    def translate(self, dx, dy):
        for p in self.points:
            p.x += dx
            p.y += dy

    def to_dict(self):
        return {"kind": self.kind, "points": [p.as_tuple() for p in self.points],
                "closed": self.closed, "layer": self.layer, "color": self.color}

    def clone(self):
        return SplineEntity([Point(p.x, p.y) for p in self.points], closed=self.closed, degree=self.degree, knots=self.knots, weights=self.weights, curve_mode=self.curve_mode,
                             **self.style_kwargs())

    def reflect_across(self, a, b):
        self.points = [_reflect_pt(p, a, b) for p in self.points]

    def rotate_around(self, center, angle_deg):
        self.points = [_rotate_pt(p, center, angle_deg) for p in self.points]

    def scale_from(self, center, factor):
        self.points = [_scale_pt(p, center, factor) for p in self.points]

    def grip_points(self):
        return [(f"pt{i}", p) for i, p in enumerate(self.points)]


class BlockDefinition:
    """A named, reusable group of entities, defined once and placed many
    times via BlockReferenceEntity ("INSERT" in DXF terms). Entities are
    stored in block-local space (as if the block's own insertion point were
    the origin), so a reference just needs an insertion point + scale +
    rotation to place a full copy anywhere.

    If `source_filepath` is set, this definition is an **Xref**: its
    entities were loaded from an external DXF file rather than defined
    inline. `reload()` re-imports that file, and anything referencing this
    definition picks up the change the next time the document syncs
    (see Document.sync_associative) - the same mechanism that keeps
    associative dimensions/hatches current."""

    def __init__(self, name: str, entities: List[Entity], source_filepath: Optional[str] = None, source_scale=1.0, attributes=None):
        self.name = name
        self.entities = entities
        self.source_filepath = source_filepath
        self.source_scale = source_scale
        self.attributes = list(attributes or [])

    @property
    def is_xref(self) -> bool:
        return self.source_filepath is not None

    def reload(self):
        """Re-import an Xref's source file. No-op for a regular block."""
        if not self.source_filepath:
            return
        from . import dxf_io  # deferred: dxf_io imports geometry, so avoid a cycle at module load
        doc = dxf_io.import_dxf(self.source_filepath)
        self.entities = doc.entities
        from .unit_conversion import scale_geometry
        for entity in self.entities:
            scale_geometry(entity, self.source_scale)


class BlockReferenceEntity(Entity):
    """A placed instance of a BlockDefinition ("INSERT"/Xref-instance in DXF
    terms). Keeps a cache of transformed copies of the block's entities
    (`resolved_entities`) for rendering/bbox/snapping, rebuilt from the
    live BlockDefinition by `rebuild()` - called automatically whenever the
    document syncs (so editing a block definition, or reloading an Xref,
    propagates to every place it's inserted)."""
    kind = "INSERT"

    def __init__(self, block_name: str, insertion_point: Point, scale: float = 1.0,
                 rotation: float = 0.0, mirrored: bool = False, clip_boundary: Optional[List[Point]] = None, attributes=None, **kwargs):
        super().__init__(**kwargs)
        self.mirrored = mirrored
        self.attributes = dict(attributes or {})
        self.block_name = block_name
        self.insertion_point = insertion_point
        self.scale = scale
        self.rotation = rotation
        self.resolved_entities: List[Entity] = []
        # World-space clip polygon (XCLIP-style), or None for unclipped.
        # Approximate clipping only: an entity is kept whole if any of its
        # bbox corners/center fall inside the polygon, dropped otherwise -
        # not true geometric clipping at the boundary (see README).
        self.clip_boundary: Optional[List[Point]] = clip_boundary

    def rebuild(self, block_def: Optional[BlockDefinition]):
        if block_def is None:
            self.resolved_entities = []
            return
        resolved = []
        from .smart_blocks import attribute_entities
        for e in block_def.entities + attribute_entities(block_def, self.attributes):
            clone = e.clone()
            if self.mirrored:
                clone.reflect_across(Point(0, 0), Point(1, 0))
            if self.scale != 1.0:
                clone.scale_from(Point(0, 0), self.scale)
            if self.rotation != 0.0:
                clone.rotate_around(Point(0, 0), self.rotation)
            clone.translate(self.insertion_point.x, self.insertion_point.y)
            if self.clip_boundary is None or self._passes_clip(clone):
                resolved.append(clone)
        self.resolved_entities = resolved

    def _passes_clip(self, entity: "Entity") -> bool:
        from . import geom_ops
        x0, y0, x1, y1 = entity.bbox()
        test_points = [Point(x0, y0), Point(x1, y0), Point(x1, y1), Point(x0, y1),
                       Point((x0 + x1) / 2, (y0 + y1) / 2)]
        from .tolerance import bounds_overlap
        clip_box=(min(p.x for p in self.clip_boundary),min(p.y for p in self.clip_boundary),max(p.x for p in self.clip_boundary),max(p.y for p in self.clip_boundary))
        return bounds_overlap((x0,y0,x1,y1),clip_box)

    def bbox(self):
        if not self.resolved_entities:
            p=self.insertion_point
            return (p.x,p.y,p.x,p.y)
        pending=list(self.resolved_entities);bounds=None
        while pending:
            entity=pending.pop()
            if isinstance(entity,BlockReferenceEntity) and entity.resolved_entities:
                pending.extend(entity.resolved_entities);continue
            box=(entity.insertion_point.x,entity.insertion_point.y,entity.insertion_point.x,entity.insertion_point.y) if isinstance(entity,BlockReferenceEntity) else entity.bbox()
            bounds=box if bounds is None else (min(bounds[0],box[0]),min(bounds[1],box[1]),max(bounds[2],box[2]),max(bounds[3],box[3]))
        return bounds

    def endpoints(self):
        return [self.insertion_point]

    def _transform_tree(self, operation, *args):
        pending=[self]
        while pending:
            entity=pending.pop()
            if not isinstance(entity,BlockReferenceEntity):
                getattr(entity,operation)(*args);continue
            if operation=='translate':
                dx,dy=args;entity.insertion_point.x+=dx;entity.insertion_point.y+=dy
                if entity.clip_boundary:
                    for p in entity.clip_boundary:p.x+=dx;p.y+=dy
            elif operation=='reflect_across':
                a,b=args;entity.insertion_point=_reflect_pt(entity.insertion_point,a,b)
                entity.rotation=2*math.degrees(math.atan2(b.y-a.y,b.x-a.x))-entity.rotation
                entity.mirrored=not entity.mirrored
                if entity.clip_boundary:entity.clip_boundary=[_reflect_pt(p,a,b) for p in entity.clip_boundary]
            elif operation=='rotate_around':
                center,angle=args;entity.insertion_point=_rotate_pt(entity.insertion_point,center,angle);entity.rotation+=angle
                if entity.clip_boundary:entity.clip_boundary=[_rotate_pt(p,center,angle) for p in entity.clip_boundary]
            elif operation=='scale_from':
                center,factor=args;entity.insertion_point=_scale_pt(entity.insertion_point,center,factor);entity.scale*=factor
                if entity.clip_boundary:entity.clip_boundary=[_scale_pt(p,center,factor) for p in entity.clip_boundary]
            pending.extend(entity.resolved_entities)

    def translate(self, dx, dy):
        self._transform_tree('translate',dx,dy)

    def to_dict(self):
        d = {"kind": self.kind, "block_name": self.block_name,
             "insertion_point": self.insertion_point.as_tuple(),
             "scale": self.scale, "rotation": self.rotation,
             "layer": self.layer, "color": self.color}
        if self.clip_boundary:
            d["clip_boundary"] = [p.as_tuple() for p in self.clip_boundary]
        return d

    def _clone_header(self):
        return BlockReferenceEntity(self.block_name,Point(self.insertion_point.x,self.insertion_point.y),
            scale=self.scale,rotation=self.rotation,mirrored=self.mirrored,attributes=self.attributes,
            clip_boundary=[Point(p.x,p.y) for p in self.clip_boundary] if self.clip_boundary else None,
            **self.style_kwargs())

    def clone(self):
        result=self._clone_header();pending=[(self,result)]
        while pending:
            source,target=pending.pop()
            for child in source.resolved_entities:
                if isinstance(child,BlockReferenceEntity):
                    clone=child._clone_header();pending.append((child,clone))
                else:clone=child.clone()
                target.resolved_entities.append(clone)
        return result

    def __deepcopy__(self, memo):
        import copy
        if id(self) in memo:return memo[id(self)]
        result=self._clone_header();result.id=self.id;result.selected=self.selected
        memo[id(self)]=result;pending=[(self,result)]
        while pending:
            source,target=pending.pop()
            for child in source.resolved_entities:
                if isinstance(child,BlockReferenceEntity):
                    clone=memo.get(id(child))
                    if clone is None:
                        clone=child._clone_header();clone.id=child.id;clone.selected=child.selected
                        memo[id(child)]=clone;pending.append((child,clone))
                else:clone=copy.deepcopy(child,memo)
                target.resolved_entities.append(clone)
        return result

    def reflect_across(self, a, b):
        self._transform_tree('reflect_across',a,b)

    def rotate_around(self, center, angle_deg):
        self._transform_tree('rotate_around',center,angle_deg)

    def scale_from(self, center, factor):
        self._transform_tree('scale_from',center,factor)
