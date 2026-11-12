"""v12 acceptance checks for precision, native integrity, and undoable tables."""
import pytest
from pycad import dxf_io, native_io
from pycad.canvas import CadCanvas, Snap
from pycad.document import Document
from pycad.geometry import CircleEntity, LineEntity, Point
from pycad.tools import AreaTool, DistanceTool


def test_layer_and_layout_tables_are_undoable():
    doc = Document()
    doc.edit_layer("add", "Walls", "#FF0000")
    assert "Walls" in doc.layers.layers
    doc.undo_stack.undo()
    assert "Walls" not in doc.layers.layers
    doc.undo_stack.redo()
    doc.edit_layer("rename", "Walls", "Structural")
    assert "Structural" in doc.layers.layers
    doc.undo_stack.undo()
    assert "Walls" in doc.layers.layers

    doc.create_layout("Sheet 1")
    assert "Sheet 1" in doc.layouts
    doc.undo_stack.undo()
    assert "Sheet 1" not in doc.layouts
    doc.undo_stack.redo()
    assert "Sheet 1" in doc.layouts


def test_native_duplicate_keys_and_backup(tmp_path):
    doc = Document()
    path = tmp_path / "drawing.pycad"
    native_io.save_project(doc, path)
    doc.edit_layer("add", "A", "#FFFFFF")
    native_io.save_project(doc, path)
    backup = path.with_name(path.name + ".bak")
    assert backup.exists()
    assert native_io.load_project(backup).layers.names() == ["0"]
    path.write_text('{"format":"PyCAD","format":"PyCAD"}')
    with pytest.raises(ValueError, match="Duplicate JSON key"):
        native_io.load_project(path)


def test_import_embeds_small_source_and_native_roundtrip(tmp_path):
    import ezdxf

    source = tmp_path / "source.dxf"
    drawing = ezdxf.new("R2018")
    drawing.modelspace().add_line((0, 0), (10, 0))
    drawing.saveas(source)
    document = dxf_io.import_dxf(source)
    assert document.source_archive["filename"] == source.name
    assert document.source_archive["sha256"]
    project = tmp_path / "source.pycad"
    native_io.save_project(document, project)
    loaded = native_io.load_project(project)
    assert loaded.source_archive["filename"] == source.name
    assert loaded.source_archive["sha256"] == document.source_archive["sha256"]


def test_precision_snaps_intersection_quadrant_and_nearest(qapp):
    doc = Document()
    doc.add_entity(LineEntity(Point(0, 0), Point(10, 0)))
    doc.add_entity(LineEntity(Point(5, -5), Point(5, 5)))
    doc.add_entity(CircleEntity(Point(20, 0), 5))
    canvas = CadCanvas(doc)
    canvas.resize(800, 600)
    canvas.show()
    qapp.processEvents()

    point, kind = canvas.find_snap_point(canvas.world_to_screen(5, 0))
    assert kind == Snap.INTERSECTION and point.as_tuple() == (5, 0)
    point, kind = canvas.find_snap_point(canvas.world_to_screen(20, 5))
    assert kind == Snap.QUADRANT and point.x == pytest.approx(20)
    point, kind = canvas.find_snap_point(canvas.world_to_screen(2.0, 0.4))
    assert kind in (Snap.NEAREST, Snap.ENDPOINT, Snap.MIDPOINT)


def test_distance_and_area_commands(main_window):
    window = main_window
    distance = DistanceTool(window)
    distance.on_click(0, 0, "", 1)
    distance.on_click(3, 4, "", 1)
    assert "DIST = 5.000 mm" in window.command_history.toPlainText()

    area = AreaTool(window)
    for point in ((0, 0), (10, 0), (10, 10), (0, 10)):
        area.on_click(*point, "", 1)
    area.on_key(16777220)  # Qt.Key_Return
    assert "AREA = 100.000000" in window.command_history.toPlainText()
