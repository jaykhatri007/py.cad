"""Camera-independent vector scene. Navigation never requests CAD regeneration."""
import json,math,os,time,hashlib,pickle,shutil
from collections import OrderedDict
from pathlib import Path
from PyQt6.QtCore import Qt,QTimer,QPointF,QRect,pyqtSlot
from PyQt6.QtGui import QPainter,QPicture,QFont,QPen,QColor,QPolygonF,QTransform,QImage
from .render_process import ProcessController
from .retained_scene import Ink
from .geometry import PolylineEntity,BlockReferenceEntity,RayEntity,XLineEntity,CircleEntity,LineEntity


def enabled(canvas):
 return canvas.isVisible() and os.environ.get('PYCAD_LEGACY_DISPLAY')!='1' and canvas.__dict__.get('persistent_scene_enabled',True) and not canvas.__dict__.get('_viewport_override') and '_plot_mm' not in canvas.__dict__


def index_tree(entries,ids=None):
 ids=list(range(len(entries))) if ids is None else ids
 if not ids:return None
 boxes=[entries[i]['bounds'] for i in ids];box=[min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes)]
 if len(ids)<=8:return [box,ids]
 axis=0 if box[2]-box[0]>=box[3]-box[1] else 1
 ids.sort(key=lambda i:entries[i]['bounds'][axis]+entries[i]['bounds'][axis+2]);m=len(ids)//2
 return [box,index_tree(entries,ids[:m]),index_tree(entries,ids[m:])]


def candidates(tree,box):
 pending=[tree];result=[]
 while pending:
  node=pending.pop()
  if node is None:continue
  b=node[0]
  if b[2]<box[0] or b[0]>box[2] or b[3]<box[1] or b[1]>box[3]:continue
  if len(node)==2:result.extend(node[1])
  else:pending.extend(node[1:])
 return sorted(result)


class VectorInk(Ink):
 """Expand dash intervals once into world geometry; widths stay cosmetic."""
 def drawPath(self,path):
  pen=self.p.pen();pattern=pen.dashPattern() if pen.style()==Qt.PenStyle.CustomDashLine else []
  if not pattern:return self.p.drawPath(path)
  from PyQt6.QtGui import QPainterPath
  length=path.length()
  if length<=1e-12:return
  path.setCachingEnabled(True);result=QPainterPath();width=max(pen.widthF(),1e-6);distance=0.;i=0
  while distance<length:
   end=min(length,distance+max(.000001,pattern[i%len(pattern)]*width))
   if i%2==0:result.addPath(path.trimmed(distance/length,end/length))
   distance=end;i+=1
  self.p.save()
  try:pen.setStyle(Qt.PenStyle.SolidLine);self.p.setPen(pen);self.p.drawPath(result)
  finally:self.p.restore()
 def drawLine(self,*args):
  from PyQt6.QtGui import QPainterPath
  from PyQt6.QtCore import QLineF
  if self.p.pen().style()!=Qt.PenStyle.CustomDashLine:return self.p.drawLine(*args)
  line=QLineF(*args);path=QPainterPath();path.moveTo(line.p1());path.lineTo(line.p2());self.drawPath(path)
 def drawLines(self,points):
  if self.p.pen().style()!=Qt.PenStyle.CustomDashLine:return self.p.drawLines(points)
  for a,b in zip(points[::2],points[1::2]):self.drawLine(a,b)
 def drawEllipse(self,*args):
  if self.p.pen().style()!=Qt.PenStyle.CustomDashLine:return self.p.drawEllipse(*args)
  from PyQt6.QtGui import QPainterPath
  from PyQt6.QtCore import QRectF
  path=QPainterPath()
  if len(args)==3:
   c,rx,ry=args;path.addEllipse(QRectF(c.x()-rx,c.y()-ry,rx*2,ry*2))
  else:path.addEllipse(*args)
  self.drawPath(path)


class RecordView:
 def __init__(self,w,h):self.w=w;self.h=h
 def width(self):return self.w
 def height(self):return self.h
 def rect(self):return QRect(0,0,self.w,self.h)


