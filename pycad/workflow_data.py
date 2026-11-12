"""Validated project workflow settings, quantity rules and sheet templates."""
import copy
import fnmatch
import math
from .document import SetAttrCommand


def _validate(table):
    allowed={'takeoff_rules','rate_library','takeoff_specs','sheet_templates','pen_styles','xref_unloaded','xref_sources'}
    if not isinstance(table,dict) or set(table)-allowed:raise ValueError('Invalid workflow settings')
    if any(not isinstance(v,dict) for v in table.values()):raise ValueError('Workflow sections must be tables')
    def text(value):
        if not isinstance(value,str) or len(value)>1000:raise ValueError('Invalid workflow text')
    def number(v,positive=False):
        if type(v) not in (int,float) or not math.isfinite(v) or (v<=0 if positive else v<0):raise ValueError('Invalid workflow number')
    for key,rule in table.get('takeoff_rules',{}).items():
        if not isinstance(rule,dict):raise ValueError('Invalid takeoff rule')
        if set(rule)!={'layer','kind','measurement','factor','description','material','specification'}:raise ValueError('Invalid takeoff rule')
        for field in ('layer','kind','description','material','specification'):text(rule[field])
        if any(len(rule[f])>200 for f in ('description','material')):raise ValueError('Descriptions and materials must be at most 200 characters')
        if not rule['layer'] or not rule['description'] or not rule['material'] or rule['measurement'] not in ('Length','Area','Volume','Count'):raise ValueError('Incomplete takeoff rule')
        number(rule['factor'],True)
    for key,r in table.get('rate_library',{}).items():
        if not isinstance(r,dict):raise ValueError('Invalid rate entry')
        if set(r)!={'description','material','unit','rate','currency','specification'}:raise ValueError('Invalid rate library entry')
        for field in ('description','material','unit','currency','specification'):text(r[field])
        number(r['rate'])
    for value in table.get('takeoff_specs',{}).values():text(value)
    for name,t in table.get('sheet_templates',{}).items():
        if not isinstance(t,dict):raise ValueError('Invalid sheet template')
        if set(t)!={'width','height','margin','scale','title'}:raise ValueError('Invalid sheet template')
        for k in ('width','height','margin','scale'):number(t[k],k!='margin')
        if 2*t['margin']>=min(t['width'],t['height']):raise ValueError('Sheet margin leaves no printable area')
        if set(t['title'])!={'project','title','number','revision','author'}:raise ValueError('Invalid template title')
        for v in t['title'].values():
            text(v)
            if len(v)>255:raise ValueError('Title fields must be at most 255 characters')
    for layer,p in table.get('pen_styles',{}).items():
        from .validation import color
        if set(p)!={'color','width','plot'} or type(p['plot']) is not bool:raise ValueError('Invalid pen style')
        color(p['color']);number(p['width'],True)
    for name,state in table.get('xref_sources',{}).items():
        if set(state)!={'size','modified_ns'} or any(not isinstance(v,str) or not v.isdigit() for v in state.values()):raise ValueError('Invalid reference source metadata')
    for name,state in table.get('xref_unloaded',{}).items():
        if set(state)!={'cache'} or len(state['cache'])!=64 or any(c not in '0123456789abcdef' for c in state['cache']):raise ValueError('Invalid reference cache')
    return table


def save(doc,table,label='Workflow settings'):
    validate(table)
    after=copy.deepcopy(doc.extensions);after['workflow']=copy.deepcopy(table)
    doc.undo_stack.push(SetAttrCommand(doc,doc,'extensions',doc.extensions,after,label))


