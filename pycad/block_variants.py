"""Ordinary derived blocks for explicit visibility and threshold stretch states."""
import copy,math,uuid
from .geometry import Point,LineEntity,PolylineEntity,TextEntity,BlockDefinition,BlockReferenceEntity,ArcEntity
from .architecture import BlockInstallCommand
from .document import SetAttrCommand
from .pro_data import settings,save_section,validate


def variant_entities(block,rule):
    entities=[]
    for source in block.entities:
        if source.layer in rule['hidden_layers']:continue
        e=copy.deepcopy(source);e.id=uuid.uuid4().hex
        def shifted(p):return Point(p.x+(rule['stretch_x'] if p.x>rule['threshold_x'] else 0),p.y+(rule['stretch_y'] if p.y>rule['threshold_y'] else 0))
        if rule['stretch_x'] or rule['stretch_y']:
            if type(e) is LineEntity:e.p1,e.p2=shifted(e.p1),shifted(e.p2)
            elif isinstance(e,PolylineEntity):
                if any(e.bulges):raise ValueError('Stretch curved polylines in the block editor')
                e.points=[shifted(p) for p in e.points]
            elif isinstance(e,TextEntity):e.position=shifted(e.position)
            else:raise ValueError('Stretch states support straight lines/polylines and text; other geometry needs the block editor')
        entities.append(e)
    return entities


def define(doc,base,state,hidden_layers=(),stretch_x=0,stretch_y=0,threshold_x=0,threshold_y=0):
    block=doc.blocks.get(base)
    if block is None or block.is_xref:raise ValueError('Choose a local base block')
    if base in settings(doc).get('variants',{}):raise ValueError('Choose the original base, not another variant')
    rule=dict(base=base,state=state,hidden_layers=list(hidden_layers),stretch_x=stretch_x,stretch_y=stretch_y,threshold_x=threshold_x,threshold_y=threshold_y);validate({'variants':{'test':rule}})
    from .validation import name as valid_name
    name=valid_name(base+'__'+state,'Variant block name');values=copy.deepcopy(settings(doc).get('variants',{}))
    if name in doc.blocks and name not in values:raise ValueError('A block already uses this name')
    derived=BlockDefinition(name,variant_entities(block,rule),attributes=copy.deepcopy(block.attributes));values[name]=rule
    doc.undo_stack.beginMacro('Define block state')
    try:doc.undo_stack.push(BlockInstallCommand(doc,derived));save_section(doc,'variants',values,'Block state settings')
    finally:doc.undo_stack.endMacro()
    return name


def apply(doc,insert,name):
    if not isinstance(insert,BlockReferenceEntity) or insert not in doc.editable_entities():raise ValueError('Select an editable block')
    rule=settings(doc).get('variants',{}).get(name);old=settings(doc).get('variants',{}).get(insert.block_name,{})
    if rule is None or insert.block_name!=rule['base'] and old.get('base')!=rule['base']:raise ValueError('State does not match this base block')
    doc.undo_stack.push(SetAttrCommand(doc,insert,'block_name',insert.block_name,name,'Switch block state'))


def symbol(doc,kind,width=900,height=2100):
    if kind not in ('Door','Window') or any(type(v) not in (int,float) or not math.isfinite(v) or v<=0 for v in (width,height)):raise ValueError('Choose Door/Window and positive dimensions')
    name=f'{kind}_{width:g}_{height:g}'
    if name in doc.blocks:raise ValueError('A block already has these symbol dimensions')
    if kind=='Door':entities=[LineEntity(Point(0,0),Point(0,width)),ArcEntity(Point(0,0),width,0,90)]
    else:
        half=width/18
        entities=[LineEntity(Point(0,y),Point(width,y)) for y in (-half,0,half)]+[LineEntity(Point(x,-half),Point(x,half)) for x in (0,width)]
    attrs=[dict(tag=k,prompt=k,default=str(v),position=[0,0],height=2.5,rotation=0.,visible=False,layer='0',style_name='Standard') for k,v in [('TYPE',kind),('WIDTH',width),('HEIGHT',height)]]
    doc.undo_stack.push(BlockInstallCommand(doc,BlockDefinition(name,entities,attributes=attrs)));return name
