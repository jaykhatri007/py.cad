"""Reviewed cleanup, reference diagnostics, recovery policy and batch publishing."""
import copy,hashlib,json,os,shutil,tempfile,time,uuid
from pathlib import Path
from .native_io import document_to_dict,document_from_dict,atomic_write

def fingerprint(doc):return hashlib.sha256(json.dumps(document_to_dict(doc),sort_keys=True,allow_nan=False).encode()).hexdigest()

def strings(value):
    result=set();pending=[value]
    while pending:
        v=pending.pop()
        if isinstance(v,str):result.add(v)
        elif isinstance(v,dict):result.update(v);pending.extend(v.values())
        elif isinstance(v,(list,tuple)):pending.extend(v)
    return result

def cleanup_plan(doc):
    from .precision_edit import protected_ids
    protected=protected_ids(doc);seen={};rows=[]
    from .native_io import entity_to_dict
    for e in doc.entities:
        if not doc.is_editable(e) or e.id in protected:continue
        if e.kind=='LINE' and e.p1.distance_to(e.p2)<=1e-12:rows.append(dict(kind='Object',name=e.id,reason='Zero-length line'));continue
        if e.kind not in ('LINE','ARC','CIRCLE','LWPOLYLINE'):continue
        value=entity_to_dict(e);value['data'].pop('id',None)
        if e.kind=='LINE':
            points=sorted((value['data']['p1'],value['data']['p2']),key=lambda p:json.dumps(p,sort_keys=True));value['data']['p1'],value['data']['p2']=points
        key=json.dumps(value,sort_keys=True)
        if key in seen:rows.append(dict(kind='Object',name=e.id,reason='Exact duplicate of '+seen[key]))
        else:seen[key]=e.id
    reserved=strings(doc.extensions)|strings(doc.constraints)
    required={e.block_name for e in doc.entities if e.kind=='INSERT'}|{n for n,b in doc.blocks.items() if b.is_xref}|(set(doc.blocks)&reserved);pending=list(required)
    while pending:
        block=doc.blocks.get(pending.pop())
        if block is None:continue
        for e in block.entities:
            if e.kind=='INSERT' and e.block_name not in required:required.add(e.block_name);pending.append(e.block_name)
    rows.extend(dict(kind='Block',name=n,reason='Unreferenced definition') for n in sorted(set(doc.blocks)-required))
    entities=doc.entities+[e for b in doc.blocks.values() for e in b.entities];layers={e.layer for e in entities}|reserved|{doc.layers.current_layer,'0'}
    layers|={s['layer'] for b in doc.blocks.values() for s in b.attributes}
    layers|={e['layer'] for e in doc.extrusions}
    rows.extend(dict(kind='Layer',name=n,reason='Unused layer') for n in sorted(set(doc.layers.layers)-layers))
    textstyles={getattr(e,'style_name','Standard') for e in entities if e.kind=='TEXT'}|{s['style_name'] for b in doc.blocks.values() for s in b.attributes}|reserved|{'Standard',doc.current_textstyle}
    dimstyles={getattr(e,'style_name','Standard') for e in entities if 'DIM' in e.kind}|reserved|{'Standard',doc.current_dimstyle}
    rows.extend(dict(kind='Text style',name=n,reason='Unused text definition') for n in sorted(set(doc.textstyles)-textstyles));rows.extend(dict(kind='Dimension style',name=n,reason='Unused dimension definition') for n in sorted(set(doc.dimstyles)-dimstyles))
    return dict(fingerprint=fingerprint(doc),rows=rows,note='Exact duplicates only, including style/link data. Managed/linked objects and references are protected. Remaining block dependencies must stay valid.')

def apply_cleanup(doc,plan,selected):
    if fingerprint(doc)!=plan['fingerprint']:raise ValueError('Drawing changed; rebuild the cleanup preview')
    allowed={(r['kind'],r['name']) for r in cleanup_plan(doc)['rows']};chosen=set(selected)
    if not chosen or not chosen<=allowed:raise ValueError('Choose entries from the current cleanup preview')
    value=document_to_dict(doc);value['entities']=[e for e in value['entities'] if ('Object',e['data']['id']) not in chosen]
    for kind,section in [('Block','blocks'),('Layer','layers'),('Text style','textstyles'),('Dimension style','dimstyles')]:value[section]={k:v for k,v in value[section].items() if (kind,k) not in chosen}
    document_from_dict(value) # no mutation before all dependencies validate
    from PyQt6.QtGui import QUndoCommand
    class Cleanup(QUndoCommand):
        def __init__(self):
            super().__init__('Apply reviewed cleanup');self.before=(list(doc.entities),dict(doc.blocks),copy.deepcopy(doc.layers.layers),copy.deepcopy(doc.textstyles),copy.deepcopy(doc.dimstyles));ids={key for kind,key in chosen if kind=='Object'};self.after=([e for e in doc.entities if e.id not in ids],{k:v for k,v in doc.blocks.items() if ('Block',k) not in chosen},{k:v for k,v in doc.layers.layers.items() if ('Layer',k) not in chosen},{k:v for k,v in doc.textstyles.items() if ('Text style',k) not in chosen},{k:v for k,v in doc.dimstyles.items() if ('Dimension style',k) not in chosen})
        def assign(self,state):doc.entities=list(state[0]);doc.blocks=dict(state[1]);doc.layers.layers=copy.deepcopy(state[2]);doc.textstyles=copy.deepcopy(state[3]);doc.dimstyles=copy.deepcopy(state[4]);doc.spatial_index.invalidate()
        def redo(self):self.assign(self.after)
        def undo(self):self.assign(self.before)
    doc.undo_stack.push(Cleanup())

