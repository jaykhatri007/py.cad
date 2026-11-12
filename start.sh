#!/usr/bin/env bash
# Ubuntu/Linux entry point. No activation, sudo pip, or executable-bit required.
set -euo pipefail
pycad_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ -n "${PYCAD_PYTHON:-}" ]]; then
    pycad_candidates=("$PYCAD_PYTHON")
else
    # Ubuntu 26.04 ships Python 3.14 as its system Python. Older Ubuntu
    # releases fall through to the compatible interpreter they provide.
    pycad_candidates=(python3.14 python3.13 python3.12 python3.11 python3)
fi
for pycad_python in "${pycad_candidates[@]}"; do
    if "$pycad_python" -c 'import sys,struct; assert sys.implementation.name == "cpython" and (3,11) <= sys.version_info[:2] <= (3,14) and struct.calcsize("P")==8' >/dev/null 2>&1; then
        exec "$pycad_python" "$pycad_root/scripts/linux_launcher.py" "$@"
    fi
done
echo "PY.cad needs 64-bit CPython 3.11–3.14 (3.12 recommended for optional CadQuery)." >&2
echo "On Ubuntu 24.04/26.04: run bash setup_ubuntu.sh, or install python3 and python3-venv." >&2
echo "For a custom interpreter, set PYCAD_PYTHON to its executable path." >&2
exit 1
