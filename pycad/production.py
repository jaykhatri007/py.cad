"""Persistent sheet sets, production annotations and auditable quantity snapshots."""
import copy,hashlib,json,math,datetime
from .native_io import document_to_dict,document_from_dict,entity_to_dict

def data(doc):return doc.extensions.get('production',{})
def digest(doc):
 v=document_to_dict(doc)
 relevant={k:v[k] for k in ('units','entities','blocks','layers')}
 relevant['extensions']={k:r for k,r in v.get('extensions',{}).items() if k not in ('production','sheets','plot_presets','viewport_overrides','views','layer_states')}
 return hashlib.sha256(json.dumps(relevant,sort_keys=True,allow_nan=False).encode()).hexdigest()

def validate(table,payload=None):
 from .validation import name,finite
 if not isinstance(table,dict) or set(table)-{'sheet_sets','quantity_snapshot'}:raise ValueError('Invalid production data')
 sets=table.get('sheet_sets',{})
 if not isinstance(sets,dict) or len(sets)>1000:raise ValueError('Invalid sheet sets')
 for key,r in sets.items():
  name(key,'Sheet set')
  if not isinstance(r,dict) or set(r)!={'spaces','issues'}:raise ValueError('Invalid sheet set record')
  spaces=r['spaces']
  if not isinstance(spaces,list) or not 1<=len(spaces)<=1000 or any(not isinstance(v,str) for v in spaces) or len(set(spaces))!=len(spaces):raise ValueError('Use distinct ordered sheets')
  for s in spaces:name(s,'Sheet name')
  if not isinstance(r['issues'],list) or len(r['issues'])>1000:raise ValueError('Invalid issue history')
  for issue in r['issues']:
   if not isinstance(issue,dict) or set(issue)!={'revision','date','note'}:raise ValueError('Invalid issue')
   for k in issue:
    if not isinstance(issue[k],str) or len(issue[k])>1000:raise ValueError('Invalid issue field')
   datetime.date.fromisoformat(issue['date'])
 snapshot=table.get('quantity_snapshot')
 if snapshot is not None:
  if not isinstance(snapshot,dict) or set(snapshot)!={'digest','created','currency','rows'}:raise ValueError('Invalid quantity snapshot')
  if not isinstance(snapshot['digest'],str) or len(snapshot['digest'])!=64 or any(c not in '0123456789abcdef' for c in snapshot['digest']):raise ValueError('Invalid quantity fingerprint')
  if not isinstance(snapshot['created'],str):raise ValueError('Invalid snapshot date')
  datetime.datetime.fromisoformat(snapshot['created']);name(snapshot['currency'],'Currency')
  if not isinstance(snapshot['rows'],list) or len(snapshot['rows'])>1000000:raise ValueError('Invalid quantity rows')
  for row in snapshot['rows']:
   if not isinstance(row,dict) or set(row)!={'source_id','description','unit','quantity','method'}:raise ValueError('Invalid quantity evidence')
   for k in ('source_id','description','unit','method'):
    if not isinstance(row[k],str) or len(row[k])>1000:raise ValueError('Invalid evidence text')
   finite(row['quantity'],'Quantity')
 return table

def save(doc,key,value,label):
 from .document import SetAttrCommand
 after=copy.deepcopy(doc.extensions);after.setdefault('production',{})[key]=copy.deepcopy(value);validate(after['production'])
 doc.undo_stack.push(SetAttrCommand(doc,doc,'extensions',doc.extensions,after,label))

def save_set(doc,name,spaces):
 if not isinstance(name,str) or name.casefold() in ('model','all layouts'):raise ValueError('Choose a sheet set name other than Model or All layouts')
 if any(s not in doc.layouts for s in spaces):raise ValueError('Select existing paper layouts')
 sets=copy.deepcopy(data(doc).get('sheet_sets',{}));sets[name]=dict(spaces=list(spaces),issues=sets.get(name,{}).get('issues',[]));save(doc,'sheet_sets',sets,'Save ordered sheet set')

def issue_set(doc,name,revision,note='',date=None):
 from .sheets import title_block
 sets=copy.deepcopy(data(doc).get('sheet_sets',{}));r=sets.get(name)
 if not r:raise ValueError('Save a sheet set first')
 if any(s not in doc.layouts for s in r['spaces']):raise ValueError('A sheet was removed or renamed; update the set')
 if not revision.strip() or len(revision)>255:raise ValueError('Enter a revision up to 255 characters')
 r['issues'].append(dict(revision=revision,date=date or datetime.date.today().isoformat(),note=note));validate({'sheet_sets':sets})
 doc.undo_stack.beginMacro('Issue sheet set')
 try:
  for s in r['spaces']:
   old=doc.extensions.get('sheets',{}).get(s,dict(project='Project',title=s,number=s,revision='',author=''));title_block(doc,s,**{**old,'revision':revision})
  save(doc,'sheet_sets',sets,'Record sheet issue')
 finally:doc.undo_stack.endMacro()

