import base64
import copy
import json
import math
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
import pytest
from pycad.document import Document, AddEntityCommand, DeleteEntitiesCommand
from pycad.geometry import Point, RectangleEntity, LineEntity
from pycad import (
    architecture,
    building,
    building_views,
    auto_rooms,
    solids,
    boq,
    materials,
    object_properties,
    automation,
    drafting_chat,
)
from pycad.native_io import (
    document_to_dict,
    document_from_dict,
    save_project,
    load_project,
)


def test_build_hidden_level_sources_and_reject_mismatched_native_block(qapp):
    d = Document()
    slab = building.create_element(d, "slab", boundary(d))
    building.set_level(d, "Ground", 0, 3000, False)
    key = building.build_models(d)[0]
    assert solids.get_shape(d, key).Volume() > 0
    payload = document_to_dict(d)
    payload["extensions"]["building_elements"][slab.id]["block"] = "missing"
    with pytest.raises(ValueError, match="block does not match"):
        document_from_dict(payload)


def test_chat_multiple_wall_refs_and_duplicate_rejection(qapp):
    d = Document()
    proposal = drafting_chat.offline(
        d, "wall from 0,0 to 1000,0; wall from 0,0 to 0,1000"
    )
    assert len({a["ref"] for a in proposal["actions"]}) == 2
    automation.apply_proposal(d, proposal["actions"])
    assert len(d.extensions["architecture"]) == 2
    before = document_to_dict(d)
    duplicate = [copy.deepcopy(proposal["actions"][0])] * 2
    with pytest.raises(ValueError, match="Duplicate"):
        automation.prepare_proposal(d, duplicate)
    assert document_to_dict(d) == before


def test_cross_drawing_paste_preserves_implicit_ground_and_conflicting_level(qapp):
    from pycad.ribbon_actions import selection_document
    from pycad.edit_commands import prepare_paste, PasteCommand

    source = Document()
    building.set_level(source, "First", 3300, 3000)
    slab = building.create_element(source, "slab", boundary(source))
    selected = selection_document(source, [slab])
    raw = json.dumps(
        dict(format="PyCAD clipboard", base=[0, 0], drawing=document_to_dict(selected))
    ).encode()
    dest = Document()
    wall = architecture.create_wall(dest, Point(0, 0), Point(1000, 0))
    dest.mark_saved()
    before = document_to_dict(dest)
    imported, tables = prepare_paste(dest, raw, Point(10000, 0))
    dest.undo_stack.push(PasteCommand(dest, imported, tables))
    assert set(building.levels(dest)) == {"Ground", "First"}
    assert building.level_for(dest, wall.id) == "Ground"
    assert building.levels(dest)["Ground"]["height"] == 3000
    dest.undo_stack.undo()
    assert document_to_dict(dest) == before and not dest.dirty
    building.set_level(dest, "First", 6000, 3500)
    imported, tables = prepare_paste(dest, raw, Point(10000, 0))
    dest.undo_stack.push(PasteCommand(dest, imported, tables))
    assert building.levels(dest)["First"]["elevation"] == 6000
    assert building.levels(dest)["First_2"]["elevation"] == 3300
    assert (
        next(iter(dest.extensions["building_elements"].values()))["level"] == "First_2"
    )


def test_boq_select_sources_switches_from_sheet_to_model(qapp):
    from PyQt6.QtCore import QTimer
    from PyQt6.QtWidgets import QApplication, QTableWidget, QPushButton
    from pycad.main_window import MainWindow
    from pycad import boq_ui

    w = MainWindow()
    wall = architecture.create_wall(w.document, Point(0, 0), Point(1000, 0))
    w.document.create_layout("Sheet")
    w._sync_space_tabs()
    w.space_tabs.setCurrentIndex(
        next(
            i for i in range(w.space_tabs.count()) if w.space_tabs.tabText(i) == "Sheet"
        )
    )
    assert w.document.current_space == "Sheet"
    failures = []

    def select():
        try:
            dialog = QApplication.activeModalWidget()
            dialog.findChild(QTableWidget).selectRow(0)
            next(
                b
                for b in dialog.findChildren(QPushButton)
                if b.text() == "Select sources"
            ).click()
        except Exception as ex:
            failures.append(ex)
            QApplication.activeModalWidget().reject()

    QTimer.singleShot(30, select)
    boq_ui.dialog(w)
    assert not failures
    assert w.document.current_space == "Model" and wall in w.canvas.selected_entities
    w.document.mark_saved()
    w.close()


