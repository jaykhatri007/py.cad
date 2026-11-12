"""Additional point-driven drafting commands using the existing undo model."""

import math
import uuid

from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import QPen, QColor
from PyQt6.QtWidgets import QInputDialog

from .tools import Tool
from .geometry import (
    Point,
    LineEntity,
    PolylineEntity,
    SplineEntity,
    CircleEntity,
    ArcEntity,
    RayEntity,
    TextEntity,
    DimensionEntity,
    BlockDefinition,
    BlockReferenceEntity,
)
from .document import (
    AddEntityCommand,
    AddBlockCommand,
    SetPointCommand,
    TranslateEntitiesCommand,
    SetAttrCommand,
)
from .geom_ops import pick_entity

LEFT = Qt.MouseButton.LeftButton.value


def pick(tool, x, y, types=None):
    entities = tool.document.visible_entities()
    if types:
        entities = [e for e in entities if isinstance(e, types)]
    return pick_entity(
        entities, Point(x, y), tool.mw.canvas.snap_radius_px / tool.mw.canvas.zoom
    )


def add_geometry_block(document, entities, prefix, insertion=None):
    """One undo step; geometry remains editable with the existing block editor."""
    name = "PYCAD_" + prefix + "_" + uuid.uuid4().hex[:10]
    block = BlockDefinition(name, entities)
    ref = BlockReferenceEntity(
        name, insertion or Point(0, 0), layer=document.layers.current_layer
    )
    document.undo_stack.beginMacro(prefix.title())
    document.undo_stack.push(AddBlockCommand(document, block))
    document.undo_stack.push(AddEntityCommand(document, ref, prefix.title()))
    document.undo_stack.endMacro()
    return ref


def table_geometry(rows, cell_width=30.0, cell_height=8.0, text_height=2.5, layer="0"):
    if not rows or not any(rows):
        raise ValueError("Enter at least one table cell.")
    columns = max(map(len, rows))
    if len(rows) > 200 or columns > 30:
        raise ValueError("Tables are limited to 200 rows and 30 columns.")
    if not (0 < text_height < cell_height and cell_width > text_height * 2):
        raise ValueError("Cell width and height must leave room for the text.")
    result = []
    width, height = columns * cell_width, len(rows) * cell_height
    for r in range(len(rows) + 1):
        result.append(
            LineEntity(
                Point(0, -r * cell_height), Point(width, -r * cell_height), layer=layer
            )
        )
    for c in range(columns + 1):
        result.append(
            LineEntity(
                Point(c * cell_width, 0), Point(c * cell_width, -height), layer=layer
            )
        )
    # Shrink long cell values to fit; retain the complete text for export/editing.
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            text = str(value).replace("\n", " ")
            size = min(
                text_height, (cell_width - text_height) / max(1, len(text)) / 0.65
            )
            result.append(
                TextEntity(
                    Point(
                        c * cell_width + text_height / 2,
                        -r * cell_height - cell_height / 2 - size / 2,
                    ),
                    text,
                    size,
                    layer=layer,
                )
            )
    return result


class PointInputTool(Tool):
    def on_text_input(self, text):
        point = self.parse_point(text, self.points[-1] if self.points else None)
        if point is None:
            raise ValueError("Enter x,y or @dx,dy, or pick a point.")
        self.on_click(point.x, point.y, "", LEFT)

    def draw_preview(self, painter, canvas):
        if self.points and self.mw.current_world_pos:
            painter.setPen(QPen(QColor("#60d6bd"), 1, Qt.PenStyle.DashLine))
            p = self.points[-1]
            painter.drawLine(
                canvas.world_to_screen(p.x, p.y),
                canvas.world_to_screen(*self.mw.current_world_pos),
            )


