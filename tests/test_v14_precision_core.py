"""v14 acceptance checks for shared tolerance and spatial picking caches."""

import pytest

from pycad.document import Document, TranslateEntitiesCommand
from pycad.geometry import LineEntity, Point, RayEntity, XLineEntity
from pycad.tolerance import EPSILON, bounds_overlap, clamp, is_close, is_zero


def test_shared_tolerance_helpers_cover_boundary_cases():
    assert is_zero(EPSILON)
    assert is_close(10.0, 10.0 + EPSILON / 2)
    assert clamp(-2.0) == 0.0
    assert clamp(2.0) == 1.0
    assert bounds_overlap((0, 0, 1, 1), (1 + EPSILON / 2, 0, 2, 1))
    assert not bounds_overlap((0, 0, 1, 1), (1 + 2 * EPSILON, 0, 2, 1))


def test_spatial_index_returns_only_overlapping_finite_entities():
    document = Document()
    near = LineEntity(Point(0, 0), Point(10, 0))
    far = LineEntity(Point(100, 100), Point(110, 100))
    document.add_entity(near)
    document.add_entity(far)

    assert document.query_entities((-1, -1, 11, 1)) == [near]
    assert document.spatial_index._dirty is False


def test_spatial_index_rebuilds_after_undoable_transform():
    document = Document()
    line = LineEntity(Point(0, 0), Point(10, 0))
    document.add_entity(line)
    assert document.query_entities((-1, -1, 11, 1)) == [line]

    document.undo_stack.push(TranslateEntitiesCommand(document, [line], 50, 0, "move"))
    assert document.query_entities((-1, -1, 11, 1)) == []
    assert document.query_entities((49, -1, 61, 1)) == [line]

    document.undo_stack.undo()
    assert document.query_entities((-1, -1, 11, 1)) == [line]


def test_query_filters_layers_and_keeps_unbounded_construction_lines():
    document = Document()
    document.layers.add_layer("Hidden")
    document.layers.add_layer("Locked")
    document.layers.set_visible("Hidden", False)
    document.layers.set_locked("Locked", True)
    hidden = LineEntity(Point(0, 0), Point(5, 0), layer="Hidden")
    locked = LineEntity(Point(0, 5), Point(5, 5), layer="Locked")
    ray = RayEntity(Point(0, 0), Point(1, 0))
    xline = XLineEntity(Point(0, 0), Point(0, 1))
    for entity in (hidden, locked, ray, xline):
        document.add_entity(entity)

    candidates = document.query_entities((1000, -1, 1001, 1), editable_only=True)
    assert ray in candidates and xline in candidates
    assert hidden not in candidates and locked not in candidates
