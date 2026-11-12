"""Opt-in read-only project import/interaction measurements, on private snapshots."""
import sys,os,json,time,hashlib,argparse,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
_APPLICATION=None
def run(paths,repeats=2):
 global _APPLICATION
 from PyQt6.QtWidgets import QApplication
 from pycad.main_window import MainWindow
 from pycad.native_io import load_project
 from pycad.stability import measure
 _APPLICATION=QApplication.instance() or QApplication([]);app=_APPLICATION;mw=MainWindow();rows=[]
 for source in paths:
  path=Path(source).resolve();before=hashlib.sha256(path.read_bytes()).hexdigest();imports=[];summary=None
  for i in range(repeats):
   start=time.perf_counter()
   if path.suffix.lower()=='.dwg':
    from pycad.dwg_ui import load_dwg
    doc=load_dwg(mw,str(path))
   elif path.suffix.lower()=='.dxf':
    from pycad.import_ui import load_dxf
    doc=load_dxf(mw,str(path))
   else:doc=load_project(path)
   if doc is None:raise ValueError('Import cancelled')
   imports.append((time.perf_counter()-start)*1000)
   if summary is None:summary=measure(doc,2)
  rows.append(dict(file=path.name,source_sha256=before,source_unchanged=hashlib.sha256(path.read_bytes()).hexdigest()==before,import_ms=imports,measurements=summary))
 for session in mw.drawing_tabs.sessions:session['doc'].mark_saved()
 mw.close()
 from pycad.document_lifecycle import dispose_documents,drain_deferred_deletes
 mw.deleteLater();dispose_documents();drain_deferred_deletes()
 return dict(rows=rows,note='Read-only originals. GUI DWG import can use the normal validated cache on later repetitions. These are host-specific measurements, not a GPU or cross-platform performance guarantee.')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('drawings',nargs='+');p.add_argument('--repeats',type=int,default=2);p.add_argument('--report',required=True);a=p.parse_args()
 if not 1<=a.repeats<=10:p.error('Use 1–10 import repetitions')
 os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
 with tempfile.TemporaryDirectory(prefix='pycad-stability-profile-') as profile:
  os.environ['PYCAD_DATA_DIR']=profile;result=run(a.drawings,a.repeats)
 Path(a.report).write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