def boundary(doc, width=6000, depth=4000):
    entity = RectangleEntity(Point(0, 0), Point(width, depth))
    doc.undo_stack.push(AddEntityCommand(doc, entity))
    return entity


def enclosure(doc):
    points = [Point(0, 0), Point(6000, 0), Point(6000, 4000), Point(0, 4000)]
    return [
        architecture.create_wall(doc, a, b, 200, 3000, "Brick")
        for a, b in zip(points, points[1:] + points[:1])
    ]


def test_level_assignment_visibility_and_elevated_wall_undo(qapp):
    d = Document()
    a = architecture.create_wall(d, Point(0, 0), Point(1000, 0))
    key = architecture.build_wall_solids(d)[0]
    d.mark_saved()
    before = document_to_dict(d)
    building.set_level(d, "First", 3300, 3000)
    building.assign_level(d, [a.id], "First")
    assert solids.get_shape(d, key).BoundingBox().zmin == pytest.approx(3300)
    building.set_level(d, "First", 3300, 3000, False)
    assert a not in d.visible_entities() and a not in d.query_entities(a.bbox())
    d.undo_stack.undo()
    d.undo_stack.undo()
    d.undo_stack.undo()
    assert document_to_dict(d) == before and not d.dirty


def test_different_storeys_do_not_join_or_share_plan_outlines(qapp):
    from pycad.wall_joining import frames

    d = Document()
    a = architecture.create_wall(d, Point(0, 0), Point(1000, 0))
    building.set_level(d, "First", 3000)
    b = architecture.create_wall(d, Point(1000, 0), Point(1000, 1000))
    assert not frames(d)[a.id]["neighbours"] and not frames(d)[b.id]["neighbours"]
    assert len(d.blocks[a.block_name].entities) == 1


def test_slab_hole_net_volume_quantities_and_invalid_preflight(qapp):
    d = Document()
    building.create_element(
        d,
        "slab",
        boundary(d),
        holes=[[[1000, 1000], [2000, 1000], [2000, 2000], [1000, 2000]]],
    )
    key = building.build_models(d)[0]
    assert solids.get_shape(d, key).Volume() == pytest.approx(23e6 * 150)
    rows = boq.report(d)["items"]
    assert next(
        r["quantity"] for r in rows if r["description"] == "Slab finish"
    ) == pytest.approx(23)
    d.mark_saved()
    before = document_to_dict(d)
    with pytest.raises(ValueError):
        building.create_element(
            d, "slab", d.entities[0], holes=[[[0, 0], [8000, 0], [8000, 100], [0, 100]]]
        )
    assert document_to_dict(d) == before and not d.dirty


@pytest.mark.parametrize("kind", ["Flat", "Shed", "Gable", "Hip"])
def test_real_roof_shapes_and_sloped_area(qapp, kind):
    d = Document()
    building.create_element(
        d, "roof", boundary(d), roof_type=kind, overhang=0, slope=30
    )
    key = building.build_models(d)[0]
    shape = solids.get_shape(d, key)
    assert shape.isValid() and shape.Volume() == pytest.approx(24e6 * 150)
    area = next(
        r["quantity"]
        for r in boq.report(d)["items"]
        if r["description"] == "Roof covering"
    )
    assert area == pytest.approx(
        24 if kind == "Flat" else 24 / math.cos(math.radians(30))
    )
    assert shape.BoundingBox().zmin == pytest.approx(3000)


