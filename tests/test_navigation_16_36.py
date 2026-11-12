import pytest
from PyQt6.QtCore import Qt,QPointF,QPoint
from PyQt6.QtGui import QImage,QPainter,QWheelEvent
from pycad.canvas import CadCanvas
from pycad.document import Document
from pycad.geometry import Point,LineEntity,BlockReferenceEntity,PolylineEntity,CircleEntity

def frame(c,cached=True,antialias=False):
 image=QImage(c.viewport().size(),QImage.Format.Format_ARGB32_Premultiplied);image.fill(Qt.GlobalColor.transparent);p=QPainter(image)
 p.setRenderHint(QPainter.RenderHint.Antialiasing,antialias)
 try:c._draw_cached_entities(p) if cached else c._draw_entities(p)
 finally:p.end()
 return image

def wheel(c,delta=120):
 p=QPointF(250,180);e=QWheelEvent(p,p,QPoint(),QPoint(0,delta),Qt.MouseButton.NoButton,Qt.KeyboardModifier.NoModifier,Qt.ScrollPhase.NoScrollPhase,False);c.wheelEvent(e)

def drawing(n):
 d=Document();d.entities=[LineEntity(Point(i%400*3,i//400*3),Point(i%400*3+2,i//400*3+1)) for i in range(n)];return d

def complete(c):
 for i in range(3000):
  image=frame(c)
  if c.progressive_stats['complete'] and (not c.selected_entities or c.__dict__.get('_selection_complete',False)):return image
 raise AssertionError('Refinement never completed')

@pytest.mark.parametrize('n',[10000,80000])
def test_wheel_burst_reuses_frame_then_refines_all_visible_objects(qapp,n):
 d=drawing(n);c=CadCanvas(d);c.resize(1000,700);c.zoom=.65;c.pan_offset=QPointF(600,n/400*1.5);complete(c);calls=[];original=c._draw_entities;c._draw_entities=lambda *a,**k:(calls.append(1),original(*a,**k))[1]
 geometry=[(e.id,e.p1.as_tuple(),e.p2.as_tuple()) for e in d.entities]
 before=c.screen_to_world(250,180)
 for i in range(16):wheel(c,120 if i<8 else -120);frame(c);assert c._last_draw_kind=='navigation preview'
 after=c.screen_to_world(250,180);assert after.x()==pytest.approx(before.x()) and after.y()==pytest.approx(before.y()) and not calls
 c._finish_navigation_preview();complete(c);assert c.progressive_stats['painted']==c.progressive_stats['candidates'] and len(d.entities)==n
 assert [(e.id,e.p1.as_tuple(),e.p2.as_tuple()) for e in d.entities]==geometry
 c.deleteLater()

def test_zero_delta_and_trackpad_fractional_zoom(qapp):
 c=CadCanvas(Document());c.resize(500,400);old=c.zoom;wheel(c,0);assert c.zoom==old
 wheel(c,30);assert c.zoom==pytest.approx(old*1.15**.25);c._finish_navigation_preview();c.deleteLater()

@pytest.mark.parametrize('antialias',[False,True])
def test_batches_preserve_painter_order_colors_and_export_fallback(qapp,antialias):
 d=Document();d.entities=[LineEntity(Point(0,0),Point(20,20),color='#ff0000'),LineEntity(Point(20,0),Point(0,20),color='#ff0000'),CircleEntity(Point(10,10),5,color='#0000ff'),LineEntity(Point(0,20),Point(20,0),color='#00ff00'),LineEntity(Point(0,10),Point(20,10),transparency=50)];c=CadCanvas(d);c.resize(500,400);c.pan_offset=QPointF(10,10)
 batch=frame(c,False,antialias)
 from pycad.fast_lines import Lines
 original=Lines.offer;Lines.offer=lambda *args:False
 try:reference=frame(c,False,antialias)
 finally:Lines.offer=original
 assert batch==reference;c.deleteLater()

def test_nested_block_refinement_matches_full_render_with_clips_and_selection(qapp):
 d=drawing(1200);leaves=d.entities;inner=BlockReferenceEntity('Inner',Point(0,0),clip_boundary=[Point(-1,-1),Point(900,-1),Point(900,30),Point(-1,30)],transparency=20);inner.resolved_entities=leaves;root=BlockReferenceEntity('Outer',Point(0,0));root.resolved_entities=[inner];d.entities=[root];c=CadCanvas(d);c.resize(1000,700);c.zoom=.7;c.pan_offset=QPointF(550,10);c.drawing_path='progressive';c.progressive_lod=False
 reference=frame(c,False);result=complete(c);assert result==reference and c.progressive_stats['draw_tasks']>1
 c.selected_entities=[root];complete(c);wheel(c);frame(c);assert c._last_draw_kind=='navigation preview';c._finish_navigation_preview();c.deleteLater()

def test_revision_change_invalidates_navigation_and_finishes_new_content(qapp):
 d=drawing(6000);c=CadCanvas(d);c.resize(600,500);c.zoom=.5;c.pan_offset=QPointF(300,30);complete(c);wheel(c);d.entities[0].p1.x=-100;d.dirty=True;d.spatial_index.invalidate();frame(c);assert c._last_draw_kind=='progressive frame'
 wheel(c);frame(c);assert c._last_draw_kind=='navigation preview';c._finish_navigation_preview();complete(c);assert c._drawing_image_key[1]==d.render_revision;c.deleteLater()