def record_vector(document,batch,request,selected=False,underlay=None,layout=None):
 from .async_display import SnapshotCanvas
 from .canvas import CadCanvas
 if layout:
  box=(0,0,layout.page_width,layout.page_height)
 elif underlay:
  x,y=underlay['origin'];w=underlay['width'];h=w*underlay['pixels'][1]/max(1,underlay['pixels'][0]);r=math.hypot(w,h);box=(x-r,y-r,x+r,y+r)
 else:
  boxes=[e.bbox() for e in batch];box=(min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes))
 if not all(math.isfinite(v) for v in box):raise ValueError('Non-finite display bounds')
 scale=min(16.,1e7/max(1.,box[2]-box[0],box[3]-box[1]));ox,oy=box[0],box[3]
 canvas=SnapshotCanvas(document,(scale,0,0,640,480),request['colors'],False)
 canvas.zoom=scale;canvas.world_to_screen=lambda x,y:QPointF((x-ox)*scale,(oy-y)*scale)
 canvas.screen_to_world=lambda x,y:QPointF(x/scale+ox,oy-y/scale)
 canvas.view=RecordView(max(128,math.ceil((box[2]-box[0])*scale)+64),max(128,math.ceil((box[3]-box[1])*scale)+64))
 canvas.selected_entities=batch if selected else [];canvas._frame_transform=(0,0,ox,oy,scale);canvas._frame_pixel_scale=scale;canvas._frame_world_box=None
 canvas._persistent_recording=True;canvas.boq_overlay_enabled=request.get('boq',False);canvas._boq_overlay_revision=(id(document),document.render_revision);canvas._boq_overlay=getattr(document,'_boq_data',{})
 # Preserve analytic polyline arcs instead of sampling them at the reference view.
 def entity(p,e):
  if document.extensions.get("office_linetypes"):
   from .office_ink import draw_custom
   if draw_custom(canvas,p,e):return
  if isinstance(e,PolylineEntity):
   from .precision import arc_data
   from PyQt6.QtCore import QRectF
   from PyQt6.QtGui import QPainterPath
   path=QPainterPath()
   if e.points:path.moveTo(canvas.world_to_screen(e.points[0].x,e.points[0].y))
   for i,(a,b) in enumerate(zip(e.points,e.points[1:]+([e.points[0]] if e.closed else []))):
    arc=arc_data(a,b,e.bulges[i])
    if arc:
     center,r,start,sweep=arc;c=canvas.world_to_screen(center.x,center.y);r*=scale;path.arcTo(QRectF(c.x()-r,c.y()-r,2*r,2*r),math.degrees(start),math.degrees(sweep))
    else:path.lineTo(canvas.world_to_screen(b.x,b.y))
   if e.closed:path.closeSubpath()
   p.save()
   try:
    if e.width>0:
     pen=QPen(p.pen());pen.setCosmetic(False);pen.setWidthF(e.width*scale);p.p.setPen(pen)
    p.drawPath(path)
   finally:p.restore()
  else:
   # Bypass camera-density substitutions: store the hatch commands once.
   CadCanvas._draw_entity(canvas,p,e)
 canvas._draw_entity=entity
 picture=QPicture();p=QPainter(picture);p.setRenderHints(QPainter.RenderHint(request['hints']));font=QFont();font.fromString(request['font']);p.setFont(font)
 try:
  if layout:
   canvas._frame_transform=None;canvas._draw_layout_viewports(VectorInk(p))
  elif underlay:
   from .underlays import draw_underlays
   saved=document.underlays;document.underlays=[underlay]
   try:draw_underlays(canvas,VectorInk(p))
   finally:document.underlays=saved
  elif batch and all(type(e) is CircleEntity and document.entity_linetype(e)=='CONTINUOUS' for e in batch) and not request.get('boq') and all(not e.transparency for e in batch):
   from PyQt6.QtGui import QPainterPath
   from PyQt6.QtCore import QRectF
   ink=VectorInk(p);path=QPainterPath();style=None
   def flush():
    if path.isEmpty():return
    color,width,opacity=style;pen=QPen(QColor(color));pen.setWidthF(width);ink.setPen(pen);p.setOpacity(opacity);ink.drawPath(path)
   for e in batch:
    if not document.is_visible(e):continue
    current=(request['colors']['ui_selection'] if selected else document.entity_color(e),max(2 if selected else 1,document.layers.layers.get(e.layer,{}).get('lineweight',.25)*3.78),1-e.transparency/100)
    if current!=style:flush();path=QPainterPath();style=current
    center=canvas.world_to_screen(e.center.x,e.center.y);r=e.radius*scale;path.addEllipse(QRectF(center.x()-r,center.y()-r,2*r,2*r))
   flush()
  else:canvas._draw_entities(VectorInk(p),entities=batch)
 finally:
  p.end();canvas.__dict__.pop("_draw_entity",None)
 # Expand culling by actual recorded ink, including labels/annotation overhangs.
 rect=picture.boundingRect();box=(min(box[0],ox+rect.left()/scale),min(box[1],oy-rect.bottom()/scale),max(box[2],ox+rect.right()/scale),max(box[3],oy-rect.top()/scale))
 return picture,dict(bounds=box,origin=(ox,oy),scale=scale)


