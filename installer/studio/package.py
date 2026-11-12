"""Wrap the verified 16.44 Linux engine without modifying the engine or CAD payload."""
import argparse
import gzip
import io
from pathlib import Path
import re
import tarfile

HERE = Path(__file__).resolve().parent
MARKER = b'# __PYCAD_NATIVE_PAYLOAD__\n'
HEADER = """#!/bin/sh
# PY.cad Studio Setup for Linux x64
set -eu
case "$(uname -s):$(uname -m)" in Linux:x86_64|Linux:amd64) ;; *)
  echo "Use the appropriate installer for this operating system and CPU." >&2; exit 1;;
esac
temp=$(mktemp -d "${TMPDIR:-/tmp}/pycad-studio.XXXXXXXX")
trap 'rm -rf -- "$temp"' EXIT
trap 'exit 130' INT
trap 'exit 143' HUP TERM
dd if="$0" of="$temp/engine" bs=1M iflag=skip_bytes,count_bytes skip=ENGINE_OFFSET count=ENGINE_SIZE status=none
chmod 700 "$temp/engine"
if [ "${1:-}" = "--uninstall" ]; then
  shift
  dd if="$0" bs=1M iflag=skip_bytes skip=ART_OFFSET status=none | tar -xz -C "$temp"
  python3 -I "$temp/uninstall.py" "$@"
  exit $?
elif [ "${1:-}" = "--classic" ]; then
  shift
elif [ "$#" -eq 0 ] || { [ "$#" -eq 1 ] && [ "$1" = "--studio-preview" ]; }; then
  preview=
  if [ "$#" -eq 1 ]; then preview=--preview; fi
  status=77
  if command -v python3 >/dev/null 2>&1; then
    dd if="$0" bs=1M iflag=skip_bytes skip=ART_OFFSET status=none | tar -xz -C "$temp"
    status=0
    if [ -n "$preview" ]; then
      python3 -I "$temp/studio.py" "$temp/engine" "$preview" || status=$?
    else
      python3 -I "$temp/studio.py" "$temp/engine" || status=$?
    fi
  fi
  if [ "$status" -ne 77 ]; then exit "$status"; fi
  if [ -n "$preview" ]; then
    echo "Studio preview needs a desktop with Python 3 and GTK 3." >&2; exit 77
  fi
  echo "Studio window unavailable; opening classic setup." >&2
fi
"$temp/engine" "$@"
exit $?
# __PYCAD_STUDIO_PAYLOAD__
"""

def engine_bytes(path):
    header, sep, data = path.read_bytes().partition(MARKER)
    match = re.search(rb'offset=(\d+); size=(\d+)',header)
    if not sep or not match or not data.startswith(b'\x7fELF'):
        raise ValueError('Expected the original Linux x64 installer')
    offset, size = map(int,match.groups())
    if offset != len(header)+len(sep)+1 or size != len(data):
        raise ValueError('Original engine payload boundaries do not match')
    return data

def bundle():
    out = io.BytesIO()
    with gzip.GzipFile(fileobj=out,mode='wb',mtime=0) as zipped, tarfile.open(fileobj=zipped,mode='w') as archive:
        for name in ('studio.py','transfer.py','uninstall.py','runtime-sources.json','art/banner.png','art/construction.gif','licenses.txt'):
            data = (HERE.parent/'assets/legal.txt' if name == 'licenses.txt' else HERE.parent/name if name == 'runtime-sources.json' else HERE/name).read_bytes()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info,io.BytesIO(data))
    return out.getvalue()

def build(original, output):
    engine = engine_bytes(original)
    def header(offset, size, art):
        return HEADER.replace('ENGINE_OFFSET',f'{offset:020d}').replace('ENGINE_SIZE',f'{size:020d}').replace('ART_OFFSET',f'{art:020d}').encode()
    start = len(header(0,0,0))
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open('wb') as f:
        f.write(header(start,len(engine),start+len(engine)))
        f.write(engine)
        f.write(bundle())
    output.chmod(0o755)

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('original',type=Path)
    p.add_argument('output',type=Path)
    a = p.parse_args()
    build(a.original,a.output)
