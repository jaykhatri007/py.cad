"""Camera-independent, disposable Qt display lists; model data stays authoritative."""
import math,time
from PyQt6.QtCore import Qt,QPointF,QRect,QRectF,QSize,QTimer
from PyQt6.QtGui import QPicture,QPainter,QPen,QPainterPath,QImage
from .geometry import (LineEntity,PolylineEntity,CircleEntity,ArcEntity,EllipseEntity,SplineEntity,HatchEntity,BlockReferenceEntity,TextEntity,RayEntity,XLineEntity)
REF=16.

class View:
 def __init__(self,real,bounds):self.real=real;self.bounds=bounds
 def rect(self):return self.bounds
 def width(self):return self.bounds.width()
 def height(self):return self.bounds.height()
 def size(self):return self.bounds.size()
 def __getattr__(self,name):return getattr(self.real,name)

class Ink:
 def __init__(self,p):self.p=p;self.world_width=False
 def setPen(self,pen):
  pen=QPen(pen);pen.setCosmetic(not self.world_width);self.p.setPen(pen)
 def __getattr__(self,name):return getattr(self.p,name)


def signature(canvas,key,painter):return key[:3]+key[8:]+(painter.renderHints().value,)

def compatible(a,b):return a is not None and a[:3]+a[8:]==b[:3]+b[8:]

def raster_fallback(canvas,painter,key):
 old=canvas.__dict__.get('_drawing_image_key');image=canvas.__dict__.get('_drawing_image')
 if image is None or not compatible(old,key) or old[3]<=0:return False
 scale=key[3]/old[3];dx=key[6]/2-old[6]/2*scale+(old[4]-key[4])*key[3];dy=key[7]/2-old[7]/2*scale+(key[5]-old[5])*key[3]
 painter.save()
 try:painter.translate(dx,dy);painter.scale(scale,scale);painter.drawImage(0,0,image)
 finally:painter.restore()
 return True


def record(canvas,batch,hints):
 boxes=[e.bbox() for e in batch];box=(min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes));ox=(box[0]+box[2])/2;oy=(box[1]+box[3])/2
 if not all(math.isfinite(v) for v in box) or max(box[2]-box[0],box[3]-box[1])*REF>1e8:return None,False
 if not any(isinstance(e,BlockReferenceEntity) for e in batch) and not all(static_entity(canvas.document,e) for e in batch):return (box,(ox,oy),None),False
 picture=QPicture();p=QPainter(picture);p.setRenderHints(hints);ink=Ink(p);exact=all(static_entity(canvas.document,e) for e in batch)
 names=('zoom','pan_offset','world_to_screen','screen_to_world','viewport','_draw_entity','_frame_transform','_frame_pixel_scale','_frame_world_box','selected_entities','_lod_paint')
 missing=object();old={name:canvas.__dict__.get(name,missing) for name in names};view=canvas.viewport();original=canvas._draw_entity
 def draw(painter,e):
  nonlocal exact
  supported=isinstance(e,(LineEntity,PolylineEntity,CircleEntity,ArcEntity,EllipseEntity,SplineEntity,BlockReferenceEntity))
  if isinstance(e,TextEntity):supported=not e.rich_html and not e.wrap_width and 1<=e.height*REF<=10000
  if isinstance(e,HatchEntity):supported=e.pattern=='SOLID'
  if not supported:exact=False;return
  if canvas.document.entity_linetype(e) not in ('CONTINUOUS','BYBLOCK') and not (e.linetype=='BYLAYER' and e.layer=='0'):exact=False
  width=ink.world_width;ink.world_width=isinstance(e,PolylineEntity) and e.width>0
  try:
   if isinstance(e,PolylineEntity):
    from .precision import arc_data
    path=QPainterPath()
    if e.points:path.moveTo(canvas.world_to_screen(e.points[0].x,e.points[0].y))
    for i,(a,b) in enumerate(zip(e.points,e.points[1:]+([e.points[0]] if e.closed else []))):
     arc=arc_data(a,b,e.bulges[i])
     if arc:
      center,radius,start,sweep=arc;point=canvas.world_to_screen(center.x,center.y);radius*=REF
      path.arcTo(QRectF(point.x()-radius,point.y()-radius,2*radius,2*radius),math.degrees(start),math.degrees(sweep))
     else:path.lineTo(canvas.world_to_screen(b.x,b.y))
    if e.closed:path.closeSubpath()
    painter.save()
    try:
     if e.width>0:
      pen=QPen(painter.pen());pen.setWidthF(max(.01,e.width*REF));pen.setCapStyle(Qt.PenCapStyle.FlatCap);pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin);painter.setPen(pen)
     painter.drawPath(path)
    finally:painter.restore()
   else:original(painter,e)
  finally:ink.world_width=width
 try:
  canvas.zoom=REF;canvas.pan_offset=QPointF(ox,oy);canvas.world_to_screen=lambda x,y:QPointF((x-ox)*REF,-(y-oy)*REF);canvas.screen_to_world=lambda x,y:QPointF(x/REF+ox,-y/REF+oy)
  bounds=QRect(math.floor((box[0]-ox)*REF)-64,math.floor(-(box[3]-oy)*REF)-64,max(128,math.ceil((box[2]-box[0])*REF)+128),max(128,math.ceil((box[3]-box[1])*REF)+128));canvas.viewport=lambda:View(view,bounds)
  canvas._draw_entity=draw;canvas._frame_transform=(0,0,ox,oy,REF);canvas._frame_pixel_scale=REF;canvas._frame_world_box=None;canvas.selected_entities=[];canvas._lod_paint=False
  canvas._draw_entities(ink,entities=batch)
 finally:
  p.end()
  for name,value in old.items():
   if value is missing:canvas.__dict__.pop(name,None)
   else:setattr(canvas,name,value)
 return (box,(ox,oy),picture),exact


