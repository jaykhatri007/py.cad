"""
tools.py
Each tool implements a small state machine driven by canvas clicks / mouse moves /
key presses, mirroring how AutoCAD commands work (click points, optionally type
values in the command line).
"""
from typing import Optional, List
import math
from PyQt6.QtGui import QPainter, QPen, QColor, QPainterPath
from PyQt6.QtCore import Qt

from .geometry import (Point, LineEntity, CircleEntity, RectangleEntity, PolylineEntity, ArcEntity,
                       PointEntity, EllipseEntity, RayEntity, XLineEntity, TextEntity, DimensionEntity,
                       HatchEntity, SplineEntity,
                       BlockDefinition, BlockReferenceEntity)
from .document import AddEntityCommand, TranslateEntitiesCommand, SetAttrCommand, DeleteEntitiesCommand, SetPointCommand

PREVIEW_COLOR = QColor(0, 200, 120)


class Tool:
    name = "TOOL"
    prompt = ""

    def __init__(self, main_window):
        self.mw = main_window
        self.document = main_window.document
        self.points: List[Point] = []
        self.active = True

    def status_prompt(self) -> str:
        return self.prompt

    def on_click(self, x: float, y: float, snap_kind: str, button: int):
        pass

    def on_move(self, x: float, y: float, snap_kind: str):
        pass

    def on_text_input(self, text: str):
        """Called when user types a value/coord into the command line and hits Enter."""
        pass

    def on_key(self, key: int):
        if key == Qt.Key.Key_Escape:
            self.finish()

    def draw_preview(self, painter: QPainter, canvas):
        pass

    def finish(self):
        self.active = False
        self.mw.tool_finished()

    @staticmethod
    def parse_point(text: str, last_point: Optional[Point] = None) -> Optional[Point]:
        """Parse 'x,y' absolute or '@dx,dy' relative coordinate entry."""
        text = text.strip()
        relative = text.startswith("@")
        if relative:
            text = text[1:]
        try:
            if "<" in text:
                distance, angle = map(float, text.split("<"))
                x = distance * math.cos(math.radians(angle))
                y = distance * math.sin(math.radians(angle))
            else:
                x, y = map(float, text.split(","))
            if not math.isfinite(x) or not math.isfinite(y):
                return None
            if relative:
                if last_point is None:
                    return None
                x, y = x + last_point.x, y + last_point.y
            return Point(x, y)
        except (ValueError, OverflowError):
            return None


class LineTool(Tool):
    name = "LINE"

    def __init__(self, main_window):
        super().__init__(main_window)
        self.segments = []

    def status_prompt(self):
        if not self.points:
            return "LINE: Specify first point"
        return "LINE: Specify next point (Enter to finish, Esc to cancel)"

    def on_click(self, x, y, snap_kind, button):
        if button != Qt.MouseButton.LeftButton.value:
            return
        p = Point(x, y)
        if self.points:
            self._commit_segment(self.points[-1], p)
        self.points.append(p)

    def _commit_segment(self, p1: Point, p2: Point):
        entity = LineEntity(Point(p1.x, p1.y), Point(p2.x, p2.y), layer=self.document.layers.current_layer,
                             linetype=self.document.current_linetype)
        self.document.undo_stack.push(AddEntityCommand(self.document, entity, "Line"))
        self.segments.append(entity)
        from .immediate_lines import committed
        committed(self.mw.canvas, entity)

    def undo_last_segment(self):
        if not self.points:
            return
        if len(self.points) == 1:
            self.points.pop()
            return
        stack = self.document.undo_stack
        command = stack.command(stack.index()-1) if stack.index() else None
        if not self.segments or getattr(command, "entity", None) is not self.segments[-1]:
            raise ValueError("The last action is no longer this Line segment; finish the command before undoing other work")
        stack.undo()
        self.segments.pop()
        self.points.pop()

    def on_text_input(self, text: str):
        keyword = text.strip().upper()
        if keyword in ("U", "UNDO"):
            self.undo_last_segment()
            return
        if keyword in ("C", "CLOSE"):
            if len(self.points) < 3:
                raise ValueError("Draw at least two segments before Close")
            if self.points[-1].distance_to(self.points[0]) > 1e-12:
                self._commit_segment(self.points[-1], self.points[0])
            self.finish()
            return
        if text.strip().lower() in ("", "enter"):
            self.finish()
            return
        last = self.points[-1] if self.points else None
        p = self.parse_point(text, last)
        if p:
            if self.points:
                self._commit_segment(self.points[-1], p)
            self.points.append(p)

    def on_key(self, key):
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.finish()
        elif key == Qt.Key.Key_Escape:
            self.finish()

    def draw_preview(self, painter, canvas):
        if self.points:
            last = self.points[-1]
            cur = self.mw.current_world_pos
            if cur is None:
                return
            pen = QPen(PREVIEW_COLOR)
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            p1 = canvas.world_to_screen(last.x, last.y)
            p2 = canvas.world_to_screen(cur[0], cur[1])
            painter.drawLine(p1, p2)


class PolylineTool(Tool):
    name = "PLINE"

    def status_prompt(self):
        if not self.points:
            return "PLINE: Specify start point"
        return "PLINE: Specify next point (C to close, Enter to finish)"

    def on_click(self, x, y, snap_kind, button):
        if button != Qt.MouseButton.LeftButton.value:
            return
        self.points.append(Point(x, y))

    def on_text_input(self, text: str):
        t = text.strip().lower()
        if t in ("u", "undo"):
            if self.points:
                self.points.pop()
            return
        if t == "c":
            self._commit(closed=True)
            self.finish()
            return
        if t in ("", "enter"):
            self._commit(closed=False)
            self.finish()
            return
        last = self.points[-1] if self.points else None
        p = self.parse_point(text, last)
        if p:
            self.points.append(p)

    def on_key(self, key):
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._commit(closed=False)
            self.finish()
        elif key == Qt.Key.Key_Escape:
            self.finish()

    def _commit(self, closed: bool):
        if len(self.points) >= 2:
            entity = PolylineEntity([Point(p.x, p.y) for p in self.points], closed=closed,
                                     layer=self.document.layers.current_layer,
                                     linetype=self.document.current_linetype)
            self.document.undo_stack.push(AddEntityCommand(self.document, entity, "Polyline"))

    def draw_preview(self, painter, canvas):
        if not self.points:
            return
        cur = self.mw.current_world_pos
        pen = QPen(PREVIEW_COLOR)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        pts = [canvas.world_to_screen(p.x, p.y) for p in self.points]
        for a, b in zip(pts, pts[1:]):
            painter.drawLine(a, b)
        if cur is not None and pts:
            painter.drawLine(pts[-1], canvas.world_to_screen(cur[0], cur[1]))


class CircleTool(Tool):
    name = "CIRCLE"

    def status_prompt(self):
        if not self.points:
            return "CIRCLE: Specify center point"
        return "CIRCLE: Specify radius"

    def on_click(self, x, y, snap_kind, button):
        if button != Qt.MouseButton.LeftButton.value:
            return
        if not self.points:
            self.points.append(Point(x, y))
        else:
            center = self.points[0]
            r = center.distance_to(Point(x, y))
            self._commit(center, r)
            self.finish()

    def on_text_input(self, text: str):
        if not self.points:
            p = self.parse_point(text)
            if p:
                self.points.append(p)
            return
        try:
            r = float(text.strip())
            self._commit(self.points[0], r)
            self.finish()
        except ValueError:
            pass

    def _commit(self, center: Point, radius: float):
        if not math.isfinite(radius) or radius <= 0:
            raise ValueError("Radius must be finite and positive")
        entity = CircleEntity(Point(center.x, center.y), radius, layer=self.document.layers.current_layer,
                               linetype=self.document.current_linetype)
        self.document.undo_stack.push(AddEntityCommand(self.document, entity, "Circle"))

    def draw_preview(self, painter, canvas):
        if not self.points:
            return
        cur = self.mw.current_world_pos
        if cur is None:
            return
        center = self.points[0]
        r = center.distance_to(Point(cur[0], cur[1]))
        pen = QPen(PREVIEW_COLOR)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        c = canvas.world_to_screen(center.x, center.y)
        painter.drawEllipse(c, r * canvas.zoom, r * canvas.zoom)


class PointTool(Tool):
    name = "POINT"

    def status_prompt(self):
        return "POINT: Specify point"

    def on_click(self, x, y, snap_kind, button):
        if button != Qt.MouseButton.LeftButton.value:
            return
        entity = PointEntity(Point(x, y), layer=self.document.layers.current_layer,
                             linetype=self.document.current_linetype)
        self.document.undo_stack.push(AddEntityCommand(self.document, entity, "Point"))
        self.finish()


class EllipseTool(Tool):
    name = "ELLIPSE"

    def status_prompt(self):
        if not self.points:
            return "ELLIPSE: Specify center"
        if len(self.points) == 1:
            return "ELLIPSE: Specify major-axis endpoint"
        return "ELLIPSE: Specify minor-axis point"

    def on_click(self, x, y, snap_kind, button):
        if button != Qt.MouseButton.LeftButton.value:
            return
        point = Point(x, y)
        if len(self.points) < 2:
            self.points.append(point)
            return
        center, major_point = self.points
        major_radius = center.distance_to(major_point)
        rotation = math.degrees(math.atan2(major_point.y - center.y, major_point.x - center.x))
        minor_radius = center.distance_to(point)
        if major_radius <= 1e-12 or minor_radius <= 1e-12:
            raise ValueError("Ellipse axes must be non-zero")
        entity = EllipseEntity(Point(center.x, center.y), major_radius, minor_radius,
                               rotation, layer=self.document.layers.current_layer,
                               linetype=self.document.current_linetype)
        self.document.undo_stack.push(AddEntityCommand(self.document, entity, "Ellipse"))
        self.finish()

    def on_key(self, key):
        if key == Qt.Key.Key_Escape:
            self.finish()

    def draw_preview(self, painter, canvas):
        if not self.points or self.mw.current_world_pos is None:
            return
        current = self.mw.current_world_pos
        pen = QPen(PREVIEW_COLOR)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        if len(self.points) == 1:
            center = self.points[0]
            painter.drawLine(canvas.world_to_screen(center.x, center.y),
                             canvas.world_to_screen(current[0], current[1]))
            return
        center, major_point = self.points
        major_radius = center.distance_to(major_point)
        rotation = math.degrees(math.atan2(major_point.y - center.y, major_point.x - center.x))
        minor_radius = center.distance_to(Point(current[0], current[1]))
        if minor_radius <= 1e-12:
            return
        preview = EllipseEntity(center, max(major_radius, 1e-9), minor_radius, rotation)
        points = [canvas.world_to_screen(p.x, p.y) for p in preview.sample_points(64)]
        if points:
            painter.drawPolyline(points + [points[0]])


class RayTool(Tool):
    name = "RAY"

    def status_prompt(self):
        return "RAY: Specify start point" if not self.points else "RAY: Specify through point"

    def on_click(self, x, y, snap_kind, button):
        if button != Qt.MouseButton.LeftButton.value:
            return
        self.points.append(Point(x, y))
        if len(self.points) == 2:
            entity = RayEntity(self.points[0], self.points[1], layer=self.document.layers.current_layer,
                               linetype=self.document.current_linetype)
            self.document.undo_stack.push(AddEntityCommand(self.document, entity, "Ray"))
            self.finish()

    def on_key(self, key):
        if key == Qt.Key.Key_Escape:
            self.finish()


class XLineTool(RayTool):
    name = "XLINE"

    def on_click(self, x, y, snap_kind, button):
        if button != Qt.MouseButton.LeftButton.value:
            return
        self.points.append(Point(x, y))
        if len(self.points) == 2:
            entity = XLineEntity(self.points[0], self.points[1], layer=self.document.layers.current_layer,
                                 linetype=self.document.current_linetype)
            self.document.undo_stack.push(AddEntityCommand(self.document, entity, "Construction line"))
            self.finish()


class RectangleTool(Tool):
    name = "RECTANGLE"

    def status_prompt(self):
        if not self.points:
            return "RECTANGLE: Specify first corner"
        return "RECTANGLE: Specify opposite corner"

    def on_click(self, x, y, snap_kind, button):
        if button != Qt.MouseButton.LeftButton.value:
            return
        if not self.points:
            self.points.append(Point(x, y))
        else:
            entity = RectangleEntity(Point(self.points[0].x, self.points[0].y), Point(x, y),
                                      layer=self.document.layers.current_layer,
                                      linetype=self.document.current_linetype)
            self.document.undo_stack.push(AddEntityCommand(self.document, entity, "Rectangle"))
            self.finish()

    def draw_preview(self, painter, canvas):
        if not self.points:
            return
        cur = self.mw.current_world_pos
        if cur is None:
            return
        pen = QPen(PREVIEW_COLOR)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        p1 = canvas.world_to_screen(self.points[0].x, self.points[0].y)
        p2 = canvas.world_to_screen(cur[0], cur[1])
        from PyQt6.QtCore import QRectF
        painter.drawRect(QRectF(p1, p2).normalized())


