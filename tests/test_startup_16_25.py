"""Pinned startup policy and a real Python 3.14 Qt 6.12 repair regression."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest
from scripts import linux_launcher as launcher


def minimal_project(tmp_path):
    source=Path(__file__).resolve().parents[1]
    project=tmp_path/'CAD repair (Jay) ü';project.mkdir()
    for name in ('start.sh','requirements.txt','requirements-install-core.txt','requirements-install-constraints.txt'):
        shutil.copy2(source/name,project/name)
    shutil.copytree(source/'scripts',project/'scripts')
    return project


def test_stamp_tracks_constraint_changes(tmp_path):
    project=minimal_project(tmp_path);identity={'version':[3,14,8],'prefix':'test'}
    original=launcher.stamp(project,identity)
    with (project/'requirements-install-constraints.txt').open('a') as stream:stream.write('\n# changed pins\n')
    assert launcher.stamp(project,identity)!=original
    assert original['schema']==2


def test_current_runtime_passes_exact_import_check():
    result=subprocess.run([sys.executable,'-c',launcher.IMPORT_CHECK],capture_output=True,text=True)
    assert result.returncode==0,result.stderr


def test_wrong_qt_runtime_version_rejected_even_with_modules():
    prefix="import importlib.metadata as md\noriginal_version=md.version\nmd.version=lambda n:'6.12.0' if n=='PyQt6-Qt6' else original_version(n)\n"
    result=subprocess.run([sys.executable,'-c',prefix+launcher.IMPORT_CHECK],capture_output=True,text=True)
    assert result.returncode!=0 and '6.11.2' in result.stderr


@pytest.mark.skipif(os.environ.get('PYCAD_RUN_LINUX_INSTALL_TEST')!='1' or sys.platform!='linux',reason='Opt-in package download / repair regression')
def test_real_repair_qt612_and_offline_reuse(tmp_path):
    project=minimal_project(tmp_path)
    python=project/'.venv-linux/bin/python'
    subprocess.run([sys.executable,'-m','venv',str(python.parent.parent)],check=True,capture_output=True,timeout=120)
    subprocess.run([str(python),'-m','pip','install','--disable-pip-version-check','--only-binary=:all:',
                    'PyQt6==6.12.0','PyQt6-Qt6==6.12.0'],check=True,capture_output=True,timeout=600)
    before=subprocess.run([str(python),'-c','from PyQt6 import QtPdf'],capture_output=True,text=True)
    assert before.returncode!=0 and 'QtPdf' in before.stderr
    env=dict(os.environ,PYCAD_PYTHON=sys.executable,PYCAD_DATA_DIR=str(tmp_path/'profile'),QT_QPA_PLATFORM='offscreen')
    repaired=subprocess.run(['bash',str(project/'start.sh'),'--setup-only'],env=env,capture_output=True,text=True,timeout=600)
    assert repaired.returncode==0,repaired.stdout+repaired.stderr
    probe=subprocess.run([str(python),'-c',launcher.IMPORT_CHECK],capture_output=True,text=True)
    assert probe.returncode==0,probe.stderr
    marker=project/'.venv-linux/pycad-linux.json';assert json.loads(marker.read_text())['schema']==2
    before_time=marker.stat().st_mtime_ns
    offline=subprocess.run(['bash',str(project/'start.sh'),'--setup-only'],env=dict(env,PIP_NO_INDEX='1'),capture_output=True,text=True,timeout=60)
    assert offline.returncode==0 and 'no package download needed' in offline.stdout
    assert marker.stat().st_mtime_ns==before_time
