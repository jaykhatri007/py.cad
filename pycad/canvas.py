"""
canvas.py
The main drawing viewport. Built on QGraphicsView/QGraphicsScene.

Coordinate convention: World Y increases upward (like AutoCAD / math convention),
but Qt's scene Y increases downward. We flip Y when converting world <-> scene.
"""
import functools
import logging
import math
from typing import Optional, List, Tuple

from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsItem
from PyQt6.QtGui import (QPainter, QPen, QColor, QBrush, QMouseEvent, QWheelEvent,
                          QPainterPath, QTransform, QKeyEvent)
from PyQt6.QtCore import Qt, QPointF, QRectF, pyqtSignal

from .geometry import (Point, LineEntity, CircleEntity, ArcEntity, PointEntity, EllipseEntity,
                       RayEntity, XLineEntity, PolylineEntity, TextEntity, DimensionEntity,
                       HatchEntity, SplineEntity, BlockReferenceEntity, Entity)
from .document import Document
from .appearance import colors as ui_colors

logger = logging.getLogger(__name__)


def safe_event(method):
    """Qt calls event handlers as C++ virtual method overrides - an
    unhandled Python exception inside one of these doesn't just print a
    traceback and move on, it can hard-abort the whole process (we hit this
    exact failure mode with a real bug earlier). Wrapping every event
    handler means a bug in one interaction (a bad click, a malformed
    fillet, etc.) logs an error and lets the app keep running, instead of
    losing the person's whole session."""
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except Exception:
            logger.exception("Error in %s", method.__qualname__)
            return None
    return wrapper


GRID_MINOR_COLOR = QColor(45, 45, 48)
GRID_MAJOR_COLOR = QColor(60, 60, 64)
BACKGROUND_COLOR = QColor(30, 30, 32)
SELECT_COLOR = QColor(0, 174, 255)
SNAP_MARKER_COLOR = QColor(255, 200, 0)

from .linetypes import PATTERNS, apply_pen, world_pixel_scale
LINETYPE_DASH_PATTERNS = {name:[abs(v) for v in values] for name,values in PATTERNS.items() if values}


class Snap:
    ENDPOINT = "Endpoint"
    MIDPOINT = "Midpoint"
    CENTER = "Center"
    INTERSECTION = "Intersection"
    PERPENDICULAR = "Perpendicular"
    QUADRANT = "Quadrant"
    TANGENT = "Tangent"
    NEAREST = "Nearest"
    GRID = "Grid"
    NONE = None


