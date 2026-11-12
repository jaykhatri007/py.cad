"""Reviewed precision editing and drawing-health reports; originals stay untouched."""
import copy,json,math,statistics
from .geometry import Point,LineEntity,PolylineEntity,ArcEntity,HatchEntity
from .native_io import document_to_dict,document_from_dict,entity_to_dict,entity_from_dict
from .efficiency import fingerprint

def filter_entities(doc,criteria,source=None):
 allowed={'kind','layer','color','block','linetype','text','min_length','max_length'}
 if not isinstance(criteria,dict) or set(criteria)-allowed:raise ValueError('Unknown selection filter')
 from .validation import finite
 for key in ('min_length','max_length'):
  if criteria.get(key) is not None:
   finite(criteria[key],'Length filter')
   if criteria[key]<0:raise ValueError('Length must not be negative')
 if criteria.get('min_length') is not None and criteria.get('max_length') is not None and criteria['min_length']>criteria['max_length']:raise ValueError('Minimum exceeds maximum length')
 result=[];editable={e.id for e in doc.editable_entities()}
 for e in (doc.entities if source is None else source):
  if e.id not in editable:continue
  if any(criteria.get(k) not in (None,'','Any') and str(getattr(e,attr,'')).casefold()!=str(criteria[k]).casefold() for k,attr in [('kind','kind'),('layer','layer'),('color','color'),('block','block_name'),('linetype','linetype')]):continue
  if criteria.get('text') and criteria['text'].casefold() not in getattr(e,'text','').casefold():continue
  if criteria.get('min_length') is not None or criteria.get('max_length') is not None:
   if e.kind=='LINE':length=e.p1.distance_to(e.p2)
   elif e.kind=='ARC':length=e.radius*math.radians((e.end_angle-e.start_angle)%360)
   elif isinstance(e,PolylineEntity):
    from .precision import polyline_measure
    length=polyline_measure(e)[0]
   elif e.kind=='CIRCLE':length=2*math.pi*e.radius
   else:continue
   if criteria.get('min_length') is not None and length<criteria['min_length']:continue
   if criteria.get('max_length') is not None and length>criteria['max_length']:continue
  result.append(e)
 return result

def select(mw,matches,mode='Replace'):
 old=mw.canvas.selected_entities;ids={e.id for e in matches};current={e.id for e in old}
 if mode=='Replace':selected=ids
 elif mode=='Add':selected=current|ids
 elif mode=='Subtract':selected=current-ids
 elif mode=='Intersect':selected=current&ids
 else:raise ValueError('Choose Replace, Add, Subtract or Intersect')
 mw.canvas.selected_entities=[e for e in mw.document.editable_entities() if e.id in selected];mw.refresh_selection_ui();mw.canvas.viewport().update()
 return mw.canvas.selected_entities

def plan(doc,replacements,remove=(),label='Precision edit'):
 ids=set(replacements)|set(remove)
 if not ids or any(doc.find_by_id(k) is None or not doc.is_editable(doc.find_by_id(k)) for k in ids):raise ValueError('Choose editable model objects')
 value=document_to_dict(doc);value['entities']=[entity_to_dict(replacements[e.id]) if e.id in replacements else entity_to_dict(e) for e in doc.entities if e.id not in remove]
 candidate=document_from_dict(value)
 return dict(fingerprint=fingerprint(doc),targets=sorted(ids),records=[entity_to_dict(e) for e in candidate.entities if e.id in replacements],remove=list(remove),label=label)

def proposed(doc,proposal):
 if fingerprint(doc)!=proposal['fingerprint']:raise ValueError('Drawing changed; build the preview again')
 v=document_to_dict(doc);records={r['data']['id']:r for r in proposal['records']};remove=set(proposal['remove']);v['entities']=[copy.deepcopy(records.get(r['data']['id'],r)) for r in v['entities'] if r['data']['id'] not in remove];v['entities'].extend(copy.deepcopy(proposal.get('added',[])));return document_from_dict(v)

