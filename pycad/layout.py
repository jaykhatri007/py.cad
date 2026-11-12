"""
layout.py
Paper Space layouts: named sheets with a fixed page size, each showing one
or more Viewports onto Model Space at a chosen scale. This is the "other
half" of a CAD file alongside Model Space - the part that maps to a real,
to-scale printed/plotted sheet.

Viewports start fitted to model extents. The viewport properties and sheet
manager control their centers/scales; physical paper dimensions remain in mm.
Per-viewport visibility/color overrides and title-block fields are native feature
tables in the drawing. Publishing uses the same vector rendering path.
"""
from typing import List, Optional
from .geometry import Point


class Viewport:
    """One window onto Model Space, placed on a Layout's paper.
    (x, y, width, height) are in paper units, with (x, y) the bottom-left
    corner - matching the paper coordinate convention the rest of PyCAD
    uses (Y increases upward). `center` is the Model Space point shown at
    the viewport's center, and `scale` is paper-units-per-model-unit
    (e.g. a 1:100 drawing scale is `scale=0.01`)."""

    def __init__(self, x: float, y: float, width: float, height: float,
                 center: Point, scale: float = 1.0):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.center = center
        self.scale = scale

    def model_to_paper(self, model_point: Point) -> Point:
        """Where a Model Space point lands within this viewport's paper rect."""
        px = (self.x + self.width / 2) + (model_point.x - self.center.x) * self.scale
        py = (self.y + self.height / 2) + (model_point.y - self.center.y) * self.scale
        return Point(px, py)


class Layout:
    """A named Paper Space sheet. `page_width`/`page_height` are in the
    same drawing units as everything else (so a 297x210 sheet is a 297x210
    unit sheet - if your drawing is in mm, that's an A4 landscape page)."""

    def __init__(self, name: str, page_width: float = 297.0, page_height: float = 210.0):
        self.name = name
        self.page_width = page_width
        self.page_height = page_height
        self.viewports: List[Viewport] = []

    def add_default_viewport(self, model_bbox, margin_fraction: float = 0.05) -> Viewport:
        """Add a single viewport sized to fill most of the page, scaled and
        centered to fit the given Model Space bounding box
        (min_x, min_y, max_x, max_y). This is the "zoom to fit" a new
        layout gets automatically so it's useful the moment it's created."""
        margin_x = self.page_width * margin_fraction
        margin_y = self.page_height * margin_fraction
        vp_width = self.page_width - 2 * margin_x
        vp_height = self.page_height - 2 * margin_y
        vp = self.add_viewport_at(margin_x, margin_y, vp_width, vp_height, model_bbox)
        return vp

    def add_viewport_at(self, x: float, y: float, width: float, height: float, model_bbox) -> Viewport:
        """Add a viewport at an explicit paper-space rectangle, auto-scaled
        and centered to fit the given Model Space bounding box
        (min_x, min_y, max_x, max_y). This is what backs both the
        auto-placed default viewport and Layout -> Add Viewport, which lets
        a single sheet carry more than one view of the model."""
        min_x, min_y, max_x, max_y = model_bbox
        model_w = max(max_x - min_x, 1e-6)
        model_h = max(max_y - min_y, 1e-6)
        scale = min(width / model_w, height / model_h) * 0.9
        center = Point((min_x + max_x) / 2, (min_y + max_y) / 2)
        vp = Viewport(x, y, width, height, center, scale)
        self.viewports.append(vp)
        return vp

    def remove_viewport(self, vp: Viewport):
        if vp in self.viewports:
            self.viewports.remove(vp)
