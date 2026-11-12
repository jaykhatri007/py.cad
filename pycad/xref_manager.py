"""Reference cache unload/reload and source-change status, without editing sources."""
import copy
import hashlib
import json
from pathlib import Path
from .document import SetAttrCommand
from .native_io import atomic_write,entity_to_dict,entity_from_dict
from . import workflow_data


def cache_folder():
    from .applog import APP_DIR
    p=Path(APP_DIR)/'xref-cache';p.mkdir(parents=True,exist_ok=True);return p


def unload(doc,name):
    block=doc.blocks[name]
    if not block.is_xref:raise ValueError('Choose an external reference')
    if name in doc.extensions.get('workflow',{}).get('xref_unloaded',{}):return
    raw=json.dumps(dict(format='PY.cad reference cache 1',entities=[entity_to_dict(e) for e in block.entities]),ensure_ascii=False,allow_nan=False).encode('utf-8')
    digest=hashlib.sha256(raw).hexdigest();atomic_write(cache_folder()/(digest+'.json'),lambda p:Path(p).write_bytes(raw))
    table=copy.deepcopy(doc.extensions.get('workflow',{}));table.setdefault('xref_unloaded',{})[name]={'cache':digest}
    doc.undo_stack.beginMacro('Unload reference')
    try:
        workflow_data.save(doc,table,'Reference unload state')
        doc.undo_stack.push(SetAttrCommand(doc,block,'entities',block.entities,[],'Unload reference geometry'))
    finally:doc.undo_stack.endMacro()


def restore_cache(doc,name):
    table=copy.deepcopy(doc.extensions.get('workflow',{}));state=table.get('xref_unloaded',{}).get(name)
    if not state:raise ValueError('Reference is not unloaded')
    workflow_data.validate(table);raw=(cache_folder()/(state['cache']+'.json')).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=state['cache']:raise ValueError('Reference cache integrity failed')
    value=json.loads(raw)
    if value.get('format')!='PY.cad reference cache 1':raise ValueError('Invalid reference cache')
    from .native_io import document_to_dict,document_from_dict
    payload=document_to_dict(doc);payload['blocks'][name]['entities']=value['entities'];payload['extensions']['workflow']['xref_unloaded'].pop(name)
    document_from_dict(payload)
    entities=[entity_from_dict(e) for e in value['entities']];table['xref_unloaded'].pop(name)
    doc.undo_stack.beginMacro('Restore cached reference')
    try:
        workflow_data.save(doc,table,'Reference load state')
        block=doc.blocks[name];doc.undo_stack.push(SetAttrCommand(doc,block,'entities',block.entities,entities,'Restore cached reference geometry'))
    finally:doc.undo_stack.endMacro()


def status(doc):
    from .xref import reference_path
    rows=[]
    unloaded=doc.extensions.get('workflow',{}).get('xref_unloaded',{})
    for name,block in doc.blocks.items():
        if not block.is_xref:continue
        try:
            p=reference_path(doc,block.source_filepath)
            stamp=(p.stat().st_size,p.stat().st_mtime_ns)
            saved=doc.extensions.get('workflow',{}).get('xref_sources',{}).get(name)
            previous=(int(saved['size']),int(saved['modified_ns'])) if saved else getattr(block,'_source_seen',None)
            state='Unloaded (private cache)' if name in unloaded else 'Changed since last check' if previous and previous!=stamp else 'Available'
            if previous is None:block._source_seen=stamp
        except (OSError,ValueError):state='Unloaded; source missing; private cache available' if name in unloaded else 'Missing source; cached drawing geometry retained'
        rows.append(dict(name=name,source=block.source_filepath,status=state,entities=len(block.entities)))
    return rows


