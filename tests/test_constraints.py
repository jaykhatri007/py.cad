import copy
import math
import pytest
from PyQt6.QtCore import Qt
from pycad.document import (
    Document,
    TranslateEntitiesCommand,
    SetPointCommand,
    SetAttrCommand,
    DeleteEntitiesCommand,
)
from pycad.geometry import Point, LineEntity, CircleEntity, ArcEntity
from pycad.constraints import (
    make_constraint,
    add_constraint,
    solve,
    ConstraintChangeCommand,
    geometry_state,
)
from pycad.native_io import (
    document_to_dict,
    document_from_dict,
    save_project,
    load_project,
)
from pycad.dxf_io import export_warnings


def line(x, y, dx, dy):
    return LineEntity(Point(x, y), Point(x + dx, y + dy))


def whole(e):
    return {"entity": e.id}


def anchor(e, key):
    return {"entity": e.id, "point": key}


def apply(d, kind, refs, **kw):
    c = make_constraint(d, kind, refs, **kw)
    assert add_constraint(d, c)
    return c


@pytest.mark.parametrize("kind", ["parallel", "perpendicular", "collinear"])
def test_line_relations_maintained_by_grip_edit_and_undo(qapp, kind):
    d = Document()
    a = line(0, 0, 10, 0)
    b = line(20, 8, 6, 10)
    d.entities = [a, b]
    apply(d, kind, [whole(a), whole(b)])
    before = document_to_dict(d)
    d.undo_stack.push(
        SetPointCommand(d, a.p2, (a.p2.x, a.p2.y), (a.p2.x + 2, a.p2.y + 3))
    )
    assert d.undo_stack.count() == 2
    assert solve(d, check_only=True)["residual"] < 1e-5
    d.undo_stack.undo()
    assert document_to_dict(d) == before
    d.undo_stack.redo()
    assert solve(d, check_only=True)["residual"] < 1e-5


def test_concentric_move_and_fixed_conflict_are_atomic(qapp):
    d = Document()
    a = CircleEntity(Point(0, 0), 5)
    b = CircleEntity(Point(10, 10), 2)
    d.entities = [a, b]
    apply(d, "concentric", [whole(a), whole(b)])
    d.undo_stack.push(TranslateEntitiesCommand(d, [a], 20, -4))
    assert a.center.distance_to(b.center) < 1e-6
    apply(d, "fixed", [whole(a)])
    before = document_to_dict(d)
    index = d.undo_stack.index()
    errors = []
    d.undo_stack.rejected.connect(errors.append)
    d.undo_stack.push(TranslateEntitiesCommand(d, [a], 3, 4))
    assert document_to_dict(d) == before and d.undo_stack.index() == index and errors


def test_coincident_endpoints_across_different_lines(qapp):
    d = Document()
    a = line(0, 0, 10, 0)
    b = line(15, 10, 10, 0)
    d.entities = [a, b]
    apply(d, "coincident", [anchor(a, "p2"), anchor(b, "p1")])
    d.undo_stack.push(TranslateEntitiesCommand(d, [a], 2, 3))
    assert a.p2.distance_to(b.p1) < 1e-6


@pytest.mark.parametrize("kind", ["linear", "aligned"])
def test_driving_point_distance_edit_changes_geometry(qapp, kind):
    d = Document()
    a = line(0, 0, 5, 4)
    d.entities = [a]
    apply(d, kind, [anchor(a, "p1"), anchor(a, "p2")], value=20)
    measure = lambda: (
        abs(a.p2.x - a.p1.x) if kind == "linear" else a.p1.distance_to(a.p2)
    )
    assert measure() == pytest.approx(20, abs=1e-6)
    records = copy.deepcopy(d.constraints)
    records[0]["value"] = 30
    d.undo_stack.push(ConstraintChangeCommand(d, records, "Edit value"))
    assert measure() == pytest.approx(30, abs=1e-6)
    d.undo_stack.undo()
    assert measure() == pytest.approx(20, abs=1e-6)


@pytest.mark.parametrize("kind", ["radius", "diameter"])
def test_radial_driving_constraint_native_roundtrip(qapp, tmp_path, kind):
    d = Document()
    e = ArcEntity(Point(8, 9), 3, 20, 120)
    d.entities = [e]
    apply(d, kind, [whole(e)], value=12)
    assert e.radius == pytest.approx(6 if kind == "diameter" else 12, abs=1e-6)
    p = tmp_path / "constrained.pycad"
    save_project(d, p)
    restored = load_project(p)
    assert document_to_dict(restored) == document_to_dict(d)
    assert solve(restored, check_only=True)["residual"] < 1e-6
    assert any("constraints" in s for s in export_warnings(d))


