"""Isolated quantity analysis; no live drawing objects or network access."""
import json
import sys
from pathlib import Path


def run(task,source,result):
    try:
        from PyQt6.QtWidgets import QApplication
        app=QApplication([])
        from .native_io import load_project,atomic_write
        doc=load_project(source)
        if task=='takeoff':
            from .workflow_data import proposed_tags
            tags,specs,report=proposed_tags(doc);value=dict(tags=tags,specs=specs,report=report)
        elif task=='pdf_vectors':
            from .pdf_vectors import import_page
            from .native_io import entity_to_dict
            entities,details=import_page(**json.loads((Path(source).parent/'parameters.json').read_text()));value=dict(entities=[entity_to_dict(e) for e in entities],details=details)
        elif task=='regional_cache':
            from .paged_drawing import create,Store
            path=Path(result).parent/'regional.pycaddb';create(doc,path);store=Store(path);value=dict(entities=store.count);store.close()
        else:raise ValueError('Unknown workflow analysis')
        output=dict(ok=True,value=value)
    except Exception as ex:output=dict(ok=False,error=str(ex))
    Path(result).write_text(json.dumps(output,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    return 0 if output['ok'] else 1


if __name__=='__main__':sys.exit(run(*sys.argv[1:4]))