@pytest.mark.parametrize("layout", ["Straight", "L", "U"])
def test_real_stair_layouts_rails_and_step_edit_undo(qapp, layout):
    d = Document()
    stair = building.create_element(d, "stair", layout=layout)
    key = building.build_models(d)[0]
    shape = solids.get_shape(d, key)
    assert shape.isValid() and shape.BoundingBox().zmax > 3000
    assert any(r["description"] == "Stair railing" for r in boq.report(d)["items"])
    d.mark_saved()
    before = document_to_dict(d)
    object_properties.apply_values(
        d, stair, {"Building.steps": "20", "Building.rails": "false"}
    )
    assert d.extensions["building_elements"][stair.id]["steps"] == 20
    assert solids.get_shape(d, key).BoundingBox().zmax == pytest.approx(3000)
    d.undo_stack.undo()
    assert document_to_dict(d) == before and not d.dirty


def test_slab_model_view_and_single_undo_reopen(qapp, tmp_path):
    d = Document()
    slab = building.create_element(d, "slab", boundary(d))
    key = building.build_models(d)[0]
    view = building_views.create_view(d, [key], view="Front", position=(10000, 500))
    save_project(d, tmp_path / "building.pycad")
    d.mark_saved()
    before = document_to_dict(d)
    object_properties.apply_values(d, slab, {"Building.thickness": 300})
    assert view.bbox()[3] - view.bbox()[1] == pytest.approx(300)
    assert view.insertion_point == Point(10000, 500)
    d.undo_stack.undo()
    assert document_to_dict(d) == before and not d.dirty
    assert document_to_dict(load_project(tmp_path / "building.pycad")) == before


def test_automatic_room_area_updates_and_open_wall_warning(qapp):
    d = Document()
    walls = enclosure(d)
    rooms = auto_rooms.detect_rooms(d)
    assert len(rooms) == 1 and auto_rooms.detect_rooms(d) == []
    room = rooms[0]
    assert architecture.room_metrics(d, d.extensions["architecture"][room.id])[
        1
    ] == pytest.approx(5800 * 3800)
    d.mark_saved()
    before = document_to_dict(d)
    # The upper wall points left; extending its left endpoint is unnecessary.
    actions = [
        dict(op="properties", ids=[walls[0].id], values={"Architecture.length": 7000}),
        dict(op="move", ids=[walls[1].id, walls[2].id], dx=1000, dy=0),
        dict(op="properties", ids=[walls[2].id], values={"Architecture.length": 7000}),
    ]
    automation.apply_proposal(d, actions)
    assert architecture.room_metrics(d, d.extensions["architecture"][room.id])[
        1
    ] == pytest.approx(6800 * 3800)
    d.undo_stack.undo()
    assert document_to_dict(d) == before and not d.dirty
    d.undo_stack.push(DeleteEntitiesCommand(d, [walls[0]]))
    assert d.room_link_status[room.id].startswith("Stale")
    assert any("last valid" in s for s in boq.report(d)["warnings"])


def test_automatic_rooms_at_unequal_width_t_junctions(qapp):
    d = Document()
    enclosure(d)
    architecture.create_wall(d, Point(3000, 0), Point(3000, 4000), 150, 3000)
    rooms = auto_rooms.detect_rooms(d)
    assert len(rooms) == 2
    areas = [
        architecture.room_metrics(d, d.extensions["architecture"][r.id])[1]
        for r in rooms
    ]
    assert areas == pytest.approx([2825 * 3800, 2825 * 3800])
    assert all(s == "Current" for s in d.room_link_status.values())


def test_hidden_viewport_layers_preserve_painter_clip_and_state(qapp):
    from PyQt6.QtGui import QPainter, QImage, QColor
    from PyQt6.QtCore import QRectF, qInstallMessageHandler
    from pycad.canvas import CadCanvas

    d = Document()
    d.edit_layer("add", "Hidden", "#00ff00")
    d.undo_stack.push(
        AddEntityCommand(d, LineEntity(Point(0, 0), Point(100, 0), layer="Hidden"))
    )
    d.undo_stack.push(AddEntityCommand(d, LineEntity(Point(0, 50), Point(100, 50))))
    canvas = CadCanvas(d)
    canvas._viewport_override = {"Hidden": {"visible": False}}
    image = QImage(200, 200, QImage.Format.Format_ARGB32)
    image.fill(QColor("white"))
    painter = QPainter(image)
    painter.setClipRect(QRectF(20, 20, 100, 100))
    clip = painter.clipBoundingRect()
    messages = []
    old_handler = qInstallMessageHandler(
        lambda kind, context, message: messages.append(message)
    )
    try:
        canvas._draw_entities(painter, paper=True)
        assert painter.clipBoundingRect() == clip
        assert not any("Unbalanced" in m for m in messages)
    finally:
        qInstallMessageHandler(old_handler)
        painter.end()
        canvas.deleteLater()


