"""Staged drafting operations, searchable model values and data-only templates."""
import copy,math,re
from types import SimpleNamespace
from pathlib import Path
from .geometry import Point,LineEntity,ArcEntity,CircleEntity,PolylineEntity,HatchEntity
from .native_io import document_to_dict,document_from_dict,entity_to_dict,entity_from_dict
from . import editing
from .precision_edit import guard
from .document_lifecycle import dispose_document


def difference(doc,candidate,label):
 before={e.id:entity_to_dict(e) for e in doc.entities};after={e.id:entity_to_dict(e) for e in candidate.entities}
 targets={k for k,v in before.items() if after.get(k)!=v}
 if not targets and set(after)==set(before):raise ValueError('No changes were produced')
 if any(not doc.is_editable(doc.find_by_id(k)) for k in targets):raise ValueError('A changed object is locked or hidden')
 # Validate the entire candidate, including all cross-object references.
 check=document_from_dict(document_to_dict(candidate));dispose_document(check)
 return dict(fingerprint=editing.fingerprint(doc),targets=sorted(targets),records=[v for k,v in after.items() if k in targets],remove=sorted(set(before)-set(after)),added=[v for k,v in after.items() if k not in before],label=label)


def polyline_plan(doc,items,operation,value=0.01):
 guard(doc,items)
 if operation=='Join':
  from .precision_edit import join
  candidate=document_from_dict(document_to_dict(doc))
  try:
   join(candidate,[candidate.find_by_id(e.id) for e in items],value)
   return difference(doc,candidate,'Join polylines')
  finally:dispose_document(candidate)
 replacements={}
 for source in items:
  if not isinstance(source,PolylineEntity):raise ValueError('This operation requires polylines; Join also accepts lines/arcs')
  e=PolylineEntity(copy.deepcopy(source.points),source.closed,bulges=list(source.bulges),width=source.width,**source.style_kwargs());e.id=source.id
  if operation=='Close':
   if len(e.points)<3:raise ValueError('At least three vertices are required to close')
   if e.points[0].distance_to(e.points[-1])<1e-10:
    e.points.pop();e.bulges.pop()
   if len(e.points)<3:raise ValueError('At least three distinct vertices are required')
   e.closed=True
  elif operation=='Open':e.closed=False;e.bulges[-1]=0.
  elif operation=='Reverse':
   n=len(e.points);old=e.bulges[:];e.points.reverse();e.bulges=[-old[(n-2-i)%n] if e.closed or i<n-1 else 0. for i in range(n)]
  elif operation=='Uniform width':
   if type(value) not in (int,float) or not math.isfinite(value) or value<0:raise ValueError('Width must be finite and nonnegative')
   e.width=float(value)
  elif operation=='Simplify':
   if not math.isfinite(value) or value<=0:raise ValueError('Use a positive simplification tolerance')
   # Remove only straight, forward-going nearly collinear vertices. Arc segments are untouched.
   again=True;spans=[[p] for p in e.points]
   from .geom_ops import point_segment_distance
   while again:
    again=False
    for i in range(len(e.points)):
     n=len(e.points)
     if n<=(3 if e.closed else 2):break
     if not e.closed and i in (0,n-1):continue
     a,b,c=e.points[(i-1)%n],e.points[i],e.points[(i+1)%n]
     if abs(e.bulges[(i-1)%n])+abs(e.bulges[i])>1e-12:continue
     if (b.x-a.x)*(c.x-b.x)+(b.y-a.y)*(c.y-b.y)<0:continue
     combined=spans[(i-1)%n]+spans[i]
     if all(point_segment_distance(p,a,c)<=value for p in combined):
      spans[(i-1)%n]=combined;spans.pop(i);e.points.pop(i);e.bulges.pop(i);again=True;break
  else:raise ValueError('Unknown polyline operation')
  replacements[e.id]=e
 return editing.plan(doc,replacements,label='Polyline '+operation)


