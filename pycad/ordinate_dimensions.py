"""Signed X/Y coordinate annotations relative to a per-annotation origin."""

from .geometry import Entity, DimensionEntity, Point


class OrdinateDimensionEntity(DimensionEntity):
    kind = "ORDINATE_DIMENSION"
    source_line_id = None

    def __init__(
        self,
        p1,
        p2,
        dim_point,
        dim_style="ordinate_x",
        text_override=None,
        style_name="Standard",
        source_entity_id=None,
        source_anchor=None,
        **kwargs,
    ):
        Entity.__init__(self, **kwargs)
        self.p1, self.p2, self.dim_point = p1, p2, dim_point
        self.dim_style, self.text_override, self.style_name = (
            dim_style,
            text_override,
            style_name,
        )
        self.source_entity_id, self.source_anchor = source_entity_id, source_anchor

    def measurement(self):
        return (
            self.p2.x - self.p1.x
            if self.dim_style == "ordinate_x"
            else self.p2.y - self.p1.y
        )

    def leader_points(self):
        elbow = (
            Point(self.p2.x, self.dim_point.y)
            if self.dim_style == "ordinate_x"
            else Point(self.dim_point.x, self.p2.y)
        )
        return self.p2, elbow, self.dim_point

    def dimension_line_points(self):
        return self.p2, self.dim_point

    def endpoints(self):
        return [self.p2, self.dim_point]

    def bbox(self):
        pts = self.leader_points()
        return (
            min(p.x for p in pts),
            min(p.y for p in pts),
            max(p.x for p in pts),
            max(p.y for p in pts),
        )

    def grip_points(self):
        return [("dim_point", self.dim_point)]

    def clone(self):
        return OrdinateDimensionEntity(
            *(Point(p.x, p.y) for p in (self.p1, self.p2, self.dim_point)),
            dim_style=self.dim_style,
            text_override=self.text_override,
            style_name=self.style_name,
            **self.style_kwargs(),
        )

    def association_status(self, document):
        if self.source_entity_id is None:
            return "Independent coordinate"
        from .annotation_links import anchor_point

        try:
            anchor_point(document.find_by_id(self.source_entity_id), self.source_anchor)
        except (ValueError, AttributeError):
            return "Source missing — last coordinate retained"
        return "Associated with " + self.source_anchor


def ordinate_geometry(entity, style):
    a, elbow, end = entity.leader_points()
    distance = a.distance_to(elbow)
    offset = min(distance, style["extension_offset"] * style["scale"])
    if distance > 1e-12:
        a = Point(
            a.x + (elbow.x - a.x) * offset / distance,
            a.y + (elbow.y - a.y) * offset / distance,
        )
    gap = style["text_gap"] * style["scale"]
    return (
        [(a, elbow), (elbow, end)],
        [],
        Point(end.x, end.y + gap),
        style["text_height"] * style["scale"],
    )
