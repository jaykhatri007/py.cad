"""Tests for pycad.geom_ops.flood_fill_boundary - the pick-a-point hatch
boundary detector - and its integration into HatchTool."""
import pytest
from pycad.geometry import Point, LineEntity, CircleEntity, ArcEntity
from pycad.document import AddEntityCommand
from pycad import geom_ops


def _polygon_area(points):
    s = 0.0
    n = len(points)
    for i in range(n):
        p1, p2 = points[i], points[(i + 1) % n]
        s += p1.x * p2.y - p2.x * p1.y
    return abs(s) / 2


def test_rectangle_from_four_separate_lines():
    walls = [
        LineEntity(Point(0, 0), Point(20, 0)),
        LineEntity(Point(20, 0), Point(20, 10)),
        LineEntity(Point(20, 10), Point(0, 10)),
        LineEntity(Point(0, 10), Point(0, 0)),
    ]
    boundary = geom_ops.flood_fill_boundary(walls, Point(10, 5), bbox=(-5, -5, 25, 15), resolution=200)
    assert boundary is not None
    assert len(boundary) == 4
    assert _polygon_area(boundary) == pytest.approx(200, rel=0.05)


def test_gap_in_boundary_is_not_enclosed():
    walls_with_gap = [
        LineEntity(Point(0, 0), Point(20, 0)),
        LineEntity(Point(20, 0), Point(20, 10)),
        LineEntity(Point(20, 10), Point(10, 10)),  # missing segment back to (0,10)-(0,0)
        LineEntity(Point(0, 10), Point(0, 0)),
    ]
    result = geom_ops.flood_fill_boundary(walls_with_gap, Point(10, 5), bbox=(-5, -5, 25, 15), resolution=200)
    assert result is None


def test_click_outside_bbox_returns_none():
    result = geom_ops.flood_fill_boundary([LineEntity(Point(0, 0), Point(10, 0))],
                                           Point(1000, 1000), bbox=(-5, -5, 25, 15))
    assert result is None


def test_triangle_boundary_reasonable_vertex_count_and_area():
    tri = [
        LineEntity(Point(0, 0), Point(10, 0)),
        LineEntity(Point(10, 0), Point(5, 10)),
        LineEntity(Point(5, 10), Point(0, 0)),
    ]
    boundary = geom_ops.flood_fill_boundary(tri, Point(5, 3), bbox=(-5, -5, 15, 15), resolution=200)
    assert boundary is not None
    assert len(boundary) <= 10  # simplification should collapse this to ~3-4, not ~200
    assert _polygon_area(boundary) == pytest.approx(50, rel=0.1)


def test_circle_boundary_reasonable_vertex_count_and_area():
    import math
    boundary = geom_ops.flood_fill_boundary([CircleEntity(Point(0, 0), 10)], Point(0, 0),
                                             bbox=(-15, -15, 15, 15), resolution=200)
    assert boundary is not None
    assert len(boundary) < 100
    assert _polygon_area(boundary) == pytest.approx(math.pi * 100, rel=0.1)


def test_mixed_lines_and_arc_boundary(main_window):
    """The scenario a single-closed-entity hatch tool couldn't handle at
    all: a rounded-corner shape made of independent Line + Arc entities."""
    w = main_window
    shapes = [
        LineEntity(Point(0, 0), Point(20, 0)),
        ArcEntity(Point(20, 10), 10, -90, 0),
        LineEntity(Point(30, 10), Point(30, 20)),
        LineEntity(Point(30, 20), Point(0, 20)),
        LineEntity(Point(0, 20), Point(0, 0)),
    ]
    for s in shapes:
        w.document.undo_stack.push(AddEntityCommand(w.document, s, "t"))
    w.canvas.zoom_extents()
    w.set_tool("HATCH",hatch_configured=True)
    w.current_tool.on_click(15, 10, "", 1)
    assert w.current_tool.boundary_points is not None
    w.current_tool.on_text_input("")
    hatches = [e for e in w.document.entities if e.kind == "HATCH"]
    assert len(hatches) == 1
    assert hatches[0].source_entity_id is None  # not a single-shape association


def test_hatch_tool_fallback_to_single_shape_stays_associative(main_window):
    w = main_window
    circle = CircleEntity(Point(0, 0), 5)
    w.document.undo_stack.push(AddEntityCommand(w.document, circle, "t"))
    w.canvas.zoom_extents()
    w.set_tool("HATCH",hatch_configured=True)
    w.current_tool.on_click(5, 0, "", 1)  # click directly on the circle boundary
    assert w.current_tool.source_entity is circle
    w.current_tool.on_text_input("solid")
    hatch = [e for e in w.document.entities if e.kind == "HATCH"][0]
    assert hatch.source_entity_id == circle.id