def renumber(doc,spaces,prefix='A',start=1):
 from .sheets import title_block
 if not spaces or len(set(spaces))!=len(spaces) or any(s not in doc.layouts for s in spaces):raise ValueError('Choose distinct existing layouts')
 if type(start) is not int or start<0 or len(prefix)>240:raise ValueError('Invalid numbering')
 doc.undo_stack.beginMacro('Renumber sheets')
 try:
  for i,s in enumerate(spaces):
   old=doc.extensions.get('sheets',{}).get(s,dict(project='Project',title=s,number=s,revision='',author=''));title_block(doc,s,**{**old,'number':prefix+str(start+i).zfill(3)})
 finally:doc.undo_stack.endMacro()

def comparison(before,after):
 from .revisions import compare
 result=compare(before,after)
 def appearances(doc):
  memo={}
  def token(e,visiting=()):
   values=[entity_to_dict(e),doc.layers.layers.get(e.layer),doc.textstyles.get(getattr(e,'style_name','')) if e.kind=='TEXT' else doc.dimstyles.get(getattr(e,'style_name','')) if 'DIM' in e.kind else None]
   if e.kind=='INSERT' and e.block_name in doc.blocks:
    name=e.block_name
    if name in visiting:raise ValueError('Cyclic block definition')
    if name not in memo:memo[name]=[token(child,(*visiting,name)) for child in doc.blocks[name].entities]
    values.append(memo[name])
   return hashlib.sha256(json.dumps(values,sort_keys=True,allow_nan=False).encode()).hexdigest()
  return {e.id:token(e) for e in doc.entities}
 a,b=appearances(before),appearances(after);changed=set(result['changed'])|{key for key in a.keys()&b.keys() if a[key]!=b[key]}
 result['changed']=sorted(changed);result['unchanged']=len(a.keys()&b.keys())-len(changed)
 result['settings_changed']=result['settings_changed'] or before.dimstyles!=after.dimstyles or before.textstyles!=after.textstyles or before.layers.layers!=after.layers.layers
 return result

def comparison_overlay(before,after):
 from .geometry import BlockDefinition
 from .document import Document
 from .native_io import entity_from_dict
 report=comparison(before,after);overlay=Document();overlay.units=after.units
 # Each version retains its own block definitions, including nested references.
 # Prefix all names to prevent old definitions from resolving through new data.
 if before.units!=after.units:raise ValueError('Drawing units differ; normalize units before overlay comparison')
 for prefix,doc,color,ids in [('OLD_',before,'#e74c3c',set(report['removed']+report['changed'])),('NEW_',after,'#27ae60',set(report['added']+report['changed'])),('CTX_',after,'#7f8c8d',{e.id for e in after.entities}-set(report['added']+report['changed']))]:
  for name,style in doc.dimstyles.items():overlay.dimstyles[prefix+name]=copy.deepcopy(style)
  for name,style in doc.textstyles.items():overlay.textstyles[prefix+name]=copy.deepcopy(style)
  for name,b in doc.blocks.items():
   entities=[]
   for source in b.entities:
    e=entity_from_dict(entity_to_dict(source));e.color=color;e.layer='0'
    if hasattr(e,'style_name'):e.style_name=prefix+e.style_name
    if e.kind=='INSERT':e.block_name=prefix+e.block_name
    entities.append(e)
   overlay.blocks[prefix+name]=BlockDefinition(prefix+name,entities,attributes=copy.deepcopy(b.attributes))
  for source in doc.entities:
   if source.id not in ids:continue
   e=entity_from_dict(entity_to_dict(source));e.id=prefix+e.id;e.layer='0';e.color=color
   if hasattr(e,'style_name'):e.style_name=prefix+e.style_name
   if e.kind=='INSERT':e.block_name=prefix+e.block_name
   overlay.entities.append(e)
 overlay.spatial_index.invalidate();return overlay,report

def quantity_snapshot(doc):
 from .revisions import quantity_rows
 report=quantity_rows(doc);rows=[dict(source_id=r['source_id'],description=r['description'],unit=r['unit'],quantity=r['adjusted_quantity'],method=r['method']) for r in report['rows']]
 return dict(digest=digest(doc),created=datetime.datetime.now(datetime.timezone.utc).isoformat(),currency=report['currency'],rows=rows)

