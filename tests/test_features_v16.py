"""Cross-feature acceptance tests for all nine v16 areas."""

import copy
import json
import math
import pytest
from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtWidgets import QMessageBox
from pycad.document import (
    Document,
    AddEntityCommand,
    TranslateEntitiesCommand,
    SetAttrCommand,
)
from pycad.geometry import (
    Point,
    LineEntity,
    CircleEntity,
    PolylineEntity,
    RectangleEntity,
    SplineEntity,
    TextEntity,
    HatchEntity,
    BlockDefinition,
    BlockReferenceEntity,
)
from pycad.native_io import (
    document_to_dict,
    document_from_dict,
    save_project,
    load_project,
)
from pycad import smart_blocks, precision, architecture, sheets, automation, layers_plus


def test_attributes_schedules_dxf_native_and_undo(qapp, tmp_path):
    from pycad import dxf_io

    d = Document()
    d.blocks["Door"] = BlockDefinition("Door", [LineEntity(Point(0, 0), Point(100, 0))])
    smart_blocks.define_attribute(d, "Door", "ID", "D01", (0, 10), 5)
    smart_blocks.define_attribute(d, "Door", "FINISH", "Paint", (0, 20), 5)
    a = BlockReferenceEntity("Door", Point(10, 10), rotation=90)
    b = BlockReferenceEntity("Door", Point(20, 20))
    d.undo_stack.push(AddEntityCommand(d, a))
    d.undo_stack.push(AddEntityCommand(d, b))
    smart_blocks.set_attributes(d, a, {"ID": "D02", "FINISH": "Wood"})
    assert a.resolved_entities[1].text == "D02"
    assert a.resolved_entities[1].position == Point(0, 10)
    rows = smart_blocks.export_schedule(d, str(tmp_path / "schedule.csv"))
    assert {r["ID"] for r in rows} == {"D01", "D02"}
    d.undo_stack.undo()
    assert a.resolved_entities[1].text == "D01"
    assert smart_blocks.schedule_rows(d, group=True)[0]["Quantity"] == 2
    d.undo_stack.redo()
    save_project(d, tmp_path / "d.pycad")
    loaded = load_project(tmp_path / "d.pycad")
    assert loaded.entities[0].attributes == a.attributes
    dxf_io.export_dxf(d, str(tmp_path / "d.dxf"))
    imported = dxf_io.import_dxf(str(tmp_path / "d.dxf"))
    assert imported.blocks["Door"].attributes[0]["tag"] == "ID"
    assert imported.entities[0].attributes["ID"] == "D02"


def test_true_arc_polyline_area_mirror_dxf_offset(qapp, tmp_path):
    from pycad import dxf_io
    from pycad.geometry_ui import offset_curved

    p = PolylineEntity([Point(-5, 0), Point(5, 0)], True, bulges=[1, 1])
    length, area = precision.polyline_measure(p)
    assert length == pytest.approx(10 * math.pi)
    assert area == pytest.approx(25 * math.pi)
    assert p.bbox() == pytest.approx((-5, -5, 5, 5))
    out = offset_curved(p, 1, Point(10, 0))
    assert precision.polyline_measure(out)[1] == pytest.approx(36 * math.pi)
    p.reflect_across(Point(0, 0), Point(1, 0))
    assert p.bulges == [-1, -1]
    d = Document()
    d.add_entity(p)
    dxf_io.export_dxf(d, str(tmp_path / "p.dxf"))
    loaded = dxf_io.import_dxf(str(tmp_path / "p.dxf"))
    assert loaded.entities[0].bulges == [-1, -1]
    assert precision.polyline_measure(loaded.entities[0])[1] == pytest.approx(
        25 * math.pi
    )


