"""Point-driven tools for curved dimensions and reference calibration."""

import math
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPen
from .geometry import Point, ArcEntity, LineEntity
from .tools import Tool, PREVIEW_COLOR
from .curved_dimensions import CurvedDimensionEntity
from .document import AddEntityCommand


class AngularDimensionTool(Tool):
    name = "DIMANGULAR"
    dim_style = "angular"

    def __init__(self, window):
        super().__init__(window)
        self.source_arc_id = None
        self.mode = "auto"
        selected = [e for e in window.canvas.selected_entities if type(e) is LineEntity]
        self.line_ids = (
            [e.id for e in selected]
            if self.dim_style == "angular" and len(selected) == 2
            else []
        )

    def status_prompt(self):
        if self.line_ids:
            return "DIMANGULAR: " + (
                "Pick second line"
                if len(self.line_ids) == 1
                else "Place dimension in the required angle sector"
            )
        if not self.points:
            return (
                "DIMANGULAR: Specify angle vertex"
                if self.mode == "points"
                else "DIMANGULAR: Pick line or arc, or enter Points / Lines / Arc"
            )
        prompts = (
            "Pick arc or specify angle vertex",
            "Specify first ray point",
            "Specify second ray point (counterclockwise from first)",
            "Specify dimension arc location",
        )
        return self.name + ": " + prompts[min(len(self.points), 3)]

    def _entity(self, point):
        from .validation import finite

        finite(point.x, "Dimension X")
        finite(point.y, "Dimension Y")
        if len(self.line_ids) == 2:
            from .annotation_links import line_angle_sector

            sources = [self.document.find_by_id(key) for key in self.line_ids]
            if any(src is None for src in sources):
                raise ValueError("A selected line was removed; cancel and select again")
            center, first, second, ids, signs = line_angle_sector(*sources, point)
            return CurvedDimensionEntity(
                center,
                first,
                second,
                point,
                source_line_ids=ids,
                line_directions=signs,
                style_name=self.document.current_dimstyle,
                layer=self.document.layers.current_layer,
            )
        return CurvedDimensionEntity(
            *(Point(p.x, p.y) for p in self.points),
            point,
            dim_style=self.dim_style,
            source_arc_id=self.source_arc_id,
            style_name=self.document.current_dimstyle,
            layer=self.document.layers.current_layer,
        )

    def on_click(self, x, y, snap_kind, button):
        if button != Qt.MouseButton.LeftButton.value:
            return
        p = Point(x, y)
        from .validation import finite

        finite(x, "Point X")
        finite(y, "Point Y")
        if len(self.line_ids) == 1:
            from .geom_ops import pick_entity
            from .annotation_links import line_angle_geometry

            src = pick_entity(
                [
                    e
                    for e in self.document.visible_entities()
                    if type(e) is LineEntity and e.id != self.line_ids[0]
                ],
                p,
                self.mw.canvas.snap_radius_px / self.mw.canvas.zoom,
            )
            if src is None:
                raise ValueError("Pick a different LINE entity")
            first = self.document.find_by_id(self.line_ids[0])
            if first is None:
                raise ValueError("The first line was removed; cancel and select again")
            line_angle_geometry(first, src)
            self.line_ids.append(src.id)
            return
        if len(self.line_ids) == 2:
            self.document.undo_stack.push(
                AddEntityCommand(self.document, self._entity(p), self.name)
            )
            self.finish()
            return
        if not self.points:
            from .geom_ops import pick_entity

            if self.mode in ("auto", "lines") and self.dim_style == "angular":
                line = pick_entity(
                    [
                        e
                        for e in self.document.visible_entities()
                        if type(e) is LineEntity
                    ],
                    p,
                    self.mw.canvas.snap_radius_px / self.mw.canvas.zoom,
                )
                if line:
                    if line.length() <= 1e-12:
                        raise ValueError("Pick a line with nonzero length")
                    self.line_ids.append(line.id)
                    return
                if self.mode == "lines":
                    raise ValueError("Pick a LINE entity")
            src = (
                pick_entity(
                    [
                        e
                        for e in self.document.visible_entities()
                        if isinstance(e, ArcEntity)
                    ],
                    p,
                    self.mw.canvas.snap_radius_px / self.mw.canvas.zoom,
                )
                if self.mode in ("auto", "arc") or self.dim_style == "arc_length"
                else None
            )
            if src:
                self.points = [Point(src.center.x, src.center.y), *src.endpoints()]
                self.source_arc_id = src.id
            elif self.dim_style == "arc_length" or self.mode == "arc":
                raise ValueError(
                    "Select a circular ARC entity; polylines and splines are not supported by DIMARC"
                )
            else:
                self.points.append(p)
        elif len(self.points) < 3:
            if self.points[0].distance_to(p) <= 1e-12:
                raise ValueError("A ray point must differ from the vertex")
            if len(self.points) == 2:
                a = math.atan2(
                    self.points[1].y - self.points[0].y,
                    self.points[1].x - self.points[0].x,
                )
                b = math.atan2(y - self.points[0].y, x - self.points[0].x)
                sweep = (b - a) % math.tau
                if sweep < 1e-10 or math.tau - sweep < 1e-10:
                    raise ValueError("Specify a nonzero angle smaller than 360 degrees")
            self.points.append(p)
        else:
            if self.points[0].distance_to(p) <= 1e-12:
                raise ValueError("Place the dimension arc away from its center")
            self.document.undo_stack.push(
                AddEntityCommand(self.document, self._entity(p), self.name)
            )
            self.finish()

    def on_text_input(self, text):
        keyword = text.strip().upper()
        modes = {
            "P": "points",
            "POINTS": "points",
            "L": "lines",
            "LINES": "lines",
            "A": "arc",
            "ARC": "arc",
        }
        if self.dim_style == "angular" and keyword in modes:
            self.mode = modes[keyword]
            self.points, self.line_ids = [], []
            self.source_arc_id = None
            return
        p = self.parse_point(text, self.points[-1] if self.points else None)
        if p is None:
            raise ValueError("Enter x,y, @dx,dy or @distance<angle")
        if self.dim_style == "angular" and not self.line_ids and not self.points:
            # Explicit coordinates are independent points, even over existing geometry.
            self.mode = "points"
        elif len(self.line_ids) == 1:
            raise ValueError("Pick the second line with the mouse")
        self.on_click(p.x, p.y, "", Qt.MouseButton.LeftButton.value)

    def draw_preview(self, painter, canvas):
        current = self.mw.current_world_pos
        if not current:
            return
        painter.setPen(QPen(PREVIEW_COLOR, 1, Qt.PenStyle.DashLine))
        if self.line_ids:
            for key in self.line_ids:
                src = self.document.find_by_id(key)
                if src is not None:
                    painter.drawLine(
                        canvas.world_to_screen(src.p1.x, src.p1.y),
                        canvas.world_to_screen(src.p2.x, src.p2.y),
                    )
            if len(self.line_ids) == 2:
                try:
                    canvas._draw_dimension(painter, self._entity(Point(*current)))
                except ValueError:
                    pass
            return
        if not self.points:
            return
        if len(self.points) == 3:
            canvas._draw_dimension(painter, self._entity(Point(*current)))
        else:
            c = self.points[0]
            painter.drawLine(
                canvas.world_to_screen(c.x, c.y), canvas.world_to_screen(*current)
            )
            if len(self.points) == 2:
                p = self.points[1]
                painter.drawLine(
                    canvas.world_to_screen(c.x, c.y), canvas.world_to_screen(p.x, p.y)
                )