class ArcTool(Tool):
    """3-point arc: start, end, point-on-arc (simplified center/radius/angle version)."""
    name = "ARC"

    def status_prompt(self):
        stage = len(self.points)
        return ["ARC: Specify center point", "ARC: Specify start point", "ARC: Specify end point"][min(stage, 2)]

    def on_click(self, x, y, snap_kind, button):
        if button != Qt.MouseButton.LeftButton.value:
            return
        self.points.append(Point(x, y))
        if len(self.points) == 3:
            import math
            center, start, end = self.points
            r = center.distance_to(start)
            a1 = math.degrees(math.atan2(start.y - center.y, start.x - center.x))
            a2 = math.degrees(math.atan2(end.y - center.y, end.x - center.x))
            entity = ArcEntity(Point(center.x, center.y), r, a1, a2, layer=self.document.layers.current_layer,
                                linetype=self.document.current_linetype)
            self.document.undo_stack.push(AddEntityCommand(self.document, entity, "Arc"))
            self.finish()

    def draw_preview(self, painter, canvas):
        cur = self.mw.current_world_pos
        if not self.points or cur is None:
            return
        pen = QPen(PREVIEW_COLOR)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        p1 = canvas.world_to_screen(self.points[-1].x, self.points[-1].y)
        p2 = canvas.world_to_screen(cur[0], cur[1])
        painter.drawLine(p1, p2)


class SelectTool(Tool):
    """Default tool: click to select, drag to move, rubber-band to
    multi-select. When exactly one entity is selected, small square grips
    appear at its editable points (line endpoints, polyline/spline
    vertices, circle center/radius, arc center/start/end) - clicking and
    dragging one reshapes just that part of the entity instead of moving
    the whole thing."""
    name = "SELECT"
    prompt = "Select: click replaces • Ctrl-click adds • Alt-click removes • drag empty space for a selection box"

    def __init__(self, main_window):
        super().__init__(main_window)
        self.dragging_entity = False
        self.drag_last_world: Optional[Point] = None
        self.drag_origin = None
        self.press_world: Optional[Point] = None
        self.box_selection_mode = "replace"
        # grip-drag state
        self.grip_entity = None
        self.grip_kind: Optional[str] = None
        self.grip_old_xy = None      # for point-based grips (SetPointCommand)
        self.grip_old_attr = None    # (attr_name, old_value) for attr-based grips (circle radius, arc angles)
        # Layout-space viewport move/resize state
        self.vp_drag_kind: Optional[str] = None   # "move" or "resize"
        self.vp_drag_target = None
        self.vp_drag_corner: Optional[str] = None
        self.vp_drag_old_rect = None
        self.vp_drag_last: Optional[Point] = None

    def status_prompt(self):
        if len(self.mw.canvas.selected_entities)==1 and isinstance(self.mw.canvas.selected_entities[0],PolylineEntity):
            return "POLYLINE: drag square vertex / round midpoint; right-click a grip for Insert, Delete, Stretch, Arc or Coordinates"
        return self.prompt

    def _selection_mode(self):
        modifiers = getattr(self.mw.canvas,"_click_modifiers",Qt.KeyboardModifier.NoModifier)
        if modifiers & Qt.KeyboardModifier.AltModifier:return 'remove'
        if modifiers & Qt.KeyboardModifier.ControlModifier:return 'add'
        return 'replace'

    def _apply_selection(self, items, mode):
        canvas=self.mw.canvas
        if mode=='replace':canvas.selected_entities=list(items)
        elif mode=='remove':
            removed={id(e) for e in items}
            canvas.selected_entities=[e for e in canvas.selected_entities if id(e) not in removed]
        else:
            existing={id(e) for e in canvas.selected_entities}
            canvas.selected_entities += [e for e in items if id(e) not in existing]

    def _group_members(self, entity):
        members={entity.id}
        for group in self.document.extensions.get('groups',{}).values():
            if entity.id in group:members.update(group)
        if len(members)==1:return [entity]
        return [e for e in self.document.entities if e.id in members and self.document.is_editable(e)]

    def _pick_entity(self, x, y):
        from .geom_ops import pick_entity
        tolerance = 8 / self.mw.canvas.zoom
        candidates = self.document.query_entities(
            (x - tolerance, y - tolerance, x + tolerance, y + tolerance),
            visible_only=True,
            editable_only=True,
        )
        return pick_entity(candidates, Point(x, y), tolerance)

    def _pick_grip(self, click: Point):
        canvas = self.mw.canvas
        if len(canvas.selected_entities) != 1:
            return None
        entity = canvas.selected_entities[0]
        if self.document.layers.is_locked(entity.layer):
            return None
        grips = entity.grip_points()
        if not grips:
            return None
        tol = canvas.snap_radius_px / canvas.zoom
        best, best_d = None, tol
        for kind, p in grips:
            d = click.distance_to(p)
            if d < best_d:
                best_d, best = d, (entity, kind)
        return best

    @staticmethod
    def _resolve_grip_point(entity, kind) -> Optional[Point]:
        """Re-fetch the live Point object for `kind` (not a copy) - valid
        for grips backed by a real stored attribute (line p1/p2, polyline/
        spline vertices, circle/arc center). Arc's start/end grips are NOT
        real points (they're derived from angle+radius each call) and are
        handled separately via angle mutation, never through this."""
        for k, p in entity.grip_points():
            if k == kind:
                return p
        return None

    def on_click(self, x, y, snap_kind, button):
        if button != Qt.MouseButton.LeftButton.value:
            return
        canvas = self.mw.canvas
        if self.document.current_space != "Model":
            layout = self.document.layouts.get(self.document.current_space)
            if layout is None:
                return
            click = Point(x, y)
            tol = canvas.snap_radius_px / canvas.zoom
            vp = canvas.selected_viewport
            if vp is not None:
                corners = {"bl": Point(vp.x, vp.y), "br": Point(vp.x + vp.width, vp.y),
                           "tr": Point(vp.x + vp.width, vp.y + vp.height), "tl": Point(vp.x, vp.y + vp.height)}
                for kind, cp in corners.items():
                    if click.distance_to(cp) < tol:
                        self.vp_drag_kind = "resize"
                        self.vp_drag_corner = kind
                        self.vp_drag_target = vp
                        self.vp_drag_old_rect = (vp.x, vp.y, vp.width, vp.height)
                        return
            canvas.selected_viewport = None
            for v in layout.viewports:
                if v.x <= x <= v.x + v.width and v.y <= y <= v.y + v.height:
                    canvas.selected_viewport = v
                    self.vp_drag_kind = "move"
                    self.vp_drag_target = v
                    self.vp_drag_old_rect = (v.x, v.y, v.width, v.height)
                    self.vp_drag_last = click
                    break
            canvas.viewport().update()
            return

        click = Point(x, y)
        selection_mode = self._selection_mode()
        if selection_mode == "replace":
            from .polyline_grips import begin_if_hit
            if begin_if_hit(self.mw,click):return
        grip_hit = self._pick_grip(click) if selection_mode == "replace" else None
        if grip_hit is not None:
            entity, kind = grip_hit
            self.grip_entity, self.grip_kind = entity, kind
            self.grip_old_xy, self.grip_old_attr = None, None
            if isinstance(entity, CircleEntity) and kind == "radius":
                self.grip_old_attr = ("radius", entity.radius)
            elif isinstance(entity, ArcEntity) and kind in ("start", "end"):
                attr = "start_angle" if kind == "start" else "end_angle"
                self.grip_old_attr = (attr, getattr(entity, attr))
            else:
                target = self._resolve_grip_point(entity, kind)
                if target is not None:
                    self.grip_old_xy = (target.x, target.y)
            return

        e = self._pick_entity(x, y)
        if e is not None:
            if selection_mode != 'replace':
                self._apply_selection(self._group_members(e),selection_mode)
                self.dragging_entity=False
                self.drag_origin=self.drag_last_world=None
                return
            if e not in canvas.selected_entities:
                self._apply_selection(self._group_members(e),'replace')
            self.dragging_entity = True
            self.drag_last_world = Point(x, y)
            self.drag_origin = Point(x, y)
        else:
            self.box_selection_mode = selection_mode
            if selection_mode == "replace":canvas.selected_entities = []
            self.press_world = Point(x, y)
            canvas.rubber_band_start = canvas.world_to_screen(x, y)
            canvas.rubber_band_end = canvas.rubber_band_start

    def on_move(self, x, y, snap_kind):
        canvas = self.mw.canvas
        if self.document.current_space != "Model" and self.vp_drag_kind is not None:
            vp = self.vp_drag_target
            if self.vp_drag_kind == "move":
                dx, dy = x - self.vp_drag_last.x, y - self.vp_drag_last.y
                vp.x += dx
                vp.y += dy
                self.vp_drag_last = Point(x, y)
            else:  # resize
                ox, oy, ow, oh = self.vp_drag_old_rect
                opp = {"bl": (ox + ow, oy + oh), "br": (ox, oy + oh),
                       "tr": (ox, oy), "tl": (ox + ow, oy)}[self.vp_drag_corner]
                nx0, ny0 = min(x, opp[0]), min(y, opp[1])
                nx1, ny1 = max(x, opp[0]), max(y, opp[1])
                vp.x, vp.y = nx0, ny0
                vp.width, vp.height = max(nx1 - nx0, 1e-6), max(ny1 - ny0, 1e-6)
            canvas.viewport().update()
            return
        if self.grip_entity is not None:
            from . import geom_ops
            entity, kind = self.grip_entity, self.grip_kind
            if isinstance(entity, CircleEntity) and kind == "radius":
                entity.radius = max(entity.center.distance_to(Point(x, y)), 1e-6)
            elif isinstance(entity, ArcEntity) and kind in ("start", "end"):
                angle = geom_ops.angle_of(entity.center, Point(x, y))
                if kind == "start":
                    entity.start_angle = angle
                else:
                    entity.end_angle = angle
            else:
                target = self._resolve_grip_point(entity, kind)
                if target is not None:
                    if entity.kind == 'MLEADER':
                        from .mleaders import validate_entity
                        candidate = entity.clone()
                        proposed = self._resolve_grip_point(candidate, kind)
                        proposed.x, proposed.y = x, y
                        try:
                            validate_entity(self.document, candidate)
                        except ValueError:
                            return
                    target.x, target.y = x, y
            self.document.sync_associative()
            return
        if self.dragging_entity and self.drag_last_world is not None:
            dx = x - self.drag_last_world.x
            dy = y - self.drag_last_world.y
            if abs(dx) + abs(dy) < 1e-12:
                return
            for e in canvas.selected_entities:
                e.translate(dx, dy)
            self.drag_last_world = Point(x, y)
            self.document.sync_associative()  # live-follow while dragging, not just after undo-stack pushes
        elif canvas.rubber_band_start is not None:
            canvas.rubber_band_end = canvas.world_to_screen(x, y)

    def on_key(self, key):
        if key == Qt.Key.Key_Escape:
            self.cancel_drag()
            self.mw.canvas.selected_entities = []
            self.mw.canvas.selected_viewport = None
            self.mw.canvas.viewport().update()
            return
        if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            canvas = self.mw.canvas
            if self.document.current_space != "Model":
                layout = self.document.layouts.get(self.document.current_space)
                vp = getattr(canvas, "selected_viewport", None)
                if layout is not None and vp is not None:
                    from .document import RemoveViewportCommand
                    self.document.undo_stack.push(RemoveViewportCommand(self.document, layout, vp, "Delete Viewport"))
                    canvas.selected_viewport = None
                    canvas.viewport().update()
                return
            if canvas.selected_entities:
                from .document import DeleteEntitiesCommand
                self.document.undo_stack.push(
                    DeleteEntitiesCommand(self.document, canvas.selected_entities, "Delete"))
                canvas.selected_entities = []

    def cancel_drag(self):
        canvas = self.mw.canvas
        if self.dragging_entity and self.drag_origin and self.drag_last_world:
            for e in canvas.selected_entities:
                e.translate(self.drag_origin.x - self.drag_last_world.x,
                            self.drag_origin.y - self.drag_last_world.y)
        if self.grip_entity is not None:
            if self.grip_old_attr:
                setattr(self.grip_entity, *self.grip_old_attr)
            elif self.grip_old_xy:
                point = self._resolve_grip_point(self.grip_entity, self.grip_kind)
                point.x, point.y = self.grip_old_xy
        if self.vp_drag_target and self.vp_drag_old_rect:
            vp = self.vp_drag_target
            vp.x, vp.y, vp.width, vp.height = self.vp_drag_old_rect
        if self.drag_origin or self.grip_entity is not None or self.vp_drag_target:
            self.document.sync_associative()
        canvas.rubber_band_start = canvas.rubber_band_end = None
        self.__init__(self.mw)

    def finish_drag(self):
        canvas = self.mw.canvas
        if self.dragging_entity and self.drag_origin and self.drag_last_world:
            dx = self.drag_last_world.x - self.drag_origin.x
            dy = self.drag_last_world.y - self.drag_origin.y
            if abs(dx) + abs(dy) > 1e-12:
                for e in canvas.selected_entities:
                    e.translate(-dx, -dy)
                self.document.undo_stack.push(TranslateEntitiesCommand(
                    self.document, canvas.selected_entities, dx, dy, "Move"))
            self.drag_origin = None
        if self.document.current_space != "Model" and self.vp_drag_kind is not None:
            vp = self.vp_drag_target
            new_rect = (vp.x, vp.y, vp.width, vp.height)
            old_rect = self.vp_drag_old_rect
            if new_rect != old_rect:
                vp.x, vp.y, vp.width, vp.height = old_rect  # revert; the command's redo() applies the final state
                from .document import SetViewportRectCommand
                self.document.undo_stack.push(
                    SetViewportRectCommand(self.document, vp, old_rect, new_rect, "Move/Resize Viewport"))
            self.vp_drag_kind = None
            self.vp_drag_target = None
            self.vp_drag_corner = None
            self.vp_drag_old_rect = None
            self.vp_drag_last = None
            return
        if self.grip_entity is not None:
            from .document import SetAttrCommand
            entity, kind = self.grip_entity, self.grip_kind
            if self.grip_old_attr is not None:
                attr, old_val = self.grip_old_attr
                new_val = getattr(entity, attr)
                setattr(entity, attr, old_val)  # revert live value so the command's redo() is the one that applies it
                if new_val != old_val:
                    self.document.undo_stack.push(
                        SetAttrCommand(self.document, entity, attr, old_val, new_val, "Grip edit"))
            elif self.grip_old_xy is not None:
                target = self._resolve_grip_point(entity, kind)
                if target is not None:
                    new_xy = (target.x, target.y)
                    target.x, target.y = self.grip_old_xy
                    if new_xy != self.grip_old_xy:
                        self.document.undo_stack.push(
                            SetPointCommand(self.document, target, self.grip_old_xy, new_xy, "Grip edit"))
            self.grip_entity, self.grip_kind = None, None
            self.grip_old_xy, self.grip_old_attr = None, None
            return
        if canvas.rubber_band_start and canvas.rubber_band_end:
            r1, r2 = canvas.rubber_band_start, canvas.rubber_band_end
            x1, y1 = min(r1.x(), r2.x()), min(r1.y(), r2.y())
            x2, y2 = max(r1.x(), r2.x()), max(r1.y(), r2.y())
            selected = []
            for e in self.document.editable_entities():
                bbox = e.bbox()
                p1 = canvas.world_to_screen(bbox[0], bbox[1])
                p2 = canvas.world_to_screen(bbox[2], bbox[3])
                ex1, ey1 = min(p1.x(), p2.x()), min(p1.y(), p2.y())
                ex2, ey2 = max(p1.x(), p2.x()), max(p1.y(), p2.y())
                window = r2.x() >= r1.x()
                inside = x1 <= ex1 and y1 <= ey1 and x2 >= ex2 and y2 >= ey2
                crossing = not (ex2 < x1 or ex1 > x2 or ey2 < y1 or ey1 > y2)
                if inside if window else crossing:
                    selected.append(e)
            self._apply_selection(selected,self.box_selection_mode)
        canvas.rubber_band_start = None
        canvas.rubber_band_end = None
        self.dragging_entity = False
        self.drag_last_world = None


