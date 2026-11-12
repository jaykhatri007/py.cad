"""Windows Known Folder shortcuts with logo and matching AppUserModelID.

Uses Shell COM directly; no extra Python packages or shell command parsing.
"""
import argparse
import ctypes as C
import os
from pathlib import Path
import sys
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from pycad.windows_identity import APP_USER_MODEL_ID


class GUID(C.Structure):
    _fields_=[('data',C.c_ubyte*16)]
    def __init__(self,value):
        super().__init__();self.data[:]=uuid.UUID(value).bytes_le


class PROPERTYKEY(C.Structure):
    _fields_=[('fmtid',GUID),('pid',C.c_uint32)]


class PROPVARIANT(C.Structure):
    _fields_=[('vt',C.c_uint16),('r1',C.c_uint16),('r2',C.c_uint16),('r3',C.c_uint16),
              ('pointer',C.c_void_p),('extra',C.c_uint64)]


def checked(result):
    if result<0:raise OSError(f'Windows shortcut operation failed: HRESULT 0x{result & 0xffffffff:08x}')


def method(pointer,index,*args):
    table=C.cast(pointer,C.POINTER(C.POINTER(C.c_void_p))).contents
    return C.WINFUNCTYPE(C.c_long,C.c_void_p,*args)(table[index])


def query(pointer,iid):
    result=C.c_void_p();guid=GUID(iid)
    checked(method(pointer,0,C.POINTER(GUID),C.POINTER(C.c_void_p))(pointer,C.byref(guid),C.byref(result)))
    return result


def release(pointer):
    if pointer:method(pointer,2)(pointer)


def known_folder(kind):
    guid=GUID({'Desktop':'b4bfcc3a-db2c-424c-b029-7fe99a87c641',
               'Programs':'a77f5d77-2e2b-44c3-a6a2-aba601054a51'}[kind])
    shell=C.WinDLL('shell32');ole=C.WinDLL('ole32')
    call=shell.SHGetKnownFolderPath
    call.argtypes=[C.POINTER(GUID),C.c_uint32,C.c_void_p,C.POINTER(C.c_void_p)];call.restype=C.c_long
    value=C.c_void_p();checked(call(C.byref(guid),0,None,C.byref(value)))
    try:return Path(C.wstring_at(value))
    finally:
        ole.CoTaskMemFree.argtypes=[C.c_void_p];ole.CoTaskMemFree(value)


def shell_link():
    ole=C.WinDLL('ole32');call=ole.CoCreateInstance
    call.argtypes=[C.POINTER(GUID),C.c_void_p,C.c_uint32,C.POINTER(GUID),C.POINTER(C.c_void_p)];call.restype=C.c_long
    cls=GUID('00021401-0000-0000-c000-000000000046')
    iid=GUID('000214f9-0000-0000-c000-000000000046')
    result=C.c_void_p();checked(call(C.byref(cls),None,1,C.byref(iid),C.byref(result)))
    return result


def create_link(path,launcher,arguments,icon,working_directory):
    link=shell_link();store=persist=None
    try:
        for index,value in ((20,str(launcher)),(11,arguments),(7,'PY.cad desktop CAD'),(9,str(working_directory))):
            checked(method(link,index,C.c_wchar_p)(link,value))
        checked(method(link,17,C.c_wchar_p,C.c_int)(link,str(icon),0))
        checked(method(link,15,C.c_int)(link,1))
        store=query(link,'886d8eeb-8cf2-4446-8d02-cdba1dbdcf99')
        key=PROPERTYKEY(GUID('9f4c2855-9f79-4b39-a8d0-e1d42de1d5f3'),5)
        text=C.create_unicode_buffer(APP_USER_MODEL_ID)
        value=PROPVARIANT(31,0,0,0,C.cast(text,C.c_void_p),0)
        checked(method(store,6,C.POINTER(PROPERTYKEY),C.POINTER(PROPVARIANT))(store,C.byref(key),C.byref(value)))
        persist=query(link,'0000010b-0000-0000-c000-000000000046')
        checked(method(persist,6,C.c_wchar_p,C.c_int)(persist,str(path),True))
    finally:
        release(persist);release(store);release(link)


def read_link(path):
    link=shell_link();persist=store=None
    try:
        persist=query(link,'0000010b-0000-0000-c000-000000000046')
        checked(method(persist,5,C.c_wchar_p,C.c_uint32)(persist,str(path),0))
        target=C.create_unicode_buffer(32768);icon=C.create_unicode_buffer(32768)
        arguments=C.create_unicode_buffer(32768);index=C.c_int()
        checked(method(link,3,C.c_wchar_p,C.c_int,C.c_void_p,C.c_uint32)(link,target,len(target),None,4))
        checked(method(link,16,C.c_wchar_p,C.c_int,C.POINTER(C.c_int))(link,icon,len(icon),C.byref(index)))
        checked(method(link,10,C.c_wchar_p,C.c_int)(link,arguments,len(arguments)))
        store=query(link,'886d8eeb-8cf2-4446-8d02-cdba1dbdcf99')
        key=PROPERTYKEY(GUID('9f4c2855-9f79-4b39-a8d0-e1d42de1d5f3'),5)
        value=PROPVARIANT()
        checked(method(store,5,C.POINTER(PROPERTYKEY),C.POINTER(PROPVARIANT))(store,C.byref(key),C.byref(value)))
        try:
            app_id=C.wstring_at(value.pointer) if value.vt==31 and value.pointer else ''
        finally:
            ole=C.WinDLL('ole32');ole.PropVariantClear.argtypes=[C.POINTER(PROPVARIANT)]
            ole.PropVariantClear(C.byref(value))
        return dict(target=target.value,icon=icon.value,icon_index=index.value,arguments=arguments.value,app_id=app_id)
    finally:
        release(persist);release(store);release(link)


def create_shortcuts(root,launcher,icons,desktop=None,programs=None):
    if sys.platform!='win32':raise RuntimeError('Windows-only shortcut creation')
    import subprocess
    root,launcher,icons=Path(root).resolve(),Path(launcher).resolve(),Path(icons).resolve()
    if not launcher.is_relative_to(root) or not launcher.is_file() or not (icons/'pycad.ico').is_file():
        raise ValueError('The installed PY.cad launcher or logo is missing')
    ole=C.WinDLL('ole32');ole.CoInitializeEx.argtypes=[C.c_void_p,C.c_uint32];ole.CoInitializeEx.restype=C.c_long
    checked(ole.CoInitializeEx(None,2))
    try:
        folders=[Path(desktop) if desktop is not None else known_folder('Desktop'),
                 Path(programs) if programs is not None else known_folder('Programs')]
        arguments=subprocess.list2cmdline(['--launch','--root',str(root)])
        for folder in folders:
            folder.mkdir(parents=True,exist_ok=True)
            path=folder/'PY.cad.lnk'
            create_link(path,launcher,arguments,icons/'pycad.ico',root)
            result=read_link(path)
            if (os.path.normcase(result['target'])!=os.path.normcase(str(launcher)) or
                os.path.normcase(result['icon'])!=os.path.normcase(str(icons/'pycad.ico')) or
                result['icon_index']!=0 or result['arguments']!=arguments or result['app_id']!=APP_USER_MODEL_ID):
                raise RuntimeError('Windows did not retain the PY.cad shortcut logo, target and application identity')
    finally:ole.CoUninitialize()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',required=True)
    parser.add_argument('--launcher',required=True);parser.add_argument('--icons',required=True)
    args=parser.parse_args();create_shortcuts(args.root,args.launcher,args.icons)