def refresh_quantities(doc):
 snapshot=quantity_snapshot(doc);save(doc,'quantity_snapshot',snapshot,'Refresh quantity evidence');return snapshot

def quantity_status(doc):
 snapshot=data(doc).get('quantity_snapshot')
 return 'Not captured' if snapshot is None else ('Current' if snapshot['digest']==digest(doc) else 'Outdated — recalculate')

def space_dimensions(doc,entities,gap):
 from .geometry import DimensionEntity,Point
 from .document import SetAttrCommand
 from .validation import finite
 finite(gap,'Dimension spacing',True)
 if len(entities)<2 or any(not isinstance(e,DimensionEntity) or not doc.is_editable(e) for e in entities):raise ValueError('Select at least two editable linear dimensions')
 first=entities[0];style=first.dim_style
 if style not in ('aligned','horizontal','vertical') or any(e.dim_style!=style for e in entities):raise ValueError('Choose dimensions with the same linear orientation')
 if style=='horizontal':u=(1.,0.)
 elif style=='vertical':u=(0.,1.)
 else:
  dx,dy=first.p2.x-first.p1.x,first.p2.y-first.p1.y;n=math.hypot(dx,dy)
  if n<=1e-12:raise ValueError('Dimension has no baseline')
  u=(dx/n,dy/n)
  for e in entities:
   dx,dy=e.p2.x-e.p1.x,e.p2.y-e.p1.y;n=math.hypot(dx,dy)
   if n<=1e-12 or abs(dx*u[1]-dy*u[0])>n*1e-7:raise ValueError('Aligned dimensions must be parallel')
 normal=(-u[1],u[0]);project=lambda p:p.x*normal[0]+p.y*normal[1];ordered=sorted(entities,key=lambda e:project(e.dim_point));base=project(ordered[0].dim_point)
 changes=[]
 for i,e in enumerate(ordered):
  delta=base+i*gap-project(e.dim_point);changes.append((e,Point(e.dim_point.x+normal[0]*delta,e.dim_point.y+normal[1]*delta)))
 doc.undo_stack.beginMacro('Space dimension lines')
 try:
  for e,p in changes:doc.undo_stack.push(SetAttrCommand(doc,e,'dim_point',e.dim_point,p,'Dimension spacing'))
 finally:doc.undo_stack.endMacro()

def text_paper_height(doc,entities,paper_mm,denominator):
 from .units import UNIT_MM
 from .validation import finite
 from .document import SetAttrCommand
 finite(paper_mm,'Paper text height',True);finite(denominator,'Annotation scale',True)
 if doc.units not in UNIT_MM:raise ValueError('Set physical drawing units')
 if not entities or any(e.kind!='TEXT' or not doc.is_editable(e) for e in entities):raise ValueError('Select editable text objects')
 height=paper_mm*denominator/UNIT_MM[doc.units];finite(height,'Model text height',True)
 doc.undo_stack.beginMacro('Set paper text height')
 try:
  for e in entities:doc.undo_stack.push(SetAttrCommand(doc,e,'height',e.height,height,'Paper text height'))
 finally:doc.undo_stack.endMacro()

def dimension_paper_size(doc,entities,paper_mm,denominator):
 """Assign independent dimension styles; existing users of a style stay unchanged."""
 import uuid
 from .units import UNIT_MM
 from .validation import finite
 from .dimstyles import style_for,validate_style
 from .table_commands import StyleTableCommand
 from .document import SetAttrCommand
 finite(paper_mm,'Paper dimension height',True);finite(denominator,'Annotation scale',True)
 if doc.units not in UNIT_MM:raise ValueError('Set physical drawing units')
 if not entities or any(e.kind not in ('DIMENSION','CURVED_DIMENSION','ORDINATE_DIMENSION') or not doc.is_editable(e) for e in entities):raise ValueError('Select editable dimension objects')
 styles=copy.deepcopy(doc.dimstyles);assignments=[];names={}
 for e in entities:
  key=e.style_name
  if key not in names:
   name='Paper_'+uuid.uuid4().hex[:12];style=copy.deepcopy(style_for(doc,e));style.update(text_height=paper_mm,scale=denominator/UNIT_MM[doc.units]);validate_style(style);styles[name]=style;names[key]=name
  assignments.append((e,names[key]))
 doc.undo_stack.beginMacro('Set paper dimension size')
 try:
  doc.undo_stack.push(StyleTableCommand(doc,styles,doc.current_dimstyle))
  for e,name in assignments:doc.undo_stack.push(SetAttrCommand(doc,e,'style_name',e.style_name,name,'Paper dimension style'))
 finally:doc.undo_stack.endMacro()
