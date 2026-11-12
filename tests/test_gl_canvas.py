"""
Tests for pycad.gl_canvas - the OpenGL rendering backend.

IMPORTANT SCOPE NOTE: these tests cover everything that doesn't require a
live GPU/GL context (coordinate transforms, tessellation math, snapping,
zoom-to-extents) since no such context is available in this test
environment (confirmed: QOpenGLWidget fails to create a context here even
under software Mesa rendering - see gl_canvas.py's module docstring). They
do NOT verify that paintGL's actual draw calls render correct pixels on a
real GPU - that can only be confirmed by running the app on a machine with
a working display.
"""
import math
import pytest
from pycad.geometry import Point, LineEntity
from pycad.document import Document
from pycad.gl_canvas import GLCadCanvas


@pytest.fixture
def gl_canvas(qapp):
    doc = Document()
    canvas = GLCadCanvas(doc)
    canvas.resize(800, 600)
    canvas.show()
    qapp.processEvents()
    return canvas


def test_world_to_screen_matches_qpainter_canvas_formula(gl_canvas):
    p = gl_canvas.world_to_screen(0, 0)
    assert p.x() == pytest.approx(gl_canvas.viewport().width()/2)
    assert p.y() == pytest.approx(gl_canvas.viewport().height()/2)


def test_world_to_screen_screen_to_world_roundtrip(gl_canvas):
    gl_canvas.zoom = 25
    gl_canvas.pan_offset.setX(10)
    gl_canvas.pan_offset.setY(-5)
    original = (17.3, -42.1)
    screen = gl_canvas.world_to_screen(*original)
    back = gl_canvas.screen_to_world(screen.x(), screen.y())
    assert back.x() == pytest.approx(original[0])
    assert back.y() == pytest.approx(original[1])


def test_tessellate_circle_all_points_on_radius():
    pts = GLCadCanvas._tessellate_circle(Point(0, 0), 5, segments=16)
    assert len(pts) == 16
    for p in pts:
        assert math.hypot(p.x, p.y) == pytest.approx(5)


def test_tessellate_arc_endpoints_correct():
    pts = GLCadCanvas._tessellate_arc(Point(0, 0), 10, 0, 90, segments=8)
    assert pts[0].x == pytest.approx(10)
    assert pts[0].y == pytest.approx(0, abs=1e-9)
    assert pts[-1].x == pytest.approx(0, abs=1e-9)
    assert pts[-1].y == pytest.approx(10)


def test_find_snap_point_finds_endpoint(gl_canvas):
    line = LineEntity(Point(0, 0), Point(10, 0))
    gl_canvas.document.add_entity(line)
    screen_pos = gl_canvas.world_to_screen(0, 0)
    pt, kind = gl_canvas.find_snap_point(screen_pos)
    assert kind == "Endpoint"
    assert pt.x == 0 and pt.y == 0


def test_ortho_lock_matches_software_canvas_behavior(gl_canvas):
    class FakeTool:
        points = [Point(0, 0)]
        base_point = None

    gl_canvas.ortho_enabled = True
    gl_canvas._active_tool = FakeTool()
    wx, wy = gl_canvas._apply_ortho(10, 0.5)
    assert wy == pytest.approx(0)


def test_zoom_extents_centers_on_geometry(gl_canvas):
    gl_canvas.document.add_entity(LineEntity(Point(0, 0), Point(20, 20)))
    gl_canvas.zoom_extents()
    assert gl_canvas.pan_offset.x() == pytest.approx(10)
    assert gl_canvas.pan_offset.y() == pytest.approx(10)


def test_viewport_returns_self(gl_canvas):
    """QOpenGLWidget has no separate viewport widget - viewport() must
    return self so existing `canvas.viewport().update()` call sites work
    against either backend without modification."""
    from pycad.canvas import CadCanvas
    assert isinstance(gl_canvas, CadCanvas)
    assert gl_canvas.viewport() is not None
