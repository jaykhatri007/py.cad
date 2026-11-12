"""Tests for pycad.geom_ops - the pure-geometry helper functions."""
import pytest
from pycad.geometry import Point
from pycad import geom_ops


def test_line_line_intersection():
    p = geom_ops.line_line_intersection(Point(0, 0), Point(10, 0), Point(5, -5), Point(5, 5))
    assert p.x == pytest.approx(5) and p.y == pytest.approx(0)


def test_line_line_intersection_parallel_returns_none():
    p = geom_ops.line_line_intersection(Point(0, 0), Point(10, 0), Point(0, 1), Point(10, 1))
    assert p is None


def test_circle_line_intersections_tangent_and_secant():
    # secant: horizontal line through a circle of radius 5 at y=0 -> two points
    pts = geom_ops.circle_line_intersections(Point(0, 0), 5, Point(-10, 0), Point(10, 0))
    assert len(pts) == 2
    xs = sorted(p.x for p in pts)
    assert xs[0] == pytest.approx(-5) and xs[1] == pytest.approx(5)


def test_circle_circle_intersections():
    pts = geom_ops.circle_circle_intersections(Point(0, 0), 5, Point(8, 0), 5)
    assert len(pts) == 2
    for p in pts:
        assert p.distance_to(Point(0, 0)) == pytest.approx(5, abs=1e-6)
        assert p.distance_to(Point(8, 0)) == pytest.approx(5, abs=1e-6)


def test_bracket_range_finds_containing_interval():
    low, high = geom_ops.bracket_range(0.0, 1.0, 0.8, [0.3, 0.5])
    assert (low, high) == (0.5, 1.0)


def test_bracket_range_no_cuts_returns_full_range():
    low, high = geom_ops.bracket_range(0.0, 1.0, 0.5, [])
    assert (low, high) == (0.0, 1.0)


def test_angle_in_arc_range_wraparound():
    assert geom_ops.angle_in_arc_range(350, 340, 20) is True
    assert geom_ops.angle_in_arc_range(30, 340, 20) is False


def test_normalize_angle_diff():
    assert geom_ops.normalize_angle_diff(350, 10) == pytest.approx(20)
    assert geom_ops.normalize_angle_diff(10, 350) == pytest.approx(-20)


def test_point_line_projection():
    proj = geom_ops.point_line_projection(Point(5, 5), Point(0, 0), Point(10, 0))
    assert proj.x == pytest.approx(5) and proj.y == pytest.approx(0)


def test_offset_line_points_picks_requested_side():
    p1, p2 = geom_ops.offset_line_points(Point(0, 0), Point(10, 0), 3, Point(0, 5))
    assert p1.y == pytest.approx(3)
    p1b, p2b = geom_ops.offset_line_points(Point(0, 0), Point(10, 0), 3, Point(0, -5))
    assert p1b.y == pytest.approx(-3)


def test_compute_hatch_lines_fills_a_square():
    boundary = [Point(0, 0), Point(10, 0), Point(10, 10), Point(0, 10)]
    lines = geom_ops.compute_hatch_lines(boundary, 0, 2)
    assert len(lines) > 0
    for a, b in lines:
        assert 0 <= a.x <= 10 and 0 <= a.y <= 10


def test_point_in_polygon_basic_square():
    square = [Point(0, 0), Point(10, 0), Point(10, 10), Point(0, 10)]
    assert geom_ops.point_in_polygon(Point(5, 5), square) is True
    assert geom_ops.point_in_polygon(Point(15, 5), square) is False
    assert geom_ops.point_in_polygon(Point(-1, 5), square) is False
