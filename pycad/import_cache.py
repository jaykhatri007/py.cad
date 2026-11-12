"""Private, versioned DWG import snapshots; content checked on every reuse."""
import hashlib,json,os,time
from pathlib import Path
from .native_io import atomic_write,parse_payload
from ._version import __version__

def folder():
    from .applog import APP_DIR
    p=Path(APP_DIR)/'import-cache';p.mkdir(parents=True,exist_ok=True);return p

def digest_source(source):
    path=Path(source).resolve();before=path.stat();digest=hashlib.sha256()
    with path.open('rb') as stream:
        while data:=stream.read(1<<20):digest.update(data)
    after=path.stat()
    if (before.st_size,before.st_mtime_ns,before.st_ino)!=(after.st_size,after.st_mtime_ns,after.st_ino):raise ValueError('Source changed while checking import cache')
    return digest.hexdigest()

def signature(mode):
    from . import dwg_native,dwg_support
    records=[]
    for name,resolve in [('direct',lambda:dwg_native.tool_path('dwgread')),('compatibility',dwg_support.reader_path)]:
        try:
            p=Path(resolve()).resolve();s=p.stat();records.append([name,str(p),s.st_size,s.st_mtime_ns])
        except Exception:records.append([name,'unavailable'])
    return dict(version=__version__,policy=mode,readers=records)

def key_for(source,digest,policy):return hashlib.sha256(json.dumps([os.path.normcase(str(Path(source).resolve())),digest,policy],sort_keys=True).encode()).hexdigest()

def lookup(root,source,policy):
    root=Path(root);digest=digest_source(source);key=key_for(source,digest,policy);result=dict(hit=False,source_digest=digest,key=key)
    try:
        meta_path=root/(key+'.json');data_path=root/(key+'.pycad')
        if meta_path.is_symlink() or data_path.is_symlink() or meta_path.stat().st_size>65536 or data_path.stat().st_size>512*1024*1024:raise ValueError('Invalid cache record')
        meta=json.loads(meta_path.read_text());raw=data_path.read_bytes()
        if meta.get('format')!='PY.cad import cache 1' or meta.get('key')!=key or meta.get('source_digest')!=digest or hashlib.sha256(raw).hexdigest()!=meta.get('sha256'):raise ValueError('Cache integrity mismatch')
        parse_payload(raw.decode('utf-8'));result.update(hit=True,raw=raw.decode('utf-8'))
    except (OSError,ValueError,UnicodeError,KeyError):pass
    return result

def store(root,source,policy,expected_digest,raw):
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    if digest_source(source)!=expected_digest:return dict(stored=False,reason='Source changed during import')
    payload=parse_payload(raw.decode('utf-8'));archive=payload.get('source_archive')
    if archive and archive.get('sha256')!=expected_digest:return dict(stored=False,reason='Imported source fingerprint differs')
    key=key_for(source,expected_digest,policy);atomic_write(root/(key+'.pycad'),lambda p:Path(p).write_bytes(raw));meta=dict(format='PY.cad import cache 1',key=key,source_digest=expected_digest,sha256=hashlib.sha256(raw).hexdigest(),created=time.time());atomic_write(root/(key+'.json'),lambda p:Path(p).write_text(json.dumps(meta)))
    # Only owned hex-key pairs are eligible for cache retention pruning.
    owned=sorted((p for p in root.glob('*.pycad') if len(p.stem)==64 and all(c in '0123456789abcdef' for c in p.stem)),key=lambda p:p.stat().st_mtime,reverse=True);total=0
    for index,p in enumerate(owned):
        total+=p.stat().st_size
        if index>=10 or total>512*1024*1024:
            p.unlink(missing_ok=True);p.with_suffix('.json').unlink(missing_ok=True)
    return dict(stored=True,key=key)

def clear():
    count=0
    for p in folder().iterdir():
        if p.suffix in ('.json','.pycad') and len(p.stem)==64 and all(c in '0123456789abcdef' for c in p.stem):p.unlink();count+=1
    return count

def load(parent,source,mode,uncached):
    from .appsettings import get_settings
    from .desk_jobs import run
    from .drawing_diagnostics import record
    if not get_settings().value('imports/cache_enabled',True,type=bool):return uncached()
    policy=signature(mode);root=str(folder());start=time.perf_counter()
    try:cached=run(parent,'cache_lookup',dict(root=root,source=str(source),policy=policy))
    except (ValueError,OSError):cached=dict(hit=False)
    if cached is None:return None
    if cached.get('hit'):
        from .import_ui import prepare_display
        document=prepare_display(parent,cached['raw'].encode('utf-8'));document.filepath=str(source);record('cache.hit',source,seconds=time.perf_counter()-start);return document
    record('cache.miss',source);document=uncached()
    if document is not None and cached.get('source_digest'):
        try:run(parent,'cache_store',dict(root=root,source=str(source),policy=policy,expected_digest=cached['source_digest']),document=document)
        except (ValueError,OSError) as ex:record('cache.store.failed',source,error=str(ex))
    return document