class StretchTool(PointInputTool):
    name = "STRETCH"

    def __init__(self, mw):
        super().__init__(mw)
        self.vertices = []
        self.whole = []

    def status_prompt(self):
        return (
            "STRETCH: First crossing-box corner",
            "STRETCH: Opposite crossing-box corner",
            "STRETCH: Base point",
            "STRETCH: Target point",
        )[min(len(self.points), 3)]

    def on_click(self, x, y, snap_kind, button):
        if button != LEFT:
            return
        self.points.append(Point(x, y))
        if len(self.points) == 2:
            a, b = self.points
            x0, x1 = sorted((a.x, b.x))
            y0, y1 = sorted((a.y, b.y))
            inside = lambda p: x0 <= p.x <= x1 and y0 <= p.y <= y1
            for e in self.document.editable_entities():
                if isinstance(e, RayEntity):
                    continue
                ex0, ey0, ex1, ey1 = e.bbox()
                if x0 <= ex0 <= ex1 <= x1 and y0 <= ey0 <= ey1 <= y1:
                    self.whole.append(e)
                elif isinstance(e, LineEntity):
                    self.vertices.extend(p for p in (e.p1, e.p2) if inside(p))
                elif isinstance(e, (PolylineEntity, SplineEntity)):
                    self.vertices.extend(p for p in e.points if inside(p))
            if not self.vertices and not self.whole:
                self.mw.command_history.appendPlainText(
                    "No editable vertices or enclosed objects in crossing box."
                )
                self.finish()
        elif len(self.points) == 4:
            base, target = self.points[2:]
            dx, dy = target.x - base.x, target.y - base.y
            if dx or dy:
                self.document.undo_stack.beginMacro("Stretch")
                if self.whole:
                    self.document.undo_stack.push(
                        TranslateEntitiesCommand(
                            self.document,
                            self.whole,
                            dx,
                            dy,
                            "Stretch enclosed objects",
                        )
                    )
                for p in self.vertices:
                    self.document.undo_stack.push(
                        SetPointCommand(
                            self.document,
                            p,
                            (p.x, p.y),
                            (p.x + dx, p.y + dy),
                            "Stretch vertex",
                        )
                    )
                self.document.undo_stack.endMacro()
            self.finish()

    def draw_preview(self, painter, canvas):
        if len(self.points) in (1, 2) and self.mw.current_world_pos:
            a = self.points[0]
            b = (
                self.points[1]
                if len(self.points) == 2
                else Point(*self.mw.current_world_pos)
            )
            painter.setPen(QPen(QColor("#60d6bd"), 1, Qt.PenStyle.DashLine))
            painter.drawRect(
                QRectF(
                    canvas.world_to_screen(a.x, a.y), canvas.world_to_screen(b.x, b.y)
                ).normalized()
            )
        else:
            super().draw_preview(painter, canvas)


class MatchLayerTool(Tool):
    name = "LAYMCH"
    prompt = "MATCH LAYER: Select target objects before starting, then pick the source object"

    def on_click(self, x, y, snap_kind, button):
        if button != LEFT:
            return
        source = pick(self, x, y)
        if source is None:
            return
        targets = [
            e
            for e in self.mw.canvas.selected_entities
            if e in self.document.editable_entities() and e.layer != source.layer
        ]
        if targets:
            self.document.undo_stack.beginMacro("Match layer")
            for e in targets:
                self.document.undo_stack.push(
                    SetAttrCommand(
                        self.document, e, "layer", e.layer, source.layer, "Match layer"
                    )
                )
            self.document.undo_stack.endMacro()
        else:
            self.mw.command_history.appendPlainText(
                "Select editable target objects before LAYMCH."
            )
        self.finish()


class MTextTool(PointInputTool):
    name = "MTEXT"
    prompt = "MTEXT: Specify insertion point (plain multiline text)"

    def on_click(self, x, y, snap_kind, button):
        if button != LEFT:
            return
        text, ok = QInputDialog.getMultiLineText(
            self.mw, "Multiline text", "Text (plain formatting):"
        )
        if ok and text:
            from .textstyles import make_text
            e = make_text(self.document, Point(x, y), text, layer=self.document.layers.current_layer)
            self.document.undo_stack.push(
                AddEntityCommand(self.document, e, "Multiline text")
            )
        self.finish()


class PlaceTableTool(PointInputTool):
    name = "TABLEPLACE"
    prompt = "TABLE: Specify top-left insertion point (static table block)"

    def on_click(self, x, y, snap_kind, button):
        if button == LEFT:
            geometry = getattr(self.mw, "pending_table_geometry", None)
            if geometry:
                add_geometry_block(self.document, geometry, "TABLE", Point(x, y))
                self.mw.pending_table_geometry = None
            self.finish()


class LeaderTool(PointInputTool):
    name = "LEADER"

    def status_prompt(self):
        return (
            "LEADER: Pick arrow tip"
            if not self.points
            else "LEADER: Pick text landing (static annotation)"
        )

    def on_click(self, x, y, snap_kind, button):
        if button != LEFT:
            return
        if not self.points:
            self.points.append(Point(x, y))
            return
        tip, landing = self.points[0], Point(x, y)
        length = tip.distance_to(landing)
        if length < 1e-9:
            raise ValueError("The leader needs two distinct points.")
        text, ok = QInputDialog.getMultiLineText(self.mw, "Leader", "Annotation text:")
        if ok and text:
            ux, uy = (landing.x - tip.x) / length, (landing.y - tip.y) / length
            arrow = min(2.5, length / 4)
            style = {"layer": self.document.layers.current_layer}
            geometry = [
                LineEntity(Point(tip.x, tip.y), landing, **style),
                LineEntity(
                    Point(tip.x, tip.y),
                    Point(
                        tip.x + arrow * (ux + 0.35 * uy),
                        tip.y + arrow * (uy - 0.35 * ux),
                    ),
                    **style,
                ),
                LineEntity(
                    Point(tip.x, tip.y),
                    Point(
                        tip.x + arrow * (ux - 0.35 * uy),
                        tip.y + arrow * (uy + 0.35 * ux),
                    ),
                    **style,
                ),
                TextEntity(Point(landing.x + 1, landing.y + 1), text, 2.5, **style),
            ]
            add_geometry_block(self.document, geometry, "LEADER")
        self.finish()