class CadCanvas(QGraphicsView):
    """The drawing surface. Emits signals the main window / tools consume."""

    world_mouse_moved = pyqtSignal(float, float, str)  # x, y, snap_kind
    world_clicked = pyqtSignal(float, float, str, int)  # x, y, snap_kind, qt_button
    key_pressed = pyqtSignal(int)

    def __init__(self, document: Document, parent=None):
        super().__init__(parent)
        self.document = document
        self.scene_ = QGraphicsScene(self)
        self.setScene(self.scene_)
        # We never add QGraphicsItems - all drawing happens in drawBackground/
        # drawForeground using our own world<->screen math. Without an explicit
        # scene rect, an empty QGraphicsScene defaults to a near-zero rect, and
        # Qt clips paint events to that area - so only a small corner of the
        # widget actually renders anything, while clicks (computed from the
        # full viewport size) land somewhere that doesn't match what's drawn.
        # A large fixed scene rect makes Qt treat the whole viewport as paintable.
        self.scene_.setSceneRect(-1_000_000, -1_000_000, 2_000_000, 2_000_000)

        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setMouseTracking(True)
        self.setBackgroundBrush(QBrush(BACKGROUND_COLOR))
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.NoAnchor)

        # view state
        self.zoom = 10.0  # pixels per world unit
        self.pan_offset = QPointF(0, 0)  # world coords shown at viewport center
        self._panning = False
        self._pan_start_mouse = None
        self._pan_start_offset = None

        self.grid_enabled = True
        self.grid_spacing = 10.0
        self.snap_enabled = True
        self.snap_radius_px = 12
        from . import appsettings
        from .appearance import SNAPS
        prefs = appsettings.get_settings()
        modes = prefs.value('drafting/snap_modes', list(SNAPS))
        self.snap_modes = set(modes if isinstance(modes, list) else [modes]) & set(SNAPS)
        try:
            self.snap_radius_px = max(2, min(40, int(prefs.value('drafting/snap_radius', 12))))
            spacing = float(prefs.value('drafting/grid_spacing', 10.0))
            self.grid_spacing = max(.000001, min(1e9, spacing)) if math.isfinite(spacing) else 10.0
        except (ValueError, TypeError, OverflowError):
            self.snap_radius_px, self.grid_spacing = 12, 10.0
        self.snap_enabled = prefs.value('drafting/snap_enabled', True, type=bool)
        self.ortho_enabled = False

        self.selected_entities: List[Entity] = []
        self.selected_viewport = None  # a layout.Viewport, only meaningful while current_space != 'Model'
        self.rubber_band_start: Optional[QPointF] = None
        self.rubber_band_end: Optional[QPointF] = None

        self._snap_point = None
        self.setCursor(Qt.CursorShape.CrossCursor)
        self._active_tool = None  # set by MainWindow

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    # -- tool wiring ---------------------------------------------------
    def set_active_tool(self, tool):
        self._active_tool = tool

    # -- coordinate transforms ------------------------------------------
    def world_to_screen(self, wx: float, wy: float) -> QPointF:
        frame=self.__dict__.get('_frame_transform')
        if frame is not None:
            cx,cy,pan_x,pan_y,zoom=frame
            return QPointF(cx+(wx-pan_x)*zoom,cy-(wy-pan_y)*zoom)
        cx, cy = self.viewport().width() / 2, self.viewport().height() / 2
        sx = cx + (wx - self.pan_offset.x()) * self.zoom
        sy = cy - (wy - self.pan_offset.y()) * self.zoom
        return QPointF(sx, sy)

    def screen_to_world(self, sx: float, sy: float) -> QPointF:
        cx, cy = self.viewport().width() / 2, self.viewport().height() / 2
        wx = (sx - cx) / self.zoom + self.pan_offset.x()
        wy = -(sy - cy) / self.zoom + self.pan_offset.y()
        return QPointF(wx, wy)

    # -- painting ---------------------------------------------------------
    def drawBackground(self, painter: QPainter, rect: QRectF):
        if painter.isActive() and painter.device() is self.viewport():
            self.paint_engine_name = painter.paintEngine().type().name
        # QGraphicsView hands us a painter already transformed into scene
        # coordinates (translated by the exposed rect's origin). We do all
        # our own pixel-space math via world_to_screen/screen_to_world, so
        # we reset to identity first - otherwise everything silently renders
        # offset by that translation (it looked like the canvas only worked
        # in one corner, because that's where our "pixel" coordinates
        # actually landed once Qt's scene transform was applied on top).
        painter.save()
        try:
            painter.resetTransform()
            painter.fillRect(self.viewport().rect(), getattr(self, 'model_background', BACKGROUND_COLOR))
            if self.document.current_space == "Model":
                if self.grid_enabled:
                    self._draw_grid(painter)
            else:
                self._draw_layout_page(painter)
        except Exception:
            logger.exception("Error drawing background/grid")
        finally:
            painter.restore()

    def _draw_layout_page(self, painter: QPainter):
        """The paper sheet itself, drawn as a plain light rectangle at the
        Layout's page size - reusing the same pan/zoom as Model Space, just
        interpreting 'world units' as paper units while a Layout is active."""
        layout = self.document.layouts.get(self.document.current_space)
        if layout is None:
            return
        p1 = self.world_to_screen(0, 0)
        p2 = self.world_to_screen(layout.page_width, layout.page_height)
        page_rect = QRectF(p1, p2).normalized()
        painter.fillRect(page_rect, getattr(self, 'paper_background', QColor(235, 235, 235)))
        pen = QPen(QColor(ui_colors(self)['ui_page_border']))
        pen.setWidth(0)
        painter.setPen(pen)
        painter.drawRect(page_rect)

    def _draw_grid(self, painter: QPainter):
        vw, vh = self.viewport().width(), self.viewport().height()
        top_left = self.screen_to_world(0, 0)
        bottom_right = self.screen_to_world(vw, vh)
        spacing = self.grid_spacing
        # adapt spacing so lines aren't too dense
        while spacing * self.zoom < 8:
            spacing *= 5
        start_x = math.floor(top_left.x() / spacing) * spacing
        end_x = math.ceil(bottom_right.x() / spacing) * spacing
        start_y = math.floor(bottom_right.y() / spacing) * spacing
        end_y = math.ceil(top_left.y() / spacing) * spacing

        pen_minor = QPen(getattr(self, 'grid_color', GRID_MINOR_COLOR))
        pen_minor.setWidth(0)
        painter.setPen(pen_minor)

        x = start_x
        while x <= end_x:
            p1 = self.world_to_screen(x, top_left.y())
            p2 = self.world_to_screen(x, bottom_right.y())
            painter.drawLine(p1, p2)
            x += spacing

        y = start_y
        while y <= end_y:
            p1 = self.world_to_screen(top_left.x(), y)
            p2 = self.world_to_screen(bottom_right.x(), y)
            painter.drawLine(p1, p2)
            y += spacing

        # axes (bold)
        pen_axis = QPen(QColor(ui_colors(self)['ui_axis']))
        pen_axis.setWidth(0)
        painter.setPen(pen_axis)
        o = self.world_to_screen(0, top_left.y())
        o2 = self.world_to_screen(0, bottom_right.y())
        painter.drawLine(o, o2)
        o = self.world_to_screen(top_left.x(), 0)
        o2 = self.world_to_screen(bottom_right.x(), 0)
        painter.drawLine(o, o2)

    def drawForeground(self, painter: QPainter, rect: QRectF):
        painter.save()
        try:
            painter.resetTransform()
            if self.document.current_space == "Model":
                self._draw_cached_entities(painter)
                from .drawing_checks import draw_highlights
                draw_highlights(self, painter)
                if getattr(self, 'comparison_overlay', None):
                    original = self.document
                    try:
                        for entity, color, source in self.comparison_overlay:
                            painter.save()
                            try:
                                self.document = source
                                self._comparison_color = color
                                painter.setOpacity(.8)
                                painter.setPen(QPen(QColor(color), 1.8, Qt.PenStyle.DashLine))
                                self._draw_entity(painter, entity)
                            finally:
                                painter.restore()
                    finally:
                        self.document = original
                        self._comparison_color = None
                navigating=self.__dict__.get("_navigation_preview",False) or self._panning
                from .progressive_display import heavy
                from .persistent_scene import enabled as persistent_enabled
                isolated=persistent_enabled(self) or (self.isVisible() and heavy(self) and self.__dict__.get('async_display_enabled',True))
                if not navigating and not isolated:self._draw_grips(painter)
                from .drafting_aids import draw as draw_drafting_aids
                draw_drafting_aids(self,painter)
                self._draw_snap_marker(painter)
                self._draw_rubber_band(painter)
                if self._active_tool is not None and not navigating:
                    self._active_tool.draw_preview(painter, self)
                from .constraint_ui import draw_constraints
                draw_constraints(painter, self)
                state=self.__dict__.get('progressive_stats',{})
                note='Navigating · detail refines when stopped' if self.__dict__.get('_navigation_preview',False) or self._panning else 'Refining drawing…' if self.__dict__.get('_last_draw_kind')=='progressive frame' and state and not state.get('complete',True) else ''
                if getattr(self,'_render_process_error',''):note='Render worker error: '+self._render_process_error[:140]
                elif self.__dict__.get('_last_draw_kind')=='background preparing frame':note='Preparing drawing display…'
                elif self.__dict__.get('_last_draw_kind')=='background refining frame' and self.__dict__.get('_drawing_image') is None:note='Building initial drawing display…'
                from .persistent_scene import enabled as persistent_enabled
                if persistent_enabled(self):note='Preparing persistent drawing scene…' if self.__dict__.get('_last_draw_kind')=='persistent scene preparing' else ''
                if getattr(self,'_render_process_error',''):note='Render worker error: '+self._render_process_error[:140]
                if note and '_plot_mm' not in self.__dict__:
                    painter.save();painter.setPen(QColor(ui_colors(self)['ui_overlay_text']));painter.drawText(10,self.viewport().height()-12,note);painter.restore()
            else:
                from .progressive_display import heavy
                dragging=getattr(self._active_tool,'vp_drag_kind',None)
                from .persistent_scene import enabled as persistent_enabled
                if dragging is None and (persistent_enabled(self) or (self.isVisible() and heavy(self))):self._draw_cached_entities(painter)
                else:self._draw_layout_viewports(painter)
                vp=self.selected_viewport
                if vp is not None:
                    painter.save();painter.setPen(QPen(QColor(ui_colors(self)['ui_selection']),1));painter.setBrush(Qt.BrushStyle.NoBrush);painter.drawRect(QRectF(self.world_to_screen(vp.x,vp.y),self.world_to_screen(vp.x+vp.width,vp.y+vp.height)).normalized());painter.restore()
            if getattr(self,'boq_overlay_enabled',False) and not ('_plot_mm' in self.__dict__):
                painter.fillRect(8,5,620,43 if getattr(self,'_boq_overlay_error','') else 24,QColor('#252b32'));painter.setPen(QColor('#efb84d'))
                painter.drawText(15,22,'BOQ: green measured/priced · amber unpriced · red unmeasured')
                if getattr(self,'_boq_overlay_error',''):painter.drawText(15,42,'BOQ overlay: '+self._boq_overlay_error[:100])
        except Exception:
            logger.exception("Error drawing foreground/entities")
        finally:
            painter.restore()

    def _draw_grips(self, painter: QPainter):
        """Small squares at the editable points of the single selected
        entity (see SelectTool's grip-drag handling for the interaction)."""
        if len(self.selected_entities) != 1:
            return
        entity = self.selected_entities[0]
        from .polyline_grips import grips as edit_grips
        grips = edit_grips(entity,self.document.render_revision)
        if not grips:
            return
        size = 5
        pen = QPen(QColor(ui_colors(self)['ui_selection']))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.setBrush(QBrush(QColor(ui_colors(self)['ui_grip'])))
        view=self.viewport();bounds=view.rect().adjusted(-6,-6,6,6);cx,cy=view.width()/2,view.height()/2;px,py=self.pan_offset.x(),self.pan_offset.y();z=self.zoom
        for _kind, p in grips:
            sp = QPointF(cx+(p.x-px)*z,cy-(p.y-py)*z)
            if not bounds.contains(sp.toPoint()):continue
            if _kind.startswith("mid"):
                painter.drawEllipse(QRectF(sp.x()-4,sp.y()-4,8,8))
            else:painter.drawRect(QRectF(sp.x()-size,sp.y()-size,size*2,size*2))

    def _draw_layout_viewports(self, painter: QPainter):
        """Each Viewport shows Model Space content nested inside a rectangle
        on the paper - a Model-space point first maps into the viewport's
        local paper position (Viewport.model_to_paper), then that paper
        position maps to screen pixels the normal way. We swap
        world_to_screen for the duration of each viewport's content so
        _draw_entity doesn't need to know anything about the nesting."""
        layout = self.document.layouts.get(self.document.current_space)
        if layout is None:
            return
        original_world_to_screen = self.world_to_screen
        original_zoom = self.zoom
        for viewport_index,vp in enumerate(layout.viewports):
            from .layers_plus import overrides
            self._viewport_override=overrides(self.document,layout.name,viewport_index)
            p1 = original_world_to_screen(vp.x, vp.y)
            p2 = original_world_to_screen(vp.x + vp.width, vp.y + vp.height)
            rect = QRectF(p1, p2).normalized()
            painter.save()
            painter.setClipRect(rect)
            from .viewport_plus import config,paper_point,clip_path
            vp_config=config(self.document,layout.name,viewport_index)
            if vp_config["clip"]:painter.setClipPath(clip_path(vp_config["clip"],original_world_to_screen),Qt.ClipOperation.IntersectClip)
            self._annotation_scale=vp_config["annotation_scale"];self._viewport_rotation=vp_config["rotation"]
            def nested_world_to_screen(wx, wy, _vp=vp):
                paper = paper_point(_vp,wx,wy,vp_config["rotation"])
                return original_world_to_screen(paper.x, paper.y)
            self.world_to_screen = nested_world_to_screen
            self.zoom = original_zoom * vp.scale
            try:
                self._draw_entities(painter, paper=True)
            finally:
                self.world_to_screen = original_world_to_screen
                self.zoom = original_zoom
                self._annotation_scale=1.0;self._viewport_rotation=0
                painter.restore()
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(ui_colors(self)['ui_selection']) if vp is self.selected_viewport else QColor(ui_colors(self)['ui_page_border']), 1))
            painter.drawRect(rect)
        self._viewport_override={}
        from .sheets import draw_title
        draw_title(self,painter,layout.name)
        from .underlays import draw_underlays
        draw_underlays(self,painter,review_space=layout.name)

    def _draw_snap_marker(self, painter):
        if self._snap_point is None or not self.snap_enabled:
            return
        point = self.world_to_screen(self._snap_point.x, self._snap_point.y)
        painter.setPen(QPen(QColor(ui_colors(self)['ui_snap']), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(QRectF(point.x()-5, point.y()-5, 10, 10))

    from .drawing_diagnostics import timed_paint as _timed_paint
    @_timed_paint
    def _draw_cached_entities(self, painter):
        self._last_draw_kind='cached frame'
        from .progressive_display import heavy
        from .persistent_scene import enabled as persistent_enabled
        large=False if persistent_enabled(self) else heavy(self)
        if getattr(self,'drawing_path','cached')=='direct' and not large and not persistent_enabled(self):
            self._last_draw_kind='direct redraw'
            self._draw_entities(painter)
            return
        from PyQt6.QtGui import QImage
        size = self.viewport().size()
        key = (id(self.document), self.document.render_revision, len(self.document.entities),
               self.zoom, self.pan_offset.x(), self.pan_offset.y(), size.width(), size.height(),
               repr(self.document.layers.layers)+repr(self.document.current_space), repr(ui_colors(self)),self.__dict__.get("progressive_lod",True),getattr(self,"boq_overlay_enabled",False))
        from .persistent_scene import enabled as persistent_enabled,paint as persistent_paint
        if persistent_enabled(self):
            persistent_paint(self,painter,key);return
        from .async_display import try_cached
        if large and try_cached(self,painter,key):return
        old=self.__dict__.get('_drawing_image_key')
        preview=self.__dict__.get('_drawing_image')
        if old is None:
            old=self.__dict__.get('_progressive_key');preview=self.__dict__.get('_progressive_image')
        navigating=self.__dict__.get('_panning',False) or self.__dict__.get('_navigation_preview',False)
        if navigating and (old is None or old[:3]+old[6:]!=key[:3]+key[6:]):
            partial=self.__dict__.get('_progressive_key')
            if partial is not None and partial[:3]+partial[6:]==key[:3]+key[6:]:old=partial;preview=self._progressive_image
        if navigating and old is not None and old[:3]+old[6:]==key[:3]+key[6:] and old[3]>0:
            factor=self.zoom/old[3];dx=size.width()/2*(1-factor)+(old[4]-self.pan_offset.x())*self.zoom;dy=size.height()/2*(1-factor)+(self.pan_offset.y()-old[5])*self.zoom
            if math.isfinite(factor) and factor>0:
                painter.save()
                try:
                    self._last_draw_kind='navigation preview'
                    painter.translate(dx,dy);painter.scale(factor,factor);painter.drawImage(0,0,preview)
                    controller=self.__dict__.get('_async_controller')
                    selection_key=None if getattr(controller,'isolated_process',False) else (old,tuple(map(id,self.selected_entities)))
                    selected_cached=selection_key is not None and self.__dict__.get('_selection_image_key')==selection_key
                    if self.selected_entities and selected_cached:painter.drawImage(0,0,self._selection_image)
                finally:painter.restore()
                if self.selected_entities and not selected_cached:
                    from .progressive_display import heavy,selection
                    controller=self.__dict__.get('_async_controller')
                    if getattr(controller,'isolated_process',False):controller.paint_selection(self,painter,key)
                    elif heavy(self):selection(self,painter,key)
                    else:self._draw_entities(painter,entities=self.selected_entities)
                return
        if large:
            from .retained_scene import paint as retained_paint
            if retained_paint(self,painter,key):return
        from .progressive_display import heavy
        if getattr(self,'drawing_path','cached')=='progressive' or large:
            self._last_draw_kind='progressive frame'
            from .progressive_display import paint
            paint(self,painter,key)
            return
        if getattr(self, '_drawing_image_key', None) != key:
            self._last_draw_kind='full redraw'
            image = QImage(size, QImage.Format.Format_ARGB32_Premultiplied)
            image.fill(Qt.GlobalColor.transparent)
            cache_painter = QPainter(image)
            cache_painter.setRenderHints(painter.renderHints())
            selection = self.selected_entities
            try:
                self.selected_entities = []
                self._draw_entities(cache_painter)
            finally:
                self.selected_entities = selection
                cache_painter.end()
            self._drawing_image = image
            self._drawing_image_key = key
        painter.drawImage(0, 0, self._drawing_image)
        if self.selected_entities:
            selection_key = (key,tuple(map(id,self.selected_entities)))
            if getattr(self,'_selection_image_key',None)!=selection_key:
                overlay=QImage(size,QImage.Format.Format_ARGB32_Premultiplied)
                overlay.fill(Qt.GlobalColor.transparent)
                overlay_painter=QPainter(overlay)
                overlay_painter.setRenderHints(painter.renderHints())
                try:
                    self._draw_entities(overlay_painter,entities=self.selected_entities)
                finally:
                    overlay_painter.end()
                self._selection_image=overlay
                self._selection_image_key=selection_key
            painter.drawImage(0,0,self._selection_image)

    def _draw_entities(self, painter: QPainter, paper=False, entities=None):
        # QWidget's missing-attribute lookup crosses into Qt; cache frame data
        # in the Python dictionary instead of repeating it for every primitive.
        cache=self.__dict__;sentinel=object();keys=('_frame_transform','_frame_pixel_scale','_frame_world_box');previous={key:cache.get(key,sentinel) for key in keys}
        try:
            default=getattr(self.world_to_screen,'__func__',None) is CadCanvas.world_to_screen
            if default:
                view=self.viewport();cache['_frame_transform']=(view.width()/2,view.height()/2,self.pan_offset.x(),self.pan_offset.y(),self.zoom)
            a=self.world_to_screen(0,0);b=self.world_to_screen(1,0);cache['_frame_pixel_scale']=math.hypot(b.x()-a.x(),b.y()-a.y())
            cache['_frame_world_box']=None
            if default and not paper and '_plot_mm' not in cache:
                a=self.screen_to_world(-32,-32);b=self.screen_to_world(self.viewport().width()+32,self.viewport().height()+32)
                cache['_frame_world_box']=(min(a.x(),b.x()),min(a.y(),b.y()),max(a.x(),b.x()),max(a.y(),b.y()))
            return self._paint_entities(painter,paper,entities)
        finally:
            for key,value in previous.items():
                if value is sentinel:cache.pop(key,None)
                else:cache[key]=value

    def _paint_entities(self, painter: QPainter, paper=False, entities=None):
        from .underlays import draw_underlays
        if entities is None:
            draw_underlays(self, painter)
        # Clip ordinary drafting paints using the existing spatial index.
        # Paper/plot transforms use their own coordinate mapping and retain
        # the complete candidate stream. Rays/Xlines are included by query_entities.
        if entities is not None:
            entities = [e for e in entities if self.document.is_visible(e)]
        elif (not paper and not ('_plot_mm' in self.__dict__) and
                getattr(self.world_to_screen, '__func__', None) is CadCanvas.world_to_screen and
                getattr(self.screen_to_world, '__func__', None) is CadCanvas.screen_to_world):
            a = self.screen_to_world(-32, -32)
            b = self.screen_to_world(self.viewport().width()+32, self.viewport().height()+32)
            entities = self.document.query_entities((min(a.x(),b.x()), min(a.y(),b.y()),
                                                    max(a.x(),b.x()), max(a.y(),b.y())))
        else:
            entities = self.document.visible_entities()
        selected = set(map(id, self.selected_entities))
        overlay_colors={}
        if getattr(self,'boq_overlay_enabled',False) and not ('_plot_mm' in self.__dict__):
            if getattr(self,'_boq_overlay_revision',None)!=(id(self.document),self.document.render_revision):
                try:
                    from .productivity import overlay
                    self._boq_overlay=overlay(self.document);self._boq_overlay_error=''
                except ValueError as error:self._boq_overlay={};self._boq_overlay_error=str(error)
                self._boq_overlay_revision=(id(self.document),self.document.render_revision)
            overlay_colors=getattr(self,'_boq_overlay',{}).get('colors',{})
        handled=set()
        if not overlay_colors and not paper and getattr(self.world_to_screen,"__func__",None) is CadCanvas.world_to_screen:
            from .gpu_geometry import draw as draw_gpu
            handled=draw_gpu(self,painter,entities)
        from .fast_lines import Lines
        fast=Lines(self,painter,selected) if not overlay_colors and not paper and '_plot_mm' not in self.__dict__ and not self.__dict__.get('_viewport_override') and not self.__dict__.get('_monochrome') else None
        for e in entities:
            if id(e) in handled:continue
            if fast is not None:
                if fast.offer(e):continue
                fast.flush()
            if ('_plot_mm' in self.__dict__) and not self.document.layers.layers.get(e.layer, {}).get("plot", True):
                continue
            painter.save()
            try:
                override=self.__dict__.get("_viewport_override",{}).get(e.layer,{})
                if not override.get("visible",True): continue
                color = QColor(overlay_colors.get(e.id,override.get("color",self.document.entity_color(e))))
                if paper and color.lightness() > 220:
                    color = QColor("#202830")
                if self.__dict__.get("_monochrome",False):
                    color = QColor("#17202A")
                pen = QPen(color)
                painter.setOpacity(1.0-e.transparency/100.0)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                style=self.document.extensions.get('workflow',{}).get('pen_styles',{}).get(e.layer,{}) if ('_plot_mm' in self.__dict__) else {}
                if style and not style['plot']:continue
                if style and not self.__dict__.get('_monochrome',False):pen.setColor(QColor(override.get('color',style['color'])))
                weight = style.get('width',self.document.layers.layers.get(e.layer, {}).get('lineweight',.25))
                pen.setWidthF(weight*self._plot_mm if ('_plot_mm' in self.__dict__) else max(1, weight*3.78))
                if id(e) in selected:pen.setWidthF(max(2,pen.widthF()))
                if id(e) in selected:
                    pen.setColor(QColor(ui_colors(self)['ui_selection']))
                apply_pen(pen,self.document.entity_linetype(e),world_pixel_scale(self),self.document.linetype_scale,
                          dense_preview=not ('_plot_mm' in self.__dict__ or self.__dict__.get('_persistent_recording',False)))
                painter.setPen(pen)
                box=e.bbox() if self.__dict__.get('_lod_paint',False) and self.__dict__.get('progressive_lod',True) else None
                if box and max(box[2]-box[0],box[3]-box[1])*abs(self.zoom)<.75:
                    painter.drawPoint(self.world_to_screen((box[0]+box[2])/2,(box[1]+box[3])/2))
                else:
                    previous=self.__dict__.get('_comparison_color',None)
                    try:
                        if e.id in overlay_colors:self._comparison_color=overlay_colors[e.id]
                        self._draw_entity(painter,e)
                    finally:self._comparison_color=previous
            except Exception:
                # one malformed entity (e.g. a degenerate arc from a bad
                # fillet edge case) shouldn't blank the rest of the drawing
                logger.exception("Error drawing entity %s (id=%s)", e.kind, getattr(e, "id", "?"))
            finally:
                painter.restore()

        if fast is not None:fast.flush()

    def _draw_entity(self, painter: QPainter, e: Entity):
        if self.document.extensions.get("office_linetypes"):
            from .office_ink import draw_custom
            if draw_custom(self,painter,e):return
        if e.kind=="TEXT" and self.__dict__.get("_annotation_scale",1.0)!=1:
            import copy
            e=copy.copy(e);e.height*=self._annotation_scale
        if isinstance(e, LineEntity):
            p1 = self.world_to_screen(e.p1.x, e.p1.y)
            p2 = self.world_to_screen(e.p2.x, e.p2.y)
            painter.drawLine(p1, p2)
        elif isinstance(e, PointEntity):
            point = self.world_to_screen(e.point.x, e.point.y)
            size = max(3.0, min(8.0, self.zoom * 0.35))
            painter.drawLine(QPointF(point.x() - size, point.y()), QPointF(point.x() + size, point.y()))
            painter.drawLine(QPointF(point.x(), point.y() - size), QPointF(point.x(), point.y() + size))
        elif isinstance(e, CircleEntity):
            c = self.world_to_screen(e.center.x, e.center.y)
            r = e.radius * self.zoom
            painter.drawEllipse(c, r, r)
        elif isinstance(e, ArcEntity):
            path = QPainterPath()
            c = self.world_to_screen(e.center.x, e.center.y)
            r = e.radius * self.zoom
            rect = QRectF(c.x() - r, c.y() - r, 2 * r, 2 * r)
            # Qt angles: degrees, CCW, 0 = 3 o'clock, but Qt's y-down flips CCW/CW visually.
            start = e.start_angle+self.__dict__.get("_viewport_rotation",0)
            span = (e.end_angle - e.start_angle) % 360.0
            path.arcMoveTo(rect, start)
            path.arcTo(rect, start, span)
            painter.drawPath(path)
        elif isinstance(e, EllipseEntity):
            points = [self.world_to_screen(p.x, p.y) for p in e.sample_points()]
            path = QPainterPath()
            if points:
                path.moveTo(points[0])
                for point in points[1:]:
                    path.lineTo(point)
                path.closeSubpath()
            painter.drawPath(path)
        elif isinstance(e, XLineEntity):
            self._draw_construction_line(painter, e, positive_only=False)
        elif isinstance(e, RayEntity):
            self._draw_construction_line(painter, e, positive_only=True)
        elif isinstance(e, PolylineEntity):
            pts = [self.world_to_screen(p.x, p.y) for p in e.sample_points()]
            path = QPainterPath()
            if pts:
                path.moveTo(pts[0])
                for p in pts[1:]:
                    path.lineTo(p)
                if e.closed:
                    path.closeSubpath()
            painter.save()
            if e.width>0:
                pen=QPen(painter.pen());pen.setWidthF(max(.01,e.width*self.zoom));pen.setCapStyle(Qt.PenCapStyle.FlatCap);pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin);painter.setPen(pen)
            painter.drawPath(path);painter.restore()
        elif isinstance(e, SplineEntity):
            samples = e._catmull_rom_samples()
            pts = [self.world_to_screen(p.x, p.y) for p in samples]
            path = QPainterPath()
            if pts:
                path.moveTo(pts[0])
                for p in pts[1:]:
                    path.lineTo(p)
            painter.drawPath(path)
        elif isinstance(e, BlockReferenceEntity):
            def clip(reference):
                if reference.clip_boundary:
                    path=QPainterPath();path.moveTo(self.world_to_screen(reference.clip_boundary[0].x,reference.clip_boundary[0].y))
                    for p in reference.clip_boundary[1:]:path.lineTo(self.world_to_screen(p.x,p.y))
                    path.closeSubpath();painter.setClipPath(path,Qt.ClipOperation.IntersectClip)
            painter.save()
            clip(e)
            from .block_display import visible_children
            box=self.__dict__.get('_frame_world_box');revision=self.document.render_revision
            pending=[('draw',child) for child in reversed(visible_children(e,box,revision))]
            while pending:
                action,sub=pending.pop()
                if action=='restore':painter.restore();continue
                if not self.document.layers.is_visible(sub.layer):continue
                if ('_plot_mm' in self.__dict__) and not self.document.layers.layers.get(sub.layer,{}).get('plot',True):continue
                painter.save()
                painter.setOpacity(painter.opacity()*(1.0-sub.transparency/100.0))
                if sub.linetype!='BYBLOCK' and not (sub.linetype=='BYLAYER' and sub.layer=='0'):
                    pen=QPen(painter.pen())
                    apply_pen(pen,self.document.entity_linetype(sub),world_pixel_scale(self),self.document.linetype_scale,dense_preview=not ('_plot_mm' in self.__dict__ or self.__dict__.get('_persistent_recording',False)))
                    painter.setPen(pen)
                pending.append(('restore',None))
                if isinstance(sub,BlockReferenceEntity):
                    clip(sub)
                    pending.extend(('draw',child) for child in reversed(visible_children(sub,box,revision)))
                else:self._draw_entity(painter,sub)
            painter.restore()
        elif isinstance(e, TextEntity):
            pos = self.world_to_screen(e.position.x, e.position.y)
            font = painter.font()
            from .textstyles import style_for
            style = style_for(self.document, e)
            font.setFamily(style['font_family'])
            font.setBold(style['bold']); font.setItalic(style['italic'])
            font.setPixelSize(max(1, min(10000, round(e.height * self.zoom))))
            painter.setFont(font)
            painter.save()
            painter.translate(pos)
            painter.rotate(-e.rotation-self.__dict__.get("_viewport_rotation",0))
            painter.shear(-math.tan(math.radians(style['oblique'])), 0)
            painter.scale(style['width_factor'], 1)
            if e.wrap_width or e.rich_html:
                from .annotations_plus import draw_text
                draw_text(painter, e, font, self.zoom, self.__dict__.get("_monochrome",False))
            else:
                for line_index, line in enumerate(e.text.split("\n")):
                    painter.drawText(QPointF(0, line_index * e.height * self.zoom * 1.4), line)
            painter.restore()
        elif isinstance(e, DimensionEntity):
            self._draw_dimension(painter, e)
        elif e.kind == 'MLEADER':
            self._draw_mleader(painter,e)
        elif isinstance(e, HatchEntity):
            self._draw_hatch(painter, e)

    def _draw_construction_line(self, painter, entity, positive_only):
        dx, dy = entity.p2.x - entity.p1.x, entity.p2.y - entity.p1.y
        length = math.hypot(dx, dy)
        if length < 1e-12:
            return
        dx, dy = dx / length, dy / length
        top_left = self.screen_to_world(0, 0)
        bottom_right = self.screen_to_world(self.viewport().width(), self.viewport().height())
        extent = math.hypot(bottom_right.x() - top_left.x(), bottom_right.y() - top_left.y()) * 2
        # Center the visible segment near the camera, even when its defining
        # points lie far outside this view. Rays retain their forward half only.
        cx = (top_left.x() + bottom_right.x()) / 2
        cy = (top_left.y() + bottom_right.y()) / 2
        center = (cx - entity.p1.x) * dx + (cy - entity.p1.y) * dy
        start = max(0.0, center - extent) if positive_only else center - extent
        end = center + extent
        if positive_only and end <= 0:
            return
        p1 = Point(entity.p1.x + dx * start, entity.p1.y + dy * start)
        p2 = Point(entity.p1.x + dx * end, entity.p1.y + dy * end)
        painter.drawLine(self.world_to_screen(p1.x, p1.y), self.world_to_screen(p2.x, p2.y))

    def _draw_dimension(self, painter: QPainter, e):
        from .dimstyles import style_for, dimension_geometry, dimension_label
        style = dict(style_for(self.document, e))
        style["scale"]*=self.__dict__.get("_annotation_scale",1.0)
        lines, fills, anchor, height = dimension_geometry(e, style)
        painter.save()
        try:
            if style['color'] != 'BYLAYER' and not self.__dict__.get('_monochrome',False) and not self.__dict__.get('_comparison_color',None):
                pen = painter.pen(); pen.setColor(QColor(style['color'])); painter.setPen(pen)
            font = painter.font()
            font.setPixelSize(max(1, min(10000, round(height*self.zoom))))
            painter.setFont(font)
            for a,b in lines:
                painter.drawLine(self.world_to_screen(a.x,a.y), self.world_to_screen(b.x,b.y))
            for triangle in fills:
                path = QPainterPath()
                path.moveTo(self.world_to_screen(triangle[0].x,triangle[0].y))
                for point in triangle[1:]: path.lineTo(self.world_to_screen(point.x,point.y))
                path.closeSubpath()
                painter.fillPath(path, painter.pen().color())
            text = dimension_label(e,style)
            position = self.world_to_screen(anchor.x,anchor.y)
            if e.dim_style not in ('radius','diameter'):
                position.setX(position.x()-painter.fontMetrics().horizontalAdvance(text)/2)
            painter.drawText(position,text)
        finally:
            painter.restore()

    def _draw_mleader(self, painter, entity):
        from .mleaders import style_for
        style = dict(style_for(self.document,entity))
        for key in ("text_height","arrow_size","landing_length","text_gap"):
            if key in style:style[key]*=self.__dict__.get("_annotation_scale",1.0)
        lines,fills,labels = entity.geometry(style)
        painter.save()
        try:
            if style['color'] != 'BYLAYER' and not self.__dict__.get('_monochrome',False) and entity not in self.selected_entities and not self.__dict__.get('_comparison_color',None):
                pen = painter.pen();pen.setColor(QColor(style['color']));painter.setPen(pen)
            for a,b in lines:
                painter.drawLine(self.world_to_screen(a.x,a.y),self.world_to_screen(b.x,b.y))
            for triangle in fills:
                path = QPainterPath()
                path.moveTo(self.world_to_screen(triangle[0].x,triangle[0].y))
                for point in triangle[1:]:path.lineTo(self.world_to_screen(point.x,point.y))
                path.closeSubpath();painter.fillPath(path,painter.pen().color())
            for text,position,height,rotation in labels:
                painter.save()
                font=painter.font();font.setPixelSize(max(1,min(10000,round(height*self.zoom))))
                painter.setFont(font)
                painter.translate(self.world_to_screen(position.x,position.y))
                painter.rotate(-rotation)
                painter.drawText(QPointF(0,0),text)
                painter.restore()
        finally:
            painter.restore()

    def _draw_radial_dimension(self, painter: QPainter, e):
        """Radius/diameter: a single leader from the circle's edge (e.p2)
        out to the label position (e.dim_point) - one arrowhead pointing
        into the circle, no extension lines (there's nothing to extend from)."""
        s_p2 = self.world_to_screen(e.p2.x, e.p2.y)
        s_label = self.world_to_screen(e.dim_point.x, e.dim_point.y)
        painter.drawLine(s_p2, s_label)
        self._draw_arrowhead(painter, s_p2, s_label)
        painter.drawText(QPointF(s_label.x() + 4, s_label.y() - 4), e.label_text())

    def _draw_arrowhead(self, painter: QPainter, tip: QPointF, tail: QPointF, size: float = 8):
        size = getattr(self, "_plot_arrow_size", size)
        dx, dy = tip.x() - tail.x(), tip.y() - tail.y()
        length_ = math.hypot(dx, dy)
        if length_ < 1e-6:
            return
        ux, uy = dx / length_, dy / length_
        px, py = -uy, ux
        base1 = QPointF(tip.x() - ux * size + px * size * 0.35, tip.y() - uy * size + py * size * 0.35)
        base2 = QPointF(tip.x() - ux * size - px * size * 0.35, tip.y() - uy * size - py * size * 0.35)
        path = QPainterPath()
        path.moveTo(tip)
        path.lineTo(base1)
        path.lineTo(base2)
        path.closeSubpath()
        painter.fillPath(path, QBrush(painter.pen().color()))

    def _draw_hatch(self, painter: QPainter, e):
        from .precision import draw_hatch
        return draw_hatch(self,painter,e)

    def _legacy_draw_hatch(self,painter,e):
        pts = [self.world_to_screen(p.x, p.y) for p in e.boundary]
        if e.pattern == "SOLID":
            path = QPainterPath()
            if pts:
                path.moveTo(pts[0])
                for p in pts[1:]:
                    path.lineTo(p)
                path.closeSubpath()
            painter.fillPath(path, QBrush(painter.pen().color()))
        else:
            from . import geom_ops
            for a, b in geom_ops.compute_hatch_lines(e.boundary, e.angle, e.spacing):
                painter.drawLine(self.world_to_screen(a.x, a.y), self.world_to_screen(b.x, b.y))

    def _draw_rubber_band(self, painter: QPainter):
        if self.rubber_band_start and self.rubber_band_end:
            pen = QPen(QColor(ui_colors(self)['ui_selection']))
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            rect = QRectF(self.rubber_band_start, self.rubber_band_end)
            painter.drawRect(rect.normalized())

    # -- snapping -----------------------------------------------------------
    def _event_snap_point(self, pos):
        if (getattr(self._active_tool,"name",None)=="SELECT" and
                not (getattr(self._active_tool,"dragging_entity",False) or
                     getattr(self._active_tool,"grip_entity",None) is not None)):
            return None,None
        return self.find_snap_point(pos)

    def find_snap_point(self, screen_pos: QPointF) -> Tuple[Optional[Point], Optional[str]]:
        if not self.snap_enabled or self.document.current_space != "Model":
            return None, None
        # Lower numbers win ties.  Endpoint and intersection snaps are more
        # useful than a nearby nearest point, which makes dense drawings feel
        # predictable while retaining the same small pixel tolerance.
        priority = {
            Snap.ENDPOINT: 0, Snap.INTERSECTION: 1, Snap.MIDPOINT: 2,
            Snap.CENTER: 3, Snap.QUADRANT: 4, Snap.PERPENDICULAR: 5,
            Snap.TANGENT: 6, Snap.NEAREST: 7,
        }
        best = None

        def consider(point, kind):
            nonlocal best
            if kind not in self.snap_modes:
                return
            if point is None or not all(math.isfinite(v) for v in (point.x, point.y)):
                return
            sp = self.world_to_screen(point.x, point.y)
            distance = math.hypot(sp.x() - screen_pos.x(), sp.y() - screen_pos.y())
            if distance > self.snap_radius_px:
                return
            key = (priority.get(kind, 99), distance)
            if best is None or key < best[0]:
                best = (key, point, kind)

        cursor_qt = self.screen_to_world(screen_pos.x(), screen_pos.y())
        cursor = Point(cursor_qt.x(), cursor_qt.y())
        world_tolerance = self.snap_radius_px / max(self.zoom, 1e-12)
        near_bbox = (cursor.x - world_tolerance, cursor.y - world_tolerance,
                     cursor.x + world_tolerance, cursor.y + world_tolerance)
        near_entities = self.document.query_entities(near_bbox, visible_only=True)
        if getattr(self._active_tool,"name",None)=="SELECT":
            moving = {id(e) for e in self.selected_entities}
            near_entities = [e for e in near_entities if id(e) not in moving]
        from .precision_edit import snap_candidates
        near_entities=snap_candidates(near_entities,near_bbox,self.document)
        for entity in near_entities:
            record = self.document.extensions.get('architecture', {}).get(entity.id, {})
            if record.get('kind') == 'wall':
                from .wall_joining import world_point
                consider(Point(*world_point(entity, record['length'], 0)), Snap.ENDPOINT)
                consider(Point(*world_point(entity, record['length'] / 2, 0)), Snap.MIDPOINT)
            for point in entity.endpoints():
                consider(point, Snap.ENDPOINT)
            for point in entity.midpoints():
                consider(point, Snap.MIDPOINT)
            for point in entity.center_points():
                consider(point, Snap.CENTER)
            for point in self._quadrant_points(entity):
                consider(point, Snap.QUADRANT)

        # Exact line/circle intersections cover the common CAD cases.  Curves
        # and polylines fall back to their tessellated edge segments below.
        if Snap.INTERSECTION in self.snap_modes:
            def distance_to_box(entity):
                x0, y0, x1, y1 = entity.bbox()
                return max(x0-cursor.x, 0, cursor.x-x1)**2 + max(y0-cursor.y, 0, cursor.y-y1)**2
            intersection_entities = sorted(near_entities, key=distance_to_box)[:64]
            for point in self._intersection_points(intersection_entities):
                consider(point, Snap.INTERSECTION)

        for entity in near_entities:
            nearest = self._nearest_point(entity, cursor)
            consider(nearest, Snap.NEAREST)
            perpendicular = self._perpendicular_point(entity, cursor)
            if perpendicular is not None:
                consider(perpendicular, Snap.PERPENDICULAR)

            # A tangent point is meaningful when a tool already supplied a
            # construction point outside a circle.  The two tangent points
            # are ranked by cursor distance so the visible marker follows the
            # cursor naturally.
            if isinstance(entity, CircleEntity):
                reference = self._snap_reference_point()
                if reference is not None:
                    for point in self._tangent_points(entity, reference):
                        consider(point, Snap.TANGENT)

        if best:
            return best[1], best[2]
        if Snap.GRID in self.snap_modes:
            grid_point = Point(round(cursor.x/self.grid_spacing)*self.grid_spacing, round(cursor.y/self.grid_spacing)*self.grid_spacing)
            consider(grid_point, Snap.GRID)
        return (best[1], best[2]) if best else (None, None)

    def _snap_reference_point(self):
        tool = self._active_tool
        if tool is None:
            return None
        points = getattr(tool, "points", None)
        if points:
            return points[-1]
        return getattr(tool, "base_point", None)

    @staticmethod
    def _quadrant_points(entity):
        if not isinstance(entity, (CircleEntity, ArcEntity)):
            return []
        points = []
        for angle in (0.0, 90.0, 180.0, 270.0):
            if isinstance(entity, ArcEntity):
                from .geom_ops import angle_in_arc_range
                if not angle_in_arc_range(angle, entity.start_angle, entity.end_angle):
                    continue
            radians = math.radians(angle)
            points.append(Point(entity.center.x + entity.radius * math.cos(radians),
                                entity.center.y + entity.radius * math.sin(radians)))
        return points

    @staticmethod
    def _entity_segments(entity):
        from . import geom_ops
        if isinstance(entity, LineEntity):
            return [(entity.p1, entity.p2)]
        if isinstance(entity, PolylineEntity):
            points = list(entity.points) + ([entity.points[0]] if entity.closed else [])
            return list(zip(points, points[1:]))
        return geom_ops.entity_to_segments(entity)

    @staticmethod
    def _point_on_arc(point, entity):
        if not isinstance(entity, ArcEntity):
            return True
        from .geom_ops import angle_in_arc_range, angle_of
        return angle_in_arc_range(angle_of(entity.center, point), entity.start_angle, entity.end_angle)

    def _intersection_points(self, entities):
        from . import geom_ops
        from .precision import polyline_parts
        entities=[part for e in entities for part in (polyline_parts(e) if isinstance(e,PolylineEntity) and any(e.bulges) else [e])]
        points = []
        for index, first in enumerate(entities):
            for second in entities[index+1:]:
                if isinstance(first,(CircleEntity,ArcEntity)) and isinstance(second,(CircleEntity,ArcEntity)):
                    points.extend(p for p in geom_ops.circle_circle_intersections(first.center,first.radius,second.center,second.radius) if self._point_on_arc(p,first) and self._point_on_arc(p,second));continue
                if isinstance(first,(CircleEntity,ArcEntity)) and isinstance(second,LineEntity):
                    points.extend(p for p in geom_ops.circle_line_intersections(first.center,first.radius,second.p1,second.p2) if self._point_on_arc(p,first) and -1e-9<=geom_ops.point_on_segment_param(second.p1,second.p2,p)<=1+1e-9);continue
                if isinstance(second,(CircleEntity,ArcEntity)) and isinstance(first,LineEntity):
                    points.extend(p for p in geom_ops.circle_line_intersections(second.center,second.radius,first.p1,first.p2) if self._point_on_arc(p,second) and -1e-9<=geom_ops.point_on_segment_param(first.p1,first.p2,p)<=1+1e-9);continue
                # Exact primitives avoid visible faceting for circle-circle
                # intersections; tessellated fallbacks handle polylines and
                # splines without introducing another geometry dependency.
                if isinstance(first, CircleEntity) and isinstance(second, CircleEntity):
                    points.extend(geom_ops.circle_circle_intersections(first.center, first.radius, second.center, second.radius))
                    continue
                if isinstance(first, CircleEntity) and isinstance(second, LineEntity):
                    points.extend(p for p in geom_ops.circle_line_intersections(first.center, first.radius, second.p1, second.p2)
                                  if -1e-9 <= geom_ops.point_on_segment_param(second.p1, second.p2, p) <= 1 + 1e-9)
                    continue
                if isinstance(second, CircleEntity) and isinstance(first, LineEntity):
                    points.extend(p for p in geom_ops.circle_line_intersections(second.center, second.radius, first.p1, first.p2)
                                  if -1e-9 <= geom_ops.point_on_segment_param(first.p1, first.p2, p) <= 1 + 1e-9)
                    continue
                for a, b in self._entity_segments(first):
                    for c, d in self._entity_segments(second):
                        point = geom_ops.line_line_intersection(a, b, c, d, segment_only=True)
                        if point is not None:
                            if self._point_on_arc(point, first) and self._point_on_arc(point, second):
                                points.append(point)
        return points

    def _nearest_point(self,entity,cursor):
        from . import geom_ops
        if isinstance(entity,PolylineEntity) and any(entity.bulges):
            from .precision import polyline_parts
            candidates=[self._nearest_point(part,cursor) for part in polyline_parts(entity)]
            return min((p for p in candidates if p is not None),key=lambda p:p.distance_to(cursor),default=None)
        if isinstance(entity, (CircleEntity, ArcEntity)):
            dx, dy = cursor.x - entity.center.x, cursor.y - entity.center.y
            distance = math.hypot(dx, dy)
            if distance > 1e-12:
                point = Point(entity.center.x + entity.radius * dx / distance,
                              entity.center.y + entity.radius * dy / distance)
                if self._point_on_arc(point, entity):
                    return point
            return min(entity.endpoints(), key=lambda p: p.distance_to(cursor), default=None)
        segments = self._entity_segments(entity)
        candidates = [geom_ops.point_line_projection(cursor, a, b) for a, b in segments]
        candidates = [p for p, (a, b) in zip(candidates, segments)
                      if min(a.x, b.x) - 1e-9 <= p.x <= max(a.x, b.x) + 1e-9 and
                         min(a.y, b.y) - 1e-9 <= p.y <= max(a.y, b.y) + 1e-9]
        return min(candidates, key=lambda p: p.distance_to(cursor), default=None)

    def _perpendicular_point(self, entity, cursor):
        from . import geom_ops
        reference = self._snap_reference_point()
        if reference is None:
            return None
        best = None
        for a, b in self._entity_segments(entity):
            candidate = geom_ops.point_line_projection(reference, a, b)
            if min(a.x, b.x) - 1e-9 <= candidate.x <= max(a.x, b.x) + 1e-9 and \
                    min(a.y, b.y) - 1e-9 <= candidate.y <= max(a.y, b.y) + 1e-9:
                if best is None or candidate.distance_to(cursor) < best.distance_to(cursor):
                    best = candidate
        return best

    @staticmethod
    def _tangent_points(circle, reference):
        dx, dy = reference.x - circle.center.x, reference.y - circle.center.y
        distance_sq = dx * dx + dy * dy
        radius_sq = circle.radius * circle.radius
        if distance_sq <= radius_sq + 1e-12:
            return []
        distance = math.sqrt(distance_sq)
        base = math.atan2(dy, dx)
        offset = math.acos(circle.radius / distance)
        return [Point(circle.center.x + circle.radius * math.cos(base + sign * offset),
                      circle.center.y + circle.radius * math.sin(base + sign * offset))
                for sign in (-1, 1)]

    # -- mouse / keyboard events ---------------------------------------------
    def _apply_ortho(self, wx: float, wy: float) -> Tuple[float, float]:
        """If Ortho mode is on and the active tool has a 'last point' to
        measure from (either a `points` list or a `base_point`), snap the
        given world position to whichever of horizontal/vertical is closer
        to the actual cursor direction from that reference point."""
        if not self.ortho_enabled or self._active_tool is None:
            return wx, wy
        ref = None
        points = getattr(self._active_tool, "points", None)
        if points:
            ref = points[-1]
        elif getattr(self._active_tool, "base_point", None) is not None:
            ref = self._active_tool.base_point
        if ref is None:
            return wx, wy
        dx, dy = wx - ref.x, wy - ref.y
        if abs(dx) >= abs(dy):
            return wx, ref.y
        return ref.x, wy

    @safe_event
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and getattr(self, "navigation_zoom", False):
            self._zoom_drag = (event.position().y(), self.zoom)
            return
        if event.button() == Qt.MouseButton.MiddleButton or (
            event.button() == Qt.MouseButton.LeftButton and getattr(self, "navigation_pan", False)
        ):
            self._panning = True
            self._pan_start_mouse = event.position()
            self._pan_start_offset = QPointF(self.pan_offset)
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return
        if event.button() == Qt.MouseButton.RightButton:
            event.accept()
            return
        pos = event.position()
        snap_pt, snap_kind = self._event_snap_point(pos)
        self._snap_point = snap_pt
        if snap_pt is not None:
            wx, wy = snap_pt.x, snap_pt.y
        else:
            w = self.screen_to_world(pos.x(), pos.y())
            wx, wy = w.x(), w.y()
            wx, wy = self._apply_ortho(wx, wy)
        from .drafting_aids import adjust as adjust_drafting_aids
        wx,wy,snap_kind=adjust_drafting_aids(self,wx,wy,snap_kind or '')
        if snap_kind.startswith(('Track','Locked')):self._snap_point=Point(wx,wy)
        self._click_modifiers = event.modifiers()
        try:
            self.world_clicked.emit(wx, wy, snap_kind or "", event.button().value)
        finally:
            self._click_modifiers = Qt.KeyboardModifier.NoModifier
        super().mousePressEvent(event)

    def pick_at(self, pos):
        from .geom_ops import pick_entity
        w = self.screen_to_world(pos.x(), pos.y())
        tol = 8 / self.zoom
        return pick_entity(self.document.query_entities((w.x()-tol,w.y()-tol,w.x()+tol,w.y()+tol),
                                                        editable_only=True),Point(w.x(),w.y()),tol)

    @safe_event
    def contextMenuEvent(self, event):
        window = self.window()
        if not hasattr(window, 'run_ribbon_command'):
            return super().contextMenuEvent(event)
        if self.document.current_space != 'Model':
            return
        if getattr(self._active_tool, 'name', None) == 'SELECT':
            from .polyline_grips import context
            point=self.screen_to_world(event.pos().x(),event.pos().y())
            menu=context(window,Point(point.x(),point.y()))
            if menu is not None:
                menu.exec(event.globalPos());menu.deleteLater();event.accept();return
            hit = self.pick_at(event.pos())
            if hit is not None and hit not in self.selected_entities:
                self.selected_entities = [hit]
                window.refresh_selection_ui()
        from .object_commands import context_menu
        menu = context_menu(window, event.pos())
        menu.exec(event.globalPos())
        menu.deleteLater()
        event.accept()

    @safe_event
    def mouseDoubleClickEvent(self, event):
        if (event.button()==Qt.MouseButton.LeftButton and
                getattr(self._active_tool,'name',None)=='SELECT' and
                event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier)):
            # The first press already applied the idempotent add/remove action.
            # A rapid repeated modifier click must not open a block editor.
            event.accept()
            return
        window = self.window()
        if (event.button() == Qt.MouseButton.LeftButton and self.document.current_space == 'Model'
                and getattr(self._active_tool, 'name', None) == 'SELECT'):
            hit = self.pick_at(event.position())
            if isinstance(hit,HatchEntity):
                cancel=getattr(self._active_tool,'cancel_drag',None)
                if cancel:cancel()
                self.selected_entities=[hit]
                if hasattr(window,'refresh_selection_ui'):window.refresh_selection_ui()
                from .hatch_ui import edit_hatch
                edit_hatch(window)
                event.accept()
                return
            if isinstance(hit, BlockReferenceEntity) and hasattr(window,'edit_block_dialog'):
                cancel = getattr(self._active_tool,'cancel_drag',None)
                if cancel: cancel()
                self.selected_entities = [hit]
                window.refresh_selection_ui()
                window.edit_block_dialog(hit.block_name)
                event.accept()
                return
        super().mouseDoubleClickEvent(event)

    @safe_event
    def mouseMoveEvent(self, event: QMouseEvent):
        pos = event.position()
        if getattr(self, "_zoom_drag", None) is not None:
            self._begin_navigation_preview()
            start_y, start_zoom = self._zoom_drag
            self.zoom = max(.01,min(100000,start_zoom * math.exp(max(-20,min(20,(start_y-pos.y())*.01)))))
            self.viewport().update()
            return
        if self._panning and self._pan_start_mouse is not None:
            dx = (pos.x() - self._pan_start_mouse.x()) / self.zoom
            dy = (pos.y() - self._pan_start_mouse.y()) / self.zoom
            self.pan_offset = QPointF(self._pan_start_offset.x() - dx,
                                       self._pan_start_offset.y() + dy)
            self.viewport().update()
            return
        snap_pt, snap_kind = self._event_snap_point(pos)
        self._snap_point = snap_pt
        if snap_pt is not None:
            wx, wy = snap_pt.x, snap_pt.y
        else:
            w = self.screen_to_world(pos.x(), pos.y())
            wx, wy = w.x(), w.y()
            wx, wy = self._apply_ortho(wx, wy)
        from .drafting_aids import adjust as adjust_drafting_aids
        wx,wy,snap_kind=adjust_drafting_aids(self,wx,wy,snap_kind or "")
        if snap_kind.startswith(("Track","Locked")):self._snap_point=Point(wx,wy)
        self.world_mouse_moved.emit(wx, wy, snap_kind or "")
        self.viewport().update()
        super().mouseMoveEvent(event)

    @safe_event
    def mouseReleaseEvent(self, event: QMouseEvent):
        if getattr(self, "_zoom_drag", None) is not None and event.button() == Qt.MouseButton.LeftButton:
            self._zoom_drag = None
            self._finish_navigation_preview()
            return
        if self._panning and event.button() in (Qt.MouseButton.MiddleButton, Qt.MouseButton.LeftButton):
            self._panning = False
            self.viewport().update()  # Replace the drag preview with an exact frame.
            self.setCursor(Qt.CursorShape.OpenHandCursor if getattr(self, "navigation_pan", False) else Qt.CursorShape.CrossCursor)
            return
        if event.button() == Qt.MouseButton.LeftButton and self._active_tool is not None:
            finish_drag = getattr(self._active_tool, "finish_drag", None)
            if callable(finish_drag):
                finish_drag()
            window = self.window()
            if hasattr(window, "refresh_selection_ui"):
                window.refresh_selection_ui()
        super().mouseReleaseEvent(event)

    def _begin_navigation_preview(self):
        from PyQt6.QtCore import QTimer
        if '_wheel_timer' not in self.__dict__:
            self._wheel_timer=QTimer(self);self._wheel_timer.setSingleShot(True);self._wheel_timer.timeout.connect(self._finish_navigation_preview)
        self._navigation_preview=True;self._wheel_timer.start(120)

    def _finish_navigation_preview(self):
        if "_wheel_timer" in self.__dict__:self._wheel_timer.stop()
        self._navigation_preview=False
        self.viewport().update()

    @safe_event
    def wheelEvent(self, event: QWheelEvent):
        delta=event.angleDelta().y() or event.pixelDelta().y()
        if not delta:event.ignore();return
        self._begin_navigation_preview()
        pos = event.position()
        before = self.screen_to_world(pos.x(), pos.y())
        factor = 1.15 ** max(-20,min(20,delta/120))
        self.zoom *= factor
        self.zoom = max(0.05, min(self.zoom, 5000))
        after = self.screen_to_world(pos.x(), pos.y())
        self.pan_offset = QPointF(self.pan_offset.x() - (after.x() - before.x()),
                                   self.pan_offset.y() - (after.y() - before.y()))
        self.viewport().update()

    @safe_event
    def keyPressEvent(self, event: QKeyEvent):
        window = self.window()
        if hasattr(window, "route_viewport_key") and window.route_viewport_key(self, event):
            return
        self.key_pressed.emit(event.key())
        if event.key() == Qt.Key.Key_Escape:
            self.rubber_band_start = None
            self.rubber_band_end = None
        super().keyPressEvent(event)

    def event(self, event):
        from PyQt6.QtCore import QEvent
        if event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Tab:
            window = self.window()
            if hasattr(window, 'route_viewport_key') and window.route_viewport_key(self, event):
                return True
        return super().event(event)

    def zoom_extents(self):
        if self.document.current_space != "Model":
            layout = self.document.layouts.get(self.document.current_space)
            if layout is not None:
                w = max(layout.page_width, 1e-6)
                h = max(layout.page_height, 1e-6)
                vw, vh = max(self.viewport().width(), 1), max(self.viewport().height(), 1)
                self.zoom = 0.85 * min(vw / w, vh / h)
                self.pan_offset = QPointF(layout.page_width / 2, layout.page_height / 2)
                self.viewport().update()
                return
        from .underlays import bounds
        boxes = [e.bbox() for e in self.document.visible_entities()] + bounds(self.document)
        if not boxes:
            self.zoom = 10.0
            self.pan_offset = QPointF(0, 0)
            self.viewport().update()
            return
        xs_min = min(b[0] for b in boxes)
        ys_min = min(b[1] for b in boxes)
        xs_max = max(b[2] for b in boxes)
        ys_max = max(b[3] for b in boxes)
        w = max(xs_max - xs_min, 1e-6)
        h = max(ys_max - ys_min, 1e-6)
        vw, vh = max(self.viewport().width(), 1), max(self.viewport().height(), 1)
        self.zoom = 0.85 * min(vw / w, vh / h)
        self.pan_offset = QPointF((xs_min + xs_max) / 2, (ys_min + ys_max) / 2)
        self.viewport().update()
