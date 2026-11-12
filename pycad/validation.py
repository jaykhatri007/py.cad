"""Strict native-format boundary checks before any document is constructed."""
from .linetypes import NAMES as LINETYPE_NAMES

import base64
import hashlib
import math
import re

MAX_ENTITIES = math.inf
# Stored geometry and repeated display instances have different memory costs.
MAX_DISPLAY_ENTITIES = math.inf
MAX_VERTICES = math.inf
MAX_BLOCK_DEPTH = math.inf
MAX_SOURCE_BYTES = 16 * 1024 * 1024
MAX_FILE_BYTES = math.inf
MAX_COORDINATE = 1e12
POINT_FIELDS = {'p1', 'p2', 'center', 'position', 'point', 'insertion_point', 'dim_point'}
POINT_LISTS = {'points', 'boundary', 'clip_boundary'}
COMMON = {'id', 'layer', 'color', 'linetype'}
FIELDS = {
    'LINE': {'p1', 'p2'}, 'RAY': {'p1', 'p2'}, 'XLINE': {'p1', 'p2'},
    'POINT': {'point'}, 'CIRCLE': {'center', 'radius'},
    'ARC': {'center', 'radius', 'start_angle', 'end_angle'},
    'ELLIPSE': {'center', 'major_radius', 'minor_radius', 'rotation'},
    'LWPOLYLINE': {'points', 'closed'}, 'RECTANGLE': {'points', 'closed'},
    'SPLINE': {'points', 'closed'}, 'TEXT': {'position', 'text', 'height', 'rotation'},
    'DIMENSION': {'p1', 'p2', 'dim_point', 'dim_style', 'text_override', 'source_line_id'},
    'CURVED_DIMENSION': {'center', 'p1', 'p2', 'dim_point', 'dim_style', 'text_override', 'source_arc_id'},
    'ORDINATE_DIMENSION': {'p1', 'p2', 'dim_point', 'dim_style', 'text_override', 'source_entity_id', 'source_anchor'},
    'MLEADER': {'position','text','leaders','style_name','scale','rotation'},
    'HATCH': {'boundary', 'pattern', 'angle', 'spacing', 'source_entity_id'},
    'INSERT': {'block_name', 'insertion_point', 'scale', 'rotation', 'mirrored', 'clip_boundary'},
}


def finite(value, label, positive=False):
    if type(value) not in (int, float) or not math.isfinite(value) or abs(value) > MAX_COORDINATE:
        raise ValueError(f'{label} must be a finite number within ±1e12')
    if positive and value <= 0:
        raise ValueError(f'{label} must be positive')
    return value


def name(value, label='Name'):
    if not isinstance(value, str) or not value.strip() or len(value) > 255 or any(ord(c) < 32 for c in value):
        raise ValueError(f'{label} must be 1–255 printable characters')
    return value


def color(value, bylayer=True):
    if not isinstance(value,str) or not (bylayer and value == 'BYLAYER' or re.fullmatch(r'#[0-9a-fA-F]{6}',value)):
        raise ValueError('Color must be #RRGGBB' + (' or BYLAYER' if bylayer else ''))


def point(value):
    if not isinstance(value,dict) or set(value)!={'point'} or not isinstance(value['point'],list) or len(value['point'])!=2:
        raise ValueError('Invalid point record')
    for coordinate in value['point']:finite(coordinate,'Coordinate')


