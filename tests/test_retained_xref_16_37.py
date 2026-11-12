import pytest
from PyQt6.QtCore import QPointF,Qt
from PyQt6.QtGui import QImage,QPainter
from pycad.document import Document
from pycad.canvas import CadCanvas
from pycad.geometry import Point,LineEntity,CircleEntity,PolylineEntity,BlockDefinition,BlockReferenceEntity
from pycad import retained_scene as r
from pycad.xref_manager import bind,source_missing,unload
from pycad.native_io import document_to_dict,document_from_dict,entity_to_dict
from test_navigation_16_36 import frame,wheel,drawing

def retained(c):
 for _ in range(6000):
  image=frame(c)
  if c.__dict__.get('_retained_scene',{}).get('ready') and c.progressive_stats['complete']:return image
 raise AssertionError('Retained scene did not finish')

def test_zoom_keeps_complete_view_during_idle_refinement(qapp,monkeypatch):
 c=CadCanvas(drawing(10000));c.zoom=.8;c.pan_offset=QPointF(600,35);retained(c)
 old=c._drawing_image.copy();wheel(c);c._finish_navigation_preview()
 import time
 original=r.draw
 def slow(*args):time.sleep(.009);return original(*args)
 monkeypatch.setattr(r,'draw',slow)
 image=frame(c);assert not c.progressive_stats['complete']
 expected=QImage(image.size(),image.format());expected.fill(Qt.GlobalColor.transparent);p=QPainter(expected)
 try:assert r.raster_fallback(c,p,c._last_retained_key)
 finally:p.end()
 assert image==expected and c._drawing_image==old;c.deleteLater()

def test_camera_replay_avoids_geometry_rebuild(qapp,monkeypatch):
 c=CadCanvas(drawing(12000));c.zoom=.6;c.pan_offset=QPointF(600,45);retained(c);sig=c._retained_scene
 def fail(*a,**kw):raise AssertionError('Geometry rebuilt on camera change')
 monkeypatch.setattr(c,'_draw_entities',fail)
 wheel(c);frame(c);assert c._last_draw_kind=='navigation preview'
 c._finish_navigation_preview();retained(c);assert c._retained_scene is sig
 c.zoom*=.5;c.pan_offset=QPointF(0,0);retained(c);assert c._drawing_image_key[3]==c.zoom;c.deleteLater()

@pytest.mark.parametrize('zoom',[.5,1,16,32])
def test_vector_colors_order_and_model_width(qapp,zoom):
 d=Document();d.entities=[LineEntity(Point(-20,-20),Point(20,20),color='#ff0000'),CircleEntity(Point(0,0),10,color='#00ff00'),PolylineEntity([Point(-15,5),Point(15,5)],width=2,color='#0000ff')]
 c=CadCanvas(d);c.zoom=zoom;c.pan_offset=QPointF(0,0)
 image=QImage(c.viewport().size(),QImage.Format.Format_ARGB32_Premultiplied);image.fill(Qt.GlobalColor.transparent);p=QPainter(image)
 try:
  item,exact=r.record(c,d.entities,p.renderHints());assert exact;r.draw(c,p,dict(items=[item]))
 finally:p.end()
 direct=frame(c,False)
 for color in ('#ff0000','#00ff00','#0000ff'):
  def bounds(im):
   pts=[(x,y) for y in range(im.height()) for x in range(im.width()) if im.pixelColor(x,y).alpha() and im.pixelColor(x,y).name()==color]
   return (min(x for x,y in pts),min(y for x,y in pts),max(x for x,y in pts),max(y for x,y in pts)) if pts else None
  assert bounds(image)==bounds(direct)
 c.deleteLater()