def test_multi_object_hlr_and_section_hatching(qapp):
    d = Document()
    enclosure(d)
    keys = architecture.build_wall_solids(d)
    front = building_views.create_view(d, keys, hidden=True)
    assert any(e.linetype == "DASHED" for e in d.blocks[front.block_name].entities)
    section = building_views.create_view(d, keys, kind="section", axis="Z", offset=1200)
    assert any(e.kind == "HATCH" for e in d.blocks[section.block_name].entities)
    object_properties.apply_values(d, section, {"BuildingView.offset": 10000})
    assert d.blocks[section.block_name].entities == []
    assert d.link_status[section.id] == "Current; section has no intersection"


def test_cached_building_without_kernel_stale_change_and_undo(
    qapp, tmp_path, monkeypatch
):
    d = Document()
    slab = building.create_element(d, "slab", boundary(d))
    key = building.build_models(d)[0]
    view = building_views.create_view(d, [key])
    save_project(d, tmp_path / "cached.pycad")

    def missing():
        raise ValueError("Kernel unavailable")

    monkeypatch.setattr(solids, "kernel", missing)
    d = load_project(tmp_path / "cached.pycad")
    before = document_to_dict(d)
    object_properties.apply_values(
        d, d.find_by_id(slab.id), {"Building.thickness": 200}
    )
    assert d.link_status[key].startswith("Stale") and d.link_status[view.id].startswith(
        "Stale"
    )
    with pytest.raises(ValueError, match="Stale"):
        solids.get_shape(d, key)
    d.undo_stack.undo()
    assert document_to_dict(d) == before and not d.dirty


def test_material_change_avoids_kernel_and_embedded_texture_roundtrip(
    qapp, monkeypatch
):
    from PyQt6.QtCore import QBuffer, QByteArray, QIODevice
    from PyQt6.QtGui import QImage, QColor

    d = Document()
    slab = building.create_element(d, "slab", boundary(d))
    key = building.build_models(d)[0]
    fingerprint = d.extensions["solids"][key]["sha256"]
    image = QImage(8, 8, QImage.Format.Format_RGB32)
    image.fill(QColor("#cc9933"))
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    encoded = base64.b64encode(bytes(data)).decode()
    materials.save_material(d, "Wood custom", "#cc9933", 0.5, "Wood", encoded)
    monkeypatch.setattr(
        solids, "kernel", lambda: (_ for _ in ()).throw(ValueError("No kernel"))
    )
    materials.assign(d, [slab.id], "Wood custom")
    assert (
        d.extensions["solids"][key]["sha256"] == fingerprint
        and d.link_status[key] == "Current"
    )
    restored = document_from_dict(document_to_dict(d))
    assert materials.appearance(restored, key)["texture"] == encoded


def test_boq_wall_opening_deductions_rates_trace_and_export(qapp, tmp_path):
    d = Document()
    wall = architecture.create_wall(d, Point(0, 0), Point(6000, 0), 200, 3000, "Brick")
    architecture.create_opening(d, wall, 1500, 900, 2100)
    rows = boq.report(d)["items"]
    masonry = next(r for r in rows if r["description"] == "Wall masonry")
    finish = next(r for r in rows if r["description"] == "Wall finish")
    assert masonry["quantity"] == pytest.approx(3.222)
    assert finish["quantity"] == pytest.approx(32.22)
    assert masonry["source_id"] == wall.id and masonry["rate"] is None
    boq.set_rates(d, {masonry["rate_key"]: 1000}, waste_percent=5)
    assert boq.report(d)["priced_total"] == pytest.approx(3383.1)
    object_properties.apply_values(d, wall, {"Architecture.height": 4000})
    assert boq.report(d)["priced_total"] == pytest.approx(4643.1)
    boq.export(d, tmp_path / "bill.json")
    boq.export(d, tmp_path / "bill.csv")
    assert (
        json.loads((tmp_path / "bill.json").read_text())["items"][0]["source_id"]
        == wall.id
    )
    assert wall.id in (tmp_path / "bill.csv").read_text(encoding="utf-8-sig")


