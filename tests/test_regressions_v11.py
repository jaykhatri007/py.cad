"""Failure-oriented tests for the v10 audit, including real Qt input and disk round trips."""

import json
import math
import pytest
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QMessageBox, QFileDialog
from pycad.document import (
    Document,
    AddEntityCommand,
    DeleteEntitiesCommand,
    TranslateEntitiesCommand,
    RotateEntitiesCommand,
    SetPointCommand,
)
from pycad.geometry import (
    Point,
    LineEntity,
    CircleEntity,
    ArcEntity,
    RectangleEntity,
    TextEntity,
    DimensionEntity,
    HatchEntity,
    BlockDefinition,
    BlockReferenceEntity,
    SplineEntity,
)
from pycad import native_io, dxf_io, geom_ops, appsettings
from pycad.tools import Tool


def drawing():
    d = Document()
    line = LineEntity(Point(0, 0), Point(100, 0), linetype="DASHED")
    d.add_entity(line)
    d.add_entity(
        DimensionEntity(
            Point(0, 0),
            Point(100, 0),
            Point(50, 10),
            source_line_id=line.id,
            text_override="WALL",
        )
    )
    d.add_entity(
        HatchEntity([Point(0, 0), Point(10, 0), Point(10, 10)], pattern="LINES")
    )
    d.add_entity(TextEntity(Point(1, 2), "Door", rotation=25))
    d.add_entity(SplineEntity([Point(0, 0), Point(5, 9), Point(10, 0)], closed=True))
    d.add_block(
        BlockDefinition("_symbol", [CircleEntity(Point(0, 0), 2)], "source.dxf")
    )
    d.add_entity(BlockReferenceEntity("_symbol", Point(20, 20), mirrored=True))
    d.add_layout("Sheet1")
    d.layers.set_color("0", "#ABCDEF")
    d.sync_associative()
    return d


def test_native_roundtrip_preserves_editability(tmp_path):
    d = drawing()
    path = tmp_path / "test.pycad"
    native_io.save_project(d, path)
    loaded = native_io.load_project(path)
    assert native_io.document_to_dict(loaded) == native_io.document_to_dict(d)
    assert not loaded.dirty
    line, dim = loaded.entities[:2]
    loaded.undo_stack.push(TranslateEntitiesCommand(loaded, [line], 15, 0))
    assert dim.p1.x == 15 and dim.text_override == "WALL"
    loaded.undo_stack.undo()
    assert dim.p1.x == 0 and not loaded.dirty


def test_native_rejects_new_schema_and_nan(tmp_path):
    for data in (
        {"format": "PyCAD", "schema_version": 99},
        {"format": "PyCAD", "schema_version": 1, "x": float("nan")},
    ):
        path = tmp_path / "bad.pycad"
        path.write_text(json.dumps(data))
        with pytest.raises(ValueError):
            native_io.load_project(path)


def test_atomic_write_failure_keeps_original(tmp_path):
    path = tmp_path / "drawing.pycad"
    path.write_text("valuable drawing")

    def fail(temporary):
        open(temporary, "w").write("partial")
        raise OSError("disk failure")

    with pytest.raises(OSError):
        native_io.atomic_write(path, fail)
    assert path.read_text() == "valuable drawing"
    assert len(list(tmp_path.iterdir())) == 1


def test_dirty_tracks_move_rotate_undo_and_layer_changes():
    d = Document()
    e = LineEntity(Point(0, 0), Point(10, 0))
    d.add_entity(e)
    d.mark_saved()
    d.undo_stack.push(TranslateEntitiesCommand(d, [e], 5, 6))
    assert d.dirty
    d.undo_stack.undo()
    assert not d.dirty
    d.layers.set_color("0", "#112233")
    assert d.dirty


def test_delete_undo_restores_draw_order():
    d = Document()
    items = [CircleEntity(Point(i, 0), 1) for i in range(4)]
    for e in items:
        d.add_entity(e)
    d.undo_stack.push(DeleteEntitiesCommand(d, [items[0], items[2]]))
    d.undo_stack.undo()
    assert d.entities == items


def test_grip_undo_after_transform_resolves_current_point():
    d = Document()
    e = LineEntity(Point(0, 0), Point(10, 0))
    d.add_entity(e)
    d.undo_stack.push(SetPointCommand(d, e.p1, (0, 0), (2, 3)))
    d.undo_stack.push(RotateEntitiesCommand(d, [e], Point(0, 0), 90))
    d.undo_stack.undo()
    d.undo_stack.undo()
    assert e.p1.x == pytest.approx(0) and e.p1.y == pytest.approx(0)


def test_drag_move_single_undo(main_window):
    w = main_window
    e = LineEntity(Point(0, 0), Point(100, 0))
    w.document.add_entity(e)
    w.document.mark_saved()
    w.current_tool.on_click(40, 0, "", 1)
    w.current_tool.on_move(45, 5, "")
    w.current_tool.on_move(50, 7, "")
    w.current_tool.finish_drag()
    assert w.document.undo_stack.count() == 1 and e.p1.as_tuple() == (10, 7)
    w.undo()
    assert e.p1.as_tuple() == (0, 0) and not w.document.dirty


