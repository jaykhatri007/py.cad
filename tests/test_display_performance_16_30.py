import copy
import pytest
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QImage,QPainter
from pycad.document import Document
from pycad.geometry import Point,LineEntity,BlockDefinition,BlockReferenceEntity,RayEntity
from pycad.canvas import CadCanvas
from pycad.native_io import document_to_dict,save_project,load_project
from pycad.block_display import visible_children


def block_doc():
 d=Document();items=[LineEntity(Point(i*10,0),Point(i*10+1,1)) for i in range(100)];d.blocks['Grid']=BlockDefinition('Grid',items);ref=BlockReferenceEntity('Grid',Point(0,0));d.entities=[ref];d.sync_associative();return d,ref

def test_ordered_child_culling_and_transform_invalidation(qapp):
 d,r=block_doc();before=document_to_dict(d);out=visible_children(r,(-1,-1,12,2),d.render_revision);assert [e.p1.x for e in out]==[0,10];assert document_to_dict(d)==before
 r.translate(1000,0);assert not visible_children(r,(-1,-1,12,2),d.render_revision)
 assert [e.p1.x for e in visible_children(r,(999,-1,1012,2),d.render_revision)]==[1000,1010]
 r.resolved_entities[0].translate(500,0);d.render_revision+=1;assert [e.p1.x for e in visible_children(r,(999,-1,1012,2),d.render_revision)]==[1010]

def test_unbounded_child_retained(qapp):
 d,r=block_doc();ray=RayEntity(Point(10000,10000),Point(10001,10001));r.resolved_entities.insert(0,ray);out=visible_children(r,(-1,-1,12,2),d.render_revision);assert out[0] is ray and [e.p1.x for e in out[1:]]==[0,10]

def test_display_cache_not_native_data(qapp,tmp_path):
 d,r=block_doc();before=document_to_dict(d);visible_children(r,(-1,-1,12,2),d.render_revision);assert document_to_dict(d)==before;save_project(d,tmp_path/'d.pycad');assert document_to_dict(load_project(tmp_path/'d.pycad'))==document_to_dict(d)

def test_frame_transform_and_cleanup(qapp,monkeypatch):
 c=CadCanvas(Document());c.resize(600,400);c.zoom=7;c.pan_offset=QPointF(37,-14);expected=[c.world_to_screen(x,y) for x,y in [(0,0),(10,20),(-50,30)]];image=QImage(600,400,QImage.Format.Format_ARGB32);p=QPainter(image)
 def paint(*args):
  assert [c.world_to_screen(x,y) for x,y in [(0,0),(10,20),(-50,30)]]==expected
  raise ValueError('Stop frame')
 monkeypatch.setattr(c,'_paint_entities',paint)
 with pytest.raises(ValueError,match='Stop frame'):c._draw_entities(p)
 p.end();assert '_frame_transform' not in c.__dict__ and '_frame_world_box' not in c.__dict__ and '_frame_pixel_scale' not in c.__dict__

def test_custom_plot_transform_not_culled(qapp,monkeypatch):
 c=CadCanvas(Document());c._plot_mm=3;c.world_to_screen=lambda x,y:QPointF(2*x+5,4*y+9);image=QImage(20,20,QImage.Format.Format_ARGB32);p=QPainter(image)
 def paint(*args):assert c.__dict__['_frame_world_box'] is None and c.__dict__['_frame_pixel_scale']==2 and c.world_to_screen(2,3)==QPointF(9,21)
 monkeypatch.setattr(c,'_paint_entities',paint);c._draw_entities(p,paper=True);p.end()

def test_culling_preserves_visible_pixels_and_selection(qapp,monkeypatch):
 from pycad import block_display
 d,r=block_doc();c=CadCanvas(d);c.resize(500,400);c.zoom=3;c.pan_offset=QPointF(20,0);before=document_to_dict(d)
 def render():
  image=QImage(c.viewport().size(),QImage.Format.Format_ARGB32);image.fill(0);p=QPainter(image);c._draw_entities(p);p.end();return image
 expected=render();monkeypatch.setattr(block_display,'visible_children',lambda ref,box,revision:ref.resolved_entities);actual=render();assert actual==expected and document_to_dict(d)==before

def test_pick_exact_tie_keeps_first(qapp):
 from pycad.geom_ops import pick_entity
 a=LineEntity(Point(0,0),Point(10,0));b=LineEntity(Point(0,0),Point(10,0));assert pick_entity([a,b],Point(5,0),1) is a

def test_explicit_level_visibility_retained(qapp):
 from pycad.building import visible
 d=Document();assert visible(d,'x');d.extensions['levels']={'Ground':dict(elevation=0,height=3000,visible=False)};assert not visible(d,'x')

def test_navigation_preview_reuses_cache_then_finishes_exact(qapp,monkeypatch):
 d,r=block_doc();c=CadCanvas(d);c.resize(500,400);c.zoom=3;c.pan_offset=QPointF(20,0);before=document_to_dict(d)
 def render():
  im=QImage(c.viewport().size(),QImage.Format.Format_ARGB32);im.fill(0);p=QPainter(im);c._draw_cached_entities(p);p.end();return im
 render();key=c._drawing_image_key;calls=[];original=c._draw_entities
 def count(*args,**kwargs):calls.append(1);return original(*args,**kwargs)
 monkeypatch.setattr(c,'_draw_entities',count);c._panning=True;c.pan_offset=QPointF(30,0);render();assert not calls and c._drawing_image_key==key
 c._panning=False;c._finish_navigation_preview();image=render();assert calls and c._drawing_image_key!=key
 expected=QImage(c.viewport().size(),QImage.Format.Format_ARGB32);expected.fill(0);p=QPainter(expected);original(p);p.end();assert image==expected and document_to_dict(d)==before

def test_navigation_does_not_reuse_stale_geometry(qapp,monkeypatch):
 d,r=block_doc();c=CadCanvas(d);im=QImage(c.viewport().size(),QImage.Format.Format_ARGB32);im.fill(0);p=QPainter(im);c._draw_cached_entities(p);key=c._drawing_image_key;c._panning=True;d.render_revision+=1;c._draw_cached_entities(p);p.end();assert c._drawing_image_key!=key
