"""Tests for pycad.geometry - entity math, cloning, transforms."""
import math
import pytest
from pycad.geometry import Point, LineEntity, CircleEntity, ArcEntity, PolylineEntity, RectangleEntity


def test_point_distance():
    assert Point(0, 0).distance_to(Point(3, 4)) == pytest.approx(5.0)


def test_line_length_and_bbox():
    line = LineEntity(Point(0, 0), Point(3, 4))
    assert line.length() == pytest.approx(5.0)
    assert line.bbox() == (0, 0, 3, 4)


def test_line_translate():
    line = LineEntity(Point(0, 0), Point(3, 4))
    line.translate(10, -10)
    assert (line.p1.x, line.p1.y) == (10, -10)
    assert (line.p2.x, line.p2.y) == (13, -6)


def test_line_clone_is_independent():
    line = LineEntity(Point(0, 0), Point(3, 4))
    clone = line.clone()
    clone.translate(1, 1)
    assert line.p1.x == 0  # original untouched
    assert clone.id != line.id


def test_circle_bbox():
    c = CircleEntity(Point(5, 5), 2)
    assert c.bbox() == (3, 3, 7, 7)


def test_rectangle_is_closed_polyline():
    r = RectangleEntity(Point(0, 0), Point(10, 5))
    assert r.closed is True
    assert len(r.points) == 4


def test_arc_endpoints():
    arc = ArcEntity(Point(0, 0), 10, 0, 90)
    p1, p2 = arc.endpoints()
    assert p1.x == pytest.approx(10) and p1.y == pytest.approx(0)
    assert p2.x == pytest.approx(0, abs=1e-9) and p2.y == pytest.approx(10)


def test_line_reflect_across_vertical_axis():
    line = LineEntity(Point(0, 0), Point(10, 0))
    line.reflect_across(Point(0, -5), Point(0, 5))  # mirror across x=0
    assert line.p2.x == pytest.approx(-10)


def test_arc_rotate_around_shifts_angles():
    arc = ArcEntity(Point(0, 0), 5, 0, 90)
    arc.rotate_around(Point(0, 0), 45)
    assert arc.start_angle == pytest.approx(45)
    assert arc.end_angle == pytest.approx(135)


def test_polyline_midpoints_open_vs_closed():
    pts = [Point(0, 0), Point(10, 0), Point(10, 10)]
    open_pl = PolylineEntity(list(pts), closed=False)
    closed_pl = PolylineEntity(list(pts), closed=True)
    assert len(open_pl.midpoints()) == 2
    assert len(closed_pl.midpoints()) == 3  # closing segment adds one more


def test_line_scale_from():
    line = LineEntity(Point(0, 0), Point(10, 0))
    line.scale_from(Point(0, 0), 2)
    assert line.p2.x == pytest.approx(20)


def test_circle_scale_from_scales_radius():
    c = CircleEntity(Point(10, 0), 5)
    c.scale_from(Point(0, 0), 2)
    assert c.center.x == pytest.approx(20)
    assert c.radius == pytest.approx(10)


def test_spline_passes_through_control_points():
    from pycad.geometry import SplineEntity
    pts = [Point(0, 0), Point(5, 10), Point(10, 0), Point(15, 10)]
    spline = SplineEntity(list(pts))
    samples = spline._catmull_rom_samples(segments_per_span=10)
    for p in pts:
        nearest = min(samples, key=lambda s: s.distance_to(p))
        assert nearest.distance_to(p) < 1e-9


def test_spline_clone_and_translate():
    from pycad.geometry import SplineEntity
    spline = SplineEntity([Point(0, 0), Point(5, 5)])
    clone = spline.clone()
    clone.translate(1, 1)
    assert spline.points[0].x == 0  # original untouched
    assert clone.points[0].x == 1


def test_block_reference_clip_boundary_filters_entities():
    from pycad.geometry import BlockDefinition, BlockReferenceEntity
    entities = [LineEntity(Point(0, 0), Point(2, 0)), LineEntity(Point(50, 50), Point(52, 50))]
    bd = BlockDefinition("Test", entities)
    ref = BlockReferenceEntity("Test", Point(0, 0))
    ref.clip_boundary = [Point(-5, -5), Point(5, -5), Point(5, 5), Point(-5, 5)]
    ref.rebuild(bd)
    assert len(ref.resolved_entities) == 1


def test_block_reference_clip_boundary_moves_with_translate():
    from pycad.geometry import BlockDefinition, BlockReferenceEntity
    bd = BlockDefinition("Test", [LineEntity(Point(0, 0), Point(2, 0))])
    ref = BlockReferenceEntity("Test", Point(0, 0))
    ref.clip_boundary = [Point(-5, -5), Point(5, -5), Point(5, 5), Point(-5, 5)]
    ref.rebuild(bd)
    ref.translate(100, 0)
    assert ref.clip_boundary[0].x == pytest.approx(95)


def test_block_reference_without_clip_boundary_unaffected():
    from pycad.geometry import BlockDefinition, BlockReferenceEntity
    entities = [LineEntity(Point(0, 0), Point(2, 0)), LineEntity(Point(50, 50), Point(52, 50))]
    bd = BlockDefinition("Test", entities)
    ref = BlockReferenceEntity("Test", Point(0, 0))
    ref.rebuild(bd)
    assert len(ref.resolved_entities) == 2