def proposed_tags(doc):
    from .native_io import document_to_dict,document_from_dict
    from . import boq
    table=doc.extensions.get('workflow',{});validate(table)
    tags={};specs={}
    for entity in doc.editable_entities():
        if entity.id in doc.extensions.get('boq',{}).get('tags',{}):continue
        if entity.id in doc.extensions.get('architecture',{}) or entity.id in doc.extensions.get('building_elements',{}):continue
        for name,r in sorted(table.get('takeoff_rules',{}).items()):
            if fnmatch.fnmatchcase(entity.layer,r['layer']) and (r['kind']=='*' or entity.kind==r['kind'].upper()):
                tags[entity.id]={k:r[k] for k in ('description','material','measurement','factor')}
                specs[entity.id]=r['specification'];break
    clone=document_from_dict(document_to_dict(doc))
    clone.extensions.setdefault('boq',{}).setdefault('tags',{}).update(tags)
    clone.extensions.setdefault('workflow',{}).setdefault('takeoff_specs',{}).update(specs)
    boq.validate_boq(clone.extensions['boq'])
    result=boq.report(clone)
    # Do not apply rules that cannot measure their targets.
    measured={r['source_id'] for r in result['items']}
    tags={k:v for k,v in tags.items() if k in measured};specs={k:v for k,v in specs.items() if k in tags}
    return tags,specs,result


def apply_tags(doc,tags,specs):
    from .boq import validate_boq
    if any((e:=doc.find_by_id(k)) is None or not doc.is_editable(e) for k in tags):raise ValueError('Takeoff preview targets changed; preview again')
    after=copy.deepcopy(doc.extensions)
    after.setdefault('boq',{}).setdefault('tags',{}).update(tags)
    after.setdefault('workflow',{}).setdefault('takeoff_specs',{}).update(specs)
    validate_boq(after['boq']);validate(after['workflow'])
    doc.undo_stack.push(SetAttrCommand(doc,doc,'extensions',doc.extensions,after,'Apply takeoff rules'))


def apply_rates(doc):
    from . import boq
    table=doc.extensions.get('workflow',{});validate(table)
    library=table.get('rate_library',{});currencies={r['currency'] for r in library.values()}
    if len(currencies)>1:raise ValueError('Use one currency per rate library; no currency conversion is assumed')
    rates=dict(doc.extensions.get('boq',{}).get('rates',{}))
    for r in library.values():rates[boq.rate_key(r['description'],r['material'],r['unit'])]=r['rate']
    current=doc.extensions.get('boq',{}).get('settings',{})
    if rates and currencies and current.get('currency','INR') not in currencies:raise ValueError('Rate library currency differs from current rates; no currency conversion is assumed')
    boq.set_rates(doc,rates,next(iter(currencies),current.get('currency','INR')),current.get('waste_percent',0))


def capture_sheet(doc,space,name,denominator=100,margin=10):
    from .sheets import DEFAULT_PRESET
    layout=doc.layouts[space]
    t={'width':layout.page_width,'height':layout.page_height,'margin':margin,'scale':denominator,
       'title':copy.deepcopy(doc.extensions.get('sheets',{}).get(space,dict(project='',title='',number='',revision='',author='')))}
    table=copy.deepcopy(doc.extensions.get('workflow',{}));table.setdefault('sheet_templates',{})[name]=t
    save(doc,table,'Save sheet template')


def create_sheet(doc,template,name):
    from .sheets import title_block,set_viewport_scale
    from .units import UNIT_MM
    table=doc.extensions.get('workflow',{});validate(table);t=table['sheet_templates'][template]
    if doc.units not in UNIT_MM:raise ValueError('Assign drawing units before applying a physical sheet scale')
    doc.undo_stack.beginMacro('Create sheet from template')
    try:
        layout=doc.create_layout(name,t['width'],t['height'])
        for v in layout.viewports:
            for field,value in dict(x=t['margin'],y=t['margin'],width=t['width']-2*t['margin'],height=t['height']-2*t['margin']).items():
                doc.undo_stack.push(SetAttrCommand(doc,v,field,getattr(v,field),value,'Template margins'))
        title_block(doc,name,**t['title'])
        for v in layout.viewports:set_viewport_scale(doc,v,t['scale'])
    finally:doc.undo_stack.endMacro()
    return layout


def validate(table):
    try:return _validate(table)
    except (KeyError,TypeError,AttributeError,OverflowError) as ex:raise ValueError('Invalid workflow configuration: '+str(ex)) from ex