def test_plain_geometry_quantity_tags_and_missing_measurements(qapp):
    d = Document()
    line = LineEntity(Point(0, 0), Point(1500, 0))
    d.undo_stack.push(AddEntityCommand(d, line))
    b = boundary(d, 2000, 1000)
    boq.tag(d, [line.id], "Skirting", measurement="Length")
    boq.tag(d, [b.id], "Concrete pad", measurement="Volume", factor=0.15)
    report = boq.report(d)
    assert report["items"][0]["quantity"] == pytest.approx(1.5)
    assert report["items"][1]["quantity"] == pytest.approx(0.3)
    assert report["unmeasured_ids"] == []
    d.units = "unitless"
    with pytest.raises(ValueError, match="physical"):
        boq.report(d)


def test_unit_conversion_keeps_building_views_and_boq_physical(qapp):
    from pycad.unit_conversion import convert_units

    d = Document()
    slab = building.create_element(d, "slab", boundary(d))
    key = building.build_models(d)[0]
    view = building_views.create_view(
        d, [key], kind="section", axis="Z", offset=50, position=(10000, 0)
    )
    d.mark_saved()
    before = document_to_dict(d)
    rows = boq.report(d)["items"]
    convert_units(d, "m")
    assert d.extensions["building_elements"][slab.id]["thickness"] == pytest.approx(
        0.15
    )
    assert d.extensions["building_views"][view.id]["offset"] == pytest.approx(0.05)
    assert [r["quantity"] for r in boq.report(d)["items"]] == pytest.approx(
        [r["quantity"] for r in rows]
    )
    d.undo_stack.undo()
    assert document_to_dict(d) == before and not d.dirty


def test_ifc_independent_reader_geometry_relationships_and_source_ids(qapp, tmp_path):
    ifc = pytest.importorskip("ifcopenshell")
    from pycad import ifc_export
    import ifcopenshell.geom
    import ifcopenshell.util.shape
    import ifcopenshell.validate

    d = Document()
    slab = building.create_element(d, "slab", boundary(d))
    walls = enclosure(d)
    architecture.create_opening(d, walls[0], 1500)
    auto_rooms.detect_rooms(d)
    building.create_element(d, "roof", d.entities[0])
    building.create_element(d, "stair", layout="L")
    building.set_level(d, "First", 3300)
    file = tmp_path / "building.ifc"
    result = ifc_export.export(d, file)
    assert result["levels"] == 2
    model = ifc.open(str(file))
    assert model.schema == "IFC4" and len(model.by_type("IfcWall")) == 4
    assert (
        len(model.by_type("IfcSpace")) == 1
        and len(model.by_type("IfcRelVoidsElement")) == 1
    )
    assert len(model.by_type("IfcRoof")) == 1 and len(model.by_type("IfcStair")) == 1
    settings = ifcopenshell.geom.settings()
    shape = ifcopenshell.geom.create_shape(settings, model.by_type("IfcSlab")[0])
    assert ifcopenshell.util.shape.get_volume(shape.geometry) == pytest.approx(3.6)
    assert slab.id in file.read_text()
    logger = ifcopenshell.validate.json_logger()
    ifcopenshell.validate.validate(model, logger)
    assert not logger.statements, logger.statements


def test_invalid_building_data_and_rate_changes_are_atomic(qapp):
    d = Document()
    stair = building.create_element(d, "stair")
    d.mark_saved()
    before = document_to_dict(d)
    for values in (
        {"Building.steps": "2.5"},
        {"Building.width": -1},
        {"Building.layout": "Spiral"},
        {"Building.rails": "maybe"},
    ):
        with pytest.raises(ValueError):
            object_properties.apply_values(d, stair, values)
    with pytest.raises(ValueError):
        boq.set_rates(d, {"negative": -1})
    bad = copy.deepcopy(before)
    bad["extensions"]["levels"]["Ground"]["elevation"] = float("nan")
    with pytest.raises(ValueError):
        document_from_dict(bad)
    assert document_to_dict(d) == before and not d.dirty


