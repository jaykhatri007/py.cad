"""Cancelable time-sliced viewport refinement, including nested block contents."""
import time,copy
from PyQt6.QtCore import Qt,QTimer
from PyQt6.QtGui import QImage,QPainter
from .geometry import BlockReferenceEntity

def heavy(canvas):
 doc=canvas.document;key=(id(doc),id(doc.entities),len(doc.entities),doc.render_revision)
 if canvas.__dict__.get('_heavy_key')!=key:
  image_cost=0
  for image in doc.underlays:
   width,height=image.get('pixels',[0,0])
   if image.get('visible',True):image_cost+=min(5000,max(0,int(width))*max(0,int(height))//256)
  count=len(doc.entities)+image_cost;pending=iter(doc.entities);stack=[pending]
  while count<5000 and stack:
   try:e=next(stack[-1])
   except StopIteration:stack.pop();continue
   if isinstance(e,BlockReferenceEntity):count+=len(e.resolved_entities);stack.append(iter(e.resolved_entities))
   else:
    count+=len(getattr(e,'points',()))*8
    if e.kind=='SPLINE':count+=len(getattr(e,'points',()))*32
    if e.kind=='HATCH':count+=len(e.boundary)+sum(len(hole) for hole in e.holes)+(128 if e.pattern!='SOLID' else 0)
    if e.kind=='TEXT':count+=16+(128 if e.rich_html or e.wrap_width else 0)
    count+=sum(len(getattr(e,k,''))//2 for k in ('text','rich_html','text_override') if isinstance(getattr(e,k,None),str))
    if e.kind=='ELLIPSE':count+=96
    if e.kind in ('DIMENSION','CURVED_DIMENSION','ORDINATE_DIMENSION'):count+=32
    if e.kind=='MLEADER':count+=64
  canvas._heavy_key=key;canvas._heavy_result=count>=5000
 return canvas._heavy_result

def block_parts(root,box,revision):
 from .block_display import visible_children
 stack=[(root,iter(visible_children(root,box,revision)),[])];emitted=False
 def wrap(batch):
  child=None
  for ref,iterator,unused in reversed(stack):
   clone=copy.copy(ref);clone.resolved_entities=list(batch) if child is None else [child];child=clone
  return child
 while stack:
  ref,iterator,batch=stack[-1]
  try:child=next(iterator)
  except StopIteration:
   if batch:emitted=True;yield wrap(batch)
   stack.pop();continue
  if isinstance(child,BlockReferenceEntity):
   if batch:emitted=True;yield wrap(batch);batch.clear()
   stack.append((child,iter(visible_children(child,box,revision)),[]))
  else:
   batch.append(child)
   if len(batch)>=64:emitted=True;yield wrap(batch);batch.clear()
 if not emitted:yield root

def tasks(entities,box,revision):
 batch=[]
 for e in entities:
  if isinstance(e,BlockReferenceEntity):
   if batch:yield batch;batch=[]
   for part in block_parts(e,box,revision):yield [part]
  else:
   batch.append(e)
   if len(batch)>=256:yield batch;batch=[]
 if batch:yield batch

def paint(canvas,painter,key):
 size=canvas.viewport().size()
 if canvas.__dict__.get('_progressive_key')!=key:
  canvas._progressive_key=key;canvas._progressive_image=QImage(size,QImage.Format.Format_ARGB32_Premultiplied);canvas._progressive_image.fill(Qt.GlobalColor.transparent)
  a=canvas.screen_to_world(-32,-32);b=canvas.screen_to_world(size.width()+32,size.height()+32);box=(min(a.x(),b.x()),min(a.y(),b.y()),max(a.x(),b.x()),max(a.y(),b.y()))
  # First display must not synchronously build the complete picking index.
  # Traverse in cooperative batches; Qt still clips the resulting strokes.
  cold=canvas.isVisible() and heavy(canvas) and canvas.document.spatial_index._dirty
  candidates=canvas.document.entities if cold else canvas.document.query_entities(box)
  canvas._progressive_entities=tasks(candidates,None if cold else box,canvas.document.render_revision)
  canvas.progressive_stats=dict(candidates=len(candidates),painted=0,draw_tasks=0,complete=False,last_chunk_ms=0)
  first=QPainter(canvas._progressive_image)
  try:
   from .underlays import draw_underlays
   draw_underlays(canvas,first)
  finally:first.end()
 state=canvas.progressive_stats
 if not state['complete']:
  start=time.perf_counter();painted=0;cache=QPainter(canvas._progressive_image);cache.setRenderHints(painter.renderHints());selected=canvas.selected_entities
  try:
   canvas.selected_entities=[];canvas._lod_paint=canvas.__dict__.get('drawing_path')=='progressive'
   while time.perf_counter()-start<.008 or painted==0:
    try:batch=next(canvas._progressive_entities)
    except StopIteration:state['complete']=True;state['painted']=state['candidates'];break
    canvas._draw_entities(cache,entities=batch);painted+=len(batch);state['draw_tasks']+=1
  finally:canvas.selected_entities=selected;canvas._lod_paint=False;cache.end()
  if not state['complete']:state['painted']=min(state['candidates'],state['painted']+painted)
  state['last_chunk_ms']=(time.perf_counter()-start)*1000
  if not state['complete']:
   token=canvas._progressive_key
   def resume():
    try:
     if canvas.__dict__.get('_progressive_key')==token:canvas.viewport().update()
    except RuntimeError:pass
   QTimer.singleShot(0,resume)
  else:canvas._drawing_image=canvas._progressive_image;canvas._drawing_image_key=key
 if not state['complete']:
  from .retained_scene import fallback
  if not fallback(canvas,painter,key):painter.drawImage(0,0,canvas._progressive_image)
 else:painter.drawImage(0,0,canvas._progressive_image)
 selection(canvas,painter,key)

def selection(canvas,painter,key):
 if not canvas.selected_entities:return
 token=(key,tuple(map(id,canvas.selected_entities)));size=canvas.viewport().size()
 if canvas.__dict__.get('_progressive_selection_key')!=token:
  canvas._progressive_selection_key=token;canvas._selection_image_key=token;canvas._selection_image=QImage(size,QImage.Format.Format_ARGB32_Premultiplied);canvas._selection_image.fill(Qt.GlobalColor.transparent)
  a=canvas.screen_to_world(-32,-32);b=canvas.screen_to_world(size.width()+32,size.height()+32);box=(min(a.x(),b.x()),min(a.y(),b.y()),max(a.x(),b.x()),max(a.y(),b.y()))
  canvas._selection_tasks=tasks(canvas.selected_entities,box,canvas.document.render_revision);canvas._selection_complete=False
 if not canvas._selection_complete:
  start=time.perf_counter();p=QPainter(canvas._selection_image);p.setRenderHints(painter.renderHints())
  try:
   while time.perf_counter()-start<.008:
    try:batch=next(canvas._selection_tasks)
    except StopIteration:canvas._selection_complete=True;break
    canvas._draw_entities(p,entities=batch)
  finally:p.end()
  if not canvas._selection_complete:
   def resume():
    try:
     if canvas.__dict__.get('_progressive_selection_key')==token:canvas.viewport().update()
    except RuntimeError:pass
   QTimer.singleShot(0,resume)
 painter.drawImage(0,0,canvas._selection_image)