def static_entity(doc,e):
 if isinstance(e,BlockReferenceEntity):return True # classified while recording children
 if isinstance(e,TextEntity):supported=not e.rich_html and not e.wrap_width and 1<=e.height*REF<=10000
 elif isinstance(e,HatchEntity):supported=e.pattern=='SOLID'
 else:supported=isinstance(e,(LineEntity,PolylineEntity,CircleEntity,ArcEntity,EllipseEntity,SplineEntity))
 return supported and doc.entity_linetype(e) in ('CONTINUOUS','BYBLOCK')


def chunks(canvas):
 # Keep highly interleaved small runs together, while isolating occasional
 # unsupported objects from long static runs. Bound Qt picture allocation.
 from .progressive_display import tasks
 for batch in tasks(canvas.document.entities,None,canvas.document.render_revision):
  runs=[];run=[];kind=None
  for entity in batch:
   eligible=static_entity(canvas.document,entity)
   if run and eligible!=kind:runs.append(run);run=[]
   kind=eligible;run.append(entity)
  if run:runs.append(run)
  if len(runs)<=5 and any(len(run)>=64 for run in runs):yield from runs
  else:yield batch


def update(canvas,painter,key):
 if (key[-1] and not (canvas.isVisible() and canvas.__dict__.get('async_display_enabled',True))) or canvas.__dict__.get('_viewport_override') or canvas.__dict__.get('_monochrome'):return None
 sig=signature(canvas,key,painter);state=canvas.__dict__.get('_retained_scene')
 if state is None or state['signature']!=sig:
  state=dict(signature=sig,items=[],iterator=chunks(canvas),ready=False,exact=not bool(canvas.document.underlays),tasks=0,compile_ms=0.)
  from .async_display import SnapshotDocument
  if canvas.isVisible() and canvas.__dict__.get('async_display_enabled',True):
   from .render_snapshot import capture
   state['capture']=capture(canvas);state['snapshot_only']=True
  else:state['snapshot_doc']=SnapshotDocument(canvas.document)
  canvas._retained_scene=state
 if not state['ready'] and not canvas.__dict__.get('_navigation_preview',False) and not canvas.__dict__.get('_panning',False):
  start=time.perf_counter()
  while time.perf_counter()-start<.008:
   if state.get('snapshot_only'):
    try:value=next(state['capture'])
    except StopIteration:state['ready']=True;break
    if value is not None:
     kind,payload=value
     if kind=='document':state['snapshot_doc']=payload
     else:state['items'].append(payload);state['tasks']+=1
    continue
   try:batch=next(state['iterator'])
   except StopIteration:state['ready']=True;break
   item,exact=record(canvas,batch,painter.renderHints());state['exact'] &= exact
   if not exact:
    pending=list(batch);unbounded=False
    while pending:
     e=pending.pop()
     if isinstance(e,(RayEntity,XLineEntity)):unbounded=True;break
     if isinstance(e,BlockReferenceEntity):pending.extend(e.resolved_entities)
    if unbounded:item=None
   from .async_display import freeze_entities
   frozen=None if exact else freeze_entities(batch)
   state['items'].append((*item,None if exact else batch,frozen) if item is not None else (None,None,None,batch,frozen))
   state['tasks']+=1

  state['compile_ms']+=(time.perf_counter()-start)*1000
  if not state['ready']:
   def resume():
    try:
     if canvas.__dict__.get('_retained_scene') is state:canvas.viewport().update()
    except RuntimeError:pass
   QTimer.singleShot(0,resume)
 return state