_COMMAND_CACHE=OrderedDict()
_COMMAND_CACHE_BYTES=0
_COMMAND_CACHE_BUDGET=64*1024*1024


def _commands(document,batch,request,selected,underlay,layout):
 picture,entry=record_vector(document,batch,request,selected,underlay,layout);overview=None
 # A second immutable command list for genuinely subpixel geometry. No
 # geometry conversion, traversal or new jobs are needed to choose it.
 if batch and not selected and not request.get('boq') and all(type(e) is CircleEntity for e in batch):
  from PyQt6.QtGui import QPolygonF
  overview=QPicture();p=QPainter(overview);ink=Ink(p);points=[];style=None;span=0.
  def flush_points():
   if not points:return
   color,opacity=style;p.setOpacity(opacity);pen=QPen(QColor(color));pen.setWidthF(1);ink.setPen(pen);ink.drawPoints(QPolygonF(points))
  try:
   p.setRenderHint(QPainter.RenderHint.Antialiasing,False)
   for e in batch:
    if not document.is_visible(e):continue
    box=e.bbox();span=max(span,box[2]-box[0],box[3]-box[1]);current=(document.entity_color(e),1-e.transparency/100)
    if current!=style:flush_points();points=[];style=current
    x,y=(box[0]+box[2])/2,(box[1]+box[3])/2;ox,oy=entry['origin'];points.append(QPointF((x-ox)*entry['scale'],(oy-y)*entry['scale']))
   flush_points()
  finally:p.end()
  entry['max_span']=span

 if batch and not selected and not request.get('boq') and all(type(e) is LineEntity and e.p1.as_tuple()!=e.p2.as_tuple() and not e.transparency and document.entity_linetype(e)=='CONTINUOUS' for e in batch):
  groups=[];ox,oy=entry['origin'];scale=entry['scale']
  for e in batch:
   if not document.is_visible(e):continue
   style=[document.entity_color(e),max(1,document.layers.layers.get(e.layer,{}).get('lineweight',.25)*3.78)]
   if not groups or groups[-1]['style']!=style:groups.append(dict(style=style,segments=[]))
   groups[-1]['segments'].append([(e.p1.x-ox)*scale,(oy-e.p1.y)*scale,(e.p2.x-ox)*scale,(oy-e.p2.y)*scale])
  entry['native_lines']=groups
 return picture,overview,entry


