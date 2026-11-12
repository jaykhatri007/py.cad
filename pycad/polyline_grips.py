"""In-canvas polyline vertex/midpoint editing, staged on an independent candidate."""
import copy,math,weakref
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QUndoCommand,QPen,QColor
from PyQt6.QtWidgets import QMenu,QInputDialog
from .geometry import Point,PolylineEntity
from .tools import Tool
from .native_io import entity_to_dict,entity_from_dict
from .precision import segment_point,arc_data
from .precision_edit import guard


_GRIPS=weakref.WeakKeyDictionary()

def grips(entity,revision=None):
 if not isinstance(entity,PolylineEntity):return entity.grip_points()
 key=(revision,id(entity.points),len(entity.points),id(entity.bulges),entity.closed)
 if revision is not None and entity in _GRIPS and _GRIPS[entity][0]==key:return _GRIPS[entity][1]
 count=len(entity.points) if entity.closed else len(entity.points)-1
 result=[(f'pt{i}',p) for i,p in enumerate(entity.points)]+[(f'mid{i}',segment_point(entity.points[i],entity.points[(i+1)%len(entity.points)],entity.bulges[i],.5)) for i in range(count)]
 if revision is not None:_GRIPS[entity]=(key,result)
 return result


def hit(canvas,point):
 if len(canvas.selected_entities)!=1:return None
 entity=canvas.selected_entities[0]
 if not isinstance(entity,PolylineEntity) or not canvas.document.is_editable(entity):return None
 tolerance=max(7,canvas.snap_radius_px)/canvas.zoom;best=None
 for kind,p in grips(entity,canvas.document.render_revision):
  distance=point.distance_to(p)
  if distance<tolerance:best=(entity,kind,p);tolerance=distance
 return best


def clone(entity):
 result=PolylineEntity(copy.deepcopy(entity.points),entity.closed,bulges=entity.bulges,width=entity.width,**entity.style_kwargs());result.id=entity.id;return result


def validate(entity):
 if len(entity.points)<2:raise ValueError('Too few polyline vertices')
 for p in entity.points:
  if not math.isfinite(p.x) or not math.isfinite(p.y):raise ValueError('Use finite vertex coordinates')
 from .precision import validate_bulges
 validate_bulges(entity.points,entity.bulges,entity.closed)
 for value in entity.bbox():
  if not math.isfinite(value):raise ValueError('Invalid polyline bounds')
 return entity


def change(source,operation,index=0,point=None,value=None):
 e=clone(source);n=len(e.points);segments=n if e.closed else n-1
 if not 0<=index<n:raise ValueError('Choose an existing vertex or segment')
 if operation in ('insert','arc','straighten','segment') and index>=segments:raise ValueError('No outgoing segment at the final open vertex')
 if operation=='vertex':e.points[index]=Point(point.x,point.y)
 elif operation=='segment':
  base=segment_point(e.points[index],e.points[(index+1)%n],e.bulges[index],.5);dx,dy=point.x-base.x,point.y-base.y
  for i in (index,(index+1)%n):e.points[i]=Point(e.points[i].x+dx,e.points[i].y+dy)
 elif operation=='insert':
  a,b=e.points[index],e.points[(index+1)%n];bulge=e.bulges[index];mid=segment_point(a,b,bulge,.5);half=math.tan(math.atan(bulge)/2)
  e.points.insert(index+1,mid);e.bulges[index]=half;e.bulges.insert(index+1,half)
 elif operation=='delete':
  if n<=2:raise ValueError('Too few vertices would remain')
  previous=(index-1)%n;left=e.closed or index>0;right=e.closed or index<n-1;merged=0.
  if left and right and (e.bulges[previous] or e.bulges[index]):
   a=arc_data(e.points[previous],e.points[index],e.bulges[previous]);b=arc_data(e.points[index],e.points[(index+1)%n],e.bulges[index])
   if a is None or b is None or a[3]*b[3]<=0 or a[0].distance_to(b[0])>max(a[1],b[1],1)*1e-7 or abs(a[1]-b[1])>max(a[1],b[1],1)*1e-7 or abs(a[3]+b[3])>=math.tau-1e-8:raise ValueError('Straighten the adjoining arc segments before deleting this vertex; matching circular arcs can be merged exactly')
   merged=math.tan((a[3]+b[3])/4)
  if left:e.bulges[previous]=merged
  e.points.pop(index);e.bulges.pop(index)
  if not e.closed:e.bulges[-1]=0.
 elif operation=='straighten':e.bulges[index]=0.
 elif operation=='arc':
  if value is not None:
   if not math.isfinite(value) or not -359<=value<=359:raise ValueError('Use an arc angle between -359 and 359 degrees')
   e.bulges[index]=math.tan(math.radians(value)/4)
  else:
   a,b=e.points[index],e.points[(index+1)%n];dx,dy=b.x-a.x,b.y-a.y;length2=dx*dx+dy*dy
   if length2<1e-18:raise ValueError('An arc needs distinct endpoints')
   e.bulges[index]=2*((point.x-(a.x+b.x)/2)*dy-(point.y-(a.y+b.y)/2)*dx)/length2
 elif operation=='reverse':
  old=e.bulges[:];e.points.reverse();e.bulges=[-old[(n-2-i)%n] if e.closed or i<n-1 else 0. for i in range(n)]
 elif operation=='close':
  if e.points[0].distance_to(e.points[-1])<1e-10:e.points.pop();e.bulges.pop()
  e.closed=True
 elif operation=='open':e.closed=False;e.bulges[-1]=0.
 else:raise ValueError('Unknown polyline operation')
 return validate(e)