def trim_plan(doc,cutters,hits,extend=False):
 from .tools import TrimTool,ExtendTool
 if not cutters:raise ValueError('Select one or more cutting edges first')
 if any(not isinstance(e,(LineEntity,CircleEntity,ArcEntity,PolylineEntity)) for e in cutters):raise ValueError('Cutting edges must be lines, circles, arcs or polylines')
 items=[doc.find_by_id(key) for key,point in hits]
 if any(e is None for e in items):raise ValueError('A target no longer exists')
 guard(doc,items)
 if {e.id for e in items}&{e.id for e in cutters}:raise ValueError('A cutting edge cannot also be a target')
 candidate=document_from_dict(document_to_dict(doc))
 try:
  tool=(ExtendTool if extend else TrimTool)(SimpleNamespace(document=candidate))
  from .precision import polyline_parts
  tool.boundaries=[part for e in cutters for part in (polyline_parts(e) if isinstance(e,PolylineEntity) else [e])]
  for key,pt in hits:
   e=candidate.find_by_id(key)
   if e is None:continue
   previous={q.id for q in candidate.entities}
   if isinstance(e,LineEntity):getattr(tool,'_extend_line' if extend else '_trim_line')(e,pt)
   elif isinstance(e,ArcEntity):getattr(tool,'_extend_arc' if extend else '_trim_arc')(e,pt)
   elif isinstance(e,CircleEntity) and not extend:tool._trim_circle(e,pt)
   else:raise ValueError('Reviewed trim supports line/arc/circle targets; extend supports lines/arcs')
   for piece in candidate.entities:
    if piece.id not in previous:
     for key,value in e.style_kwargs().items():setattr(piece,key,copy.deepcopy(value))
  return difference(doc,candidate,'Extend to cutting edges' if extend else 'Trim to cutting edges')
 finally:dispose_document(candidate)


def fence_hits(doc,cutters,points,extend=False):
 from .geom_ops import line_line_intersection
 excluded={e.id for e in cutters};result=[]
 for e in doc.editable_entities():
  if e.id in excluded or not isinstance(e,(LineEntity,ArcEntity,CircleEntity)) or extend and isinstance(e,CircleEntity):continue
  # Sampling identifies targets; the trim/extend operation itself uses exact intersections.
  if isinstance(e,LineEntity):samples=[e.p1,e.p2]
  elif isinstance(e,ArcEntity):
   sweep=(e.end_angle-e.start_angle)%360;samples=[Point(e.center.x+e.radius*math.cos(math.radians(e.start_angle+sweep*i/180)),e.center.y+e.radius*math.sin(math.radians(e.start_angle+sweep*i/180))) for i in range(181)]
  else:samples=[Point(e.center.x+e.radius*math.cos(math.tau*i/360),e.center.y+e.radius*math.sin(math.tau*i/360)) for i in range(361)]
  hit=next((p for a,b in zip(points,points[1:]) for c,d in zip(samples,samples[1:]) if (p:=line_line_intersection(a,b,c,d,segment_only=True)) is not None),None)
  if hit is not None:result.append((e.id,hit))
 if not result:raise ValueError('Fence did not cross any supported target objects')
 return result


def hatch_boundaries_plan(doc,hatches):
 if not hatches or any(not isinstance(h,HatchEntity) or not doc.is_editable(h) for h in hatches):raise ValueError('Select editable hatches')
 candidate=document_from_dict(document_to_dict(doc))
 try:
  for h in hatches:
   for loop in [h.boundary,*h.holes]:candidate.entities.append(PolylineEntity(copy.deepcopy(loop),closed=True,**h.style_kwargs()))
  proposal=difference(doc,candidate,'Recreate hatch outlines');proposal['note']='Creates independent closed polylines for every stored outer/island loop. Original hatch and associations remain intact.';return proposal
 finally:dispose_document(candidate)


def hatch_settings_plan(doc,hatches,values):
 from .hatch_ui import OPTIONS
 if not hatches or any(not isinstance(h,HatchEntity) for h in hatches):raise ValueError('Select one or more hatches')
 if set(values)-set(OPTIONS):raise ValueError('Unknown hatch settings')
 replacements={}
 for h in hatches:
  e=entity_from_dict(entity_to_dict(h))
  for key,value in values.items():setattr(e,key,copy.deepcopy(value))
  replacements[h.id]=e
 return editing.plan(doc,replacements,label='Update selected hatch settings')


