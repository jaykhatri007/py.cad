"""Real cmd.exe launcher regression; skipped on non-Windows hosts.

Uses a temporary project and real dependencies, never the user's .venv.
Run this test with network access on first setup.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


@unittest.skipUnless(sys.platform == "win32", "Requires Windows cmd.exe")
class WindowsLauncherTest(unittest.TestCase):
    def test_setup_repair_offline_restart_and_arguments(self):
        source = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(prefix="pycad-launcher-") as tmp:
            project = Path(tmp) / "CAD project (test)!"
            project.mkdir()
            shutil.copy2(source / "start_windows.bat", project)
            shutil.copy2(source / "requirements.txt", project)
            # Model an environment left behind after uninstalling its runtime.
            (project / ".venv").mkdir()
            (project / ".venv" / "keep.txt").write_text("preserve me")
            (project / "main.py").write_text(
                "import json, pathlib, sys\n"
                "from PyQt6.QtWidgets import QApplication\n"
                "import ezdxf\n"
                "app = QApplication([])\n"
                "pathlib.Path('launched.json').write_text(json.dumps(sys.argv[1:]))\n",
                encoding="utf-8",
            )
            env = dict(
                os.environ,
                PYCAD_PYTHON="",
                # Reproduce the reported case: Python on PATH without py.exe.
                PATH=os.pathsep.join((
                    str(Path(sys.executable).parent),
                    str(Path(os.environ["SystemRoot"]) / "System32"),
                )),
                PYCAD_NO_INSTALL="1",
                PYCAD_NO_PAUSE="1",
                PYCAD_SETUP_ONLY="1",
                QT_QPA_PLATFORM="offscreen",
            )
            cmd = os.environ.get("COMSPEC", "cmd.exe")

            def run_launcher(arguments=""):
                command = f'"{cmd}" /d /v:off /s /c ""{project / "start_windows.bat"}"{arguments}"'
                result = subprocess.run(
                    command,
                    cwd=project, env=env, capture_output=True, text=True,
                    errors="replace", timeout=600,
                )
                self.assertEqual(
                    result.returncode, 0, result.stdout + "\n" + result.stderr
                )

            run_launcher()
            backups = list(project.glob(".venv-backup-*"))
            self.assertEqual(len(backups), 1)
            self.assertEqual((backups[0] / "keep.txt").read_text(), "preserve me")
            self.assertTrue((project / ".venv/Scripts/python.exe").is_file())
            marker = project / ".venv/pycad-requirements.sha256"
            self.assertTrue(marker.is_file())
            self.assertFalse((project / "launched.json").exists())
            original_marker_time = marker.stat().st_mtime_ns
            # Existing setup must start without contacting a package index.
            env["PYCAD_SETUP_ONLY"] = "0"
            env["PIP_NO_INDEX"] = "1"
            run_launcher(' "drawing with spaces.pycad"')
            self.assertEqual(
                json.loads((project / "launched.json").read_text()),
                ["drawing with spaces.pycad"],
            )
            self.assertEqual(marker.stat().st_mtime_ns, original_marker_time)
            self.assertEqual(len(list(project.glob(".venv-backup-*"))), 1)


if __name__ == "__main__":
    unittest.main()
