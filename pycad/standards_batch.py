"""Native-file standards application to exclusive new outputs; source files stay intact."""
import json,os,time,hashlib
from pathlib import Path
from .coordination import read_standard,validate_standard,apply_standard
from .native_io import load_project,save_project

def run(paths,profile,output,stage):
 validate_standard(profile);root=Path(output);root.mkdir(parents=True,exist_ok=True);stage=Path(stage);stage.mkdir(parents=True,exist_ok=True);rows=[]
 for index,source in enumerate(paths):
  p=Path(source);target=root/(p.stem+'-standard.pycad')
  if p.suffix.lower()!='.pycad':rows.append(dict(source=str(p),status='Skipped',message='Convert to native .pycad first'));continue
  if target.exists() or target.resolve()==p.resolve():rows.append(dict(source=str(p),status='Skipped',message='Output exists or is the input'));continue
  try:
   before=hashlib.sha256(p.read_bytes()).hexdigest();doc=load_project(p);apply_standard(doc,profile);temporary=stage/(str(index)+'.pycad');save_project(doc,temporary,backup=False)
   # Same-filesystem hard link publishes complete bytes exclusively. Do not fall
   # back to a partially visible copy on filesystems without hard-link support.
   if hashlib.sha256(p.read_bytes()).hexdigest()!=before:raise ValueError('Source changed during processing; output not published')
   os.link(temporary,target);unchanged=hashlib.sha256(p.read_bytes()).hexdigest()==before;rows.append(dict(source=str(p),output=str(target),status='Completed',source_unchanged=unchanged))
  except (OSError,ValueError,TypeError) as ex:rows.append(dict(source=str(p),status='Failed',message=str(ex)))
 return dict(rows=rows,note='Existing outputs are never replaced. Completed outputs remain if a later job is cancelled. Native-only batch; drawing units must match the profile.')