class OffsetTool(Tool):
    """OFFSET: type a distance, click an entity, click a side. Repeats until Esc."""
    name = "OFFSET"

    def __init__(self, main_window):
        super().__init__(main_window)
        self.distance: Optional[float] = None
        self.stage = "distance"  # distance -> select -> side

    def status_prompt(self):
        if self.stage == "distance":
            return "OFFSET: Specify offset distance (type a number, Enter)"
        if self.stage == "select":
            return f"OFFSET: Select object to offset (distance={self.distance})"
        return "OFFSET: Specify point on side to offset"

    def on_text_input(self, text: str):
        if self.stage == "distance":
            try:
                d = float(text.strip())
                if math.isfinite(d) and d > 0:
                    self.distance = d
                    self.stage = "select"
            except ValueError:
                pass

    def on_click(self, x, y, snap_kind, button):
        if button != Qt.MouseButton.LeftButton.value:
            return
        from . import geom_ops
        click = Point(x, y)
        canvas = self.mw.canvas
        from .hatch_ui import loop_for
        from .geom_ops import point_in_polygon
        closed=[]
        for entity in self.document.visible_entities():
            if isinstance(entity,CircleEntity) or isinstance(entity,PolylineEntity) and entity.closed:
                loop=loop_for(entity)
                if point_in_polygon(click,loop):
                    area=abs(sum(a.x*b.y-b.x*a.y for a,b in zip(loop,loop[1:]+loop[:1])))
                    closed.append((area,entity,loop))
        if closed:
            _,entity,loop=min(closed,key=lambda item:item[0])
            self.source_entity=entity;self.boundary_points=loop
            self.holes=[]
            for other in self.document.visible_entities():
                if other is entity:continue
                if isinstance(other,CircleEntity) or isinstance(other,PolylineEntity) and other.closed:
                    interior=loop_for(other)
                    if all(point_in_polygon(p,loop) for p in interior):self.holes.append(interior)
            return
        if self.stage == "select" and self.distance:
            tol = canvas.snap_radius_px / canvas.zoom
            entity = geom_ops.pick_entity(self.document.editable_entities(), click, tol)
            if entity is not None:
                self._target = entity
                self._click_point = click
                self.stage = "side"
        elif self.stage == "side":
            self._create_offset(self._target, self._click_point, click)
            self.stage = "select"

    def _create_offset(self, entity, click_point, side_point):
        from . import geom_ops
        new_entity = None
        if isinstance(entity, LineEntity):
            p1, p2 = geom_ops.offset_line_points(entity.p1, entity.p2, self.distance, side_point)
            new_entity = LineEntity(p1, p2, layer=entity.layer, color=entity.color)
        elif isinstance(entity, CircleEntity):
            outward = side_point.distance_to(entity.center) >= entity.radius
            new_r = entity.radius + (self.distance if outward else -self.distance)
            if new_r > 0:
                new_entity = CircleEntity(Point(entity.center.x, entity.center.y), new_r,
                                           layer=entity.layer, color=entity.color)
        elif isinstance(entity,ArcEntity):
            outward=side_point.distance_to(entity.center)>=entity.radius
            new_radius=entity.radius+(self.distance if outward else -self.distance)
            if new_radius<=0: raise ValueError('Offset collapses the arc')
            new_entity=ArcEntity(Point(entity.center.x,entity.center.y),new_radius,entity.start_angle,entity.end_angle,**entity.style_kwargs())
        elif isinstance(entity, PolylineEntity) and any(entity.bulges):
            from .geometry_ui import offset_curved
            new_entity=offset_curved(entity,self.distance,side_point)
        elif isinstance(entity, PolylineEntity):
            try:
                new_pts = geom_ops.offset_polyline(entity.points, entity.closed, self.distance, side_point)
            except ValueError as ex:
                if hasattr(self.mw, "command_history"):
                    self.mw.command_history.appendPlainText(str(ex))
                return
            new_entity = PolylineEntity(new_pts, closed=entity.closed, width=entity.width,
                                         layer=entity.layer, color=entity.color)
        if new_entity is not None:
            new_entity.linetype = entity.linetype
            self.document.undo_stack.push(AddEntityCommand(self.document, new_entity, "Offset"))

    def draw_preview(self, painter, canvas):
        pass


class MirrorTool(Tool):
    """MIRROR: uses the current selection. Click two points for the mirror axis,
    then type Y/N (default N) to choose whether to erase the source objects."""
    name = "MIRROR"

    def __init__(self, main_window):
        super().__init__(main_window)
        self.axis_points: List[Point] = []
        self.done_picking_axis = False

    def status_prompt(self):
        if not self.mw.canvas.selected_entities:
            return "MIRROR: No objects selected - select objects first, then run MIRROR"
        if not self.axis_points:
            return "MIRROR: Specify first point of mirror line"
        if len(self.axis_points) == 1:
            return "MIRROR: Specify second point of mirror line"
        return "MIRROR: Erase source objects? Type Y or N (Enter = No)"

    def on_click(self, x, y, snap_kind, button):
        if button != Qt.MouseButton.LeftButton.value or self.done_picking_axis:
            return
        if not self.mw.canvas.selected_entities:
            self.finish()
            return
        self.axis_points.append(Point(x, y))
        if len(self.axis_points) == 2:
            self.done_picking_axis = True

    def on_text_input(self, text: str):
        if not self.done_picking_axis:
            return
        erase = text.strip().lower().startswith("y")
        self._commit(erase)
        self.finish()

    def on_key(self, key):
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self.done_picking_axis:
            self._commit(False)
            self.finish()
        elif key == Qt.Key.Key_Escape:
            self.finish()

    def _commit(self, erase_source: bool):
        a, b = self.axis_points
        canvas = self.mw.canvas
        selected = list(canvas.selected_entities)
        self.document.undo_stack.beginMacro("Mirror")
        for e in selected:
            clone = e.clone()
            clone.reflect_across(a, b)
            self.document.undo_stack.push(AddEntityCommand(self.document, clone, "Mirror copy"))
        if erase_source:
            from .document import DeleteEntitiesCommand
            self.document.undo_stack.push(DeleteEntitiesCommand(self.document, selected, "Mirror erase source"))
        self.document.undo_stack.endMacro()
        canvas.selected_entities = []

    def draw_preview(self, painter, canvas):
        if len(self.axis_points) == 1 and self.mw.current_world_pos:
            pen = QPen(PREVIEW_COLOR)
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            p1 = canvas.world_to_screen(self.axis_points[0].x, self.axis_points[0].y)
            cur = self.mw.current_world_pos
            p2 = canvas.world_to_screen(cur[0], cur[1])
            painter.drawLine(p1, p2)


class ArrayRectTool(Tool):
    """ARRAYRECT: uses current selection. Type "rows,cols,row_spacing,col_spacing"."""
    name = "ARRAYRECT"

    def status_prompt(self):
        if not self.mw.canvas.selected_entities:
            return "ARRAYRECT: No objects selected - select objects first"
        return "ARRAYRECT: Type rows,cols,row_spacing,col_spacing (e.g. 3,4,20,20) then Enter"

    def on_text_input(self, text: str):
        if not self.mw.canvas.selected_entities:
            self.finish()
            return
        try:
            parts = [float(v) for v in text.split(",")]
            rows, cols, dy, dx = int(parts[0]), int(parts[1]), parts[2], parts[3]
        except (ValueError, IndexError):
            return
        selected = list(self.mw.canvas.selected_entities)
        if not all(math.isfinite(v) for v in parts) or rows < 1 or cols < 1 or rows * cols * len(selected) > 10000:
            raise ValueError("Array requires positive counts and at most 10,000 entities")
        self.document.undo_stack.beginMacro("Rectangular Array")
        for r in range(rows):
            for c in range(cols):
                if r == 0 and c == 0:
                    continue
                for e in selected:
                    clone = e.clone()
                    clone.translate(c * dx, r * dy)
                    self.document.undo_stack.push(AddEntityCommand(self.document, clone, "Array item"))
        self.document.undo_stack.endMacro()
        self.finish()

    def on_key(self, key):
        if key == Qt.Key.Key_Escape:
            self.finish()


class ArrayPolarTool(Tool):
    """ARRAYPOLAR: uses current selection. Click a center point, then type
    "count,fill_angle" (fill_angle defaults to 360 if omitted)."""
    name = "ARRAYPOLAR"

    def __init__(self, main_window):
        super().__init__(main_window)
        self.center: Optional[Point] = None

    def status_prompt(self):
        if not self.mw.canvas.selected_entities:
            return "ARRAYPOLAR: No objects selected - select objects first"
        if self.center is None:
            return "ARRAYPOLAR: Specify center point of array"
        return "ARRAYPOLAR: Type count[,fill_angle] (e.g. 6 or 6,180) then Enter"

    def on_click(self, x, y, snap_kind, button):
        if button != Qt.MouseButton.LeftButton.value:
            return
        if not self.mw.canvas.selected_entities:
            self.finish()
            return
        if self.center is None:
            self.center = Point(x, y)

    def on_text_input(self, text: str):
        if self.center is None:
            return
        try:
            parts = [float(v) for v in text.split(",")]
            count = int(parts[0])
            fill_angle = parts[1] if len(parts) > 1 else 360.0
        except (ValueError, IndexError):
            return
        if not math.isfinite(fill_angle) or count * len(self.mw.canvas.selected_entities) > 10000:
            raise ValueError("Array limit is 10,000 entities")
        if count < 2:
            return
        step = fill_angle / count if abs(fill_angle - 360.0) < 1e-9 else fill_angle / (count - 1)
        selected = list(self.mw.canvas.selected_entities)
        self.document.undo_stack.beginMacro("Polar Array")
        for i in range(1, count):
            angle = step * i
            for e in selected:
                clone = e.clone()
                clone.rotate_around(self.center, angle)
                self.document.undo_stack.push(AddEntityCommand(self.document, clone, "Array item"))
        self.document.undo_stack.endMacro()
        self.finish()

    def on_key(self, key):
        if key == Qt.Key.Key_Escape:
            self.finish()

    def draw_preview(self, painter, canvas):
        if self.center is not None:
            pen = QPen(PREVIEW_COLOR)
            painter.setPen(pen)
            c = canvas.world_to_screen(self.center.x, self.center.y)
            painter.drawEllipse(c, 4, 4)