def test_rational_bspline_preserved_in_dxf(qapp, tmp_path):
    from pycad import dxf_io

    s = SplineEntity(
        [Point(1, 0), Point(1, 1), Point(0, 1)],
        degree=2,
        curve_mode="nurbs",
        weights=[1, math.sqrt(0.5), 1],
        knots=[0, 0, 0, 1, 1, 1],
    )
    p = precision.spline_curve(s).point(0.5)
    assert (p.x, p.y) == pytest.approx((math.sqrt(0.5), math.sqrt(0.5)))
    d = Document()
    d.add_entity(s)
    dxf_io.export_dxf(d, str(tmp_path / "s.dxf"))
    loaded = dxf_io.import_dxf(str(tmp_path / "s.dxf")).entities[0]
    assert loaded.curve_mode == "nurbs"
    assert loaded.weights == pytest.approx(s.weights)
    p = precision.spline_curve(loaded).point(0.5)
    assert p.x == pytest.approx(math.sqrt(0.5))


def test_hatch_hole_roundtrip_and_crossing_rejection(qapp, tmp_path):
    from pycad import dxf_io

    outer = [Point(0, 0), Point(10, 0), Point(10, 10), Point(0, 10)]
    hole = [Point(3, 3), Point(7, 3), Point(7, 7), Point(3, 7)]
    h = HatchEntity(outer, pattern="SOLID", holes=[hole])
    d = Document()
    d.add_entity(h)
    save_project(d, tmp_path / "h.pycad")
    assert len(load_project(tmp_path / "h.pycad").entities[0].holes) == 1
    dxf_io.export_dxf(d, str(tmp_path / "h.dxf"))
    assert len(dxf_io.import_dxf(str(tmp_path / "h.dxf")).entities[0].holes) == 1
    with pytest.raises(ValueError):
        precision.validate_holes(outer, [[Point(-1, 3), Point(2, 3), Point(2, 5)]])


def test_sheets_multiple_page_sizes_title_and_physical_scale(qapp, tmp_path):
    import fitz
    from pycad.plotting import publish_pdf

    d = Document()
    d.units = "m"
    d.add_entity(RectangleEntity(Point(0, 0), Point(10, 5)))
    a = d.create_layout("Plan", 297, 210)
    b = d.create_layout("Detail", 210, 297)
    sheets.title_block(d, "Plan", "House", "Floor plan", "A101", "B", "Designer")
    sheets.set_viewport_scale(d, a.viewports[0], 100)
    assert a.viewports[0].scale == 10
    sheets.save_preset(d, "Print", dict(sheets.DEFAULT_PRESET))
    save_project(d, tmp_path / "sheets.pycad")
    loaded = load_project(tmp_path / "sheets.pycad")
    assert loaded.extensions["sheets"]["Plan"]["number"] == "A101"
    publish_pdf(d, tmp_path / "all.pdf", ["Plan", "Detail"])
    pdf = fitz.open(tmp_path / "all.pdf")
    assert len(pdf) == 2
    assert pdf[0].rect.width == pytest.approx(297 / 25.4 * 72, abs=1)
    assert pdf[1].rect.height == pytest.approx(297 / 25.4 * 72, abs=1)
    assert "Floor plan" in pdf[0].get_text()


def test_layer_states_filters_overrides_native_and_undo(qapp):
    d = Document()
    d.edit_layer("add", "Walls", "#abcdef")
    layers_plus.save_state(d, "Plan")
    d.edit_layer("visible", "Walls", False)
    layers_plus.restore_state(d, "Plan")
    assert d.layers.layers["Walls"]["visible"]
    d.undo_stack.undo()
    assert not d.layers.layers["Walls"]["visible"]
    assert layers_plus.matches(d.layers.layers["Walls"], "Hidden")
    assert not layers_plus.matches(d.layers.layers["Walls"], "Visible")
    from pycad.feature_data import edit_table

    edit_table(
        d,
        "viewport_overrides",
        "Plan::0",
        {"Walls": {"visible": False, "color": "#123456"}},
    )
    e = document_from_dict(document_to_dict(d))
    assert layers_plus.overrides(e, "Plan", 0)["Walls"]["color"] == "#123456"


