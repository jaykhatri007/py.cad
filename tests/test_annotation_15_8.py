"""Drafting, persistence, recovery and interchange acceptance for v15.8."""

import copy
import math

import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from pycad.geometry import Point, LineEntity, CircleEntity, PointEntity
from pycad.annotation_links import line_angle_geometry, line_angle_sector
from pycad.curved_dimensions import CurvedDimensionEntity
from pycad.ordinate_dimensions import OrdinateDimensionEntity
from pycad.document import (
    Document,
    SetAttrCommand,
    DeleteEntitiesCommand,
    SetPointCommand,
)
from pycad.native_io import (
    document_to_dict,
    document_from_dict,
    save_project,
    load_project,
)
from pycad.dimstyles import dimension_label, dimension_geometry
from pycad.unit_conversion import convert_units
from pycad.ribbon_actions import selection_document
from pycad import geom_ops


def linked_angle(doc, location=Point(20, 5)):
    a = LineEntity(Point(0, 0), Point(10, 0))
    b = LineEntity(Point(0, 0), Point(10, 10))
    center, p1, p2, ids, signs = line_angle_sector(a, b, location)
    dim = CurvedDimensionEntity(
        center,
        p1,
        p2,
        Point(location.x, location.y),
        source_line_ids=ids,
        line_directions=signs,
    )
    doc.entities = [a, b, dim]
    doc.sync_associative()
    return a, b, dim


@pytest.mark.parametrize(
    "angle,expected", [(30, 60), (100, 120), (220, 60), (320, 120)]
)
def test_angle_sector_selects_acute_and_obtuse_quadrants(qapp, angle, expected):
    first = LineEntity(Point(-10, 0), Point(10, 0))
    second = LineEntity(Point(0, 0), Point(5, 5 * math.sqrt(3)))
    r = math.radians(angle)
    loc = Point(20 * math.cos(r), 20 * math.sin(r))
    c, p1, p2, ids, signs = line_angle_sector(first, second, loc)
    dim = CurvedDimensionEntity(
        c, p1, p2, loc, source_line_ids=ids, line_directions=signs
    )
    assert dim.measurement() == pytest.approx(expected)


@pytest.mark.parametrize("length,offset", [(1e-8, 0), (20, 1e9)])
def test_supporting_line_intersection_is_scale_relative(qapp, length, offset):
    a = LineEntity(Point(offset, offset), Point(offset + length, offset))
    b = LineEntity(
        Point(offset, offset + length), Point(offset + length, offset + 2 * length)
    )
    c, _, _ = line_angle_geometry(a, b)
    assert c.as_tuple() == pytest.approx((offset - length, offset))


@pytest.mark.parametrize("end", [(10, 0), (0, 0), (10, 1e-11)])
def test_parallel_degenerate_and_nearly_parallel_lines_rejected(qapp, end):
    a = LineEntity(Point(0, 0), Point(10, 0))
    b = LineEntity(Point(0, 0), Point(*end))
    with pytest.raises(ValueError):
        line_angle_geometry(a, b)


def test_two_line_workflow_edit_undo_and_reopen(main_window, tmp_path):
    w = main_window
    a = LineEntity(Point(0, 0), Point(10, 0))
    b = LineEntity(Point(0, 0), Point(10, 10))
    w.document.entities = [a, b]
    w.canvas.zoom = 10
    w.set_tool("DIMANGULAR")
    for x, y in [(8, 0), (5, 5), (20, 5)]:
        w._on_world_clicked(x, y, "", 1)
    dim = w.document.entities[-1]
    assert dim.source_line_ids == [a.id, b.id]
    assert dim.measurement() == pytest.approx(45)
    w.document.undo_stack.push(SetAttrCommand(w.document, b, "p2", b.p2, Point(0, 10)))
    assert dim.measurement() == pytest.approx(90)
    w.undo()
    assert dim.measurement() == pytest.approx(45)
    w.redo()
    path = tmp_path / "angles.pycad"
    save_project(w.document, path)
    loaded = load_project(path)
    assert loaded.entities[-1].association_status(loaded) == "Associated with two lines"
    assert loaded.entities[-1].measurement() == pytest.approx(90)
    loaded.undo_stack.push(
        SetAttrCommand(loaded, loaded.entities[1], "p2", Point(0, 10), Point(10, 10))
    )
    assert loaded.entities[-1].measurement() == pytest.approx(45)


