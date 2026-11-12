"""Portable startup/resource regressions plus opt-in real Windows acceptance."""
import ctypes
import importlib.util
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
from types import SimpleNamespace
import pytest
from pycad import windows_identity

ROOT=Path(__file__).resolve().parents[1]


def module(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/f'{name}.py')
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result


def test_process_identity_and_qt_metadata(qapp,monkeypatch):
    calls=[]
    def setter(value):calls.append(value);return 0
    monkeypatch.setattr(windows_identity.sys,'platform','win32')
    monkeypatch.setattr(ctypes,'WinDLL',lambda *a,**k:SimpleNamespace(SetCurrentProcessExplicitAppUserModelID=setter),raising=False)
    assert windows_identity.set_process_identity()
    assert calls==[windows_identity.APP_USER_MODEL_ID]
    windows_identity.configure_application(qapp)
    assert qapp.applicationName()==qapp.applicationDisplayName()=='PY.cad'
    assert not qapp.windowIcon().isNull()


def test_non_windows_startup_does_not_call_windows_api(monkeypatch):
    monkeypatch.setattr(windows_identity.sys,'platform','linux')
    assert windows_identity.set_process_identity() is False


def test_version_resource_has_correct_structure_and_app_strings():
    data=module('prepare_windows_identity').version_resource('16.19.0')
    length,value_length,kind=struct.unpack_from('<HHH',data)
    assert length==len(data) and value_length==52 and kind==0
    key='VS_VERSION_INFO\0'.encode('utf-16le')
    offset=(6+len(key)+3)&~3
    assert struct.unpack_from('<I',data,offset)[0]==0xfeef04bd
    assert struct.unpack_from('<I',data,offset+8)[0]==(16<<16)|19
    for text in ('FileDescription\0','ProductName\0','PY.cad\0','OriginalFilename\0','PY.cad.exe\0','Python Software Foundation'):
        assert text.encode('utf-16le') in data


def test_icon_resource_group_contains_all_logo_sizes():
    m=module('prepare_windows_identity');source=(ROOT/'assets/pycad.ico').read_bytes()
    rows=m.icon_resources(source);group=rows[-1][2]
    count=struct.unpack_from('<H',source,4)[0]
    assert count>1 and len(rows)==count+1
    assert struct.unpack_from('<HHH',group)==(0,1,count)
    for index in range(count):
        size,offset=struct.unpack_from('<II',source,6+index*16+8)
        assert rows[index][2]==source[offset:offset+size]
        assert struct.unpack_from('<IH',group,6+index*14+8)==(size,101+index)
    with pytest.raises((ValueError,struct.error)):m.icon_resources(b'bad icon')


def test_bootstrap_uses_venv_workers_packages_and_preserves_arguments(tmp_path):
    env=tmp_path/'CAD environment ü';(env/'Scripts').mkdir(parents=True)
    (env/'Scripts/python.exe').write_bytes(b'worker placeholder')
    packages=env/'Lib/site-packages';packages.mkdir(parents=True)
    (packages/'private_fixture.py').write_text('VALUE=731\n')
    result=tmp_path/'result.json'
    source=tmp_path/'main fixture.py'
    source.write_text('import sys,json,private_fixture\nfrom pathlib import Path\nPath('+repr(str(result))+').write_text(json.dumps(dict(argv=sys.argv[1:],prefix=sys.prefix,executable=sys.executable,value=private_fixture.VALUE)))\n')
    arguments=['Drawing ü & spaces.dwg',"Jay's file",'--literal']
    subprocess.run([sys.executable,str(ROOT/'scripts/windows_app_start.py'),'--env',str(env),'--main',str(source),'--',*arguments],check=True)
    data=json.loads(result.read_text())
    assert data['argv']==arguments and data['value']==731
    assert data['prefix']==str(env) and data['executable']==str(env/'Scripts/python.exe')


def test_shortcut_guids_and_unicode_variant_layout():
    m=module('windows_shortcuts')
    assert ctypes.sizeof(m.GUID)==16 and ctypes.sizeof(m.PROPERTYKEY)==20
    if ctypes.sizeof(ctypes.c_void_p)==8:
        assert ctypes.sizeof(m.PROPVARIANT)==24 and m.PROPVARIANT.pointer.offset==8
    assert bytes(m.GUID('00021401-0000-0000-c000-000000000046').data).hex()=='0114020000000000c000000000000046'
    assert m.APP_USER_MODEL_ID==windows_identity.APP_USER_MODEL_ID


@pytest.mark.skipif(sys.platform!='win32' or os.environ.get('PYCAD_IDENTITY_TEST')!='1',reason='Opt-in actual Windows shell/resource acceptance')
def test_real_windows_private_host_probe_and_shortcuts(tmp_path):
    # Run on Windows with the installed managed environment and PYCAD_TEST_ROOT.
    root=Path(os.environ['PYCAD_TEST_ROOT'])
    receipt=json.loads((root/'current.json').read_text())
    release=root/'releases'/receipt['release']
    identity=json.loads((release/'windows-app.json').read_text())
    output=tmp_path/'probe.json'
    subprocess.run([identity['host'],str(ROOT/'scripts/windows_app_start.py'),'--env',str(release/'env'),
                    '--main',str(ROOT/'main.py'),'--probe',str(output)],check=True)
    assert json.loads(output.read_text())['name']=='PY.cad'
    m=module('windows_shortcuts')
    # Exercise real COM without writing to the user's actual Desktop/Start menu.
    launcher=next((root/'launchers').glob('*.exe'))
    m.create_shortcuts(root,launcher,root/'icons',tmp_path/'Desktop',tmp_path/'Programs')
    assert (tmp_path/'Desktop/PY.cad.lnk').is_file() and (tmp_path/'Programs/PY.cad.lnk').is_file()