class ArcLengthDimensionTool(AngularDimensionTool):
    name = "DIMARC"
    dim_style = "arc_length"

    def status_prompt(self):
        return "DIMARC: " + (
            "Pick a circular arc"
            if not self.points
            else "Specify dimension arc location"
        )


class OrdinateDimensionTool(Tool):
    name = "DIMORDINATE"

    def __init__(self, window):
        super().__init__(window)
        self.origin = Point(0, 0)
        self.axis = None
        self.origin_pending = False
        self.source_entity_id = self.source_anchor = None

    def status_prompt(self):
        if self.origin_pending:
            return "DIMORDINATE: Specify datum origin"
        if not self.points:
            return f"DIMORDINATE: Pick feature point; X / Y / Origin (datum {self.origin.x:g},{self.origin.y:g})"
        return "DIMORDINATE: Place leader endpoint; X / Y sets measured axis"

    def _entity(self, point):
        from .ordinate_dimensions import OrdinateDimensionEntity
        from .validation import finite

        finite(point.x, "Leader X")
        finite(point.y, "Leader Y")
        feature = self.points[0]
        if feature.distance_to(point) <= 1e-12:
            raise ValueError("Place the leader away from its feature point")
        axis = self.axis or (
            "x" if abs(point.y - feature.y) >= abs(point.x - feature.x) else "y"
        )
        return OrdinateDimensionEntity(
            Point(self.origin.x, self.origin.y),
            Point(feature.x, feature.y),
            point,
            dim_style="ordinate_" + axis,
            style_name=self.document.current_dimstyle,
            source_entity_id=self.source_entity_id,
            source_anchor=self.source_anchor,
            layer=self.document.layers.current_layer,
        )

    def _accept(self, point, associate):
        from .validation import finite

        finite(point.x, "Point X")
        finite(point.y, "Point Y")
        if self.origin_pending:
            self.origin, self.origin_pending = point, False
        elif not self.points:
            from .annotation_links import pick_anchor

            link = (
                pick_anchor(
                    self.document,
                    point,
                    self.mw.canvas.snap_radius_px / self.mw.canvas.zoom,
                )
                if associate
                else None
            )
            if link:
                point, self.source_entity_id, self.source_anchor = link
            self.points.append(point)
        else:
            self.document.undo_stack.push(
                AddEntityCommand(self.document, self._entity(point), self.name)
            )
            self.finish()

    def on_click(self, x, y, snap_kind, button):
        if button == Qt.MouseButton.LeftButton.value:
            self._accept(Point(x, y), True)

    def on_text_input(self, text):
        keyword = text.strip().upper()
        if keyword in ("X", "Y"):
            self.axis = keyword.lower()
            return
        if keyword in ("O", "ORIGIN"):
            self.origin_pending = True
            return
        point = self.parse_point(text, self.points[-1] if self.points else self.origin)
        if point is None:
            raise ValueError("Enter X, Y, Origin, or a coordinate")
        self._accept(point, False)

    def draw_preview(self, painter, canvas):
        if self.points and self.mw.current_world_pos and not self.origin_pending:
            painter.setPen(QPen(PREVIEW_COLOR, 1, Qt.PenStyle.DashLine))
            try:
                canvas._draw_dimension(
                    painter, self._entity(Point(*self.mw.current_world_pos))
                )
            except ValueError:
                pass