def reference_report(doc):
    from .xref import reference_path
    from PyQt6.QtGui import QFontDatabase
    rows=[]
    for name,b in doc.blocks.items():
        if b.is_xref:
            try:path=reference_path(doc,b.source_filepath);status='Available' if path.is_file() else 'Missing';resolved=str(path)
            except ValueError as ex:status='Needs relink';resolved=str(ex)
            rows.append(dict(kind='Drawing',name=name,path=resolved,status=status))
    families={f.casefold() for f in QFontDatabase.families()}|{'sans serif','serif','monospace'}
    for name,r in doc.textstyles.items():rows.append(dict(kind='Font',name=name,path=r['font_family'],status='Available' if r['font_family'].casefold() in families else 'Substituted / unavailable'))
    for r in doc.underlays:rows.append(dict(kind='Embedded image / PDF',name=r['name'],path='Embedded PNG',status='Embedded; no external file required'))
    for name,r in doc.extensions.get('productivity',{}).get('tables',{}).items():
        if r['csv_path']:
            try:path=reference_path(doc,r['csv_path']);status='Available' if path.is_file() else 'Missing';resolved=str(path)
            except ValueError as ex:status='Needs relink';resolved=str(ex)
            rows.append(dict(kind='CSV table',name=name,path=resolved,status=status))
    return rows

def substitute_font(doc,name,family):
    from .document import SetAttrCommand
    from .textstyles import validate_style
    if name not in doc.textstyles:raise ValueError('Choose an existing text style')
    after=copy.deepcopy(doc.textstyles);after[name]['font_family']=family;validate_style(after[name]);doc.undo_stack.push(SetAttrCommand(doc,doc,'textstyles',doc.textstyles,after,'Substitute missing font'))

def recover_startup(mw):
    from . import appsettings
    if not appsettings.recovery_file_exists() or not appsettings.get_settings().value('recovery/automatic_restore',True,type=bool):return False
    from .document_tabs import load_recovery_tabs
    from .native_io import load_project
    try:
        # Keep the validated input snapshots until normal confirmed shutdown.
        if not load_recovery_tabs(mw):
            doc=load_project(appsettings.RECOVERY_PATH);doc.filepath=None;doc._force_dirty=True;mw.drawing_tabs.add_document(doc)
        for session in mw.drawing_tabs.sessions:
            doc=session['doc']
            if doc.filepath is None or doc.dirty:doc._force_dirty=True
        mw.command_history.appendPlainText('Recovered prior unsaved session as editable copies. Save to keep the recovered work.');mw.refresh_document_ui();return True
    except (ValueError,OSError) as ex:mw.command_history.appendPlainText('Automatic recovery could not validate snapshots: '+str(ex));return False

def publish_new(stage,target):
    stage,target=Path(stage),Path(target)
    try:os.link(stage,target)
    except FileExistsError:raise ValueError('Output already exists; source and existing output retained')
    except OSError:
        fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        try:
            with os.fdopen(fd,'wb') as stream,stage.open('rb') as source:shutil.copyfileobj(source,stream);stream.flush();os.fsync(stream.fileno())
        except Exception:target.unlink(missing_ok=True);raise

