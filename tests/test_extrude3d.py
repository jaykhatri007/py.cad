"""Tests for pycad.extrude3d. Skipped automatically if cadquery isn't installed."""
import pytest
from pycad.geometry import Point, CircleEntity, RectangleEntity, PolylineEntity

cadquery = pytest.importorskip("cadquery")
from pycad import extrude3d


def test_is_extrudable():
    assert extrude3d.is_extrudable(CircleEntity(Point(0, 0), 5))
    assert extrude3d.is_extrudable(RectangleEntity(Point(0, 0), Point(10, 10)))
    assert not extrude3d.is_extrudable(PolylineEntity([Point(0, 0), Point(10, 0)], closed=False))


def test_extrude_circle_volume(tmp_path):
    circle = CircleEntity(Point(0, 0), 5)
    solid = extrude3d.extrude_and_export(circle, 10, str(tmp_path / "c.step"))
    import math
    assert solid.val().Volume() == pytest.approx(math.pi * 25 * 10, rel=1e-3)


def test_extrude_rectangle_volume(tmp_path):
    rect = RectangleEntity(Point(0, 0), Point(4, 5))
    solid = extrude3d.extrude_and_export(rect, 3, str(tmp_path / "r.step"))
    assert solid.val().Volume() == pytest.approx(4 * 5 * 3, rel=1e-6)


def test_extrude_open_polyline_raises():
    open_pl = PolylineEntity([Point(0, 0), Point(10, 0)], closed=False)
    with pytest.raises(extrude3d.ExtrudeError):
        extrude3d.extrude_to_solid(open_pl, 5)


def test_extrude_zero_height_raises():
    circle = CircleEntity(Point(0, 0), 5)
    with pytest.raises(extrude3d.ExtrudeError):
        extrude3d.extrude_to_solid(circle, 0)
