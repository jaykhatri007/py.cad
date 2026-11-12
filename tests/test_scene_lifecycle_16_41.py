import pytest,weakref
from PyQt6.QtCore import QProcess
from PyQt6.QtGui import QImage,QPainter
from PyQt6.QtWidgets import QWidget
from PyQt6 import sip
from pycad.document import Document
from pycad.geometry import Point,LineEntity
from pycad.canvas import CadCanvas
from pycad.persistent_scene import SceneController,paint
from test_persistent_scene_16_40 import ready,frame


def key(c):
 from pycad.appearance import colors
 return (id(c.document),c.document.render_revision,len(c.document.entities),c.zoom,c.pan_offset.x(),c.pan_offset.y(),c.viewport().width(),c.viewport().height(),repr(c.document.layers.layers)+repr(c.document.current_space),repr(colors(c)),True,False)


def test_reentrant_paint_does_not_reenter_capture_generator(qapp,monkeypatch):
 from pycad import render_snapshot
 d=Document();d.entities=[LineEntity(Point(0,0),Point(10,10))];c=CadCanvas(d);c.resize(800,600)
 original=render_snapshot.capture;calls=[]
 def render(canvas):
  image=QImage(800,600,QImage.Format.Format_ARGB32_Premultiplied);p=QPainter(image)
  try:paint(canvas,p,key(canvas))
  finally:p.end()
 def capture(canvas):
  calls.append('start');render(canvas);yield from original(canvas)
 monkeypatch.setattr(render_snapshot,'capture',capture)
 try:
  render(c)
  qapp.processEvents()
  assert calls==['start']
 finally:
  if '_scene_controller' in c.__dict__:c._scene_controller.close()
  c.deleteLater();qapp.processEvents()


def test_queued_process_signals_disconnect_when_controller_is_deleted(qapp,monkeypatch):
 c=CadCanvas(Document());controller=SceneController(c);process=QProcess();seen=[]
 monkeypatch.setattr(controller,'_exit',lambda *args:seen.append('late callback'))
 # Use the production connection path with a process outside the controller's
 # ownership so delayed signals can actually outlive the receiver.
 if hasattr(controller,'_connect_process'):controller._connect_process(process)
 else:process.finished.connect(lambda code,status:controller._exit(process,code))
 monkeypatch.setattr(__import__('sys'),'excepthook',lambda *args:seen.append(args))
 controller.close();sip.delete(controller);process.finished.emit(0,QProcess.ExitStatus.NormalExit);qapp.processEvents()
 assert not seen
 process.deleteLater();c.deleteLater();qapp.processEvents()


def test_deleted_canvas_during_capture_does_not_escape_paint(qapp,monkeypatch):
 from pycad import render_snapshot
 c=CadCanvas(Document());image=QImage(800,600,QImage.Format.Format_ARGB32_Premultiplied);p=QPainter(image);k=key(c)
 def capture(canvas):
  sip.delete(canvas);yield None
 monkeypatch.setattr(render_snapshot,'capture',capture)
 try:
  assert paint(c,p,k);qapp.processEvents()
 finally:p.end();qapp.processEvents()


def test_replaced_capture_cannot_lose_its_timer_wakeup(qapp):
 from PyQt6.QtCore import QObject
 from pycad.scene_capture import CaptureTask
 owner=QObject();task=CaptureTask(owner);replacement=dict(iterator=iter(()),ready=False,items=[])
 def original():
  task.start(replacement);task.timer.stop();task.step() # replacement tick consumed during an active step
  yield None
 state=dict(iterator=original(),ready=False,items=[]);task.start(state);task.timer.stop();task.step();qapp.processEvents()
 try:assert replacement['ready']
 finally:task.cancel();owner.deleteLater();qapp.processEvents()