def draw(canvas,painter,state):
 a=canvas.screen_to_world(-40,-40);b=canvas.screen_to_world(canvas.viewport().width()+40,canvas.viewport().height()+40);view=(min(a.x(),b.x()),min(a.y(),b.y()),max(a.x(),b.x()),max(a.y(),b.y()));zoom=canvas.zoom
 from .tolerance import bounds_overlap
 for item in state['items']:
  bounds,origin,picture=item[:3];dynamic=item[3] if len(item)>3 else None
  if bounds is not None and not bounds_overlap(bounds,view):continue
  if dynamic is not None:
   canvas._draw_entities(painter,entities=dynamic);continue
  point=canvas.world_to_screen(*origin);painter.save()
  try:painter.translate(point);painter.scale(zoom/REF,zoom/REF);painter.drawPicture(0,0,picture)
  finally:painter.restore()


def paint(canvas,painter,key):
 state=update(canvas,painter,key)
 if state is None:return False
 if not state['ready']:
  if state.get('snapshot_only'):
   raster_fallback(canvas,painter,key);canvas._last_draw_kind='background preparing frame';canvas.progressive_stats=dict(complete=False,candidates=len(canvas.document.entities),painted=0,draw_tasks=state['tasks'],last_chunk_ms=0)
   return True
  return False
 from .async_display import paint as background_paint
 if background_paint(canvas,painter,key,state):return True
 canvas._last_draw_kind='retained vector frame'
 token=(state['signature'],key);frame=canvas.__dict__.get('_retained_frame')
 if frame is None or frame['token']!=token:
  image=QImage(canvas.viewport().size(),QImage.Format.Format_ARGB32_Premultiplied);image.fill(Qt.GlobalColor.transparent)
  frame=dict(token=token,image=image,items=iter(state['items']),complete=False,tasks=0);canvas._retained_frame=frame
  if canvas.document.underlays:
   from .underlays import draw_underlays
   underlay=QPainter(image)
   try:draw_underlays(canvas,underlay)
   finally:underlay.end()
 if not frame['complete']:
  start=time.perf_counter();cache=QPainter(frame['image']);cache.setRenderHints(painter.renderHints());selected=canvas.selected_entities
  try:
   canvas.selected_entities=[]
   while time.perf_counter()-start<.008:
    try:item=next(frame['items'])
    except StopIteration:frame['complete']=True;break
    draw(canvas,cache,dict(items=[item]));frame['tasks']+=1
  finally:canvas.selected_entities=selected;cache.end()
  if frame['complete']:
   canvas._drawing_image=frame['image'];canvas._drawing_image_key=key
  else:
   def resume():
    try:
     if canvas.__dict__.get('_retained_frame') is frame:canvas.viewport().update()
    except RuntimeError:pass
   QTimer.singleShot(0,resume)
 if frame['complete'] or not raster_fallback(canvas,painter,key):painter.drawImage(0,0,frame['image'])
 from .progressive_display import selection
 selection(canvas,painter,key)
 canvas.progressive_stats=dict(candidates=len(canvas.document.entities),painted=len(canvas.document.entities) if frame['complete'] else 0,draw_tasks=frame['tasks'],complete=frame['complete'],last_chunk_ms=0,retained=True,compile_ms=state['compile_ms'])
 canvas._last_retained_key=key
 return True


def fallback(canvas,painter,key):
 return raster_fallback(canvas,painter,key)
