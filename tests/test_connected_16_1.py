import copy
import pytest
from pycad.document import (
    Document,
    TranslateEntitiesCommand,
    DeleteEntitiesCommand,
    AddEntityCommand,
)
from pycad.geometry import (
    Point,
    RectangleEntity,
    LineEntity,
    CircleEntity,
    BlockDefinition,
    BlockReferenceEntity,
)
from pycad import architecture, solids, wall_joining, drawing_checks, object_properties
from pycad.feature_data import edit_table
from pycad.native_io import (
    document_to_dict,
    document_from_dict,
    save_project,
    load_project,
)


def walls(doc, width=200):
    a = architecture.create_wall(doc, Point(0, 0), Point(1000, 0), 200, 3000)
    b = architecture.create_wall(doc, Point(1000, 0), Point(1000, 1000), width, 3000)
    return a, b


def test_miter_corner_shared_vertices_and_no_internal_seam(qapp):
    d = Document()
    a, b = walls(d)
    f = wall_joining.frames(d)
    assert f[a.id]["polygon"][1] == pytest.approx((1100, -100))
    assert f[a.id]["polygon"][2] == pytest.approx((900, 100))
    assert f[b.id]["polygon"][0] == pytest.approx((1100, -100))
    assert f[b.id]["polygon"][3] == pytest.approx((900, 100))
    lines = d.blocks[a.block_name].entities + d.blocks[b.block_name].entities
    assert len(lines) == 6 and all(isinstance(e, LineEntity) for e in lines)
    d.mark_saved()
    before = document_to_dict(d)
    d.undo_stack.push(TranslateEntitiesCommand(d, [b], 500, 0))
    assert not wall_joining.frames(d)[a.id]["neighbours"]
    d.undo_stack.undo()
    assert document_to_dict(d) == before and not d.dirty


@pytest.mark.parametrize("width", [100, 300])
def test_unequal_wall_corner_miters(qapp, width):
    d = Document()
    a, b = walls(d, width)
    f = wall_joining.frames(d)
    assert f[a.id]["polygon"][1] == pytest.approx((1000 + width / 2, -100))
    assert f[a.id]["polygon"][2] == pytest.approx((1000 - width / 2, 100))


def test_t_join_removes_through_wall_seam(qapp):
    d = Document()
    a = architecture.create_wall(d, Point(0, 0), Point(2000, 0))
    b = architecture.create_wall(d, Point(1000, 0), Point(1000, 1000))
    assert b.id in wall_joining.frames(d)[a.id]["neighbours"]
    for e in a.resolved_entities:
        assert isinstance(e, LineEntity)
        if abs(e.p1.y - 100) < 1e-7 and abs(e.p2.y - 100) < 1e-7:
            assert (
                max(e.p1.x, e.p2.x) <= 900 + 1e-7 or min(e.p1.x, e.p2.x) >= 1100 - 1e-7
            )


def test_collinear_join_has_no_end_cap(qapp):
    d = Document()
    a = architecture.create_wall(d, Point(0, 0), Point(1000, 0))
    b = architecture.create_wall(d, Point(1000, 0), Point(2000, 0))
    assert not any(
        abs(e.p1.x - 1000) < 1e-8 and abs(e.p2.x - 1000) < 1e-8
        for wall in (a, b)
        for e in wall.resolved_entities
    )


def test_wall_models_miter_volume_and_stable_update_ids(qapp):
    pytest.importorskip("cadquery")
    d = Document()
    a, b = walls(d)
    keys = architecture.build_wall_solids(d)
    shapes = [solids.get_shape(d, k) for k in keys]
    assert sum(s.Volume() for s in shapes) == pytest.approx(1200000000)
    assert shapes[0].intersect(shapes[1]).Volume() == pytest.approx(0, abs=1e-5)
    assert architecture.build_wall_solids(d) == keys
    assert len(d.extensions["solids"]) == 2


