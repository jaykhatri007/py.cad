"""Hash-checked project archives with source-preserving dependency copies."""
import hashlib,json,zipfile,stat,os,tempfile,shutil
from pathlib import Path,PurePosixPath
from .native_io import document_to_dict,document_from_dict,atomic_write


def digest(raw):return hashlib.sha256(raw).hexdigest()


def safe_name(name):
    p=PurePosixPath(name)
    if not name or p.is_absolute() or '..' in p.parts or '\\' in name or ':' in name or str(p)!=name.rstrip('/') or any(part in ('','.') for part in p.parts):raise ValueError('Unsafe archive path')
    # Refuse Windows aliases/device names as well as POSIX traversal.
    for part in p.parts:
        if part.rstrip(' .')!=part or part.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*[f'COM{i}' for i in range(1,10)],*[f'LPT{i}' for i in range(1,10)]}:raise ValueError('Unsafe cross-platform archive name')
    return p


def checked_files(path,expected_sha=None):
    if expected_sha and digest(Path(path).read_bytes())!=expected_sha.lower():raise ValueError('Archive SHA256 does not match')
    with zipfile.ZipFile(path) as z:
        seen=set();files={}
        for info in z.infolist():
            name=info.filename;safe_name(name);canonical=name.casefold()
            if canonical in seen or stat.S_ISLNK(info.external_attr>>16):raise ValueError('Duplicate or symbolic archive entry')
            seen.add(canonical)
            if not info.is_dir():files[name]=z.read(info)
        return files


def pack(doc,path,fonts=()):
    from .xref import reference_path
    value=document_to_dict(doc);files={};missing=[]
    for block in value['blocks'].values():
        if not block['source_filepath']:continue
        p=reference_path(doc,block['source_filepath'])
        if not p.is_file():missing.append(str(p));continue
        raw=p.read_bytes();rel='references/'+digest(raw)[:16]+'/'+p.name;safe_name(rel);files[rel]=raw;block['source_filepath']=rel
    for record in value.get('extensions',{}).get('productivity',{}).get('tables',{}).values():
        if not record['csv_path']:continue
        source=reference_path(doc,record['csv_path'])
        if not source.is_file():missing.append(str(source));continue
        raw=source.read_bytes();rel='tables/'+digest(raw)[:16]+'/'+source.name;safe_name(rel);files[rel]=raw;record['csv_path']=rel
    if missing:raise ValueError('Missing references: '+'; '.join(missing))
    for source in fonts:
        p=Path(source)
        if p.suffix.lower() not in ('.ttf','.otf','.shx') or not p.is_file():raise ValueError('Choose an existing font file')
        raw=p.read_bytes();name='fonts/'+digest(raw)[:16]+'/'+p.name;safe_name(name);files[name]=raw
    value['source_filepath']=None;files['drawing.pycad']=json.dumps(value,ensure_ascii=False,allow_nan=False).encode()
    manifest=dict(format='PY.cad project bundle 1',files={k:digest(v) for k,v in files.items()},font_families=sorted({v['font_family'] for v in doc.textstyles.values()}),note='Native underlays are embedded. Fonts are explicitly selected; verify redistribution rights. Raw nested external source files may have dependencies outside this manifest; active cached block geometry remains in the native drawing.')
    def write(filename):
        with zipfile.ZipFile(filename,'w',zipfile.ZIP_DEFLATED) as z:
            for name,raw in files.items():z.writestr(name,raw)
            z.writestr('manifest.json',json.dumps(manifest,indent=2))
    atomic_write(path,write);return manifest


def unpack(path,destination):
    dest=Path(destination)
    if dest.exists():raise ValueError('Extract into a new directory')
    files=checked_files(path);manifest=json.loads(files.get('manifest.json',b'{}'))
    if manifest.get('format')!='PY.cad project bundle 1' or set(files)-{'manifest.json'}!=set(manifest.get('files',{})):raise ValueError('Incomplete project bundle')
    for name,sha in manifest['files'].items():
        if digest(files[name])!=sha:raise ValueError('Project file hash mismatch')
    value=json.loads(files['drawing.pycad']);document_from_dict(value)
    # All serialized references must resolve to bundled files, not external paths.
    for block in value['blocks'].values():
        source=block['source_filepath']
        if source and source not in manifest['files']:raise ValueError('Unbundled reference path')
    for record in value.get('extensions',{}).get('productivity',{}).get('tables',{}).values():
        if record['csv_path'] and record['csv_path'] not in manifest['files']:raise ValueError('Unbundled CSV path')
    dest.parent.mkdir(parents=True,exist_ok=True);stage=Path(tempfile.mkdtemp(prefix='.pycad-project-',dir=dest.parent))
    try:
        for name,raw in files.items():p=stage/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
        os.rename(stage,dest)
    finally:
        if stage.exists():shutil.rmtree(stage)
    return dest/'drawing.pycad'


def load_fonts(directory):
    from PyQt6.QtGui import QFontDatabase
    return {str(p):QFontDatabase.addApplicationFont(str(p)) for p in (Path(directory)/'fonts').rglob('*') if p.suffix.lower() in ('.ttf','.otf')}