class FilletTool(Tool):
    """FILLET: click two entities (lines, arcs, or circles) near the ends/
    sides you want to keep, then type a radius. Supports Line-Line, Line-Arc,
    Line-Circle, and Arc/Circle-Arc/Circle combinations. Because a true
    tangent fillet only ever touches a curve at a single point, arcs/circles
    generally don't need trimming themselves - only straight lines (and arcs
    whose current span doesn't yet reach the new tangent point) get adjusted."""
    name = "FILLET"

    def __init__(self, main_window):
        super().__init__(main_window)
        self.first_entity = None
        self.first_click = None
        self.second_entity = None
        self.second_click = None

    def status_prompt(self):
        if self.first_entity is None:
            return "FILLET: Select first line/arc/circle (click near the end/side to keep)"
        if self.second_entity is None:
            return "FILLET: Select second line/arc/circle (click near the end/side to keep)"
        return "FILLET: Specify fillet radius (type a number, Enter)"

    def _pickable(self):
        return [e for e in self.document.visible_entities()
                if isinstance(e, (LineEntity, ArcEntity, CircleEntity))]

    def on_click(self, x, y, snap_kind, button):
        if button != Qt.MouseButton.LeftButton.value:
            return
        from . import geom_ops
        click = Point(x, y)
        canvas = self.mw.canvas
        tol = canvas.snap_radius_px / canvas.zoom
        entity = geom_ops.pick_entity(self._pickable(), click, tol)
        if entity is None:
            return
        if self.first_entity is None:
            self.first_entity, self.first_click = entity, click
        elif self.second_entity is None and entity is not self.first_entity:
            self.second_entity, self.second_click = entity, click

    def on_text_input(self, text: str):
        if self.second_entity is None:
            return
        try:
            radius = float(text.strip())
        except ValueError:
            return
        self._commit(radius)
        self.finish()

    def _commit(self, radius: float):
        e1, e2, c1, c2 = self.first_entity, self.second_entity, self.first_click, self.second_click
        is_line1, is_line2 = isinstance(e1, LineEntity), isinstance(e2, LineEntity)
        try:
            if is_line1 and is_line2:
                self._fillet_line_line(e1, e2, c1, c2, radius)
            elif is_line1 or is_line2:
                line, curve, line_click, curve_click = (e1, e2, c1, c2) if is_line1 else (e2, e1, c2, c1)
                self._fillet_line_curve(line, curve, line_click, curve_click, radius)
            else:
                self._fillet_curve_curve(e1, e2, c1, c2, radius)
        except (ValueError, ZeroDivisionError):
            pass  # geometrically impossible fillet for the given pick/radius - no-op

    # -- Line-Line (unchanged algorithm) --------------------------------
    def _fillet_line_line(self, l1, l2, click1, click2, radius):
        from . import geom_ops
        inter = geom_ops.line_line_intersection(l1.p1, l1.p2, l2.p1, l2.p2)
        if inter is None:
            return

        def kept_direction(line, click):
            t_click = geom_ops.point_on_segment_param(line.p1, line.p2, click)
            t_inter = geom_ops.point_on_segment_param(line.p1, line.p2, inter)
            far_end = line.p2 if t_click > t_inter else line.p1
            return geom_ops.normalize(geom_ops.sub(far_end, inter))

        dir1 = kept_direction(l1, click1)
        dir2 = kept_direction(l2, click2)
        cos_theta = max(-1.0, min(1.0, geom_ops.dot(dir1, dir2)))
        theta = math.acos(cos_theta)
        if theta < 1e-6 or theta > math.pi - 1e-6:
            return
        tan_dist = radius / math.tan(theta / 2)
        bis_dist = radius / math.sin(theta / 2)
        tangent1 = Point(inter.x + dir1[0] * tan_dist, inter.y + dir1[1] * tan_dist)
        tangent2 = Point(inter.x + dir2[0] * tan_dist, inter.y + dir2[1] * tan_dist)
        bis = geom_ops.normalize((dir1[0] + dir2[0], dir1[1] + dir2[1]))
        if bis == (0.0, 0.0):
            return
        center = Point(inter.x + bis[0] * bis_dist, inter.y + bis[1] * bis_dist)
        a1 = geom_ops.angle_of(center, tangent1)
        a2 = geom_ops.angle_of(center, tangent2)
        arc = ArcEntity(center, radius, a1, a2, layer=l1.layer, color=l1.color)

        def near_end_attr(line):
            return "p1" if line.p1.distance_to(inter) < line.p2.distance_to(inter) else "p2"

        attr1, attr2 = near_end_attr(l1), near_end_attr(l2)
        old1, old2 = getattr(l1, attr1), getattr(l2, attr2)
        self.document.undo_stack.beginMacro("Fillet")
        self.document.undo_stack.push(SetAttrCommand(self.document, l1, attr1, old1, tangent1, "Fillet trim"))
        self.document.undo_stack.push(SetAttrCommand(self.document, l2, attr2, old2, tangent2, "Fillet trim"))
        self.document.undo_stack.push(AddEntityCommand(self.document, arc, "Fillet arc"))
        self.document.undo_stack.endMacro()

    # -- Line-Curve (line meets an arc or circle) -----------------------
    def _fillet_line_curve(self, line, curve, line_click, curve_click, radius):
        from . import geom_ops
        cc, cr = curve.center, curve.radius
        # candidate fillet centers: on the offset line (distance=radius, toward
        # the curve's center), at distance (cr+radius) [external tangent] or
        # |cr-radius| [internal tangent] from the curve's center
        off1, off2 = geom_ops.offset_line_points(line.p1, line.p2, radius, cc)
        candidates = []
        candidates += geom_ops.circle_line_intersections(cc, cr + radius, off1, off2)
        if cr - radius > 1e-9:
            candidates += geom_ops.circle_line_intersections(cc, cr - radius, off1, off2)
        if radius - cr > 1e-9:
            candidates += geom_ops.circle_line_intersections(cc, radius - cr, off1, off2)
        if not candidates:
            return
        # pick whichever candidate best matches where the user actually clicked
        center = min(candidates, key=lambda p: p.distance_to(line_click) + p.distance_to(curve_click))
        tangent_on_line = geom_ops.point_line_projection(center, line.p1, line.p2)
        dir_to_curve = geom_ops.normalize(geom_ops.sub(center, cc))
        if dir_to_curve == (0.0, 0.0):
            return
        tangent_on_curve = Point(cc.x + dir_to_curve[0] * cr, cc.y + dir_to_curve[1] * cr)
        a1 = geom_ops.angle_of(center, tangent_on_line)
        a2 = geom_ops.angle_of(center, tangent_on_curve)
        arc = ArcEntity(center, radius, a1, a2, layer=line.layer, color=line.color)

        attr = "p1" if line.p1.distance_to(tangent_on_line) < line.p2.distance_to(tangent_on_line) else "p2"
        old = getattr(line, attr)

        self.document.undo_stack.beginMacro("Fillet")
        self.document.undo_stack.push(SetAttrCommand(self.document, line, attr, old, tangent_on_line, "Fillet trim"))
        self._maybe_extend_arc(curve, tangent_on_curve)
        self.document.undo_stack.push(AddEntityCommand(self.document, arc, "Fillet arc"))
        self.document.undo_stack.endMacro()

    # -- Curve-Curve (two arcs and/or circles) ---------------------------
    def _fillet_curve_curve(self, e1, e2, click1, click2, radius):
        from . import geom_ops
        c1, r1 = e1.center, e1.radius
        c2, r2 = e2.center, e2.radius
        candidates = []
        for ra in ((r1 + radius,), (abs(r1 - radius),) if r1 != radius else ()):
            for rb in ((r2 + radius,), (abs(r2 - radius),) if r2 != radius else ()):
                for a in ra:
                    for b in rb:
                        candidates += geom_ops.circle_circle_intersections(c1, a, c2, b)
        if not candidates:
            return
        center = min(candidates, key=lambda p: p.distance_to(click1) + p.distance_to(click2))
        dir1 = geom_ops.normalize(geom_ops.sub(center, c1))
        dir2 = geom_ops.normalize(geom_ops.sub(center, c2))
        if dir1 == (0.0, 0.0) or dir2 == (0.0, 0.0):
            return
        tangent1 = Point(c1.x + dir1[0] * r1, c1.y + dir1[1] * r1)
        tangent2 = Point(c2.x + dir2[0] * r2, c2.y + dir2[1] * r2)
        a1 = geom_ops.angle_of(center, tangent1)
        a2 = geom_ops.angle_of(center, tangent2)
        arc = ArcEntity(center, radius, a1, a2, layer=e1.layer, color=e1.color)

        self.document.undo_stack.beginMacro("Fillet")
        self._maybe_extend_arc(e1, tangent1)
        self._maybe_extend_arc(e2, tangent2)
        self.document.undo_stack.push(AddEntityCommand(self.document, arc, "Fillet arc"))
        self.document.undo_stack.endMacro()

    def _maybe_extend_arc(self, entity, tangent_point):
        """If `entity` is an Arc whose current span doesn't reach the tangent
        point, extend the nearer endpoint's angle to meet it. Circles never
        need adjustment - they're already a closed curve tangent at one point."""
        from . import geom_ops
        if not isinstance(entity, ArcEntity):
            return
        tangent_angle = geom_ops.angle_of(entity.center, tangent_point)
        if geom_ops.angle_in_arc_range(tangent_angle, entity.start_angle, entity.end_angle):
            return
        d_start = geom_ops.angle_distance(tangent_angle, entity.start_angle)
        d_end = geom_ops.angle_distance(tangent_angle, entity.end_angle)
        attr = "start_angle" if d_start < d_end else "end_angle"
        old = getattr(entity, attr)
        self.document.undo_stack.push(SetAttrCommand(self.document, entity, attr, old, tangent_angle,
                                                       "Fillet arc extend"))

    def on_key(self, key):
        if key == Qt.Key.Key_Escape:
            self.finish()


class ChamferTool(Tool):
    """CHAMFER: click two lines near the ends to keep, then type dist1,dist2
    (or a single distance to use for both)."""
    name = "CHAMFER"

    def __init__(self, main_window):
        super().__init__(main_window)
        self.first_line = None
        self.first_click = None
        self.second_line = None
        self.second_click = None

    def status_prompt(self):
        if self.first_line is None:
            return "CHAMFER: Select first line (click near the end to keep)"
        if self.second_line is None:
            return "CHAMFER: Select second line (click near the end to keep)"
        return "CHAMFER: Specify distance(s) - e.g. '10' or '10,15' - then Enter"

    def on_click(self, x, y, snap_kind, button):
        if button != Qt.MouseButton.LeftButton.value:
            return
        from . import geom_ops
        click = Point(x, y)
        canvas = self.mw.canvas
        tol = canvas.snap_radius_px / canvas.zoom
        entity = geom_ops.pick_entity(
            [e for e in self.document.visible_entities() if isinstance(e, LineEntity)], click, tol)
        if entity is None:
            return
        if self.first_line is None:
            self.first_line, self.first_click = entity, click
        elif self.second_line is None and entity is not self.first_line:
            self.second_line, self.second_click = entity, click

    def on_text_input(self, text: str):
        if self.second_line is None:
            return
        try:
            parts = [float(v) for v in text.split(",")]
            d1 = parts[0]
            d2 = parts[1] if len(parts) > 1 else parts[0]
        except (ValueError, IndexError):
            return
        self._commit(d1, d2)
        self.finish()

    def _commit(self, d1: float, d2: float):
        from . import geom_ops
        l1, l2 = self.first_line, self.second_line
        inter = geom_ops.line_line_intersection(l1.p1, l1.p2, l2.p1, l2.p2)
        if inter is None:
            return

        def kept_direction(line, click):
            t_click = geom_ops.point_on_segment_param(line.p1, line.p2, click)
            t_inter = geom_ops.point_on_segment_param(line.p1, line.p2, inter)
            far_end = line.p2 if t_click > t_inter else line.p1
            return geom_ops.normalize(geom_ops.sub(far_end, inter))

        dir1 = kept_direction(l1, self.first_click)
        dir2 = kept_direction(l2, self.second_click)
        cp1 = Point(inter.x + dir1[0] * d1, inter.y + dir1[1] * d1)
        cp2 = Point(inter.x + dir2[0] * d2, inter.y + dir2[1] * d2)
        chamfer_line = LineEntity(cp1, cp2, layer=l1.layer, color=l1.color)

        def near_end_attr(line):
            return "p1" if line.p1.distance_to(inter) < line.p2.distance_to(inter) else "p2"

        attr1, attr2 = near_end_attr(l1), near_end_attr(l2)
        old1, old2 = getattr(l1, attr1), getattr(l2, attr2)

        self.document.undo_stack.beginMacro("Chamfer")
        self.document.undo_stack.push(SetAttrCommand(self.document, l1, attr1, old1, cp1, "Chamfer trim"))
        self.document.undo_stack.push(SetAttrCommand(self.document, l2, attr2, old2, cp2, "Chamfer trim"))
        self.document.undo_stack.push(AddEntityCommand(self.document, chamfer_line, "Chamfer line"))
        self.document.undo_stack.endMacro()

    def on_key(self, key):
        if key == Qt.Key.Key_Escape:
            self.finish()