def test_angular_driving_constraint(qapp):
    d = Document()
    a = line(0, 0, 10, 0)
    b = line(30, 20, 0, 10)
    d.entities = [a, b]
    apply(d, "angular", [whole(a), whole(b)], value=35)
    ux, uy = a.p2.x - a.p1.x, a.p2.y - a.p1.y
    vx, vy = b.p2.x - b.p1.x, b.p2.y - b.p1.y
    angle = math.degrees(math.atan2(abs(ux * vy - uy * vx), ux * vx + uy * vy))
    assert angle == pytest.approx(35, abs=1e-6)


def test_conflicting_radius_and_fixed_rejected_without_history(qapp):
    d = Document()
    e = CircleEntity(Point(0, 0), 5)
    d.entities = [e]
    apply(d, "fixed", [whole(e)])
    before = document_to_dict(d)
    assert not add_constraint(d, make_constraint(d, "radius", [whole(e)], value=10))
    assert document_to_dict(d) == before and d.undo_stack.count() == 1


def test_macro_solver_runs_once_and_rolls_back_every_child(qapp):
    d = Document()
    a = line(0, 0, 10, 0)
    b = line(10, 0, 10, 0)
    d.entities = [a, b]
    apply(d, "coincident", [anchor(a, "p2"), anchor(b, "p1")])
    before = document_to_dict(d)
    d.undo_stack.beginMacro("Move together")
    d.undo_stack.push(TranslateEntitiesCommand(d, [a], 0, 4))
    d.undo_stack.push(TranslateEntitiesCommand(d, [b], 0, 4))
    d.undo_stack.endMacro()
    assert a.p2.y == pytest.approx(4) and b.p1.y == pytest.approx(4)
    d.undo_stack.undo()
    assert document_to_dict(d) == before
    apply(d, "fixed", [whole(a)])
    before = document_to_dict(d)
    index = d.undo_stack.index()
    d.undo_stack.beginMacro("Conflicting batch")
    d.undo_stack.push(TranslateEntitiesCommand(d, [a], 0, 4))
    d.undo_stack.push(SetAttrCommand(d, b, "color", b.color, "#FF0000"))
    d.undo_stack.endMacro()
    assert document_to_dict(d) == before and d.undo_stack.index() == index


def test_delete_prunes_constraints_and_undo_restores_them(qapp):
    d = Document()
    a = line(0, 0, 10, 0)
    b = line(0, 10, 10, 0)
    d.entities = [a, b]
    apply(d, "parallel", [whole(a), whole(b)])
    before = document_to_dict(d)
    d.undo_stack.push(DeleteEntitiesCommand(d, [b]))
    assert not d.constraints
    d.undo_stack.undo()
    assert document_to_dict(d) == before
    d.undo_stack.redo()
    assert not d.constraints


def test_native_rejects_dangling_constraints_and_unsatisfied_geometry(qapp):
    d = Document()
    a = CircleEntity(Point(0, 0), 5)
    d.entities = [a]
    apply(d, "radius", [whole(a)], value=5)
    payload = document_to_dict(d)
    payload["constraints"][0]["refs"][0]["entity"] = "missing"
    with pytest.raises(ValueError):
        document_from_dict(payload)
    payload = document_to_dict(d)
    payload["entities"][0]["data"]["radius"] = 100
    with pytest.raises(ValueError, match="Conflicting"):
        document_from_dict(payload)


def test_command_input_creates_driving_constraint(main_window):
    w = main_window
    e = CircleEntity(Point(0, 0), 5)
    w.document.entities = [e]
    w.run_ribbon_command("DCRADIUS")
    w.current_tool.on_click(5, 0, "", Qt.MouseButton.LeftButton.value)
    assert w.current_tool.await_value
    w.command_line.setText("12")
    w._on_command_entered()
    assert e.radius == pytest.approx(12, abs=1e-6) and len(w.document.constraints) == 1
    assert w.current_tool.name == "SELECT"
    assert w.ribbon.findChild(
        __import__("PyQt6.QtWidgets", fromlist=["QToolButton"]).QToolButton,
        "ribbon_gcparallel",
    ).isEnabled()


