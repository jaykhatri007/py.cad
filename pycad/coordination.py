"""Shared properties, portable project standards, library metadata and reference graph."""
import copy,json,math,os,time
from pathlib import Path
from .native_io import document_to_dict,document_from_dict,entity_to_dict,entity_from_dict
MIXED='— mixed —'

def common_properties(doc,items):
 from .object_properties import values_for
 if not items:return {}
 maps=[]
 for item in items:
  values=values_for(doc,item)
  values={k:v for k,v in values.items() if not k.startswith(('Architecture.','Building.','BuildingView.','View.','Level.'))}
  values.update({k:getattr(item,k) for k in ('layer','color','linetype','transparency','hyperlink')})
  if hasattr(item,'style_name') and len({q.kind for q in items})==1:values['style_name']=item.style_name
  if item.kind in ('TEXT','MLEADER'):values['text']=item.text
  maps.append(values)
 common=set(maps[0]).intersection(*(set(m) for m in maps[1:]))
 return {k:maps[0][k] if all(m[k]==maps[0][k] for m in maps) else MIXED for k in sorted(common)}

def properties_plan(doc,items,changes):
 from .editing import plan
 from .object_properties import values_for
 from .validation import finite
 common=common_properties(doc,items)
 if not changes or set(changes)-set(common):raise ValueError('Choose shared property fields')
 replacements={}
 for item in items:
  if not doc.contains_entity(item) or not doc.is_editable(item):raise ValueError('Every selected object must be editable')
  clone=entity_from_dict(entity_to_dict(item));values=values_for(doc,item)
  for key,raw in changes.items():
   if raw==MIXED:raise ValueError('Replace mixed values with an explicit value')
   if key.startswith('Attribute.'):
    clone.attributes[key.split('.',1)[1]]=str(raw);continue
   previous=values.get(key,getattr(item,key,None))
   if type(previous) in (float,int):value=float(raw);finite(value,key)
   else:
    if not isinstance(raw,str):raise ValueError('Use text for '+key)
    value=raw
   if '.' in key:
    attr,coord=key.split('.');setattr(getattr(clone,attr),coord,value)
   else:setattr(clone,key,value)
  replacements[item.id]=clone
 return plan(doc,replacements,label='Shared object properties')

def capture_standard(doc):
 return dict(format='PY.cad standard 1',units=doc.units,layers={k:{p:v[p] for p in ('color','linetype','lineweight','plot')} for k,v in doc.layers.layers.items()},textstyles=copy.deepcopy(doc.textstyles),dimstyles=copy.deepcopy(doc.dimstyles),plot_presets=copy.deepcopy(doc.extensions.get('plot_presets',{})))

def validate_standard(profile):
 from .document import Document
 from .layers import LAYER_DEFAULTS
 if not isinstance(profile,dict) or set(profile)!={'format','units','layers','textstyles','dimstyles','plot_presets'} or profile['format']!='PY.cad standard 1':raise ValueError('Invalid project standard')
 for section in ('layers','textstyles','dimstyles','plot_presets'):
  if not isinstance(profile[section],dict) or len(profile[section])>1000:raise ValueError('Invalid standard section')
 for name,r in profile['layers'].items():
  if not isinstance(r,dict) or set(r)!={'color','linetype','lineweight','plot'}:raise ValueError('Invalid standard layer')
 d=Document();v=document_to_dict(d);v['units']=profile['units'];v['layers'].update({k:{**LAYER_DEFAULTS,**r} for k,r in profile['layers'].items()});v['textstyles'].update(profile['textstyles']);v['dimstyles'].update(profile['dimstyles']);v['extensions']['plot_presets']=copy.deepcopy(profile['plot_presets']);document_from_dict(v);return profile

def standard_candidate(doc,profile):
 validate_standard(profile)
 if profile['units']!=doc.units:raise ValueError('Standard drawing units differ; convert drawing units explicitly first')
 from .layers import LAYER_DEFAULTS
 value=document_to_dict(doc)
 for name,r in profile['layers'].items():value['layers'][name]={**LAYER_DEFAULTS,**value['layers'].get(name,{}),**r}
 for section in ('textstyles','dimstyles'):value[section].update(copy.deepcopy(profile[section]))
 value['extensions'].setdefault('plot_presets',{}).update(copy.deepcopy(profile['plot_presets']));return document_from_dict(value)

def standard_diff(doc,profile):
 candidate=standard_candidate(doc,profile);rows=[]
 for section,old,new in [('Layer',doc.layers.layers,candidate.layers.layers),('Text style',doc.textstyles,candidate.textstyles),('Dimension style',doc.dimstyles,candidate.dimstyles),('Plot preset',doc.extensions.get('plot_presets',{}),candidate.extensions.get('plot_presets',{}))]:
  for name,record in new.items():
   if old.get(name)!=record:rows.append(dict(kind=section,name=name,change='Update' if name in old else 'Add'))
 return candidate,rows

def apply_standard(doc,profile):
 from PyQt6.QtGui import QUndoCommand
 candidate,rows=standard_diff(doc,profile)
 if not rows:return False
 class Apply(QUndoCommand):
  def __init__(self):super().__init__('Apply project standard');self.old=(copy.deepcopy(doc.layers.layers),copy.deepcopy(doc.textstyles),copy.deepcopy(doc.dimstyles),copy.deepcopy(doc.extensions));self.new=(copy.deepcopy(candidate.layers.layers),copy.deepcopy(candidate.textstyles),copy.deepcopy(candidate.dimstyles),copy.deepcopy(candidate.extensions))
  def assign(self,state):doc.layers.layers,doc.textstyles,doc.dimstyles,doc.extensions=copy.deepcopy(state);doc.spatial_index.invalidate();doc.dirty=True
  def redo(self):self.assign(self.new)
  def undo(self):self.assign(self.old)
 doc.undo_stack.push(Apply());return True

