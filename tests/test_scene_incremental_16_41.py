import pytest
from PyQt6.QtCore import QPointF
from pycad.document import Document
from pycad.geometry import Point,LineEntity
from pycad.canvas import CadCanvas
from test_persistent_scene_16_40 import ready,wait,frame


def test_one_edit_reuses_unchanged_command_lists_and_worker(qapp,monkeypatch):
 monkeypatch.delenv('PYCAD_LEGACY_DISPLAY',raising=False)
 d=Document();d.entities=[LineEntity(Point(i,0),Point(i,20)) for i in range(8000)];c=CadCanvas(d);c.resize(900,600);c.zoom=.5;c.pan_offset=QPointF(300,10);c.show()
 try:
  ready(qapp,c);old=c._scene_controller.scene;pid=c._persistent_worker_stats['renderer_pid'];old_picture=old['pictures'][2]
  d.entities[0].p1.x=-100;d.dirty=True;c.viewport().update();qapp.processEvents();ready(qapp,c)
  stats=c._persistent_worker_stats
  assert stats['renderer_pid']==pid and stats['vector_cache_misses']==1 and stats['vector_cache_hits']==31
  assert c._scene_controller.scene['pictures'][2] is old_picture
  assert c._scene_controller.scene['pictures'][0] is not old['pictures'][0]
 finally:c._scene_controller.close();c.hide();c.deleteLater();qapp.processEvents()


def test_pick_index_is_warm_before_first_query_and_matches_updated_bounds(qapp,monkeypatch):
 monkeypatch.delenv('PYCAD_LEGACY_DISPLAY',raising=False)
 d=Document();d.entities=[LineEntity(Point(i,0),Point(i,20)) for i in range(8000)];c=CadCanvas(d);c.show()
 try:
  ready(qapp,c);wait(qapp,lambda:getattr(d,'_spatial_revision',None)==d.render_revision)
  monkeypatch.setattr(d,'rebuild_spatial_index',lambda:pytest.fail('Cold index built on first pick'))
  assert len(d.query_entities((1.9,-1,2.1,21)))==1
  d.entities[2].p1.x=-500;d.entities[2].p2.x=-500;d.dirty=True;c.viewport().update();qapp.processEvents();ready(qapp,c)
  wait(qapp,lambda:getattr(d,'_spatial_revision',None)==d.render_revision)
  assert not d.query_entities((1.9,-1,2.1,21)) and d.entities[2] in d.query_entities((-501,-1,-499,21))
 finally:c._scene_controller.close();c.hide();c.deleteLater();qapp.processEvents()


def test_style_change_invalidates_cached_commands(qapp,monkeypatch):
 monkeypatch.delenv('PYCAD_LEGACY_DISPLAY',raising=False)
 d=Document();d.entities=[LineEntity(Point(i,0),Point(i,20),color='BYLAYER') for i in range(800)];c=CadCanvas(d);c.show()
 try:
  ready(qapp,c);old=c._scene_controller.scene
  d.layers.layers['0']['color']='#ff0000';d.dirty=True;c.viewport().update();qapp.processEvents();ready(qapp,c)
  assert c._persistent_worker_stats['vector_cache_hits']==0 and c._persistent_worker_stats['vector_cache_misses']==4
  assert c._scene_controller.scene['pictures'][0] is not old['pictures'][0]
 finally:c._scene_controller.close();c.hide();c.deleteLater();qapp.processEvents()


def test_explicit_regen_rebuilds_all_batches(qapp,monkeypatch):
 from pycad.persistent_scene import regenerate
 monkeypatch.delenv('PYCAD_LEGACY_DISPLAY',raising=False)
 d=Document();d.entities=[LineEntity(Point(i,0),Point(i,20)) for i in range(800)];c=CadCanvas(d);c.show()
 try:
  ready(qapp,c);regenerate(c);qapp.processEvents();ready(qapp,c)
  assert c._persistent_worker_stats['vector_cache_hits']==0 and c._persistent_worker_stats['vector_cache_misses']==4
 finally:c._scene_controller.close();c.hide();c.deleteLater();qapp.processEvents()
