"""No live workspace objects; export tasks never spawn converters."""
import json,sys
from pathlib import Path

def execute(request):
    task=request['task'];p=request['parameters']
    if task=='cache_lookup':
        from .import_cache import lookup
        return lookup(**p)
    if task=='cache_store':
        from .import_cache import store
        return store(**p,raw=Path(request['drawing']).read_bytes())
    if task=='native_read':
        from .native_io import parse_payload
        raw=Path(p['source']).read_bytes();parse_payload(raw.decode('utf-8'));return dict(raw=raw.decode('utf-8'))
    if task=='health':
        from .native_io import load_project
        from .editing import health
        try:doc=load_project(request['drawing'])
        except ValueError as ex:return dict(rows=[dict(code='INVALID_DATA',message=str(ex),ids=[],severity='Error')],objects=0,note='Native validation failed before detailed health scan')
        return health(doc,**p)
    if task=='standards_batch':
        from .standards_batch import run
        return run(**p)
    if task=='stability':
        from .native_io import load_project
        from .stability import measure
        return measure(load_project(request['drawing']),p.get('repeats',3))
    if task=='export':
        from .native_io import load_project,save_project
        from .dxf_io import export_dxf
        from .plotting import publish_pdf
        doc=load_project(request['drawing']);target=Path(p['stage']);kind=p['format']
        if kind=='Native':save_project(doc,target,backup=False)
        elif kind=='DXF':export_dxf(doc,str(target))
        elif kind=='PDF':publish_pdf(doc,str(target),p['spaces'],preset=p.get('preset'))
        else:raise ValueError('Choose Native, DXF or PDF')
        from .dxf_io import export_warnings
        return dict(bytes=target.stat().st_size,warnings=export_warnings(doc) if kind=='DXF' else list(doc.import_warnings))
    raise ValueError('Unknown desk task')

def main(source,result):
    from PyQt6.QtWidgets import QApplication
    app=QApplication([])
    try:output=dict(ok=True,value=execute(json.loads(Path(source).read_text())))
    except Exception as ex:output=dict(ok=False,error=str(ex))
    Path(result).write_text(json.dumps(output,ensure_ascii=False,allow_nan=False),encoding='utf-8')
    from .document_lifecycle import dispose_documents,drain_deferred_deletes
    dispose_documents();drain_deferred_deletes();return 0 if output['ok'] else 1
if __name__=='__main__':sys.exit(main(*sys.argv[1:3]))
