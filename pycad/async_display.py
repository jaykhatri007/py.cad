"""Background QImage rendering from private geometry snapshots; no worker widgets."""
import copy, math, time, threading, types, weakref, logging
from collections import OrderedDict
from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal, pyqtSlot, Qt, QPointF, QSize, QRect
from PyQt6.QtGui import QImage, QPainter

_CONTROLLERS = weakref.WeakSet()


def freeze_entities(entities):
    """Copy only model fields, never disposable indices or live Qt caches."""
    from .geometry import BlockReferenceEntity
    from .render_snapshot import model_field
    result=[];pending=[(entities,result)]
    while pending:
        source,target=pending.pop()
        for entity in source:
            clone=object.__new__(type(entity))
            clone.__dict__={k:copy.deepcopy(v) for k,v in entity.__dict__.items() if model_field(k) and k!='resolved_entities'}
            if isinstance(entity,BlockReferenceEntity):
                clone.resolved_entities=[];pending.append((entity.resolved_entities,clone.resolved_entities))
            target.append(clone)
    return result


class SnapshotDocument:
    def __init__(self,doc):
        for key in ('layers','textstyles','dimstyles','mleaderstyles','units','unit_settings','linetype_scale','extensions','isolated_ids','render_revision','current_space','underlays','filepath','layouts'):
            setattr(self,key,copy.deepcopy(getattr(doc,key)))
        self.entities=[]
    def __getattr__(self,key):
        from .document import Document
        method=getattr(Document,key,None)
        if callable(method):return types.MethodType(method,self)
        raise AttributeError(key)


class View:
    def __init__(self,w,h):self.w=w;self.h=h
    def width(self):return self.w
    def height(self):return self.h
    def size(self):return QSize(self.w,self.h)
    def rect(self):return QRect(0,0,self.w,self.h)


class SnapshotCanvas:
    def __init__(self,doc,pose,colors,lod=False):
        self.document=doc;self.zoom,self.pan_offset=pose[0],QPointF(pose[1],pose[2]);self.view=View(pose[3],pose[4]);self.appearance_colors=colors
        self.selected_entities=[];self.gpu_geometry_enabled=False;self.boq_overlay_enabled=False;self.lod=lod;self.point_count=0;self.selected_viewport=None
    def viewport(self):return self.view
    def _draw_entities(self,painter,paper=False,entities=None):
        from .geometry import LineEntity,CircleEntity,ArcEntity,PolylineEntity,HatchEntity
        if self.lod and not self.boq_overlay_enabled and entities and all(isinstance(e,(LineEntity,CircleEntity,ArcEntity,PolylineEntity,HatchEntity)) for e in entities):
            bounds=[]
            for e in entities:
                box=e.__dict__.get('_snapshot_bbox')
                if box is None:box=e.bbox();e._snapshot_bbox=box
                bounds.append(box)
            if all(max(b[2]-b[0],b[3]-b[1])*self.zoom<1.5 for b in bounds):
                from PyQt6.QtGui import QPen,QColor
                points=[];style=None
                def flush():
                    if not points:return
                    color,width,opacity=style;pen=QPen(QColor(color));pen.setWidthF(width);painter.setPen(pen);painter.setOpacity(opacity);painter.drawPoints(points)
                painter.save()
                try:
                    for e,b in zip(entities,bounds):
                        if not self.document.is_visible(e):continue
                        ink=(self.document.entity_color(e),max(1,self.document.layers.layers.get(e.layer,{}).get('lineweight',.25)*3.78),1-e.transparency/100)
                        if ink!=style:flush();points=[];style=ink
                        points.append(self.world_to_screen((b[0]+b[2])/2,(b[1]+b[3])/2));self.point_count+=1
                    flush()
                finally:painter.restore()
                return
        from .canvas import CadCanvas
        return CadCanvas._draw_entities(self,painter,paper,entities)
    def _draw_entity(self,painter,entity):
        from .geometry import HatchEntity
        if isinstance(entity,HatchEntity) and entity.pattern!='SOLID':
            from .hatching import GRADIENTS,definitions,render_loops
            if entity.pattern not in GRADIENTS and entity.boundary:
                cached=entity.__dict__.get('_snapshot_dense')
                if cached is None:
                    from PyQt6.QtGui import QPainterPath
                    spacing=min((abs(-math.sin(math.radians(a))*off[0]+math.cos(math.radians(a))*off[1]) for a,_,off,_ in definitions(entity)),default=float('inf'))
                    origin=entity.boundary[0];path=QPainterPath();path.setFillRule(Qt.FillRule.OddEvenFill)
                    for loop in render_loops(entity):
                        if not loop:continue
                        path.moveTo(loop[0].x-origin.x,loop[0].y-origin.y)
                        for point in loop[1:]:path.lineTo(point.x-origin.x,point.y-origin.y)
                        path.closeSubpath()
                    cached=(spacing,(origin.x,origin.y),path);entity._snapshot_dense=cached
                spacing,origin,path=cached
                if spacing*self.zoom<2:
                    from PyQt6.QtGui import QTransform,QColor,QBrush
                    at=self.world_to_screen(*origin);mapped=QTransform(self.zoom,0,0,-self.zoom,at.x(),at.y()).map(path)
                    if entity.background_color:painter.fillPath(mapped,QColor(entity.background_color))
                    painter.fillPath(mapped,QBrush(painter.pen().color(),Qt.BrushStyle.Dense4Pattern));return
        from .canvas import CadCanvas
        return CadCanvas._draw_entity(self,painter,entity)
    def __getattr__(self,key):
        from .canvas import CadCanvas
        method=getattr(CadCanvas,key,None)
        if callable(method):return types.MethodType(method,self)
        raise AttributeError(key)