def test_escape_reverts_live_drag(main_window):
    w = main_window
    e = LineEntity(Point(0, 0), Point(100, 0))
    w.document.add_entity(e)
    w.document.mark_saved()
    w.current_tool.on_click(40, 0, "", 1)
    w.current_tool.on_move(45, 5, "")
    w.cancel_command()
    assert e.p1.as_tuple() == (0, 0) and not w.document.dirty


def test_locked_layer_not_pickable_or_deletable(main_window):
    w = main_window
    e = LineEntity(Point(0, 0), Point(100, 0))
    w.document.add_entity(e)
    w.document.layers.set_locked("0", True)
    assert w.current_tool._pick_entity(30, 0) is None
    w.document.undo_stack.push(DeleteEntitiesCommand(w.document, [e]))
    assert e in w.document.entities


def test_selection_is_distance_based_not_bbox(main_window):
    w = main_window
    e = LineEntity(Point(0, 0), Point(100, 100))
    w.document.add_entity(e)
    assert w.current_tool._pick_entity(1, 90) is None
    assert w.current_tool._pick_entity(50, 50) is e


def test_real_command_typing_does_not_trigger_letter_shortcuts(main_window):
    w = main_window
    w.command_line.setFocus()
    QTest.keyClicks(w.command_line, "LINE")
    assert w.command_line.text() == "LINE" and w.current_tool.name == "SELECT"
    QTest.keyClick(w.command_line, Qt.Key.Key_Return)
    for text in ("0,0", "@100<30"):
        QTest.keyClicks(w.command_line, text)
        QTest.keyClick(w.command_line, Qt.Key.Key_Return)
    assert len(w.document.entities) == 1
    assert w.document.entities[0].length() == pytest.approx(100)
    QTest.keyClick(w.command_line, Qt.Key.Key_Escape)
    assert w.current_tool.name == "SELECT"


def test_status_updates_after_canvas_click(main_window):
    w = main_window
    w.set_tool("CIRCLE")
    w._on_world_clicked(0, 0, "", 1)
    assert "radius" in w.tool_label.text().lower()


@pytest.mark.parametrize("text", ["nan,0", "0,inf", "@5,0", "1e309,0"])
def test_invalid_points_rejected(text):
    assert Tool.parse_point(text) is None


def test_polar_relative_coordinates():
    p = Tool.parse_point("@10<90", Point(2, 3))
    assert p.x == pytest.approx(2) and p.y == pytest.approx(13)


def test_new_cancel_keeps_drawing(main_window, monkeypatch):
    w = main_window
    e = CircleEntity(Point(0, 0), 2)
    w.document.add_entity(e)
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *a, **k: QMessageBox.StandardButton.Cancel
    )
    assert not w.drawing_tabs.close_drawing(w.drawing_tabs.active) and e in w.document.entities


def test_save_cancel_blocks_close(main_window, monkeypatch):
    w = main_window
    w.document.add_entity(CircleEntity(Point(0, 0), 2))
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *a, **k: QMessageBox.StandardButton.Save
    )
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: ("", ""))
    assert not w.close() and w.isVisible()


def test_save_failure_blocks_replacement(main_window, monkeypatch, tmp_path):
    w = main_window
    w.document.add_entity(CircleEntity(Point(0, 0), 2))
    w.document.filepath = str(tmp_path / "x.pycad")
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *a, **k: QMessageBox.StandardButton.Save
    )
    monkeypatch.setattr(
        QMessageBox, "critical", lambda *a, **k: QMessageBox.StandardButton.Ok
    )
    monkeypatch.setattr(
        dxf_io,
        "export_any",
        lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")),
    )
    assert not w.drawing_tabs.close_drawing(w.drawing_tabs.active) and len(w.document.entities) == 1


def test_document_switch_resets_tools_tabs_selection(main_window, tmp_path):
    w = main_window
    d = drawing()
    w._replace_document(d)
    w.set_tool("LINE")
    w.current_tool.on_text_input("1,2")
    empty = Document()
    w._replace_document(empty)
    assert w.current_tool.document is empty and w.canvas.document is empty
    assert w.current_tool.name == "SELECT" and not w.canvas.selected_entities
    assert w.space_tabs.count() == 1


def test_native_autosave_retains_dimension_and_empty_changes(main_window, tmp_path):
    w = main_window
    w._replace_document(drawing())
    w._do_autosave()
    loaded = native_io.load_project(appsettings.RECOVERY_PATH)
    assert isinstance(loaded.entities[1], DimensionEntity)
    w.document.entities = []
    w._do_autosave()
    assert not native_io.load_project(appsettings.RECOVERY_PATH).entities


