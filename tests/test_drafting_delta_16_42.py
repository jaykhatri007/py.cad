import gc,weakref
import pytest
from PyQt6.QtCore import QPointF,Qt
from PyQt6.QtGui import QFont,QPainter
from PyQt6.QtTest import QTest
from pycad.document import Document,AddEntityCommand,TranslateEntitiesCommand,DeleteEntitiesCommand,SetAttrCommand
from pycad.geometry import Point,LineEntity,PolylineEntity,DimensionEntity
from pycad.canvas import CadCanvas
from pycad.persistent_scene import record_vector,regenerate,replay
from test_persistent_scene_16_40 import ready,frame

@pytest.fixture
def drawing(qapp,monkeypatch):
 monkeypatch.delenv('PYCAD_LEGACY_DISPLAY',raising=False)
 d=Document();d.entities=[LineEntity(Point(i,0),Point(i,20)) for i in range(8000)]
 c=CadCanvas(d);c.resize(900,600);c.zoom=2;c.pan_offset=QPointF(30,10);c.show();ready(qapp,c)
 yield c
 c._scene_controller.close();c.hide();c.deleteLater();qapp.processEvents()

def test_add_move_undo_redo_without_capture(qapp,drawing,monkeypatch):
 c=drawing;d=c.document;ctrl=c._scene_controller;scene=ctrl.scene;jobs=ctrl.jobs
 monkeypatch.setattr(ctrl.capture_task,'start',lambda *a:pytest.fail('Full capture on independent edit'))
 e=LineEntity(Point(0,1),Point(20,1));d.check_issues=['old'];d.undo_stack.push(AddEntityCommand(d,e));assert not d.check_issues
 for cmd in [TranslateEntitiesCommand(d,[e],5,5)]:d.undo_stack.push(cmd);frame(c)
 d.undo_stack.undo();frame(c);d.undo_stack.undo();frame(c);assert d.find_by_id(e.id) is None
 d.undo_stack.redo();frame(c);assert d.find_by_id(e.id) is e
 assert ctrl.scene is scene and ctrl.jobs==jobs and c._last_draw_kind=='persistent vector scene'

def test_existing_move_patches_only_batch(qapp,drawing):
 c=drawing;d=c.document;ctrl=c._scene_controller;scene=ctrl.scene;jobs=ctrl.jobs;e=d.entities[1]
 d.undo_stack.push(TranslateEntitiesCommand(d,[e],1000,100));frame(c)
 assert ctrl.scene is scene and ctrl.jobs==jobs and len(ctrl.delta.patches)==1
 assert e not in d.spatial_index.query((0,0,2,21))
 assert e in d.spatial_index.query((1000,100,1002,121))
 d.undo_stack.undo();frame(c);assert e.p1.x==1

def test_associative_source_falls_back(qapp,drawing):
 c=drawing;d=c.document;e=d.entities[0];dim=DimensionEntity(Point(0,0),Point(0,20),Point(2,0),source_line_id=e.id)
 d.entities.append(dim);d.dirty=True;d.sync_associative();qapp.processEvents();ready(qapp,c);jobs=c._scene_controller.jobs
 d.undo_stack.push(TranslateEntitiesCommand(d,[e],5,5));qapp.processEvents();ready(qapp,c)
 assert c._scene_controller.jobs>jobs and dim.p1.as_tuple()==e.p1.as_tuple()

def test_main_window_line_clicks_and_coordinates_keep_scene(qapp,monkeypatch):
 monkeypatch.delenv('PYCAD_LEGACY_DISPLAY',raising=False)
 from pycad.main_window import MainWindow
 w=MainWindow();w.show();c=w.canvas;ready(qapp,c);scene=c._scene_controller.scene;jobs=c._scene_controller.jobs
 w.command_line.setText('L');w._on_command_entered()
 for x in (1,5,10,15):w._on_world_clicked(x,2,'',Qt.MouseButton.LeftButton.value);qapp.processEvents()
 w.command_line.setText('20,2');w._on_command_entered();QTest.qWait(200);frame(c)
 assert len(w.document.entities)==4 and c._scene_controller.scene is scene and c._scene_controller.jobs==jobs
 w.document.mark_saved();w.close();qapp.processEvents()

def test_stationary_frame_reused_for_additions(qapp,drawing):
 c=drawing;frame(c);image=c._static_scene_frame['image'];scene=c._scene_controller.scene
 for i in range(10):
  c.document.undo_stack.push(AddEntityCommand(c.document,LineEntity(Point(i,1),Point(i,5))));frame(c)
  assert c._static_scene_frame['image'] is image
 assert c._scene_controller.scene is scene

def test_native_line_paths_equal_picture(qapp,drawing):
 c=drawing;scene=c._scene_controller.scene
 from PyQt6.QtGui import QImage
 def render():
  image=QImage(c.viewport().size(),QImage.Format.Format_ARGB32_Premultiplied);image.fill(0);p=QPainter(image);p.setRenderHints(c.renderHints())
  try:replay(c,p,scene)
  finally:p.end()
  return image
 native=render();paths=scene['native_paths'];scene['native_paths']=[[] for _ in paths]
 try:assert render()==native
 finally:scene['native_paths']=paths

def test_delete_undo_preserves_scene(qapp,drawing):
 c=drawing;d=c.document;e=d.entities[2];scene=c._scene_controller.scene;jobs=c._scene_controller.jobs
 d.undo_stack.push(DeleteEntitiesCommand(d,[e]));frame(c);assert not d.contains_entity(e)
 d.undo_stack.undo();frame(c);assert d.contains_entity(e)
 assert c._scene_controller.scene is scene and c._scene_controller.jobs==jobs

def test_recording_does_not_leave_cycles(qapp,monkeypatch):
 from pycad.async_display import SnapshotCanvas
 from pycad.appearance import colors
 refs=[];original=SnapshotCanvas.__init__
 def track(self,*a,**kw):original(self,*a,**kw);refs.append(weakref.ref(self))
 monkeypatch.setattr(SnapshotCanvas,'__init__',track)
 d=Document();e=LineEntity(Point(0,0),Point(5,5));c=CadCanvas(d);was=gc.isenabled();gc.disable()
 try:
  for _ in range(10):record_vector(d,[e],dict(colors=colors(c),font=QFont().toString(),hints=0,boq=False))
  assert all(ref() is None for ref in refs)
 finally:
  if was:gc.enable()
  c.deleteLater();qapp.processEvents()

def test_delete_undo_after_regen_restores_order(qapp,drawing):
 c=drawing;d=c.document;e=d.entities[0];d.undo_stack.push(DeleteEntitiesCommand(d,[e]));frame(c)
 regenerate(c);qapp.processEvents();ready(qapp,c);jobs=c._scene_controller.jobs
 d.undo_stack.undo();qapp.processEvents();ready(qapp,c)
 assert d.entities[0] is e and c._scene_controller.jobs>jobs

def test_large_proposed_polyline_falls_back(qapp,drawing):
 from pycad.edit_journal import begin,end
 d=drawing.document;e=PolylineEntity([Point(0,0),Point(1,1)]);d.undo_stack.push(AddEntityCommand(d,e));frame(drawing)
 token=begin(d,SetAttrCommand(d,e,'points',e.points,[Point(i,0) for i in range(256)]))
 try:assert token[1] is None
 finally:end(d,token)
