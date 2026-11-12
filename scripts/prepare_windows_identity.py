"""Brand an app-private interpreter copy; original Python binaries stay intact."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pycad._version import __version__


def version_resource(version):
    def align(data): return data + b'\0' * (-len(data) % 4)
    def node(key, value=b'', children=b'', text=False):
        header = struct.pack('<HHH', 0, len(value)//2 if text else len(value), int(text))
        data = align(header + (key+'\0').encode('utf-16le'))
        data = align(data + value) + children
        return struct.pack('<H',len(data)) + data[2:]
    values = {'FileDescription':'PY.cad', 'ProductName':'PY.cad', 'InternalName':'PY.cad',
              'OriginalFilename':'PY.cad.exe', 'CompanyName':'Jay Kundanlal Khatri',
              'FileVersion':version, 'ProductVersion':version,
              'LegalCopyright':'Python Software Foundation and contributors. PY.cad branding by Jay Kundanlal Khatri.'}
    strings = b''.join(node(k, (v+'\0').encode('utf-16le'), text=True) for k,v in values.items())
    table = node('StringFileInfo', children=node('040904B0', children=strings, text=True), text=True)
    variables = node('VarFileInfo', children=node('Translation',struct.pack('<HH',0x409,1200)), text=True)
    parts = [int(v) for v in version.split('.')[:3]] + [0]
    hi,lo = (parts[0]<<16)|parts[1], (parts[2]<<16)|parts[3]
    fixed = struct.pack('<13I',0xfeef04bd,0x10000,hi,lo,hi,lo,0x3f,0,0x40004,1,0,0,0)
    return node('VS_VERSION_INFO', fixed, table+variables)


def icon_resources(data):
    reserved, kind, count = struct.unpack_from('<HHH', data)
    if reserved or kind != 1 or not 1 <= count <= 256:
        raise ValueError('Invalid PY.cad ICO')
    entries = []
    images = []
    for i in range(count):
        width,height,colors,reserved,planes,bits,size,offset = struct.unpack_from('<BBBBHHII',data,6+i*16)
        if offset < 6+count*16 or size <= 0 or offset+size > len(data):
            raise ValueError('Invalid icon image offset')
        resource_id = 101+i
        entries.append(struct.pack('<BBBBHHIH',width,height,colors,reserved,planes,bits,size,resource_id))
        images.append((3, resource_id, data[offset:offset+size]))
    return images + [(14,1,struct.pack('<HHH',0,1,count)+b''.join(entries))]


def update_resources(path, resources):
    kernel = ctypes.WinDLL('kernel32',use_last_error=True)
    begin, update, end = kernel.BeginUpdateResourceW, kernel.UpdateResourceW, kernel.EndUpdateResourceW
    begin.argtypes=[ctypes.c_wchar_p,ctypes.c_int];begin.restype=ctypes.c_void_p
    update.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_uint16,ctypes.c_void_p,ctypes.c_uint32]
    update.restype=ctypes.c_int
    end.argtypes=[ctypes.c_void_p,ctypes.c_int];end.restype=ctypes.c_int
    handle=begin(str(path),False)
    if not handle: raise ctypes.WinError(ctypes.get_last_error())
    committed=False
    try:
        for kind,number,data in resources:
            buffer=ctypes.create_string_buffer(data)
            for language in (0,0x409):
                if not update(handle,kind,number,language,buffer,len(data)):
                    raise ctypes.WinError(ctypes.get_last_error())
        if not end(handle,False):raise ctypes.WinError(ctypes.get_last_error())
        committed=True
    finally:
        if not committed:end(handle,True)


def prepare(install_root, release):
    if sys.platform != 'win32':raise RuntimeError('Windows-only branding preparation')
    install_root=Path(install_root).resolve();release=Path(release).resolve()
    home=Path(sys.base_prefix).resolve()
    if not home.is_relative_to((install_root/'python').resolve()):
        raise RuntimeError('Branding requires the installer-owned managed Python runtime')
    if not release.is_relative_to(install_root/'releases'):
        raise RuntimeError('Invalid private release path')
    source=home/'pythonw.exe'
    if not source.is_file():raise RuntimeError('The managed Python GUI executable is missing')
    original_hash=hashlib.sha256(source.read_bytes()).hexdigest()
    resources=icon_resources((ROOT/'assets/pycad.ico').read_bytes())+[(16,1,version_resource(__version__))]
    branding_hash=hashlib.sha256(b''.join(data for _,_,data in resources)).hexdigest()
    host=home/f'PY.cad-{__version__}-{branding_hash[:10]}.exe'
    marker=host.with_suffix('.identity.json')
    if host.exists():
        metadata=json.loads(marker.read_text(encoding='utf-8'))
        if metadata.get('source_sha256')!=original_hash or metadata.get('sha256')!=hashlib.sha256(host.read_bytes()).hexdigest():
            raise RuntimeError('The branded runtime copy failed its integrity check')
    else:
        fd,name=tempfile.mkstemp(prefix='.pycad-brand-',suffix='.exe',dir=home);os.close(fd)
        temporary=Path(name)
        try:
            shutil.copyfile(source,temporary)
            update_resources(temporary,resources)
            os.replace(temporary,host)
            metadata={'source_sha256':original_hash,'sha256':hashlib.sha256(host.read_bytes()).hexdigest()}
            marker.write_text(json.dumps(metadata),encoding='utf-8')
        finally:
            temporary.unlink(missing_ok=True)
    assert hashlib.sha256(source.read_bytes()).hexdigest()==original_hash
    metadata={**metadata,'format':1,'name':'PY.cad','host':str(host)}
    (release/'windows-app.json').write_text(json.dumps(metadata),encoding='utf-8')


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',required=True);parser.add_argument('--release',required=True)
    args=parser.parse_args();prepare(args.root,args.release)