class TrimTool(Tool):
    """TRIM: click boundary entities, then Enter, then click the portion of a
    line, arc, or circle you want removed. Boundaries (Line/Circle/Arc) are
    treated as extending infinitely for cutting purposes - same convention
    AutoCAD uses by default. A full circle with 2+ cuts becomes a single arc
    (a circle has no start/end, so removing one sector always leaves exactly
    one piece); a line or arc with 2+ cuts can split into two separate pieces
    if the clicked segment sits between two interior cuts."""
    name = "TRIM"

    def __init__(self, main_window):
        super().__init__(main_window)
        self.boundaries: List = []
        self.picking_boundaries = True

    def status_prompt(self):
        if self.picking_boundaries:
            return f"TRIM: Select cutting edges ({len(self.boundaries)} selected) - Enter when done"
        return "TRIM: Click the segment to trim away (Esc to finish)"

    def on_click(self, x, y, snap_kind, button):
        if button != Qt.MouseButton.LeftButton.value:
            return
        from . import geom_ops
        click = Point(x, y)
        canvas = self.mw.canvas
        tol = canvas.snap_radius_px / canvas.zoom
        if self.picking_boundaries:
            e = geom_ops.pick_entity(self.document.editable_entities(), click, tol, exclude=self.boundaries)
            if e is not None:
                self.boundaries.append(e)
            return
        target = geom_ops.pick_entity(
            [e for e in self.document.editable_entities() if isinstance(e, (LineEntity, CircleEntity, ArcEntity, PolylineEntity))],
            click, tol, exclude=self.boundaries)
        if target is None:
            return
        if isinstance(target,PolylineEntity):
            from .geometry_ui import trim_polyline
            trim_polyline(self,target,click)
        elif isinstance(target, LineEntity):
            self._trim_line(target, click)
        elif isinstance(target, CircleEntity):
            self._trim_circle(target, click)
        elif isinstance(target, ArcEntity):
            self._trim_arc(target, click)

    def _line_boundary_intersections(self, p1: Point, p2: Point) -> List:
        """Boundary crossing points against the infinite line through p1,p2.
        Circle/Arc boundaries are treated as their full underlying circle."""
        from . import geom_ops
        pts = []
        from .precision import polyline_parts
        boundaries=[part for boundary in self.boundaries for part in (polyline_parts(boundary) if isinstance(boundary,PolylineEntity) else [boundary])]
        for b in boundaries:
            if isinstance(b, LineEntity):
                pt = geom_ops.line_line_intersection(p1, p2, b.p1, b.p2, segment_only=False)
                if pt is not None:
                    pts.append(pt)
            elif isinstance(b, (CircleEntity, ArcEntity)):
                pts.extend(geom_ops.circle_line_intersections(b.center, b.radius, p1, p2))
        return pts

    def _circle_boundary_intersections(self, center: Point, radius: float) -> List:
        from . import geom_ops
        pts = []
        from .precision import polyline_parts
        boundaries=[part for boundary in self.boundaries for part in (polyline_parts(boundary) if isinstance(boundary,PolylineEntity) else [boundary])]
        for b in boundaries:
            if isinstance(b, LineEntity):
                pts.extend(geom_ops.circle_line_intersections(center, radius, b.p1, b.p2))
            elif isinstance(b, (CircleEntity, ArcEntity)):
                pts.extend(geom_ops.circle_circle_intersections(center, radius, b.center, b.radius))
        return pts

    def _trim_line(self, line: LineEntity, click: Point):
        from . import geom_ops
        raw_pts = self._line_boundary_intersections(line.p1, line.p2)
        cut_ts = [t for t in (geom_ops.point_on_segment_param(line.p1, line.p2, p) for p in raw_pts)
                  if 0.0 <= t <= 1.0]
        if not cut_ts:
            return
        t_click = geom_ops.point_on_segment_param(line.p1, line.p2, click)
        low, high = geom_ops.bracket_range(0.0, 1.0, t_click, cut_ts)
        self._apply_1d_trim(line, "p1", "p2", low, high, 1.0,
                             lambda t: geom_ops.point_at_param(line.p1, line.p2, t),
                             lambda a, b: LineEntity(a, b, layer=line.layer, color=line.color,
                                                      linetype=line.linetype))

    def _trim_arc(self, arc: ArcEntity, click: Point):
        from . import geom_ops
        span = (arc.end_angle - arc.start_angle) % 360.0
        if span == 0:
            span = 360.0

        def pos(angle):
            return (angle - arc.start_angle) % 360.0

        raw_pts = self._circle_boundary_intersections(arc.center, arc.radius)
        cut_positions = []
        for p in raw_pts:
            ang = geom_ops.angle_of(arc.center, p)
            pp = pos(ang)
            if 0.0 <= pp <= span:
                cut_positions.append(pp)
        if not cut_positions:
            return
        click_pos = pos(geom_ops.angle_of(arc.center, click))
        low, high = geom_ops.bracket_range(0.0, span, click_pos, cut_positions)

        def angle_at(p):
            return arc.start_angle + p

        self._apply_1d_trim(arc, "start_angle", "end_angle", low, high, span, angle_at,
                             lambda a, b: ArcEntity(Point(arc.center.x, arc.center.y), arc.radius, a, b,
                                                     layer=arc.layer, color=arc.color, linetype=arc.linetype))

    def _apply_1d_trim(self, entity, low_attr, high_attr, low, high, full_high, value_at, make_piece):
        """Shared bracket-trim logic for Line (param t in [0,1], full_high=1.0)
        and Arc (angular position in [0,span], full_high=span). `(low, high)`
        is the bracket CONTAINING the click - i.e. the piece to REMOVE.
        `value_at` maps a bracket coordinate back to a real Point (lines) or
        angle (arcs). `make_piece` builds a replacement entity from two such
        values - used when the removed bracket sits between two interior
        cuts, leaving two separate kept pieces on either side."""
        eps = 1e-9
        removed_touches_start = low <= eps
        removed_touches_end = high >= full_high - eps
        self.document.undo_stack.beginMacro("Trim")
        from .document import DeleteEntitiesCommand
        if removed_touches_start and removed_touches_end:
            # the clicked segment spans the entire entity - nothing survives
            self.document.undo_stack.push(DeleteEntitiesCommand(self.document, [entity], "Trim (removed all)"))
        elif removed_touches_start:
            # kept piece is [high, full_high] - pull the low-side wall inward
            old = getattr(entity, low_attr)
            self.document.undo_stack.push(SetAttrCommand(self.document, entity, low_attr, old,
                                                           value_at(high), "Trim"))
        elif removed_touches_end:
            # kept piece is [0, low] - pull the high-side wall inward
            old = getattr(entity, high_attr)
            self.document.undo_stack.push(SetAttrCommand(self.document, entity, high_attr, old,
                                                           value_at(low), "Trim"))
        else:
            # interior removal - two separate kept pieces survive
            piece1 = make_piece(value_at(0.0), value_at(low))
            piece2 = make_piece(value_at(high), value_at(full_high))
            self.document.undo_stack.push(DeleteEntitiesCommand(self.document, [entity], "Trim split"))
            self.document.undo_stack.push(AddEntityCommand(self.document, piece1, "Trim piece"))
            self.document.undo_stack.push(AddEntityCommand(self.document, piece2, "Trim piece"))
        self.document.undo_stack.endMacro()

    def _trim_circle(self, circle: CircleEntity, click: Point):
        """A full circle has no start/end, so removing one sector always
        leaves exactly one contiguous arc behind (never a split)."""
        from . import geom_ops
        raw_pts = self._circle_boundary_intersections(circle.center, circle.radius)
        angles = sorted(set(round(geom_ops.angle_of(circle.center, p) % 360.0, 9) for p in raw_pts))
        if len(angles) < 2:
            return
        click_angle = geom_ops.angle_of(circle.center, click) % 360.0
        n = len(angles)
        for i in range(n):
            a0, a1 = angles[i], angles[(i + 1) % n]
            span = (a1 - a0) % 360.0
            if span <= 1e-9:
                continue
            if (click_angle - a0) % 360.0 <= span:
                new_start = a1
                new_end = a1 + (360.0 - span)
                break
        else:
            return
        new_arc = ArcEntity(Point(circle.center.x, circle.center.y), circle.radius, new_start, new_end,
                             layer=circle.layer, color=circle.color, linetype=circle.linetype)
        from .document import DeleteEntitiesCommand
        self.document.undo_stack.beginMacro("Trim")
        self.document.undo_stack.push(DeleteEntitiesCommand(self.document, [circle], "Trim circle"))
        self.document.undo_stack.push(AddEntityCommand(self.document, new_arc, "Trim result"))
        self.document.undo_stack.endMacro()

    def on_text_input(self, text: str):
        if self.picking_boundaries and text.strip() in ("", "enter"):
            self.picking_boundaries = False

    def on_key(self, key):
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self.picking_boundaries:
            self.picking_boundaries = False
        elif key == Qt.Key.Key_Escape:
            self.finish()

    def draw_preview(self, painter, canvas):
        pass


class ExtendTool(Tool):
    """EXTEND: click boundary entities, then Enter, then click near the end of
    a line or arc you want stretched out to meet the nearest boundary.
    Boundaries (Line/Circle/Arc) are treated as extending infinitely, same
    convention as Trim. Circles can't themselves be extended (they're
    already closed) so they're pick-able only as boundaries, not targets."""
    name = "EXTEND"

    def __init__(self, main_window):
        super().__init__(main_window)
        self.boundaries: List = []
        self.picking_boundaries = True

    def status_prompt(self):
        if self.picking_boundaries:
            return f"EXTEND: Select boundary edges ({len(self.boundaries)} selected) - Enter when done"
        return "EXTEND: Click near the end of the line/arc to extend (Esc to finish)"

    def on_click(self, x, y, snap_kind, button):
        if button != Qt.MouseButton.LeftButton.value:
            return
        from . import geom_ops
        click = Point(x, y)
        canvas = self.mw.canvas
        tol = canvas.snap_radius_px / canvas.zoom
        if self.picking_boundaries:
            e = geom_ops.pick_entity(self.document.editable_entities(), click, tol, exclude=self.boundaries)
            if e is not None:
                self.boundaries.append(e)
            return
        target = geom_ops.pick_entity(
            [e for e in self.document.visible_entities() if isinstance(e, (LineEntity, ArcEntity))],
            click, tol, exclude=self.boundaries)
        if target is None:
            return
        if isinstance(target, LineEntity):
            self._extend_line(target, click)
        else:
            self._extend_arc(target, click)

    def _extend_line(self, line: LineEntity, click: Point):
        from . import geom_ops
        near_attr = "p1" if click.distance_to(line.p1) < click.distance_to(line.p2) else "p2"
        far_attr = "p2" if near_attr == "p1" else "p1"
        near_pt, far_pt = getattr(line, near_attr), getattr(line, far_attr)

        candidates = []
        for b in self.boundaries:
            if isinstance(b, LineEntity):
                pt = geom_ops.line_line_intersection(far_pt, near_pt, b.p1, b.p2, segment_only=False)
                if pt is not None:
                    candidates.append(pt)
            elif isinstance(b, (CircleEntity, ArcEntity)):
                candidates.extend(geom_ops.circle_line_intersections(b.center, b.radius, far_pt, near_pt))
        if not candidates:
            return
        valid = []
        for pt in candidates:
            t = geom_ops.point_on_segment_param(far_pt, near_pt, pt)
            if t > 1.0 + 1e-9:
                valid.append((t, pt))
        if not valid:
            return
        valid.sort(key=lambda tp: tp[0])
        _, new_pt = valid[0]
        old = getattr(line, near_attr)
        self.document.undo_stack.push(SetAttrCommand(self.document, line, near_attr, old, new_pt, "Extend"))

    def _extend_arc(self, arc: ArcEntity, click: Point):
        from . import geom_ops
        span = (arc.end_angle - arc.start_angle) % 360.0
        if span == 0:
            span = 360.0

        def pos(angle):
            return (angle - arc.start_angle) % 360.0

        candidates = []
        for b in self.boundaries:
            if isinstance(b, LineEntity):
                candidates.extend(geom_ops.circle_line_intersections(arc.center, arc.radius, b.p1, b.p2))
            elif isinstance(b, (CircleEntity, ArcEntity)):
                candidates.extend(geom_ops.circle_circle_intersections(arc.center, arc.radius, b.center, b.radius))
        if not candidates:
            return
        beyond = [pos(geom_ops.angle_of(arc.center, p)) for p in candidates]
        beyond = [p for p in beyond if p > span + 1e-9]
        if not beyond:
            return
        start_pt = Point(arc.center.x + arc.radius * math.cos(math.radians(arc.start_angle)),
                          arc.center.y + arc.radius * math.sin(math.radians(arc.start_angle)))
        end_pt = Point(arc.center.x + arc.radius * math.cos(math.radians(arc.end_angle)),
                        arc.center.y + arc.radius * math.sin(math.radians(arc.end_angle)))
        extend_end_side = click.distance_to(end_pt) < click.distance_to(start_pt)
        if extend_end_side:
            new_pos = min(beyond)
            old = arc.end_angle
            new_val = arc.start_angle + new_pos
            self.document.undo_stack.push(SetAttrCommand(self.document, arc, "end_angle", old, new_val, "Extend"))
        else:
            new_pos = max(beyond)
            old = arc.start_angle
            new_val = arc.start_angle + (new_pos - 360.0)
            self.document.undo_stack.push(SetAttrCommand(self.document, arc, "start_angle", old, new_val, "Extend"))

    def on_text_input(self, text: str):
        if self.picking_boundaries and text.strip() in ("", "enter"):
            self.picking_boundaries = False

    def on_key(self, key):
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self.picking_boundaries:
            self.picking_boundaries = False
        elif key == Qt.Key.Key_Escape:
            self.finish()


