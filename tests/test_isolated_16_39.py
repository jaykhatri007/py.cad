import os
import pytest
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QImage,QColor
from pycad.document import Document
from pycad.canvas import CadCanvas
from pycad.geometry import Point,PolylineEntity,HatchEntity,TextEntity
from pycad.progressive_display import heavy
from pycad.render_snapshot import freeze_iter
from test_background_16_38 import prepared,wait,dispose,background_frame

@pytest.mark.parametrize('kind',['polyline','hatch','text'])
def test_complexity_not_only_entity_count(qapp,kind):
 d=Document()
 if kind=='polyline':e=PolylineEntity([Point(i,i%7) for i in range(10000)])
 elif kind=='hatch':
  import math
  e=HatchEntity([Point(0,0),Point(1,0),Point(1,1),Point(0,1)],pattern='SOLID');e.boundary=[Point(100*math.cos(i*6.283/6000),100*math.sin(i*6.283/6000)) for i in range(6000)]
 else:e=TextEntity(Point(0,0),'x',rich_html='<b>'+'X'*12000+'</b>')
 d.entities=[e];c=CadCanvas(d);assert len(d.entities)==1 and heavy(c);dispose(c,qapp)

def test_large_point_capture_yields_and_is_independent(qapp):
 e=PolylineEntity([Point(i,i%9) for i in range(20000)]);it=freeze_iter([e]);count=0
 while True:
  try:next(it);count+=1
  except StopIteration as result:clone=result.value[0];break
 assert count>100 and clone.id==e.id;clone.points[100].x=-1;assert e.points[100].x==100

def test_nearby_zoom_does_not_request_render_or_recompile(qapp):
 c=prepared(qapp);controller=c._async_controller;jobs=controller.jobs;revision=c.document.render_revision
 for factor in (1.15,1/1.15,1.1,1/1.1)*4:
  c.zoom*=factor;background_frame(c);assert c._last_draw_kind=='background cached frame'
 assert controller.jobs==jobs and c._async_worker_stats['model_compiles']==1 and c.document.render_revision==revision;dispose(c,qapp)

def test_uncached_zoom_keeps_model_in_same_process(qapp):
 c=prepared(qapp);pid=c._async_worker_stats['renderer_pid'];c.zoom*=2;c.viewport().update();wait(qapp,lambda:c.__dict__.get('_drawing_image_key',(0,0,0,0))[3]==c.zoom,30)
 assert c._async_worker_stats['renderer_pid']==pid!=os.getpid() and c._async_worker_stats['model_compiles']==1;dispose(c,qapp)

def test_selected_complex_polyline_never_paints_geometry_or_grips_on_ui(qapp,monkeypatch):
 d=Document();e=PolylineEntity([Point(i,i%9) for i in range(12000)]);d.entities=[e];c=CadCanvas(d);c.resize(900,650);c.zoom=.06;c.pan_offset=QPointF(6000,4);c.selected_entities=[e]
 monkeypatch.setattr(c,'_draw_entities',lambda *a,**k:pytest.fail('Geometry painted on UI'))
 monkeypatch.setattr(c,'_draw_grips',lambda *a,**k:pytest.fail('Grips painted on UI'))
 c.show();wait(qapp,lambda:c.__dict__.get('_last_draw_kind')=='background cached frame' and c.__dict__.get('_selection_complete',False),45)
 c.zoom*=1.15;c.viewport().update();qapp.processEvents();assert c._last_draw_kind=='background cached frame';dispose(c,qapp)

def test_underlay_uses_process_instead_of_sync_fallback(qapp):
 import base64,hashlib
 from PyQt6.QtCore import QByteArray,QBuffer,QIODevice
 c=prepared(qapp);im=QImage(8,8,QImage.Format.Format_ARGB32);im.fill(QColor('#ff0000'));buf=QByteArray();out=QBuffer(buf);out.open(QIODevice.OpenModeFlag.WriteOnly);im.save(out,'PNG');raw=bytes(buf)
 c.document.underlays=[dict(id='u',name='test',kind='image',page=0,png=base64.b64encode(raw).decode(),sha256=hashlib.sha256(raw).hexdigest(),pixels=[8,8],origin=[580,10],width=30,rotation=0,opacity=.5,visible=True,plot=True,locked=False)]
 c.document.dirty=True;c.viewport().update();wait(qapp,lambda:c.__dict__.get('_drawing_image_key',(0,0))[1]==c.document.render_revision,30)
 assert c._async_worker_stats['renderer_pid']!=os.getpid() and not getattr(c,'_render_process_error',None);dispose(c,qapp)

def test_layout_heavy_view_is_isolated(qapp):
 from pycad.layout import Layout,Viewport
 c=prepared(qapp);layout=Layout('Sheet');layout.viewports=[Viewport(10,10,250,180,Point(600,20),.2)];c.document.layouts['Sheet']=layout;c.document.current_space='Sheet';c.document.dirty=True;c.zoom=2;c.pan_offset=QPointF(150,105);c.viewport().update()
 wait(qapp,lambda:c.__dict__.get('_drawing_image_key',(0,0))[1]==c.document.render_revision,30)
 assert c._async_worker_stats['renderer_pid']!=os.getpid() and not getattr(c,'_render_process_error',None);dispose(c,qapp)

def test_failed_renderer_never_silently_runs_ui_geometry(qapp,monkeypatch):
 c=prepared(qapp);controller=c._async_controller;controller._fail('deliberate test');c.zoom*=2
 monkeypatch.setattr(c,'_draw_entities',lambda *a,**k:pytest.fail('Synchronous fallback'))
 background_frame(c);assert controller.error and c._last_draw_kind=='background refining frame';dispose(c,qapp)

def test_model_change_while_process_busy_does_not_leave_active_job_stuck(qapp):
 c=prepared(qapp);controller=c._async_controller;c.zoom*=3;c.viewport().update();wait(qapp,lambda:controller.active is not None)
 c.document.entities[0].p1.x=-100;c.document.dirty=True;c.document.spatial_index.invalidate();c.viewport().update();wait(qapp,lambda:c.__dict__.get('_drawing_image_key',(0,0))[1]==c.document.render_revision,30)
 assert not controller.error;dispose(c,qapp)

def test_boq_overlay_does_not_force_ui_rasterization(qapp,monkeypatch):
 c=prepared(qapp);c.boq_overlay_enabled=True;c.viewport().update()
 monkeypatch.setattr(c,'_draw_entities',lambda *a,**k:pytest.fail('BOQ geometry painted on UI'))
 wait(qapp,lambda:c.__dict__.get('_drawing_image_key',(None,))[-1] is True,30)
 assert c._async_worker_stats['renderer_pid']!=os.getpid() and not getattr(c,'_render_process_error',None);dispose(c,qapp)
