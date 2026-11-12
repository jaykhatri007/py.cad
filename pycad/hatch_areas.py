"""Selected boundaries and combined even-odd regions, validated before mutation."""
import copy
from .geometry import HatchEntity,CircleEntity,PolylineEntity

def touches(a,b,c,d):
    from .geom_ops import line_line_intersection
    if line_line_intersection(a,b,c,d,True) is not None:return True
    def on(p,x,y):return abs((p.x-x.x)*(y.y-x.y)-(p.y-x.y)*(y.x-x.x))<=1e-9*max(1,abs(y.x-x.x),abs(y.y-x.y)) and min(x.x,y.x)-1e-9<=p.x<=max(x.x,y.x)+1e-9 and min(x.y,y.y)-1e-9<=p.y<=max(x.y,y.y)+1e-9
    return on(a,c,d) or on(b,c,d) or on(c,a,b) or on(d,a,b)

def make(areas,options,layer,combined=False,associative=True):
    if not areas:raise ValueError('Pick an area first')
    if not combined:return [HatchEntity(copy.deepcopy(a['boundary']),holes=copy.deepcopy(a['holes']),source_entity_id=a['source'].id if a['source'] is not None and associative else None,source_hole_ids=a.get('hole_sources',[]) if associative else [],layer=layer,**copy.deepcopy(options)) for a in areas]
    loops=[copy.deepcopy(loop) for a in areas for loop in [a['boundary'],*a['holes']]]
    if sum(map(len,loops))>10000:raise ValueError('Simplify hatch outlines to 10,000 vertices')
    work=0
    for i,a in enumerate(loops):
        for b in loops[i+1:]:
            if max(p.x for p in a)<min(p.x for p in b) or max(p.x for p in b)<min(p.x for p in a) or max(p.y for p in a)<min(p.y for p in b) or max(p.y for p in b)<min(p.y for p in a):continue
            work+=len(a)*len(b)
            if work>1000000:raise ValueError('Boundary checks too complex; simplify outlines')
            if any(touches(a[j],a[(j+1)%len(a)],b[k],b[(k+1)%len(b)]) for j in range(len(a)) for k in range(len(b))):raise ValueError('Combined boundaries must not cross or touch')
    from .geom_ops import point_in_polygon
    sizes=[abs(sum(a.x*b.y-b.x*a.y for a,b in zip(loop,loop[1:]+loop[:1]))) for loop in loops]
    depths=[sum(sizes[j]>sizes[i] and point_in_polygon(loop[0],other) for j,other in enumerate(loops) if j!=i) for i,loop in enumerate(loops)]
    opts=copy.deepcopy(options);opts.update(boundary_mode='evenodd',loop_flags=[1 if depth==0 else 16 if depth==1 else 0 for depth in depths])
    return [HatchEntity(loops[0],holes=loops[1:],layer=layer,**opts)]

def from_selected(doc,entities,options,combined=False,associative=True):
    from .hatch_ui import loop_for
    from .geom_ops import point_in_polygon
    if not entities or any(not (isinstance(e,CircleEntity) or isinstance(e,PolylineEntity) and e.closed) for e in entities):raise ValueError('Select closed circles or closed polylines')
    loops=[loop_for(e) for e in entities];sizes=[abs(sum(a.x*b.y-b.x*a.y for a,b in zip(loop,loop[1:]+loop[:1]))) for loop in loops]
    if any(len(loop)<3 or size<=1e-12 for loop,size in zip(loops,sizes)):raise ValueError('Boundary must enclose an area')
    areas=[dict(boundary=loop,holes=[],source=e) for loop,e in zip(loops,entities)];make(areas,options,doc.layers.current_layer,True,False)
    parents=[min((j for j,other in enumerate(loops) if sizes[j]>sizes[i] and point_in_polygon(loop[0],other)),key=lambda j:sizes[j],default=None) for i,loop in enumerate(loops)]
    def root(i):
        while parents[i] is not None:i=parents[i]
        return i
    grouped=[]
    for i,a in enumerate(areas):
        if parents[i] is None:
            children=[j for j in range(len(areas)) if j!=i and root(j)==i];grouped.append(dict(boundary=a['boundary'],holes=[loops[j] for j in children],source=a['source'],hole_sources=[entities[j].id for j in children]))
    return make(grouped,options,doc.layers.current_layer,combined,associative)

def apply(doc,hatches):
    from .native_io import document_to_dict,entity_to_dict
    from .validation import validate_payload
    from .document import AddEntityCommand
    candidate=document_to_dict(doc);candidate['entities'].extend(entity_to_dict(e) for e in hatches);validate_payload(candidate)
    doc.undo_stack.beginMacro('Hatch areas')
    try:
        for e in hatches:doc.undo_stack.push(AddEntityCommand(doc,e,'Hatch'))
    finally:doc.undo_stack.endMacro()
