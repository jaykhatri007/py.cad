"""Explicit application identity for Windows-hosted Qt windows."""
import sys
from .identity import DISPLAY_NAME, LEGACY_APP_ID
from ._version import __version__

APP_USER_MODEL_ID = 'JayKhatri.PYcad.Desktop'


def set_process_identity():
    if sys.platform != 'win32':
        return False
    import ctypes
    shell = ctypes.WinDLL('shell32', use_last_error=True)
    setter = shell.SetCurrentProcessExplicitAppUserModelID
    setter.argtypes = [ctypes.c_wchar_p]
    setter.restype = ctypes.c_long
    result = setter(APP_USER_MODEL_ID)
    if result < 0:
        raise OSError(f'Cannot set PY.cad Windows identity: HRESULT 0x{result & 0xffffffff:08x}')
    return True


def configure_application(app):
    from .branding import app_icon
    app.setApplicationName(DISPLAY_NAME)
    app.setApplicationDisplayName(DISPLAY_NAME)
    app.setApplicationVersion(__version__)
    app.setOrganizationName(LEGACY_APP_ID)
    app.setDesktopFileName('pycad-managed')
    app.setWindowIcon(app_icon())