def export_scene(document,data,request):
 global _COMMAND_CACHE_BYTES
 if request.get('regenerate'):_COMMAND_CACHE.clear();_COMMAND_CACHE_BYTES=0
 target=Path(request['image']);directory=target.with_suffix('');directory.mkdir()
 selected=request['mode']=='scene_selection';ids=set(request['selection']);entries=[];infinite=[];hits=misses=0
 metadata=data.get('metadata_fingerprint')
 if metadata is None:metadata=hashlib.sha256(pickle.dumps({k:v for k,v in document.__dict__.items() if k not in ('entities','render_revision')},protocol=4)).hexdigest()
 style=hashlib.sha256(json.dumps([metadata,request['colors'],request['font'],request['hints'],request.get('boq',False),selected,sorted(ids) if selected else []],sort_keys=True).encode()).hexdigest()
 fingerprints=data.get('fingerprints') or [hashlib.sha256(pickle.dumps(item,protocol=4)).hexdigest() for item in data['items']]
 def emit(batch,fingerprint,underlay=None,layout=None):
  nonlocal hits,misses
  global _COMMAND_CACHE_BYTES
  cache_key=style+':'+fingerprint
  if cache_key in _COMMAND_CACHE:
   value=_COMMAND_CACHE.pop(cache_key);_COMMAND_CACHE[cache_key]=value;hits+=1
  else:
   picture,overview,entry=_commands(document,batch,request,selected,underlay,layout)
   size=picture.size()+(overview.size() if overview is not None else 0)
   value=(picture,overview,entry,size);_COMMAND_CACHE[cache_key]=value;_COMMAND_CACHE_BYTES+=size;misses+=1
   while len(_COMMAND_CACHE)>1 and _COMMAND_CACHE_BYTES>_COMMAND_CACHE_BUDGET:_COMMAND_CACHE_BYTES-=_COMMAND_CACHE.popitem(last=False)[1][3]
  picture,overview,entry,size=value;entry=dict(entry);entry['cache_key']=cache_key;entry['ids']=[e.id for e in batch];entry['layers']=list(dict.fromkeys(e.layer for e in batch));entry['layer']=entry['layers'][0] if len(entry['layers'])==1 else None
  name=str(len(entries))+'.qpic'
  if not picture.save(str(directory/name)):raise ValueError('Could not save vector display list')
  entry['file']=name
  if overview is not None:
   name=str(len(entries))+'.overview.qpic'
   if not overview.save(str(directory/name)):raise ValueError('Could not save overview display list')
   entry['overview_file']=name
  entries.append(entry)
 if document.current_space!='Model':
  layout=document.layouts.get(document.current_space)
  if layout:emit([],hashlib.sha256(''.join(fingerprints).encode()).hexdigest(),layout=layout)
 else:
  if not selected:
   for underlay in document.underlays:
    if underlay.get('visible',True):emit([],hashlib.sha256(pickle.dumps(underlay,protocol=4)).hexdigest(),underlay)
  for item,fingerprint in zip(data['items'],fingerprints):
   batch=[e for e in item[4] if not selected or e.id in ids];bounded=[]
   for e in batch:
    if isinstance(e,(RayEntity,XLineEntity)):infinite.append(dict(p1=e.p1.as_tuple(),p2=e.p2.as_tuple(),ray=isinstance(e,RayEntity),color=request['colors']['ui_selection'] if selected else document.entity_color(e)))
    else:bounded.append(e)
   if bounded:emit(bounded,fingerprint)
 grip_points=[]
 if document.current_space=='Model' and selected and len(ids)==1:
  from .polyline_grips import grips
  matching=[e for e in document.entities if e.id in ids]
  if matching:
   for kind,point in grips(matching[0],document.render_revision):grip_points.append(point.as_tuple())
 result=dict(entries=entries,tree=index_tree(entries),infinite=infinite,grips=grip_points)
 target.write_text(json.dumps(result));return dict(vector_batches=len(entries),vector_cache_hits=hits,vector_cache_misses=misses,vector_cache_bytes=_COMMAND_CACHE_BYTES)


