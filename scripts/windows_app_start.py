"""Start the installed Qt application inside the branded, private runtime copy.

The original venv executable remains sys.executable for isolated parser/GPU
workers. The actual Windows main process is the branded PY.cad executable.
"""
import argparse
import json
import os
from pathlib import Path
import runpy
import site
import sys


def ensure_stdio():
    # GUI Python can have no standard streams. Keep logging/print diagnostics
    # usable without creating a console window or touching Program Files.
    output = None
    for name in ('stdout','stderr'):
        stream = getattr(sys,name)
        try:
            valid = stream is not None and os.fstat(stream.fileno()) is not None
        except (OSError,ValueError,AttributeError):
            valid = False
        if not valid:
            if output is None:
                directory = Path(os.environ.get('PYCAD_DATA_DIR') or
                                 str(Path(os.environ.get('LOCALAPPDATA',Path.home()))/'PY.cad'))/'logs'
                directory.mkdir(parents=True,exist_ok=True)
                output = (directory/'application.log').open('a',encoding='utf-8',buffering=1)
            setattr(sys,name,output)
    if sys.stdin is None:
        sys.stdin = open(os.devnull,'r')


def activate(env):
    env = Path(env).resolve()
    executable = env / 'Scripts/python.exe'
    packages = env / 'Lib/site-packages'
    if not executable.is_file() or not packages.is_dir():
        raise RuntimeError('The installed PY.cad environment is incomplete; run Setup to repair it')
    base = Path(sys.base_prefix)
    base_packages = os.path.normcase(str(base/'Lib/site-packages'))
    sys.path[:] = [p for p in sys.path if os.path.normcase(os.path.abspath(p)) != base_packages]
    sys._base_executable = str(base/'python.exe')
    sys.prefix = sys.exec_prefix = str(env)
    os.environ['VIRTUAL_ENV'] = str(env)
    site.ENABLE_USER_SITE = False
    site.addsitedir(str(packages))
    sys.executable = str(executable)
    return env


def probe(path, full=False):
    import ctypes
    from PyQt6.QtWidgets import QApplication
    from pycad.windows_identity import APP_USER_MODEL_ID, set_process_identity, configure_application
    assert set_process_identity()
    app = QApplication([])
    configure_application(app)
    assert app.applicationName() == app.applicationDisplayName() == 'PY.cad'
    assert not app.windowIcon().isNull()
    import numpy, ezdxf
    assert numpy.zeros(2).shape == (2,) and ezdxf.new().dxfversion
    if full:
        import cadquery as cq, ifcopenshell
        assert cq.Workplane('XY').box(1,1,1).val().isValid()
        ifcopenshell.file(schema='IFC4')
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GetModuleFileNameW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint32]
    kernel.GetModuleFileNameW.restype = ctypes.c_uint32
    buffer = ctypes.create_unicode_buffer(32768)
    assert kernel.GetModuleFileNameW(None, buffer, len(buffer))
    assert Path(buffer.value).name.startswith('PY.cad-')
    version = ctypes.WinDLL('version', use_last_error=True)
    version.GetFileVersionInfoSizeW.argtypes=[ctypes.c_wchar_p,ctypes.c_void_p]
    version.GetFileVersionInfoSizeW.restype=ctypes.c_uint32
    size=version.GetFileVersionInfoSizeW(buffer.value,None)
    assert size
    data=ctypes.create_string_buffer(size)
    version.GetFileVersionInfoW.argtypes=[ctypes.c_wchar_p,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_void_p]
    assert version.GetFileVersionInfoW(buffer.value,0,size,data)
    value=ctypes.c_void_p();length=ctypes.c_uint32()
    version.VerQueryValueW.argtypes=[ctypes.c_void_p,ctypes.c_wchar_p,ctypes.POINTER(ctypes.c_void_p),ctypes.POINTER(ctypes.c_uint32)]
    assert version.VerQueryValueW(data,r'\StringFileInfo\040904B0\FileDescription',ctypes.byref(value),ctypes.byref(length))
    assert ctypes.wstring_at(value)=='PY.cad'
    from prepare_windows_identity import icon_resources, ROOT
    expected=icon_resources((ROOT/'assets/pycad.ico').read_bytes())
    kernel.GetModuleHandleW.argtypes=[ctypes.c_wchar_p];kernel.GetModuleHandleW.restype=ctypes.c_void_p
    instance=kernel.GetModuleHandleW(None)
    kernel.FindResourceW.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p];kernel.FindResourceW.restype=ctypes.c_void_p
    kernel.LoadResource.argtypes=[ctypes.c_void_p,ctypes.c_void_p];kernel.LoadResource.restype=ctypes.c_void_p
    kernel.SizeofResource.argtypes=[ctypes.c_void_p,ctypes.c_void_p];kernel.SizeofResource.restype=ctypes.c_uint32
    kernel.LockResource.argtypes=[ctypes.c_void_p];kernel.LockResource.restype=ctypes.c_void_p
    for kind,number,payload in expected:
        resource=kernel.FindResourceW(instance,number,kind);assert resource
        size=kernel.SizeofResource(instance,resource)
        memory=kernel.LockResource(kernel.LoadResource(instance,resource))
        assert memory and ctypes.string_at(memory,size)==payload
    shell = ctypes.WinDLL('shell32', use_last_error=True)
    shell.GetCurrentProcessExplicitAppUserModelID.argtypes = [ctypes.POINTER(ctypes.c_void_p)]
    shell.GetCurrentProcessExplicitAppUserModelID.restype = ctypes.c_long
    value = ctypes.c_void_p()
    assert shell.GetCurrentProcessExplicitAppUserModelID(ctypes.byref(value)) == 0
    try:
        assert ctypes.wstring_at(value) == APP_USER_MODEL_ID
    finally:
        ole = ctypes.WinDLL('ole32'); ole.CoTaskMemFree.argtypes = [ctypes.c_void_p]
        ole.CoTaskMemFree(value)
    Path(path).write_text(json.dumps({'name':'PY.cad', 'host':buffer.value,
        'python':sys.executable, 'prefix':sys.prefix, 'app_id':APP_USER_MODEL_ID}), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--env', required=True)
    parser.add_argument('--main', required=True)
    parser.add_argument('--probe')
    parser.add_argument('--full', action='store_true')
    parser.add_argument('arguments', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    ensure_stdio()
    activate(args.env)
    source = Path(args.main).resolve()
    sys.path.insert(0, str(source.parent))
    if args.probe:
        try:
            probe(args.probe, args.full)
        except Exception:
            import traceback
            Path(args.probe).write_text(json.dumps({'error':traceback.format_exc()}),encoding='utf-8')
            raise
        return 0
    forwarded = args.arguments[1:] if args.arguments[:1] == ['--'] else args.arguments
    sys.argv = [str(source), *forwarded]
    runpy.run_path(str(source), run_name='__main__')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
