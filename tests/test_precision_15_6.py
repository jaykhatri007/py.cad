"""Cross-component drafting, unit conversion, and curved annotation workflows."""

import math
import pytest
from PyQt6.QtCore import Qt, QEvent, QPointF, QTimer
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QCheckBox, QComboBox, QDialog
from pycad.geometry import (
    Point,
    LineEntity,
    ArcEntity,
    CircleEntity,
    BlockDefinition,
    BlockReferenceEntity,
)
from pycad.document import Document, AddEntityCommand, SetPointCommand, SetAttrCommand
from pycad.native_io import (
    document_to_dict,
    document_from_dict,
    save_project,
    load_project,
)
from pycad.unit_conversion import convert_units
from pycad.curved_dimensions import CurvedDimensionEntity
from pycad.dimstyles import dimension_geometry, dimension_label
from pycad.constraints import make_constraint, add_constraint, solve
from pycad.units import units_dialog


def move(w, qapp, x, y):
    view = w.canvas.viewport()
    pos = w.canvas.world_to_screen(x, y)
    qapp.sendEvent(
        view,
        QMouseEvent(
            QEvent.Type.MouseMove,
            pos,
            QPointF(view.mapToGlobal(pos.toPoint())),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        ),
    )
    qapp.processEvents()


def begin(w, qapp, name="LINE", raw=(3, 4)):
    w.canvas.snap_enabled = False
    w.set_tool(name)
    w._on_world_clicked(0, 0, "", 1)
    move(w, qapp, *raw)


def key_text(text):
    for c in text:
        QTest.keyClicks(QApplication.focusWidget(), c)


def test_length_angle_typed_at_cursor_commits_exact_point_and_rebases(
    main_window, qapp
):
    w = main_window
    begin(w, qapp)
    key_text("100")
    panel = w.canvas.dynamic_input
    assert panel.active and panel.isVisible() and panel.window() is w
    assert w.canvas.measurement_overlay.isVisible()
    assert not w.canvas.measurement_overlay.geometry().intersects(panel.geometry())
    QTest.keyClick(QApplication.focusWidget(), Qt.Key.Key_Tab)
    assert panel.locks[0] == 100
    key_text("30")
    assert w.current_world_pos == pytest.approx((100 * math.cos(math.pi / 6), 50))
    QTest.keyClick(QApplication.focusWidget(), Qt.Key.Key_Return)
    assert len(w.document.entities) == 1
    line = w.document.entities[0]
    assert line.p2.as_tuple() == pytest.approx((100 * math.cos(math.pi / 6), 50))
    assert not panel.active and not w.command_line.text()
    assert w.document.undo_stack.count() == 1
    # Next segment is free and starts at the new endpoint.
    move(w, qapp, line.p2.x + 3, line.p2.y + 4)
    assert w.canvas.measurement_overlay.measurement.values[0][1] == pytest.approx(5)
    w.cancel_command()
    w.undo()
    assert not w.document.entities
    w.redo()
    assert w.document.entities[0] is line


def test_length_lock_follows_mouse_direction_and_overrides_ortho(main_window, qapp):
    w = main_window
    begin(w, qapp)
    key_text("10")
    QTest.keyClick(QApplication.focusWidget(), Qt.Key.Key_Tab)
    move(w, qapp, 0, 20)
    assert w.current_world_pos == pytest.approx((0, 10))
    key_text("45")
    w.canvas.ortho_enabled = True
    move(w, qapp, 20, 1)
    assert w.current_world_pos == pytest.approx((math.sqrt(50), math.sqrt(50)))
    w._on_world_clicked(20, 0, "", 1)
    assert w.document.entities[0].p2.as_tuple() == pytest.approx(
        (math.sqrt(50), math.sqrt(50))
    )