class SceneController(ProcessController):
 def __init__(self,canvas):
  super().__init__(canvas);self.scene=None;self.selection_scene=None;self.selected_ids=None;self.loading=None;self.previous_scene=None;self.picture_cache=OrderedDict();self.picture_cache_bytes=0;self.force_regeneration=False;self.delta=None
  from .index_warmup import IndexWarmer
  self.index_warmer=IndexWarmer(self)
  from .scene_capture import CaptureTask
  self.capture_task=CaptureTask(self);self.capture_task.ready.connect(self._capture_ready)
 def close(self,*args):
  if self.__dict__.get('_closing',False) or self.__dict__.get('closed',False):return
  from PyQt6 import sip
  if not sip.isdeleted(self.index_warmer):self.index_warmer.cancel()
  if not sip.isdeleted(self.capture_task):self.capture_task.cancel()
  super().close(*args)
 @pyqtSlot(object)
 def _capture_ready(self,state):
  canvas=self.canvas()
  if not self.closed and canvas is not None and canvas.__dict__.get('_persistent_capture') is state:self._wake()
 def reset(self,signature):
  if self.signature==signature:return
  self.capture_task.cancel();self.delta=None
  canvas=self.canvas()
  if canvas is not None and self.signature is not None:
   from .edit_journal import invalidate
   invalidate(canvas.document)
  self.force_regeneration=self.signature is not None and self.signature[-1]!=signature[-1]
  if self.force_regeneration:self.picture_cache.clear();self.picture_cache_bytes=0
  # Multiple revisions can arrive before a replacement scene is complete.
  # Keep the last complete scene until an atomic replacement is ready.
  self.previous_scene=(self.scene or self.previous_scene) if self.signature is not None and self.signature[0]==signature[0] else None
  self.scene=None;self.selection_scene=None;self.selected_ids=None;self.loading=None
  # Keep the native worker and its unchanged command lists across model edits.
  process=self.process;self.process=None
  super().reset(signature)
  if process is not None:
   from PyQt6 import sip
   if sip.isdeleted(process) or process.state()==process.ProcessState.NotRunning:process=None
  self.process=process
  canvas=self.canvas()
  if canvas is not None:self.index_warmer.start(canvas.document)
 def _send(self,request):
  if not hasattr(request,'regenerate'):request.regenerate=self.force_regeneration;self.force_regeneration=False
  request.mode='scene_selection' if request.mode in ('overlay','scene_selection') else 'scene'
  super()._send(request)
 def _read(self,process):
  if self.process is not process:return
  self.buffer+=bytes(process.readAllStandardOutput())
  while b'\n' in self.buffer:
   line,self.buffer=self.buffer.split(b'\n',1)
   try:
    result=json.loads(line);request=self.active
    if request is None or result.get('id')!=request.id:
     ident=result.get('id','')
     if isinstance(ident,str) and len(ident)==32 and all(c in '0123456789abcdef' for c in ident):
      old=Path(self.directory.name)/ident;shutil.rmtree(old,ignore_errors=True);old.with_suffix('.pixels').unlink(missing_ok=True)
     continue
    if result.get('error'):self._fail(result['error']);continue
    if request.signature!=self.signature:self.active=None;self._wake();continue
    manifest=json.loads(Path(request.image).read_text());manifest['pictures']=[];manifest['overviews']=[];manifest['native_paths']=[];request.stats=result['stats']
    self.loading=(request,manifest,0);self._load()
   except Exception as ex:self._fail(repr(ex))
 @pyqtSlot()
 def _load(self):
  if self.closed or self.loading is None:return
  request,manifest,i=self.loading
  if request is not self.active:self.loading=None;return
  start=time.perf_counter();directory=Path(request.image).with_suffix('')
  try:
   while i<len(manifest['entries']) and time.perf_counter()-start<.006:
    entry=manifest['entries'][i];cache_key=entry.get('cache_key',(self.model_token,entry['file']));path=directory/entry['file']
    if cache_key in self.picture_cache:
     pic,overview,size,native_paths=self.picture_cache.pop(cache_key)
    else:
     pic=QPicture()
     if not pic.load(str(path)):raise ValueError('Invalid private vector display list')
     overview=None
     if 'overview_file' in entry:
      overview=QPicture()
      if not overview.load(str(directory/entry['overview_file'])):raise ValueError('Invalid overview display list')
     native_paths=[]
     from PyQt6.QtGui import QPainterPath
     for group in entry.get('native_lines',[]):
      path_data=QPainterPath()
      for x1,y1,x2,y2 in group['segments']:path_data.moveTo(x1,y1);path_data.lineTo(x2,y2)
      pen=QPen(QColor(group['style'][0]));pen.setWidthF(group['style'][1]);pen.setCosmetic(True);pen.setCapStyle(Qt.PenCapStyle.SquareCap)
      native_paths.append((pen,path_data))
     size=pic.size()+(overview.size() if overview is not None else 0)+sum(path.elementCount()*24 for pen,path in native_paths);self.picture_cache_bytes+=size
    path.unlink()
    if 'overview_file' in entry:(directory/entry['overview_file']).unlink()
    entry.pop("native_lines",None)
    self.picture_cache[cache_key]=(pic,overview,size,native_paths)
    while len(self.picture_cache)>1 and self.picture_cache_bytes>64*1024*1024:self.picture_cache_bytes-=self.picture_cache.popitem(last=False)[1][2]
    manifest['pictures'].append(pic);manifest['overviews'].append(overview);manifest['native_paths'].append(native_paths);i+=1
   if i<len(manifest['entries']):self.loading=(request,manifest,i);QTimer.singleShot(0,self._load);return
   self.loading=None;self.active=None;directory.rmdir();Path(request.image).unlink()
   manifest['grip_polygon']=QPolygonF([QPointF(x,y) for x,y in manifest.pop('grips',[])])
   if request.mode=='scene_selection':self.selection_scene=manifest;self.selected_ids=request.selection
   else:self.scene=manifest;self.previous_scene=None
   c=self.canvas()
   if c is not None:c._persistent_worker_stats=request.stats;c._render_process_error=''
   if c is not None and request.mode=='scene':
    from .incremental_display import attach
    self.delta=attach(c,manifest,self.signature)
    import gc
    gc.collect(2)
   self._wake()
  except Exception as ex:self._fail(repr(ex))
 def selection_ids(self,canvas):
  ids=super().selection_ids(canvas)
  return tuple(k for k in ids if self.delta is None or k not in self.delta.affected)
 def paint_selection(self,canvas,painter,key):
  ids=self.selection_ids(canvas)
  if not ids:canvas._selection_complete=True;return
  if self.selected_ids==ids and self.selection_scene is not None:
   replay(canvas,painter,self.selection_scene);canvas._selection_complete=True
   points=self.selection_scene['grip_polygon']
   if points:
    transform=QTransform(canvas.zoom,0,0,-canvas.zoom,canvas.viewport().width()/2-canvas.pan_offset.x()*canvas.zoom,canvas.viewport().height()/2+canvas.pan_offset.y()*canvas.zoom)
    painter.save();pen=QPen(QColor(__import__('pycad.appearance',fromlist=['colors']).colors(canvas)['ui_grip']),6);pen.setCapStyle(Qt.PenCapStyle.SquareCap);painter.setPen(pen);painter.drawPoints(transform.map(points));painter.restore()
  else:
   canvas._selection_complete=False
   if self._state is not None:self.request(self._state,key,painter,canvas,overlay=True)


