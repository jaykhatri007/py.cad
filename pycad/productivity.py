"""Validated native formula tables, parameters, survey and drawing evidence."""
import copy,csv,hashlib,io,json,math,uuid
from pathlib import Path
from .cell_formulas import calculate,number
from .geometry import Point,LineEntity,TextEntity,PointEntity,BlockDefinition,BlockReferenceEntity


def state(doc,key):return doc.extensions.get('productivity',{}).get(key,{})

def positive(v):
    number(v)
    if v<=0:raise ValueError('Use a positive number')

def text(v):
    if not isinstance(v,str) or not v.strip() or len(v)>255 or any(ord(c)<32 for c in v):raise ValueError('Use a printable name')

def validate(data):
    if not isinstance(data,dict) or set(data)-{'tables','parameters','survey','standards'}:raise ValueError('Invalid productivity data')
    for section,values in data.items():
        if not isinstance(values,dict) or len(values)>1000:raise ValueError('Invalid productivity section')
        for key,r in values.items():
            text(key)
            if not isinstance(r,dict):raise ValueError('Invalid record')
            if section=='tables':
                if set(r)!={'cells','position','cell_width','row_height','csv_path','schedule'}:raise ValueError('Invalid table record')
                cells=r['cells']
                if not isinstance(cells,list) or not 1<=len(cells)<=2000 or any(not isinstance(row,list) or not 1<=len(row)<=100 for row in cells) or len({len(row) for row in cells})!=1:raise ValueError('Use a rectangular table up to 2000 rows / 100 columns')
                if any(not isinstance(v,str) or len(v)>10000 for row in cells for v in row):raise ValueError('Invalid table cell')
                if not isinstance(r['position'],list) or len(r['position'])!=2:raise ValueError('Invalid table position')
                for n in r['position']:number(n)
                positive(r['cell_width']);positive(r['row_height'])
                if r['cell_width']<=r['row_height']*.3:raise ValueError('Column too narrow')
                if not isinstance(r['csv_path'],str) or r['schedule'] not in ('','BOQ','Blocks','Rooms'):raise ValueError('Invalid table source')
                calculate(cells)
            elif section=='parameters':
                if set(r)!={'base','width_name','height_name','base_width','base_height','width','height','rotation','threshold_x','threshold_y'}:raise ValueError('Invalid block parameters')
                for k in ('base','width_name','height_name'):text(r[k])
                if key==r['base'] or r['width_name']==r['height_name']:raise ValueError('Use a separate base and distinct parameter names')
                for k in ('base_width','base_height','width','height'):positive(r[k])
                for k in ('rotation','threshold_x','threshold_y'):number(r[k])
            elif section=='survey':
                if set(r)!={'crs','zone','north','origin_e','origin_n','scale','rotation'} or r['crs'] not in ('Local','WGS84 UTM') or type(r['north']) is not bool or type(r['zone']) is not int or not 1<=r['zone']<=60:raise ValueError('Invalid coordinate system')
                for k in ('origin_e','origin_n','rotation'):number(r[k])
                positive(r['scale'])
            elif section=='standards':
                if set(r)!={'layers','text_height','dimension_styles','tolerance'} or not isinstance(r['layers'],dict) or not isinstance(r['dimension_styles'],list):raise ValueError('Invalid office standard')
                positive(r['text_height']);number(r['tolerance'])
                if r['tolerance']<0:raise ValueError('Invalid tolerance')
                from .validation import color
                for name,props in r['layers'].items():
                    text(name)
                    if not isinstance(props,dict) or set(props)!={'color','lineweight'}:raise ValueError('Invalid layer standard')
                    color(props['color']);positive(props['lineweight'])
                for name in r['dimension_styles']:text(name)
    return data

def save(doc,key,records,label):
    from .feature_data import edit_table
    validate({key:records});edit_table(doc,'productivity',key,records,label)

