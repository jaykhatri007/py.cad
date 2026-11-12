"""Run the same signed Microsoft runtime repair as the native setup."""

import base64
import os
from pathlib import Path
import subprocess
import sys


def repair(log):
    text = Path(log).read_text(encoding="utf-8", errors="replace")[-16000:].lower()
    if sys.platform != "win32" or not any(s in text for s in ("dll load failed", "vcruntime", "0xc0000135")):
        return 1
    root = Path(os.environ.get("LOCALAPPDATA") or os.environ["TEMP"]) / "PyCAD" / "runtime-repair"
    target = str(root / "vc_redist.x64.exe").replace("'", "''")
    script = "$pycadRuntimeFile='" + target + "';\n" + (Path(__file__).resolve().parents[1] / "installer/repair-runtime.ps1").read_text()
    encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    print("A Microsoft Visual C++ runtime is needed. Approve Windows' Microsoft authorization prompt.", flush=True)
    return subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded], check=False).returncode


if __name__ == "__main__":
    sys.exit(repair(sys.argv[1]))
