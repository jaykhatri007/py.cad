"""Linux bootstrap with isolated environments, offline reuse and useful errors.

Only the standard library is imported before the application environment exists.
"""

import argparse
from contextlib import contextmanager
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = 2
PROBE = r'''
import json,sys,struct,importlib.metadata as md
assert sys.implementation.name=='cpython' and (3,11)<=sys.version_info[:2]<=(3,14)
assert struct.calcsize('P')==8
print(json.dumps({'prefix':sys.prefix,'version':list(sys.version_info[:3])}))
'''
IMPORT_CHECK = r'''
import importlib.metadata as md
from PyQt6 import QtWidgets,QtPrintSupport,QtOpenGL,QtOpenGLWidgets,QtPdf,QtSvg
import ezdxf,numpy
for name,expected in (('PyQt6','6.11.0'),('PyQt6-Qt6','6.11.2'),('ezdxf','1.4.4'),('numpy','2.3.5')):
    actual=md.version(name)
    assert actual==expected,(name,actual,'expected',expected)
'''


def capture(arguments, **kwargs):
    return subprocess.run([str(a) for a in arguments], capture_output=True,
                          text=True, errors='replace', timeout=60, **kwargs)


def env_identity(python):
    try:
        result = capture([python, '-c', PROBE])
        return json.loads(result.stdout) if result.returncode == 0 else None
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


def stamp(root, identity, optional=False):
    requirements = b''.join((root / name).read_bytes() for name in
                            ('requirements-install-core.txt', 'requirements-install-constraints.txt'))
    if optional:
        requirements += (root / 'requirements-3d.txt').read_bytes()
    return {'schema': SCHEMA, 'root': str(root.resolve()), 'identity': identity,
            'requirements': hashlib.sha256(requirements).hexdigest()}


def read_stamp(path):
    try:
        value = json.loads(path.read_text())
        return value if isinstance(value, dict) else None
    except (OSError, ValueError):
        return None


def write_stamp(path, value):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, indent=2) + '\n')
    temp.replace(path)


