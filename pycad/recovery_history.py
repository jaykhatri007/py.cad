"""Owned snapshot history, integrity checks and conservative repair proposals."""
import hashlib
import json
import math
import time
import uuid
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from .native_io import atomic_write,save_project,load_project

POOL=ThreadPoolExecutor(max_workers=1,thread_name_prefix='pycad-history')
_PENDING=None


def folder():
    from .applog import APP_DIR
    p=Path(APP_DIR)/'history';p.mkdir(parents=True,exist_ok=True);return p


def store_bytes(raw,source='',keep=20):
    # Validate snapshots with the native parser before publishing history metadata.
    from .native_io import parse_payload
    parse_payload(raw.decode('utf-8'))
    group=hashlib.sha256(str(source).encode()).hexdigest();sha=hashlib.sha256(raw).hexdigest()
    previous=next((r for r in entries() if r['group']==group),None)
    if previous and previous['sha256']==sha:
        try:checked_path(previous);return previous
        except (OSError,ValueError):pass
    root=folder();token=uuid.uuid4().hex;path=root/(token+'.pycad')
    atomic_write(path,lambda p:Path(p).write_bytes(raw))
    group=hashlib.sha256(str(source).encode()).hexdigest()
    entry=dict(format='PY.cad history 1',file=path.name,source=str(source),group=group,created=time.time(),sha256=hashlib.sha256(raw).hexdigest())
    atomic_write(root/(token+'.json'),lambda p:Path(p).write_text(json.dumps(entry),encoding='utf-8'))
    own=[r for r in entries() if r['group']==group]
    for old in own[max(1,int(keep)):]:
        # Only delete history entries whose owned filename and hash still match.
        try:checked_path(old).unlink();(root/(Path(old['file']).stem+'.json')).unlink()
        except (OSError,ValueError):pass
    return entry


def entries():
    result=[]
    for p in folder().glob('*.json'):
        try:
            r=json.loads(p.read_text());token=p.stem
            if r.get('format')=='PY.cad history 1' and len(token)==32 and all(c in '0123456789abcdef' for c in token) and r.get('file')==token+'.pycad' and type(r.get('created')) in (int,float) and math.isfinite(r['created']) and isinstance(r.get('source'),str) and all(isinstance(r.get(k),str) and len(r[k])==64 and all(c in '0123456789abcdef' for c in r[k]) for k in ('group','sha256')):result.append(r)
        except (ValueError,OSError):pass
    return sorted(result,key=lambda r:r['created'],reverse=True)


def checked_path(entry):
    name=entry['file'];token=Path(name).stem
    if len(token)!=32 or any(c not in '0123456789abcdef' for c in token) or name!=token+'.pycad':raise ValueError('Invalid history entry')
    path=folder()/name
    if hashlib.sha256(path.read_bytes()).hexdigest()!=entry['sha256']:raise ValueError('Recovery snapshot integrity check failed')
    return path


def snapshot(doc,keep=20):
    from .native_io import document_to_dict
    raw=json.dumps(document_to_dict(doc),ensure_ascii=False,allow_nan=False).encode('utf-8')
    return store_bytes(raw,doc.filepath or 'Untitled-'+str(id(doc)),keep)


def archive_autosave(mw):
    global _PENDING
    if _PENDING is not None and not _PENDING.done():return
    from . import appsettings
    settings=appsettings.get_settings();keep=int(settings.value('recovery/history_count',20))
    base=Path(appsettings.RECOVERY_PATH)
    if base.exists():
        # Bytes are captured before queuing so later autosaves cannot change the version.
        raw=base.read_bytes();source=mw.document.filepath or 'Untitled-'+str(id(mw.document))
        job=POOL.submit(store_bytes,raw,source,keep);_PENDING=job
        def finished(f):
            try:f.result()
            except Exception:
                import logging;logging.getLogger(__name__).exception('History archive failed')
        job.add_done_callback(finished)


def restore(entry):
    doc=load_project(checked_path(entry));doc.filepath=None;doc._force_dirty=True
    return doc


def repair_candidates(doc):
    from .geometry import LineEntity
    from .precision_edit import protected_ids
    protected=protected_ids(doc);seen={};result=[]
    for e in doc.entities:
        if not doc.is_editable(e) or e.id in protected:continue
        if isinstance(e,LineEntity) and e.p1.distance_to(e.p2)<=1e-12:
            result.append(dict(id=e.id,reason='Zero-length line'));continue
        if e.kind not in ('LINE','ARC','CIRCLE','LWPOLYLINE'):continue
        data=e.to_dict();data.pop('id',None)
        if e.kind=='LINE':data['p1'],data['p2']=sorted((data['p1'],data['p2']))
        key=json.dumps([e.kind,data],sort_keys=True)
        if key in seen:result.append(dict(id=e.id,reason='Exact duplicate of '+seen[key]))
        else:seen[key]=e.id
    return result


def repair(doc,ids):
    from .native_io import document_to_dict,document_from_dict
    from .precision_edit import ReplaceGeometry
    allowed={r['id'] for r in repair_candidates(doc)}
    if not ids or not set(ids)<=allowed:raise ValueError('Repair proposal is stale or contains protected geometry')
    payload=document_to_dict(doc);payload['entities']=[e for e in payload['entities'] if e['data']['id'] not in ids]
    document_from_dict(payload) # full preflight before any deletion
    targets=[e for e in doc.entities if e.id in ids]
    doc.undo_stack.push(ReplaceGeometry(doc,targets,[],'Apply reviewed audit repair'))