def gaps(items,tolerance):
 if not math.isfinite(tolerance) or tolerance<=0:raise ValueError('Use a positive gap tolerance')
 points=[]
 for e in items:
  if isinstance(e,LineEntity):points.extend((e.id,p) for p in (e.p1,e.p2))
  elif isinstance(e,PolylineEntity) and not e.closed:points.extend((e.id,p) for p in (e.points[0],e.points[-1]))
 cells={};rows=[]
 for key,p in points:
  cell=(math.floor(p.x/tolerance),math.floor(p.y/tolerance))
  for dx in (-1,0,1):
   for dy in (-1,0,1):
    for other,q in cells.get((cell[0]+dx,cell[1]+dy),[]):
     distance=p.distance_to(q)
     if 1e-10<distance<=tolerance:rows.append(dict(ids=[other,key],distance=distance,point=[(p.x+q.x)/2,(p.y+q.y)/2]))
  cells.setdefault(cell,[]).append((key,p))
 return rows


def search(doc,query,fields=('Text','Attributes','Layer','ID'),case=False,whole=False):
 if not isinstance(query,str) or not query:raise ValueError('Enter search text')
 pattern=re.compile(('(?<!\\w)'+re.escape(query)+'(?!\\w)') if whole else re.escape(query),0 if case else re.IGNORECASE);rows=[]
 for e in doc.entities:
  values=[]
  if 'Text' in fields and e.kind=='TEXT':values.append(('Text',e.text))
  if 'Attributes' in fields and e.kind=='INSERT':
   block=doc.blocks.get(e.block_name);attributes={a['tag']:a['default'] for a in block.attributes} if block else {};attributes.update(e.attributes)
   values.extend(('Attribute.'+k,str(v)) for k,v in attributes.items())
  if 'Layer' in fields:values.append(('Layer',e.layer))
  if 'ID' in fields:values.append(('ID',e.id))
  if 'Block name' in fields and e.kind=='INSERT':values.append(('Block name',e.block_name))
  for field,value in values:
   if pattern.search(value):rows.append(dict(id=e.id,field=field,value=value,editable=doc.is_editable(e)))
 return rows


def replace_plan(doc,rows,query,replacement,case=False,whole=False):
 if not rows:raise ValueError('Check results to replace')
 if not query:raise ValueError('Enter search text')
 pattern=re.compile(('(?<!\\w)'+re.escape(query)+'(?!\\w)') if whole else re.escape(query),0 if case else re.IGNORECASE);replacements={}
 for row in rows:
  source=doc.find_by_id(row['id'])
  if source is None:raise ValueError('Search result is stale')
  e=replacements.setdefault(source.id,entity_from_dict(entity_to_dict(source)));field=row['field']
  if field=='Text':
   if source.text!=row['value']:raise ValueError('Text changed; search again')
   e.text=pattern.sub(lambda _:replacement,e.text);e.rich_html='' # plain replacement must not retain stale rich text
  elif field.startswith('Attribute.'):
   key=field[len('Attribute.'):]
   block=doc.blocks.get(source.block_name);defaults={a['tag']:a['default'] for a in block.attributes} if block else {};current=source.attributes.get(key,defaults.get(key))
   if current!=row['value']:raise ValueError('Attribute changed; search again')
   e.attributes[key]=pattern.sub(lambda _:replacement,current)
  else:raise ValueError('Only text and attribute values can be replaced; layer, ID and block-name matches are locate-only')
 return editing.plan(doc,replacements,label='Replace checked drawing values')


def template_document(doc,geometry=False):
 value=document_to_dict(doc)
 if not geometry:
  # Settings and sheets remain; object-linked annotations and project metadata are excluded.
  value.update(entities=[],blocks={},constraints=[],extensions={k:copy.deepcopy(v) for k,v in value['extensions'].items() if k in ('sheets','plot_presets','viewport_overrides','views','layer_states')},extrusions=[],underlays=[],source_archive=None,source_filepath=None)
 result=document_from_dict(value);result.filepath=None;result.source_filepath=None;result.source_archive=None;result._force_dirty=True
 return result


def save_template(doc,path,geometry=False):
 from .native_io import save_project
 result=template_document(doc,geometry)
 try:
  from .file_workspace import absolute_references
  absolute_references(result,doc.filepath or str(Path.cwd()/'drawing.pycad'));save_project(result,path)
 finally:dispose_document(result)


def open_template(path):
 from .native_io import load_project
 result=load_project(path)
 from .file_workspace import absolute_references
 absolute_references(result,path)
 result.filepath=None;result.source_filepath=None;result.source_archive=None;result._force_dirty=True;return result