def test_preselected_lines_and_coordinate_placement(main_window):
    w = main_window
    a, b, _ = linked_angle(w.document)
    w.document.entities = [a, b]
    w.canvas.selected_entities = [a, b]
    w.set_tool("DIMANGULAR")
    assert "sector" in w.current_tool.status_prompt()
    w.current_tool.on_text_input("0,20")
    assert w.document.entities[-1].measurement() == pytest.approx(135)


def test_explicit_points_does_not_link_over_line_geometry(main_window):
    w = main_window
    w.document.entities = [LineEntity(Point(0, 0), Point(10, 0))]
    w.set_tool("DIMANGULAR")
    for text in ("Points", "0,0", "10,0", "0,10", "20,20"):
        w.current_tool.on_text_input(text)
    assert w.document.entities[-1].source_line_ids == []
    assert w.document.entities[-1].measurement() == pytest.approx(90)


def test_source_delete_and_parallel_fallback_recover_after_undo(qapp, tmp_path):
    doc = Document()
    a, b, dim = linked_angle(doc)
    doc.undo_stack.push(SetAttrCommand(doc, b, "p2", b.p2, Point(10, 0)))
    assert dim.measurement() == pytest.approx(45)
    assert "parallel" in dim.association_status(doc)
    save_project(doc, tmp_path / "parallel.pycad")
    assert load_project(tmp_path / "parallel.pycad").entities[
        -1
    ].measurement() == pytest.approx(45)
    doc.undo_stack.undo()
    assert dim.association_status(doc) == "Associated with two lines"
    doc.undo_stack.push(DeleteEntitiesCommand(doc, [b]))
    assert "Source missing" in dim.association_status(doc)
    assert dim.measurement() == pytest.approx(45)
    doc.undo_stack.undo()
    doc.undo_stack.push(SetAttrCommand(doc, b, "p2", b.p2, Point(0, 10)))
    assert dim.measurement() == pytest.approx(90)


def test_copy_selection_and_unit_conversion_links(qapp):
    doc = Document()
    a, b, dim = linked_angle(doc)
    assert dim.clone().source_line_ids == []
    solo = selection_document(doc, [dim])
    assert solo.entities[0].source_line_ids == []
    paired = selection_document(doc, [a, b, dim])
    assert paired.entities[-1].source_line_ids == dim.source_line_ids
    convert_units(doc, "m")
    assert dim.measurement() == pytest.approx(45)
    assert dim.dim_point.x == pytest.approx(0.02)
    doc.undo_stack.undo()
    assert dim.dim_point.x == pytest.approx(20)


@pytest.mark.parametrize(
    "axis,feature,expected", [("X", (-25, 10), -25), ("Y", (10, -35), -35)]
)
def test_ordinate_typed_signed_coordinate_and_datum(
    main_window, axis, feature, expected
):
    w = main_window
    w.set_tool("DIMORDINATE")
    for text in (
        axis,
        "Origin",
        "100,100",
        f"{feature[0] + 100},{feature[1] + 100}",
        "@20,20",
    ):
        w.current_tool.on_text_input(text)
    e = w.document.entities[-1]
    assert isinstance(e, OrdinateDimensionEntity)
    assert e.measurement() == expected
    assert e.p1.as_tuple() == (100, 100)
    assert e.source_entity_id is None
    assert dimension_label(e, w.document.dimstyles["Standard"]) == f"{expected:.2f}"
    w.undo()
    assert not w.document.entities
    w.redo()
    assert w.document.entities[-1] is e