def replay(canvas,painter,scene,additions=True,world_box=None):
 a=canvas.screen_to_world(-32,-32);b=canvas.screen_to_world(canvas.viewport().width()+32,canvas.viewport().height()+32);box=(min(a.x(),b.x()),min(a.y(),b.y()),max(a.x(),b.x()),max(a.y(),b.y()))
 if world_box is not None:box=world_box
 delta=scene.get('delta')
 if delta:delta.prepare(canvas,painter)
 visible=candidates(scene['tree'],box)
 if delta:visible=sorted(set(visible)|set(delta.extra_candidates(box)))
 for i in visible:
  if delta and i in delta.patches:delta.paint_record(canvas,painter,delta.patches[i]);continue
  entry=scene['entries'][i];point=canvas.world_to_screen(*entry['origin']);factor=canvas.zoom/entry['scale'];painter.save()
  try:
   painter.translate(point);painter.scale(factor,factor)
   if scene.get('native_paths') and scene['native_paths'][i]:
    painter.setBrush(Qt.BrushStyle.NoBrush);painter.setOpacity(1)
    for pen,path in scene['native_paths'][i]:painter.setPen(pen);painter.drawPath(path)
   else:painter.drawPicture(0,0,scene['overviews'][i] if scene['overviews'][i] is not None and canvas.__dict__.get('progressive_lod',True) and entry['max_span']*canvas.zoom<1.5 else scene['pictures'][i])
  finally:painter.restore()
 for item in scene['infinite']:
  # Truly infinite construction lines need only two camera-clipped endpoints.
  x,y=item['p1'];dx,dy=item['p2'][0]-x,item['p2'][1]-y;n=math.hypot(dx,dy)
  if n<=1e-12:continue
  dx/=n;dy/=n;cx,cy=(box[0]+box[2])/2,(box[1]+box[3])/2;t=(cx-x)*dx+(cy-y)*dy;r=math.hypot(box[2]-box[0],box[3]-box[1])*2;lo=max(0,t-r) if item['ray'] else t-r;hi=t+r
  if hi<lo:continue
  painter.save();painter.setPen(QPen(QColor(item['color']),1));painter.drawLine(canvas.world_to_screen(x+dx*lo,y+dy*lo),canvas.world_to_screen(x+dx*hi,y+dy*hi));painter.restore()
 if additions and delta:delta.draw_added(canvas,painter,box)
 return len(visible)


