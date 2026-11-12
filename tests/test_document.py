"""Tests for pycad.document - the undo stack and associative sync."""
import pytest
from pycad.geometry import Point, LineEntity, CircleEntity, DimensionEntity, HatchEntity, PolylineEntity
from pycad.document import Document, AddEntityCommand, DeleteEntitiesCommand, TranslateEntitiesCommand


def test_add_and_undo():
    doc = Document()
    line = LineEntity(Point(0, 0), Point(10, 0))
    doc.undo_stack.push(AddEntityCommand(doc, line, "add"))
    assert len(doc.entities) == 1
    doc.undo_stack.undo()
    assert len(doc.entities) == 0
    doc.undo_stack.redo()
    assert len(doc.entities) == 1


def test_delete_command_reversible():
    doc = Document()
    line = LineEntity(Point(0, 0), Point(10, 0))
    doc.add_entity(line)
    doc.undo_stack.push(DeleteEntitiesCommand(doc, [line], "delete"))
    assert len(doc.entities) == 0
    doc.undo_stack.undo()
    assert len(doc.entities) == 1


def test_find_by_id():
    doc = Document()
    line = LineEntity(Point(0, 0), Point(10, 0))
    doc.add_entity(line)
    assert doc.find_by_id(line.id) is line
    assert doc.find_by_id("nonexistent") is None


def test_associative_dimension_follows_source_line():
    doc = Document()
    line = LineEntity(Point(0, 0), Point(10, 0))
    doc.add_entity(line)
    dim = DimensionEntity(Point(0, 0), Point(10, 0), Point(5, 3), source_line_id=line.id)
    doc.add_entity(dim)
    doc.undo_stack.push(TranslateEntitiesCommand(doc, [line], 20, 0, "move"))
    assert dim.p1.x == pytest.approx(20)
    assert dim.p2.x == pytest.approx(30)
    doc.undo_stack.undo()
    assert dim.p1.x == pytest.approx(0)


def test_associative_hatch_follows_source_circle():
    doc = Document()
    circle = CircleEntity(Point(0, 0), 5)
    doc.add_entity(circle)
    from pycad import geom_ops
    hatch = HatchEntity(geom_ops.circle_to_polygon(circle.center, circle.radius),
                         source_entity_id=circle.id)
    doc.add_entity(hatch)
    doc.undo_stack.push(TranslateEntitiesCommand(doc, [circle], 15, 0, "move"))
    assert all(p.x > 5 for p in hatch.boundary)  # shifted well clear of the original 0-centered circle


def test_dimension_without_source_does_not_sync():
    doc = Document()
    line = LineEntity(Point(0, 0), Point(10, 0))
    doc.add_entity(line)
    dim = DimensionEntity(Point(0, 0), Point(10, 0), Point(5, 3))  # no source_line_id
    doc.add_entity(dim)
    doc.undo_stack.push(TranslateEntitiesCommand(doc, [line], 20, 0, "move"))
    assert dim.p1.x == pytest.approx(0)  # unaffected - not linked


def test_layer_manager_visibility():
    doc = Document()
    doc.layers.add_layer("hidden_layer")
    doc.layers.set_visible("hidden_layer", False)
    line = LineEntity(Point(0, 0), Point(10, 0), layer="hidden_layer")
    doc.add_entity(line)
    assert line not in doc.visible_entities()