class Signals(QObject):
    finished=pyqtSignal(object,object,object)


class Job(QRunnable):
    def __init__(self,items,doc,pose,hints,colors,signature,lod=False):
        super().__init__();self.items=items;self.doc=doc;self.pose=pose;self.hints=hints;self.colors=colors;self.signature=signature;self.lod=lod
        self.signals=Signals();self.cancelled=threading.Event();self.stats={}
    def run(self):
        image=None;error=None;p=None;start=time.perf_counter();errors=[];ident=threading.get_ident()
        class Capture(logging.Handler):
            def emit(self,record):
                if record.thread==ident and record.levelno>=logging.ERROR:errors.append(record.getMessage())
        capture=Capture();log=logging.getLogger('pycad.canvas');log.addHandler(capture)
        try:
            z,px,py,w,h=self.pose
            image=QImage(w,h,QImage.Format.Format_ARGB32_Premultiplied);image.fill(Qt.GlobalColor.transparent)
            p=QPainter(image);p.setRenderHints(self.hints)
            if getattr(self,'base_font',None):
                from PyQt6.QtGui import QFont
                font=QFont();font.fromString(self.base_font);p.setFont(font)
            proxy=SnapshotCanvas(self.doc,self.pose,self.colors,self.lod)
            proxy.boq_overlay_enabled=getattr(self,'boq',False)
            if proxy.boq_overlay_enabled:
                proxy._boq_overlay_revision=(id(self.doc),self.doc.render_revision);proxy._boq_overlay=getattr(self.doc,'_boq_data',{})
            box=(px-w/2/z-40/z,py-h/2/z-40/z,px+w/2/z+40/z,py+h/2/z+40/z)
            from .tolerance import bounds_overlap
            from .retained_scene import REF
            from .underlays import draw_underlays
            if self.doc.current_space!='Model':proxy._draw_layout_viewports(p)
            else:draw_underlays(proxy,p)
            count=0
            for item in (() if self.doc.current_space!='Model' else self.items):
                if self.cancelled.is_set():return
                bounds,origin,picture,dynamic=item[:4]
                if bounds is not None and not bounds_overlap(bounds,box):continue
                if dynamic is not None:
                    proxy._draw_entities(p,entities=item[4])
                else:
                    p.save()
                    try:
                        p.translate(w/2+(origin[0]-px)*z,h/2-(origin[1]-py)*z);p.scale(z/REF,z/REF);p.drawPicture(0,0,picture)
                    finally:p.restore()
                count+=1
                if not getattr(self,'_external_process',False):time.sleep(0)
            if errors:raise RuntimeError('; '.join(errors))
            self.stats=dict(worker_ms=(time.perf_counter()-start)*1000,items=count,lod_points=proxy.point_count)
        except Exception as ex:error=repr(ex)
        finally:
            log.removeHandler(capture)
            if p is not None:p.end()
            if not self.cancelled.is_set():self.signals.finished.emit(self,image,error)
            else:self.signals.finished.emit(self,None,'cancelled')