def present(canvas,painter,scene):
 if canvas.__dict__.get('_navigation_preview') or canvas.__dict__.get('_panning'):return replay(canvas,painter,scene)
 delta=scene.get('delta')
 if delta:delta.prepare(canvas,painter)
 view=canvas.viewport();dpr=view.devicePixelRatioF()
 token=(id(scene),canvas.zoom,canvas.pan_offset.x(),canvas.pan_offset.y(),view.width(),view.height(),dpr,painter.renderHints().value,canvas.__dict__.get('progressive_lod',True),delta.base_version if delta else 0)
 frame=canvas.__dict__.get('_static_scene_frame')
 if frame is not None and frame['token']!=token:
  from .layer_display import repair
  repair(canvas,painter,scene,frame,token,delta)
 if frame is None or frame['token']!=token:
  image=QImage(math.ceil(view.width()*dpr),math.ceil(view.height()*dpr),QImage.Format.Format_ARGB32_Premultiplied)
  if image.isNull():return replay(canvas,painter,scene)
  image.setDevicePixelRatio(dpr);image.setDotsPerMeterX(round(view.logicalDpiX()/.0254));image.setDotsPerMeterY(round(view.logicalDpiY()/.0254));image.fill(0)
  target=QPainter(image);target.setRenderHints(painter.renderHints());target.setFont(painter.font())
  try:count=replay(canvas,target,scene,additions=False)
  finally:target.end()
  frame=dict(token=token,image=image,count=count);canvas._static_scene_frame=frame
  if delta:delta.damage.clear()
 painter.drawImage(0,0,frame['image'])
 if delta:
  a=canvas.screen_to_world(-32,-32);b=canvas.screen_to_world(view.width()+32,view.height()+32)
  delta.draw_added(canvas,painter,(min(a.x(),b.x()),min(a.y(),b.y()),max(a.x(),b.x()),max(a.y(),b.y())))
 return frame['count']


def _paint(canvas,painter,key):
 controller=canvas.__dict__.get('_scene_controller')
 if controller is None:controller=canvas._scene_controller=SceneController(canvas)
 sig=key[:3]+key[8:10]+key[11:]+(canvas.__dict__.get('_scene_generation',0),)
 if not (controller.scene is not None and controller.delta is not None and controller.delta.accept(canvas.document,controller.signature,sig)):
  controller.reset(sig)
 if controller.scene is None:
  state=canvas.__dict__.get('_persistent_capture')
  if state is None or state['signature']!=sig:
   from .render_snapshot import capture
   state=dict(signature=sig,items=[],iterator=capture(canvas),ready=False);canvas._persistent_capture=state
   controller.capture_task.start(state)
  if state.get('error'):controller._fail(state['error'])
  elif state['ready']:controller.request(state,key,painter,canvas)
  if controller.previous_scene is not None:present(canvas,painter,controller.previous_scene)
  from .immediate_lines import paint_pending
  paint_pending(canvas,painter)
  canvas._last_draw_kind='persistent scene preparing';return True
 canvas.__dict__.pop('_pending_line_ink',None)
 start=time.perf_counter();count=present(canvas,painter,controller.scene);controller.paint_selection(canvas,painter,key)
 if controller.delta:controller.delta.draw_selection(canvas,painter)
 canvas._last_draw_kind='persistent vector scene';canvas.persistent_scene_stats=dict(ready=True,compile_jobs=controller.jobs,visible_batches=count,total_batches=len(controller.scene['entries']),last_present_ms=(time.perf_counter()-start)*1000,delta_sequence=controller.delta.cursor if controller.delta else None,local_patch_batches=len(controller.delta.patches) if controller.delta else 0,added_batches=len(controller.delta.added) if controller.delta else 0,fast_drafting_blocked=controller.delta.state.blocked if controller.delta else True,layer_batches=len({layer for entry in controller.scene['entries'] for layer in entry.get('layers',[])}),dirty_region_updates=canvas.__dict__.get('_dirty_region_updates',0))
 return True


def paint(canvas,painter,key):
 # A paint can be nested by Qt/platform callbacks while capture yields. Guard
 # the whole transaction so neither the generator nor its state is reentered.
 if canvas.__dict__.get('_persistent_paint_active',False):return True
 canvas._persistent_paint_active=True
 try:return _paint(canvas,painter,key)
 except Exception as error:
  controller=canvas.__dict__.get('_scene_controller')
  from PyQt6 import sip
  if not sip.isdeleted(canvas):
   if controller is not None and not sip.isdeleted(controller):controller._fail(repr(error))
   else:canvas._render_process_error=repr(error)
  return True
 finally:canvas._persistent_paint_active=False


def regenerate(canvas):
 canvas._scene_generation=canvas.__dict__.get('_scene_generation',0)+1
 canvas.__dict__.pop('_retained_scene',None);canvas.viewport().update()