def test_chat_units_room_plan_and_one_step_undo(qapp):
    d = Document()
    response = drafting_chat.offline(d, "draw a room 6m x 4m")
    assert (
        response["actions"][0]["width"] == 6000
        and response["actions"][0]["depth"] == 4000
    )
    d.mark_saved()
    before = document_to_dict(d)
    count = d.undo_stack.count()
    automation.apply_proposal(d, response["actions"])
    assert (
        len([r for r in d.extensions["architecture"].values() if r["kind"] == "wall"])
        == 4
    )
    assert d.undo_stack.count() == count + 1
    assert "measured items" in drafting_chat.offline(d, "show BOQ")["message"]
    d.undo_stack.undo()
    assert document_to_dict(d) == before and not d.dirty


def test_architectural_chat_aliases_opening_preview_and_atomic_rejection(qapp):
    d = Document()
    actions = [
        dict(
            op="wall",
            ref="@wall",
            start=[0, 0],
            end=[6000, 0],
            width=200,
            height=3000,
            material="Brick",
        ),
        dict(
            op="opening",
            ref="@door",
            wall="@wall",
            station=1500,
            width=900,
            height=2100,
            sill=0,
            type="door",
            identifier="D01",
        ),
    ]
    before = document_to_dict(d)
    clone = automation.prepare_proposal(d, actions)
    assert len(clone.entities) == 2 and document_to_dict(d) == before
    invalid = copy.deepcopy(actions)
    invalid[1]["station"] = 7000
    with pytest.raises(ValueError):
        automation.apply_proposal(d, invalid)
    assert document_to_dict(d) == before
    automation.apply_proposal(d, actions)
    assert len(d.entities) == 2
    d.undo_stack.undo()
    assert document_to_dict(d) == before


def test_chat_dock_proposal_and_changed_drawing_guard(qapp, monkeypatch):
    from pycad.main_window import MainWindow

    w = MainWindow()
    w.resize(1200, 800)
    w.show()
    drafting_chat.show(w)
    qapp.processEvents()
    chat = w.drafting_chat
    before = document_to_dict(w.document)
    chat.prompt.setPlainText("rectangle 1000x500")
    chat.send()
    assert chat.pending and document_to_dict(w.document) == before
    assert 280 <= chat.width() <= 420
    w.document.undo_stack.push(
        AddEntityCommand(w.document, LineEntity(Point(0, 0), Point(100, 0)))
    )
    chat.review()
    assert chat.pending is None and "Drawing changed" in chat.history.toPlainText()
    w.document.mark_saved()
    w.close()


def test_ai_chat_http_schema_context_and_invalid_code_rejection(qapp):
    d = Document()
    wall = architecture.create_wall(d, Point(0, 0), Point(6000, 0))
    value = {
        "message": "Change the wall height",
        "actions": [
            dict(op="properties", ids=[wall.id], values={"Architecture.height": 3600})
        ],
    }
    seen = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            seen["body"] = json.loads(
                self.rfile.read(int(self.headers["Content-Length"]))
            )
            seen["auth"] = self.headers.get("Authorization")
            raw = json.dumps(
                {"choices": [{"message": {"content": json.dumps(value)}}]}
            ).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    endpoint = f"http://127.0.0.1:{server.server_port}/v1/chat/completions"
    try:
        context = drafting_chat.context_for(d, [wall.id])
        result = drafting_chat.request_chat(
            endpoint,
            "session-key",
            "local-model",
            "make selected wall 3.6m high",
            context,
        )
        assert result == value and seen["auth"] == "Bearer session-key"
        assert wall.id in seen["body"]["messages"][1]["content"]
        assert "session-key" not in json.dumps(seen["body"])
        value["actions"] = [{"op": "python", "code": "raise Exception()"}]
        with pytest.raises(ValueError):
            drafting_chat.request_chat(endpoint, "", "model", "do it", context)
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
