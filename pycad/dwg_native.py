"""Verified LibreDWG tools, automatic reader policy and open-source R2000 export."""
from pathlib import Path
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile

from . import dwg_support

MODES = {'auto': 'Auto · direct reader with compatibility fallback',
         'direct': 'Direct · no DXF intermediate (supported 2D objects)',
         'compatibility': 'Compatibility · existing DXF bridge'}


class DirectUnsupported(ValueError):
    """The direct adapter cannot represent this drawing; compatibility may help."""


def requested_mode():
    from .appsettings import get_settings
    mode = os.environ.get('PYCAD_DWG_MODE', str(get_settings().value('dwg/import_mode', 'auto'))).lower()
    # An explicit legacy converter override must continue to select that converter.
    if os.environ.get('PYCAD_DWG_CONVERTER') and 'PYCAD_DWG_MODE' not in os.environ:
        return 'compatibility'
    return mode if mode in MODES else 'auto'


def tool_path(name):
    from .dxf_io import DWGSupportError
    if name not in ('dwgread', 'dwgwrite'):
        raise ValueError('Unknown DWG tool')
    override = os.environ.get('PYCAD_' + name.upper(), '')
    if override:
        path = Path(override).expanduser()
        if not path.is_absolute() or not path.is_file():
            raise DWGSupportError('PYCAD_' + name.upper() + ' must name an existing absolute executable path.')
        return path
    arch = {'x86_64':'amd64', 'AMD64':'amd64', 'aarch64':'arm64', 'arm64':'arm64'}.get(platform.machine(), platform.machine())
    key = {'win32':'windows', 'linux':'linux', 'darwin':'darwin'}.get(sys.platform, sys.platform) + '-' + arch
    filename = name + ('.exe' if sys.platform == 'win32' else '')
    manifest_path = dwg_support.VENDOR / 'manifest.json'
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    files = manifest.get('binaries', {}).get(key, {})
    compatible = True
    if key == 'linux-amd64':
        libc, version = platform.libc_ver()
        try:
            compatible = libc == 'glibc' and tuple(map(int, version.split('.')[:2])) >= (2, 38)
        except ValueError:
            compatible = False
    if filename in files and compatible:
        for item, digest in files.items():
            path = dwg_support.VENDOR / 'bin' / key / item
            if Path(item).name != item or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                raise DWGSupportError('Bundled LibreDWG tool failed its integrity check. Reinstall PY.cad.')
        return dwg_support.VENDOR / 'bin' / key / filename
    found = shutil.which(name)
    if found:
        return Path(found).resolve()
    raise DWGSupportError('No compatible GNU LibreDWG ' + name + ' is available. Windows x64 and Ubuntu 24.04+ x64 tools are bundled; other systems need an installed LibreDWG tool. Optional ODA File Converter remains available for DWG export.')


def direct_arguments():
    return ['-v0', '-O', 'JSON', '-o', 'drawing.json', '--', 'input.dwg']


def run_tool(executable, arguments, directory, timeout=120):
    flags = {'creationflags': subprocess.CREATE_NO_WINDOW} if sys.platform == 'win32' else {}
    with tempfile.TemporaryFile() as log:
        try:
            result = subprocess.run([str(executable), *arguments], cwd=directory, stdout=log, stderr=log,
                                    timeout=timeout, **flags)
        except subprocess.TimeoutExpired as ex:
            raise ValueError('LibreDWG timed out; original drawing unchanged') from ex
        log.seek(0, 2)
        log.seek(max(0, log.tell()-8000))
        text = log.read().decode('utf-8', 'replace')
    if result.returncode != 0:
        raise ValueError('LibreDWG failed (exit ' + str(result.returncode) + '); original drawing unchanged.\n' + text[-4000:])
    return text


def read_direct(source):
    from .dwg_json import import_json
    executable = tool_path('dwgread')
    with tempfile.TemporaryDirectory(prefix='pycad-direct-') as directory:
        dwg_support.stage_source(source, directory)
        run_tool(executable, direct_arguments(), directory)
        return import_json(Path(directory) / 'drawing.json', str(Path(source).absolute()))


def export_r2000(document, destination):
    """Atomic, explicit R2000 export; never relabel modern output as lossless."""
    from .dxf_io import _build_ezdxf_doc
    from .native_io import atomic_write
    executable = tool_path('dwgwrite')
    from .geometry import HatchEntity
    from itertools import chain
    source_entities = chain(document.entities, chain.from_iterable(b.entities for b in document.blocks.values()))
    if any(isinstance(e, HatchEntity) and e.pattern.startswith('GRADIENT_') for e in source_entities):
        raise ValueError('R2000 DWG cannot preserve gradient hatches. Save .pycad or DXF instead; destination unchanged.')
    doc = _build_ezdxf_doc(document)
    # LibreDWG's supported writer target. This is still a DXF export bridge.
    doc.dxfversion = 'AC1015'
    with tempfile.TemporaryDirectory(prefix='pycad-dwg-save-') as directory:
        doc.saveas(str(Path(directory) / 'drawing.dxf'))
        run_tool(executable, ['-v0', '--as', 'r2000', '-I', 'DXF', '-o', 'output.dwg', '--', 'drawing.dxf'], directory)
        output = Path(directory) / 'output.dwg'
        if not output.is_file() or output.stat().st_size <= 6 or output.read_bytes()[:6] != b'AC1015':
            raise ValueError('LibreDWG returned no valid R2000 DWG; destination unchanged')
        # A writer can return success while dropping an unsupported object.
        # Read the result back before publishing it and compare structure.
        import ezdxf
        check = Path(directory) / 'verify'; check.mkdir()
        recovered = ezdxf.readfile(dwg_support.convert_sync(output, check))
        def profile(drawing):
            from collections import Counter
            return {b.name.upper(): Counter((e.dxftype(), len(e.paths) if e.dxftype() == 'HATCH' else 0)
                    for e in b) for b in drawing.blocks}
        expected, actual = profile(doc), profile(recovered)
        if any(actual.get(name) != counts for name, counts in expected.items()):
            raise ValueError('DWG export read-back did not preserve drawing/block entity types and hatch loops; destination unchanged. Save .pycad or DXF instead.')
        from .exchange_quality import verify_export_extents
        verify_export_extents(doc,recovered)
        atomic_write(destination, lambda path: shutil.copyfile(output, path))