def apply(doc,proposal):
 candidate=proposed(doc,proposal)
 if any(doc.find_by_id(k) is None or not doc.is_editable(doc.find_by_id(k)) for k in proposal['targets']):raise ValueError('A target is no longer editable')
 from PyQt6.QtGui import QUndoCommand
 class Edit(QUndoCommand):
  def __init__(self):super().__init__(proposal['label']);self.before=list(doc.entities);changed={e.id:e for e in candidate.entities};self.after=[changed[e.id] if e.id in proposal['targets'] else e for e in doc.entities if e.id not in proposal['remove']]+[e for e in candidate.entities if e.id not in {q.id for q in doc.entities}]
  def assign(self,value):doc.entities=list(value);doc.spatial_index.invalidate();doc.dirty=True
  def redo(self):self.assign(self.after)
  def undo(self):self.assign(self.before)
 doc.undo_stack.push(Edit())

def vertex_plan(doc,vertices,dx,dy):
 from .validation import finite
 finite(dx,'Offset x');finite(dy,'Offset y');replacements={}
 if not vertices:raise ValueError('Check at least one vertex')
 for key,kinds in vertices.items():
  source=doc.find_by_id(key)
  if source is None or source.kind not in ('LINE','LWPOLYLINE','RECTANGLE'):raise ValueError('Vertex stretch supports lines and polylines')
  e=entity_from_dict(entity_to_dict(source));grips=dict(e.grip_points())
  for kind in set(kinds):
   if kind not in grips:raise ValueError('Vertex no longer exists')
   grips[kind].x+=dx;grips[kind].y+=dy
  replacements[key]=e
 return plan(doc,replacements,label='Stretch checked vertices')

def segment_plan(doc,entity,index,operation,value=0.):
 from .validation import finite
 finite(value,'Segment value');e=entity_from_dict(entity_to_dict(entity))
 if not isinstance(e,PolylineEntity):raise ValueError('Select one polyline or rectangle')
 n=len(e.points);count=n if e.closed else n-1
 if type(index) is not int or not 0<=index<count:raise ValueError('Choose a segment index')
 # Edited rectangles become general polylines: their four-corner constructor cannot store an inserted vertex.
 if e.kind=='RECTANGLE':e=PolylineEntity(copy.deepcopy(e.points),e.closed,bulges=list(e.bulges),width=e.width,**e.style_kwargs());e.id=entity.id
 if operation=='Insert midpoint':
  b=e.bulges[index];a,c=e.points[index],e.points[(index+1)%n]
  if abs(b)>1e-12:
   # Half-angle bulge and exact circular midpoint; preserves the same arc.
   midpoint=Point((a.x+c.x)/2+(c.y-a.y)*b/2,(a.y+c.y)/2-(c.x-a.x)*b/2);half=math.tan(math.atan(b)/2)
  else:midpoint=Point((a.x+c.x)/2,(a.y+c.y)/2);half=0.
  e.points.insert(index+1,midpoint);e.bulges[index]=half;e.bulges.insert(index+1,half)
 elif operation=='Remove start vertex':
  if n<=(3 if e.closed else 2):raise ValueError('Too few vertices would remain')
  previous=(index-1)%n
  if abs(e.bulges[index])>1e-12 or ((index>0 or e.closed) and abs(e.bulges[previous])>1e-12):raise ValueError('Straighten adjoining arcs before removing this vertex')
  e.points.pop(index);e.bulges.pop(index)
 elif operation=='Straighten':e.bulges[index]=0.
 elif operation=='Arc angle':
  if not -359<=value<=359:raise ValueError('Use a signed included angle from -359 to 359 degrees')
  e.bulges[index]=math.tan(math.radians(value)/4)
 else:raise ValueError('Unknown segment operation')
 return plan(doc,{e.id:e},label=operation)

