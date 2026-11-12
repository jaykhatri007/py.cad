"""Offline portable release staging; keeps previous versions and user data intact."""
import hashlib,json,os,shutil,tempfile,re
from pathlib import Path
from .project_bundle import checked_files
from .native_io import atomic_write
VERSION=r'\d+\.\d+\.\d+'


def stage(archive,sha256,root):
    if not re.fullmatch('[0-9a-fA-F]{64}',sha256):raise ValueError('Enter an independently obtained release SHA256')
    files=checked_files(archive,sha256);prefix='PY.cad/'
    if any(not k.startswith(prefix) for k in files):raise ValueError('Choose the complete PY.cad release ZIP')
    match=re.fullmatch(r'__version__ = "('+VERSION+r')"\s*',files.get(prefix+'pycad/_version.py',b'').decode('utf-8'))
    if not match or prefix+'start.sh' not in files or prefix+'LICENSE' not in files:raise ValueError('Incomplete PY.cad release')
    version=match[1];base=Path(root);base.mkdir(parents=True,exist_ok=True);target=base/version
    if target.exists():raise ValueError('Release already staged; existing version is preserved')
    temporary=Path(tempfile.mkdtemp(prefix='.stage-',dir=base))
    try:
        for name,raw in files.items():
            rel=name[len(prefix):];p=temporary/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
            if p.suffix in ('.sh','.run','.command') or rel.startswith('vendor/libredwg/bin/') and p.name in ('dwgread','dwgwrite','dwg2dxf'):p.chmod(0o755)
        (temporary/'portable-release.json').write_text(json.dumps(dict(version=version,archive_sha256=sha256.lower())))
        os.rename(temporary,target)
    finally:
        if temporary.exists():shutil.rmtree(temporary)
    return version


def select(root,version):
    root=Path(root)
    if not isinstance(version,str) or not re.fullmatch(VERSION,version) or not (root/version/'portable-release.json').is_file():raise ValueError('Choose an existing staged release')
    path=root/'current.json';old=json.loads(path.read_text()) if path.exists() else {};value=dict(current=version,previous=old.get('current') if old.get('current')!=version else old.get('previous'))
    atomic_write(path,lambda p:Path(p).write_text(json.dumps(value)));return root/version


def rollback(root):
    root=Path(root);value=json.loads((root/'current.json').read_text());previous=value.get('previous')
    if not previous:raise ValueError('No previous portable release selected')
    return select(root,previous)


def releases(root):
    root=Path(root)
    return sorted(p.name for p in root.iterdir() if p.is_dir() and re.fullmatch(VERSION,p.name) and (p/'portable-release.json').is_file()) if root.exists() else []
