import os,time
import pytest
from PyQt6.QtCore import QPointF,Qt
from PyQt6.QtGui import QImage,QPainter
from pycad.document import Document
from pycad.geometry import Point,LineEntity,TextEntity,PolylineEntity,HatchEntity,BlockReferenceEntity
from pycad.canvas import CadCanvas
from pycad.persistent_scene import regenerate


def wait(app,test,seconds=60):
 end=time.monotonic()+seconds
 while time.monotonic()<end:
  app.processEvents()
  if test():return
  time.sleep(.001)
 raise AssertionError('Persistent scene did not become ready')


def ready(app,c):
 c.viewport().update()
 wait(app,lambda:bool(c.__dict__.get('_render_process_error')) or c.__dict__.get('_last_draw_kind')=='persistent vector scene')
 assert not c.__dict__.get('_render_process_error')
 return c._scene_controller


def frame(c):
 im=QImage(c.viewport().size(),QImage.Format.Format_ARGB32_Premultiplied);im.fill(0);p=QPainter(im)
 try:c._draw_cached_entities(p)
 finally:p.end()
 return im


@pytest.fixture
def drawing(qapp,monkeypatch):
 monkeypatch.delenv('PYCAD_LEGACY_DISPLAY',raising=False)
 d=Document();d.entities=[LineEntity(Point(i,0),Point(i,40)) for i in range(7000)]+[TextEntity(Point(40,10),'Styled notes')]
 c=CadCanvas(d);c.resize(1000,700);c.zoom=2;c.pan_offset=QPointF(100,20);c.show();ready(qapp,c)
 yield c
 c._scene_controller.close();c.hide();c.deleteLater();qapp.processEvents()


def test_arbitrary_zoom_pan_and_resize_never_rebuild_or_request_pixels(qapp,drawing,monkeypatch):
 c=drawing;controller=c._scene_controller;scene=controller.scene;jobs=controller.jobs;pid=c._persistent_worker_stats['renderer_pid']
 monkeypatch.setattr(c,'_draw_entities',lambda *a,**k:pytest.fail('CAD traversal on navigation'))
 for z,x,y in [(1e-3,-10000,-900),(300,6000,20),(.03,3500,400),(2,100,20)]:
  c.zoom=z;c.pan_offset=QPointF(x,y);frame(c);qapp.processEvents()
 c.resize(1200,800);frame(c);qapp.processEvents()
 assert controller.scene is scene and controller.jobs==jobs==1 and c._persistent_worker_stats['renderer_pid']==pid
 assert c._persistent_worker_stats['model_compiles']==1 and c._last_draw_kind=='persistent vector scene'