def reload_gui(mw,name,path=None):
    from .xref import reference_path
    from .dwg_ui import load_dwg
    from .import_ui import load_dxf
    from .table_commands import LayerStateCommand
    from .unit_conversion import scale_geometry
    block=mw.document.blocks[name];p=Path(path) if path else reference_path(mw.document,block.source_filepath)
    imported=(load_dwg if p.suffix.lower()=='.dwg' else load_dxf)(mw,str(p))
    if imported is None:return False
    styles=copy.deepcopy(mw.document.textstyles);mapping={}
    for key,value in imported.textstyles.items():
        target=key
        if target in styles and styles[target]!=value:target='XREF_'+hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()[:16]
        styles[target]=value;mapping[key]=target
    pending=list(reversed(imported.entities));entities=[]
    from .geometry import BlockReferenceEntity,TextEntity
    while pending:
        e=pending.pop()
        if isinstance(e,BlockReferenceEntity):pending.extend(reversed(e.resolved_entities))
        else:
            clone=e.clone();scale_geometry(clone,block.source_scale)
            if isinstance(clone,TextEntity):clone.style_name=mapping.get(clone.style_name,clone.style_name)
            entities.append(clone)
    from .xref import portable_path
    table=copy.deepcopy(mw.document.extensions.get('workflow',{}));table.get('xref_unloaded',{}).pop(name,None)
    stat=p.stat();table.setdefault('xref_sources',{})[name]={'size':str(stat.st_size),'modified_ns':str(stat.st_mtime_ns)}
    mw.document.undo_stack.beginMacro('Reload external reference')
    try:
        workflow_data.save(mw.document,table,'Reference state')
        mw.document.undo_stack.push(LayerStateCommand(mw.document,{**imported.layers.layers,**mw.document.layers.layers},mw.document.layers.current_layer,'Reference layers'))
        # Keep imported text styles available to the flattened source entities.
        mw.document.undo_stack.push(SetAttrCommand(mw.document,mw.document,'textstyles',mw.document.textstyles,styles,'Reference text styles'))
        if path:mw.document.undo_stack.push(SetAttrCommand(mw.document,block,'source_filepath',block.source_filepath,portable_path(mw.document,p),'Relink reference'))
        mw.document.undo_stack.push(SetAttrCommand(mw.document,block,'entities',block.entities,entities,'Reload reference geometry'))
    finally:mw.document.undo_stack.endMacro()
    block._source_seen=(p.stat().st_size,p.stat().st_mtime_ns)
    mw.refresh_document_ui();return True


def attach_gui(mw,path):
    from .dwg_ui import load_dwg
    from .import_ui import load_dxf
    from .geometry import BlockDefinition,BlockReferenceEntity,TextEntity
    from .document import AddBlockCommand
    from .table_commands import LayerStateCommand
    from .unit_conversion import scale_geometry
    from .units import UNIT_MM
    from .xref import portable_path
    p=Path(path);name=p.stem
    if name in mw.document.blocks:raise ValueError('A block/reference with this name already exists')
    imported=(load_dwg if p.suffix.lower()=='.dwg' else load_dxf)(mw,str(p))
    if imported is None:return None
    scale=UNIT_MM.get(imported.units,1)/UNIT_MM.get(mw.document.units,1)
    styles=copy.deepcopy(mw.document.textstyles);mapping={}
    for key,value in imported.textstyles.items():
        target=key
        if target in styles and styles[target]!=value:target='XREF_'+hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()[:16]
        styles[target]=value;mapping[key]=target
    pending=list(reversed(imported.entities));entities=[]
    while pending:
        e=pending.pop()
        if isinstance(e,BlockReferenceEntity):pending.extend(reversed(e.resolved_entities))
        else:
            clone=e.clone();scale_geometry(clone,scale)
            if isinstance(clone,TextEntity):clone.style_name=mapping.get(clone.style_name,clone.style_name)
            entities.append(clone)
    doc=mw.document;doc.undo_stack.beginMacro('Attach CAD reference')
    try:
        doc.undo_stack.push(LayerStateCommand(doc,{**imported.layers.layers,**doc.layers.layers},doc.layers.current_layer,'Reference layers'))
        doc.undo_stack.push(SetAttrCommand(doc,doc,'textstyles',doc.textstyles,styles,'Reference text styles'))
        doc.undo_stack.push(AddBlockCommand(doc,BlockDefinition(name,entities,source_filepath=portable_path(doc,p),source_scale=scale)))
        table=copy.deepcopy(doc.extensions.get('workflow',{}));stat=p.stat();table.setdefault('xref_sources',{})[name]={'size':str(stat.st_size),'modified_ns':str(stat.st_mtime_ns)}
        workflow_data.save(doc,table,'Reference source metadata')
    finally:doc.undo_stack.endMacro()
    if imported.import_warnings:mw.command_history.appendPlainText('Reference import: '+'; '.join(imported.import_warnings))
    return name


