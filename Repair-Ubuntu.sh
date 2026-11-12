#!/usr/bin/env bash
set -euo pipefail
pycad_repair_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
bash "$pycad_repair_root/start.sh" --setup-only
bash "$pycad_repair_root/start.sh" --diagnose
printf '%s\n' 'Repair complete. Start PY.cad with: bash start.sh'