def batch(parent,sources,destination,kind,all_sheets=False,loader=None,exporter=None,progress=None,cancelled=None):
    from .desk_jobs import run
    from .native_io import load_project
    from .dwg_ui import load_dwg
    from .import_ui import load_dxf
    target_dir=Path(destination);target_dir.mkdir(parents=True,exist_ok=True);suffix={'Native':'.pycad','DXF':'.dxf','PDF':'.pdf'}.get(kind)
    if suffix is None:raise ValueError('Choose Native, DXF or PDF')
    rows=[];stop=False
    for index,source in enumerate(sources):
        path=Path(source).resolve();target=target_dir/(path.stem+suffix)
        if stop or cancelled and cancelled():rows.append(dict(source=str(path),output=str(target),status='Not run / cancelled'));stop=True;continue
        if progress:progress(index,len(sources),path.name)
        if target.exists() or target.is_symlink() or target.resolve()==path:rows.append(dict(source=str(path),output=str(target),status='Skipped existing output'));continue
        try:
            if loader:doc=loader(path)
            elif path.suffix.lower()=='.dwg':doc=load_dwg(parent,str(path))
            elif path.suffix.lower()=='.dxf':doc=load_dxf(parent,str(path))
            elif path.suffix.lower()=='.pycad':
                from .import_ui import prepare_display
                result=run(parent,'native_read',dict(source=str(path)))
                doc=prepare_display(parent,result['raw'].encode('utf-8')) if result is not None else None
            else:raise ValueError('Supported inputs: DWG, DXF, PY.cad')
            if doc is None:stop=True;rows.append(dict(source=str(path),output=str(target),status='Cancelled'));continue
            if cancelled and cancelled():stop=True;rows.append(dict(source=str(path),output=str(target),status='Cancelled'));continue
            staging=tempfile.TemporaryDirectory(prefix='.pycad-batch-',dir=target_dir);stage=Path(staging.name)/('output'+suffix)
            try:
                spaces=['Model',*doc.layouts] if all_sheets else ['Model']
                value=exporter(doc,stage,kind,spaces) if exporter else run(parent,'export',dict(stage=str(stage),format=kind,spaces=spaces),document=doc)
                if value is None:stop=True;rows.append(dict(source=str(path),output=str(target),status='Cancelled'));continue
                if cancelled and cancelled():stop=True;rows.append(dict(source=str(path),output=str(target),status='Cancelled'));continue
                publish_new(stage,target);rows.append(dict(source=str(path),output=str(target),status='Completed',warnings=value.get('warnings',[])))
            finally:staging.cleanup()
        except (ValueError,OSError,RuntimeError) as ex:rows.append(dict(source=str(path),output=str(target),status='Failed',error=str(ex)))
    report=dict(format='PY.cad batch report 1',created=time.time(),rows=rows,cancelled=stop)
    report_path=target_dir/('PY.cad-batch-'+uuid.uuid4().hex+'.json');raw=json.dumps(report,indent=2,ensure_ascii=False).encode();fd=os.open(report_path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,'wb') as stream:stream.write(raw)
    report['report_path']=str(report_path);return report

def dashboard(doc,canvas):
    from .drawing_diagnostics import report
    import statistics
    result=report(doc,canvas);samples=list(canvas.__dict__.get('_paint_samples',[]));groups={}
    for row in samples:groups.setdefault(row['kind'],[]).append(row['ms'])
    timings={kind:dict(samples=len(values),median_ms=statistics.median(values),p95_ms=sorted(values)[min(len(values)-1,int(len(values)*.95))]) for kind,values in groups.items()};advice=[]
    if len(doc.entities)>10000:advice.append('Use cached navigation or a regional inspection cache for this drawing.')
    if result['kinds'].get('HATCH',0)>50:advice.append('Dense hatches may use a display approximation; check scale and display mode.')
    if canvas.__dict__.get('drawing_path','cached')=='direct':advice.append('Cached display reduces repeated redraws during ordinary cursor motion.')
    if any(r['median_ms']>33 for kind,r in timings.items() if 'redraw' in kind):advice.append('Full redraw exceeds 33 ms; try cached/progressive display and benchmark GPU settings on your machine.')
    events=result['events'];result.update(timing_groups=timings,recommendations=advice,cache_hits=sum(e['stage']=='cache.hit' for e in events),cache_misses=sum(e['stage']=='cache.miss' for e in events),note='Preview/cached frame timings are separated from full redraws; no physical GPU speed is inferred.')
    return result


def schedule_recovery(mw):
    timer=mw.__dict__.get('_recovery_debounce')
    if timer is None or not hasattr(mw,'drawing_tabs'):return
    state=tuple((id(s['doc']),s['doc'].undo_stack.index()) for s in mw.drawing_tabs.sessions)
    if state!=mw.__dict__.get('_last_recovery_indices'):
        mw._last_recovery_indices=state
        if any(not s['doc'].undo_stack.isClean() for s in mw.drawing_tabs.sessions):timer.start(30000)

def reconcile_saved_recovery(mw):
    from .document_tabs import clear_recovery_tabs
    from . import appsettings
    if any(s['doc'].dirty for s in mw.drawing_tabs.sessions):mw._do_autosave()
    else:clear_recovery_tabs();appsettings.mark_clean_exit()