def test_rich_text_wrap_linked_leader_fit_and_undo(qapp):
    from pycad.mleaders import MultileaderEntity
    from pycad.feature_data import edit_table
    from pycad.dimstyles import dimension_geometry, DEFAULT_STYLE
    from pycad.geometry import DimensionEntity
    from pycad.annotations_plus import validate_html

    d = Document()
    t = TextEntity(
        Point(0, 0),
        "Bold plain",
        height=2,
        wrap_width=8,
        rich_html="<p><b>Bold</b> plain</p>",
    )
    d.add_entity(t)
    line = LineEntity(Point(1, 2), Point(4, 5))
    d.add_entity(line)
    leader = MultileaderEntity(Point(20, 20), "Linked", [[Point(0, 0), Point(10, 10)]])
    d.add_entity(leader)
    edit_table(d, "leader_links", leader.id, [{"source": line.id, "anchor": "p2"}])
    d.undo_stack.push(TranslateEntitiesCommand(d, [line], 10, 10))
    assert leader.leaders[0][0] == Point(14, 15)
    d.undo_stack.undo()
    assert leader.leaders[0][0] == Point(4, 5)
    loaded = document_from_dict(document_to_dict(d))
    assert loaded.entities[0].rich_html == t.rich_html
    assert t.bbox()[2] <= 8.1
    _, _, anchor, _ = dimension_geometry(
        DimensionEntity(Point(0, 0), Point(1, 0), Point(0, 2)), DEFAULT_STYLE
    )
    assert anchor.x > 1
    with pytest.raises(ValueError):
        validate_html('<img src="https://example.com/x">')


def test_architecture_hosts_rooms_finishes_native_and_undo(qapp, tmp_path):
    d = Document()
    wall = architecture.create_wall(d, Point(0, 0), Point(6000, 0))
    door = architecture.create_opening(d, wall, 1500, 900, identifier="D10")
    window = architecture.create_opening(
        d, wall, 4000, 1200, 1200, "window", "W10", 900
    )
    assert len(d.blocks[wall.block_name].entities) == 3
    boundary = RectangleEntity(Point(0, 0), Point(6000, 4000))
    d.undo_stack.push(AddEntityCommand(d, boundary))
    room = architecture.create_room(d, boundary, "Office", "102", "Tile")
    assert architecture.finish_rows(d)[0]["Area"] == 24
    d.undo_stack.push(TranslateEntitiesCommand(d, [wall], 100, 200))
    assert door.insertion_point == Point(1600, 200)
    assert window.insertion_point == Point(4100, 200)
    architecture.export_finishes(d, tmp_path / "finishes.csv")
    assert "Office" in (tmp_path / "finishes.csv").read_text(encoding="utf-8-sig")
    d.mark_saved()
    before = document_to_dict(d)
    d.sync_associative()
    assert not d.dirty and document_to_dict(d) == before
    save_project(d, tmp_path / "arch.pycad")
    loaded = load_project(tmp_path / "arch.pycad")
    assert architecture.finish_rows(loaded)[0]["Finish"] == "Tile"
    assert any(r.get("Identifier") == "D10" for r in smart_blocks.schedule_rows(loaded))
    with pytest.raises(ValueError):
        architecture.create_opening(d, wall, 1500, 1000)