class UnderlayCalibrateTool(Tool):
    name = "UNDERLAYCALIBRATE"

    def __init__(self, window):
        super().__init__(window)
        records = [
            r for r in self.document.underlays if r["visible"] and not r["locked"]
        ]
        self.underlay_id = records[0]["id"] if len(records) == 1 else None

    def status_prompt(self):
        if not self.underlay_id:
            return "Choose a reference and Calibrate in UNDERLAYS"
        return (
            "Calibrate: "
            + (
                "Pick first reference point",
                "Pick second reference point",
                f"Enter known distance in {self.document.units}; Enter to apply",
            )[min(len(self.points), 2)]
        )

    def on_click(self, x, y, snap_kind, button):
        if button != Qt.MouseButton.LeftButton.value:
            return
        if not self.underlay_id:
            raise ValueError("Use UNDERLAYS to choose a reference to calibrate")
        if len(self.points) < 2:
            p = Point(x, y)
            if self.points and p.distance_to(self.points[0]) <= 1e-12:
                raise ValueError("Pick two distinct reference points")
            self.points.append(p)

    def on_text_input(self, text):
        if len(self.points) < 2:
            p = self.parse_point(text, self.points[-1] if self.points else None)
            if p is None:
                raise ValueError("Pick a point or enter x,y")
            self.on_click(p.x, p.y, "", Qt.MouseButton.LeftButton.value)
        else:
            from .underlays import calibrate

            factor = calibrate(
                self.document,
                self.underlay_id,
                self.points[0].as_tuple(),
                self.points[1].as_tuple(),
                float(text),
            )
            self.mw.command_history.appendPlainText(
                f"Underlay calibrated ×{factor:.9g}. The first reference point stayed fixed. Undo restores the previous scale."
            )
            self.finish()

    def draw_preview(self, painter, canvas):
        if not self.points or not self.mw.current_world_pos:
            return
        a = self.points[0]
        b = (
            self.points[1]
            if len(self.points) == 2
            else Point(*self.mw.current_world_pos)
        )
        painter.setPen(QPen(PREVIEW_COLOR, 1, Qt.PenStyle.DashLine))
        painter.drawLine(
            canvas.world_to_screen(a.x, a.y), canvas.world_to_screen(b.x, b.y)
        )


PRECISION_TOOLS = {
    c.name: c
    for c in (
        AngularDimensionTool,
        ArcLengthDimensionTool,
        OrdinateDimensionTool,
        UnderlayCalibrateTool,
    )
}