def arc_through(entity,through):
 if not isinstance(entity,ArcEntity):raise ValueError('Select one arc')
 a,b=entity.endpoints();c=through
 from .validation import finite
 finite(c.x,'Arc point x');finite(c.y,'Arc point y')
 # Translate to a local origin to avoid cancellation with survey coordinates.
 bx,by,cx,cy=b.x-a.x,b.y-a.y,c.x-a.x,c.y-a.y;det=2*(bx*cy-by*cx)
 if abs(det)<=1e-10*max(1.,math.hypot(bx,by)*math.hypot(cx,cy)):raise ValueError('Arc point is collinear with the endpoints')
 b2,c2=bx*bx+by*by,cx*cx+cy*cy;x=(b2*cy-c2*by)/det;y=(bx*c2-cx*b2)/det;center=Point(a.x+x,a.y+y);angle=lambda p:math.degrees(math.atan2(p.y-center.y,p.x-center.x))%360
 start,end,middle=angle(a),angle(b),angle(c)
 if (middle-start)%360>(end-start)%360:start,end=end,start
 e=entity_from_dict(entity_to_dict(entity));e.center=center;e.radius=center.distance_to(a);e.start_angle=start;e.end_angle=end
 return e

def arc_plan(doc,entity,through):return plan(doc,{entity.id:arc_through(entity,through)},label='Reshape arc through point')

def simple_polygon(points):
 # Adjacent edges are skipped by the spatial crossing test; reject backtracking explicitly.
 for a,b,c in zip(points[-1:]+points[:-1],points,points[1:]+points[:1]):
  ux,uy=b.x-a.x,b.y-a.y;vx,vy=c.x-b.x,c.y-b.y
  if abs(ux*vy-uy*vx)<=1e-12*max(1.,math.hypot(ux,uy)*math.hypot(vx,vy)) and ux*vx+uy*vy<0:raise ValueError('Adjacent boundary segments overlap/backtrack')
 from .takeoff_geometry import hatch_area
 return hatch_area(HatchEntity(copy.deepcopy(points),pattern='SOLID'))

def boundary_plan(doc,items,tolerance=.01):
 from .validation import finite
 from .precision_edit import guard
 finite(tolerance,'Gap tolerance',True);guard(doc,items)
 if len(items)==1 and isinstance(items[0],PolylineEntity):
  source=items[0]
  if any(abs(b)>1e-12 for b in source.bulges):raise ValueError('Repair supports straight segments; use arc/segment tools for curved boundaries')
  points=copy.deepcopy(source.points);clean=[]
  for pt in points:
   if not clean or pt.distance_to(clean[-1])>tolerance:clean.append(pt)
  if len(clean)>2 and clean[-1].distance_to(clean[0])<=tolerance:clean.pop()
  elif not source.closed:raise ValueError('End gap exceeds tolerance; inspect/extend it explicitly')
  if len(clean)<3 or simple_polygon(clean)<=1e-12:raise ValueError('No simple closed area remains')
  e=PolylineEntity(clean,True,width=source.width,**source.style_kwargs());e.id=source.id
  return plan(doc,{e.id:e},label='Repair closed boundary')
 if any(not isinstance(e,LineEntity) for e in items):raise ValueError('Choose a straight polyline or a closed chain of lines')
 if len(items)>2000:raise ValueError('Use a smaller selected chain for detailed boundary repair')
 # Cluster endpoints conservatively: no transitive chain may bridge the tolerance.
 nodes=[];members=[];edges=[];duplicates=[]
 def node(p):
  hits=[i for i,group in enumerate(members) if all(p.distance_to(q)<=tolerance for q in group)]
  if len(hits)>1:raise ValueError('Ambiguous endpoint clusters; use a smaller tolerance')
  if hits:i=hits[0];members[i].append(p);nodes[i]=Point(sum(q.x for q in members[i])/len(members[i]),sum(q.y for q in members[i])/len(members[i]));return i
  nodes.append(copy.deepcopy(p));members.append([p]);return len(nodes)-1
 styles={json.dumps(e.style_kwargs(),sort_keys=True) for e in items}
 if len(styles)!=1:raise ValueError('Boundary lines must share all drawing styles')
 for e in items:
  if e.p1.distance_to(e.p2)<=1e-12:duplicates.append(e.id);continue
  a,b=node(e.p1),node(e.p2)
  if a==b:raise ValueError('Tolerance collapses a short segment; choose a smaller tolerance')
  if {a,b} in [{x,y} for x,y in edges]:duplicates.append(e.id)
  else:edges.append((a,b))
 if len(edges)<3:raise ValueError('Choose a closed chain with at least three segments')
 neighbors={i:[] for i in range(len(nodes))}
 for a,b in edges:neighbors[a].append(b);neighbors[b].append(a)
 if any(len(v)!=2 for v in neighbors.values()):raise ValueError('Gaps, branches or overlaps remain; no unambiguous closed boundary')
 order=[0];previous=None;current=0
 while True:
  nxt=next(v for v in neighbors[current] if v!=previous)
  if nxt==0:break
  if nxt in order:raise ValueError('Disconnected or ambiguous chain')
  order.append(nxt);previous,current=current,nxt
 if len(order)!=len(nodes):raise ValueError('Multiple separate loops: repair them separately')
 points=[nodes[i] for i in order]
 if simple_polygon(points)<=1e-12:raise ValueError('Boundary must enclose a simple nonzero area')
 first=items[0];e=PolylineEntity(points,True,**first.style_kwargs());e.id=first.id
 proposal=plan(doc,{e.id:e},[q.id for q in items[1:]],'Repair selected boundary');proposal['note']=f'{len(items)} lines → one closed polyline; {len(duplicates)} duplicate/zero segments removed; endpoint movement limited by tolerance.';return proposal