def commit(mw,source,candidate,label):
 doc=mw.document;guard(doc,[source]);validate(candidate)
 if doc.find_by_id(source.id) is not source:raise ValueError('Polyline changed; select it again')
 if entity_to_dict(source)['data']==entity_to_dict(candidate)['data']:return False
 canvas=weakref.ref(mw.canvas)
 class Edit(QUndoCommand):
  def __init__(self):super().__init__(label)
  def assign(self,entity):
   index=next((i for i,e in enumerate(doc.entities) if e.id==source.id),None)
   if index is None:raise ValueError('Edited polyline is missing')
   doc.entities[index]=entity;doc.spatial_index.invalidate();doc.dirty=True
   view=canvas()
   if view is not None and view.document is doc:view.selected_entities=[entity if e.id==source.id else e for e in view.selected_entities]
  def redo(self):self.assign(candidate)
  def undo(self):self.assign(source)
 doc.undo_stack.push(Edit());mw.refresh_document_ui();mw.refresh_selection_ui();return True


class Drag(Tool):
 name='POLYGRIP'
 def __init__(self,mw,entity,kind,operation=None):
  super().__init__(mw);guard(self.document,[entity]);self.source=entity;self.index=int(kind[3:] if kind.startswith('mid') else kind[2:]);self.operation=operation or ('segment' if kind.startswith('mid') else 'vertex');self.candidate=None;self.error='';self.revision=self.document.render_revision
  base=dict(grips(entity))[kind];self.points=[Point(base.x,base.y)]
 def status_prompt(self):return 'POLYLINE '+self.operation.upper()+': drag/click point or enter x,y / @dx,dy; Esc cancels'+(' · '+self.error if self.error else '')
 def on_move(self,x,y,kind):
  try:self.candidate=change(self.source,self.operation,self.index,Point(x,y));self.error=''
  except (ValueError,OverflowError) as ex:self.candidate=None;self.error=str(ex)
 def on_click(self,x,y,kind,button):
  if button==Qt.MouseButton.LeftButton.value:self.on_move(x,y,kind);self.finish_drag()
 def on_text_input(self,text):
  point=self.parse_point(text,self.points[0])
  if point is None:raise ValueError('Enter x,y or @dx,dy')
  self.on_click(point.x,point.y,'',Qt.MouseButton.LeftButton.value)
 def finish_drag(self):
  if self.mw.document is not self.document or self.document.render_revision!=self.revision:raise ValueError('Drawing changed; restart this grip edit')
  if self.error:raise ValueError(self.error)
  if self.candidate is not None:commit(self.mw,self.source,self.candidate,'Polyline '+self.operation)
  self.finish()
 def draw_preview(self,painter,canvas):
  if self.candidate is None:return
  painter.save();painter.setOpacity(.9);painter.setPen(QPen(QColor('#65d9b2'),1.8,Qt.PenStyle.DashLine))
  try:canvas._draw_entity(painter,self.candidate)
  finally:painter.restore()


def start(mw,entity,kind,operation=None):
 from .editing_ui import activate
 tool=Drag(mw,entity,kind,operation);activate(mw,tool);return tool


def begin_if_hit(mw,point):
 found=hit(mw.canvas,point)
 if not found:return False
 entity,kind,unused=found
 if kind.startswith('pt'):
  try:guard(mw.document,[entity])
  except ValueError:return False  # Retain the established associative vertex tool.
 start(mw,entity,kind);return True


def context(mw,point):
 found=hit(mw.canvas,point)
 if not found:return None
 entity,kind,base=found;index=int(kind[3:] if kind.startswith('mid') else kind[2:]);mid=kind.startswith('mid');count=len(entity.points) if entity.closed else len(entity.points)-1;menu=QMenu(mw.canvas);menu.setTitle('Polyline grip');menu.setObjectName('polyline_grip_menu')
 from .feature_helpers import safe_action
 def action(label,callback,enabled=True):a=menu.addAction(label,safe_action(mw,callback));a.setEnabled(enabled);return a
 def edit(operation,where=index,value=None):return commit(mw,entity,change(entity,operation,where,value=value),'Polyline '+operation)
 action('Stretch segment' if mid else 'Stretch vertex',lambda:start(mw,entity,kind))
 if not mid:
  def coordinates():
   text,ok=QInputDialog.getText(mw,'Vertex coordinates','Absolute x,y or relative @dx,dy',text=f'{base.x:g},{base.y:g}')
   if ok:
    point=Tool.parse_point(text,base)
    if point is None:raise ValueError('Enter finite x,y coordinates')
    commit(mw,entity,change(entity,'vertex',index,point),'Set polyline vertex coordinates')
  action('Set vertex coordinates…',coordinates);action('Delete vertex',lambda:edit('delete'))
  action('Insert vertex before',lambda:edit('insert',(index-1)%len(entity.points)),entity.closed or index>0)
 action('Insert vertex at midpoint' if mid else 'Insert vertex after',lambda:edit('insert'),index<count)
 action('Convert / reshape segment to arc',lambda:start(mw,entity,f'mid{index}','arc'),index<count)
 def angle():
  value,ok=QInputDialog.getDouble(mw,'Arc segment','Signed included angle (degrees)',math.degrees(4*math.atan(entity.bulges[index])),-359,359,6)
  if ok:edit('arc',value=value)
 action('Set segment arc angle…',angle,index<count)
 action('Straighten segment',lambda:edit('straighten'),index<count and bool(entity.bulges[index]));menu.addSeparator()
 action('Reverse polyline',lambda:edit('reverse'));action('Open polyline' if entity.closed else 'Close polyline',lambda:edit('open' if entity.closed else 'close'))
 menu.addSeparator();action('Advanced multi-vertex editor…',lambda:mw.run_ribbon_command('ADVGRIPS'))
 return menu
