"""Synthetic offscreen MainWindow drafting benchmark; not physical input latency.
Usage: python benchmark_drafting.py SOURCE_ROOT OUTPUT_JSON [SEGMENTS] [layered|long-dashed]
"""
import os,sys,time,json,statistics
from pathlib import Path
root=Path(sys.argv[1]).resolve();out=Path(sys.argv[2]).resolve();count=int(sys.argv[3]) if len(sys.argv)>3 else 50
os.environ['PYCAD_GRAPHICS']='software';os.environ['QT_QPA_PLATFORM']='offscreen';os.environ['PYCAD_DATA_DIR']=str(out.parent/('profile-'+out.stem));os.environ.pop('PYCAD_LEGACY_DISPLAY',None)
sys.path.insert(0,str(root))
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt,QPointF,QPoint
from PyQt6.QtGui import QImage,QPainter,QWheelEvent
from pycad.main_window import MainWindow
from pycad.document import Document
from pycad.geometry import Point,LineEntity
from pycad._version import __version__
app=QApplication([]);w=MainWindow();w.resize(1250,850);w.show();d=Document();d.entities=[LineEntity(Point(i%1000,i//1000),Point(i%1000+.7,i//1000+.5)) for i in range(80000)];
if len(sys.argv)>4 and sys.argv[4]=='layered':
 from pycad.geometry import TextEntity,HatchEntity
 from pycad.productivity import survey_config
 for i in range(8):d.layers.layers[f'L{i}']=dict(d.layers.layers['0'])
 for i,e in enumerate(d.entities):e.layer=f'L{min(7,i//10000)}'
 for i in range(100):
  x=i*9;d.entities.extend([TextEntity(Point(x,5),'Mixed note',layer='L1'),HatchEntity([Point(x,10),Point(x+3,10),Point(x+3,13),Point(x,13)],pattern='SOLID',layer='L2')])
 d.extensions={'production':{'sheet_sets':{}},'productivity':{'survey':{'site':survey_config()}}}
if len(sys.argv)>4 and sys.argv[4]=='long-dashed':d.current_linetype='DASHED'
w.drawing_tabs.add_document(d);c=w.canvas;c.zoom=.7;c.pan_offset=QPointF(500,40);c.grid_enabled=False;c.snap_enabled=False
kinds=[]
def wait_ready():
 deadline=time.monotonic()+120;c.viewport().update()
 while time.monotonic()<deadline:
  app.processEvents();kinds.append(c.__dict__.get('_last_draw_kind'))
  if c.__dict__.get('_render_process_error'):raise RuntimeError(c._render_process_error)
  ctrl=c.__dict__.get('_scene_controller');delta=getattr(ctrl,'delta',None)
  if ctrl and ctrl.scene is not None and c.__dict__.get('_last_draw_kind')=='persistent vector scene' and (ctrl.signature[1]==d.render_revision or delta and delta.state.ready and delta.state.revision==d.render_revision and delta.cursor==delta.state.sequence):return
  time.sleep(.001)
 raise RuntimeError('Timed out waiting for scene')
wait_ready();w.set_tool('LINE');w._on_world_clicked(500,40,'',Qt.MouseButton.LeftButton.value);wait_ready();ctrl=c._scene_controller;jobs=ctrl.jobs;scene=ctrl.scene;kinds.clear();callbacks=[];totals=[]
for i in range(count):
 start=time.perf_counter();w._on_world_clicked((5500 if i%2==0 else 500) if len(sys.argv)>4 and sys.argv[4]=='long-dashed' else 501+i*.5,41+i*.1,'',Qt.MouseButton.LeftButton.value);callbacks.append((time.perf_counter()-start)*1000);wait_ready();totals.append((time.perf_counter()-start)*1000)
result=dict(version=__version__,objects_before=len(d.entities)-count,segments=count,callback_median_ms=statistics.median(callbacks),callback_max_ms=max(callbacks),commit_to_ready_median_ms=statistics.median(totals),commit_to_ready_max_ms=max(totals),drafting_jobs=ctrl.jobs-jobs,same_base_scene=ctrl.scene is scene,preparing_observations=kinds.count('persistent scene preparing'))
w.cancel_command();wait_ready();zoom=[];jobs=ctrl.jobs
for delta in [120]*8+[-120]*8:
 event=QWheelEvent(QPointF(300,200),QPointF(300,200),QPoint(),QPoint(0,delta),Qt.MouseButton.NoButton,Qt.KeyboardModifier.NoModifier,Qt.ScrollPhase.NoScrollPhase,False);c.wheelEvent(event)
 image=QImage(c.viewport().size(),QImage.Format.Format_ARGB32_Premultiplied);image.fill(0);p=QPainter(image);p.setRenderHints(c.renderHints());start=time.perf_counter();c._draw_cached_entities(p);zoom.append((time.perf_counter()-start)*1000);p.end();app.processEvents()
result.update(zoom_median_ms=statistics.median(zoom),zoom_max_ms=max(zoom),additional_zoom_jobs=ctrl.jobs-jobs,physical_gpu_tested=False,physical_input_latency_measured=False)
out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2));d.mark_saved();w.close();app.processEvents()