def test_missing_bind_preserves_clip_transform_geometry_and_undo(qapp,tmp_path):
 d=Document();d.filepath=str(tmp_path/'drawing.pycad');curves=[CircleEntity(Point(0,0),2),PolylineEntity([Point(0,0),Point(4,0),Point(4,3)],bulges=[.5,0,0],width=.2)]
 d.blocks['R']=BlockDefinition('R',curves,source_filepath='missing.dxf',source_scale=.001)
 ref=BlockReferenceEntity('R',Point(12,30),scale=2,rotation=40,clip_boundary=[Point(0,0),Point(30,0),Point(30,40),Point(0,40)]);d.entities=[ref];d.sync_associative()
 before=entity_to_dict(ref);geometry=[entity_to_dict(e) for e in curves];assert source_missing(d,'R')
 assert bind(d,['R'],True)==['R'];assert not d.blocks['R'].is_xref
 assert entity_to_dict(ref)==before and [entity_to_dict(e) for e in d.blocks['R'].entities]==geometry and d.blocks['R'].source_scale==.001
 loaded=document_from_dict(document_to_dict(d));assert not loaded.blocks['R'].is_xref and entity_to_dict(loaded.entities[0])==before
 d.undo_stack.undo();assert d.blocks['R'].source_filepath=='missing.dxf';d.undo_stack.redo();assert not d.blocks['R'].is_xref

def test_missing_only_keeps_live_nested_link(qapp,tmp_path):
 path=tmp_path/'live.dxf';path.write_bytes(b'external source must not change')
 d=Document();d.blocks['Live']=BlockDefinition('Live',[LineEntity(Point(0,0),Point(1,1))],source_filepath=str(path));d.blocks['Missing']=BlockDefinition('Missing',[BlockReferenceEntity('Live',Point(0,0))],source_filepath='not-here.dxf');d.entities=[BlockReferenceEntity('Missing',Point(0,0))];d.sync_associative()
 assert bind(d,list(d.blocks),True)==['Missing'];assert d.blocks['Live'].is_xref
 assert bind(d,['Live'])==['Live'];assert path.read_bytes()==b'external source must not change'

def test_unloaded_bind_and_atomic_corruption_rejection(qapp,monkeypatch,tmp_path):
 import pycad.xref_manager as x
 monkeypatch.setattr(x,'cache_folder',lambda:tmp_path)
 d=Document();d.blocks['R']=BlockDefinition('R',[CircleEntity(Point(1,2),3)],source_filepath='gone.dxf');d.entities=[BlockReferenceEntity('R',Point(0,0))];d.sync_associative();unload(d,'R')
 cache=tmp_path/(d.extensions['workflow']['xref_unloaded']['R']['cache']+'.json');raw=cache.read_bytes();cache.write_bytes(b'bad');count=d.undo_stack.count()
 with pytest.raises(ValueError,match='integrity'):bind(d,['R'])
 assert d.blocks['R'].is_xref and not d.blocks['R'].entities and count==d.undo_stack.count()
 cache.write_bytes(raw);assert bind(d,['R'])==['R'];assert isinstance(d.blocks['R'].entities[0],CircleEntity)
 d.undo_stack.undo();assert d.blocks['R'].is_xref and not d.blocks['R'].entities and 'R' in d.extensions['workflow']['xref_unloaded']
 d.undo_stack.redo();assert not d.blocks['R'].is_xref and d.blocks['R'].entities

def test_editor_binds_missing_xref(main_window,monkeypatch,tmp_path):
 import pycad.main_window as w
 doc=main_window.document;doc.blocks['R']=BlockDefinition('R',[CircleEntity(Point(0,0),3)],source_filepath=str(tmp_path/'missing.dxf'))
 class Dialog:
  def __init__(self,mw,name,block):assert not block.is_xref
  def exec(self):return 0
 monkeypatch.setattr(w,'BlockEditorDialog',Dialog)
 main_window.edit_block_dialog('R');assert not doc.blocks['R'].is_xref
 assert {'BIND','BINDMISSING'}<=set(main_window.command_names)


def test_layer_and_revision_changes_discard_retained_geometry(qapp):
 d=drawing(6000);c=CadCanvas(d);c.zoom=.7;c.pan_offset=QPointF(600,20);retained(c);old=c._retained_scene
 d.entities[0].p1.x=-20;d.dirty=True;d.spatial_index.invalidate();retained(c)
 assert c._retained_scene is not old and c._drawing_image_key[1]==d.render_revision
 old=c._retained_scene;d.layers.layers['0']['color']='#ff0000';retained(c);assert c._retained_scene is not old
 c.deleteLater()


def test_nested_clips_and_opacity_in_display_list(qapp):
 d=drawing(6000);root=BlockReferenceEntity('R',Point(0,0),transparency=25,clip_boundary=[Point(0,0),Point(550,0),Point(550,35),Point(0,35)]);root.resolved_entities=d.entities;d.entities=[root];c=CadCanvas(d);c.zoom=.7;c.pan_offset=QPointF(400,20)
 direct=frame(c,False);result=retained(c);assert result==direct
 c.deleteLater()


