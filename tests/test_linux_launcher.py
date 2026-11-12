"""Opt-in real Linux setup test; downloads dependencies on the first setup."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


@pytest.mark.skipif(sys.platform != 'linux' or os.environ.get('PYCAD_RUN_LINUX_INSTALL_TEST') != '1',
                    reason='Opt-in Linux install test; set PYCAD_RUN_LINUX_INSTALL_TEST=1')
def test_real_linux_setup_repair_offline_restart_and_file_argument(tmp_path):
    source = Path(__file__).resolve().parents[1]
    project = tmp_path / 'CAD project (Jay)! ü'
    project.mkdir()
    for name in ('start.sh', 'requirements.txt', 'requirements-install-core.txt', 'requirements-install-constraints.txt'):
        shutil.copy2(source / name, project / name)
    shutil.copytree(source / 'scripts', project / 'scripts')
    (project / '.venv').mkdir()
    (project / '.venv/Windows environment.txt').write_text('keep Windows')
    (project / '.venv-linux').mkdir()
    (project / '.venv-linux/keep.txt').write_text('keep Linux')
    (project / 'main.py').write_text(
        'import sys,json,pathlib\nfrom PyQt6.QtWidgets import QApplication\n'
        'app=QApplication([])\npathlib.Path("launched.json").write_text(json.dumps(sys.argv[1:]))\n')
    env = dict(os.environ, PYCAD_PYTHON=sys.executable,
               PYCAD_DATA_DIR=str(tmp_path / 'profile'), QT_QPA_PLATFORM='offscreen')
    def run(*arguments):
        result = subprocess.run(['bash', str(project / 'start.sh'), *arguments],
                                cwd=tmp_path, env=env, capture_output=True, text=True, timeout=600)
        assert result.returncode == 0, result.stdout + result.stderr
        return result
    run('--setup-only')
    backups = list(project.glob('.venv-linux-backup-*'))
    assert len(backups) == 1 and (backups[0] / 'keep.txt').read_text() == 'keep Linux'
    assert (project / '.venv/Windows environment.txt').read_text() == 'keep Windows'
    marker = project / '.venv-linux/pycad-linux.json'
    before = marker.stat().st_mtime_ns
    env['PIP_NO_INDEX'] = '1'
    drawing = tmp_path / 'relative drawing ü.pycad'
    drawing.write_text('argument routing only')
    result = run('--foreground', drawing.name)
    assert 'no package download' in result.stdout
    assert json.loads((project / 'launched.json').read_text()) == [str(drawing)]
    assert marker.stat().st_mtime_ns == before
    assert 'Required Python imports: OK' in run('--diagnose').stdout
