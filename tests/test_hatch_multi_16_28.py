"""Multiple area picks stay staged, use common settings and commit atomically."""
import copy
import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage,QPainter,QColor
from pycad.geometry import Point,RectangleEntity,HatchEntity,CircleEntity
from pycad.tools import HatchTool
from pycad.native_io import document_to_dict,save_project,load_project

LEFT=Qt.MouseButton.LeftButton.value


def begin(mw):
    mw.set_tool('HATCH',hatch_configured=True);tool=mw.current_tool;tool.options.update(pattern='ANSI31',angle=25,pattern_scale=2,color='#22aa66');return tool


def mock_regions(monkeypatch):
    import pycad.geom_ops as geom
    def detect(entities,click,*args,**kwargs):
        if click.y<0:return None
        x=0 if click.x<20 else 30
        return [Point(x,0),Point(x+10,0),Point(x+10,10),Point(x,10)]
    monkeypatch.setattr(geom,'flood_fill_boundary',detect)


def test_multiple_picks_common_settings_and_one_undo(main_window,monkeypatch,tmp_path):
    mock_regions(monkeypatch);mw=main_window;tool=begin(mw);before=document_to_dict(mw.document)
    tool.on_click(5,5,'',LEFT);tool.on_click(35,5,'',LEFT)
    assert len(tool.areas)==2 and '2 area(s)' in tool.status_prompt() and document_to_dict(mw.document)==before
    tool.on_key(Qt.Key.Key_Return);hatches=[e for e in mw.document.entities if isinstance(e,HatchEntity)]
    assert len(hatches)==2 and all(h.pattern=='ANSI31' and h.angle==25 and h.pattern_scale==2 and h.color=='#22aa66' for h in hatches)
    assert mw.document.undo_stack.index()==1
    save_project(mw.document,tmp_path/'areas.pycad');assert len(load_project(tmp_path/'areas.pycad').entities)==2
    mw.document.undo_stack.undo();assert document_to_dict(mw.document)==before
    mw.document.undo_stack.redo();assert len(mw.document.entities)==2


def test_repeated_pick_does_not_duplicate(main_window,monkeypatch):
    mock_regions(monkeypatch);tool=begin(main_window)
    for _ in range(3):tool.on_click(5,5,'',LEFT)
    assert len(tool.areas)==1


def test_remove_last_and_repick(main_window,monkeypatch):
    mock_regions(monkeypatch);tool=begin(main_window);tool.on_click(5,5,'',LEFT);tool.on_click(35,5,'',LEFT);tool.on_text_input('U')
    assert len(tool.areas)==1 and tool.boundary_points[0].x==0
    tool.on_text_input('REMOVE');assert tool.boundary_points is None
    tool.on_click(35,5,'',LEFT);tool.on_key(Qt.Key.Key_Return);assert len(main_window.document.entities)==1 and main_window.document.entities[0].boundary[0].x==30


def test_invalid_pick_preserves_previous_areas(main_window,monkeypatch):
    mock_regions(monkeypatch);tool=begin(main_window);tool.on_click(5,5,'',LEFT);tool.on_click(100,-100,'',LEFT)
    assert len(tool.areas)==1 and tool.boundary_points is not None
    tool.on_key(Qt.Key.Key_Return);assert len(main_window.document.entities)==1


def test_escape_discards_all_previews(main_window,monkeypatch):
    mock_regions(monkeypatch);tool=begin(main_window);before=document_to_dict(main_window.document);tool.on_click(5,5,'',LEFT);tool.on_click(35,5,'',LEFT);tool.on_key(Qt.Key.Key_Escape)
    assert document_to_dict(main_window.document)==before and main_window.document.undo_stack.index()==0


def test_pattern_input_applies_all_picks(main_window,monkeypatch):
    mock_regions(monkeypatch);tool=begin(main_window);tool.on_click(5,5,'',LEFT);tool.on_click(35,5,'',LEFT);tool.on_text_input('SOLID')
    assert len(main_window.document.entities)==2 and all(e.pattern=='SOLID' for e in main_window.document.entities)


