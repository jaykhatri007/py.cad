#!/bin/sh
# macOS companion for the default per-user PY.cad installation.
set -eu
root="$HOME/Library/Application Support/PyCAD/Installation"
dir=$(CDPATH='' cd -P "$(dirname "$0")" && pwd)
release=$(/usr/bin/plutil -extract release raw -o - "$root/current.json") || {
  echo 'No managed PY.cad installation was found.' >&2
  exit 1
}
printf '%s\n' "$release" | /usr/bin/grep -Eq '^pycad-[0-9]+(\.[0-9]+){1,3}-[0-9a-f]{12}$' || {
  echo 'The PY.cad installation receipt is invalid.' >&2
  exit 1
}
python="$root/releases/$release/env/bin/python"
if [ ! -x "$python" ]; then
  echo 'The private Python runtime is missing. Repair the installation before running this uninstaller.' >&2
  exit 1
fi
exec "$python" -I "$dir/uninstall.py"
