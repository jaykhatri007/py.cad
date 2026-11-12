# pycad.spec
# Build a standalone PY.cad executable with:
#   pyinstaller packaging/pycad.spec
# The result lands in dist/PY.cad/ (a folder build, not --onefile) because
# CadQuery/OCP ship a large number of shared libraries that a single-file
# build would have to unpack on every launch - a folder build starts faster
# and is the standard approach for OCP-based apps.
#
# Run this from the project root (the directory containing main.py).

import os
import sys
from PyInstaller.utils.hooks import collect_all

block_cipher = None
PROJECT_ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))

# CadQuery/OCP bundle their own binary data files and hidden imports that
# PyInstaller's static analysis can't discover on its own - collect_all()
# grabs everything the packages themselves declare.
datas = [
    (os.path.join(PROJECT_ROOT, "vendor"), "vendor"),
    (os.path.join(PROJECT_ROOT, "assets"), "assets"),
    (os.path.join(PROJECT_ROOT, "legal"), "legal"),
    (os.path.join(PROJECT_ROOT, "LICENSES"), "LICENSES"),
    (os.path.join(PROJECT_ROOT, "LICENSE"), "."),
    (os.path.join(PROJECT_ROOT, "COPYRIGHT"), "."),
    (os.path.join(PROJECT_ROOT, "THIRD_PARTY_NOTICES.md"), "."),
]
binaries = []
hiddenimports = []
for pkg in ("cadquery", "OCP"):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass  # if cadquery/OCP aren't installed, ship without the 3D extrude feature

a = Analysis(
    [os.path.join(PROJECT_ROOT, "main.py")],
    pathex=[PROJECT_ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PY.cad",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # windowed app - no terminal popup on Windows/Mac
    icon=os.path.join(PROJECT_ROOT, "assets", "pycad.ico" if sys.platform == "win32" else "pycad.icns") if sys.platform in ("win32", "darwin") else None,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="PY.cad",
)
