import pytest
from PyQt6.QtCore import QPointF
from pycad.document import Document
from pycad.canvas import CadCanvas
from pycad.geometry import Point,TextEntity,BlockReferenceEntity,LineEntity
from pycad.render_snapshot import freeze_iter,value_copy
from pycad.async_display import freeze_entities
from test_background_16_38 import wait,dispose

def cooperative(entities):
 it=freeze_iter(entities)
 while True:
  try:next(it)
  except StopIteration as done:return done.value

@pytest.mark.parametrize('freeze',[cooperative,freeze_entities])
def test_text_snapshot_preserves_style_and_bbox_without_caches(freeze):
 text=TextEntity(Point(4,7),'Styled\ntext',wrap_width=8,rotation=20)
 text._text_style.update(width_factor=1.8,oblique=14,bold=True)
 text._display_index=object()
 root=BlockReferenceEntity('Notes',Point(0,0));root.resolved_entities=[text]
 clone=freeze([root])[0].resolved_entities[0]
 assert clone.bbox()==text.bbox()
 assert clone._text_style==text._text_style and clone._text_style is not text._text_style
 assert '_display_index' not in clone.__dict__
 clone._text_style['width_factor']=.2
 assert text._text_style['width_factor']==1.8

@pytest.mark.parametrize('nested',[False,True])
def test_visible_heavy_drawing_with_styled_text_renders_and_selects(qapp,nested):
 d=Document();text=TextEntity(Point(590,20),'Imported notes',style_name='Notes')
 text._text_style.update(width_factor=1.7,oblique=12)
 if nested:
  root=BlockReferenceEntity('Notes',Point(0,0));root.resolved_entities=[text]
 else:root=text
 d.entities=[LineEntity(Point(i,0),Point(i,30)) for i in range(7000)]+[root]
 c=CadCanvas(d);c.resize(1000,700);c.zoom=.7;c.pan_offset=QPointF(600,25);c.show()
 try:
  wait(qapp,lambda:c.__dict__.get('_last_draw_kind')=='background cached frame' or bool(c.__dict__.get('_render_process_error')),30)
  assert not c.__dict__.get('_render_process_error')
  c.selected_entities=[root];c.viewport().update()
  wait(qapp,lambda:c.__dict__.get('_selection_complete',False),30)
  assert not c.__dict__.get('_render_process_error')
 finally:dispose(c,qapp)
