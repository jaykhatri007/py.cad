"""Simulate abrupt termination after a committed private recovery checkpoint."""
import argparse,json,os,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

def phase(name,result):
    from PyQt6.QtWidgets import QApplication
    from pycad.main_window import MainWindow
    from pycad.document import AddEntityCommand
    from pycad.geometry import Point,LineEntity
    from pycad import appsettings
    app=QApplication([]);w=MainWindow()
    if name=='write':
        appsettings.get_settings().setValue('recovery/automatic_restore',True);w.document.undo_stack.push(AddEntityCommand(w.document,LineEntity(Point(1,2),Point(8,9))));w._do_autosave();assert Path(appsettings.RECOVERY_PATH).is_file();os._exit(17)
    w.show()
    for _ in range(5):app.processEvents()
    assert len(w.document.entities)==1 and w.document.filepath is None and w.document.dirty
    line=w.document.entities[0];assert line.p1.as_tuple()==(1,2) and line.p2.as_tuple()==(8,9)
    Path(result).write_text(json.dumps(dict(abrupt_exit_after_checkpoint=True,automatic_restore=True,unsaved_copy=True,original_files_overwritten=False)))
    for session in w.drawing_tabs.sessions:session['doc'].mark_saved()
    w.close()

def run(root):
    root=Path(root).resolve()
    if root.exists():raise ValueError('Choose a new isolated test directory')
    root.mkdir(parents=True);result=root/'result.json';env={**os.environ,'PYCAD_DATA_DIR':str(root),'QT_QPA_PLATFORM':'offscreen'}
    command=[sys.executable,str(Path(__file__).resolve())]
    first=subprocess.run([*command,'--phase','write','--result',str(result)],env=env,timeout=60,capture_output=True)
    if first.returncode!=17:raise ValueError(first.stderr.decode('utf-8','replace'))
    subprocess.run([*command,'--phase','restore','--result',str(result)],check=True,env=env,timeout=60,capture_output=True);return json.loads(result.read_text())
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root');p.add_argument('--phase');p.add_argument('--result');a=p.parse_args()
    if a.phase:phase(a.phase,a.result)
    else:print(json.dumps(run(a.root),indent=2))