def read_csv(path):
    path=Path(path)
    if path.stat().st_size>16*1024*1024:raise ValueError('CSV exceeds 16 MiB')
    rows=list(csv.reader(io.StringIO(path.read_text(encoding='utf-8-sig'))))
    if not rows:raise ValueError('CSV is empty')
    width=max(map(len,rows));return [row+['']*(width-len(row)) for row in rows]

def schedule_cells(doc,kind):
    if kind=='Rooms':
        from .architecture import room_metrics
        from .units import UNIT_MM
        factor=UNIT_MM.get(doc.units)
        area_factor=(factor/1000)**2 if factor else 1.
        length_factor=factor/1000 if factor else 1.
        rows=[['Room','Number','Area (m²)' if factor else 'Area (units²)','Perimeter (m)' if factor else 'Perimeter (units)']]
        for key,r in doc.extensions.get('architecture',{}).items():
            if r['kind']=='room':
                _,area,perimeter=room_metrics(doc,r)
                rows.append([r['name'],r['number'],f'{area*area_factor:.10g}',f'{perimeter*length_factor:.10g}'])
        return rows
    if kind=='BOQ':
        from .revisions import quantity_rows
        rows=quantity_rows(doc,synchronize=False)['rows']
        return [['Description','Unit','Quantity','Rate','Cost']]+[[r['description'],r['unit'],f"{r['adjusted_quantity']:.10g}",'' if r['rate'] is None else f"{r['rate']:.10g}",'' if r['adjusted_cost'] is None else f"{r['adjusted_cost']:.10g}"] for r in rows]
    counts={}
    for e in doc.entities:
        if e.kind=='INSERT' and e.block_name not in state(doc,'tables'):counts[e.block_name]=counts.get(e.block_name,0)+1
    return [['Block','Count']]+[[k,str(v)] for k,v in sorted(counts.items())]

def table_entities(r,cells):
    values=calculate(cells);w,h=r['cell_width'],r['row_height'];rows,cols=len(values),len(values[0]);out=[]
    for y in range(rows+1):out.append(LineEntity(Point(0,-y*h),Point(cols*w,-y*h)))
    for x in range(cols+1):out.append(LineEntity(Point(x*w,0),Point(x*w,-rows*h)))
    for y,row in enumerate(values):
        for x,v in enumerate(row):out.append(TextEntity(Point(x*w+h*.15,-y*h-h*.7),f'{v:.10g}' if isinstance(v,(int,float)) else v,height=h*.4,wrap_width=w-h*.3))
    for e in out:
        for p in e.endpoints():number(p.x);number(p.y)
    return out

def preflight(doc,block,section,name,r,insert=None):
    from .native_io import document_to_dict,entity_to_dict
    from .validation import validate_payload
    v=document_to_dict(doc);v['blocks'][name]=dict(entities=[entity_to_dict(e) for e in block.entities],attributes=copy.deepcopy(block.attributes),source_filepath=None,source_scale=1.)
    v['extensions'].setdefault('productivity',{}).setdefault(section,{})[name]=copy.deepcopy(r)
    if insert:v['entities'].append(entity_to_dict(insert))
    validate_payload(v)

def create_table(doc,name,cells,position=(0,0),cell_width=35,row_height=8,csv_path='',schedule=''):
    from .architecture import BlockInstallCommand
    from .document import AddEntityCommand
    if name in doc.blocks:raise ValueError('Block/table name already exists')
    r=dict(cells=cells,position=list(position),cell_width=cell_width,row_height=row_height,csv_path=csv_path,schedule=schedule);validate({'tables':{name:r}})
    block=BlockDefinition(name,table_entities(r,schedule_cells(doc,schedule) if schedule else cells));insert=BlockReferenceEntity(name,Point(*position));preflight(doc,block,'tables',name,r,insert)
    doc.undo_stack.beginMacro('Drawing table')
    try:
        doc.undo_stack.push(BlockInstallCommand(doc,block));doc.undo_stack.push(AddEntityCommand(doc,insert,'Place table'));save(doc,'tables',{**state(doc,'tables'),name:r},'Link table')
    finally:doc.undo_stack.endMacro()