def health(doc,distant=1e6):
 from .validation import finite,validate_payload
 from .efficiency import cleanup_plan
 finite(distant,'Distant-object threshold',True);rows=[];boxes=[]
 def add(code,message,ids=(),severity='Warning'):rows.append(dict(code=code,message=message,ids=list(ids),severity=severity))
 try:validate_payload(document_to_dict(doc))
 except (ValueError,TypeError,OverflowError) as ex:add('INVALID_DATA',str(ex),severity='Error')
 for e in doc.entities:
  try:
   box=e.bbox()
   if len(box)!=4 or not all(math.isfinite(v) for v in box):raise ValueError('Invalid bounds')
   if e.kind not in ('RAY','XLINE'):boxes.append((e.id,(box[0]+box[2])/2,(box[1]+box[3])/2))
   if e.kind=='LINE' and e.p1.distance_to(e.p2)<=1e-12:add('ZERO_LENGTH','Zero-length line',[e.id])
   if isinstance(e,PolylineEntity) and e.closed:
    if len(e.points)>2000:add('DETAIL_SKIPPED','Detailed boundary check skipped above 2,000 vertices; inspect a selected region',[e.id],'Info')
    elif not any(abs(b)>1e-12 for b in e.bulges):
     try:
      if simple_polygon(e.points)<=1e-12:add('ZERO_AREA','Closed polyline encloses no area',[e.id])
     except ValueError as ex:add('BOUNDARY',str(ex),[e.id])
   for key in ('source_line_id','source_entity_id'):
    source=getattr(e,key,None)
    if source and doc.find_by_id(source) is None:add('MISSING_ASSOCIATION','Missing source '+source,[e.id])
  except (ValueError,TypeError,OverflowError,AttributeError) as ex:add('GEOMETRY',str(ex),[e.id],'Error')
 if boxes:
  x=statistics.median(v[1] for v in boxes);y=statistics.median(v[2] for v in boxes)
  for key,a,b in boxes:
   if math.hypot(a-x,b-y)>distant:add('DISTANT',f'Object center is more than {distant:g} drawing units from median center',[key])
 try:
  for r in cleanup_plan(doc)['rows']:add('CLEANUP',r['kind']+': '+r['reason']+' '+r['name'],[r['name']] if r['kind']=='Object' else (), 'Info')
 except ValueError as ex:add('CLEANUP',str(ex),severity='Error')
 return dict(rows=rows,objects=len(doc.entities),distant_threshold=distant,note='Read-only diagnosis. Distant geometry may be intentional survey data. Detailed boundary repair is reviewed separately.')