def test_invalid_field_and_escape_do_not_commit_and_f12_clears_lock(main_window, qapp):
    w = main_window
    begin(w, qapp)
    key_text("-2")
    QTest.keyClick(QApplication.focusWidget(), Qt.Key.Key_Return)
    assert not w.document.entities and w.canvas.dynamic_input.active
    assert "positive" in w.canvas.dynamic_input.hint.text()
    QTest.keyClick(QApplication.focusWidget(), Qt.Key.Key_Escape)
    assert w.current_tool.name == "SELECT" and not w.canvas.dynamic_input.active
    begin(w, qapp)
    key_text("20")
    w.dynamic_action.trigger()
    assert not w.canvas.dynamic_input.active and not w.document.entities
    assert w.current_tool.name == "LINE"


@pytest.mark.parametrize("text,end", [("12,34", (12, 34)), ("@10<90", (0, 10))])
def test_coordinate_input_still_routes_from_viewport(main_window, qapp, text, end):
    w = main_window
    begin(w, qapp)
    key_text(text)
    QTest.keyClick(QApplication.focusWidget(), Qt.Key.Key_Return)
    assert len(w.document.entities) == 1
    assert w.document.entities[0].p2.as_tuple() == pytest.approx(end)


def test_tab_entry_circle_and_rectangle(main_window, qapp):
    w = main_window
    begin(w, qapp, "CIRCLE")
    QTest.keyClick(w.canvas, Qt.Key.Key_Tab)
    assert w.canvas.dynamic_input.active
    key_text("7.25")
    QTest.keyClick(QApplication.focusWidget(), Qt.Key.Key_Space)
    assert w.document.entities[-1].radius == pytest.approx(7.25)
    begin(w, qapp, "RECTANGLE", (-5, -8))
    key_text("12")
    QTest.keyClick(QApplication.focusWidget(), Qt.Key.Key_Tab)
    key_text("6")
    QTest.keyClick(QApplication.focusWidget(), Qt.Key.Key_Return)
    assert w.document.entities[-1].bbox() == pytest.approx((-12, -6, 0, 0))


def test_dynamic_move_uses_same_undo_path(main_window, qapp):
    w = main_window
    e = LineEntity(Point(0, 0), Point(10, 0))
    w.document.entities = [e]
    w.canvas.selected_entities = [e]
    w.set_tool("MOVE")
    # Preselection means the next click selects the base point.
    w._on_world_clicked(0, 0, "", 1)
    move(w, qapp, 5, 0)
    key_text("20")
    QTest.keyClick(QApplication.focusWidget(), Qt.Key.Key_Tab)
    key_text("90")
    QTest.keyClick(QApplication.focusWidget(), Qt.Key.Key_Return)
    assert e.p1.as_tuple() == pytest.approx((0, 20))
    w.undo()
    assert e.p1.as_tuple() == pytest.approx((0, 0))


def test_conversion_preserves_physical_geometry_blocks_and_paper(qapp, tmp_path):
    d = Document()
    line = LineEntity(Point(1000, 2000), Point(2000, 2000))
    d.undo_stack.push(AddEntityCommand(d, line))
    d.undo_stack.push(SetPointCommand(d, line.p2, (2000, 2000), (3000, 2000)))
    child = LineEntity(Point(0, 0), Point(500, 0))
    d.blocks["Child"] = BlockDefinition("Child", [child])
    nested = BlockReferenceEntity("Child", Point(100, 0), scale=2)
    d.blocks["Parent"] = BlockDefinition("Parent", [nested])
    block = BlockReferenceEntity("Parent", Point(1000, 0), scale=3)
    d.entities.append(block)
    d.sync_associative()
    old_block_box = block.bbox()
    layout = d.create_layout("A3", 420, 297)
    vp = layout.viewports[0]
    old_paper = vp.model_to_paper(line.p2).as_tuple()
    old_rect = (vp.x, vp.y, vp.width, vp.height)
    before = document_to_dict(d)
    count = d.undo_stack.count()
    assert convert_units(d, "m") == 0.001
    assert line.p2.as_tuple() == pytest.approx((3, 2))
    assert block.bbox() == pytest.approx([v * 0.001 for v in old_block_box])
    assert block.scale == 3 and nested.scale == 2
    assert d.dimstyles["Standard"]["text_height"] == pytest.approx(0.0025)
    assert vp.model_to_paper(line.p2).as_tuple() == pytest.approx(old_paper)
    assert (vp.x, vp.y, vp.width, vp.height) == old_rect and layout.page_width == 420
    assert d.layers.layers["0"]["lineweight"] == 0.25
    assert d.undo_stack.count() == count + 1
    after = document_to_dict(d)
    p = tmp_path / "converted.pycad"
    save_project(d, p)
    assert document_to_dict(load_project(p)) == after
    d.undo_stack.undo()
    assert document_to_dict(d) == before
    d.undo_stack.redo()
    assert document_to_dict(d) == after
    d.undo_stack.undo()
    d.undo_stack.undo()
    d.undo_stack.undo()
    assert line.p2.as_tuple() == (
        2000,
        2000,
    )  # the earlier endpoint edit still targets this line


