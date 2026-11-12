"""v13 geometry expansion checks for real CAD entity coverage."""
import pytest
from PyQt6.QtCore import Qt

from pycad import dxf_io, native_io
from pycad.canvas import CadCanvas
from pycad.document import Document
from pycad.geometry import EllipseEntity, Point, PointEntity, RayEntity, XLineEntity
from pycad.tools import EllipseTool, PointTool, RayTool, XLineTool


def geometry_document():
    document = Document()
    document.add_entity(PointEntity(Point(1, 2)))
    document.add_entity(EllipseEntity(Point(5, 5), 4, 2, 30))
    document.add_entity(RayEntity(Point(0, 0), Point(1, 0)))
    document.add_entity(XLineEntity(Point(0, 0), Point(0, 1)))
    return document


def test_new_entities_native_roundtrip(tmp_path):
    document = geometry_document()
    path = tmp_path / "geometry.pycad"
    native_io.save_project(document, path)
    loaded = native_io.load_project(path)
    assert [entity.kind for entity in loaded.entities] == ["POINT", "ELLIPSE", "RAY", "XLINE"]
    ellipse = loaded.entities[1]
    assert ellipse.major_radius == pytest.approx(4)
    assert ellipse.minor_radius == pytest.approx(2)
    assert ellipse.rotation == pytest.approx(30)


def test_new_entities_dxf_roundtrip(tmp_path):
    document = geometry_document()
    path = tmp_path / "geometry.dxf"
    dxf_io.export_dxf(document, path)
    loaded = dxf_io.import_dxf(path)
    assert sorted(entity.kind for entity in loaded.entities) == ["ELLIPSE", "POINT", "RAY", "XLINE"]


def test_ellipse_bbox_and_sampling():
    ellipse = EllipseEntity(Point(10, 20), 8, 3, 45)
    samples = ellipse.sample_points(128)
    x0, y0, x1, y1 = ellipse.bbox()
    assert len(samples) == 128
    assert min(point.x for point in samples) >= x0 - 1e-9
    assert max(point.x for point in samples) <= x1 + 1e-9
    assert min(point.y for point in samples) >= y0 - 1e-9
    assert max(point.y for point in samples) <= y1 + 1e-9


def test_new_entities_are_snap_candidates(qapp):
    document = geometry_document()
    canvas = CadCanvas(document)
    canvas.resize(800, 600)
    canvas.show()
    qapp.processEvents()
    point, kind = canvas.find_snap_point(canvas.world_to_screen(1, 2))
    assert kind in ("Endpoint", "Center")
    assert point.x == pytest.approx(1)
    assert point.y == pytest.approx(2)


def test_new_drawing_tools_create_undoable_entities(main_window):
    window = main_window
    point_tool = PointTool(window)
    point_tool.on_click(1, 2, "", Qt.MouseButton.LeftButton.value)
    ellipse_tool = EllipseTool(window)
    ellipse_tool.on_click(5, 5, "", Qt.MouseButton.LeftButton.value)
    ellipse_tool.on_click(9, 5, "", Qt.MouseButton.LeftButton.value)
    ellipse_tool.on_click(5, 7, "", Qt.MouseButton.LeftButton.value)
    ray_tool = RayTool(window)
    ray_tool.on_click(0, 0, "", Qt.MouseButton.LeftButton.value)
    ray_tool.on_click(1, 0, "", Qt.MouseButton.LeftButton.value)
    xline_tool = XLineTool(window)
    xline_tool.on_click(0, 0, "", Qt.MouseButton.LeftButton.value)
    xline_tool.on_click(0, 1, "", Qt.MouseButton.LeftButton.value)
    assert [entity.kind for entity in window.document.entities[-4:]] == ["POINT", "ELLIPSE", "RAY", "XLINE"]
    for _ in range(4):
        window.document.undo_stack.undo()
    assert not window.document.entities