@pytest.mark.parametrize("location,axis", [((30, 80), "x"), ((80, 30), "y")])
def test_ordinate_automatic_axis_from_leader_direction(main_window, location, axis):
    w = main_window
    w.set_tool("DIMORDINATE")
    w.current_tool.on_text_input("30,30")
    w._on_world_clicked(*location, "", 1)
    assert w.document.entities[-1].dim_style == "ordinate_" + axis


@pytest.mark.parametrize(
    "entity,point,anchor",
    [
        (LineEntity(Point(20, 10), Point(50, 10)), (50, 10), "p2"),
        (CircleEntity(Point(50, 10), 10), (50, 10), "center"),
        (PointEntity(Point(50, 10)), (50, 10), "point"),
    ],
)
def test_ordinate_source_link_edit_and_reopen(
    main_window, tmp_path, entity, point, anchor
):
    w = main_window
    entity = copy.deepcopy(entity)
    w.document.entities = [entity]
    w.canvas.zoom = 10
    w.set_tool("DIMORDINATE")
    w.current_tool.on_text_input("X")
    w._on_world_clicked(*point, "", 1)
    w._on_world_clicked(55, 40, "", 1)
    dim = w.document.entities[-1]
    assert dim.source_entity_id == entity.id and dim.source_anchor == anchor
    p = getattr(entity, anchor)
    w.document.undo_stack.push(
        SetAttrCommand(w.document, entity, anchor, p, Point(75, 10))
    )
    assert dim.measurement() == 75
    w.undo()
    assert dim.measurement() == 50
    path = tmp_path / "ordinate.pycad"
    save_project(w.document, path)
    loaded = load_project(path)
    assert loaded.entities[-1].source_entity_id == entity.id
    loaded.undo_stack.push(DeleteEntitiesCommand(loaded, [loaded.entities[0]]))
    assert "retained" in loaded.entities[-1].association_status(loaded)


def test_ordinate_grip_plot_dxf_scale_and_properties(main_window, tmp_path):
    from pycad.plotting import export_pdf
    from pycad.dxf_io import export_dxf
    import ezdxf
    import fitz

    w = main_window
    e = OrdinateDimensionEntity(Point(0, 0), Point(25, 15), Point(35, 40))
    w.document.entities = [e]
    w.document.undo_stack.push(
        SetPointCommand(w.document, e.dim_point, (35, 40), (40, 50))
    )
    assert e.grip_points() == [("dim_point", e.dim_point)]
    w.undo()
    assert e.dim_point.as_tuple() == (35, 40)
    style = w.document.dimstyles["Standard"]
    lines, fills, _, _ = dimension_geometry(e, style)
    assert len(lines) == 2 and fills == []
    assert geom_ops.distance_to_entity(Point(25, 30), e) == 0
    w.canvas.selected_entities = [e]
    w.properties_panel.refresh()
    assert "Independent coordinate" in w.properties_panel.info.text()
    assert "25.00" in w.properties_panel.info.text()
    pdf, dxf = tmp_path / "ordinate.pdf", tmp_path / "ordinate.dxf"
    export_pdf(w.document, pdf)
    with fitz.open(pdf) as plotted:
        assert "25.00" in plotted[0].get_text()
    export_dxf(w.document, dxf)
    exchange = ezdxf.readfile(dxf)
    assert any(t.dxf.text == "25.00" for t in exchange.modelspace().query("TEXT"))
    assert len(exchange.modelspace().query("LINE")) == 2
    convert_units(w.document, "m")
    assert e.measurement() == pytest.approx(0.025)
    w.undo()
    assert e.measurement() == 25


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_line_ids", ["x"]),
        ("line_directions", [True, 1]),
        ("source_line_ids", ["x", "x"]),
        ("source_line_ids", "xy"),
    ],
)
def test_malformed_angular_links_rejected(qapp, field, value):
    doc = Document()
    linked_angle(doc)
    payload = document_to_dict(doc)
    payload["entities"][-1]["data"][field] = value
    with pytest.raises(ValueError):
        document_from_dict(payload)


