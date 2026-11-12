"""Conservative, bounded edit journal for independent primitive commands."""
from collections import deque
from types import SimpleNamespace
from .linetypes import PATTERNS
from .geometry import LineEntity,CircleEntity,ArcEntity,PolylineEntity,PointEntity


def primitive(e):
 return type(e) in (LineEntity,CircleEntity,ArcEntity,PointEntity) or isinstance(e,PolylineEntity) and len(e.points)<=128


def cheap(doc,e):
 if type(e) is LineEntity:return True
 if not primitive(e):return False
 pattern=PATTERNS.get(doc.entity_linetype(e),())
 if pattern:
  box=e.bbox();span=max(box[2]-box[0],box[3]-box[1])*max(4,len(getattr(e,'points',())))
  if span/max(1e-12,sum(abs(x) for x in pattern)*doc.linetype_scale)>64:return False
 return True


def current(doc):
 state=doc.__dict__.get('_edit_state')
 return state if state is not None and state.ready and state.collection is doc.entities and state.count==len(doc.entities) and state.revision==doc.render_revision else None


def invalidate(doc):
 state=doc.__dict__.get('_edit_state')
 if state is not None:state.ready=False


def prepare(doc):
 existing=current(doc)
 if existing is not None:return existing
 ids={e.id:e for e in doc.entities};sources=set()
 for e in list(doc.entities)+[e for b in doc.blocks.values() for e in b.entities]:
  for name in ('source_line_id','source_entity_id','source_arc_id'):
   value=getattr(e,name,None)
   if value:sources.add(value)
  for name in ('source_line_ids','source_hole_ids'):sources.update(getattr(e,name,()) or ())
 # Feature metadata is not a dependency. Protect the actual referenced IDs.
 # Live schedule tables and automatic room discovery can depend on all objects.
 def referenced(value):
  if isinstance(value,str):
   if value in ids:sources.add(value)
  elif isinstance(value,dict):
   for key,item in value.items():referenced(key);referenced(item)
  elif isinstance(value,(list,tuple)):
   for item in value:referenced(item)
 referenced(doc.extensions)
 global_dependencies=bool(doc.extensions.get('auto_rooms') or any(table.get('schedule') for table in doc.extensions.get('productivity',{}).get('tables',{}).values()))
 constraint_ids={ref['entity'] for constraint in doc.constraints for ref in constraint['refs']}
 blocked=bool(doc.constraints or global_dependencies)
 state=SimpleNamespace(ready=True,revision=doc.render_revision,collection=doc.entities,count=len(doc.entities),ids=ids,sources=sources,blocked=blocked,global_dependencies=global_dependencies,constraint_ids=constraint_ids,sequence=0,events=deque(maxlen=2048),coverage={},ranks={e.id:i for i,e in enumerate(doc.entities)},next_rank=len(doc.entities))
 doc._edit_state=state;return state


def independent_add(doc,command):
 state=current(doc)
 return bool(state is not None and not state.global_dependencies and type(command).__name__=='AddEntityCommand' and type(command.entity) is LineEntity and command.entity.id not in state.constraint_ids and command.entity.id not in state.sources and not getattr(command,'needs_solve',False))


def begin(doc,command,undo=False):
 previous=doc.__dict__.get('_edit_context');state=current(doc);context=None
 if state is not None and ((not state.blocked and not doc.constraints) or independent_add(doc,command)) and not getattr(command,'needs_solve',False):
  name=type(command).__name__;entities=[];operation='change'
  if name=='AddEntityCommand':entities=[command.entity];operation='remove' if undo else 'add'
  elif name=='DeleteEntitiesCommand':
   entities=command.entities;operation='add' if undo else 'remove'
   if undo and any(e.id not in state.ranks for e in entities):entities=[]
  elif name in ('TranslateEntitiesCommand','RotateEntitiesCommand','ScaleEntitiesCommand'):entities=command.entities
  elif name in ('SetAttrCommand','SetPointCommand'):
   entities=[command.entity if name=='SetAttrCommand' else command.owner]
   if name=='SetAttrCommand':
    attr=command.attr_name
    if attr not in ('p1','p2','center','radius','start_angle','end_angle','points','bulges','closed','width','color','transparency','hyperlink'):entities=[]
    proposed=command.old_value if undo else command.new_value
    if attr=='points' and (not isinstance(proposed,(list,tuple)) or len(proposed)>128):entities=[]
  if entities and len(entities)<=128 and all(cheap(doc,e) and (operation!='change' or not PATTERNS.get(doc.entity_linetype(e),())) and e.id not in state.sources and state.coverage.get(e.id,True) for e in entities):
   valid_index=not doc.spatial_index._dirty and getattr(doc,'_spatial_collection',None)==(id(doc.entities),len(doc.entities)) and getattr(doc,'_spatial_revision',None)==doc.render_revision
   context=SimpleNamespace(state=state,entities=list(entities),operation=operation,handled=False,index_valid=valid_index)
 if context is None:invalidate(doc)
 doc._edit_context=context;return previous,context


def end(doc,token):
 previous,context=token
 if context is not None and not context.handled:invalidate(doc)
 doc._edit_context=previous


def active(doc):
 context=doc.__dict__.get('_edit_context')
 return context is not None and context.handled and context.state is doc.__dict__.get('_edit_state') and context.state.ready


def revision(doc):
 state=doc.__dict__.get('_edit_state')
 if state is not None and state.ready:
  state.revision=doc.render_revision
  context=doc.__dict__.get('_edit_context')
  if context is not None and context.index_valid:doc._spatial_revision=doc.render_revision


def sync(doc):
 context=doc.__dict__.get('_edit_context')
 if context is None or context.state is not doc.__dict__.get('_edit_state') or not context.state.ready:return False
 state=context.state
 if not context.handled:
  doc.check_issues=[]
  for e in context.entities:
   if context.operation=='remove':state.ids.pop(e.id,None)
   else:
    state.ids[e.id]=e
    if e.id not in state.ranks:state.ranks[e.id]=state.next_rank;state.next_rank+=1
   if context.index_valid:
    doc.spatial_index.remove(e)
    if context.operation!='remove':doc.spatial_index.insert(e)
  if context.index_valid:
   doc.spatial_index._dirty=False;doc._spatial_collection=(id(doc.entities),len(doc.entities))
  state.sequence+=1;state.events.append((state.sequence,context.operation,context.entities));state.count=len(doc.entities);context.handled=True
 revision(doc);return True
