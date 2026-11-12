"""Exercise the launcher in a real controlling pseudo-terminal without Qt."""
import json
import os
from pathlib import Path
import pty
import signal
import sys
import time

import tempfile
import unittest
from unittest.mock import patch

from scripts import linux_launcher as launcher

@unittest.skipUnless(sys.platform == 'linux', 'Linux terminal lifecycle')
class DetachedLaunchTest(unittest.TestCase):
    def test_application_survives_terminal_hangup(self):
        with tempfile.TemporaryDirectory() as path:
            tmp_path = Path(path)
            env = {'QT_QPA_PLATFORM': 'offscreen', 'PYCAD_DATA_DIR': str(tmp_path / 'profile'),
                   'XDG_DATA_HOME': str(tmp_path / 'xdg')}
            with patch.object(launcher, 'ROOT', tmp_path), patch.object(launcher, 'prepare', return_value=sys.executable), patch.dict(os.environ, env):
                self.exercise(tmp_path)

    def exercise(self, tmp_path):
        entry = launcher.install_desktop(tmp_path)
        entry.write_text(entry.read_text().replace('Terminal=false', 'Terminal=true'))
        (tmp_path / 'main.py').write_text(
            'import os,sys,time,json,pathlib\n'
            'assert not os.isatty(0) and not os.isatty(1)\n'
            'print("child log ready", flush=True)\n'
            'ready=pathlib.Path("ready.tmp")\n'
            'ready.write_text(json.dumps([os.getpid(),os.getsid(0),sys.argv[1:]]))\n'
            'ready.rename("ready")\n'
            'while not pathlib.Path("after-hangup").exists(): time.sleep(.025)\n'
            'pathlib.Path("survived").touch()\n'
        )
        drawing = tmp_path / 'Drawing ü.dxf'
        parent, terminal = pty.fork()
        if parent == 0:
            try:
                assert os.isatty(0)
                assert launcher.main([str(drawing)]) == 0
                while True:
                    signal.pause()
            finally:
                os._exit(1)
        child = None
        try:
            def await_file(name):
                deadline = time.monotonic() + 8
                while not (tmp_path / name).exists() and time.monotonic() < deadline:
                    time.sleep(.025)
                assert (tmp_path / name).exists(), name
            await_file('ready')
            child, session, arguments = json.loads((tmp_path / 'ready').read_text())
            assert child == session != parent
            assert arguments == [str(drawing)]
            os.close(terminal)
            terminal = None
            _, status = os.waitpid(parent, 0)
            parent = None
            assert os.WIFSIGNALED(status) and os.WTERMSIG(status) == signal.SIGHUP
            (tmp_path / 'after-hangup').touch()
            await_file('survived')
            assert 'Terminal=false' in entry.read_text()
            log = next((tmp_path / 'profile/logs').glob('startup-linux-*.log'))
            assert 'child log ready' in log.read_text()
        finally:
            if terminal is not None:
                os.close(terminal)
            for pid in (parent, child):
                if pid:
                    try:
                        os.kill(pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass
            if parent:
                os.waitpid(parent, 0)
