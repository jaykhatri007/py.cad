"""Cooperative private model snapshots; no Qt geometry painting on capture."""
import copy
from .geometry import Point,BlockReferenceEntity

def model_field(key):
    """Keep required model state while excluding disposable renderer caches."""
    return not key.startswith('_') or key in ('_text_style','_mleader_style')

def value_copy(value,counter):
    counter[0]+=1
    if counter[0]%128==0:yield None
    if value is None or type(value) in (str,bytes,int,float,bool):return value
    if isinstance(value,Point):return Point(value.x,value.y)
    if isinstance(value,(list,tuple,set)):
        result=[]
        for item in value:result.append((yield from value_copy(item,counter)))
        return tuple(result) if isinstance(value,tuple) else set(result) if isinstance(value,set) else result
    if isinstance(value,dict):
        result={}
        for key,item in value.items():result[key]=yield from value_copy(item,counter)
        return result
    if hasattr(value,'__dict__'):
        result=object.__new__(type(value));result.__dict__={}
        for key,item in value.__dict__.items():
            if model_field(key):result.__dict__[key]=yield from value_copy(item,counter)
        return result
    return copy.deepcopy(value)

def freeze_iter(entities):
    result=[];stack=[(iter(entities),result)];counter=[0]
    while stack:
        iterator,target=stack[-1]
        try:entity=next(iterator)
        except StopIteration:stack.pop();continue
        clone=object.__new__(type(entity));clone.__dict__={}
        for key,value in entity.__dict__.items():
            if model_field(key) and key!='resolved_entities':clone.__dict__[key]=yield from value_copy(value,counter)
        target.append(clone)
        if isinstance(entity,BlockReferenceEntity):clone.resolved_entities=[];stack.append((iter(entity.resolved_entities),clone.resolved_entities))
        yield None
    return result

def capture(canvas):
    from .async_display import SnapshotDocument
    from .progressive_display import tasks
    doc=SnapshotDocument.__new__(SnapshotDocument);counter=[0]
    for key in ('layers','textstyles','dimstyles','mleaderstyles','units','unit_settings','linetype_scale','extensions','isolated_ids','render_revision','current_space','underlays','filepath','layouts','link_status'):
        setattr(doc,key,(yield from value_copy(getattr(canvas.document,key,{}),counter)))
    doc.entities=[];yield ('document',doc)
    from .edit_journal import primitive
    # Ordered layer runs preserve cross-layer overlap/draw order. Expensive
    # geometry never makes a neighboring independent primitive unpatchable.
    for batch in tasks(canvas.document.entities,None,canvas.document.render_revision):
        # Highly interleaved layer order must not create one native file per
        # entity. Retain ordered bounded packets in that case; local damage
        # composition still avoids repainting the whole view.
        split_layers=sum(a.layer!=b.layer for a,b in zip(batch,batch[1:]))<=16
        run=[];last=None
        for entity in batch:
            key=(entity.layer if split_layers else None,primitive(entity))
            if run and (key!=last or len(run)>=256):
                frozen=yield from freeze_iter(run);yield ('batch',(None,None,None,True,frozen));run=[]
            run.append(entity);last=key
        if run:
            frozen=yield from freeze_iter(run);yield ('batch',(None,None,None,True,frozen))
