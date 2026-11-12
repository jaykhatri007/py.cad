import copy
import math
import pytest
from PyQt6.QtCore import Qt, QPoint, QEvent, QPointF
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QDialog, QComboBox, QSpinBox, QLabel
from pycad.document import Document
from pycad.geometry import Point, LineEntity, CircleEntity, ArcEntity, PolylineEntity
from pycad.measurements import measurement_for
from pycad.units import DEFAULT_SETTINGS, change_units, format_length, format_angle
from pycad.native_io import (
    document_to_dict,
    document_from_dict,
    save_project,
    load_project,
)


def move(w, qapp, x, y):
    view = w.canvas.viewport()
    pos = w.canvas.world_to_screen(x, y)
    event = QMouseEvent(
        QEvent.Type.MouseMove,
        pos,
        QPointF(view.mapToGlobal(pos.toPoint())),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    qapp.sendEvent(view, event)
    qapp.processEvents()


def values(w):
    m = measurement_for(w.current_tool, w.current_world_pos)
    return {label: value for label, value, kind in m.values}


def test_actual_line_readout_snaps_ortho_and_never_mutates(main_window, qapp):
    w = main_window
    w.canvas.snap_enabled = False
    w.set_tool("LINE")
    w._on_world_clicked(0, 0, "", 1)
    before = document_to_dict(w.document)
    move(w, qapp, 3, 4)
    hud = w.canvas.measurement_overlay
    assert hud.isVisible() and hud.window() is w
    assert values(w)["Length"] == pytest.approx(5)
    assert values(w)["Angle"] == pytest.approx(53.130102354)
    assert ("Length", "5.000 mm") in hud.display_values
    assert document_to_dict(w.document) == before and w.document.undo_stack.count() == 0
    w.canvas.ortho_enabled = True
    move(w, qapp, 8, 2)
    assert values(w)["Length"] == pytest.approx(8) and values(w)["Angle"] == 0
    # Object snap must use the picked endpoint rather than the raw pointer or Ortho.
    target = LineEntity(Point(6, 4), Point(20, 4))
    w.document.add_entity(target)
    w.canvas.snap_enabled = True
    move(w, qapp, 6.3, 4.2)
    assert values(w)["Length"] == pytest.approx(math.hypot(6, 4))
    assert w.current_world_pos == (6, 4)
    w.cancel_command()
    assert not hud.isVisible()


def test_polyline_measurement_rebases_after_each_click(main_window, qapp):
    w = main_window
    w.canvas.snap_enabled = False
    w.set_tool("PLINE")
    w._on_world_clicked(0, 0, "", 1)
    w._on_world_clicked(3, 4, "", 1)
    move(w, qapp, 6, 8)
    assert values(w)["Length"] == pytest.approx(5)
    assert values(w)["ΔX"] == pytest.approx(3)


def test_grip_line_shows_new_length_then_disappears_on_release(main_window, qapp):
    w = main_window
    e = LineEntity(Point(0, 0), Point(10, 0))
    w.document.add_entity(e)
    w.canvas.selected_entities = [e]
    w.canvas.snap_enabled = False
    w._on_world_clicked(10, 0, "", 1)
    move(w, qapp, 12, 5)
    assert values(w)["Length"] == pytest.approx(13)
    assert w.canvas.measurement_overlay.isVisible()
    QTest.mouseRelease(
        w.canvas.viewport(),
        Qt.MouseButton.LeftButton,
        pos=w.canvas.world_to_screen(12, 5).toPoint(),
    )
    qapp.processEvents()
    assert not w.canvas.measurement_overlay.isVisible()
    assert e.length() == pytest.approx(13)
    w.undo()
    assert e.length() == pytest.approx(10)


def test_f12_during_constrained_preview_does_not_commit_or_cancel(main_window, qapp):
    from pycad.constraints import make_constraint, add_constraint

    w = main_window
    e = CircleEntity(Point(0, 0), 5)
    w.document.add_entity(e)
    add_constraint(
        w.document, make_constraint(w.document, "radius", [{"entity": e.id}], 5)
    )
    w.canvas.selected_entities = [e]
    w.canvas.snap_enabled = False
    w._on_world_clicked(5, 0, "", 1)
    move(w, qapp, 8, 0)
    count = w.document.undo_stack.count()
    assert e.radius == 8
    QTest.keyClick(w.canvas, Qt.Key.Key_F12)
    assert w.canvas.measurement_overlay.isVisible()
    assert not w.dynamic_action.isChecked()
    assert e.radius == 8 and w.current_tool.grip_entity is e
    QTest.keyClick(w.canvas, Qt.Key.Key_F12)
    assert w.canvas.measurement_overlay.isVisible()
    assert w.document.undo_stack.count() == count
    w.current_tool.finish_drag()
    w.refresh_document_ui()
    assert e.radius == 5  # Constraint rejects the incompatible committed radius.
    assert not w.canvas.measurement_overlay.isVisible()


@pytest.mark.parametrize(
    "command,points,cursor,key,expected",
    [
        ("RECTANGLE", [(0, 0)], (3, 4), "Width", 3),
        ("RECTANGLE", [(0, 0)], (3, 4), "Height", 4),
        ("CIRCLE", [(0, 0)], (3, 4), "Diameter", 10),
        ("ARC", [(0, 0), (10, 0)], (0, 10), "Sweep", 90),
        ("ARC", [(0, 0), (10, 0)], (0, 10), "Arc length", 5 * math.pi),
        ("ELLIPSE", [(0, 0)], (3, 4), "Axis radius", 5),
        ("DIST", [(0, 0)], (-3, -4), "Distance", 5),
        ("SPLINE", [(0, 0)], (3, 4), "Next chord", 5),
    ],
)
def test_shape_specific_measurements(
    main_window, command, points, cursor, key, expected
):
    w = main_window
    w.set_tool(command)
    for x, y in points:
        w._on_world_clicked(x, y, "", 1)
    w._on_mouse_moved(*cursor, "")
    assert values(w)[key] == pytest.approx(expected)


def test_move_stretch_and_rotate_measurements(main_window):
    w = main_window
    e = LineEntity(Point(0, 0), Point(10, 0))
    w.document.add_entity(e)
    w.canvas.selected_entities = [e]
    w.set_tool("MOVE")
    w._on_world_clicked(2, 1, "", 1)
    w._on_mouse_moved(5, 5, "")
    assert values(w)["Movement"] == 5
    w.set_tool("ROTATE")
    w._on_world_clicked(0, 0, "", 1)
    w._on_mouse_moved(0, 10, "")
    assert values(w)["Angle"] == 90
    w.set_tool("STRETCH")
    for p in ((11, 2), (9, -2), (10, 0)):
        w._on_world_clicked(*p, "", 1)
    w._on_mouse_moved(12, 5, "")
    assert values(w)["New length"] == pytest.approx(13)
    assert e.length() == 10  # Preview readout must not edit the drawing.


def test_arc_and_polyline_grip_values(main_window):
    w = main_window
    arc = ArcEntity(Point(0, 0), 10, 0, 45)
    poly = PolylineEntity([Point(30, 0), Point(35, 0), Point(35, 5)])
    w.document.entities = [arc, poly]
    w.canvas.selected_entities = [arc]
    w._on_world_clicked(10 / math.sqrt(2), 10 / math.sqrt(2), "", 1)
    w._on_mouse_moved(0, 10, "")
    assert values(w)["Sweep"] == pytest.approx(90)
    w.cancel_command()
    w.canvas.selected_entities = [poly]
    w._on_world_clicked(35, 0, "", 1)
    w._on_mouse_moved(34, 2, "")
    assert values(w)["Previous edge"] == pytest.approx(math.sqrt(20))
    assert values(w)["Next edge"] == pytest.approx(math.sqrt(10))


def test_command_overlay_collision_edges_leave_and_layout(main_window, qapp):
    w = main_window
    w.set_tool("LINE")
    w._on_world_clicked(0, 0, "", 1)
    view = w.canvas.viewport()
    for position in (QPoint(20, 20), QPoint(view.width() - 6, view.height() - 6)):
        point = w.canvas.screen_to_world(position.x(), position.y())
        move(w, qapp, point.x(), point.y())
        hud = w.canvas.measurement_overlay
        assert hud.isVisible() and view.rect().contains(hud.geometry())
        w.canvas.command_overlay.begin()
        w.command_line.setText("@100<45")
        qapp.processEvents()
        prompt = w.canvas.command_overlay
        assert prompt.isVisible()
        if hud.isVisible():
            assert not hud.geometry().intersects(prompt.geometry())
        w.dismiss_viewport_input(clear=True)
    w.document.current_space = "Layout1"
    w.refresh_measurements()
    assert not hud.isVisible()
    w.document.current_space = "Model"
    w.cancel_command()


@pytest.mark.parametrize(
    "unit,value,expected",
    [
        ("mm", 304.8, "1′ 0″"),
        ("m", 0.6858, "2′ 3″"),
        ("in", 11.9999, "1′ 0″"),
        ("ft", -1.5, "−1′ 6″"),
        ("in", 1.125, "0′ 1 1/8″"),
    ],
)
def test_architectural_readout_converts_real_units(unit, value, expected):
    settings = {**DEFAULT_SETTINGS, "length_format": "architectural"}
    assert format_length(value, unit, settings) == expected


def test_precision_zero_suppression_and_angle_formats():
    s = dict(DEFAULT_SETTINGS)
    assert format_length(-0.000001, "mm", s) == "0.000 mm"
    assert format_length(12.5, "unitless", {**s, "suppress_zeros": True}) == "12.5 u"
    assert format_angle(-90, s) == "270.00°"
    assert format_angle(359.9999, s) == "0.00°"
    assert format_angle(90, {**s, "angle_format": "gradians"}) == "100.00 gon"
    assert (
        format_angle(350, {**s, "angle_format": "radians", "angle_precision": 0})
        == "6 rad"
    )
    assert format_angle(360, s, normalize=False) == "360.00°"


def test_units_persist_undo_without_geometry_changes_and_old_files_load(qapp, tmp_path):
    d = Document()
    d.entities = [LineEntity(Point(0, 0), Point(123.456789, 0))]
    before = document_to_dict(d)
    settings = {
        **DEFAULT_SETTINGS,
        "length_format": "architectural",
        "length_precision": 5,
        "angle_format": "radians",
        "angle_precision": 4,
    }
    change_units(d, "ft", settings)
    assert d.entities[0].p2.x == 123.456789
    path = tmp_path / "units.pycad"
    save_project(d, path)
    restored = load_project(path)
    assert restored.units == "ft" and restored.unit_settings == settings
    d.undo_stack.undo()
    assert document_to_dict(d) == before
    d.undo_stack.redo()
    assert d.units == "ft" and d.unit_settings == settings
    for schema in (1, 2, 3, 4):
        old = copy.deepcopy(before)
        old.pop("unit_settings")
        old["schema_version"] = schema
        assert document_from_dict(old).unit_settings == DEFAULT_SETTINGS


@pytest.mark.parametrize(
    "key,value",
    [
        ("length_precision", True),
        ("length_precision", 9),
        ("angle_precision", -1),
        ("angle_format", "invalid"),
        ("length_format", "invalid"),
        ("suppress_zeros", 1),
    ],
)
def test_invalid_native_unit_settings_are_rejected(qapp, key, value):
    payload = document_to_dict(Document())
    payload["unit_settings"][key] = value
    with pytest.raises(ValueError):
        document_from_dict(payload)


def test_units_manager_cancel_apply_and_undo(main_window, monkeypatch):
    w = main_window
    before = document_to_dict(w.document)

    def interact(dialog):
        assert dialog.objectName() == "drawing_units_manager"
        unit = dialog.findChild(QComboBox, "drawing_unit")
        unit.setCurrentIndex(unit.findData("m"))
        length = dialog.findChild(QComboBox, "length_format")
        length.setCurrentIndex(length.findData("architectural"))
        assert "′" in dialog.findChild(QLabel, "unit_preview").text()
        dialog.findChild(QSpinBox, "angle_precision").setValue(4)
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(QDialog, "exec", interact)
    w.units_dialog()
    assert document_to_dict(w.document) == before

    def accept(dialog):
        interact(dialog)
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(QDialog, "exec", accept)
    w.run_ribbon_command("UNITS")
    assert w.document.units == "m" and w.units_button.text() == "m"
    assert w.document.unit_settings["angle_precision"] == 4
    w.undo()
    assert document_to_dict(w.document) == before and w.units_button.text() == "mm"


def test_unitless_manager_and_dynamic_command(main_window, monkeypatch):
    def interact(dialog):
        length = dialog.findChild(QComboBox, "length_format")
        length.setCurrentIndex(length.findData("architectural"))
        unit = dialog.findChild(QComboBox, "drawing_unit")
        unit.setCurrentIndex(unit.findData("unitless"))
        assert length.currentData() == "decimal"
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(QDialog, "exec", interact)
    w = main_window
    w.units_dialog()
    assert w.document.units == "unitless"
    before = document_to_dict(w.document)
    w.run_ribbon_command("DYNMODE")
    assert not w.dynamic_action.isChecked()
    assert document_to_dict(w.document) == before
