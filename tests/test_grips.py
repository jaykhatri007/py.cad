"""Tests for grip editing - dragging individual endpoints/vertices via SelectTool."""
import pytest
from pycad.geometry import Point, LineEntity, CircleEntity, ArcEntity, PolylineEntity
from pycad.document import AddEntityCommand


def test_line_endpoint_grip_points():
    line = LineEntity(Point(0, 0), Point(10, 0))
    grips = dict(line.grip_points())
    assert set(grips.keys()) == {"p1", "p2"}
    assert grips["p1"] is line.p1
    assert grips["p2"] is line.p2


def test_circle_grip_points():
    circle = CircleEntity(Point(5, 5), 3)
    grips = dict(circle.grip_points())
    assert grips["center"] is circle.center
    assert grips["radius"].x == pytest.approx(8)


def test_arc_grip_points():
    arc = ArcEntity(Point(0, 0), 10, 0, 90)
    grips = dict(arc.grip_points())
    assert grips["center"] is arc.center
    assert grips["start"].x == pytest.approx(10)
    assert grips["end"].y == pytest.approx(10)


def test_polyline_grip_points_are_live_vertices():
    poly = PolylineEntity([Point(0, 0), Point(10, 0), Point(10, 10)])
    grips = dict(poly.grip_points())
    assert grips["pt1"] is poly.points[1]


def test_drag_line_endpoint_via_select_tool(main_window):
    w = main_window
    line = LineEntity(Point(0, 0), Point(10, 0))
    w.document.undo_stack.push(AddEntityCommand(w.document, line, "t"))
    w.canvas.selected_entities = [line]
    w.set_tool("SELECT")
    st = w.current_tool
    st.on_click(10, 0, "", 1)
    assert st.grip_entity is line and st.grip_kind == "p2"
    st.on_move(20, 5, "")
    assert line.p2.x == 20 and line.p2.y == 5
    assert line.p1.x == 0  # untouched
    st.finish_drag()
    w.undo()
    assert line.p2.x == 10 and line.p2.y == 0


def test_drag_circle_radius_grip(main_window):
    w = main_window
    circle = CircleEntity(Point(0, 0), 5)
    w.document.undo_stack.push(AddEntityCommand(w.document, circle, "t"))
    w.canvas.selected_entities = [circle]
    w.set_tool("SELECT")
    st = w.current_tool
    st.on_click(5, 0, "", 1)
    assert st.grip_kind == "radius"
    st.on_move(12, 0, "")
    assert circle.radius == pytest.approx(12)
    st.finish_drag()
    w.undo()
    assert circle.radius == pytest.approx(5)


def test_drag_arc_end_angle_grip_preserves_radius(main_window):
    w = main_window
    arc = ArcEntity(Point(0, 0), 10, 0, 90)
    w.document.undo_stack.push(AddEntityCommand(w.document, arc, "t"))
    w.canvas.selected_entities = [arc]
    w.set_tool("SELECT")
    st = w.current_tool
    end_pt = arc.endpoints()[1]
    st.on_click(end_pt.x, end_pt.y, "", 1)
    assert st.grip_kind == "end"
    st.on_move(-10, 0.001, "")
    assert arc.radius == pytest.approx(10)
    assert arc.end_angle == pytest.approx(180, abs=0.1)
    st.finish_drag()
    w.undo()
    assert arc.end_angle == pytest.approx(90)


def test_drag_polyline_vertex_grip(main_window):
    w = main_window
    poly = PolylineEntity([Point(0, 0), Point(10, 0), Point(10, 10)])
    w.document.undo_stack.push(AddEntityCommand(w.document, poly, "t"))
    w.canvas.selected_entities = [poly]
    w.set_tool("SELECT")
    st = w.current_tool
    st.on_click(10, 0, "", 1)
    drag=w.current_tool
    assert drag.name == 'POLYGRIP' and drag.index == 1
    drag.on_move(15, 5, "")
    assert poly.points[1] == Point(10,0)  # uncommitted preview is isolated
    assert drag.candidate.points[1] == Point(15,5)
    drag.finish_drag()
    assert w.document.find_by_id(poly.id).points[1] == Point(15,5)
    w.undo()
    assert w.document.find_by_id(poly.id).points[1] == Point(10,0)


def test_grip_not_active_with_multiple_selected(main_window):
    """Grips only appear when exactly one entity is selected."""
    w = main_window
    line1 = LineEntity(Point(0, 0), Point(10, 0))
    line2 = LineEntity(Point(0, 20), Point(10, 20))
    w.document.undo_stack.push(AddEntityCommand(w.document, line1, "t"))
    w.document.undo_stack.push(AddEntityCommand(w.document, line2, "t"))
    w.canvas.selected_entities = [line1, line2]
    w.set_tool("SELECT")
    st = w.current_tool
    grip = st._pick_grip(Point(10, 0))
    assert grip is None