def test_locked_neighbor_rejects_constraint_change(qapp):
    d = Document()
    a = line(0, 0, 10, 0)
    b = line(0, 10, 10, 0)
    d.entities = [a, b]
    apply(d, "parallel", [whole(a), whole(b)])
    d.layers.add_layer("Locked")
    b.layer = "Locked"
    d.layers.layers["Locked"]["locked"] = True
    before = geometry_state(d)
    d.undo_stack.beginMacro("Rotate both endpoints")
    d.undo_stack.push(SetPointCommand(d, a.p1, a.p1.as_tuple(), (2, 3)))
    d.undo_stack.push(SetPointCommand(d, a.p2, a.p2.as_tuple(), (12, 8)))
    d.undo_stack.endMacro()
    assert geometry_state(d) == before


def test_grip_target_preserves_unchanged_coordinate(qapp):
    d = Document()
    a = line(0, 0, 10, 0)
    b = line(0, 10, 10, 0)
    d.entities = [a, b]
    apply(d, "parallel", [whole(a), whole(b)])
    d.layers.add_layer("Locked")
    b.layer = "Locked"
    d.layers.layers["Locked"]["locked"] = True
    original_b = geometry_state(d)[b.id]
    d.undo_stack.push(SetPointCommand(d, a.p2, a.p2.as_tuple(), (10, 5)))
    assert a.p2.as_tuple() == (10, 5)
    assert geometry_state(d)[b.id] == original_b
    assert abs(a.p2.y - a.p1.y) < 1e-6


def test_large_geometry_index_does_not_expand_billions_of_cells(qapp):
    d = Document()
    e = line(-1e9, -1e9, 2e9, 2e9)
    d.entities = [e]
    assert d.query_entities((-1, -1, 1, 1)) == [e]
    assert d.query_entities((-2e9, -2e9, 2e9, 2e9)) == [e]
    assert len(d.spatial_index._cells) <= 4096


def test_uncommitted_drag_cannot_write_invalid_native_file(
    main_window, tmp_path, monkeypatch
):
    w = main_window
    e = CircleEntity(Point(0, 0), 5)
    w.document.entities = [e]
    apply(w.document, "radius", [whole(e)], value=5)
    w.canvas.selected_entities = [e]
    w.set_tool("SELECT")
    tool = w.current_tool
    tool.on_click(5, 0, "", 1)
    tool.on_move(12, 0, "")
    assert e.radius == 12
    with pytest.raises(ValueError):
        save_project(w.document, tmp_path / "bad.pycad")
    w._do_autosave()
    import pycad.appsettings as settings
    from pathlib import Path

    assert not Path(settings.RECOVERY_PATH).exists()
    tool.finish_drag()
    assert e.radius == 5 and len(w.document.constraints) == 1
    save_project(w.document, tmp_path / "good.pycad")


def test_constraint_manager_and_visibility_command(main_window, monkeypatch):
    from PyQt6.QtWidgets import QDialog

    w = main_window
    e = CircleEntity(Point(0, 0), 5)
    w.document.entities = [e]
    apply(w.document, "radius", [whole(e)], value=5)
    w.run_ribbon_command("CONSTRAINTBAR")
    assert not w.document.constraint_settings["show"]
    w.document.undo_stack.undo()
    assert w.document.constraint_settings["show"]
    monkeypatch.setattr(QDialog, "exec", lambda self: 0)
    w.run_ribbon_command("CONSTRAINTSETTINGS")
    assert "Command failed" not in w.command_history.toPlainText()
    w.canvas.selected_entities = [e]
    w.run_ribbon_command("DELCONSTRAINT")
    assert w.document.constraints == []
    w.document.undo_stack.undo()
    assert len(w.document.constraints) == 1


def test_undo_redo_cancels_uncommitted_grip_preview(main_window):
    w = main_window
    e = CircleEntity(Point(0, 0), 5)
    w.document.entities = [e]
    apply(w.document, "radius", [whole(e)], value=5)
    w.canvas.selected_entities = [e]
    w.set_tool("SELECT")
    w.current_tool.on_click(5, 0, "", 1)
    w.current_tool.on_move(12, 0, "")
    w.undo()
    assert not w.document.constraints and e.radius == 5
    w.current_tool.finish_drag()
    w.redo()
    assert len(w.document.constraints) == 1 and e.radius == 5
    assert solve(w.document, check_only=True)["residual"] < 1e-6