def source_missing(doc,name):
    """A missing/unresolved path is distinct from an available live reference."""
    from .xref import reference_path
    block=doc.blocks[name]
    if not block.is_xref:return False
    try:return not bool(block.source_filepath) or not reference_path(doc,block.source_filepath).is_file()
    except (OSError,ValueError):return True


def bind(doc,names,missing_only=False):
    """Make definitions local in one undo step; retain instances and native geometry.

    Plan/cache validation finishes before mutation. Binding a definition affects
    all its instances. Nested available references remain independently linked.
    """
    names=list(dict.fromkeys(names));table=copy.deepcopy(doc.extensions.get('workflow',{}));workflow_data.validate(table);plans=[]
    for name in names:
        if name not in doc.blocks:raise ValueError('Unknown reference: '+name)
        block=doc.blocks[name]
        if not block.is_xref or (missing_only and not source_missing(doc,name)):continue
        entities=block.entities;state=table.get('xref_unloaded',{}).get(name)
        if state:
            raw=(cache_folder()/(state['cache']+'.json')).read_bytes()
            if hashlib.sha256(raw).hexdigest()!=state['cache']:raise ValueError('Reference cache integrity failed: '+name)
            value=json.loads(raw)
            if value.get('format')!='PY.cad reference cache 1':raise ValueError('Invalid reference cache: '+name)
            # Validate the restored document before changing the current drawing.
            from .native_io import document_to_dict,document_from_dict
            payload=document_to_dict(doc);payload['blocks'][name]['entities']=value['entities'];payload['extensions']['workflow']['xref_unloaded'].pop(name)
            document_from_dict(payload)
            entities=[entity_from_dict(e) for e in value['entities']]
        if not entities:raise ValueError('No cached geometry to bind for '+name+'. Relink or reload its source first.')
        plans.append((name,block,entities,bool(state)))
        for key in ('xref_unloaded','xref_sources'):table.get(key,{}).pop(name,None)
    if not plans:return []
    doc.undo_stack.beginMacro('Bind references to drawing')
    try:
        workflow_data.save(doc,table,'Bound reference metadata')
        for name,block,entities,restore in plans:
            if restore:doc.undo_stack.push(SetAttrCommand(doc,block,'entities',block.entities,entities,'Restore reference geometry'))
            doc.undo_stack.push(SetAttrCommand(doc,block,'source_filepath',block.source_filepath,None,'Make reference local'))
    finally:doc.undo_stack.endMacro()
    return [plan[0] for plan in plans]


def bind_gui(mw,missing=False):
    doc=mw.document
    names=list(doc.blocks) if missing else [e.block_name for e in mw.canvas.selected_entities if getattr(e,'kind','')=='INSERT' and e.block_name in doc.blocks and doc.blocks[e.block_name].is_xref]
    if not names and not missing:raise ValueError('Select an external reference, then use BIND; or choose Bind in Xref Manager.')
    bound=bind(doc,names,missing_only=missing)
    mw.refresh_document_ui();mw.command_history.appendPlainText('Bound to drawing: '+(', '.join(bound) if bound else 'no matching cached references'))
    return bound