class Controller(QObject):
    BUDGET=48*1024*1024
    def __init__(self,canvas):
        super().__init__(canvas);self.canvas=weakref.ref(canvas);self.pool=QThreadPool();self.pool.setMaxThreadCount(1);self.pool.setExpiryTimeout(3000)
        self.cache=OrderedDict();self.bytes=0;self.active=None;self.signature=None;self.hits=0;self.jobs=0;self.closed=False
        _CONTROLLERS.add(self);canvas.destroyed.connect(self.close)
    def close(self,*args):
        if self.closed:return
        self.closed=True
        if self.active:self.active.cancelled.set()
        from PyQt6 import sip
        if not sip.isdeleted(self.pool):self.pool.waitForDone()
        self.active=None;self.cache.clear();self.bytes=0
    @pyqtSlot(object,object,object)
    def accept(self,job,image,error):
        if self.active is job:self.active=None
        canvas=self.canvas()
        if self.closed or canvas is None:return
        if job.signature!=self.signature:
            try:canvas.viewport().update()
            except RuntimeError:pass
            return
        if error and error!='cancelled':
            canvas._async_display_error=error
        elif image is not None:
            pose=job.pose;key=tuple(pose)
            if key in self.cache:self.bytes-=self.cache.pop(key).sizeInBytes()
            self.cache[key]=image;self.bytes+=image.sizeInBytes()
            while self.bytes>self.BUDGET and len(self.cache)>1:
                self.bytes-=self.cache.popitem(last=False)[1].sizeInBytes()
            canvas._async_worker_stats=job.stats
            canvas._boq_overlay_error=job.stats.get('boq_error','')
            canvas._render_process_error=''
        try:canvas.viewport().update()
        except RuntimeError:pass
    def reset(self,signature):
        if self.signature==signature:return
        if self.active:self.active.cancelled.set()
        self.signature=signature;self.cache.clear();self.bytes=0
    def cached(self,canvas,painter,key):
        z,px,py,w,h=key[3:8]
        for pose,image in reversed(list(self.cache.items())):
            oz,ox,oy,iw,ih=pose
            reuse=canvas.__dict__.get('reuse_nearby_zooms',True) and getattr(self,'isolated_process',False)
            if (not (.8<=z/oz<=1.25)) if reuse else (abs(z/oz-1)>1e-10):continue
            ratio=z/oz;dx=w/2-iw/2*ratio+(ox-px)*z;dy=h/2-ih/2*ratio+(py-oy)*z
            if dx>1e-5 or dy>1e-5 or dx+iw*ratio<w-1e-5 or dy+ih*ratio<h-1e-5:continue
            painter.save()
            try:painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform);painter.translate(dx,dy);painter.scale(ratio,ratio);painter.drawImage(0,0,image)
            finally:painter.restore()
            self.cache.move_to_end(pose);self.hits+=1
            # Maintain the established viewport-image contract for wheel previews.
            if canvas.__dict__.get('_drawing_image_key')!=key:
                cropped=QImage(w,h,QImage.Format.Format_ARGB32_Premultiplied);cropped.fill(Qt.GlobalColor.transparent);p=QPainter(cropped)
                try:p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform);p.translate(dx,dy);p.scale(ratio,ratio);p.drawImage(0,0,image)
                finally:p.end()
                canvas._drawing_image=cropped;canvas._drawing_image_key=key
            from .progressive_display import selection
            if hasattr(self,'paint_selection'):self.paint_selection(canvas,painter,key)
            else:selection(canvas,painter,key)
            canvas._last_draw_kind='background cached frame'
            canvas.progressive_stats=dict(complete=True,candidates=len(canvas.document.entities),painted=len(canvas.document.entities),draw_tasks=0,last_chunk_ms=0,background=True,cache_hits=self.hits,worker_jobs=self.jobs,cache_bytes=self.bytes)
            return True
        return False


def enabled(canvas):
    return canvas.__dict__.get('async_display_enabled',True) and canvas.isVisible()


def try_cached(canvas,painter,key):
    controller=canvas.__dict__.get('_async_controller')
    if controller is None or not enabled(canvas):return False
    from .retained_scene import signature
    controller.reset(signature(canvas,key,painter));return controller.cached(canvas,painter,key)


def paint(canvas,painter,key,state):
    if not enabled(canvas):
        controller=canvas.__dict__.get('_async_controller')
        if controller is not None and controller.active:
            controller.active.cancelled.set()
            from .retained_scene import raster_fallback
            raster_fallback(canvas,painter,key)
            return True
        return False
    controller=canvas.__dict__.get('_async_controller')
    if controller is None:
        from .render_process import ProcessController
        controller=ProcessController(canvas);canvas._async_controller=controller
    controller.reset(state['signature'])
    if controller.cached(canvas,painter,key):return True
    controller.request(state,key,painter,canvas)
    from .retained_scene import raster_fallback
    if not raster_fallback(canvas,painter,key):
        partial=canvas.__dict__.get('_progressive_image')
        if partial is not None:painter.drawImage(0,0,partial)
    from .progressive_display import selection
    if hasattr(controller,'paint_selection'):controller.paint_selection(canvas,painter,key)
    else:selection(canvas,painter,key)
    canvas._last_draw_kind='background refining frame'
    canvas.progressive_stats=dict(complete=False,candidates=len(canvas.document.entities),painted=0,draw_tasks=0,last_chunk_ms=0,background=True,cache_hits=controller.hits,worker_jobs=controller.jobs,cache_bytes=controller.bytes)
    return True


def shutdown():
    for controller in list(_CONTROLLERS):controller.close()
