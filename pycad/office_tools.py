"""Office drafting transactions and project publishing."""
import copy
import hashlib
import json
import math
from pathlib import Path
import tempfile
from .office_data import door_recipe, sheet_rows, label

def door_block(name, params):
    from .geometry import ArcEntity, BlockDefinition, LineEntity, Point
    w,a,h,s = (params[k] for k in ('width','angle','hand','swing'))
    closed = 0 if h == 'Left' else 180
    opened = closed + a * (1 if (h=='Left') == (s=='In') else -1)
    theta=math.radians(opened)
    o=Point(0,0)
    leaf=LineEntity(o,Point(w*math.cos(theta),w*math.sin(theta)),linetype='BYLAYER')
    arc=ArcEntity(o,w,min(closed,opened)%360,max(closed,opened)%360,linetype='BYLAYER')
    return BlockDefinition(name,[leaf,arc])

def apply_door(doc, params, point=None, ref=None):
    from .architecture import BlockInstallCommand
    from .document import AddEntityCommand, SetAttrCommand
    from .edit_commands import unique
    from .feature_data import edit_table
    from .geometry import BlockReferenceEntity
    params=door_recipe(**params)
    if ref is not None and (ref.kind!='INSERT' or not doc.is_editable(ref) or not door_params(doc,ref)):
        raise ValueError('Select an editable parametric door.')
    if ref is None and (point is None or not all(math.isfinite(v) and abs(v)<=1e12 for v in (point.x,point.y)) or (doc.layers.is_locked(doc.layers.current_layer) or not doc.layers.is_visible(doc.layers.current_layer))):
        raise ValueError('Choose a valid hinge point and an editable layer.')
    doors=doc.extensions.get('office_doors',{})
    name=next((k for k,v in doors.items() if v==params and k in doc.blocks),None)
    install=name is None
    if install:
        if len(doors)>=1000: raise ValueError('This drawing already has 1,000 door definitions.')
        name=unique('PYCAD_DOOR_'+hashlib.sha256(repr(params).encode()).hexdigest()[:10].upper(),doc.blocks)
    if ref is not None and ref.block_name==name: return ref
    doc.undo_stack.beginMacro('Edit parametric door' if ref else 'Insert parametric door')
    try:
        if install:
            doc.undo_stack.push(BlockInstallCommand(doc,door_block(name,params)))
            edit_table(doc,'office_doors',name,params)
        if ref is None:
            ref=BlockReferenceEntity(name,point,layer=doc.layers.current_layer,linetype='BYLAYER')
            doc.undo_stack.push(AddEntityCommand(doc,ref,'Insert door'))
        else:
            doc.undo_stack.push(SetAttrCommand(doc,ref,'block_name',ref.block_name,name,'Change door geometry'))
    finally: doc.undo_stack.endMacro()
    return ref

def door_params(doc, ref):
    return doc.extensions.get('office_doors',{}).get(getattr(ref,'block_name',None))

def export_office_block(doc,name,path):
    from .coordination import block_preview
    from .native_io import save_project
    from .document_lifecycle import dispose_document
    out=block_preview(doc,name)
    try:
        out.layers=copy.deepcopy(doc.layers)
        out.extensions={area:{k:copy.deepcopy(v) for k,v in doc.extensions.get(area,{}).items()
                              if area=='office_linetypes' or k in out.blocks}
                        for area in ('office_doors','office_linetypes')}
        out.extensions={k:v for k,v in out.extensions.items() if v}
        save_project(out,path,backup=False)
    finally: dispose_document(out)

def catalog_payload(source):
    from .native_io import document_to_dict
    if (len(source.entities)!=1 or source.entities[0].kind!='INSERT' or
            source.entities[0].block_name not in source.blocks):
        raise ValueError('Choose a block saved from the office library.')
    ref=source.entities[0]
    return json.dumps(dict(format='PyCAD clipboard',base=[ref.insertion_point.x,ref.insertion_point.y],drawing=document_to_dict(source)),allow_nan=False).encode()