def set_table(doc,name,r):
    if name not in state(doc,'tables'):raise ValueError('Choose a linked table')
    validate({'tables':{name:r}});preflight(doc,BlockDefinition(name,table_entities(r,schedule_cells(doc,r['schedule']) if r['schedule'] else r['cells'])),'tables',name,r);save(doc,'tables',{**state(doc,'tables'),name:r},'Update table')

def parameter_attributes(doc,r):
    out=copy.deepcopy(doc.blocks[r['base']].attributes);a=math.radians(r['rotation']);co,si=math.cos(a),math.sin(a)
    for spec in out:
        x,y=spec['position'];x+=r['width']-r['base_width'] if x>r['threshold_x'] else 0;y+=r['height']-r['base_height'] if y>r['threshold_y'] else 0
        spec['position']=[number(x*co-y*si),number(x*si+y*co)];spec['rotation']+=r['rotation']
    return out

def parameter_entities(doc,name,r):
    from .block_variants import variant_entities
    out=variant_entities(doc.blocks[r['base']],dict(hidden_layers=[],stretch_x=r['width']-r['base_width'],stretch_y=r['height']-r['base_height'],threshold_x=r['threshold_x'],threshold_y=r['threshold_y']))
    for source,e in zip(doc.blocks[r['base']].entities,out):
        e.id=uuid.uuid5(uuid.NAMESPACE_URL,'pycad-param:'+name+':'+source.id).hex
        if r['rotation']:e.rotate_around(Point(0,0),r['rotation'])
        for point in e.endpoints():number(point.x);number(point.y)
    return out

def define_parameters(doc,name,r):
    from .architecture import BlockInstallCommand
    validate({'parameters':{name:r}})
    if r['base'] not in doc.blocks or doc.blocks[r['base']].is_xref or r['base'] in state(doc,'parameters') or r['base'] in state(doc,'tables'):raise ValueError('Choose an ordinary local base')
    if name in doc.blocks and name not in state(doc,'parameters'):raise ValueError('Block name already exists')
    block=BlockDefinition(name,parameter_entities(doc,name,r),attributes=parameter_attributes(doc,r));preflight(doc,block,'parameters',name,r)
    doc.undo_stack.beginMacro('Block parameters')
    try:doc.undo_stack.push(BlockInstallCommand(doc,block));save(doc,'parameters',{**state(doc,'parameters'),name:r},'Named parameters')
    finally:doc.undo_stack.endMacro()

def sync(doc):
    from .native_io import entity_to_dict
    errors=[]
    for name,r in state(doc,'parameters').items():
        if name not in doc.blocks or r['base'] not in doc.blocks:continue
        try:
            stamp=hashlib.sha256(json.dumps([r,[entity_to_dict(e) for e in doc.blocks[r['base']].entities],doc.blocks[r['base']].attributes],sort_keys=True).encode()).hexdigest()
            if getattr(doc.blocks[name],'_productivity_stamp',None)==stamp:continue
            entities=parameter_entities(doc,name,r);attrs=parameter_attributes(doc,r);doc.blocks[name].entities=entities;doc.blocks[name].attributes=attrs;doc.blocks[name]._productivity_stamp=stamp
        except ValueError as e:errors.append(dict(block=name,error=str(e)))
    for name,r in state(doc,'tables').items():
        if name not in doc.blocks:continue
        try:
            cells=schedule_cells(doc,r['schedule']) if r['schedule'] else r['cells'];stamp=json.dumps([r,cells],sort_keys=True)
            if getattr(doc.blocks[name],'_productivity_stamp',None)==stamp:continue
            out=table_entities(r,cells)
            for i,e in enumerate(out):e.id=uuid.uuid5(uuid.NAMESPACE_URL,'pycad-table:'+name+':'+str(i)).hex
            doc.blocks[name].entities=out;doc.blocks[name]._productivity_stamp=stamp
        except ValueError as e:errors.append(dict(table=name,error=str(e)))
    doc.productivity_issues=errors

