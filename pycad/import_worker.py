"""Isolated DXF loader. The GUI may kill this process when opening is cancelled."""

import json
import hashlib
import sys
import traceback
from pathlib import Path


def run(source, result, error, original_source=None, import_note=None):
    import time
    started=time.perf_counter()
    try:
        from .dxf_io import import_dxf
        from .native_io import save_project

        print("Mapping DWG data…" if Path(source).suffix.lower()==".json" else "Reading and converting DXF…", flush=True)
        if Path(source).suffix.lower() == '.json':
            from .dwg_json import import_json
            document = import_json(source, original_source)
        else:
            document = import_dxf(source, original_source=original_source)
        if import_note:
            document.import_warnings = sorted(set(document.import_warnings + [import_note]))
        print(f"Parsed {len(document.entities)} objects and {len(document.blocks)} blocks; checking workspace…", flush=True)
        save_project(document, result, backup=False)
        Path(error).write_text(json.dumps({"sha256": hashlib.sha256(Path(result).read_bytes()).hexdigest(),"import_metrics":{"entities":len(document.entities),"blocks":len(document.blocks),"worker_seconds":time.perf_counter()-started}}), encoding="utf-8")
        return 0
    except Exception as ex:
        Path(error).write_text(json.dumps({"message": str(ex), "type": type(ex).__name__}), encoding="utf-8")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(run(*sys.argv[1:6]))