def validate_source(source):
    if source is None:return
    if not isinstance(source,dict) or set(source)!={'filename','sha256','data_base64'}:
        raise ValueError('Invalid imported source archive')
    name(source['filename'],'Source filename')
    content=source['data_base64']
    if not isinstance(content,str) or len(content)>4*((MAX_SOURCE_BYTES+2)//3):
        raise ValueError('Embedded source exceeds 16 MiB')
    try:raw=base64.b64decode(content,validate=True)
    except Exception as ex:raise ValueError('Invalid embedded source encoding') from ex
    if len(raw)>MAX_SOURCE_BYTES or hashlib.sha256(raw).hexdigest()!=source['sha256']:
        raise ValueError('Imported source checksum mismatch')


def validate_payload(data):
    if not isinstance(data,dict) or data.get('format')!='PyCAD' or type(data.get('schema_version')) is not int or data['schema_version'] not in (1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18):
        raise ValueError('Unsupported PY.cad project format/version')
    required={'format','schema_version','units','layers','entities','blocks','layouts'}
    optional={'import_warnings','source_filepath','current_layer','current_linetype','source_archive','dimstyles','current_dimstyle','mleaderstyles','current_mleaderstyle','extrusions','constraints','constraint_settings','cad_standard','unit_settings','underlays'}
    optional |= {'textstyles', 'current_textstyle', 'extensions'}
    optional.add('linetype_scale')
    from .linetypes import validate_scale
    validate_scale(data.get('linetype_scale',1.0))
    from .feature_data import validate_extensions
    validate_extensions(data.get('extensions', {}), data)
    if not required<=set(data) or set(data)-required-optional:
        raise ValueError('Missing or unknown project fields')
    if data['units'] not in ('mm','cm','m','in','ft','unitless'):raise ValueError('Unsupported drawing units')
    from .units import DEFAULT_SETTINGS as UNIT_DEFAULTS, validate_settings as validate_units
    validate_units(data.get('unit_settings', UNIT_DEFAULTS), data['units'])
    from .underlays import validate_underlays
    validate_underlays(data.get('underlays', []))
    layers=data['layers']; blocks=data['blocks']; layouts=data['layouts']
    if not all(isinstance(v,dict) for v in (layers,blocks,layouts)) or '0' not in layers:
        raise ValueError('Invalid layer/block/layout tables; layer 0 is required')
    for key,props in layers.items():
        name(key,'Layer name')
        if not isinstance(props,dict) or not {'color','visible','locked'}<=set(props) or set(props)-{'color','visible','locked','frozen','linetype','lineweight','plot'}:raise ValueError('Invalid layer properties')
        for field in ('frozen','plot'):
            if field in props and type(props[field]) is not bool:raise ValueError('Layer state must be boolean')
        if props.get('linetype','CONTINUOUS') not in LINETYPE_NAMES and props.get('linetype') not in data.get('extensions',{}).get('office_linetypes',{}):raise ValueError('Invalid layer linetype')
        weight=props.get('lineweight',0.25)
        finite(weight,'Lineweight')
        if not 0<=weight<=2.11:raise ValueError('Lineweight must be 0–2.11 mm')
        color(props['color'],False)
        if any(type(props[k]) is not bool for k in ('visible','locked')):raise ValueError('Layer state must be boolean')
    if data.get('current_layer','0') not in layers:raise ValueError('Current layer is missing')
    name(data.get('current_linetype','CONTINUOUS'),'Linetype')
    from .dimstyles import DEFAULT_STYLE, validate_style
    styles=data.get('dimstyles', {'Standard': DEFAULT_STYLE})
    if not isinstance(styles,dict) or 'Standard' not in styles or len(styles)>1000:
        raise ValueError('Invalid dimension style table')
    for key,value in styles.items():
        name(key,'Dimension style name');validate_style(value)
    if data.get('current_dimstyle','Standard') not in styles:
        raise ValueError('Current dimension style is missing')
    from .mleaders import DEFAULT_STYLE as MLEADER_STYLE, validate_style as validate_mleader_style
    mleaderstyles = data.get('mleaderstyles',{'Standard':MLEADER_STYLE})
    if not isinstance(mleaderstyles,dict) or 'Standard' not in mleaderstyles or len(mleaderstyles)>1000:
        raise ValueError('Invalid multileader style table')
    for key,value in mleaderstyles.items():
        name(key,'Multileader style name');validate_mleader_style(value)
    name(data.get('current_mleaderstyle','Standard'),'Current multileader style')
    if data.get('current_mleaderstyle','Standard') not in mleaderstyles:
        raise ValueError('Current multileader style is missing')
    from .textstyles import DEFAULT_STYLE as TEXT_STYLE, validate_style as validate_textstyle
    textstyles = data.get('textstyles', {'Standard': TEXT_STYLE})
    if not isinstance(textstyles, dict) or 'Standard' not in textstyles or len(textstyles) > 1000:
        raise ValueError('Invalid text style table')
    for key, value in textstyles.items():
        name(key, 'Text style name'); validate_textstyle(value)
    name(data.get('current_textstyle', 'Standard'), 'Current text style')
    if data.get('current_textstyle', 'Standard') not in textstyles:
        raise ValueError('Current text style is missing')
    from .model3d import validate_feature
    features=data.get('extrusions',[])
    if not isinstance(features,list) or len(features)>1000:raise ValueError('Too many 3D features (maximum 1,000)')
    feature_ids=set()
    for feature in features:
        validate_feature(feature,layers)
        if feature['id'] in feature_ids:raise ValueError('Duplicate 3D feature ID')
        feature_ids.add(feature['id'])
    total=vertices=0
    ids=set()
    def entities(records):
        nonlocal total,vertices
        if not isinstance(records,list):raise ValueError('Entities must be a list')
        total+=len(records)
        for record in records:
            if not isinstance(record,dict) or set(record)!={'kind','data'} or record['kind'] not in FIELDS:
                raise ValueError('Invalid/unsupported entity record')
            kind=record['kind']; e=record['data']
            if not isinstance(e,dict):raise ValueError('Invalid entity data')
            entity_fields=set(e)-{'transparency','hyperlink'}-({'style_name'} if kind in ('DIMENSION','CURVED_DIMENSION','ORDINATE_DIMENSION','TEXT') else set())
            from .precision import validate_entity_extras
            extras = validate_entity_extras(kind, e)
            if kind == "HATCH":
                vertices += sum(len(loop) for loop in e.get("holes",[]))
            entity_fields -= extras
            if kind in ('LWPOLYLINE','RECTANGLE'):
                entity_fields.discard('width')
                finite(e.get('width',0),'Polyline width')
                if e.get('width',0)<0:raise ValueError('Polyline width must be nonnegative')
            if kind == 'CURVED_DIMENSION':
                entity_fields -= {'source_line_ids', 'line_directions'}
                refs, signs = e.get('source_line_ids', []), e.get('line_directions', [])
                if (not isinstance(refs,list) or not isinstance(signs,list)
                    or len(refs) not in (0,2) or len(signs) != len(refs)
                    or any(type(s) is not int or s not in (-1,1) for s in signs)):
                    raise ValueError('Invalid angular line references or directions')
                for ref in refs:name(ref,'Angular line ID')
                if refs and (refs[0] == refs[1] or e.get('source_arc_id') is not None or e.get('dim_style') != 'angular'):
                    raise ValueError('Angular annotation requires two different lines and no arc link')
            transparency=e.get('transparency',0.0)
            if type(transparency) not in (int,float) or not math.isfinite(transparency) or not 0<=transparency<=90:raise ValueError('Transparency must be 0–90 percent')
            hyperlink=e.get('hyperlink','')
            if not isinstance(hyperlink,str) or len(hyperlink)>2048:raise ValueError('Invalid hyperlink')
            if hyperlink:
                from urllib.parse import urlparse
                parsed=urlparse(hyperlink)
                if parsed.scheme not in ('http','https') or not parsed.netloc or any(ord(c)<32 for c in hyperlink):raise ValueError('Hyperlinks must be HTTP or HTTPS URLs')
            if entity_fields!=COMMON|FIELDS[kind]:raise ValueError(f'Missing or unknown {kind} fields')
            name(e['id'],'Entity ID')
            if e['id'] in ids:raise ValueError('Duplicate entity IDs')
            ids.add(e['id']);color(e['color']);name(e['linetype'],'Linetype')
            if e['layer'] not in layers:raise ValueError('Entity references a missing layer')
            if kind == 'MLEADER':
                from .mleaders import validate_record
                validate_record(e,mleaderstyles)
                vertices += len(e['leaders'])*2
            if kind == 'TEXT':
                name(e.get('style_name', 'Standard'), 'Text style name')
                if e.get('style_name', 'Standard') not in textstyles:
                    raise ValueError('Text references a missing style')
            for key in POINT_FIELDS&set(e):point(e[key])
            if kind in ('RAY','XLINE') and e['p1']['point'] == e['p2']['point']:
                raise ValueError('Construction line direction must be non-zero')
            for key in POINT_LISTS&set(e):
                values=e[key]
                if key=='clip_boundary' and values is None:continue
                if not isinstance(values,list):raise ValueError('Vertices must be a list')
                vertices+=len(values)
                minimum=4 if kind=='RECTANGLE' else 3 if key in ('boundary','clip_boundary') else 2
                if len(values)<minimum:raise ValueError('Not enough vertices')
                if kind=='RECTANGLE' and len(values)!=4:raise ValueError('Rectangle needs four vertices')
                for value in values:point(value)
            for key in {'radius','major_radius','minor_radius','height','spacing'}&set(e):finite(e[key],key,True)
            for key in {'rotation','angle','start_angle','end_angle'}&set(e):finite(e[key],key)
            for key in {'closed','mirrored'}&set(e):
                if type(e[key]) is not bool:raise ValueError(f'{key} must be boolean')
            if kind=='RECTANGLE' and not e['closed']:raise ValueError('Rectangle must be closed')
            if kind=='INSERT':
                finite(e['scale'],'Block scale')
                if e['scale']==0 or e['block_name'] not in blocks:raise ValueError('Invalid block scale or missing block')
            if kind=='TEXT' and (not isinstance(e['text'],str) or len(e['text'])>100000):raise ValueError('Invalid text')
            if kind=='TEXT':
                from .geometry import TextEntity,Point
                candidate=TextEntity(Point(*e['position']['point']),e['text'],e['height'],e['rotation'])
                candidate._text_style=textstyles[e.get('style_name','Standard')]
                for coordinate in candidate.bbox():finite(coordinate,'Text extent')
            if kind in ('DIMENSION','CURVED_DIMENSION','ORDINATE_DIMENSION'):
                if e.get('style_name','Standard') not in styles:raise ValueError('Dimension references a missing style')
                modes = (('angular','arc_length') if kind=='CURVED_DIMENSION' else
                         ('ordinate_x','ordinate_y') if kind=='ORDINATE_DIMENSION' else
                         ('aligned','horizontal','vertical','radius','diameter'))
                if e['dim_style'] not in modes:raise ValueError('Invalid dimension style')
                if e['text_override'] is not None and not isinstance(e['text_override'],str):raise ValueError('Invalid dimension text')
                if kind=='CURVED_DIMENSION':
                    c,a,b = (e[k]['point'] for k in ('center','p1','p2'))
                    if math.dist(c,a) <= 1e-12 or math.dist(c,b) <= 1e-12:raise ValueError('Dimension arms must be nonzero')
                    sweep=(math.atan2(b[1]-c[1],b[0]-c[0])-math.atan2(a[1]-c[1],a[0]-c[0]))%math.tau
                    if sweep < 1e-10 or math.tau-sweep < 1e-10:raise ValueError('Dimension angle must be between 0 and 360 degrees')
                    if math.dist(c,e['dim_point']['point']) <= 1e-12:raise ValueError('Dimension arc radius must be positive')
                if kind == 'ORDINATE_DIMENSION':
                    if e['source_anchor'] not in (None,'p1','p2','point','center') or (e['source_anchor'] is None) != (e['source_entity_id'] is None):
                        raise ValueError('Invalid ordinate source anchor')
            for key in ('source_line_id','source_entity_id','source_arc_id'):
                if e.get(key) is not None:name(e[key],'Source entity ID')
    entities(data['entities'])
    from .constraints import validate_records, validate_settings, DEFAULT_SETTINGS
    validate_records(data.get('constraints', []), {e['data']['id']:e['kind'] for e in data['entities']})
    validate_settings(data.get('constraint_settings', DEFAULT_SETTINGS))
    from .project_tools import validate_standard
    validate_standard(data.get('cad_standard'))
    for key,block in blocks.items():
        name(key,'Block name')
        if not isinstance(block,dict) or set(block)-{'source_scale','attributes'}!={'entities','source_filepath'}:raise ValueError('Invalid block record')
        finite(block.get('source_scale',1.0),'Reference unit scale',True)
        if block['source_filepath'] is not None and not isinstance(block['source_filepath'],str):raise ValueError('Invalid xref path')
        from .smart_blocks import validate_attributes
        validate_attributes(block.get('attributes', []), layers, textstyles)
        entities(block['entities'])
    for records in [data['entities'], *(block['entities'] for block in blocks.values())]:
        kinds = {r['data']['id']:r['kind'] for r in records}
        for record in records:
            e = record['data']
            if record['kind'] == 'CURVED_DIMENSION':
                if any(ref in kinds and kinds[ref] != 'LINE' for ref in e.get('source_line_ids', [])):
                    raise ValueError('Angular source must be a LINE')
            elif record['kind'] == 'ORDINATE_DIMENSION' and e['source_entity_id'] in kinds:
                allowed = {'p1':('LINE',),'p2':('LINE',),'point':('POINT',),'center':('CIRCLE','ARC')}
                if kinds[e['source_entity_id']] not in allowed[e['source_anchor']]:
                    raise ValueError('Ordinate source does not support this anchor')
    from .block_budget import block_order
    block_order(blocks,lambda block:(e['data']['block_name'] for e in block['entities'] if e['kind']=='INSERT'))
    for key,record in layouts.items():
        name(key,'Layout name')
        if key.casefold()=='model' or not isinstance(record,dict) or set(record)!={'page_width','page_height','viewports'}:raise ValueError('Invalid layout record')
        finite(record['page_width'],'Page width',True);finite(record['page_height'],'Page height',True)
        if not isinstance(record['viewports'],list) or len(record['viewports'])>1000:raise ValueError('Too many/invalid viewports')
        for vp in record['viewports']:
            if not isinstance(vp,dict) or set(vp)!={'x','y','width','height','center','scale'}:raise ValueError('Invalid viewport record')
            for attr in ('x','y','width','height','scale'):finite(vp[attr],attr,attr in ('width','height','scale'))
            point({'point':vp['center']})
    if data.get('source_filepath') is not None and not isinstance(data['source_filepath'],str):raise ValueError('Invalid source path')
    warnings=data.get('import_warnings',[])
    if not isinstance(warnings,list) or len(warnings)>10000 or any(not isinstance(w,str) for w in warnings):raise ValueError('Invalid import report')
    validate_source(data.get('source_archive'))
    return data