def test_dashed_lines_use_full_renderer_fallback(qapp):
 d=drawing(6000)
 for e in d.entities:e.linetype='DASHED'
 c=CadCanvas(d);c.zoom=.7;c.pan_offset=QPointF(600,20);retained(c);assert not c._retained_scene['exact'] and c._retained_scene['ready']
 wheel(c);frame(c);c._finish_navigation_preview();image=frame(c);assert not image.isNull();c.deleteLater()

@pytest.mark.parametrize('bulge',[.5,-.5,2.,-2.])
def test_compact_arc_path_follows_polyline_curve(qapp,bulge):
 from pycad.precision import segment_point
 d=Document();e=PolylineEntity([Point(-10,0),Point(10,0)],bulges=[bulge,0]);d.entities=[e];c=CadCanvas(d);c.zoom=8;c.pan_offset=QPointF(0,0)
 im=QImage(c.viewport().size(),QImage.Format.Format_ARGB32_Premultiplied);im.fill(Qt.GlobalColor.transparent);p=QPainter(im)
 try:
  item,exact=r.record(c,[e],p.renderHints());assert exact;r.draw(c,p,dict(items=[item]))
 finally:p.end()
 for t in (.1,.25,.5,.75,.9):
  point=segment_point(e.points[0],e.points[1],bulge,t);screen=c.world_to_screen(point.x,point.y);x=round(screen.x());y=round(screen.y())
  if 2<=x<im.width()-2 and 2<=y<im.height()-2:assert any(im.pixelColor(x+dx,y+dy).alpha()>0 for dx in (-1,0,1) for dy in (-1,0,1))
 c.deleteLater()


def test_bound_reference_dxf_roundtrip_retains_curves(qapp,tmp_path):
 from pycad.dxf_io import export_dxf,import_dxf
 d=Document();d.blocks['Ref']=BlockDefinition('Ref',[CircleEntity(Point(2,3),4),PolylineEntity([Point(0,0),Point(5,0)],bulges=[.5,0])],source_filepath='missing.dxf');d.entities=[BlockReferenceEntity('Ref',Point(20,40))];d.sync_associative();bind(d,['Ref'])
 path=tmp_path/'bound.dxf';export_dxf(d,str(path));loaded=import_dxf(str(path));assert not loaded.blocks['Ref'].is_xref
 assert isinstance(loaded.blocks['Ref'].entities[0],CircleEntity) and loaded.blocks['Ref'].entities[1].bulges[0]==pytest.approx(.5)
 assert loaded.entities[0].insertion_point.as_tuple()==(20,40)


def test_dynamic_object_does_not_disable_static_cache(qapp,monkeypatch):
 from pycad.geometry import PointEntity
 d=drawing(6000);point=PointEntity(Point(600,20));d.entities.insert(300,point);c=CadCanvas(d);c.zoom=.7;c.pan_offset=QPointF(600,20);retained(c)
 assert not c._retained_scene['exact'];calls=[];original=c._draw_entities
 def traced(*args,**kw):calls.extend(kw.get('entities',[]));return original(*args,**kw)
 monkeypatch.setattr(c,'_draw_entities',traced);c.zoom*=1.2;retained(c)
 assert calls==[point];c.deleteLater()


def test_dynamic_selection_stays_out_of_base_cache(qapp):
 from pycad.geometry import PointEntity
 d=drawing(6000);point=PointEntity(Point(600,20));d.entities.insert(0,point);c=CadCanvas(d);c.zoom=.7;c.pan_offset=QPointF(600,20);c.selected_entities=[point];retained(c);base=c._drawing_image.copy()
 c.selected_entities=[];result=retained(c);assert result==base;c.deleteLater()


def test_unbounded_construction_line_reaches_distant_view(qapp):
 from pycad.geometry import XLineEntity
 d=drawing(6000);d.entities.append(XLineEntity(Point(0,0),Point(1,0)));c=CadCanvas(d);c.zoom=1;c.pan_offset=QPointF(50000,0);image=retained(c)
 assert image.pixelColor(image.width()//2,image.height()//2).alpha()>0;c.deleteLater()