def test_t_join_volume_without_overlap_and_neighbor_updates(qapp):
    pytest.importorskip("cadquery")
    d = Document()
    through = architecture.create_wall(d, Point(0, 0), Point(2000, 0))
    architecture.create_wall(d, Point(1000, 0), Point(1000, 1000))
    keys = architecture.build_wall_solids(d)
    assert solids.get_shape(d, keys[1]).BoundingBox().ymin == pytest.approx(100)
    assert sum(solids.get_shape(d, key).Volume() for key in keys) == pytest.approx(
        580000 * 3000
    )
    object_properties.apply_values(d, through, {"Architecture.width": 300})
    assert solids.get_shape(d, keys[1]).BoundingBox().ymin == pytest.approx(150)
    d.undo_stack.undo()
    assert solids.get_shape(d, keys[1]).BoundingBox().ymin == pytest.approx(100)


def test_joined_plan_dxf_roundtrip(qapp, tmp_path):
    from pycad import dxf_io

    d = Document()
    a, b = walls(d)
    dxf_io.export_dxf(d, str(tmp_path / "joined.dxf"))
    restored = dxf_io.import_dxf(str(tmp_path / "joined.dxf"))
    assert len(restored.entities) == 2
    lines = [
        child for entity in restored.entities for child in entity.resolved_entities
    ]
    assert len(lines) == 6
    assert any(child.p2.x == pytest.approx(1100) for child in lines)


def test_live_parameter_update_and_one_undo_restores_saved_native(qapp):
    pytest.importorskip("cadquery")
    d = Document()
    wall = architecture.create_wall(d, Point(0, 0), Point(6000, 0))
    key = architecture.build_wall_solids(d)[0]
    d.mark_saved()
    before = document_to_dict(d)
    count = d.undo_stack.count()
    object_properties.apply_values(d, wall, {"Architecture.height": "4000"})
    assert d.undo_stack.count() == count + 1
    assert solids.get_shape(d, key).Volume() == pytest.approx(6000 * 200 * 4000)
    d.undo_stack.undo()
    assert document_to_dict(d) == before and not d.dirty
    d.undo_stack.redo()
    assert solids.get_shape(d, key).Volume() == pytest.approx(6000 * 200 * 4000)


def test_moving_wall_updates_model_placement_and_cached_undo(qapp):
    pytest.importorskip("cadquery")
    d = Document()
    wall = architecture.create_wall(d, Point(0, 0), Point(1000, 0))
    key = architecture.build_wall_solids(d)[0]
    d.mark_saved()
    before = document_to_dict(d)
    d.undo_stack.push(TranslateEntitiesCommand(d, [wall], 250, 100))
    assert solids.get_shape(d, key).BoundingBox().xmin == pytest.approx(250)
    d.undo_stack.undo()
    assert document_to_dict(d) == before and not d.dirty


def test_opening_edits_update_cut_volume(qapp):
    pytest.importorskip("cadquery")
    d = Document()
    wall = architecture.create_wall(d, Point(0, 0), Point(6000, 0))
    opening = architecture.create_opening(d, wall, 1500)
    key = architecture.build_wall_solids(d)[0]
    object_properties.apply_values(d, opening, {"Architecture.width": "1000"})
    assert solids.get_shape(d, key).Volume() == pytest.approx(
        6000 * 200 * 3000 - 1000 * 200 * 2100
    )


def test_linked_elevation_updates_height_and_preserves_placement(qapp):
    pytest.importorskip("cadquery")
    d = Document()
    wall = architecture.create_wall(d, Point(0, 0), Point(1000, 0))
    key = architecture.build_wall_solids(d)[0]
    view = solids.place_view(
        d, solids.elevation_paths(d, key), key, "Front", (2000, 500)
    )
    d.mark_saved()
    before = document_to_dict(d)
    object_properties.apply_values(d, wall, {"Architecture.height": 4000})
    assert view.bbox()[3] == pytest.approx(4500)
    assert view.insertion_point == Point(2000, 500)
    d.undo_stack.undo()
    assert document_to_dict(d) == before and not d.dirty


def test_section_plane_editor_and_empty_intersection(qapp):
    pytest.importorskip("cadquery")
    d = Document()
    architecture.create_wall(d, Point(0, 0), Point(1000, 0))
    key = architecture.build_wall_solids(d)[0]
    view = solids.place_view(
        d, solids.section_paths(d, key, "Z", 100), key, "Section Z=100"
    )
    object_properties.apply_values(d, view, {"View.offset": 4000})
    assert not d.blocks[view.block_name].entities
    assert d.link_status[view.id] == "Current; section has no intersection"
    d.undo_stack.undo()
    assert d.blocks[view.block_name].entities


