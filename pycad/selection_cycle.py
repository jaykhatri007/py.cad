"""Cycle all editable hit candidates while retaining normal pick semantics."""
from .geometry import Point
from .geom_ops import distance_to_entity

def hits(doc,point,tolerance):
    candidates=doc.query_entities((point.x-tolerance,point.y-tolerance,point.x+tolerance,point.y+tolerance),editable_only=True);result=[]
    for order,e in enumerate(candidates):
        distance=distance_to_entity(point,e,tolerance)
        if distance<tolerance:result.append((e.kind=='HATCH',distance,order,e))
    return [r[-1] for r in sorted(result,key=lambda r:r[:3])]

def candidates(mw):
    x,y=mw.current_world_pos;point=Point(x,y);tolerance=8/max(mw.canvas.zoom,1e-12);key=(id(mw.document),mw.document.render_revision,x,y,tolerance)
    if mw.canvas.__dict__.get('_cycle_key')!=key:mw.canvas._cycle_key=key;mw.canvas._cycle_items=hits(mw.document,point,tolerance);mw.canvas._cycle_index=-1
    return mw.canvas._cycle_items

def cycle(mw,reverse=False):
    if getattr(mw.current_tool,'name',None)!='SELECT':return False
    items=candidates(mw)
    if not items:mw.statusBar().showMessage('No editable objects under the cursor',2000);return True
    mw.canvas._cycle_index=((len(items)-1 if reverse else 0) if mw.canvas._cycle_index<0 else (mw.canvas._cycle_index+(-1 if reverse else 1))%len(items));mw.canvas.selected_entities=[items[mw.canvas._cycle_index]];mw.refresh_selection_ui();mw.statusBar().showMessage(f'Overlap {mw.canvas._cycle_index+1} of {len(items)} · Tab / Shift+Tab to cycle',3000);return True

def choose(mw):
    from PyQt6.QtWidgets import QInputDialog
    items=candidates(mw)
    if not items:raise ValueError('Move the cursor over editable geometry first')
    labels=[f'{i+1}: {e.kind} · {e.layer} · {getattr(e,"block_name","")} · {e.id}' for i,e in enumerate(items)];value,ok=QInputDialog.getItem(mw,'Overlapping objects','Choose object',labels,0,False)
    if ok:mw.canvas.selected_entities=[items[labels.index(value)]];mw.refresh_selection_ui()
