"""Angular and arc-length annotations, with shared plot/export primitives."""

import math
from .geometry import Entity, DimensionEntity, Point, _rotate_pt, _reflect_pt, _scale_pt


class CurvedDimensionEntity(DimensionEntity):
    kind = "CURVED_DIMENSION"
    source_line_id = None

    def __init__(
        self,
        center,
        p1,
        p2,
        dim_point,
        dim_style="angular",
        text_override=None,
        style_name="Standard",
        source_arc_id=None,
        source_line_ids=None,
        line_directions=None,
        **kwargs,
    ):
        Entity.__init__(self, **kwargs)
        self.center, self.p1, self.p2, self.dim_point = center, p1, p2, dim_point
        self.dim_style, self.text_override, self.style_name = (
            dim_style,
            text_override,
            style_name,
        )
        self.source_arc_id = source_arc_id
        self.source_line_ids = list(source_line_ids or [])
        self.line_directions = list(line_directions or [])

    def association_status(self, document):
        if self.source_line_ids:
            from .annotation_links import line_angle_geometry

            sources = [document.find_by_id(key) for key in self.source_line_ids]
            if any(source is None for source in sources):
                return "Source missing — last angle retained"
            try:
                center, _, _ = line_angle_geometry(*sources, self.line_directions)
                if center.distance_to(self.dim_point) <= 1e-12:
                    return "Placement is at intersection — last angle retained"
            except ValueError as error:
                return str(error) + " — last angle retained"
            return "Associated with two lines"
        if self.source_arc_id:
            from .geometry import ArcEntity

            return (
                "Associated with arc"
                if isinstance(document.find_by_id(self.source_arc_id), ArcEntity)
                else "Source missing — last angle retained"
            )
        return "Independent angle"

    def angles(self):
        start = math.atan2(self.p1.y - self.center.y, self.p1.x - self.center.x)
        end = math.atan2(self.p2.y - self.center.y, self.p2.x - self.center.x)
        return start, (end - start) % math.tau

    def measurement(self):
        sweep = self.angles()[1]
        return (
            math.degrees(sweep)
            if self.dim_style == "angular"
            else self.center.distance_to(self.p1) * sweep
        )

    def label_text(self):
        from .dimstyles import dimension_label, DEFAULT_STYLE

        return dimension_label(self, DEFAULT_STYLE)

    def arc_points(self):
        start, sweep = self.angles()
        radius = self.center.distance_to(self.dim_point)
        count = max(2, math.ceil(math.degrees(sweep) / 2))
        return [
            Point(
                self.center.x + radius * math.cos(start + sweep * i / count),
                self.center.y + radius * math.sin(start + sweep * i / count),
            )
            for i in range(count + 1)
        ]

    def dimension_line_points(self):
        pts = self.arc_points()
        return pts[0], pts[-1]

    def bbox(self):
        points = [self.center, self.p1, self.p2, self.dim_point, *self.arc_points()]
        return (
            min(p.x for p in points),
            min(p.y for p in points),
            max(p.x for p in points),
            max(p.y for p in points),
        )

    def endpoints(self):
        return [self.center, self.p1, self.p2, *self.dimension_line_points()]

    def grip_points(self):
        return [("dim_point", self.dim_point)]

    def translate(self, dx, dy):
        for p in (self.center, self.p1, self.p2, self.dim_point):
            p.x += dx
            p.y += dy

    def clone(self):
        return CurvedDimensionEntity(
            *(Point(p.x, p.y) for p in (self.center, self.p1, self.p2, self.dim_point)),
            dim_style=self.dim_style,
            text_override=self.text_override,
            style_name=self.style_name,
            **self.style_kwargs(),
        )

    def reflect_across(self, a, b):
        self.center, self.p1, self.p2, self.dim_point = [
            _reflect_pt(p, a, b)
            for p in (self.center, self.p2, self.p1, self.dim_point)
        ]
        self.source_arc_id = None
        self.source_line_ids = []
        self.line_directions = []

    def rotate_around(self, center, angle_deg):
        self.center, self.p1, self.p2, self.dim_point = [
            _rotate_pt(p, center, angle_deg)
            for p in (self.center, self.p1, self.p2, self.dim_point)
        ]

    def scale_from(self, center, factor):
        self.center, self.p1, self.p2, self.dim_point = [
            _scale_pt(p, center, factor)
            for p in (self.center, self.p1, self.p2, self.dim_point)
        ]

    def to_dict(self):
        result = super().to_dict()
        result["center"] = self.center.as_tuple()
        return result


def curved_geometry(entity, style):
    points = entity.arc_points()
    lines = list(zip(points, points[1:]))
    fills = []
    size = style["arrow_size"] * style["scale"]
    for tip, toward in ((points[0], points[1]), (points[-1], points[-2])):
        length = tip.distance_to(toward)
        if length < 1e-12:
            continue
        ux, uy = (toward.x - tip.x) / length, (toward.y - tip.y) / length
        p = Point(tip.x + size * (ux - 0.35 * uy), tip.y + size * (uy + 0.35 * ux))
        q = Point(tip.x + size * (ux + 0.35 * uy), tip.y + size * (uy - 0.35 * ux))
        if style["arrow_type"] == "Closed":
            fills.append([tip, p, q])
        elif style["arrow_type"] == "Open":
            lines.extend([(tip, p), (tip, q)])
        else:
            dx, dy = (ux - uy) * size * 0.4, (uy + ux) * size * 0.4
            lines.append((Point(tip.x - dx, tip.y - dy), Point(tip.x + dx, tip.y + dy)))
    for source, target in ((entity.p1, points[0]), (entity.p2, points[-1])):
        distance = source.distance_to(target)
        if distance > 1e-12:
            ux, uy = (target.x - source.x) / distance, (target.y - source.y) / distance
            offset = min(style["extension_offset"] * style["scale"], distance)
            beyond = style["extension_beyond"] * style["scale"]
            lines.append(
                (
                    Point(source.x + ux * offset, source.y + uy * offset),
                    Point(target.x + ux * beyond, target.y + uy * beyond),
                )
            )
    angle = sum((entity.angles()[0], entity.angles()[1] / 2))
    radius = (
        entity.center.distance_to(entity.dim_point) + style["text_gap"] * style["scale"]
    )
    anchor = Point(
        entity.center.x + radius * math.cos(angle),
        entity.center.y + radius * math.sin(angle),
    )
    return lines, fills, anchor, style["text_height"] * style["scale"]
