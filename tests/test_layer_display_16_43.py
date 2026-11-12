import pytest
from PyQt6.QtCore import Qt,QPointF
from pycad.document import Document,AddEntityCommand,TranslateEntitiesCommand
from pycad.geometry import Point,LineEntity,HatchEntity,TextEntity
from pycad.canvas import CadCanvas
from pycad.persistent_scene import regenerate
from test_persistent_scene_16_40 import ready,frame,wait


def create(qapp):
 d=Document();d.layers.layers['Notes']=dict(d.layers.layers['0']);d.layers.layers['Notes']['color']='#ff6600'
 d.entities=[LineEntity(Point(i,0),Point(i,20),layer='0' if i<500 else 'Notes') for i in range(1000)]
 d.entities.insert(4,HatchEntity([Point(0,0),Point(5,0),Point(5,5),Point(0,5)],pattern='SOLID'))
 c=CadCanvas(d);c.resize(900,600);c.pan_offset=QPointF(20,10);c.zoom=5;c.show();ready(qapp,c);return c

@pytest.fixture
def mixed(qapp,monkeypatch):
 monkeypatch.delenv('PYCAD_LEGACY_DISPLAY',raising=False);c=create(qapp);yield c
 c._scene_controller.close();c.hide();c.deleteLater();qapp.processEvents()


def test_mixed_layers_are_separate_ordered_batches(mixed):
 c=mixed;entries=c._scene_controller.scene['entries'];ids=[k for entry in entries for k in entry['ids']]
 assert ids==[e.id for e in c.document.entities]
 for entry in entries:
  batch=[c.document.find_by_id(k) for k in entry['ids']]
  assert len({e.layer for e in batch})==1 and len(batch)<=256
  assert len({e.kind=='HATCH' for e in batch})==1


def test_line_next_to_hatch_can_move_without_full_scene(mixed):
 c=mixed;ctrl=c._scene_controller;scene=ctrl.scene;jobs=ctrl.jobs;frame(c);image=c._static_scene_frame['image']
 c.document.undo_stack.push(TranslateEntitiesCommand(c.document,[c.document.entities[0]],10,2));changed=frame(c)
 assert ctrl.scene is scene and ctrl.jobs==jobs and c._static_scene_frame['image'] is image and c._dirty_region_updates==1
 # A full presentation of the same model must produce identical pixels.
 c.__dict__.pop('_static_scene_frame');assert frame(c)==changed
 c.document.undo_stack.undo();frame(c)


def test_metadata_does_not_disable_unrelated_new_line(qapp,mixed):
 c=mixed;d=c.document;d.extensions={'production':{'sheet_sets':{}},'productivity':{'survey':{'site':__import__('pycad.productivity',fromlist=['survey_config']).survey_config()}}}
 d.dirty=True;qapp.processEvents();ready(qapp,c);ctrl=c._scene_controller;scene=ctrl.scene;jobs=ctrl.jobs
 d.undo_stack.push(AddEntityCommand(d,LineEntity(Point(0,3),Point(10,3),layer='Notes')));frame(c)
 assert ctrl.scene is scene and ctrl.jobs==jobs and not ctrl.delta.state.blocked
 assert ctrl.delta.added_layers==['Notes']


def test_drafting_overlay_keeps_actual_cad_layer(mixed):
 c=mixed;d=c.document;ctrl=c._scene_controller
 for layer in ('Notes','0','Notes'):
  d.undo_stack.push(AddEntityCommand(d,LineEntity(Point(1,2),Point(3,4),layer=layer)));frame(c)
 assert ctrl.delta.added_layers==['Notes','0','Notes']
 assert len(d.layers.layers)==2


def test_repeated_invalidations_keep_last_complete_scene(mixed):
 c=mixed;ctrl=c._scene_controller;old=ctrl.scene;sig=ctrl.signature
 ctrl.reset((sig[0],sig[1]+1,*sig[2:]));assert ctrl.previous_scene is old
 ctrl.reset((sig[0],sig[1]+2,*sig[2:]));assert ctrl.previous_scene is old
 # Invalidate through the real paint path twice before either compile completes.
 for i in range(2):
  c.document.dirty=True;image=frame(c)
  assert ctrl.previous_scene is old and any(image.pixelColor(x,300).alpha() for x in range(image.width()))


def test_refresh_command_keeps_picture_until_replacement(qapp,monkeypatch):
 monkeypatch.delenv('PYCAD_LEGACY_DISPLAY',raising=False)
 from pycad.main_window import MainWindow
 w=MainWindow();w.show();d=w.document;d.entities=[LineEntity(Point(0,0),Point(10,10))];d.dirty=True;ready(qapp,w.canvas);old=w.canvas._scene_controller.scene
 w.command_line.setText('REFRESH');w._on_command_entered();frame(w.canvas)
 assert w.canvas._scene_controller.previous_scene is old
 wait(qapp,lambda:w.canvas._scene_controller.scene is not None)
 assert w.canvas._scene_controller.scene is not old
 d.mark_saved();w.close();qapp.processEvents()


def test_second_canvas_reuses_document_journal(qapp,mixed):
 c=mixed;state=c._scene_controller.delta.state;other=CadCanvas(c.document);other.resize(500,400);other.show();ready(qapp,other)
 assert other._scene_controller.delta.state is state
 c.document.undo_stack.push(AddEntityCommand(c.document,LineEntity(Point(1,2),Point(3,4))));a=c._scene_controller.scene;b=other._scene_controller.scene
 frame(c);frame(other);assert c._scene_controller.scene is a and other._scene_controller.scene is b
 other._scene_controller.close();other.hide();other.deleteLater();qapp.processEvents()


def test_loaded_mixed_drawing_real_mouse_clicks(qapp,monkeypatch,tmp_path,mixed):
 from PyQt6.QtTest import QTest
 from pycad.main_window import MainWindow
 from pycad.native_io import save_project,load_project
 from pycad.productivity import survey_config
 d=mixed.document;d.extensions={'production':{'sheet_sets':{}},'productivity':{'survey':{'site':survey_config()}}}
 save_project(d,tmp_path/'mixed.pycad');loaded=load_project(tmp_path/'mixed.pycad')
 w=MainWindow();w.show();w.drawing_tabs.add_document(loaded);c=w.canvas;c.zoom=5;c.pan_offset=QPointF(20,10);ready(qapp,c);ctrl=c._scene_controller;scene=ctrl.scene;jobs=ctrl.jobs;count=len(loaded.entities)
 monkeypatch.setattr(ctrl.capture_task,'start',lambda *a:pytest.fail('Whole-file snapshot on mouse drafting'))
 w.command_line.setText('L');w._on_command_entered()
 for x in (10,15,20,25):
  QTest.mouseClick(c.viewport(),Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,c.world_to_screen(x,10).toPoint());QTest.qWait(150);frame(c)
  assert ctrl.scene is scene and c._last_draw_kind=='persistent vector scene'
 assert len(loaded.entities)==count+3 and ctrl.jobs==jobs
 loaded.mark_saved();w.close();qapp.processEvents()


def test_interleaved_layers_keep_packet_count_bounded(qapp):
 from pycad.render_snapshot import capture
 d=Document();d.layers.layers['Other']=dict(d.layers.layers['0']);d.entities=[LineEntity(Point(i,0),Point(i,1),layer='Other' if i%2 else '0') for i in range(1000)];c=CadCanvas(d)
 batches=[item[1][4] for item in capture(c) if item is not None and item[0]=='batch']
 assert len(batches)==4 and [e.id for batch in batches for e in batch]==[e.id for e in d.entities]
 c.deleteLater();qapp.processEvents()