def test_cached_reopen_without_kernel_stale_edit_and_undo(qapp, tmp_path, monkeypatch):
    pytest.importorskip("cadquery")
    d = Document()
    wall = architecture.create_wall(d, Point(0, 0), Point(1000, 0))
    key = architecture.build_wall_solids(d)[0]
    view = solids.place_view(d, solids.elevation_paths(d, key), key, "Front")
    save_project(d, tmp_path / "live.pycad")

    def missing():
        raise ValueError("Optional 3D kernel is unavailable")

    monkeypatch.setattr(solids, "kernel", missing)
    d = load_project(tmp_path / "live.pycad")
    before = document_to_dict(d)
    wall = d.find_by_id(wall.id)
    object_properties.apply_values(d, wall, {"Architecture.height": 4000})
    assert d.link_status[key].startswith("Stale") and d.link_status[view.id].startswith(
        "Stale"
    )
    assert d.extensions["solids"][key] == before["extensions"]["solids"][key]
    with pytest.raises(ValueError, match="Stale"):
        solids.get_shape(d, key)
    assert any(i["code"] == "STALE_LINK" for i in drawing_checks.inspect(d))
    d.undo_stack.undo()
    assert document_to_dict(d) == before and not d.dirty


def test_delete_wall_hides_model_and_undo_restores_it(qapp):
    pytest.importorskip("cadquery")
    d = Document()
    wall = architecture.create_wall(d, Point(0, 0), Point(1000, 0))
    key = architecture.build_wall_solids(d)[0]
    original = copy.deepcopy(d.extensions["solids"][key])
    d.undo_stack.push(DeleteEntitiesCommand(d, [wall]))
    assert key not in d.extensions["solids"]
    d.undo_stack.undo()
    assert d.extensions["solids"][key] == original


def test_delete_or_detach_model_does_not_recreate_it(qapp):
    pytest.importorskip("cadquery")
    d = Document()
    wall = architecture.create_wall(d, Point(0, 0), Point(1000, 0))
    key = architecture.build_wall_solids(d)[0]
    edit_table(d, "solids", key, None)
    d.sync_associative()
    assert (
        key not in d.extensions.get("wall_models", {})
        and key not in d.extensions["solids"]
    )
    d.undo_stack.undo()
    edit_table(d, "wall_models", key, None)
    before = copy.deepcopy(d.extensions["solids"][key])
    object_properties.apply_values(d, wall, {"Architecture.height": 4000})
    assert d.extensions["solids"][key] == before


def test_unit_conversion_live_models_views_and_undo(qapp):
    pytest.importorskip("cadquery")
    from pycad.unit_conversion import convert_units

    d = Document()
    architecture.create_wall(d, Point(0, 0), Point(1000, 0))
    key = architecture.build_wall_solids(d)[0]
    view = solids.place_view(
        d, solids.section_paths(d, key, "Z", 100), key, "Section Z=100", (2000, 0)
    )
    d.mark_saved()
    before = document_to_dict(d)
    convert_units(d, "m")
    assert d.extensions["view_links"][view.id]["offset"] == pytest.approx(0.1)
    assert solids.get_shape(d, key).Volume() == pytest.approx(0.6)
    assert view.bbox()[2] == pytest.approx(3)
    d.undo_stack.undo()
    assert document_to_dict(d) == before and not d.dirty


@pytest.mark.parametrize(
    "area,bad",
    [
        ("wall_models", []),
        ("wall_models", {"x": {"wall": "a", "fingerprint": "bad"}}),
        ("view_links", {"x": {}}),
    ],
)
def test_invalid_link_tables_rejected(qapp, area, bad):
    data = document_to_dict(Document())
    data["extensions"][area] = bad
    with pytest.raises(ValueError):
        document_from_dict(data)