def office_standard(doc):return dict(layers={k:dict(color=v['color'],lineweight=v.get('lineweight',.25)) for k,v in doc.layers.layers.items()},text_height=doc.textstyles.get(doc.current_textstyle,{}).get('height',2.5),dimension_styles=list(doc.dimstyles),tolerance=.001)

def check_standard(doc,r):
    validate({'standards':{'office':r}});issues=[]
    for name,v in doc.layers.layers.items():
        expected=r['layers'].get(name)
        if expected is None:issues.append(dict(object=name,kind='Layer name',actual='Not in office standard'));continue
        for k in ('color','lineweight'):
            actual=v.get(k,.25);target=expected[k]
            if (abs(actual-target)>r['tolerance'] if k=='lineweight' else str(actual).lower()!=str(target).lower()):issues.append(dict(object=name,kind=k,actual=actual,expected=target))
    for e in doc.entities+[e for b in doc.blocks.values() for e in b.entities]:
        if e.kind=='TEXT' and abs(e.height-r['text_height'])>r['tolerance']:issues.append(dict(source_id=e.id,kind='Text height',actual=e.height,expected=r['text_height']))
        if 'DIM' in e.kind and getattr(e,'style_name','Standard') not in r['dimension_styles']:issues.append(dict(source_id=e.id,kind='Dimension style',actual=getattr(e,'style_name','Standard')))
    return issues

def survey_config():return dict(crs='Local',zone=43,north=True,origin_e=0.,origin_n=0.,scale=1.,rotation=0.)

def utm(lon,lat,zone,north):
    number(lon);number(lat)
    if type(zone) is not int or not 1<=zone<=60 or type(north) is not bool or not -80<=lat<=84 or not -180<=lon<=180 or (lat>=0)!=north:raise ValueError('Invalid WGS84 UTM zone / hemisphere / latitude')
    central=(zone-1)*6-177
    if abs(lon-central)>9:raise ValueError('Point too far from UTM zone')
    a=6378137.;e2=.0066943799901413165;ep=e2/(1-e2);k=.9996;phi=math.radians(lat);dl=math.radians(lon-central);n=a/math.sqrt(1-e2*math.sin(phi)**2);t=math.tan(phi)**2;c=ep*math.cos(phi)**2;aa=math.cos(phi)*dl
    m=a*((1-e2/4-3*e2**2/64-5*e2**3/256)*phi-(3*e2/8+3*e2**2/32+45*e2**3/1024)*math.sin(2*phi)+(15*e2**2/256+45*e2**3/1024)*math.sin(4*phi)-35*e2**3/3072*math.sin(6*phi))
    return 500000+k*n*(aa+(1-t+c)*aa**3/6+(5-18*t+t*t+72*c-58*ep)*aa**5/120),k*(m+n*math.tan(phi)*(aa*aa/2+(5-t+9*c+4*c*c)*aa**4/24+(61-58*t+t*t+600*c-330*ep)*aa**6/720))+(0 if north else 10000000)

def to_drawing(e,n,cfg):
    a=math.radians(cfg['rotation']);x=(e-cfg['origin_e'])/cfg['scale'];y=(n-cfg['origin_n'])/cfg['scale'];return Point(x*math.cos(a)-y*math.sin(a),x*math.sin(a)+y*math.cos(a))

def to_survey(p,cfg):
    a=math.radians(-cfg['rotation']);return cfg['origin_e']+(p.x*math.cos(a)-p.y*math.sin(a))*cfg['scale'],cfg['origin_n']+(p.x*math.sin(a)+p.y*math.cos(a))*cfg['scale']

