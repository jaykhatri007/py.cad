import copy
import pytest
from PyQt6.QtCore import QPointF,Qt
from PyQt6.QtGui import QImage,QPainter
from pycad.document import Document,AddEntityCommand
from pycad.geometry import Point,LineEntity
from pycad.canvas import CadCanvas
from pycad.constraints import make_constraint
from pycad.immediate_lines import record,draw,committed
from test_persistent_scene_16_40 import ready,frame

@pytest.fixture
def drawing(qapp,monkeypatch):
 monkeypatch.delenv('PYCAD_LEGACY_DISPLAY',raising=False)
 d=Document();d.entities=[LineEntity(Point(i,0),Point(i,20)) for i in range(8000)]
 c=CadCanvas(d);c.resize(900,600);c.zoom=5;c.pan_offset=QPointF(20,10);c.show();ready(qapp,c)
 yield c
 c._scene_controller.close();c.hide();c.deleteLater();qapp.processEvents()

@pytest.mark.parametrize('linetype',['CONTINUOUS','DASHED','CENTER','DOTTED'])
def test_long_bylayer_lines_never_prepare_scene(qapp,drawing,monkeypatch,linetype):
 c=drawing;d=c.document;d.layers.layers['0']['linetype']=linetype;d.dirty=True;qapp.processEvents();ready(qapp,c);ctrl=c._scene_controller;scene=ctrl.scene;jobs=ctrl.jobs
 monkeypatch.setattr(ctrl.capture_task,'start',lambda *a:pytest.fail('Scene capture on simple line'))
 e=LineEntity(Point(-10000,-10),Point(10000,-10));d.undo_stack.push(AddEntityCommand(d,e));image=frame(c)
 assert ctrl.scene is scene and ctrl.jobs==jobs and c._last_draw_kind=='persistent vector scene'
 row=round(c.world_to_screen(0,-10).y())
 assert any(image.pixelColor(x,y).alpha() for y in range(row-1,row+2) for x in range(image.width()))
 for _ in range(2):d.undo_stack.undo();frame(c);d.undo_stack.redo();frame(c)
 assert ctrl.scene is scene and ctrl.jobs==jobs


def test_existing_constraints_do_not_solve_unrelated_line(qapp,monkeypatch):
 monkeypatch.delenv('PYCAD_LEGACY_DISPLAY',raising=False)
 d=Document();a=LineEntity(Point(0,0),Point(5,0));d.entities=[a];d.constraints=[make_constraint(d,'fixed',[{'entity':a.id}])];before=copy.deepcopy(d.constraints)
 c=CadCanvas(d);c.show();ready(qapp,c);ctrl=c._scene_controller;scene=ctrl.scene;jobs=ctrl.jobs
 import pycad.constraints as module
 monkeypatch.setattr(module,'geometry_state',lambda *a:pytest.fail('Whole drawing solver snapshot on unrelated line'))
 e=LineEntity(Point(5,5),Point(10,10));d.undo_stack.push(AddEntityCommand(d,e));frame(c);d.undo_stack.undo();frame(c);d.undo_stack.redo();frame(c)
 assert d.constraints==before and a.p1.as_tuple()==(0,0) and a.p2.as_tuple()==(5,0) and ctrl.scene is scene and ctrl.jobs==jobs
 c._scene_controller.close();c.hide();c.deleteLater();qapp.processEvents()


def test_line_ink_is_visible_before_worker_finishes(drawing,monkeypatch):
 c=drawing;d=c.document;ctrl=c._scene_controller
 # Stall a necessary global rebuild rather than waiting for its worker.
 d.dirty=True;monkeypatch.setattr(ctrl.capture_task,'start',lambda *a:None);before=frame(c)
 e=LineEntity(Point(10,-10),Point(20,-10));d.undo_stack.push(AddEntityCommand(d,e));committed(c,e);image=frame(c);point=c.world_to_screen(15,-10).toPoint()
 assert before.pixelColor(point).alpha()==0 and image.pixelColor(point).alpha()>0 and ctrl.scene is None
 d.undo_stack.undo();assert frame(c).pixelColor(point).alpha()==0

@pytest.mark.parametrize('zoom',[.1,1,16,50])
def test_native_dash_ink_matches_direct_canvas_at_camera(qapp,drawing,zoom):
 c=drawing;d=c.document;c.zoom=zoom;c.pan_offset=QPointF(0,-10);d.entities=[LineEntity(Point(-100,-10),Point(100,-10),linetype='CENTER',transparency=25)]
 def render(native):
  image=QImage(c.viewport().size(),QImage.Format.Format_ARGB32_Premultiplied);image.fill(0);p=QPainter(image);p.setRenderHints(c.renderHints())
  try:
   if native:draw(c,p,record(d,d.entities)[1]['lines'])
   else:c._draw_entities(p,entities=d.entities)
  finally:p.end()
  return image
 assert render(True)==render(False)


def test_selection_of_new_line_does_not_request_scene(drawing,monkeypatch):
 c=drawing;d=c.document;ctrl=c._scene_controller;scene=ctrl.scene;jobs=ctrl.jobs;e=LineEntity(Point(1,1),Point(10,1));d.undo_stack.push(AddEntityCommand(d,e));frame(c)
 monkeypatch.setattr(ctrl.capture_task,'start',lambda *a:pytest.fail('Scene preparation on selection'))
 c.selected_entities=[e];frame(c)
 assert ctrl.scene is scene and ctrl.jobs==jobs and c._selection_complete


def test_mouse_placement_of_long_dashed_line(qapp,monkeypatch):
 from PyQt6.QtTest import QTest
 from pycad.main_window import MainWindow
 monkeypatch.delenv('PYCAD_LEGACY_DISPLAY',raising=False)
 w=MainWindow();w.show();d=w.document;d.current_linetype='DASHED';c=w.canvas;c.zoom=.05;c.pan_offset=QPointF(3000,0);c.snap_enabled=False;ready(qapp,c);ctrl=c._scene_controller;scene=ctrl.scene;jobs=ctrl.jobs
 monkeypatch.setattr(ctrl.capture_task,'start',lambda *a:pytest.fail('Scene capture on long-line mouse click'))
 w.set_tool('LINE')
 for x in (500,5500,500,5500):
  QTest.mouseClick(c.viewport(),Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,c.world_to_screen(x,0).toPoint());QTest.qWait(150);frame(c)
  assert ctrl.scene is scene and c._last_draw_kind=='persistent vector scene'
 assert len(d.entities)==3 and ctrl.jobs==jobs
 d.mark_saved();w.close();qapp.processEvents()