def test_conversion_updates_driving_constraints_fixed_geometry_and_solids(qapp):
    from pycad.model3d import create_extrusion

    d = Document()
    line = LineEntity(Point(0, 0), Point(1000, 0))
    arc = ArcEntity(Point(2000, 0), 500, 15, 120)
    d.entities = [line, arc]
    add_constraint(d, make_constraint(d, "fixed", [{"entity": arc.id}]))
    add_constraint(
        d,
        make_constraint(
            d,
            "aligned",
            [{"entity": line.id, "point": "p1"}, {"entity": line.id, "point": "p2"}],
            value=1000,
        ),
    )
    circle = CircleEntity(Point(4000, 0), 300)
    d.entities.append(circle)
    create_extrusion(d, circle, 2500)
    before = document_to_dict(d)
    convert_units(d, "m")
    assert solve(d, check_only=True)["residual"] < 1e-6
    assert d.constraints[0]["fixed"] == pytest.approx([2, 0, 0.5, 15, 120])
    assert d.constraints[1]["value"] == 1
    assert d.extrusions[0]["height"] == 2.5 and d.extrusions[0]["profile"][
        "radius"
    ] == pytest.approx(0.3)
    d.undo_stack.undo()
    assert document_to_dict(d) == before


def test_conversion_xref_reload_retains_new_units(qapp, tmp_path):
    from pycad.dxf_io import export_dxf

    src = Document()
    src.entities = [LineEntity(Point(0, 0), Point(1000, 0))]
    path = tmp_path / "reference.dxf"
    export_dxf(src, path)
    d = Document()
    d.blocks["Ref"] = BlockDefinition("Ref", [src.entities[0].clone()], str(path))
    block = BlockReferenceEntity("Ref", Point(0, 0))
    d.entities = [block]
    d.sync_associative()
    convert_units(d, "m")
    assert d.blocks["Ref"].source_scale == 0.001
    d.reload_xref("Ref")
    assert block.bbox() == pytest.approx((0, 0, 1, 0))
    d = document_from_dict(document_to_dict(d))
    d.reload_xref("Ref")
    assert d.entities[0].bbox() == pytest.approx((0, 0, 1, 0))


@pytest.mark.parametrize("target", ["unitless", "bad"])
def test_invalid_conversion_is_atomic(qapp, target):
    d = Document()
    d.entities = [LineEntity(Point(0, 0), Point(10, 0))]
    before = document_to_dict(d)
    with pytest.raises(ValueError):
        convert_units(d, target)
    assert document_to_dict(d) == before and not d.undo_stack.canUndo()


def test_conversion_out_of_bounds_preflight_does_not_mutate(qapp):
    d = Document()
    d.units = "m"
    d.entities = [LineEntity(Point(0, 0), Point(1e11, 0))]
    before = document_to_dict(d)
    with pytest.raises(ValueError):
        convert_units(d, "mm")
    assert document_to_dict(d) == before