def test_tabs_independent_undo_view_and_close_cancel(main_window, monkeypatch):
    w = main_window
    first = w.document
    line = LineEntity(Point(0, 0), Point(10, 0))
    first.undo_stack.push(AddEntityCommand(first, line))
    w.canvas.zoom = 7
    w.canvas.pan_offset = QPointF(5, 6)
    assert w.new_file()
    second = w.document
    second.undo_stack.push(AddEntityCommand(second, CircleEntity(Point(0, 0), 4)))
    w.drawing_tabs.setCurrentIndex(0)
    assert (
        w.document is first
        and w.canvas.zoom == 7
        and w.canvas.pan_offset == QPointF(5, 6)
    )
    w.undo()
    assert not first.entities and len(second.entities) == 1
    w.drawing_tabs.setCurrentIndex(1)
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *a, **k: QMessageBox.StandardButton.Cancel
    )
    assert not w.drawing_tabs.close_drawing(1)
    assert w.drawing_tabs.count() == 2


def test_solid_boolean_revolve_sweep_section_export_native(qapp, tmp_path):
    pytest.importorskip("cadquery")
    from pycad.model3d import create_extrusion
    from pycad import solids

    d = Document()
    a = RectangleEntity(Point(0, 0), Point(10, 10))
    b = RectangleEntity(Point(5, 0), Point(15, 10))
    d.add_entity(a)
    d.add_entity(b)
    x = create_extrusion(d, a, 10)
    y = create_extrusion(d, b, 10)
    for op, volume in [("union", 1500), ("subtract", 500), ("intersect", 500)]:
        key = solids.boolean(d, [x["id"], y["id"]], op)
        assert solids.get_shape(d, key).Volume() == pytest.approx(volume)
        assert solids.section_paths(d, key, "Z", 5)
        assert solids.elevation_paths(d, key, "Front")
    key = solids.revolve(d, RectangleEntity(Point(5, 0), Point(10, 10)))
    assert solids.get_shape(d, key).Volume() == pytest.approx(math.pi * 75 * 10)
    key = solids.sweep(d, LineEntity(Point(0, 0), Point(20, 0)), 2)
    assert solids.get_shape(d, key).Volume() == pytest.approx(math.pi * 4 * 20)
    solids.export_solid(d, key, tmp_path / "solid.step")
    assert (tmp_path / "solid.step").stat().st_size > 1000
    save_project(d, tmp_path / "3d.pycad")
    loaded = load_project(tmp_path / "3d.pycad")
    assert solids.get_shape(loaded, key).Volume() == pytest.approx(math.pi * 4 * 20)


def test_assistant_atomic_preview_apply_undo_recorder(qapp, main_window):
    d = Document()
    actions = automation.parse_instruction("room 6000x4000")
    preview = automation.prepare_proposal(d, actions)
    assert not d.entities and len(preview.entities) == 6
    automation.apply_proposal(d, actions)
    assert len(d.entities) == 6 and d.undo_stack.count() == 1
    d.undo_stack.undo()
    assert not d.entities and not d.extensions.get("architecture")
    before = document_to_dict(d)
    with pytest.raises(ValueError):
        automation.apply_proposal(d, [{"op": "circle", "center": [0, 0], "radius": -1}])
    assert document_to_dict(d) == before
    w = main_window
    recorder = automation.Recorder(w)
    w.document.undo_stack.push(
        AddEntityCommand(w.document, LineEntity(Point(0, 0), Point(10, 0)))
    )
    recorded = recorder.stop()
    assert recorded[0]["op"] == "add"
    automation.apply_proposal(w.document, recorded)
    assert (
        len(w.document.entities) == 2 and len({e.id for e in w.document.entities}) == 2
    )


def test_python_plugin_registers_reviewable_command(main_window, tmp_path):
    path = tmp_path / "plugin.py"
    path.write_text(
        "def register(api):\n    api.register_command('TESTPLUGIN',lambda:api.propose([{'op':'circle','center':[0,0],'radius':2}]))\n"
    )
    automation.load_plugin(main_window, path)
    assert "TESTPLUGIN" in main_window.command_names


