"""Interactive ZOOM choices and per-drawing, per-space previous views."""

import copy
import math
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QPen
from .tools import Tool, SelectTool
from .command_options import Option
from .geometry import Point


class ZoomTool(Tool):
    name = "ZOOM"

    def __init__(self, mw):
        super().__init__(mw)
        self.mode = "choices"
        self.view = mw.model_workspace.active if mw.model_workspace is not None and mw.viewport_stack.currentWidget() is mw.model_workspace else None
        self.key = (self.document.current_space, id(self.view) if self.view else 0)

    def status_prompt(self):
        if self.mode == "window":
            return "ZOOM Window: Specify first corner" if not self.points else "ZOOM Window: Specify opposite corner"
        if self.mode == "selected":
            return "ZOOM Selected: Click objects, then Enter"
        return "ZOOM: Choose a highlighted option or enter a positive scale factor <Extents>"

    def sync_view(self):
        view = self.mw.model_workspace.active if self.mw.model_workspace is not None and self.mw.viewport_stack.currentWidget() is self.mw.model_workspace else None
        key = (self.document.current_space, id(view) if view else 0)
        if key != self.key:
            self.mode = "choices"
            self.points = []
        self.view, self.key = view, key

    def keyword_options(self):
        self.sync_view()
        previous = self.key in getattr(self.document, "_zoom_previous_views", {})
        result = [Option("E", "Extents"), Option("A", "All"), Option("P", "Previous", previous), Option("I", "In"), Option("O", "Out")]
        if self.view is None:
            result = [Option("W", "Window"), Option("S", "Selected", self.document.current_space == "Model", aliases=("SE", "SELECTION", "OBJECT", "OBJECTS")), *result, Option("R", "Realtime")]
        result.append(Option("ENTER", "Zoom selected" if self.mode == "selected" else "Extents", self.mode != "selected" or bool(self.mw.canvas.selected_entities)))
        return result

    def snapshot(self):
        if self.view:
            return copy.deepcopy(self.view.camera)
        return self.mw.canvas.zoom, QPointF(self.mw.canvas.pan_offset)

    def remember(self):
        if not hasattr(self.document, "_zoom_previous_views"):
            self.document._zoom_previous_views = {}
        self.document._zoom_previous_views[self.key] = self.snapshot()

    def fit_boxes(self, boxes):
        if not boxes:
            raise ValueError("No visible objects to zoom to")
        if any(not math.isfinite(v) for box in boxes for v in box):
            raise ValueError("Cannot zoom to non-finite bounds")
        x0,y0=min(b[0] for b in boxes),min(b[1] for b in boxes)
        x1,y1=max(b[2] for b in boxes),max(b[3] for b in boxes)
        canvas=self.mw.canvas
        self.remember()
        canvas.zoom=max(.01,min(100000,.85*min(canvas.viewport().width()/max(x1-x0,1e-6),canvas.viewport().height()/max(y1-y0,1e-6))))
        canvas.pan_offset=QPointF((x0+x1)/2,(y0+y1)/2)
        canvas.viewport().update()
        self.finish()

    def on_text_input(self, text):
        self.sync_view()
        value=text.strip().upper()
        if not value:
            if self.mode == "selected":
                selected=[e for e in self.mw.canvas.selected_entities if e in self.document.visible_entities()]
                self.fit_boxes([e.bbox() for e in selected])
                return
            value="E"
        if self.mode == "window":
            point=self.parse_point(text,self.points[-1] if self.points else None)
            if point:
                self.on_click(point.x,point.y,"",Qt.MouseButton.LeftButton.value)
                return
        if value in ("W","WINDOW") and self.view is None:
            self.mode="window";self.points=[];return
        if value in ("S","SE","SELECTED","SELECTION","OBJECT","OBJECTS") and self.view is None:
            if self.mw.canvas.selected_entities:
                self.mode="selected";self.on_text_input("")
            else:
                self.mode="selected"
            return
        if value in ("E","EXTENTS","A","ALL"):
            if value in ("A","ALL") and self.view is None and self.document.current_space=="Model":
                from .underlays import bounds
                self.fit_boxes([e.bbox() for e in self.document.visible_entities()]+bounds(self.document)+[(0,0,0,0)])
            else:
                self.remember();self.mw.fit_active();self.finish()
            return
        if value in ("P","PREVIOUS"):
            history=getattr(self.document,"_zoom_previous_views",{})
            if self.key not in history:raise ValueError("No previous Zoom view in this drawing and space")
            old=history[self.key];history[self.key]=self.snapshot()
            if self.view:
                self.view.camera=old;self.view.navigation.sync(old,self.view.interaction_mode);self.view.update()
            else:
                self.mw.canvas.zoom,self.mw.canvas.pan_offset=old;self.mw.canvas.viewport().update()
            self.finish();return
        if value in ("R","REALTIME") and self.view is None:
            self.remember()
            from .ribbon_actions import realtime_zoom
            realtime_zoom(self.mw);return
        if value in ("I","IN","O","OUT"):
            factor=2.0 if value in ("I","IN") else .5
        else:
            try:factor=float(value[:-1] if value.endswith("X") else value)
            except ValueError:raise ValueError("Choose a highlighted Zoom option or enter a positive scale factor")
            if not math.isfinite(factor) or factor<=0:raise ValueError("Zoom scale must be finite and positive")
        self.remember();self.mw.zoom_active(factor);self.finish()

    def on_click(self,x,y,snap_kind,button):
        if button != Qt.MouseButton.LeftButton.value:return
        if self.mode=="window":
            self.points.append(Point(x,y))
            if len(self.points)==2:
                a,b=self.points
                if abs(a.x-b.x)<1e-9 or abs(a.y-b.y)<1e-9:
                    self.points.pop();raise ValueError("Zoom Window needs nonzero width and height")
                self.fit_boxes([(min(a.x,b.x),min(a.y,b.y),max(a.x,b.x),max(a.y,b.y))])
        elif self.mode=="selected":
            entity=SelectTool(self.mw)._pick_entity(x,y)
            if entity:
                selected=self.mw.canvas.selected_entities
                selected.remove(entity) if entity in selected else selected.append(entity)
                self.mw.canvas.viewport().update()

    def on_key(self,key):
        if key in (Qt.Key.Key_Return,Qt.Key.Key_Enter):self.on_text_input("")
        else:super().on_key(key)

    def draw_preview(self,painter,canvas):
        if self.mode=="window" and self.points and self.mw.current_world_pos:
            a=self.points[0];b=self.mw.current_world_pos
            from .appearance import colors
            painter.setPen(QPen(QColor(colors(canvas)['ui_preview']),1,Qt.PenStyle.DashLine));painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(QRectF(canvas.world_to_screen(a.x,a.y),canvas.world_to_screen(*b)).normalized())