def test_invalid_source_type_and_ordinate_anchor_rejected(qapp):
    doc = Document()
    a, b, angle = linked_angle(doc)
    circle = CircleEntity(Point(0, 0), 10)
    circle.id = a.id
    doc.entities = [circle, b, angle]
    with pytest.raises(ValueError, match="source must"):
        document_from_dict(document_to_dict(doc))
    ordinate = OrdinateDimensionEntity(
        Point(0, 0),
        Point(0, 0),
        Point(10, 10),
        source_entity_id=circle.id,
        source_anchor="p2",
    )
    doc.entities = [circle, ordinate]
    with pytest.raises(ValueError, match="support this anchor"):
        document_from_dict(document_to_dict(doc))


def test_schema_six_curved_annotations_migrate(qapp):
    doc = Document()
    angle = CurvedDimensionEntity(
        Point(0, 0), Point(10, 0), Point(0, 10), Point(20, 20)
    )
    doc.entities = [angle]
    payload = document_to_dict(doc)
    payload["schema_version"] = 6
    for key in ("source_line_ids", "line_directions"):
        del payload["entities"][0]["data"][key]
    reopened = document_from_dict(payload)
    assert reopened.entities[0].source_line_ids == []
    assert reopened.entities[0].measurement() == 90


def test_viewport_ordinate_command_enter_and_escape(main_window, qapp):
    from pycad.ribbon_catalog import TOOLS

    w = main_window
    assert TOOLS["DIMORDINATE"].status != "planned"
    w.canvas.viewport().setFocus()
    QTest.keyClicks(w.canvas.viewport(), "DIMORDINATE")
    QTest.keyClick(w.canvas.viewport(), Qt.Key.Key_Space)
    qapp.processEvents()
    assert w.current_tool.name == "DIMORDINATE"
    QTest.keyClick(w.canvas.viewport(), Qt.Key.Key_Escape)
    qapp.processEvents()
    assert not w.document.entities


def test_cursor_preview_reads_selected_sector_and_coordinate(main_window):
    from pycad.measurements import measurement_for

    w = main_window
    a, b, _ = linked_angle(w.document)
    w.canvas.selected_entities = [a, b]
    w.set_tool("DIMANGULAR")
    result = measurement_for(w.current_tool, (0, 20))
    assert result.values[0] == ("Angle", 135.0, "sweep")
    w.canvas.selected_entities = []
    w.set_tool("DIMORDINATE")
    for text in ("X", "Origin", "100,100", "75,90"):
        w.current_tool.on_text_input(text)
    result = measurement_for(w.current_tool, (80, 120))
    assert result.values[0] == ("X coordinate", -25.0, "length")
    assert result.values[1:] == [
        ("Datum X", 100.0, "length"),
        ("Datum Y", 100.0, "length"),
    ]


def test_two_line_plot_and_dxf_share_angle_label(qapp, tmp_path):
    from pycad.plotting import export_pdf
    from pycad.dxf_io import export_dxf, export_warnings
    import ezdxf
    import fitz

    doc = Document()
    _, _, dim = linked_angle(doc)
    export_pdf(doc, tmp_path / "angle.pdf")
    with fitz.open(tmp_path / "angle.pdf") as pdf:
        assert "45.00" in pdf[0].get_text()
    export_dxf(doc, tmp_path / "angle.dxf")
    exchange = ezdxf.readfile(tmp_path / "angle.dxf")
    assert any(t.dxf.text == "45.00°" for t in exchange.modelspace().query("TEXT"))
    assert any("Dimensions become" in warning for warning in export_warnings(doc))
