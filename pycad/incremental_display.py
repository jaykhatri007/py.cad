"""Local primitive display patches; no whole-document snapshot on draft edits."""
import weakref
from . import edit_journal
from .geometry import LineEntity


def overlap(a,b):return not (a[2]<b[0] or a[0]>b[2] or a[3]<b[1] or a[1]>b[3])


class DeltaDisplay:
 def __init__(self,doc,scene,state):
  self.doc=weakref.ref(doc);self.state=state;self.cursor=state.sequence;self.sources=[];self.slots={};self.patches={};self.dirty=set();self.added=[];self.added_slots={};self.added_pictures={};self.added_dirty=set();self.affected=set();self.base_version=0;self.damage=[];self.added_layers=[];self.entries=scene['entries']
  for i,entry in enumerate(scene['entries']):
   batch=[state.ids[k] for k in entry.get('ids',()) if k in state.ids];self.sources.append(batch)
   safe=bool(batch) and all(edit_journal.cheap(doc,e) for e in batch)
   if not all(type(e) is LineEntity for e in batch) and any(type(e) is LineEntity and doc.entity_linetype(e)!='CONTINUOUS' for e in batch):safe=False
   for e in batch:
    previous=self.slots.get(e.id)
    if previous is None:self.slots[e.id]=i
    elif isinstance(previous,int):self.slots[e.id]=[previous,i]
    else:previous.append(i)
    state.coverage[e.id]=state.coverage.get(e.id,True) and safe
 def accept(self,doc,old_signature,new_signature):
  if old_signature is None or old_signature[0]!=new_signature[0] or old_signature[3:]!=new_signature[3:]:return False
  state=edit_journal.current(doc)
  if state is not self.state:return False
  if state.sequence==self.cursor:return True
  events=[event for event in state.events if event[0]>self.cursor]
  if not events or events[0][0]!=self.cursor+1:return False
  for sequence,operation,entities in events:
   for entity in entities:
    key=entity.id;self.affected.add(key)
    if key in self.slots:
     indices=self.slots[key]
     if isinstance(indices,int):self.dirty.add(indices)
     else:self.dirty.update(indices)
    else:
     if key not in self.added_slots:
      if not self.added or len(self.added[-1])>=128 or self.added_layers[-1]!=entity.layer or (type(self.added[-1][0]) is LineEntity)!=(type(entity) is LineEntity):self.added.append([]);self.added_layers.append(entity.layer)
      index=len(self.added)-1;self.added[index].append(entity);self.added_slots[key]=index
     self.added_dirty.add(self.added_slots[key])
  self.cursor=state.sequence;return True
 def prepare(self,canvas,painter):
  if not self.dirty and not self.added_dirty:return
  from .persistent_scene import record_vector
  from .appearance import colors
  request=dict(colors=colors(canvas),font=painter.font().toString(),hints=painter.renderHints().value,boq=False)
  doc=self.doc()
  if self.dirty:self.base_version+=1
  for indices,sources,records in ((self.dirty,self.sources,self.patches),(self.added_dirty,self.added,self.added_pictures)):
   for index in indices:
    batch=[e for e in sources[index] if self.state.ids.get(e.id) is e]
    if indices is self.dirty:
     old=records.get(index)
     self.damage.append(old[1]['bounds'] if old else self.entries[index]['bounds'])
    from .immediate_lines import record
    records[index]=(record(doc,batch) if all(type(e) is LineEntity for e in batch) else record_vector(doc,batch,request)) if batch else None
    if indices is self.dirty and records[index] is not None:self.damage.append(records[index][1]['bounds'])
   indices.clear()
 def paint_record(self,canvas,painter,record):
  if record is None:return
  picture,entry=record
  if 'lines' in entry:
   from .immediate_lines import draw
   draw(canvas,painter,entry['lines']);return
  at=canvas.world_to_screen(*entry['origin']);factor=canvas.zoom/entry['scale'];painter.save()
  try:painter.translate(at);painter.scale(factor,factor);painter.drawPicture(0,0,picture)
  finally:painter.restore()
 def extra_candidates(self,view):return [i for i,record in self.patches.items() if record is not None and overlap(record[1]['bounds'],view)]
 def draw_added(self,canvas,painter,view):
  for index in sorted(self.added_pictures):
   record=self.added_pictures[index]
   if record is not None and overlap(record[1]['bounds'],view):self.paint_record(canvas,painter,record)
 def draw_selection(self,canvas,painter):
  selected=[e for e in canvas.selected_entities if e.id in self.affected and self.state.ids.get(e.id) is e]
  if selected:
   canvas._draw_entities(painter,entities=selected)
   if len(canvas.selected_entities)==1:canvas._draw_grips(painter)


def attach(canvas,scene,signature):
 from .persistent_scene import enabled
 if not enabled(canvas) or canvas.document.current_space!='Model' or getattr(canvas,'boq_overlay_enabled',False):return None
 if signature[0]!=id(canvas.document) or signature[1]!=canvas.document.render_revision:return None
 state=edit_journal.prepare(canvas.document);delta=DeltaDisplay(canvas.document,scene,state);scene['delta']=delta;return delta