def insert_catalog(doc, raw, point, use_existing=False):
    from .edit_commands import PasteCommand, prepare_paste
    from .native_io import entity_to_dict, document_to_dict, document_from_dict
    from .document import AddEntityCommand
    from .geometry import BlockReferenceEntity
    if doc.layers.is_locked(doc.layers.current_layer) or not doc.layers.is_visible(doc.layers.current_layer):
        raise ValueError('Choose an editable layer before inserting.')
    if use_existing:
        data=json.loads(raw)['drawing']['entities'][0]['data']
        name=next((n for n in doc.blocks if n.casefold()==data['block_name'].casefold()),None)
        if name is None: raise ValueError('Existing definition is no longer available.')
        ref=BlockReferenceEntity(name,point,layer=doc.layers.current_layer,linetype='BYLAYER')
        data=document_to_dict(doc);data['entities'].append(entity_to_dict(ref));document_from_dict(data)
        doc.undo_stack.push(AddEntityCommand(doc,ref,'Insert existing block'))
        return ref
    imported,tables=prepare_paste(doc,raw,point)
    ref=imported.entities[0]
    ref.layer=doc.layers.current_layer
    ref.linetype='BYLAYER'
    doc.undo_stack.push(PasteCommand(doc,imported,tables))
    return ref

def publish_project(rows,revision,target,progress=None):
    from pypdf import PdfWriter
    from .native_io import load_project, atomic_write
    from .document_lifecycle import dispose_document
    from .plotting import export_pdf
    rows=sheet_rows(rows); revision=label(revision,40)
    if Path(target).resolve() in {Path(r.drawing).resolve() for r in rows}:
        raise ValueError('Choose a PDF destination separate from the source drawings.')
    with tempfile.TemporaryDirectory(prefix='pycad-sheets-') as folder:
        writer=PdfWriter()
        try:
            for i,r in enumerate(rows):
                if progress: progress(i,len(rows))
                doc=load_project(r.drawing)
                try:
                    if r.layout not in doc.layouts: raise ValueError(f'{Path(r.drawing).name}: layout {r.layout} is missing.')
                    sheets=doc.extensions.setdefault('sheets',{})
                    sheets[r.layout]={**dict(project='', title=r.layout, author=''),**sheets.get(r.layout,{}), 'number':r.number,'revision':revision}
                    pdf=Path(folder)/f'{i}.pdf'
                    export_pdf(doc,str(pdf),r.layout)
                    writer.append(str(pdf),import_outline=False)
                finally: dispose_document(doc)
            atomic_write(target,lambda path: writer.write(path))
        finally: writer.close()

def save_linetype(doc,recipe,layer):
    from .feature_data import validate_extensions
    from .document import SetAttrCommand
    from .office_data import linetype_recipe
    recipe=linetype_recipe(**recipe)
    after=copy.deepcopy(doc.extensions)
    after.setdefault('office_linetypes',{})[recipe['name']]=recipe
    validate_extensions(after)
    if layer is not None and layer not in doc.layers.layers:raise ValueError('Layer no longer exists.')
    doc.undo_stack.beginMacro('Save custom linetype')
    try:
        doc.undo_stack.push(SetAttrCommand(doc,doc,'extensions',doc.extensions,after,'Save custom linetype'))
        if layer is not None:doc.edit_layer('linetype',layer,recipe['name'])
    finally:doc.undo_stack.endMacro()

def edit_review(doc,record,review):
    from .feature_data import edit_table,validate_extensions
    from .underlays import UnderlaysCommand,validate_underlays
    uid=record['id']
    if review['space']!='Model' and review['space'] not in doc.layouts:raise ValueError('Review layout is missing.')
    after=[record if r['id']==uid else r for r in doc.underlays]
    if not any(r['id']==uid for r in after):after.append(record)
    validate_underlays(after)
    ext=copy.deepcopy(doc.extensions)
    ext.setdefault('office_reviews',{})[uid]=review
    validate_extensions(ext)
    doc.undo_stack.beginMacro('Edit PDF review')
    try:
        if after!=doc.underlays:
            doc.undo_stack.push(UnderlaysCommand(doc,after,'Set review overlay'))
        edit_table(doc,'office_reviews',uid,review,'Set review comments')
    finally:doc.undo_stack.endMacro()
