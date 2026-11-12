"""Reviewed room modules with hosted openings and associative dimensions."""
import math
from .geometry import Point,DimensionEntity,RectangleEntity
from .document import AddEntityCommand


def plan(rooms,start=(0,0),gap=500,wall_width=200,height=3000,doors=True,dimensions=True):
    if not isinstance(rooms,list) or not 1<=len(rooms)<=100:raise ValueError('Provide 1–100 named rooms with width and depth')
    if len(start)!=2 or any(type(v) not in (int,float) or not math.isfinite(v) for v in (*start,gap,wall_width,height)):raise ValueError('Use finite planning dimensions')
    if gap<wall_width or wall_width<=0 or height<=0:raise ValueError('Use positive wall sizes and separation at least the wall thickness')
    if type(doors) is not bool or type(dimensions) is not bool:raise ValueError('Planner options must be boolean')
    actions=[];x,y=start
    for i,r in enumerate(rooms):
        if not isinstance(r,dict) or set(r)!={'name','width','depth'} or not isinstance(r['name'],str) or not r['name'].strip():raise ValueError('Each room needs name, width and depth')
        w,d=r['width'],r['depth']
        if any(type(v) not in (int,float) or not math.isfinite(v) or v<=2*wall_width for v in (w,d)):raise ValueError('Room sizes must exceed twice the wall thickness')
        if doors and (w<1000 or height<2100):raise ValueError('Default door requires a 1000 mm wall length and 2100 mm height; change sizes or disable doors')
        actions.append(dict(op='planned_room',ref=f'@planned{i}',start=[x,y],width=w,depth=d,wall_width=wall_width,height=height,name=r['name'],number=str(101+i),finish='Paint',door=doors,dimensions=dimensions));x+=w+gap
    from .automation import validate_actions
    return validate_actions(actions)


def execute(doc,a,id_map):
    from .architecture import create_wall,create_room,create_opening
    from .associations import bind_dimension
    if doc.units!='mm':raise ValueError('Room planner currently requires millimetre drawing units')
    # Imported typed plans receive the same semantic validation as the planner form.
    plan([dict(name=a['name'],width=a['width'],depth=a['depth'])],a['start'],a['wall_width'],a['wall_width'],a['height'],a['door'],a['dimensions'])
    x,y=a['start'];w,d=a['width'],a['depth'];points=[Point(x,y),Point(x+w,y),Point(x+w,y+d),Point(x,y+d)]
    walls=[create_wall(doc,p,q,a['wall_width'],a['height']) for p,q in zip(points,points[1:]+points[:1])]
    boundary=RectangleEntity(points[0],points[2],layer=doc.layers.current_layer);doc.undo_stack.push(AddEntityCommand(doc,boundary,'Planned boundary'))
    room=create_room(doc,boundary,a['name'],a['number'],a['finish']);id_map[a['ref']]=room.id
    if a['door']:create_opening(doc,walls[0],w/2,900,2100,'door','D'+a['number'],0)
    if a['dimensions']:
        offset=max(2*a['wall_width'],min(w,d)*.12)
        for anchors,p1,p2,position,orientation in [(('vertex:0','vertex:1'),points[0],points[1],Point(x+w/2,y-offset),'horizontal'),(('vertex:1','vertex:2'),points[1],points[2],Point(x+w+offset,y+d/2),'vertical')]:
            e=DimensionEntity(Point(p1.x,p1.y),Point(p2.x,p2.y),position,dim_style=orientation,layer=doc.layers.current_layer,style_name=doc.current_dimstyle);doc.undo_stack.push(AddEntityCommand(doc,e,'Planned dimension'));bind_dimension(doc,e,[boundary.id,boundary.id],anchors)