class TextTool(Tool):
    """TEXT: click an insertion point, then type the text and press Enter."""
    name = "TEXT"

    def __init__(self, main_window):
        super().__init__(main_window)
        self.insertion_point: Optional[Point] = None
        self.height = 2.5

    def status_prompt(self):
        if self.insertion_point is None:
            return "TEXT: Specify insertion point"
        return "TEXT: Type the text and press Enter"

    def on_click(self, x, y, snap_kind, button):
        if button != Qt.MouseButton.LeftButton.value or self.insertion_point is not None:
            return
        self.insertion_point = Point(x, y)

    def on_text_input(self, text: str):
        if self.insertion_point is None:
            p = self.parse_point(text)
            if p:
                self.insertion_point = p
            return
        if not text:
            return
        from .textstyles import make_text
        entity = make_text(self.document, Point(self.insertion_point.x, self.insertion_point.y), text,
                           layer=self.document.layers.current_layer)
        self.document.undo_stack.push(AddEntityCommand(self.document, entity, "Text"))
        self.finish()

    def on_key(self, key):
        if key == Qt.Key.Key_Escape:
            self.finish()

    def draw_preview(self, painter, canvas):
        if self.insertion_point is not None:
            pen = QPen(PREVIEW_COLOR)
            painter.setPen(pen)
            p = canvas.world_to_screen(self.insertion_point.x, self.insertion_point.y)
            painter.drawEllipse(p, 3, 3)


class DimensionTool(Tool):
    """DIM: click the two points to measure, then click where to place the
    dimension line. Subclasses fix `dim_style` to 'aligned', 'horizontal', or
    'vertical' (see DimensionEntity for what each means).

    If your first click lands on an existing LINE (within snap tolerance)
    instead of empty space, the whole line is used as the source and the
    dimension becomes associative - it'll track that line's endpoints if the
    line is later moved, mirrored, arrayed, etc. (see Document.sync_associative)."""
    name = "DIM"
    dim_style = "aligned"

    def __init__(self, main_window):
        super().__init__(main_window)
        self.p1: Optional[Point] = None
        self.p2: Optional[Point] = None
        self.source_line_id: Optional[str] = None

    def status_prompt(self):
        if self.p1 is None:
            return f"DIM ({self.dim_style}): Specify first extension line origin, or click a line to dimension it"
        if self.p2 is None:
            return f"DIM ({self.dim_style}): Specify second extension line origin"
        return f"DIM ({self.dim_style}): Specify dimension line location"

    def on_click(self, x, y, snap_kind, button):
        if button != Qt.MouseButton.LeftButton.value:
            return
        p = Point(x, y)
        if self.p1 is None:
            from . import geom_ops
            canvas = self.mw.canvas
            tol = canvas.snap_radius_px / canvas.zoom
            line = geom_ops.pick_entity(
                [e for e in self.document.visible_entities() if isinstance(e, LineEntity)], p, tol)
            if line is not None:
                self.p1 = Point(line.p1.x, line.p1.y)
                self.p2 = Point(line.p2.x, line.p2.y)
                self.source_line_id = line.id
            else:
                self.p1 = p
        elif self.p2 is None:
            self.p2 = p
        else:
            entity = DimensionEntity(Point(self.p1.x, self.p1.y), Point(self.p2.x, self.p2.y), p,
                                      dim_style=self.dim_style, style_name=self.document.current_dimstyle, source_line_id=self.source_line_id,
                                      layer=self.document.layers.current_layer)
            self.document.undo_stack.push(AddEntityCommand(self.document, entity, "Dimension"))
            self.finish()

    def on_key(self, key):
        if key == Qt.Key.Key_Escape:
            self.finish()

    def draw_preview(self, painter, canvas):
        cur = self.mw.current_world_pos
        if cur is None:
            return
        pen = QPen(PREVIEW_COLOR)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        if self.p1 is not None and self.p2 is None:
            p1s = canvas.world_to_screen(self.p1.x, self.p1.y)
            p2s = canvas.world_to_screen(cur[0], cur[1])
            painter.drawLine(p1s, p2s)
        elif self.p1 is not None and self.p2 is not None:
            preview = DimensionEntity(Point(self.p1.x, self.p1.y), Point(self.p2.x, self.p2.y),
                                       Point(cur[0], cur[1]), dim_style=self.dim_style)
            dl1, dl2 = preview.dimension_line_points()
            painter.drawLine(canvas.world_to_screen(self.p1.x, self.p1.y),
                              canvas.world_to_screen(dl1.x, dl1.y))
            painter.drawLine(canvas.world_to_screen(self.p2.x, self.p2.y),
                              canvas.world_to_screen(dl2.x, dl2.y))
            painter.drawLine(canvas.world_to_screen(dl1.x, dl1.y), canvas.world_to_screen(dl2.x, dl2.y))


class DimAlignedTool(DimensionTool):
    name = "DIMALIGNED"
    dim_style = "aligned"


class DimHorizontalTool(DimensionTool):
    name = "DIMHORIZONTAL"
    dim_style = "horizontal"


class DimVerticalTool(DimensionTool):
    name = "DIMVERTICAL"
    dim_style = "vertical"


class HatchTool(Tool):
    """HATCH: click a point inside an enclosed area - it can be bounded by
    ANY mix of lines/arcs/circles/polylines/splines, not just a single
    pre-existing closed shape (see geom_ops.flood_fill_boundary). Falls
    back to the old "click directly on a closed circle/polyline" behavior
    if boundary detection doesn't find an enclosed area at that point (e.g.
    clicking exactly on a circle you want to fill still works). Then
    keep picking additional regions, optionally revise settings, and press
    Enter to commit them together. U removes the last staged region."""
    name = "HATCH"

    def __init__(self, main_window):
        super().__init__(main_window)
        self.boundary_points: Optional[List[Point]] = None
        self.source_entity = None  # set only for the single-shape fallback path (enables associativity)
        self.holes = []
        self.areas = []
        self.combined = False
        self._pick_revision = None
        from .hatch_ui import defaults
        self.options = defaults()
        self.associative = True

    def status_prompt(self):
        count=len(self.areas)
        return (f"HATCH: {count} area(s) selected; pick more, Enter apply, U remove last, A manage areas, C combine, Separate, Settings, Esc cancel"
                if count else "HATCH: Pick inside one or more areas (or click closed boundaries); Settings, Esc to cancel")

    def _current(self):
        area=self.areas[-1] if self.areas else None
        self.boundary_points=area['boundary'] if area else None
        self.holes=area['holes'] if area else []
        self.source_entity=area['source'] if area else None

    def on_click(self,x,y,snap_kind,button):
        if button!=Qt.MouseButton.LeftButton.value:return
        from .geom_ops import point_in_polygon
        from .hatching import render_loops
        for area in self.areas:
            h=HatchEntity(area['boundary'],holes=area['holes'],**self.options)
            if sum(point_in_polygon(Point(x,y),loop) for loop in render_loops(h))%2:
                return  # Repeated clicks in an already selected filled region do not duplicate it.
        self.boundary_points=None;self.holes=[];self.source_entity=None
        try:self._detect_area(x,y)
        except Exception:
            self._current();raise
        if self.boundary_points is not None:
            import copy
            # Boundary fallback clicks can lie exactly on a previously queued outline.
            source=self.source_entity
            duplicate=source is not None and any(area['source'] is source for area in self.areas)
            if not duplicate:
                if not self.areas:self._pick_revision=(self.document.render_revision,len(self.document.entities))
                self.areas.append(dict(boundary=copy.deepcopy(self.boundary_points),holes=copy.deepcopy(self.holes),source=source))
        self._current()
        self.mw.canvas.viewport().update()

    def _detect_area(self,x,y):
        from . import geom_ops
        click = Point(x, y)
        canvas = self.mw.canvas

        vw, vh = canvas.viewport().width(), canvas.viewport().height()
        top_left = canvas.screen_to_world(0, 0)
        bottom_right = canvas.screen_to_world(vw, vh)
        bbox = (min(top_left.x(), bottom_right.x()), min(top_left.y(), bottom_right.y()),
                max(top_left.x(), bottom_right.x()), max(top_left.y(), bottom_right.y()))
        from .appsettings import get_settings
        from .hatching import bridge_gaps
        boundary_set=bridge_gaps(self.document.visible_entities(),float(get_settings().value('hatch/gap_tolerance',0)))
        detected = geom_ops.flood_fill_boundary(boundary_set, click, bbox, resolution=300)
        if detected is not None:
            self.boundary_points = detected
            self.source_entity = None
            # Preserve interior closed loops instead of filling across them.
            from .hatch_ui import loop_for
            from .geom_ops import point_in_polygon
            for entity in self.document.visible_entities():
                if isinstance(entity, CircleEntity) or isinstance(entity,PolylineEntity) and entity.closed:
                    loop=loop_for(entity)
                    if loop and all(point_in_polygon(p,detected) for p in loop) and not point_in_polygon(click,loop):
                        self.holes.append(loop)
            return

        # Fallback: click directly on a single closed circle/polyline (also
        # the only path that gets an associative hatch, since it has one
        # clear source entity to track)
        tol = canvas.snap_radius_px / canvas.zoom
        candidates = [e for e in self.document.visible_entities()
                      if isinstance(e, CircleEntity) or (isinstance(e, PolylineEntity) and e.closed)]
        entity = geom_ops.pick_entity(candidates, click, tol)
        if entity is not None:
            if isinstance(entity, CircleEntity):
                self.boundary_points = geom_ops.circle_to_polygon(entity.center, entity.radius)
            else:
                self.boundary_points = [Point(p.x, p.y) for p in entity.points]
            self.source_entity = entity

    def on_text_input(self, text: str):
        text = text.strip()
        if text.upper() in ('A','AREAS'):
            from .productivity_ui import revise_hatch_areas
            revise_hatch_areas(self.mw,self);return
        if text.upper() in ('C','COMBINE','SEPARATE'):
            self.combined=text.upper()!='SEPARATE';self.mw.canvas.viewport().update();return
        if text.upper() in ('U','UNDO','REMOVE','REMOVE LAST'):
            if self.areas:self.areas.pop()
            self._current();self.mw.canvas.viewport().update();return
        if text.upper() in ('SETTINGS','S','OPTIONS'):
            from .hatch_ui import HatchDialog
            from PyQt6.QtWidgets import QDialog
            boundary=self.boundary_points or [Point(0,0),Point(50,0),Point(50,50),Point(0,50)]
            dialog=HatchDialog(self.mw,HatchEntity(boundary,holes=self.holes,source_entity_id=self.source_entity.id if self.source_entity else None,**self.options))
            if dialog.exec()==QDialog.DialogCode.Accepted:
                self.options=dialog.values();self.associative=dialog.associative.isChecked()
            return
        if self.boundary_points is None:
            return
        pattern, angle, spacing = (self.options.get('pattern','LINES'),self.options.get('angle',45),self.options.get('spacing',5))
        from .hatching import pattern_names
        if text.upper() in pattern_names():
            pattern = text.upper()
        elif text:
            try:
                parts = [float(v) for v in text.split(",")]
                angle = parts[0]
                spacing = parts[1] if len(parts) > 1 else spacing
            except ValueError:
                raise ValueError('Use a pattern name, Settings, or angle,spacing')
        self._commit(pattern, angle, spacing)
        self.finish()

    def on_key(self, key):
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self.boundary_points is not None:
            self._commit(self.options.get('pattern','LINES'),self.options.get('angle',45),self.options.get('spacing',5))
            self.finish()
        elif key == Qt.Key.Key_Escape:
            self.finish()

    def _commit(self, pattern, angle, spacing):
        import copy
        if self.areas and self._pick_revision!=(self.document.render_revision,len(self.document.entities)):
            raise ValueError('Drawing changed while picking hatch areas; cancel and pick the areas again')
        areas=self.areas or [dict(boundary=self.boundary_points,holes=self.holes,source=self.source_entity)]
        hatches=[]
        for area in areas:
            source=area['source'];options=copy.deepcopy(self.options)
            if pattern!=options.get('pattern','LINES'):options['pattern_definition']=[]
            options.update(pattern=pattern,angle=angle,spacing=spacing)
            options.setdefault('color',source.color if source is not None else 'BYLAYER')
            hatches.append(HatchEntity(copy.deepcopy(area['boundary']),holes=copy.deepcopy(area['holes']),**options,
                source_entity_id=source.id if source is not None and self.associative else None,
                layer=self.document.layers.current_layer))
        if self.combined:
            from .hatch_areas import make
            options=copy.deepcopy(self.options);options.update(pattern=pattern,angle=angle,spacing=spacing)
            hatches=make(areas,options,self.document.layers.current_layer,True,False)
        from .native_io import document_to_dict,entity_to_dict
        from .validation import validate_payload
        candidate=document_to_dict(self.document);candidate['entities'].extend(entity_to_dict(h) for h in hatches);validate_payload(candidate)
        self.document.undo_stack.beginMacro('Hatch multiple areas' if len(hatches)>1 else 'Hatch')
        try:
            for hatch in hatches:self.document.undo_stack.push(AddEntityCommand(self.document,hatch,'Hatch'))
        finally:self.document.undo_stack.endMacro()

    def draw_preview(self,painter,canvas):
        if self.boundary_points is None:return
        areas=self.areas or [dict(boundary=self.boundary_points,holes=self.holes,source=self.source_entity)]
        from .hatching import paint
        for area in areas:
            painter.save()
            try:
                preview=HatchEntity(area['boundary'],holes=area['holes'],**self.options)
                painter.setPen(QPen(PREVIEW_COLOR));painter.setOpacity(.5);paint(canvas,painter,preview)
                painter.setOpacity(1);pen=QPen(PREVIEW_COLOR);pen.setStyle(Qt.PenStyle.DashLine);painter.setPen(pen)
                for loop in [area['boundary'],*area['holes']]:
                    path=QPainterPath()
                    if loop:
                        path.moveTo(canvas.world_to_screen(loop[0].x,loop[0].y))
                        for point in loop[1:]:path.lineTo(canvas.world_to_screen(point.x,point.y))
                        path.closeSubpath();painter.drawPath(path)
            finally:painter.restore()