class CenterMarkTool(Tool):
    name = "CENTERMARK"
    prompt = "CENTERMARK: Pick a circle or arc (static center mark)"

    def on_click(self, x, y, snap_kind, button):
        if button != LEFT:
            return
        e = pick(self, x, y, (CircleEntity, ArcEntity))
        if e is None:
            return
        c, r = e.center, e.radius * 1.15
        self.document.undo_stack.beginMacro("Center mark")
        for a, b in [
            (Point(c.x - r, c.y), Point(c.x + r, c.y)),
            (Point(c.x, c.y - r), Point(c.x, c.y + r)),
        ]:
            self.document.undo_stack.push(
                AddEntityCommand(
                    self.document,
                    LineEntity(
                        a,
                        b,
                        layer=self.document.layers.current_layer,
                        linetype="DASHDOT",
                    ),
                    "Center mark",
                )
            )
        self.document.undo_stack.endMacro()
        self.finish()


class CenterlineTool(Tool):
    name = "CENTERLINE"

    def __init__(self, mw):
        super().__init__(mw)
        self.first = None

    def status_prompt(self):
        return (
            "CENTERLINE: Pick first line"
            if self.first is None
            else "CENTERLINE: Pick second parallel line (static centerline)"
        )

    def on_click(self, x, y, snap_kind, button):
        if button != LEFT:
            return
        e = pick(self, x, y, (LineEntity,))
        if e is None or isinstance(e, RayEntity):
            return
        if self.first is None:
            self.first = e
            return
        a = self.first
        if a is e:
            raise ValueError("Pick a different line.")
        ax, ay = a.p2.x - a.p1.x, a.p2.y - a.p1.y
        bx, by = e.p2.x - e.p1.x, e.p2.y - e.p1.y
        lengths = math.hypot(ax, ay) * math.hypot(bx, by)
        if lengths < 1e-12 or abs(ax * by - ay * bx) > lengths * 1e-6:
            raise ValueError(
                "This centerline tool requires two nonzero parallel lines."
            )
        b1, b2 = (e.p1, e.p2) if ax * bx + ay * by >= 0 else (e.p2, e.p1)
        p1 = Point((a.p1.x + b1.x) / 2, (a.p1.y + b1.y) / 2)
        p2 = Point((a.p2.x + b2.x) / 2, (a.p2.y + b2.y) / 2)
        self.document.undo_stack.push(
            AddEntityCommand(
                self.document,
                LineEntity(
                    p1, p2, layer=self.document.layers.current_layer, linetype="DASHDOT"
                ),
                "Centerline",
            )
        )
        self.finish()


class RadiusMeasureTool(Tool):
    name = "MEASURERADIUS"
    prompt = "RADIUS: Pick a circle or arc"

    def on_click(self, x, y, snap_kind, button):
        if button != LEFT:
            return
        e = pick(self, x, y, (CircleEntity, ArcEntity))
        if e:
            self.mw.command_history.appendPlainText(
                f"RADIUS = {e.radius:.6f}  DIAMETER = {2 * e.radius:.6f} {self.document.units}"
            )
            self.finish()


class AngleMeasureTool(PointInputTool):
    name = "MEASUREANGLE"

    def status_prompt(self):
        return (
            "ANGLE: Pick vertex",
            "ANGLE: Pick point on first ray",
            "ANGLE: Pick point on second ray",
        )[min(len(self.points), 2)]

    def on_click(self, x, y, snap_kind, button):
        if button != LEFT:
            return
        point = Point(x, y)
        if self.points and point.distance_to(self.points[0]) < 1e-12:
            raise ValueError("The ray point must differ from the vertex.")
        self.points.append(point)
        if len(self.points) == 3:
            v, a, b = self.points
            angle = math.degrees(
                math.atan2(
                    abs((a.x - v.x) * (b.y - v.y) - (a.y - v.y) * (b.x - v.x)),
                    (a.x - v.x) * (b.x - v.x) + (a.y - v.y) * (b.y - v.y),
                )
            )
            self.mw.command_history.appendPlainText(
                f"ANGLE = {angle:.6f} degrees (smaller included angle)"
            )
            self.finish()