def test_fallback_preserves_independent_source_links(main_window,monkeypatch):
    import pycad.geom_ops as geom
    monkeypatch.setattr(geom,'flood_fill_boundary',lambda *a,**k:None)
    mw=main_window;a=RectangleEntity(Point(0,0),Point(10,10));b=CircleEntity(Point(30,5),5);mw.document.entities=[a,b];tool=begin(mw)
    tool.on_click(0,5,'',LEFT);tool.on_click(35,5,'',LEFT);tool.on_key(Qt.Key.Key_Return)
    assert [h.source_entity_id for h in mw.document.entities if isinstance(h,HatchEntity)]==[a.id,b.id]


def test_holes_do_not_leak_between_regions(main_window,monkeypatch):
    mock_regions(monkeypatch);mw=main_window;hole=CircleEntity(Point(5,5),1);mw.document.entities=[hole];tool=begin(mw);tool.on_click(2,2,'',LEFT);tool.on_click(35,5,'',LEFT)
    assert len(tool.areas[0]['holes'])==1 and not tool.areas[1]['holes']
    tool.on_key(Qt.Key.Key_Return);hatches=[e for e in mw.document.entities if isinstance(e,HatchEntity)];assert len(hatches[0].holes)==1 and not hatches[1].holes


def test_stale_drawing_rejected_without_partial_hatches(main_window,monkeypatch):
    mock_regions(monkeypatch);tool=begin(main_window);tool.on_click(5,5,'',LEFT);tool.on_click(35,5,'',LEFT);main_window.document.sync_associative();before=document_to_dict(main_window.document)
    with pytest.raises(ValueError,match='Drawing changed'):tool.on_key(Qt.Key.Key_Return)
    assert document_to_dict(main_window.document)==before and main_window.document.undo_stack.index()==0


def test_all_previews_draw_without_mutation(main_window,monkeypatch):
    mock_regions(monkeypatch);mw=main_window;tool=begin(mw);tool.on_click(5,5,'',LEFT);tool.on_click(35,5,'',LEFT);before=document_to_dict(mw.document);image=QImage(mw.canvas.viewport().size(),QImage.Format.Format_ARGB32);image.fill(QColor('white'));p=QPainter(image);tool.draw_preview(p,mw.canvas);p.end();assert document_to_dict(mw.document)==before


def test_real_two_enclosures_pick_and_apply(main_window):
    mw=main_window;mw.document.entities=[RectangleEntity(Point(0,0),Point(10,10)),RectangleEntity(Point(20,0),Point(30,10))];mw.canvas.zoom_extents();tool=begin(mw);tool.on_click(5,5,'',LEFT);tool.on_click(25,5,'',LEFT);assert len(tool.areas)==2;tool.on_key(Qt.Key.Key_Return);assert len([e for e in mw.document.entities if isinstance(e,HatchEntity)])==2


def test_detector_error_retains_existing_preview(main_window,monkeypatch):
    mock_regions(monkeypatch);tool=begin(main_window);tool.on_click(5,5,'',LEFT)
    def fail(*args):raise ValueError('Invalid second boundary')
    monkeypatch.setattr(tool,'_detect_area',fail)
    with pytest.raises(ValueError):tool.on_click(35,5,'',LEFT)
    assert len(tool.areas)==1 and tool.boundary_points is not None
    tool.on_key(Qt.Key.Key_Return);assert len(main_window.document.entities)==1


def test_remove_last_shortcut_is_available_and_enabled(main_window,monkeypatch):
    from pycad.command_options import options,resolve
    mock_regions(monkeypatch);tool=begin(main_window);assert not next(o for o in options(main_window) if o.key=='U').enabled
    tool.on_click(5,5,'',LEFT);assert resolve(main_window,'REMOVE').key=='U' and resolve(main_window,'U').enabled
