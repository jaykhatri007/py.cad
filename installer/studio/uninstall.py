"""Reversible removal of a verified, per-user Unix PY.cad installation."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import sys
import tempfile

def data_home():
    value=Path(os.environ.get('XDG_DATA_HOME',''))
    return value if value.is_absolute() else Path.home()/'.local/share'

def install_root():
    if sys.platform=='darwin':
        return Path.home()/'Library/Application Support/PyCAD/Installation'
    return data_home()/'pycad/installation'

def clean(path):
    if path.resolve()!=path:
        raise ValueError('Refusing a symbolic link: '+str(path))
    return path

def json_file(path):
    clean(path)
    if not path.is_file() or path.stat().st_size>65536:
        raise ValueError('Installation marker is missing or invalid: '+str(path))
    data=json.loads(path.read_text())
    if not isinstance(data,dict): raise ValueError("Invalid installation marker: "+str(path))
    return data

def validate(root):
    clean(root)
    data=json_file(root/'current.json')
    name=data.get('release','')
    version=data.get('version','')
    if (data.get('schema')!=1 or not isinstance(version,str)
        or not re.fullmatch(r'[0-9]+(?:\.[0-9]+){1,3}',version)
        or not isinstance(name,str) or not re.fullmatch(r'pycad-'+re.escape(version)+r'-[0-9a-f]{12}',name)
        or not str(data.get('platform','')).startswith(('darwin-' if sys.platform=='darwin' else 'linux-'))):
        raise ValueError('Not a recognized PY.cad installation receipt')
    owner=json_file(root/'releases'/name/'owner.json')
    if owner!={'application':'PyCAD','version':version}:
        raise ValueError('PY.cad ownership marker did not match')
    if not clean(root/'PyCAD').is_file() or root.stat().st_uid!=os.getuid():
        raise ValueError('The installation does not belong to this account')

def desktop_quote(s):
    s=s.replace('%','%%')
    for char in ('\\','"','`','$'):
        s=s.replace(char,'\\'+char)
    return '"'+s+'"'

def uninstall_entry(root, legacy=False):
    exe=desktop_quote('/usr/bin/python3')
    script=desktop_quote(str(root/'uninstall-studio.py'))
    command=exe+' -I '+script
    if not legacy:
        command+=' --root '+desktop_quote(str(root))
    command=command.replace('\\','\\\\')
    text='[Desktop Entry]\nType=Application\nName=Uninstall PY.cad\nExec='+command
    text+='\nTerminal='+('true' if legacy else 'false')+'\nCategories=Graphics;Engineering;\n'
    if not legacy:
        text+='Icon='+str(root/'icons/pycad.png').replace('\\','\\\\')+'\n'
    return text

def shortcuts(root):
    if sys.platform=='darwin':
        p=Path.home()/'Applications/PY.cad.app'
        marker=p/'Contents/PyCAD-Managed.txt'
        launch=p/'Contents/MacOS/PyCAD'
        if all(f.resolve()==f for f in (p,marker,launch)) and marker.is_file() and launch.is_file():
            q=lambda s: "'"+str(s).replace("'","'\\''")+"'"
            expected='#!/bin/sh\nexec '+q(root/'PyCAD')+' --root '+q(root)+' --launch "$@"\n'
            if marker.read_text()=='PyCAD managed installation\n' and launch.read_text()==expected:
                yield p
    else:
        folder=data_home()/'applications'
        p=folder/'pycad-managed.desktop'
        command=(desktop_quote(str(root/'PyCAD'))+' --root '+desktop_quote(str(root))+' --launch').replace('\\','\\\\')
        if p.resolve()==p and p.is_file() and 'Exec='+command in p.read_text().splitlines():
            yield p
        p=folder/'pycad-uninstall.desktop'
        if p.resolve()==p and p.is_file() and p.read_text() in (uninstall_entry(root),uninstall_entry(root,legacy=True)):
            yield p

def remove(root=None):
    root=install_root() if root is None else root
    validate(root)
    with os.fdopen(os.open(clean(root/'setup.lock'),os.O_RDWR|os.O_NOFOLLOW),'rb') as lock:
        try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError as exc: raise ValueError('Close the active PY.cad installer before uninstalling.') from exc
        validate(root)
        links=list(shortcuts(root))
        recovery=Path(tempfile.mkdtemp(prefix='PY.cad-removed-',dir=root.parent))
        try:
            root.rename(recovery/'installation')
        except OSError:
            recovery.rmdir()
            raise
        notes=[]
        for path in links:
            try: path.rename(recovery/path.name)
            except OSError: notes.append('Could not remove the shortcut at '+str(path))
        return recovery,notes

def graphical_remove(root):
    """Linux desktop entry: confirm, remove and report in a GTK window."""
    import ctypes as c

    ptr, integer, text = c.c_void_p, c.c_int, c.c_char_p
    gtk = c.CDLL('libgtk-3.so.0')
    def bind(name, result, *args):
        fn = getattr(gtk, 'gtk_'+name)
        fn.restype, fn.argtypes = result, list(args)
        return fn
    if not bind('init_check', integer, ptr, ptr)(None, None):
        raise RuntimeError('No graphical display is available; PY.cad was not removed.')
    create = bind('message_dialog_new', ptr, ptr, integer, integer, integer, text)
    destroy = bind('widget_destroy', None, ptr)
    add_button = bind('dialog_add_button', ptr, ptr, text, integer)
    run = bind('dialog_run', integer, ptr)
    title = bind('window_set_title', None, ptr, text)
    default = bind('dialog_set_default_response', None, ptr, integer)

    def dialog(message, kind=0, confirm=False):
        widget = create(None, 1, kind, 0, b'%s', text(message.encode()))
        try:
            title(widget, b'Uninstall PY.cad')
            if confirm:
                add_button(widget, b'Cancel', -6)
                add_button(widget, b'Uninstall', -5)
                default(widget, -6)
            else:
                add_button(widget, b'Close', -7)
            return run(widget)
        finally:
            destroy(widget)

    try:
        validate(root)
        if dialog('Close PY.cad before continuing.\n\nMove this installation and its shortcuts to a recovery folder? Drawings and settings will be kept.', kind=2, confirm=True) != -5:
            return 0
        recovery, notes = remove(root)
    except (OSError, ValueError) as exc:
        dialog(str(exc), kind=3)
        return 1
    dialog('PY.cad was removed from Applications.\n\nRecovery folder:\n'+str(recovery)
           +'\n\nCheck this folder for files you want to keep before deleting it.'
           + ('\n\n'+'\n'.join(notes) if notes else ''))
    return 0


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--yes',action='store_true',help='Confirm that PY.cad is closed and remove this installation')
    parser.add_argument('--root', type=Path, help=argparse.SUPPRESS)
    args=parser.parse_args()
    try:
        root=args.root or install_root()
        if sys.platform=='linux' and not args.yes:
            return graphical_remove(root)
        validate(root)
        if not args.yes and input('Close PY.cad first. Move the installation and verified shortcuts to a recovery folder? Type YES: ')!='YES':
            print('Uninstall cancelled.')
            return 0
        recovery,notes=remove(root)
        print('PY.cad removed from its active location. Recoverable files: '+str(recovery))
        print('To reclaim disk space, delete this folder after checking it for drawings you want to keep.')
        for note in notes: print(note)
        return 0
    except (OSError,ValueError,EOFError,RuntimeError) as exc:
        print('PY.cad uninstall: '+str(exc),file=sys.stderr)
        return 1

if __name__=='__main__':
    sys.exit(main())