def test_units_manager_explicit_conversion_option(main_window, qapp):
    w = main_window
    w.document.entities = [LineEntity(Point(0, 0), Point(1000, 0))]

    def accept():
        dialog = w.findChild(QDialog, "drawing_units_manager")
        combo = dialog.findChild(QComboBox, "drawing_unit")
        combo.setCurrentIndex(combo.findData("m"))
        field = dialog.findChild(QCheckBox, "convert_geometry")
        assert field.isEnabled()
        field.setChecked(True)
        dialog.accept()

    QTimer.singleShot(0, accept)
    units_dialog(w)
    assert w.document.units == "m" and w.document.entities[0].length() == pytest.approx(
        1
    )
    w.undo()
    assert w.document.units == "mm"


def test_angular_dimension_three_points_and_reflex_round_trip(main_window, tmp_path):
    w = main_window
    w.set_tool("DIMANGULAR")
    for x, y in ((0, 0), (10, 0), (0, -10), (20, 20)):
        w._on_world_clicked(x, y, "", 1)
    e = w.document.entities[-1]
    assert isinstance(e, CurvedDimensionEntity)
    assert e.measurement() == pytest.approx(270)
    style = w.document.dimstyles["Standard"]
    assert dimension_label(e, style) == "270.00°"
    lines, fills, anchor, height = dimension_geometry(e, style)
    assert len(lines) > 100 and len(fills) == 2 and height == 2.5
    path = tmp_path / "angle.pycad"
    save_project(w.document, path)
    loaded = load_project(path)
    assert loaded.entities[-1].measurement() == 270
    w.undo()
    assert not w.document.entities
    w.redo()
    assert w.document.entities[-1] is e


def test_arc_length_association_grip_scale_and_export(main_window, qapp, tmp_path):
    from pycad.plotting import export_pdf
    from pycad.dxf_io import export_dxf, export_warnings
    import ezdxf

    w = main_window
    a = ArcEntity(Point(0, 0), 10, 0, 90)
    w.document.entities = [a]
    w.canvas.zoom = 10
    w.set_tool("DIMARC")
    w._on_world_clicked(10 / math.sqrt(2), 10 / math.sqrt(2), "", 1)
    w._on_world_clicked(15, 15, "", 1)
    e = w.document.entities[-1]
    assert e.source_arc_id == a.id and e.measurement() == pytest.approx(5 * math.pi)
    w.document.undo_stack.push(SetAttrCommand(w.document, a, "radius", 10, 20))
    assert e.measurement() == pytest.approx(10 * math.pi)
    w.undo()
    assert e.measurement() == pytest.approx(5 * math.pi)
    w.document.undo_stack.push(
        SetPointCommand(w.document, e.dim_point, (15, 15), (20, 20))
    )
    assert e.dim_point.as_tuple() == (20, 20)
    w.undo()
    assert e.dim_point.as_tuple() == (15, 15)
    copied = e.clone()
    copied.reflect_across(Point(0, 0), Point(1, 0))
    assert (
        copied.measurement() == pytest.approx(e.measurement())
        and copied.source_arc_id is None
    )
    pdf = tmp_path / "arc.pdf"
    export_pdf(w.document, pdf)
    assert pdf.stat().st_size > 500
    dxf = tmp_path / "arc.dxf"
    export_dxf(w.document, dxf)
    assert len(ezdxf.readfile(dxf).modelspace().query("LINE")) > 20
    assert any("Dimensions become" in s for s in export_warnings(w.document))
    convert_units(w.document, "cm")
    assert e.measurement() == pytest.approx(math.pi / 2)


def test_invalid_curved_dimension_rejected_on_load(qapp):
    d = Document()
    e = CurvedDimensionEntity(Point(0, 0), Point(1, 0), Point(0, 1), Point(2, 2))
    d.entities = [e]
    data = document_to_dict(d)
    data["entities"][0]["data"]["p1"] = {"point": [0, 0]}
    with pytest.raises(ValueError, match="arms"):
        document_from_dict(data)
