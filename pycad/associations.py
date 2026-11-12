"""Persistent dimension/closed-hatch anchors with reversible binding."""
import copy
from .geometry import Point,DimensionEntity,HatchEntity,PolylineEntity,LineEntity,CircleEntity,ArcEntity
from .pro_data import settings,save_section


def anchor(e,name):
    if e is None:raise ValueError('Source is missing')
    if name in ('p1','p2','center','point') and isinstance(getattr(e,name,None),Point):
        p=getattr(e,name);return Point(p.x,p.y)
    if name.startswith('vertex:') and isinstance(e,PolylineEntity):
        try:i=int(name[7:])
        except ValueError:raise ValueError('Use vertex:0, vertex:1, etc.')
        if 0<=i<len(e.points):p=e.points[i];return Point(p.x,p.y)
    if name in ('start','end') and isinstance(e,ArcEntity):return e.endpoints()[int(name=='end')]
    if name=='east' and isinstance(e,(CircleEntity,ArcEntity)):return Point(e.center.x+e.radius,e.center.y)
    raise ValueError('Unsupported source anchor')


def closed_loop(e):
    from .hatch_ui import loop_for
    if not isinstance(e,CircleEntity) and not (isinstance(e,PolylineEntity) and e.closed):raise ValueError('Hatch sources must be circles or closed polylines')
    return loop_for(e)


def validate_hatch(trial):
    from .takeoff_geometry import hatch_area
    from .geom_ops import point_in_polygon
    area=hatch_area(trial)
    if area<=1e-12 or any(not point_in_polygon(loop[0],trial.boundary) for loop in trial.holes):raise ValueError("Hatch islands must remain inside the outer boundary")


def install(doc,target,links,changes,label):
    from .document import SetAttrCommand
    doc.undo_stack.beginMacro(label)
    try:
        for attr,value in changes.items():doc.undo_stack.push(SetAttrCommand(doc,target,attr,getattr(target,attr),value,label))
        save_section(doc,'associations',links,label)
    finally:doc.undo_stack.endMacro()


def bind_dimension(doc,target,sources,anchors):
    if type(target) is not DimensionEntity or target not in doc.editable_entities():raise ValueError('Select an editable linear/radial dimension')
    if len(sources)!=2 or len(anchors)!=2 or target.id in sources:raise ValueError('Choose two source anchors')
    points=[anchor(doc.find_by_id(k),a) for k,a in zip(sources,anchors)]
    links=copy.deepcopy(settings(doc).get('associations',{}));links[target.id]=dict(kind='dimension',sources=list(sources),anchors=list(anchors))
    install(doc,target,links,dict(p1=points[0],p2=points[1],source_line_id=None),'Associate dimension')


def bind_hatch(doc,target,sources):
    from .takeoff_geometry import hatch_area
    if not isinstance(target,HatchEntity) or target not in doc.editable_entities() or not sources or target.id in sources:raise ValueError('Choose an editable hatch and closed boundaries')
    loops=[closed_loop(doc.find_by_id(k)) for k in sources];trial=copy.deepcopy(target);trial.boundary=loops[0];trial.holes=loops[1:];trial.loop_flags=[]
    validate_hatch(trial)
    links=copy.deepcopy(settings(doc).get('associations',{}));links[target.id]=dict(kind='hatch',sources=list(sources),anchors=[])
    install(doc,target,links,dict(boundary=trial.boundary,holes=trial.holes,loop_flags=[],source_entity_id=None,source_hole_ids=[]),'Associate hatch')


def detach(doc,ids):
    links=copy.deepcopy(settings(doc).get('associations',{}))
    for key in ids:links.pop(key,None)
    save_section(doc,'associations',links,'Detach associations')


def sync(doc):
    from .takeoff_geometry import hatch_area
    issues=[]
    for key,r in settings(doc).get('associations',{}).items():
        e=doc.find_by_id(key)
        if e is None:continue
        try:
            if r['kind']=='dimension':
                if type(e) is not DimensionEntity:raise ValueError('Target type changed')
                points=[anchor(doc.find_by_id(k),a) for k,a in zip(r['sources'],r['anchors'])];e.p1,e.p2=points
            else:
                if not isinstance(e,HatchEntity):raise ValueError('Target type changed')
                loops=[closed_loop(doc.find_by_id(k)) for k in r['sources']];trial=copy.deepcopy(e);trial.boundary=loops[0];trial.holes=loops[1:];trial.loop_flags=[]
                validate_hatch(trial)
                e.boundary,e.holes,e.loop_flags=trial.boundary,trial.holes,[]
        except (ValueError,AttributeError,TypeError,IndexError) as ex:issues.append(dict(id=key,reason=str(ex),status='Last valid geometry retained'))
    doc.association_issues=issues