def survey_entities(rows,cfg,geographic=False,label_height=2.5):
    validate({'survey':{'drawing':cfg}});positive(label_height);out=[];seen=set()
    for row in rows:
        if len(row) not in (3,4):raise ValueError('Use ID,Easting,Northing[,Elevation] or ID,Longitude,Latitude[,Elevation]; no header')
        name=row[0].strip();text(name)
        if name in seen:raise ValueError('Duplicate survey ID')
        seen.add(name);east,north=float(row[1]),float(row[2]);number(east);number(north)
        if geographic:
            if cfg['crs']!='WGS84 UTM':raise ValueError('Choose WGS84 UTM for longitude / latitude')
            east,north=utm(east,north,cfg['zone'],cfg['north'])
        point=to_drawing(east,north,cfg);label=f'{name} E {east:.3f} N {north:.3f}'
        if len(row)==4 and row[3].strip():label+=f' Z {number(float(row[3])):.3f}'
        out.extend([PointEntity(point),TextEntity(Point(point.x+label_height*.5,point.y+label_height*.5),label,height=label_height)])
    if not out:raise ValueError('No survey points')
    return out

def bearing(a,b,cfg):
    ea,na=to_survey(a,cfg);eb,nb=to_survey(b,cfg);de,dn=eb-ea,nb-na
    return dict(azimuth_degrees=math.degrees(math.atan2(de,dn))%360,quadrant_bearing=('N' if dn>=0 else 'S')+f' {math.degrees(math.atan2(abs(de),abs(dn))):.6f}° '+('E' if de>=0 else 'W'),distance=math.hypot(de,dn),units='survey units; metres for UTM')

def overlay(doc):
    from .revisions import quantity_rows
    value=quantity_rows(doc,synchronize=False);colors={e.id:'#d66565' for e in doc.entities};status={e.id:'Unmeasured' for e in doc.entities}
    for r in value['rows']:colors[r['source_id']]='#45b882' if r['rate'] is not None else '#efb84d';status[r['source_id']]='Measured / priced' if r['rate'] is not None else 'Measured / unpriced'
    return dict(colors=colors,status=status,rows=value['rows'],warnings=value['warnings'])

def explain(doc,entities,question='',failure=''):
    from .native_io import entity_to_dict
    from .revisions import quantity_rows
    try:quantities={r['source_id']:r for r in quantity_rows(doc)['rows']};warning=''
    except ValueError as e:quantities={};warning=str(e)
    rows=[]
    for e in entities:
        r=dict(source_id=e.id,type=e.kind,layer=e.layer,geometry=entity_to_dict(e)['data'],explanation=f'{e.kind} on layer {e.layer}.')
        if e.kind=='INSERT':r['explanation']+=f' Block {e.block_name}; instance transforms apply.'
        if e.kind=='HATCH':r['explanation']+=f' Pattern {e.pattern}, scale {e.pattern_scale:g}, {len(e.holes)} additional loops.'
        if e.id in quantities:
            q=quantities[e.id];r['quantity']=q;r['explanation']+=f" Gross {q['gross_quantity']:g} {q['unit']}; deduction {q['deduction']:g}; waste {q['waste_quantity']:g}; final {q['adjusted_quantity']:g}. Cost = final quantity × rate."
        else:r['explanation']+=' No BOQ measurement assigned.'
        rows.append(r)
    advice=''
    for words,message in [(('hatch','island','boundary'),'Check closed boundaries, crossings, touching islands and gap tolerance.'),(('block','stretch'),'Check the local base and straight geometry supported by threshold stretch.'),(('cell','formula'),'Check addresses, circular references and numeric inputs.'),(('dwg','dxf','import'),'Inspect DWGREPORT and the exact source/import error.'),(('select','selection'),'Check editable selection, current space and locked layers.')]:
        if any(word in failure.lower() for word in words):advice=message;break
    return dict(mode='Grounded offline explanation; no network request',question=question,rows=rows,quantity_warning=warning,failure=failure,next_check=advice or ('Inspect the exact command requirements and error.' if failure else ''),note='Explains saved evidence; does not infer unknown design intent or certify quantities.')
