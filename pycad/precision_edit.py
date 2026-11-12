"""Undoable exact line/arc chain joins, breaks and spatial block snapping."""
import collections
import math
from PyQt6.QtGui import QUndoCommand
from .geometry import Point,LineEntity,ArcEntity,PolylineEntity,BlockReferenceEntity


def protected_ids(doc):
    found=set()
    def walk(value):
        if isinstance(value,str):found.add(value)
        elif isinstance(value,dict):
            for k,v in value.items():found.add(k);walk(v)
        elif isinstance(value,(list,tuple)):
            for v in value:walk(v)
    walk(doc.extensions);walk(doc.constraints)
    from .native_io import entity_to_dict
    for e in doc.entities:
        for k,v in vars(e).items():
            if k.startswith('source_'):walk(v)
    return found


class ReplaceGeometry(QUndoCommand):
    def __init__(self,doc,targets,replacements,label):
        super().__init__(label);self.doc=doc;self.before=list(doc.entities)
        ids={e.id for e in targets};first=min(i for i,e in enumerate(doc.entities) if e.id in ids)
        self.after=[e for e in doc.entities if e.id not in ids];self.after[first:first]=replacements
    def assign(self,value):
        self.doc.entities=list(value);self.doc.spatial_index.invalidate();self.doc.dirty=True
    def redo(self):self.assign(self.after)
    def undo(self):self.assign(self.before)


def guard(doc,items):
    protected=protected_ids(doc)
    if not items or any(not doc.is_editable(e) or e.id in protected for e in items):
        raise ValueError('Choose editable, unlinked geometry; managed, grouped or associated objects need their existing edit tools')


def join(doc,items,tolerance=1e-7):
    guard(doc,items)
    if not math.isfinite(tolerance) or tolerance<=0:raise ValueError('Use a positive join tolerance')
    if len({(e.layer,e.color,e.linetype,e.transparency,e.hyperlink) for e in items})!=1:raise ValueError('Join geometry must share layer, color, linetype and transparency')
    widths={getattr(e,'width',0.) for e in items}
    if len(widths)!=1:raise ValueError('Join geometry must have the same uniform width')
    parts=[]
    for e in items:
        if isinstance(e,LineEntity):parts.append((e.p1,e.p2,0))
        elif isinstance(e,ArcEntity):
            sweep=(e.end_angle-e.start_angle)%360
            if sweep<=1e-10:raise ValueError('Full circles cannot be joined as open arc segments')
            parts.append((*e.endpoints(),math.tan(math.radians(sweep)/4)))
        elif isinstance(e,PolylineEntity) and not e.closed:
            parts.extend((a,b,e.bulges[i]) for i,(a,b) in enumerate(zip(e.points,e.points[1:])))
        else:raise ValueError('Join supports lines, arcs and open polylines')
    cells=collections.defaultdict(list);points=[]
    def node(p):
        x,y=math.floor(p.x/tolerance),math.floor(p.y/tolerance)
        for dx in (-1,0,1):
            for dy in (-1,0,1):
                for index in cells[x+dx,y+dy]:
                    if points[index].distance_to(p)<=tolerance:return index
        index=len(points);points.append(Point(p.x,p.y));cells[x,y].append(index);return index
    edges=[];adj=collections.defaultdict(list)
    for a,b,bulge in parts:
        u,v=node(a),node(b)
        if u==v:raise ValueError('Degenerate join segment')
        index=len(edges);edges.append((u,v,bulge));adj[u].append(index);adj[v].append(index)
    if any(len(v)>2 for v in adj.values()):raise ValueError('Branched geometry cannot form one polyline')
    ends=[n for n,v in adj.items() if len(v)==1]
    if len(ends) not in (0,2):raise ValueError('Geometry is disconnected')
    current=ends[0] if ends else edges[0][0];start=current;used=set();vertices=[];bulges=[]
    while True:
        candidates=[i for i in adj[current] if i not in used]
        if not candidates:break
        index=candidates[0];used.add(index);u,v,b=edges[index]
        vertices.append(points[current]);bulges.append(b if u==current else -b);current=v if u==current else u
    if len(used)!=len(edges):raise ValueError('Geometry is disconnected')
    closed=current==start
    if not closed:vertices.append(points[current]);bulges.append(0)
    result=PolylineEntity(vertices,closed=closed,bulges=bulges,width=next(iter(widths)),**items[0].style_kwargs())
    doc.undo_stack.push(ReplaceGeometry(doc,items,[result],'Join exact curves'));return result


def break_at(doc,entity,fraction):
    guard(doc,[entity])
    if not math.isfinite(fraction) or not 0<fraction<1:raise ValueError('Break fraction must be between zero and one')
    if isinstance(entity,LineEntity):
        p=Point(entity.p1.x+(entity.p2.x-entity.p1.x)*fraction,entity.p1.y+(entity.p2.y-entity.p1.y)*fraction)
        parts=[LineEntity(entity.p1,p,**entity.style_kwargs()),LineEntity(p,entity.p2,**entity.style_kwargs())]
    elif isinstance(entity,ArcEntity):
        angle=entity.start_angle+((entity.end_angle-entity.start_angle)%360)*fraction
        parts=[ArcEntity(entity.center,entity.radius,entity.start_angle,angle,**entity.style_kwargs()),ArcEntity(entity.center,entity.radius,angle,entity.end_angle,**entity.style_kwargs())]
    else:raise ValueError('Break at supports a line or circular arc')
    doc.undo_stack.push(ReplaceGeometry(doc,[entity],parts,'Break curve'));return parts


def snap_candidates(entities,box,doc):
    from .spatial_index import SpatialIndex
    from .tolerance import bounds_overlap
    pending=list(reversed(entities));result=[]
    while pending:
        e=pending.pop()
        if not doc.layers.is_visible(e.layer):continue
        if isinstance(e,BlockReferenceEntity):
            result.append(e) # insertion remains a snap candidate
            key=(id(e.resolved_entities),len(e.resolved_entities),doc.render_revision,e.insertion_point.x,e.insertion_point.y,e.scale,e.rotation,e.mirrored)
            if getattr(e,'_snap_index_key',None)!=key:
                e._snap_index=SpatialIndex();e._snap_index.rebuild(e.resolved_entities);e._snap_index_key=key
            pending.extend(reversed(e._snap_index.query(box)))
        elif bounds_overlap(e.bbox(),box):result.append(e)
    return result