def test_dxf_layer_and_viewport_roundtrip(tmp_path):
    d = Document()
    d.layers.add_layer("Walls", "#123456")
    d.layers.set_locked("Walls", True)
    d.layers.set_visible("Walls", False)
    d.add_entity(CircleEntity(Point(0, 0), 3, layer="Walls"))
    v = d.add_layout("Layout1").viewports[0]
    v.scale = 0.01
    p = tmp_path / "x.dxf"
    dxf_io.export_dxf(d, str(p))
    r = dxf_io.import_dxf(str(p))
    assert r.layers.layers["Walls"] == d.layers.layers["Walls"]
    assert r.layouts["Layout1"].viewports[0].scale == pytest.approx(0.01)
    assert not r.dirty


def test_ellipse_import_is_supported_and_roundtrips(tmp_path):
    import ezdxf

    raw = ezdxf.new()
    raw.modelspace().add_ellipse((0, 0), (10, 0), 0.5)
    p = tmp_path / "original.dxf"
    raw.saveas(p)
    d = dxf_io.import_dxf(str(p))
    assert not d.import_warnings
    assert d.entities[0].kind == "ELLIPSE"
    export_path = tmp_path / "ellipse-roundtrip.dxf"
    dxf_io.export_any(d, str(export_path))
    assert export_path.exists()


def test_dxf_nested_blocks_and_nonzero_base(tmp_path):
    import ezdxf

    raw = ezdxf.new()
    a = raw.blocks.new("_A", base_point=(5, 0))
    a.add_line((5, 0), (15, 0))
    b = raw.blocks.new("B")
    b.add_blockref("_A", (20, 0))
    raw.modelspace().add_blockref("B", (30, 0))
    p = tmp_path / "block.dxf"
    raw.saveas(p)
    d = dxf_io.import_dxf(str(p))
    assert d.entities[0].bbox() == pytest.approx((50, 0, 60, 0))


def test_closed_spline_export_does_not_crash(tmp_path):
    d = Document()
    d.add_entity(SplineEntity([Point(0, 0), Point(10, 0), Point(10, 10)], closed=True))
    dxf_io.export_dxf(d, str(tmp_path / "closed.dxf"))
    assert dxf_io.import_dxf(str(tmp_path / "closed.dxf")).entities[0].closed


def test_arc_wraparound_tessellation():
    e = ArcEntity(Point(0, 0), 10, 350, 10)
    segments = geom_ops.entity_to_segments(e)
    assert all(p.x > 9 for segment in segments for p in segment)


def test_mirrored_block_survives_rebuild():
    d = Document()
    b = BlockDefinition("X", [LineEntity(Point(1, 2), Point(4, 5))])
    d.add_block(b)
    e = BlockReferenceEntity("X", Point(10, 0))
    e.rebuild(b)
    e.reflect_across(Point(0, 0), Point(1, 0))
    d.add_entity(e)
    before = e.bbox()
    d.sync_associative()
    assert e.bbox() == pytest.approx(before)


def test_clone_preserves_linetype():
    for e in [
        LineEntity(Point(0, 0), Point(1, 1)),
        CircleEntity(Point(0, 0), 2),
        ArcEntity(Point(0, 0), 2, 0, 90),
        TextEntity(Point(0, 0), "A"),
    ]:
        e.linetype = "DASHED"
        assert e.clone().linetype == "DASHED"


def test_vector_pdf_physical_scale(qapp, tmp_path):
    fitz = pytest.importorskip("fitz")
    from pycad.plotting import export_pdf

    d = Document()
    d.add_entity(LineEntity(Point(0, 0), Point(100, 0)))
    path = tmp_path / "scale.pdf"
    export_pdf(d, str(path), scale_denominator=1)
    with fitz.open(path) as pdf:
        page = pdf[0]
        assert not page.get_images()
        assert page.rect.width == pytest.approx(297 / 25.4 * 72, abs=1)
        lines = [
            item
            for drawing in page.get_drawings()
            for item in drawing["items"]
            if item[0] == "l"
        ]
        assert lines and abs(lines[0][2].x - lines[0][1].x) == pytest.approx(
            100 / 25.4 * 72, abs=0.1
        )


def test_rectangle_offset_closes_last_corner_and_uses_consistent_side():
    points = RectangleEntity(Point(0, 0), Point(10, 10)).points
    outside = geom_ops.offset_polyline(points, True, 2, Point(20, 5))
    assert [p.as_tuple() for p in outside] == [(-2, -2), (12, -2), (12, 12), (-2, 12)]
    inside = geom_ops.offset_polyline(points, True, 2, Point(5, 5))
    assert [p.as_tuple() for p in inside] == [(2, 2), (8, 2), (8, 8), (2, 8)]
    with pytest.raises(ValueError, match="collapses"):
        geom_ops.offset_polyline(points, True, 6, Point(5, 5))


def test_creating_block_undo_removes_definition(main_window):
    w = main_window
    e = LineEntity(Point(0, 0), Point(10, 0))
    w.document.add_entity(e)
    w.canvas.selected_entities = [e]
    w.set_tool("BLOCK")
    w.current_tool.on_click(0, 0, "", 1)
    w.current_tool.on_text_input("Test")
    assert "Test" in w.document.blocks
    w.undo()
    assert "Test" not in w.document.blocks and e in w.document.entities