def test_far_pan_displays_previously_unseen_geometry_without_worker(qapp,drawing):
 c=drawing;jobs=c._scene_controller.jobs;c.pan_offset=QPointF(6000,20);im=frame(c)
 assert any(im.pixelColor(x,im.height()//2).alpha() for x in range(im.width()))
 assert c._scene_controller.jobs==jobs and c.persistent_scene_stats['visible_batches']>0


def test_selected_scene_and_grips_survive_all_camera_changes(qapp,drawing,monkeypatch):
 c=drawing;c.selected_entities=[c.document.entities[-1]];c.viewport().update()
 wait(qapp,lambda:c.__dict__.get('_selection_complete',False));controller=c._scene_controller;jobs=controller.jobs;scene=controller.selection_scene
 monkeypatch.setattr(c,'_draw_grips',lambda *a:pytest.fail('Grip geometry regenerated'))
 for zoom in (.005,50,.2,4):c.zoom=zoom;c.pan_offset=QPointF(40,10);frame(c);qapp.processEvents()
 assert controller.selection_scene is scene and controller.jobs==jobs and c._selection_complete


def test_edit_and_explicit_regen_invalidate_scene(qapp,drawing):
 c=drawing;old=c._scene_controller.scene;c.document.entities[0].p1.x=-200;c.document.dirty=True;c.viewport().update();qapp.processEvents();ready(qapp,c)
 assert c._scene_controller.scene is not old
 old=c._scene_controller.scene;regenerate(c);qapp.processEvents();ready(qapp,c)
 assert c._scene_controller.scene is not old


@pytest.mark.parametrize('kind',['block','polyline','hatch','underlay','layout'])
def test_complex_content_is_persistent_across_navigation(qapp,monkeypatch,kind):
 monkeypatch.delenv('PYCAD_LEGACY_DISPLAY',raising=False)
 d=Document()
 if kind=='block':
  root=BlockReferenceEntity('Notes',Point(0,0));root.resolved_entities=[TextEntity(Point(10,10),'Block notes',wrap_width=20,rich_html='<b>Rich text</b>')];d.entities=[root]
 elif kind=='polyline':d.entities=[PolylineEntity([Point(i,i%9) for i in range(12000)],bulges=[.2]*11999+[0])]
 elif kind=='hatch':d.entities=[HatchEntity([Point(0,0),Point(40,0),Point(40,40),Point(0,40)],pattern='ANSI31',spacing=2)]
 elif kind=='underlay':
  import base64
  from PyQt6.QtCore import QByteArray,QBuffer,QIODevice
  im=QImage(16,16,QImage.Format.Format_ARGB32);im.fill(Qt.GlobalColor.red);raw=QByteArray();buf=QBuffer(raw);buf.open(QIODevice.OpenModeFlag.WriteOnly);im.save(buf,'PNG')
  d.underlays=[dict(id='test',name='image',kind='image',png=base64.b64encode(bytes(raw)).decode(),pixels=[16,16],origin=[0,0],width=40,rotation=0,opacity=1,visible=True)]
 else:
  from pycad.layout import Layout,Viewport
  d.entities=[LineEntity(Point(0,0),Point(20,20))];layout=Layout('Sheet');layout.viewports=[Viewport(10,10,100,100,Point(10,10),1)];d.layouts['Sheet']=layout;d.current_space='Sheet'
 c=CadCanvas(d);c.resize(900,600);c.zoom=.03 if kind=='polyline' else 3;c.pan_offset=QPointF(100,20);c.show()
 try:
  if kind=='layout':c._draw_cached_entities=lambda p:CadCanvas._draw_cached_entities(c,p)
  ready(qapp,c);controller=c._scene_controller;scene=controller.scene;jobs=controller.jobs
  for z in (.01,30,.5):c.zoom=z;c.pan_offset=QPointF(20,20);frame(c);qapp.processEvents()
  assert scene is controller.scene and jobs==controller.jobs
 finally:
  if '_scene_controller' in c.__dict__:c._scene_controller.close()
  c.hide();c.deleteLater();qapp.processEvents()


def test_dash_lengths_stay_in_world_units_without_regen(qapp,monkeypatch):
 monkeypatch.delenv('PYCAD_LEGACY_DISPLAY',raising=False)
 d=Document();d.entities=[LineEntity(Point(0,0),Point(30,0),linetype='DASHED')];c=CadCanvas(d);c.resize(800,500);c.zoom=10;c.pan_offset=QPointF(15,0);c.show()
 try:
  ready(qapp,c);jobs=c._scene_controller.jobs
  for z in (10,20,5):
   c.zoom=z;im=frame(c);y=im.height()//2
   def alpha(x):return im.pixelColor(round(im.width()/2+(x-15)*z),y).alpha()
   assert alpha(3)>0 and alpha(8)==0 and alpha(13)>0
  assert c._scene_controller.jobs==jobs
 finally:c._scene_controller.close();c.hide();c.deleteLater();qapp.processEvents()


def test_close_during_capture_and_close_ready_worker(qapp,monkeypatch):
 from pycad.async_display import shutdown
 monkeypatch.delenv('PYCAD_LEGACY_DISPLAY',raising=False)
 d=Document();d.entities=[PolylineEntity([Point(i,i%7) for i in range(20000)])]
 c=CadCanvas(d);c.show();qapp.processEvents();shutdown()
 assert c._scene_controller.closed;c.hide();c.deleteLater();qapp.processEvents()


def test_subpixel_toggle_uses_existing_scene(drawing,qapp):
 c=drawing;scene=c._scene_controller.scene;jobs=c._scene_controller.jobs
 for value in (False,True,False):c.progressive_lod=value;frame(c);qapp.processEvents()
 assert c._scene_controller.scene is scene and c._scene_controller.jobs==jobs


def test_regen_command_reaches_scene_and_performance_controls(main_window,qapp,monkeypatch):
 monkeypatch.delenv('PYCAD_LEGACY_DISPLAY',raising=False)
 w=main_window;ready(qapp,w.canvas);old=w.canvas._scene_controller.scene
 w.command_line.setText('REGEN');w._on_command_entered();qapp.processEvents();ready(qapp,w.canvas)
 assert w.canvas._scene_controller.scene is not old
 from pycad.workflow_ui import WorkflowDialog
 dialog=WorkflowDialog(w)
 assert any('Regenerate drawing display' in b.text() for b in dialog.findChildren(__import__('PyQt6.QtWidgets',fromlist=['QPushButton']).QPushButton))
 dialog.close()


def test_actual_wheel_and_middle_pan_events_do_not_rebuild(drawing,qapp):
 from PyQt6.QtCore import QPoint
 from PyQt6.QtGui import QWheelEvent
 from PyQt6.QtTest import QTest
 c=drawing;scene=c._scene_controller.scene;jobs=c._scene_controller.jobs
 for delta in [120]*8+[-120]*8:
  c.wheelEvent(QWheelEvent(QPointF(430,320),QPointF(430,320),QPoint(),QPoint(0,delta),Qt.MouseButton.NoButton,Qt.KeyboardModifier.NoModifier,Qt.ScrollPhase.NoScrollPhase,False));qapp.processEvents()
 c._finish_navigation_preview();qapp.processEvents()
 QTest.mousePress(c.viewport(),Qt.MouseButton.MiddleButton,pos=QPoint(300,300));QTest.mouseMove(c.viewport(),QPoint(750,400));QTest.mouseRelease(c.viewport(),Qt.MouseButton.MiddleButton,pos=QPoint(750,400));qapp.processEvents()
 assert c._scene_controller.scene is scene and c._scene_controller.jobs==jobs
 assert c._last_draw_kind=='persistent vector scene'


def test_old_saved_direct_setting_does_not_bypass_new_scene(qapp,monkeypatch):
 monkeypatch.delenv('PYCAD_LEGACY_DISPLAY',raising=False)
 d=Document();d.entities=[LineEntity(Point(0,0),Point(20,20))];c=CadCanvas(d);c.drawing_path='direct';c.show()
 try:
  ready(qapp,c);jobs=c._scene_controller.jobs;c.zoom*=10;frame(c)
  assert c._last_draw_kind=='persistent vector scene' and c._scene_controller.jobs==jobs
 finally:c._scene_controller.close();c.hide();c.deleteLater();qapp.processEvents()