def test_architecture_clipboard_and_unit_conversion(qapp, tmp_path):
    from pycad.ribbon_actions import selection_document
    from pycad.edit_commands import prepare_paste, PasteCommand
    from pycad.unit_conversion import convert_units

    d = Document()
    wall = architecture.create_wall(d, Point(0, 0), Point(6000, 0))
    door = architecture.create_opening(d, wall, 1500, 900)
    selected = selection_document(d, [wall, door])
    target = Document()
    target.units = "m"
    raw = json.dumps(
        {
            "format": "PyCAD clipboard",
            "base": [0, 0],
            "drawing": document_to_dict(selected),
        }
    ).encode()
    imported, tables = prepare_paste(target, raw, Point(10, 0))
    target.undo_stack.push(PasteCommand(target, imported, tables))
    records = target.extensions["architecture"]
    assert next(r for r in records.values() if r["kind"] == "wall")["length"] == 6
    assert target.entities[1].insertion_point == Point(11.5, 0)
    target.undo_stack.undo()
    assert not target.entities and not target.extensions
    convert_units(d, "m")
    assert d.extensions["architecture"][wall.id]["length"] == 6
    d.undo_stack.undo()
    assert d.extensions["architecture"][wall.id]["length"] == 6000


@pytest.mark.parametrize(
    "area,value",
    [
        ("plot_presets", {"Bad": {"margin": 1}}),
        ("leader_links", {"Bad": [{"source": "id", "anchor": "execute"}]}),
        ("sheets", {"Bad": {"title": 1}}),
        ("solids", {"Bad": {"brep": "bad"}}),
        ("macros", {"Bad": {"actions": [{"op": "execute", "code": "oops"}]}}),
    ],
)
def test_malformed_feature_data_rejected(qapp, area, value):
    data = document_to_dict(Document())
    data["extensions"][area] = value
    with pytest.raises(ValueError):
        document_from_dict(data)


def test_multi_tab_recovery_preserves_inactive_dirty_drawing(
    main_window, tmp_path, monkeypatch
):
    from pycad.document_tabs import save_recovery, load_recovery_tabs
    from pycad import appsettings

    w = main_window
    first = w.document
    first.undo_stack.push(
        AddEntityCommand(first, LineEntity(Point(0, 0), Point(30, 0)))
    )
    w.new_file()
    assert not w.document.dirty
    save_recovery(w)
    assert (tmp_path / "recovery.pycad.tabs.json").exists()
    # A fresh starter replaces the sessions, simulating a new application launch.
    w.drawing_tabs.sessions = w.drawing_tabs.sessions[:1]
    w.drawing_tabs.blockSignals(True)
    while w.drawing_tabs.count() > 1:
        w.drawing_tabs.removeTab(1)
    w.drawing_tabs.active = 0
    w.drawing_tabs.setCurrentIndex(0)
    w.drawing_tabs.blockSignals(False)
    w._replace_document(Document())
    assert load_recovery_tabs(w)
    assert w.drawing_tabs.count() == 2 and w.drawing_tabs.active == 1
    assert w.drawing_tabs.sessions[0]["doc"].dirty
    assert len(w.drawing_tabs.sessions[0]["doc"].entities) == 1


def test_ai_provider_validated_declarative_response(monkeypatch):
    from pycad import ai_provider

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, size):
            return json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "actions": [
                                            {
                                                "op": "circle",
                                                "center": [0, 0],
                                                "radius": 10,
                                            }
                                        ]
                                    }
                                )
                            }
                        }
                    ]
                }
            ).encode()

    class Opener:
        def open(self, request, timeout):
            assert request.get_header("Authorization") == "Bearer test-secret"
            assert "test-secret" not in request.data.decode()
            return Response()

    monkeypatch.setattr(ai_provider, "build_opener", lambda *args: Opener())
    actions = ai_provider.request_actions(
        "https://example.com/v1/chat/completions",
        "test-secret",
        "model",
        "circle",
        {"units": "mm"},
    )
    assert actions[0]["radius"] == 10
    with pytest.raises(ValueError):
        ai_provider.validate_endpoint("http://example.com/v1/chat/completions")