def entity_metrics(e):
    values = {}
    if isinstance(e, RayEntity):
        values["extent"] = "infinite"
    elif isinstance(e, LineEntity):
        values["length"] = e.p1.distance_to(e.p2)
    elif isinstance(e, ArcEntity):
        values["radius"] = e.radius
        values["length"] = math.radians((e.end_angle - e.start_angle) % 360) * e.radius
    elif isinstance(e, CircleEntity):
        values.update(
            radius=e.radius,
            circumference=2 * math.pi * e.radius,
            area=math.pi * e.radius**2,
        )
    elif isinstance(e,PolylineEntity):
        from .precision import polyline_measure
        length,area=polyline_measure(e);values['length']=length
        if e.closed: values['area']=area
    elif isinstance(e, DimensionEntity):
        values["measurement"] = e.measurement()
    x0, y0, x1, y1 = e.bbox()
    values.update(width=x1 - x0, height=y1 - y0)
    return values


class QuickMeasureTool(Tool):
    name = "QUICKMEASURE"
    prompt = "QUICK MEASURE: Pick an entity (Esc to finish)"

    def on_click(self, x, y, snap_kind, button):
        if button != LEFT:
            return
        e = pick(self, x, y)
        if e:
            values = ", ".join(
                f"{k}={v:.6f}" if isinstance(v, (int, float)) else f"{k}={v}"
                for k, v in entity_metrics(e).items()
            )
            self.mw.command_history.appendPlainText(
                f"{e.kind}: {values} [lengths {self.document.units}; areas square units]"
            )


class ChainDimensionTool(PointInputTool):
    name = "DIMCONTINUE"
    baseline = False

    def __init__(self, mw):
        super().__init__(mw)
        self.source = None
        self.count = 0

    def status_prompt(self):
        return (
            f"{self.name}: Pick a linear dimension"
            if self.source is None
            else f"{self.name}: Next extension origin (Esc / Enter to finish)"
        )

    def on_click(self, x, y, snap_kind, button):
        if button != LEFT:
            return
        if self.source is None:
            e = pick(self, x, y, (DimensionEntity,))
            if e and e.dim_style in ("horizontal", "vertical", "aligned"):
                self.source = e
                self.anchor = (
                    Point(e.p1.x, e.p1.y) if self.baseline else Point(e.p2.x, e.p2.y)
                )
            return
        e = self.source
        target = Point(x, y)
        if target.distance_to(self.anchor) < 1e-9:
            raise ValueError("Use a distinct extension origin.")
        self.count += 1
        dx, dy = e.p2.x - e.p1.x, e.p2.y - e.p1.y
        length = math.hypot(dx, dy)
        nx, ny = (
            (
                (0, 1)
                if e.dim_style == "horizontal"
                else (-1, 0)
                if e.dim_style == "vertical"
                else (-dy / length, dx / length)
            )
            if length
            else (0, 1)
        )
        offset = self.count * 5 if self.baseline else 0
        dim = DimensionEntity(
            Point(self.anchor.x, self.anchor.y),
            target,
            Point(e.dim_point.x + nx * offset, e.dim_point.y + ny * offset),
            dim_style=e.dim_style,
            style_name=e.style_name,
            layer=self.document.layers.current_layer,
        )
        self.document.undo_stack.push(AddEntityCommand(self.document, dim, self.name))
        if not self.baseline:
            self.anchor = target
        self.points = [target]

    def on_key(self, key):
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Escape):
            self.finish()


class BaselineDimensionTool(ChainDimensionTool):
    name = "DIMBASELINE"
    baseline = True


class ZoomWindowTool(PointInputTool):
    name = "ZOOMWINDOW"
    prompt = "ZOOM WINDOW: Pick two opposite corners"

    def on_click(self, x, y, snap_kind, button):
        if button != LEFT:
            return
        self.points.append(Point(x, y))
        if len(self.points) == 2:
            a, b = self.points
            width, height = abs(a.x - b.x), abs(a.y - b.y)
            if width < 1e-9 or height < 1e-9:
                self.points.pop()
                raise ValueError("The zoom window needs nonzero width and height.")
            canvas = self.mw.canvas
            canvas.zoom = max(
                0.01,
                min(
                    100000,
                    min(
                        canvas.viewport().width() / width,
                        canvas.viewport().height() / height,
                    )
                    * 0.95,
                ),
            )
            canvas.pan_offset = QPointF((a.x + b.x) / 2, (a.y + b.y) / 2)
            self.finish()


EXTRA_TOOLS = {
    cls.name: cls
    for cls in (
        StretchTool,
        MatchLayerTool,
        MTextTool,
        PlaceTableTool,
        LeaderTool,
        CenterMarkTool,
        CenterlineTool,
        RadiusMeasureTool,
        AngleMeasureTool,
        QuickMeasureTool,
        ChainDimensionTool,
        BaselineDimensionTool,
        ZoomWindowTool,
    )
}
EXTRA_TOOLS["MLEADER"] = LeaderTool