def test_property_editor_attributes_primitive_parameters_and_atomic_rejection(qapp):
    from pycad import smart_blocks

    d = Document()
    circle = CircleEntity(Point(0, 0), 10)
    d.undo_stack.push(AddEntityCommand(d, circle))
    object_properties.apply_values(d, circle, {"radius": "20", "center.x": "5"})
    assert circle.radius == 20 and circle.center.x == 5
    d.undo_stack.undo()
    before = document_to_dict(d)
    with pytest.raises(ValueError):
        object_properties.apply_values(d, circle, {"radius": "-1"})
    assert document_to_dict(d) == before
    d.blocks["Door"] = BlockDefinition("Door", [])
    smart_blocks.define_attribute(d, "Door", "ID", "D01")
    insert = BlockReferenceEntity("Door", Point(0, 0))
    d.undo_stack.push(AddEntityCommand(d, insert))
    object_properties.apply_values(d, insert, {"Attribute.ID": "D02"})
    assert insert.attributes["ID"] == "D02"
    d.undo_stack.undo()
    assert not insert.attributes


def test_property_rejects_overlap_bounds_and_locked_layer(qapp):
    d = Document()
    wall = architecture.create_wall(d, Point(0, 0), Point(6000, 0))
    opening = architecture.create_opening(d, wall, 1500)
    architecture.create_opening(d, wall, 3000)
    before = document_to_dict(d)
    with pytest.raises(ValueError, match="overlap"):
        object_properties.apply_values(d, opening, {"Architecture.station": 3000})
    assert document_to_dict(d) == before
    with pytest.raises(ValueError):
        object_properties.apply_values(d, wall, {"Architecture.height": 1000})
    d.edit_layer("locked", "0", True)
    with pytest.raises(ValueError, match="editable"):
        object_properties.apply_values(d, wall, {"Architecture.material": "Concrete"})


def test_closed_wall_loop_has_no_open_end_warnings(qapp):
    d = Document()
    points = [Point(0, 0), Point(3000, 0), Point(3000, 3000), Point(0, 3000)]
    for a, b in zip(points, points[1:] + points[:1]):
        architecture.create_wall(d, a, b)
    assert not drawing_checks.inspect(d)


def test_checks_highlight_free_ends_overlaps_rooms_and_clear_on_edit(qapp):
    d = Document()
    wall = architecture.create_wall(d, Point(0, 0), Point(6000, 0))
    architecture.create_opening(d, wall, 1500)
    b = architecture.create_opening(d, wall, 3000)
    # Emulate an imported/problematic drawing without silently repairing it.
    d.extensions["architecture"][b.id]["station"] = 1500
    boundary = RectangleEntity(Point(0, 0), Point(6000, 4000))
    d.undo_stack.push(AddEntityCommand(d, boundary))
    architecture.create_room(d, boundary)
    boundary.closed = False
    before = document_to_dict(d)
    codes = {i["code"] for i in drawing_checks.inspect(d)}
    assert {"OPEN_WALL_END", "OVERLAPPING_OPENINGS", "OPEN_ROOM"} <= codes
    assert document_to_dict(d) == before
    d.undo_stack.push(TranslateEntitiesCommand(d, [wall], 10, 0))
    assert not d.check_issues


def test_compact_properties_ui_and_new_commands(main_window, qapp):
    w = main_window
    wall = architecture.create_wall(w.document, Point(0, 0), Point(6000, 0))
    w.canvas.selected_entities = [wall]
    w.properties_panel.show()
    w.properties_panel.raise_()
    w.properties_panel.refresh()
    editor = w.properties_panel.object_editor
    keys = [
        editor.table.item(i, 0).data(
            __import__("PyQt6.QtCore", fromlist=["Qt"]).Qt.ItemDataRole.UserRole
        )
        for i in range(editor.table.rowCount())
    ]
    assert "Architecture.material" in keys and "Architecture.height" in keys
    assert editor.table.height() == 180 and w.properties_panel.width() < 450
    for i, key in enumerate(keys):
        if key == "Architecture.material":
            editor.table.item(i, 1).setText("Concrete")
    editor.commit()
    assert w.document.extensions["architecture"][wall.id]["material"] == "Concrete"
    assert {"CHECKDRAWING", "UPDATELINKS"} <= set(w.command_names)