def read_standard(path):
 p=Path(path)
 if p.stat().st_size>8*1024*1024:raise ValueError('Standard exceeds 8 MiB')
 return validate_standard(json.loads(p.read_text(encoding='utf-8')))

def reference_graph(doc):
 from .xref_manager import status
 statuses={r['name']:r for r in status(doc)};parents={name:[] for name in doc.blocks};missing=[]
 for name,b in doc.blocks.items():
  for child in b.entities:
   if child.kind=='INSERT':
    if child.block_name in parents:parents[child.block_name].append(name)
    else:missing.append(dict(parent=name,child=child.block_name))
 rows=[]
 for name,r in statuses.items():
  direct=[q.id for q in doc.entities if q.kind=='INSERT' and q.block_name==name];ancestors=set();pending=list(parents[name])
  while pending:
   current=pending.pop()
   if current in ancestors:continue
   ancestors.add(current);pending.extend(parents.get(current,[]))
  ids=direct+[q.id for q in doc.entities if q.kind=='INSERT' and q.block_name in ancestors]
  rows.append({**r,'parents':sorted(set(parents[name])),'ancestors':sorted(ancestors),'instance_ids':sorted(set(ids))})
 return dict(rows=rows,edges=[dict(parent=p,child=n) for n,ps in parents.items() for p in sorted(set(ps))],missing_definitions=missing,note='Dependencies present in this drawing. Reloaded external files currently become imported snapshots; this is not recursive filesystem reference discovery.')

def block_metadata():
 from .appsettings import get_settings
 value=json.loads(get_settings().value('coordination/block_metadata','{}'))
 if not isinstance(value,dict) or any(not isinstance(k,str) or not isinstance(v,dict) or set(v)!={'category','favorite'} or not isinstance(v['category'],str) or len(v['category'])>100 or type(v['favorite']) is not bool for k,v in value.items()):raise ValueError('Invalid local block metadata')
 return value

def set_block_metadata(name,category=None,favorite=None):
 from .appsettings import get_settings
 values=block_metadata();record=values.setdefault(name,dict(category='',favorite=False))
 if category is not None:
  if not isinstance(category,str) or len(category)>100:raise ValueError('Category must be up to 100 characters')
  record['category']=category
 if favorite is not None:record['favorite']=bool(favorite)
 get_settings().setValue('coordination/block_metadata',json.dumps(values))

def managed_blocks(doc):
 names={r.get('block') for r in doc.extensions.get('architecture',{}).values()};names.update(doc.extensions.get('productivity',{}).get('tables',{}));names.update(doc.extensions.get('building_elements',{}).get(k,{}).get('block') for k in doc.extensions.get('building_elements',{}));return names

def block_preview(doc,name,scale=1.,rotation=0.):
 from .document import Document
 from .geometry import BlockDefinition,BlockReferenceEntity,Point
 from .validation import finite
 finite(scale,'Insertion scale',True);finite(rotation,'Insertion rotation')
 if name not in doc.blocks:raise ValueError('Block no longer exists')
 out=Document();out.units=doc.units;out.layers=copy.deepcopy(doc.layers)
 for layer in out.layers.layers.values():layer.update(visible=True,frozen=False,locked=False)
 out.textstyles=copy.deepcopy(doc.textstyles);out.dimstyles=copy.deepcopy(doc.dimstyles);out.mleaderstyles=copy.deepcopy(doc.mleaderstyles)
 required=set();pending=[name]
 while pending:
  n=pending.pop()
  if n in required:continue
  if n not in doc.blocks:raise ValueError('Missing nested block '+n)
  required.add(n);pending.extend(e.block_name for e in doc.blocks[n].entities if e.kind=='INSERT')
 for n in required:
  b=doc.blocks[n];out.blocks[n]=BlockDefinition(n,[entity_from_dict(entity_to_dict(e)) for e in b.entities],attributes=copy.deepcopy(b.attributes))
 ref=BlockReferenceEntity(name,Point(0,0),scale=scale,rotation=rotation);out.entities=[ref];out.sync_associative();return out

def thumbnail_document(doc,name,limit=128):
 from .document import Document
 from .geometry import Point
 out=Document();out.layers=copy.deepcopy(doc.layers)
 for layer in out.layers.layers.values():layer.update(visible=True,frozen=False,locked=False)
 out.textstyles=copy.deepcopy(doc.textstyles);pending=[(q,[]) for q in reversed(doc.blocks[name].entities)];seen=0
 while pending and len(out.entities)<limit and seen<2000:
  source,chain=pending.pop();seen+=1
  if source.kind=='INSERT':
   if len(chain)<64 and source.block_name in doc.blocks:pending.extend((q,[source,*chain]) for q in reversed(doc.blocks[source.block_name].entities))
   continue
  e=source.clone()
  for ref in chain:
   if ref.mirrored:e.reflect_across(Point(0,0),Point(1,0))
   e.scale_from(Point(0,0),ref.scale);e.rotate_around(Point(0,0),ref.rotation);e.translate(ref.insertion_point.x,ref.insertion_point.y)
  out.entities.append(e)
 out.sync_associative();return out