class DistanceTool(Tool):
    """DIST: report the exact distance and angle between two picked points."""
    name = "DIST"

    def status_prompt(self):
        return "DIST: Specify first point" if not self.points else "DIST: Specify second point"

    def on_click(self, x, y, snap_kind, button):
        if button != Qt.MouseButton.LeftButton.value:
            return
        self.points.append(Point(x, y))
        if len(self.points) == 2:
            first, second = self.points
            dx, dy = second.x - first.x, second.y - first.y
            distance = math.hypot(dx, dy)
            angle = math.degrees(math.atan2(dy, dx)) % 360.0
            from .units import format_length, format_angle
            fmt = lambda v: format_length(v, self.document.units, self.document.unit_settings)
            self.mw.command_history.appendPlainText(
                f"DIST = {fmt(distance)}  delta=({fmt(dx)}, {fmt(dy)})  angle={format_angle(angle, self.document.unit_settings)}"
            )
            self.mw.tool_label.setText(f"Distance {fmt(distance)}")
            self.finish()

    def on_text_input(self, text: str):
        point = self.parse_point(text, self.points[-1] if self.points else None)
        if point:
            self.on_click(point.x, point.y, "", Qt.MouseButton.LeftButton.value)

    def on_key(self, key):
        if key == Qt.Key.Key_Escape:
            self.finish()

    def draw_preview(self, painter, canvas):
        if not self.points or self.mw.current_world_pos is None:
            return
        pen = QPen(PREVIEW_COLOR)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        start = self.points[0]
        current = self.mw.current_world_pos
        painter.drawLine(canvas.world_to_screen(start.x, start.y),
                         canvas.world_to_screen(current[0], current[1]))


class AreaTool(Tool):
    """AREA: accumulate a boundary and report shoelace area/perimeter."""
    name = "AREA"

    def status_prompt(self):
        if len(self.points) < 3:
            return "AREA: Specify boundary point (Enter to finish)"
        return "AREA: Specify next point (Enter to finish)"

    def on_click(self, x, y, snap_kind, button):
        if button == Qt.MouseButton.LeftButton.value:
            self.points.append(Point(x, y))

    def _report(self):
        if len(self.points) < 3:
            self.finish()
            return
        area = 0.0
        perimeter = 0.0
        for first, second in zip(self.points, self.points[1:] + self.points[:1]):
            area += first.x * second.y - second.x * first.y
            perimeter += first.distance_to(second)
        area = abs(area) / 2.0
        self.mw.command_history.appendPlainText(
            f"AREA = {area:.6f} square {self.document.units}  PERIMETER = {perimeter:.6f} {self.document.units}"
        )
        self.mw.tool_label.setText(f"Area {area:.6f} square {self.document.units}")
        self.finish()

    def on_text_input(self, text: str):
        if text.strip().lower() in ("", "enter", "close"):
            self._report()
            return
        point = self.parse_point(text, self.points[-1] if self.points else None)
        if point:
            self.points.append(point)

    def on_key(self, key):
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._report()
        elif key == Qt.Key.Key_Escape:
            self.finish()

    def draw_preview(self, painter, canvas):
        if not self.points:
            return
        pen = QPen(PREVIEW_COLOR)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        points = list(self.points)
        if self.mw.current_world_pos is not None:
            x, y = self.mw.current_world_pos
            points.append(Point(x, y))
        for first, second in zip(points, points[1:]):
            painter.drawLine(canvas.world_to_screen(first.x, first.y),
                             canvas.world_to_screen(second.x, second.y))


class CopyTool(Tool):
    """COPY: uses the current selection. Click a base point, then click a
    destination point - the selection is copied (originals untouched).
    Keeps running so you can click more destinations for multiple copies
    from the same base point (AutoCAD's default COPY behavior); Enter/Esc
    to stop."""
    name = "COPY"

    def __init__(self, main_window):
        super().__init__(main_window)
        self.base_point: Optional[Point] = None

    def status_prompt(self):
        if not self.mw.canvas.selected_entities:
            return "COPY: No objects selected - select objects first, then run COPY"
        if self.base_point is None:
            return "COPY: Specify base point"
        return "COPY: Specify destination point (click again for more copies, Enter/Esc to finish)"

    def on_click(self, x, y, snap_kind, button):
        if button != Qt.MouseButton.LeftButton.value:
            return
        if not self.mw.canvas.selected_entities:
            self.finish()
            return
        p = Point(x, y)
        if self.base_point is None:
            self.base_point = p
            return
        dx, dy = p.x - self.base_point.x, p.y - self.base_point.y
        selected = list(self.mw.canvas.selected_entities)
        self.document.undo_stack.beginMacro("Copy")
        for e in selected:
            clone = e.clone()
            clone.translate(dx, dy)
            self.document.undo_stack.push(AddEntityCommand(self.document, clone, "Copy"))
        self.document.undo_stack.endMacro()

    def on_text_input(self, text):
        if not text:
            self.finish()
            return
        point = self.parse_point(text, self.base_point)
        if point:
            self.on_click(point.x, point.y, "", Qt.MouseButton.LeftButton.value)

    def on_key(self, key):
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Escape):
            self.finish()

    def draw_preview(self, painter, canvas):
        if self.base_point is None or self.mw.current_world_pos is None:
            return
        pen = QPen(PREVIEW_COLOR)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        p1 = canvas.world_to_screen(self.base_point.x, self.base_point.y)
        cur = self.mw.current_world_pos
        p2 = canvas.world_to_screen(cur[0], cur[1])
        painter.drawLine(p1, p2)


class RotateTool(Tool):
    """ROTATE: uses the current selection. Click a base point (pivot), then
    either click a point to set the rotation angle (measured from horizontal
    through the base point) or type an angle in degrees."""
    name = "ROTATE"

    def __init__(self, main_window):
        super().__init__(main_window)
        self.base_point: Optional[Point] = None

    def status_prompt(self):
        if not self.mw.canvas.selected_entities:
            return "ROTATE: No objects selected - select objects first, then run ROTATE"
        if self.base_point is None:
            return "ROTATE: Specify base point"
        return "ROTATE: Specify rotation angle (click a point, or type degrees)"

    def on_click(self, x, y, snap_kind, button):
        if button != Qt.MouseButton.LeftButton.value:
            return
        if not self.mw.canvas.selected_entities:
            self.finish()
            return
        p = Point(x, y)
        if self.base_point is None:
            self.base_point = p
            return
        from . import geom_ops
        angle = geom_ops.angle_of(self.base_point, p)
        self._commit(angle)
        self.finish()

    def on_text_input(self, text: str):
        if self.base_point is None:
            return
        try:
            angle = float(text.strip())
        except ValueError:
            return
        self._commit(angle)
        self.finish()

    def _commit(self, angle: float):
        from .document import RotateEntitiesCommand
        selected = list(self.mw.canvas.selected_entities)
        self.document.undo_stack.push(
            RotateEntitiesCommand(self.document, selected, self.base_point, angle, "Rotate"))

    def on_key(self, key):
        if key == Qt.Key.Key_Escape:
            self.finish()

    def draw_preview(self, painter, canvas):
        if self.base_point is None or self.mw.current_world_pos is None:
            return
        pen = QPen(PREVIEW_COLOR)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        p1 = canvas.world_to_screen(self.base_point.x, self.base_point.y)
        cur = self.mw.current_world_pos
        p2 = canvas.world_to_screen(cur[0], cur[1])
        painter.drawLine(p1, p2)


class ScaleTool(Tool):
    """SCALE: uses the current selection. Click a base point, then either
    type a scale factor directly, or click two reference points - the
    factor becomes dist(base, second click) / dist(base, first click),
    mirroring AutoCAD's Reference option."""
    name = "SCALE"

    def __init__(self, main_window):
        super().__init__(main_window)
        self.base_point: Optional[Point] = None
        self.ref_points: List[Point] = []

    def status_prompt(self):
        if not self.mw.canvas.selected_entities:
            return "SCALE: No objects selected - select objects first, then run SCALE"
        if self.base_point is None:
            return "SCALE: Specify base point"
        return "SCALE: Type a scale factor, or click two points to set it by reference"

    def on_click(self, x, y, snap_kind, button):
        if button != Qt.MouseButton.LeftButton.value:
            return
        if not self.mw.canvas.selected_entities:
            self.finish()
            return
        p = Point(x, y)
        if self.base_point is None:
            self.base_point = p
            return
        self.ref_points.append(p)
        if len(self.ref_points) == 2:
            d1 = self.base_point.distance_to(self.ref_points[0])
            d2 = self.base_point.distance_to(self.ref_points[1])
            if d1 > 1e-9:
                self._commit(d2 / d1)
            self.finish()

    def on_text_input(self, text: str):
        if self.base_point is None:
            return
        try:
            factor = float(text.strip())
            if not math.isfinite(factor) or factor <= 0:
                raise ValueError("Scale factor must be finite and positive")
        except ValueError:
            return
        if factor != 0:
            self._commit(factor)
        self.finish()

    def _commit(self, factor: float):
        from .document import ScaleEntitiesCommand
        selected = list(self.mw.canvas.selected_entities)
        self.document.undo_stack.push(
            ScaleEntitiesCommand(self.document, selected, self.base_point, factor, "Scale"))

    def on_key(self, key):
        if key == Qt.Key.Key_Escape:
            self.finish()


class SplineTool(Tool):
    """SPLINE: click a sequence of fit points; the curve passes through
    every one of them (Catmull-Rom). 'C' closes it into a loop, Enter
    finishes an open curve."""
    name = "SPLINE"

    def status_prompt(self):
        if not self.points:
            return "SPLINE: Specify first point"
        return "SPLINE: Specify next point (C to close, Enter to finish)"

    def on_click(self, x, y, snap_kind, button):
        if button != Qt.MouseButton.LeftButton.value:
            return
        self.points.append(Point(x, y))

    def on_text_input(self, text: str):
        t = text.strip().lower()
        if t in ("u", "undo"):
            if self.points:
                self.points.pop()
            return
        if t == "c":
            self._commit(closed=True)
            self.finish()
            return
        if t in ("", "enter"):
            self._commit(closed=False)
            self.finish()
            return
        last = self.points[-1] if self.points else None
        p = self.parse_point(text, last)
        if p:
            self.points.append(p)

    def on_key(self, key):
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._commit(closed=False)
            self.finish()
        elif key == Qt.Key.Key_Escape:
            self.finish()

    def _commit(self, closed: bool):
        if len(self.points) >= 2:
            entity = SplineEntity([Point(p.x, p.y) for p in self.points], closed=closed,
                                   layer=self.document.layers.current_layer,
                                   linetype=self.document.current_linetype)
            self.document.undo_stack.push(AddEntityCommand(self.document, entity, "Spline"))

    def draw_preview(self, painter, canvas):
        if not self.points:
            return
        cur = self.mw.current_world_pos
        pen = QPen(PREVIEW_COLOR)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        pts = [canvas.world_to_screen(p.x, p.y) for p in self.points]
        for a, b in zip(pts, pts[1:]):
            painter.drawLine(a, b)
        if cur is not None and pts:
            painter.drawLine(pts[-1], canvas.world_to_screen(cur[0], cur[1]))


class DimRadialTool(Tool):
    """Shared base for DIMRADIUS/DIMDIAMETER: click a circle or arc, then
    click where the label should sit. Subclasses set `dim_style`."""
    name = "DIMRADIAL"
    dim_style = "radius"

    def __init__(self, main_window):
        super().__init__(main_window)
        self.source_entity = None
        self.circle_point: Optional[Point] = None

    def status_prompt(self):
        if self.source_entity is None:
            return f"DIM{self.dim_style.upper()}: Select a circle or arc"
        return f"DIM{self.dim_style.upper()}: Specify label position"

    def on_click(self, x, y, snap_kind, button):
        if button != Qt.MouseButton.LeftButton.value:
            return
        from . import geom_ops
        click = Point(x, y)
        if self.source_entity is None:
            canvas = self.mw.canvas
            tol = canvas.snap_radius_px / canvas.zoom
            candidates = [e for e in self.document.visible_entities()
                          if isinstance(e, (CircleEntity, ArcEntity))]
            entity = geom_ops.pick_entity(candidates, click, tol)
            if entity is not None:
                self.source_entity = entity
                angle = geom_ops.angle_of(entity.center, click)
                self.circle_point = Point(
                    entity.center.x + entity.radius * math.cos(math.radians(angle)),
                    entity.center.y + entity.radius * math.sin(math.radians(angle)))
        else:
            dim = DimensionEntity(Point(self.source_entity.center.x, self.source_entity.center.y),
                                   Point(self.circle_point.x, self.circle_point.y), click,
                                   dim_style=self.dim_style, style_name=self.document.current_dimstyle, layer=self.document.layers.current_layer)
            self.document.undo_stack.push(AddEntityCommand(self.document, dim, "Dimension"))
            self.finish()

    def on_key(self, key):
        if key == Qt.Key.Key_Escape:
            self.finish()

    def draw_preview(self, painter, canvas):
        if self.source_entity is None or self.mw.current_world_pos is None:
            return
        pen = QPen(PREVIEW_COLOR)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        p1 = canvas.world_to_screen(self.circle_point.x, self.circle_point.y)
        cur = self.mw.current_world_pos
        p2 = canvas.world_to_screen(cur[0], cur[1])
        painter.drawLine(p1, p2)


