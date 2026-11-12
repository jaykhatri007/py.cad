import time,copy,threading
import pytest
from PyQt6.QtCore import Qt,QPointF
from PyQt6.QtGui import QImage,QPainter
from pycad.geometry import Point,LineEntity,PolylineEntity,CircleEntity,HatchEntity,TextEntity,DimensionEntity,BlockReferenceEntity
from pycad.document import Document
from pycad.canvas import CadCanvas
from pycad.async_display import SnapshotDocument,freeze_entities,Job,Controller,shutdown
from test_navigation_16_36 import frame,drawing

def background_frame(c):
 im=QImage(c.viewport().size(),QImage.Format.Format_ARGB32_Premultiplied);im.fill(Qt.GlobalColor.transparent);p=QPainter(im)
 p.setRenderHints(QPainter.RenderHint(c._retained_scene['signature'][-1]))
 try:c._draw_cached_entities(p)
 finally:p.end()
 return im



def wait(qapp,predicate,seconds=15):
 end=time.monotonic()+seconds
 while time.monotonic()<end:
  qapp.processEvents()
  if predicate():return
  time.sleep(.001)
 raise AssertionError('Background work did not finish')


def prepared(qapp,n=7000):
 c=CadCanvas(drawing(n));c.resize(1000,700);c.zoom=.7;c.pan_offset=QPointF(600,25);c.show()
 wait(qapp,lambda:c.__dict__.get('_last_draw_kind')=='background cached frame',30)
 return c


def dispose(c,qapp):
 if '_async_controller' in c.__dict__:c._async_controller.close()
 c.hide();c.deleteLater();qapp.processEvents()


@pytest.mark.parametrize('style',['CONTINUOUS','DASHED','CENTER','DOT','PHANTOM'])
@pytest.mark.parametrize('aa',[False,True])
def test_ordered_dash_batches_equal_individual_strokes(qapp,monkeypatch,style,aa):
 d=Document();d.entities=[LineEntity(Point(-30+i,-15),Point(-20+i,30),linetype=style,color='#ef3050') for i in range(8)]+[CircleEntity(Point(0,0),10,color='#00ff00')]+[LineEntity(Point(-20,0),Point(30,0),linetype=style,color='#30a0ff')]
 c=CadCanvas(d);c.zoom=6;image=frame(c,False,aa)
 from pycad.fast_lines import Lines
 monkeypatch.setattr(Lines,'offer',lambda *a:False);assert image==frame(c,False,aa);dispose(c,qapp)


def samples():
 return [LineEntity(Point(-20,0),Point(20,0),linetype='DASHED'),CircleEntity(Point(0,0),8),PolylineEntity([Point(-5,-5),Point(15,-5)],bulges=[.4,0]),HatchEntity([Point(-15,-15),Point(15,-15),Point(15,15),Point(-15,15)],pattern='ANSI31',spacing=2),TextEntity(Point(-10,10),'Text',height=2,wrap_width=12,rich_html='<b>Test</b>'),DimensionEntity(Point(-20,0),Point(20,0),Point(0,25))]


def test_private_worker_snapshot_matches_full_renderer(qapp):
 d=Document();d.entities=samples();c=CadCanvas(d);c.zoom=5;expected=frame(c,False);pose=(c.zoom,0,0,c.viewport().width(),c.viewport().height())
 items=[]
 for e in d.entities:items.append((e.bbox(),None,None,[e],freeze_entities([e])))
 job=Job(items,SnapshotDocument(d),pose,QPainter.RenderHint(0),{'ui_selection':'#00aaff'},('test',));result=[];job.signals.finished.connect(lambda job,im,error:result.append((im,error)));job.run()
 assert result[0][1] is None and result[0][0]==expected;dispose(c,qapp)


def test_snapshot_keeps_geometry_independent(qapp):
 d=Document();root=BlockReferenceEntity('R',Point(0,0));root.resolved_entities=[LineEntity(Point(1,2),Point(3,4))];root._display_index=object();clones=freeze_entities([root]);root.resolved_entities[0].p1.x=100
 assert clones[0].resolved_entities[0].p1.x==1 and '_display_index' not in clones[0].__dict__ and clones[0].id==root.id


def test_nearby_pan_reuses_overscan_without_another_worker(qapp):
 c=prepared(qapp);controller=c._async_controller;jobs=controller.jobs;c.pan_offset=QPointF(c.pan_offset.x()+25/c.zoom,c.pan_offset.y());background_frame(c)
 assert c._last_draw_kind=='background cached frame' and controller.jobs==jobs and controller.bytes<=controller.BUDGET
 dispose(c,qapp)


def test_return_zoom_reuses_cached_view_and_geometry_is_not_mutated(qapp):
 c=prepared(qapp);controller=c._async_controller;old=c.zoom;before=[(e.id,e.p1.as_tuple(),e.p2.as_tuple()) for e in c.document.entities]
 c.zoom*=1.4;c.viewport().update();wait(qapp,lambda:c.__dict__.get('_drawing_image_key',(0,0,0,0))[3]==c.zoom);jobs=controller.jobs
 c.zoom=old;background_frame(c);assert c._last_draw_kind=='background cached frame' and controller.jobs==jobs
 assert [(e.id,e.p1.as_tuple(),e.p2.as_tuple()) for e in c.document.entities]==before;dispose(c,qapp)