def test_architectural_3d_wall_opening_volume_and_undo(qapp):
    pytest.importorskip("cadquery")
    from pycad.solids import get_shape

    d = Document()
    wall = architecture.create_wall(d, Point(0, 0), Point(6000, 0), 200, 3000)
    architecture.create_opening(d, wall, 1500, 900, 2100, "door", "D01", 0)
    keys = architecture.build_wall_solids(d)
    assert get_shape(d, keys[0]).Volume() == pytest.approx(
        6000 * 200 * 3000 - 900 * 200 * 2100
    )
    d.undo_stack.undo()
    assert not d.extensions.get("solids")


def test_saved_solid_model_browser_rename_delete_undo(main_window):
    pytest.importorskip("cadquery")
    from pycad import solids

    w = main_window
    key = solids.revolve(w.document, RectangleEntity(Point(5, 0), Point(10, 10)))
    w.open_model_workspace()
    workspace = w.model_workspace
    assert workspace.features.count() == 1 and workspace.selected()["solid"]
    workspace.edit_feature("name", "Revolved ring")
    assert w.document.extensions["solids"][key]["name"] == "Revolved ring"
    workspace.edit_feature("delete", None)
    assert not w.document.extensions.get("solids")
    w.undo()
    assert key in w.document.extensions["solids"]


def test_lowercase_point_attribute_tag_survives_native(qapp):
    d = Document()
    d.blocks["Symbol"] = BlockDefinition("Symbol", [])
    insert = BlockReferenceEntity("Symbol", Point(0, 0), attributes={"point": "12"})
    d.add_entity(insert)
    assert document_from_dict(document_to_dict(d)).entities[0].attributes == {
        "point": "12"
    }


def test_attribute_style_layer_dependencies_and_purge(qapp):
    from pycad import textstyles
    from pycad.file_workspace import purge_candidates
    from pycad.project_tools import TranslateLayerCommand

    d = Document()
    d.edit_layer("add", "Attribute labels", "#aabbcc")
    d.layers.current_layer = "Attribute labels"
    textstyles.edit_style(
        d, "add", "Wide", {**textstyles.DEFAULT_STYLE, "width_factor": 2}
    )
    d.current_textstyle = "Wide"
    d.blocks["Door"] = BlockDefinition("Door", [])
    smart_blocks.define_attribute(d, "Door", "ID", "Door label", (0, 0), 5)
    d.current_textstyle = "Standard"
    d.layers.current_layer = "0"
    e = BlockReferenceEntity("Door", Point(0, 0))
    d.undo_stack.push(AddEntityCommand(d, e))
    assert e.resolved_entities[0]._text_style["width_factor"] == 2
    candidates = purge_candidates(d)
    assert (
        "Wide" not in candidates["textstyles"]
        and "Attribute labels" not in candidates["layers"]
    )
    with pytest.raises(ValueError):
        textstyles.edit_style(d, "delete", "Wide")
    d.undo_stack.push(TranslateLayerCommand(d, "Attribute labels", "0"))
    assert d.blocks["Door"].attributes[0]["layer"] == "0"
    document_from_dict(document_to_dict(d))
    d.undo_stack.undo()
    assert d.blocks["Door"].attributes[0]["layer"] == "Attribute labels"


def test_template_new_document_keeps_dirty_tab(main_window, tmp_path):
    from pycad.file_workspace import load_as_new

    w = main_window
    first = w.document
    first.undo_stack.push(
        AddEntityCommand(first, LineEntity(Point(0, 0), Point(10, 0)))
    )
    template = Document()
    template.add_entity(CircleEntity(Point(0, 0), 5))
    save_project(template, tmp_path / "template.pycad")
    assert load_as_new(w, tmp_path / "template.pycad")
    assert (
        w.drawing_tabs.count() == 2
        and len(first.entities) == 1
        and w.document is not first
    )