class DimRadiusTool(DimRadialTool):
    name = "DIMRADIUS"
    dim_style = "radius"


class DimDiameterTool(DimRadialTool):
    name = "DIMDIAMETER"
    dim_style = "diameter"


class BlockTool(Tool):
    """BLOCK: uses the current selection. Click a base point (the block's
    insertion origin), then type a name. The selected entities are removed
    from the drawing and replaced by a single block reference at the base
    point - the same "define once, insert as one object" behavior AutoCAD's
    BLOCK command has. Undo restores the original loose entities."""
    name = "BLOCK"

    def __init__(self, main_window):
        super().__init__(main_window)
        self.base_point: Optional[Point] = None

    def status_prompt(self):
        if not self.mw.canvas.selected_entities:
            return "BLOCK: No objects selected - select objects first, then run BLOCK"
        if self.base_point is None:
            return "BLOCK: Specify base point (insertion origin)"
        return "BLOCK: Type a name for the block, Enter"

    def on_click(self, x, y, snap_kind, button):
        if button != Qt.MouseButton.LeftButton.value:
            return
        if not self.mw.canvas.selected_entities:
            self.finish()
            return
        if self.base_point is None:
            self.base_point = Point(x, y)

    def on_text_input(self, text: str):
        name = text.strip()
        if self.base_point is None or not name:
            return
        if name in self.document.blocks:
            return  # name clash - refuse silently rather than clobber an existing block
        selected = list(self.mw.canvas.selected_entities)
        local_entities = []
        for e in selected:
            clone = e.clone()
            clone.translate(-self.base_point.x, -self.base_point.y)
            local_entities.append(clone)
        block_def = BlockDefinition(name, local_entities)
        ref = BlockReferenceEntity(name, Point(self.base_point.x, self.base_point.y),
                                    layer=self.document.layers.current_layer)
        ref.rebuild(block_def)

        from .document import AddBlockCommand
        self.document.undo_stack.beginMacro("Create Block")
        self.document.undo_stack.push(AddBlockCommand(self.document, block_def))
        self.document.undo_stack.push(DeleteEntitiesCommand(self.document, selected, "Block source"))
        self.document.undo_stack.push(AddEntityCommand(self.document, ref, "Block reference"))
        self.document.undo_stack.endMacro()
        self.mw.canvas.selected_entities = []
        self.finish()

    def on_key(self, key):
        if key == Qt.Key.Key_Escape:
            self.finish()


class InsertBlockTool(Tool):
    """INSERT: type a block name (or it's preset when launched from the
    Insert Block dialog / Xref menu action), then click where to place it."""
    name = "INSERT"

    def __init__(self, main_window):
        super().__init__(main_window)
        self.preset_block_name: Optional[str] = None
        self.block_name: Optional[str] = self.preset_block_name

    def status_prompt(self):
        if not self.block_name:
            names = ", ".join(self.document.blocks.keys()) or "(none defined)"
            return f"INSERT: Type a block name to place [{names}]"
        return f"INSERT ({self.block_name}): Specify insertion point"

    def on_text_input(self, text: str):
        name = text.strip()
        if not self.block_name:
            if name in self.document.blocks:
                self.block_name = name
            return

    def on_click(self, x, y, snap_kind, button):
        if button != Qt.MouseButton.LeftButton.value or not self.block_name:
            return
        block_def = self.document.blocks.get(self.block_name)
        ref = BlockReferenceEntity(self.block_name, Point(x, y), layer=self.document.layers.current_layer)
        ref.rebuild(block_def)
        self.document.undo_stack.push(AddEntityCommand(self.document, ref, "Insert block"))
        self.finish()

    def on_key(self, key):
        if key == Qt.Key.Key_Escape:
            self.finish()

    def draw_preview(self, painter, canvas):
        if not self.block_name or self.mw.current_world_pos is None:
            return
        block_def = self.document.blocks.get(self.block_name)
        if block_def is None:
            return
        cur = self.mw.current_world_pos
        pen = QPen(PREVIEW_COLOR)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        for e in block_def.entities:
            clone = e.clone()
            clone.translate(cur[0], cur[1])
            # reuse whatever the canvas already knows how to draw, just in the preview color
            canvas._draw_entity(painter, clone)


class XClipTool(Tool):
    """XCLIP: select a block/xref reference first, run this, then click two
    corners to set its clip boundary - anything outside that rectangle
    (in world space, moves with the reference from then on) is hidden.
    This is an approximate clip (whole entities in/out by bounding-box
    test), not true clipping exactly at the boundary line - see README."""
    name = "XCLIP"

    def __init__(self, main_window):
        super().__init__(main_window)
        self.target: Optional[BlockReferenceEntity] = None

    def status_prompt(self):
        if self.target is None:
            return "XCLIP: Select a block/xref reference first, then run this command"
        if not self.points:
            return "XCLIP: Specify first corner of the clip boundary"
        return "XCLIP: Specify opposite corner"

    def on_click(self, x, y, snap_kind, button):
        if button != Qt.MouseButton.LeftButton.value:
            return
        if self.target is None:
            selected = [e for e in self.mw.canvas.selected_entities if isinstance(e, BlockReferenceEntity)]
            if not selected:
                self.finish()
                return
            self.target = selected[0]
            return
        if not self.points:
            self.points.append(Point(x, y))
        else:
            x0, y0 = self.points[0].x, self.points[0].y
            boundary = [Point(x0, y0), Point(x, y0), Point(x, y), Point(x0, y)]
            from .document import SetAttrCommand
            self.document.undo_stack.push(SetAttrCommand(self.document,self.target,'clip_boundary',self.target.clip_boundary,boundary,'Clip reference'))
            self.finish()

    def on_key(self, key):
        if key == Qt.Key.Key_Escape:
            self.finish()

    def draw_preview(self, painter, canvas):
        if self.target is None or not self.points:
            return
        cur = self.mw.current_world_pos
        if cur is None:
            return
        pen = QPen(PREVIEW_COLOR)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        p1 = canvas.world_to_screen(self.points[0].x, self.points[0].y)
        p2 = canvas.world_to_screen(cur[0], cur[1])
        from PyQt6.QtCore import QRectF
        painter.drawRect(QRectF(p1, p2).normalized())


class AddViewportTool(Tool):
    """Layout-space only: click two corners to place a new Viewport on the
    current layout's paper, auto-scaled and centered to fit the current
    Model Space extents. A layout can carry as many viewports as you like -
    each one just needs its own placement rectangle."""
    name = "ADDVIEWPORT"

    def status_prompt(self):
        if self.document.current_space == "Model":
            return "ADDVIEWPORT: Switch to a Layout tab first"
        if not self.points:
            return "ADDVIEWPORT: Specify first corner"
        return "ADDVIEWPORT: Specify opposite corner"

    def on_click(self, x, y, snap_kind, button):
        if button != Qt.MouseButton.LeftButton.value or self.document.current_space == "Model":
            return
        if not self.points:
            self.points.append(Point(x, y))
        else:
            layout = self.document.layouts.get(self.document.current_space)
            if layout is None:
                self.finish()
                return
            x0, y0 = min(self.points[0].x, x), min(self.points[0].y, y)
            w, h = abs(x - self.points[0].x), abs(y - self.points[0].y)
            if w > 1e-6 and h > 1e-6:
                model_entities = self.document.entities
                from .underlays import bounds as underlay_bounds
                boxes = [e.bbox() for e in model_entities] + underlay_bounds(self.document)
                if boxes:
                    bbox = (min(b[0] for b in boxes), min(b[1] for b in boxes),
                            max(b[2] for b in boxes), max(b[3] for b in boxes))
                else:
                    bbox = (0.0, 0.0, 100.0, 100.0)
                from .document import AddViewportCommand
                self.document.undo_stack.push(
                    AddViewportCommand(self.document, layout, x0, y0, w, h, bbox, "Add Viewport"))
            self.finish()

    def on_key(self, key):
        if key == Qt.Key.Key_Escape:
            self.finish()

    def draw_preview(self, painter, canvas):
        if not self.points:
            return
        cur = self.mw.current_world_pos
        if cur is None:
            return
        pen = QPen(PREVIEW_COLOR)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        p1 = canvas.world_to_screen(self.points[0].x, self.points[0].y)
        p2 = canvas.world_to_screen(cur[0], cur[1])
        from PyQt6.QtCore import QRectF
        painter.drawRect(QRectF(p1, p2).normalized())


class MoveTool(CopyTool):
    name = "MOVE"

    def __init__(self, main_window):
        super().__init__(main_window)
        self.picking_base = False

    def selection_anchor(self):
        """Reference the first selected object, independently of cursor position."""
        selected = self.mw.canvas.selected_entities
        if not selected:
            raise ValueError("Select objects before MOVE")
        entity = selected[0]
        for attr in ("insertion_point", "position", "point", "center", "p1"):
            point = getattr(entity, attr, None)
            if isinstance(point, Point):
                return Point(point.x, point.y)
        for attr in ("points", "boundary"):
            points = getattr(entity, attr, None)
            if points:
                return Point(points[0].x, points[0].y)
        x, y, _, _ = entity.bbox()
        return Point(x, y)

    def keyword_options(self):
        from .command_options import Option
        return [Option("B", "Base point", aliases=("BASE", "BASEPOINT"))]

    def status_prompt(self):
        if not self.mw.canvas.selected_entities:
            return "MOVE: Select objects first"
        if self.base_point is not None:
            return "MOVE: Destination x,y or @dx,dy (B resets base point)"
        if self.picking_base:
            return "MOVE: Specify base point x,y or click, then destination"
        anchor = self.selection_anchor()
        return (f"MOVE: Destination x,y / @dx,dy; reference {anchor.x:g},{anchor.y:g} "
                "on first selected object; click or B for base point")

    def move_to(self, point):
        selected = list(self.mw.canvas.selected_entities)
        if not selected:
            raise ValueError("Select objects before MOVE")
        current = {e.id: e for e in self.document.entities}
        if self.mw.document is not self.document or any(
                current.get(e.id) is not e or not self.document.is_editable(e)
                for e in selected):
            raise ValueError("Selection changed or contains locked/hidden objects; select again")
        base = self.base_point or self.selection_anchor()
        dx, dy = point.x-base.x, point.y-base.y
        if not all(math.isfinite(v) for v in (point.x, point.y, dx, dy)):
            raise ValueError("Use finite coordinates and displacement")
        for entity in selected:
            x0,y0,x1,y1 = entity.bbox()
            if not all(math.isfinite(v) for v in (x0+dx,y0+dy,x1+dx,y1+dy)):
                raise ValueError("Move would produce non-finite geometry")
        if dx or dy:
            self.document.undo_stack.push(TranslateEntitiesCommand(
                self.document, selected, dx, dy, "Move"))
        self.finish()

    def on_click(self, x, y, snap_kind, button):
        if button != Qt.MouseButton.LeftButton.value:
            return
        if not self.mw.canvas.selected_entities:
            raise ValueError("Select objects before MOVE")
        if self.base_point is None:
            self.base_point = Point(x, y)
            self.picking_base = False
        else:
            self.move_to(Point(x, y))

    def on_text_input(self, text):
        text = text.strip()
        if not text:
            self.finish()
            return
        if text.upper() in ("B", "BASE", "BASEPOINT"):
            self.base_point = None
            self.picking_base = True
            return
        reference = self.base_point or self.selection_anchor()
        point = self.parse_point(text, reference)
        if point is None:
            raise ValueError("Enter destination x,y, relative @dx,dy, or B for an explicit base point")
        if self.picking_base:
            self.base_point = point
            self.picking_base = False
        else:
            self.move_to(point)


TOOL_REGISTRY = {
    "LINE": LineTool,
    "PLINE": PolylineTool,
    "POLYLINE": PolylineTool,
    "CIRCLE": CircleTool,
    "POINT": PointTool,
    "ELLIPSE": EllipseTool,
    "RAY": RayTool,
    "XLINE": XLineTool,
    "RECTANGLE": RectangleTool,
    "RECT": RectangleTool,
    "ARC": ArcTool,
    "SPLINE": SplineTool,
    "SELECT": SelectTool,
    "COPY": CopyTool,
    "MOVE": MoveTool,
    "ROTATE": RotateTool,
    "SCALE": ScaleTool,
    "OFFSET": OffsetTool,
    "MIRROR": MirrorTool,
    "ARRAYRECT": ArrayRectTool,
    "ARRAYPOLAR": ArrayPolarTool,
    "FILLET": FilletTool,
    "CHAMFER": ChamferTool,
    "TRIM": TrimTool,
    "EXTEND": ExtendTool,
    "TEXT": TextTool,
    "DTEXT": TextTool,
    "DIMALIGNED": DimAlignedTool,
    "DIMLINEAR": DimAlignedTool,
    "DIMHORIZONTAL": DimHorizontalTool,
    "DIMVERTICAL": DimVerticalTool,
    "DIMRADIUS": DimRadiusTool,
    "DIMDIAMETER": DimDiameterTool,
    "HATCH": HatchTool,
    "DIST": DistanceTool,
    "DISTANCE": DistanceTool,
    "AREA": AreaTool,
    "BLOCK": BlockTool,
    "INSERT": InsertBlockTool,
    "ADDVIEWPORT": AddViewportTool,
    "XCLIP": XClipTool,
}