def test_edit_invalidates_frame_and_dynamic_snapshot(qapp):
 c=prepared(qapp);controller=c._async_controller;old=controller.signature;c.document.entities[0].p1.x=-100;c.document.dirty=True;c.document.spatial_index.invalidate();c.viewport().update()
 wait(qapp,lambda:controller.signature!=old and c.__dict__.get('_drawing_image_key',(0,0))[1]==c.document.render_revision)
 assert controller.signature!=old;dispose(c,qapp)


def test_worker_runs_off_gui_thread_and_close_cancels(qapp,monkeypatch):
 import os
 c=prepared(qapp);assert c._async_worker_stats['renderer_pid']!=os.getpid()
 c.zoom*=2;c.viewport().update();qapp.processEvents();dispose(c,qapp)


def test_superseded_document_cannot_install_stale_result(qapp):
 c=prepared(qapp);old=c._async_controller;job=Job((),SnapshotDocument(c.document),(1,0,0,10,10),QPainter.RenderHint(0),{},('stale',));job.cancelled.set();old.active=job;old.signature=('current',);old.accept(job,QImage(10,10,QImage.Format.Format_ARGB32),None)
 assert old.active is None and not any(pose[3:]==(10,10) for pose in old.cache);dispose(c,qapp)


def test_visible_cold_display_defers_picking_index(qapp,monkeypatch):
 d=drawing(10000);c=CadCanvas(d);c.resize(900,650);c.zoom=.6;c.pan_offset=QPointF(600,30)
 def fail(*a):raise AssertionError('Synchronous picking-index construction on display')
 monkeypatch.setattr(d,'rebuild_spatial_index',fail);c.show();wait(qapp,lambda:c.__dict__.get('_last_draw_kind')=='background cached frame',30)
 assert d.spatial_index._dirty;dispose(c,qapp)


def test_unsaved_ui_marker_does_not_serialize_dirty_undo_stack(qapp,monkeypatch):
 from pycad.document import AddEntityCommand
 from pycad.document_tabs import modified_for_ui
 d=Document();d.undo_stack.push(AddEntityCommand(d,LineEntity(Point(0,0),Point(2,0))))
 import pycad.native_io as n
 def fail(*a):raise AssertionError('Serialized entire drawing for UI star')
 monkeypatch.setattr(n,'document_to_dict',fail);assert modified_for_ui(d)


@pytest.mark.parametrize('zoom',[.2,.5,2.,10.])
def test_dense_hatch_snapshot_preserves_pattern_and_islands(qapp,zoom):
 d=Document();e=HatchEntity([Point(-10,-10),Point(10,-10),Point(10,10),Point(-10,10)],holes=[[Point(-3,-3),Point(3,-3),Point(3,3),Point(-3,3)]],pattern='ANSI31',spacing=.2,background_color='#132435');d.entities=[e];c=CadCanvas(d);c.zoom=zoom;expected=frame(c,False)
 items=[(e.bbox(),None,None,[e],freeze_entities([e]))];job=Job(items,SnapshotDocument(d),(zoom,0,0,c.viewport().width(),c.viewport().height()),QPainter.RenderHint(0),{'ui_selection':'#00aaff'},('test',));out=[];job.signals.finished.connect(lambda j,im,err:out.append((im,err)));job.run()
 assert out[0][1] is None and out[0][0]==expected;dispose(c,qapp)


def test_interleaved_styles_do_not_create_a_picture_per_tiny_run(qapp):
 from pycad.retained_scene import chunks
 d=drawing(10000)
 for i,e in enumerate(d.entities):e.linetype='DASHED' if i%2 else 'CONTINUOUS'
 c=CadCanvas(d);batches=list(chunks(c));assert len(batches)==40 and sum(map(len,batches))==10000;dispose(c,qapp)



def test_adaptive_points_are_optional_and_preserve_native_objects(qapp):
 from pycad.async_display import SnapshotCanvas
 d=Document();d.entities=[LineEntity(Point(i,0),Point(i+.5,.3),linetype='DASHED') for i in range(256)]
 private=freeze_entities(d.entities);doc=SnapshotDocument(d);pose=(1,0,0,500,400);image=QImage(500,400,QImage.Format.Format_ARGB32_Premultiplied);image.fill(Qt.GlobalColor.transparent);p=QPainter(image)
 try:
  proxy=SnapshotCanvas(doc,pose,{'ui_selection':'#00aaff'},True);proxy._draw_entities(p,entities=private);assert proxy.point_count==256
  precise=SnapshotCanvas(doc,pose,{'ui_selection':'#00aaff'},False);precise._draw_entities(p,entities=private);assert precise.point_count==0
 finally:p.end()
 assert all(e.p2.x==i+.5 and e.linetype=='DASHED' for i,e in enumerate(d.entities))
 assert all(e.id==private[i].id for i,e in enumerate(d.entities))