@contextmanager
def setup_lock(root):
    import fcntl
    with (root / '.pycad-linux-setup.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError('Another PY.cad setup is active. Wait for it to finish.') from error
        yield


def prepare(root, log, optional=False):
    envdir = root / '.venv-linux'
    python = envdir / 'bin/python'
    marker = envdir / 'pycad-linux.json'
    old = read_stamp(marker)
    identity = env_identity(python)
    # A copied Windows .venv is untouched. Moved/broken Linux environments are
    # retained as backups; never erase the user's existing folder.
    stale = (identity is None or Path(identity['prefix']).resolve() != envdir.resolve()
             or (old is not None and old.get('root') != str(root.resolve())))
    if envdir.exists() and stale:
        backup = root / ('.venv-linux-backup-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
        envdir.rename(backup)
        print('Preserved old Linux environment:', backup, flush=True)
        identity = None
    if identity is None:
        print('Creating Linux Python environment…', flush=True)
        result = subprocess.run([sys.executable, '-m', 'venv', str(envdir)],
                                stdout=log, stderr=subprocess.STDOUT)
        if result.returncode:
            raise RuntimeError('Cannot create the environment. Install python3-venv (or the matching versioned venv package), then retry.')
        identity = env_identity(python)
        if identity is None:
            raise RuntimeError('The new environment does not contain a supported Python runtime.')
    expected = stamp(root, identity)
    probe = capture([python, '-c', IMPORT_CHECK])
    if read_stamp(marker) != expected or probe.returncode:
        if probe.returncode:
            log.write(probe.stdout + probe.stderr); log.flush()
        print('Installing/checking PY.cad packages (first setup or changed requirements)…', flush=True)
        command = [str(python), '-m', 'pip', 'install', '--disable-pip-version-check',
                   '--only-binary=:all:', '--retries', '5', '--timeout', '120']
        if probe.returncode:
            # A satisfied-but-broken wheel (or mismatched Qt pair) needs replacement,
            # not another broad install that reports "already satisfied".
            command.append('--force-reinstall')
        command += ['-r', str(root / 'requirements-install-core.txt')]
        result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
        if result.returncode:
            raise RuntimeError('Python package setup failed. Check the log, Internet access and Python version. Do not use sudo pip.')
        probe = capture([python, '-c', IMPORT_CHECK])
        if probe.returncode:
            log.write(probe.stdout + probe.stderr); log.flush()
            raise RuntimeError('Pinned Python packages still cannot load; see the traceback in the log. For missing Linux shared libraries run bash setup_ubuntu.sh. A missing QtPdf module requires the pinned Qt package repair, not apt alone.')
        write_stamp(marker, expected)
    else:
        print('Linux environment ready; no package download needed.', flush=True)
    if optional:
        extra = envdir / 'pycad-3d.json'
        expected_extra = stamp(root, identity, optional=True)
        probe = capture([python, '-c', 'import cadquery; assert cadquery.__version__ == "2.7.0"'])
        if read_stamp(extra) != expected_extra or probe.returncode:
            print('Installing optional CadQuery solid export packages…', flush=True)
            result = subprocess.run([str(python), '-m', 'pip', 'install', '--disable-pip-version-check',
                                     '-r', str(root / 'requirements-3d.txt')], stdout=log, stderr=subprocess.STDOUT)
            probe = capture([python, '-c', 'import cadquery; assert cadquery.__version__ == "2.7.0"'])
            if result.returncode or probe.returncode:
                log.write(probe.stdout + probe.stderr); log.flush()
                raise RuntimeError('Optional CadQuery setup failed. Core CAD is retained. Use Python 3.12 for the validated 3D environment.')
            write_stamp(extra, expected_extra)
    return python


def entry_string(value):
    return str(value).replace('\\', '\\\\').replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')


def exec_quote(value):
    # Desktop Entry Exec quoting, followed by the general string escape pass.
    text = str(value).replace('%', '%%')
    for char in ('\\', '"', '`', '$'):
        text = text.replace(char, '\\' + char)
    return entry_string('"' + text + '"')


def install_desktop(root):
    data = Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local/share').expanduser()
    if not data.is_absolute():
        raise RuntimeError('XDG_DATA_HOME must be an absolute directory.')
    path = data / 'applications/pycad-local.desktop'
    if path.exists() and 'X-PyCAD-Managed=true' not in path.read_text():
        raise RuntimeError('An unrelated pycad-local.desktop already exists; keep it or rename it before installing the shortcut.')
    path.parent.mkdir(parents=True, exist_ok=True)
    text = '\n'.join(('[Desktop Entry]', 'Type=Application', 'Name=PY.cad',
        'Comment=Python CAD drafting and model workspace',
        'Exec=/usr/bin/bash ' + exec_quote(root / 'start.sh') + ' -- %f',
        'Icon=' + entry_string(root / 'assets/pycad-icon.png'), 'Terminal=false',
        'Categories=Graphics;Engineering;', 'StartupNotify=false',
        'X-PyCAD-Managed=true', ''))
    path.write_text(text, encoding='utf-8')
    print('Applications shortcut:', path)
    return path


def display_environment(args):
    env = dict(os.environ)
    if args.xcb:
        env['QT_QPA_PLATFORM'] = 'xcb'
    elif args.wayland:
        env['QT_QPA_PLATFORM'] = 'wayland'
    elif not env.get('QT_QPA_PLATFORM') and env.get('DISPLAY'):
        # X11 on classic desktops or XWayland on GNOME Wayland.
        env['QT_QPA_PLATFORM'] = 'xcb'
    if args.software_rendering:
        env['PYCAD_GRAPHICS'] = 'software'
        env['LIBGL_ALWAYS_SOFTWARE'] = '1'
        env['QT_OPENGL'] = 'software'
    return env


def diagnose(root):
    identity = env_identity(root / '.venv-linux/bin/python')
    os_release = {}
    try:
        for line in Path('/etc/os-release').read_text().splitlines():
            if '=' in line:
                key, value = line.split('=', 1)
                os_release[key] = value.strip().strip('"')
    except OSError:
        pass
    print(json.dumps({'system': platform.platform(), 'machine': platform.machine(),
        'distribution': os_release.get('PRETTY_NAME'),
        'distribution_version': os_release.get('VERSION_ID'),
        'bootstrap_python': sys.version.split()[0], 'project': str(root),
        'linux_environment': identity, 'DISPLAY': os.environ.get('DISPLAY'),
        'WAYLAND_DISPLAY': os.environ.get('WAYLAND_DISPLAY'),
        'QT_QPA_PLATFORM': os.environ.get('QT_QPA_PLATFORM'),
        'windows_environment_present': (root / '.venv/Scripts/python.exe').exists()}, indent=2))
    if identity:
        result = capture([root / '.venv-linux/bin/python', '-c', IMPORT_CHECK])
        print('Required Python imports:', 'OK' if result.returncode == 0 else result.stderr)
        return result.returncode
    print('Run bash setup_ubuntu.sh to prepare this folder.')
    return 1


def main(argv=None):
    parser = argparse.ArgumentParser(description='PY.cad Ubuntu/Linux launcher')
    parser.add_argument('--setup-only', action='store_true')
    parser.add_argument('--with-3d', action='store_true')
    parser.add_argument('--install-desktop', action='store_true')
    parser.add_argument('--diagnose', action='store_true', help='Read-only environment report')
    parser.add_argument('--check', action='store_true', help='Open/check/close the app in an isolated temporary profile')
    parser.add_argument('--foreground', action='store_true', help='Keep the terminal attached for debugging')
    backend = parser.add_mutually_exclusive_group()
    backend.add_argument('--xcb', action='store_true')
    backend.add_argument('--wayland', action='store_true')
    parser.add_argument('--software-rendering', action='store_true')
    parser.add_argument('drawing', nargs='?', help='Optional drawing, resolved from your current directory')
    args = parser.parse_args(argv)
    if sys.platform != 'linux':
        parser.error('Use start_windows.bat on Windows. This launcher targets Linux.')
    if args.diagnose:
        return diagnose(ROOT)
    env = display_environment(args)
    if not args.setup_only and not (env.get('DISPLAY') or env.get('WAYLAND_DISPLAY')
                                  or env.get('QT_QPA_PLATFORM') in ('offscreen', 'minimal')):
        print('No graphical display found. Run from your Ubuntu desktop terminal. Use --setup-only for installation without a display.', file=sys.stderr)
        return 1
    # Resolve before changing the application working directory.
    drawing = str(Path(args.drawing).expanduser().resolve()) if args.drawing else None
    data = Path(os.environ.get('PYCAD_DATA_DIR') or Path.home() / '.pycad').expanduser().resolve()
    if os.environ.get('PYCAD_DATA_DIR'):
        env['PYCAD_DATA_DIR'] = str(data)
    logs = data / 'logs'
    logs.mkdir(parents=True, exist_ok=True)
    logpath = logs / ('startup-linux-' + datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.log')
    print('Startup log:', logpath, flush=True)
    try:
        with logpath.open('w', encoding='utf-8') as log:
            with setup_lock(ROOT):
                python = prepare(ROOT, log, args.with_3d)
            if args.install_desktop:
                install_desktop(ROOT)
            else:
                # Refresh only the legacy shortcut belonging to this folder.
                data_home = Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local/share').expanduser()
                entry = data_home / 'applications/pycad-local.desktop'
                if data_home.is_absolute() and entry.is_file() and not entry.is_symlink():
                    try:
                        lines = entry.read_text(encoding='utf-8', errors='replace').splitlines()
                        expected = 'Exec=/usr/bin/bash ' + exec_quote(ROOT / 'start.sh') + ' -- %f'
                        if {'X-PyCAD-Managed=true', 'Terminal=true', expected}.issubset(lines):
                            install_desktop(ROOT)
                    except OSError as error:
                        print('Could not refresh the existing Applications shortcut:', error, file=sys.stderr)
            if args.setup_only:
                return 0
            if args.check:
                with tempfile.TemporaryDirectory(prefix='pycad-desktop-check-') as profile:
                    env['PYCAD_DATA_DIR'] = profile
                    result = subprocess.run([str(python), str(ROOT / 'scripts/check_desktop.py')],
                                            cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=60)
            else:
                command = [str(python), str(ROOT / 'main.py')]
                if drawing:
                    command.append(drawing)
                if not args.foreground:
                    app = subprocess.Popen(command, cwd=ROOT, env=env,
                                           stdin=subprocess.DEVNULL, stdout=log,
                                           stderr=subprocess.STDOUT, start_new_session=True)
                    print(f'PY.cad started independently of this terminal (PID {app.pid}).', flush=True)
                    return 0
                result = subprocess.run(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
            if result.returncode:
                raise RuntimeError('PY.cad could not start or exited with an error. For Qt/xcb errors run setup_ubuntu.sh; try --xcb or --software-rendering if needed.')
        if args.check:
            print(logpath.read_text())
        return 0
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(str(error), file=sys.stderr)
        print('Details:', logpath, file=sys.stderr)
        if logpath.exists():
            print('\n'.join(logpath.read_text(errors='replace').splitlines()[-18:]), file=sys.stderr)
        return 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except OSError as error:
        print('Cannot write PY.cad startup files:', error, file=sys.stderr)
        print('Extract the build into a writable folder under your Ubuntu home directory and retry.', file=sys.stderr)
        sys.exit(1)
