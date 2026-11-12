"""Local LibreDWG conversion. Never write beside or replace the input drawing."""

from pathlib import Path
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile

from .validation import MAX_FILE_BYTES

ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
VENDOR = ROOT / "vendor" / "libredwg"
NOTE = ("DWG was imported through LibreDWG conversion. Unsupported/proxy objects, "
        "external references and some advanced DWG features may be missing or approximated. "
        "Review this drawing before use and save an editable .pycad copy; the original DWG is unchanged.")


def reader_path():
    from .dxf_io import DWGSupportError
    override = os.environ.get("PYCAD_DWG_CONVERTER", "")
    if override:
        path = Path(override).expanduser()
        if not path.is_absolute() or not path.is_file():
            raise DWGSupportError("PYCAD_DWG_CONVERTER must name an existing absolute path to LibreDWG dwg2dxf.")
        return path
    arch = {"x86_64": "amd64", "AMD64": "amd64", "arm64": "arm64", "aarch64": "arm64"}.get(platform.machine(), platform.machine())
    key = {"win32": "windows", "linux": "linux", "darwin": "darwin"}.get(sys.platform, sys.platform) + "-" + arch
    manifest_path = VENDOR / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    if key == "linux-amd64":
        libc, version = platform.libc_ver()
        parts = tuple(int(x) for x in version.split(".")[:2]) if version and all(x.isdigit() for x in version.split(".")[:2]) else ()
        if libc != "glibc" or parts < (2, 38):
            found = shutil.which("dwg2dxf")
            if found:
                return Path(found).resolve()
            raise DWGSupportError("The bundled Linux DWG reader needs glibc 2.38 or later (Ubuntu 24.04+). "
                                  "Install a compatible GNU LibreDWG dwg2dxf and set PYCAD_DWG_CONVERTER to its absolute path.")
    files = manifest.get("binaries", {}).get(key)
    if files:
        for name, expected in files.items():
            path = VENDOR / "bin" / key / name
            if Path(name).name != name or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise DWGSupportError("The bundled DWG reader failed its integrity check. Reinstall this PY.cad build.")
        return VENDOR / "bin" / key / ("dwg2dxf.exe" if sys.platform == "win32" else "dwg2dxf")
    found = shutil.which("dwg2dxf")
    if found:
        return Path(found).resolve()
    raise DWGSupportError(
        "No LibreDWG reader is available for this system. This build bundles Windows x64 and Linux x64 readers. "
        "On macOS/other systems install GNU LibreDWG dwg2dxf, or set PYCAD_DWG_CONVERTER to its absolute path. "
        "DXF files can also be opened directly. See Help → DWG support.")


def stage_source(source, directory, cancel=None, progress=None):
    source = Path(source).absolute()
    if not source.is_file():
        raise ValueError("DWG file does not exist: " + str(source))
    size = source.stat().st_size
    with source.open("rb") as stream:
        signature = stream.read(6)
    if not signature.startswith(b"AC") or len(signature) != 6:
        raise ValueError("This is not a supported DWG file header. Renaming a PDF/DXF to .dwg does not convert it.")
    # ASCII arguments in a Unicode-capable QProcess working directory also
    # avoid older Windows converter argv/codepage limitations and option names.
    target = Path(directory) / "input.dwg"
    with source.open("rb") as src, target.open("xb") as dst:
        total = 0
        while True:
            if cancel and cancel():raise InterruptedError('Source staging cancelled')
            chunk=src.read(1 << 20)
            if not chunk:break
            total += len(chunk)
            dst.write(chunk)
            if progress:progress(total,size)
    return target


def conversion_arguments():
    # Preserve the source version: forcing r2018 can lose older block/entity ownership.
    return ["-v0", "-o", "drawing.dxf", "--", "input.dwg"]


def checked_output(directory, exit_code, diagnostics=""):
    path = Path(directory) / "drawing.dxf"
    # LibreDWG warning bitmasks can also describe omitted content. Treat any
    # nonzero exit as a failed import rather than silently opening a partial DXF.
    if exit_code != 0:
        raise ValueError("DWG conversion failed (reader exit " + str(exit_code) + "). "
                         "The file may be corrupt or contain unsupported features. Original drawing unchanged.\n" + diagnostics[-4000:])
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError("The DWG reader returned no DXF drawing. Original drawing unchanged.")
    return path


def convert_sync(source, directory, timeout=120):
    """Programmatic API; the GUI uses a directly cancellable QProcess instead."""
    executable = reader_path()
    stage_source(source, directory)
    flags = {"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform == "win32" else {}
    with tempfile.TemporaryFile() as log:
        try:
            result = subprocess.run([str(executable), *conversion_arguments()], cwd=directory,
                                    stdout=log, stderr=log, timeout=timeout, **flags)
        except subprocess.TimeoutExpired as ex:
            raise ValueError("DWG conversion timed out; source unchanged") from ex
        except OSError as ex:
            raise ValueError("Could not start the LibreDWG reader: " + str(ex)) from ex
        log.seek(0, 2)
        log.seek(max(0, log.tell() - 8000))
        diagnostics = log.read().decode("utf-8", "replace")
    return checked_output(directory, result.returncode, diagnostics)