def test_wall_axis_endpoint_snap(main_window):
    from pycad.canvas import Snap

    w = main_window
    architecture.create_wall(w.document, Point(0, 0), Point(1000, 0))
    w.canvas.zoom_extents()
    w.canvas.snap_modes = {Snap.ENDPOINT}
    point, kind = w.canvas.find_snap_point(w.canvas.world_to_screen(1000, 0))
    assert kind == Snap.ENDPOINT and point == Point(1000, 0)


def test_legacy_schema_10_remains_readable(qapp):
    data = document_to_dict(Document())
    data["schema_version"] = 10
    assert document_to_dict(document_from_dict(data))["schema_version"] == __import__("pycad.native_io",fromlist=["SCHEMA_VERSION"]).SCHEMA_VERSION


def test_legacy_generated_view_migrates_and_stays_detached_after_new_save(qapp):
    pytest.importorskip("cadquery")
    from pycad.model3d import create_extrusion

    d = Document()
    profile = RectangleEntity(Point(0, 0), Point(1000, 200))
    d.add_entity(profile)
    feature = create_extrusion(d, profile, 3000)
    view = solids.place_view(
        d,
        solids.elevation_paths(d, feature["id"]),
        feature["id"],
        "Front",
        linked=False,
    )
    data = document_to_dict(d)
    data["schema_version"] = 10
    data["extrusions"][0]["height"] = 4000
    restored = document_from_dict(data)
    assert restored.find_by_id(view.id).bbox()[3] == pytest.approx(4000)
    assert view.id in restored.extensions["view_links"]
    edit_table(restored, "view_links", view.id, None)
    assert view.id not in document_from_dict(document_to_dict(restored)).extensions.get(
        "view_links", {}
    )


def test_deleted_opening_does_not_block_replacement_or_wall_edit(qapp):
    d = Document()
    wall = architecture.create_wall(d, Point(0, 0), Point(6000, 0))
    door = architecture.create_opening(d, wall, 1500)
    d.undo_stack.push(DeleteEntitiesCommand(d, [door]))
    object_properties.apply_values(d, wall, {"Architecture.height": 1000})
    new = architecture.create_opening(d, wall, 1500, 900, 500, "window", "W01", 100)
    assert d.find_by_id(new.id)
    document_from_dict(document_to_dict(d))


def test_non_geometry_identifier_change_keeps_cached_model_current(qapp, monkeypatch):
    pytest.importorskip("cadquery")
    d = Document()
    wall = architecture.create_wall(d, Point(0, 0), Point(6000, 0))
    door = architecture.create_opening(d, wall, 1500)
    key = architecture.build_wall_solids(d)[0]
    before = copy.deepcopy(d.extensions["solids"][key])
    monkeypatch.setattr(
        solids, "kernel", lambda: (_ for _ in ()).throw(ValueError("no kernel"))
    )
    object_properties.apply_values(d, door, {"Architecture.identifier": "D20"})
    assert d.link_status[key] == "Current" and d.extensions["solids"][key] == before


def test_stale_view_pdf_rejected_atomically_but_unaffected_plan_can_plot(
    qapp, tmp_path, monkeypatch
):
    pytest.importorskip("cadquery")
    from pycad.plotting import publish_pdf

    d = Document()
    wall = architecture.create_wall(d, Point(0, 0), Point(1000, 0))
    key = architecture.build_wall_solids(d)[0]
    solids.place_view(d, solids.elevation_paths(d, key), key, "Front", (10000, 0))
    layout = d.create_layout("Plan", 297, 210)
    layout.viewports[0].center = Point(500, 0)
    layout.viewports[0].scale = 0.1
    monkeypatch.setattr(
        solids, "kernel", lambda: (_ for _ in ()).throw(ValueError("no kernel"))
    )
    object_properties.apply_values(d, wall, {"Architecture.height": 4000})
    path = tmp_path / "output.pdf"
    path.write_bytes(b"prior drawing")
    with pytest.raises(ValueError, match="stale linked view"):
        publish_pdf(d, path, ["Model"])
    assert path.read_bytes() == b"prior drawing"
    publish_pdf(d, path, ["Plan"])
    assert path.read_bytes().startswith(b"%PDF")
