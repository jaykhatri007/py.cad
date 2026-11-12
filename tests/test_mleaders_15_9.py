"""Native multileader drafting, history, persistence and output acceptance."""

import math
import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QInputDialog
from pycad.document import Document, SetPointCommand, ScaleEntitiesCommand
from pycad.geometry import Point, BlockDefinition, BlockReferenceEntity
from pycad.mleaders import (
    MultileaderEntity,
    DEFAULT_STYLE,
    validate_style,
    validate_text,
    edit_branches,
    edit_style,
)
from pycad.mleader_tools import edit_text, apply_style
from pycad.native_io import (
    document_to_dict,
    document_from_dict,
    save_project,
    load_project,
)
from pycad.unit_conversion import convert_units
from pycad.geom_ops import distance_to_entity
from pycad.ribbon_actions import selection_document
from pycad.measurements import measurement_for


def annotation(doc, branches=1, style_name="Standard"):
    e = MultileaderEntity(
        Point(30, 12),
        "ROOM 01\nPaint finish",
        [[Point(0, i * 20), Point(12, 12 + i * 10)] for i in range(branches)],
        style_name=style_name,
    )
    doc.entities = [e]
    doc.sync_associative()
    return e


def click(w, x, y):
    w._on_world_clicked(x, y, "", Qt.MouseButton.LeftButton.value)


def enter(w, text):
    w.command_line.setText(text)
    w._on_command_entered()


def test_create_native_multiline_current_style_and_reopen(
    main_window, monkeypatch, tmp_path
):
    w = main_window
    edit_style(w.document, "add", "Notes", {**DEFAULT_STYLE, "text_height": 3.5})
    edit_style(w.document, "current", "Notes")
    monkeypatch.setattr(
        QInputDialog, "getMultiLineText", lambda *a: ("Wall\nFinish — café", True)
    )
    enter(w, "ML")
    for text in ("0,0", "@10,10", "@20,0"):
        enter(w, text)
    e = w.document.entities[0]
    assert e.kind == "MLEADER" and not w.document.blocks
    assert e.leaders[0][1].as_tuple() == (10, 10)
    assert e.position.as_tuple() == (30, 10) and e.style_name == "Notes"
    assert e.geometry()[2][0][2] == 3.5
    save_project(w.document, tmp_path / "notes.pycad")
    loaded = load_project(tmp_path / "notes.pycad")
    assert document_to_dict(loaded) == document_to_dict(w.document)
    w.undo()
    assert not w.document.entities
    w.redo()
    assert w.document.entities[0] is e


def test_cancel_dialog_and_escape_leave_no_partial_annotation(main_window, monkeypatch):
    w = main_window
    monkeypatch.setattr(QInputDialog, "getMultiLineText", lambda *a: ("", False))
    w.set_tool("MLEADER")
    for x, y in ((0, 0), (10, 10), (30, 10)):
        click(w, x, y)
    assert not w.document.entities and not w.document.undo_stack.canUndo()
    w.set_tool("MLEADER")
    click(w, 0, 0)
    w.cancel_command()
    assert not w.document.entities


def test_degenerate_tip_elbow_rejected_before_dialog(main_window):
    w = main_window
    w.set_tool("MLEADER")
    enter(w, "0,0")
    enter(w, "0,0")
    assert len(w.current_tool.points) == 1
    assert "must differ" in w.command_history.toPlainText()


def test_add_remove_branches_preserves_text_identity_and_undo(main_window):
    w = main_window
    e = annotation(w.document)
    original = document_to_dict(w.document)
    w.canvas.selected_entities = [e]
    w.run_ribbon_command("MLEADERADD")
    assert w.current_tool.target is e
    enter(w, "0,40")
    enter(w, "12,30")
    assert len(e.leaders) == 2 and e.text == "ROOM 01\nPaint finish"
    w.undo()
    assert document_to_dict(w.document) == original
    w.redo()
    w.canvas.selected_entities = [e]
    w.set_tool("MLEADERREMOVE")
    click(w, 0, 40)
    assert len(e.leaders) == 1 and e.leaders[0][0].y == 0
    w.undo()
    assert len(e.leaders) == 2 and w.document.entities[0] is e
    w.redo()
    assert len(e.leaders) == 1


def test_branch_tool_can_pick_without_preselection(main_window):
    w = main_window
    e = annotation(w.document)
    w.canvas.zoom = 10
    w.canvas.selected_entities = []
    w.set_tool("MLEADERADD")
    click(w, 2, 2)
    assert w.current_tool.target is e
    click(w, 0, 40)
    click(w, 15, 30)
    assert len(e.leaders) == 2


def test_last_branch_rejected_and_missed_branch_does_not_remove(main_window):
    w = main_window
    e = annotation(w.document)
    w.canvas.selected_entities = [e]
    w.set_tool("MLEADERREMOVE")
    click(w, 0, 0)
    assert len(e.leaders) == 1 and "ERASE" in w.command_history.toPlainText()
    edit_branches(w.document, e, e.leaders + [[Point(0, 40), Point(12, 30)]], "Add")
    click(w, -500, -500)
    assert len(e.leaders) == 2


@pytest.mark.parametrize("state", ["locked", "frozen", "visible"])
def test_branch_and_text_edits_respect_layer_state(main_window, state, monkeypatch):
    w = main_window
    e = annotation(w.document)
    w.canvas.selected_entities = [e]
    w.set_tool("MLEADERADD")
    w.document.layers.layers["0"][state] = state != "visible"
    with pytest.raises(ValueError):
        w.current_tool.on_click(10, 50, "", 1)
    with pytest.raises(ValueError):
        edit_branches(w.document, e, e.leaders, "Edit")
    with pytest.raises(ValueError):
        edit_text(w)
    assert len(e.leaders) == 1


def test_text_edit_undo_cancel_and_invalid_text(main_window, monkeypatch):
    w = main_window
    e = annotation(w.document)
    old = e.text
    w.canvas.selected_entities = [e]
    monkeypatch.setattr(
        QInputDialog, "getMultiLineText", lambda *a: ("NEW\nLiteral {\\P}", True)
    )
    w.run_ribbon_command("MLEADEREDIT")
    assert e.text == "NEW\nLiteral {\\P}"
    w.undo()
    assert e.text == old
    w.redo()
    monkeypatch.setattr(QInputDialog, "getMultiLineText", lambda *a: ("", False))
    edit_text(w)
    assert e.text == "NEW\nLiteral {\\P}"
    count = w.document.undo_stack.count()
    monkeypatch.setattr(QInputDialog, "getMultiLineText", lambda *a: (" ", True))
    with pytest.raises(ValueError):
        edit_text(w)
    assert w.document.undo_stack.count() == count


def test_style_changes_propagate_to_annotations_and_undo(qapp):
    doc = Document()
    e = annotation(doc)
    bounds = e.bbox()
    edit_style(
        doc,
        "modify",
        "Standard",
        {**DEFAULT_STYLE, "text_height": 6, "arrow_type": "Open"},
    )
    assert e.bbox()[2] > bounds[2] and not e.geometry()[1]
    doc.undo_stack.undo()
    assert e.bbox() == bounds and e.geometry()[1]
    doc.undo_stack.redo()
    assert e.geometry()[2][0][2] == 6


def test_style_current_and_reference_deletion_guards(qapp):
    doc = Document()
    edit_style(doc, "add", "Notes")
    with pytest.raises(ValueError):
        edit_style(doc, "add", "notes")
    edit_style(doc, "current", "Notes")
    with pytest.raises(ValueError):
        edit_style(doc, "delete", "Notes")
    edit_style(doc, "current", "Standard")
    e = annotation(doc, style_name="Notes")
    doc.blocks["NoteBlock"] = BlockDefinition("NoteBlock", [e.clone()])
    doc.entities = []
    with pytest.raises(ValueError):
        edit_style(doc, "delete", "Notes")
    doc.blocks.clear()
    edit_style(doc, "delete", "Notes")
    assert "Notes" not in doc.mleaderstyles
    doc.undo_stack.undo()
    assert "Notes" in doc.mleaderstyles


def test_apply_style_only_edits_unlocked_selection_as_one_undo(main_window):
    w = main_window
    e = annotation(w.document)
    locked = e.clone()
    w.document.layers.add_layer("Locked")
    w.document.layers.layers["Locked"]["locked"] = True
    locked.layer = "Locked"
    w.document.entities.append(locked)
    edit_style(w.document, "add", "Notes", {**DEFAULT_STYLE, "text_height": 5})
    w.canvas.selected_entities = [e, locked]
    apply_style(w, "Notes")
    assert e.style_name == "Notes" and locked.style_name == "Standard"
    w.undo()
    assert e.style_name == "Standard"


def test_schema8_nested_points_and_legacy_defaults(qapp):
    doc = Document()
    e = annotation(doc, 2)
    e.rotation = 37
    payload = document_to_dict(doc)
    from pycad.native_io import SCHEMA_VERSION
    assert payload["schema_version"] == SCHEMA_VERSION
    assert "_mleader_style" not in payload["entities"][0]["data"]
    restored = document_from_dict(payload)
    assert document_to_dict(restored) == payload
    legacy = document_to_dict(Document())
    legacy["schema_version"] = 7
    del legacy["mleaderstyles"], legacy["current_mleaderstyle"]
    old = document_from_dict(legacy)
    assert old.mleaderstyles == {"Standard": DEFAULT_STYLE}


@pytest.mark.parametrize(
    "field,value",
    [
        ("leaders", []),
        ("leaders", [[{"point": [0, 0]}]]),
        ("leaders", [[{"point": [0, 0]}, {"point": [0, 0]}]]),
        ("leaders", [[{"point": [math.nan, 0]}, {"point": [10, 10]}]]),
        ("style_name", "Missing"),
        ("style_name", []),
        ("scale", 0),
        ("scale", math.inf),
        ("rotation", math.nan),
        ("text", ""),
        ("text", "A\x00B"),
        ("text", "x" * 257),
        ("text", "x\n" * 128),
    ],
)
def test_malformed_native_mleaders_are_rejected(qapp, field, value):
    doc = Document()
    annotation(doc)
    payload = document_to_dict(doc)
    payload["entities"][0]["data"][field] = value
    with pytest.raises(ValueError):
        document_from_dict(payload)


@pytest.mark.parametrize(
    "key,value",
    [
        ("text_height", 0),
        ("scale", -1),
        ("text_gap", math.inf),
        ("arrow_type", "Bogus"),
        ("color", "red"),
        ("arrow_size", True),
    ],
)
def test_style_validation_rejects_invalid_inputs(key, value):
    with pytest.raises(ValueError):
        validate_style({**DEFAULT_STYLE, key: value})


def test_branch_limit_and_style_overflow_reject_without_history_change(qapp):
    doc = Document()
    e = annotation(doc, 64)
    before = document_to_dict(doc)
    with pytest.raises(ValueError):
        edit_branches(doc, e, e.leaders + [[Point(0, 2), Point(1, 3)]], "Add")
    with pytest.raises(ValueError):
        edit_style(
            doc,
            "modify",
            "Standard",
            {**DEFAULT_STYLE, "text_height": 1e6, "scale": 1e6},
        )
    assert document_to_dict(doc) == before and not doc.undo_stack.canUndo()


def test_constructor_and_clone_do_not_share_grip_points(qapp):
    point = Point(0, 0)
    e = MultileaderEntity(point, "Tag", [[point, Point(10, 10)]])
    e.position.x = 3
    assert point.x == 0 and e.leaders[0][0].x == 0
    clone = e.clone()
    clone.leaders[0][0].x = 9
    assert e.leaders[0][0].x == 0 and clone.id != e.id


def test_hit_testing_uses_text_and_branches_not_empty_bbox(qapp):
    doc = Document()
    e = annotation(doc)
    assert distance_to_entity(Point(5, 5), e) == pytest.approx(0)
    assert distance_to_entity(Point(34, 13), e) == 0
    assert distance_to_entity(Point(2, 10), e) > 1
    e.rotate_around(Point(0, 0), 90)
    assert distance_to_entity(Point(-13, 34), e) == 0


def test_grips_edit_undo_and_prevent_collapsed_branch(main_window):
    w = main_window
    e = annotation(w.document)
    w.canvas.zoom = 10
    w.canvas.selected_entities = [e]
    w.set_tool("SELECT")
    click(w, 0, 0)
    w.current_tool.on_move(-5, 2, "")
    w.current_tool.finish_drag()
    assert e.leaders[0][0].as_tuple() == (-5, 2)
    w.undo()
    assert e.leaders[0][0].as_tuple() == (0, 0)
    w.redo()
    click(w, -5, 2)
    w.current_tool.on_move(12, 12, "")
    w.current_tool.finish_drag()
    assert e.leaders[0][0].as_tuple() == (-5, 2)


def test_grip_history_resolves_points_after_branch_list_replacement(qapp):
    doc = Document()
    e = annotation(doc)
    doc.undo_stack.push(SetPointCommand(doc, e.leaders[0][0], (0, 0), (-2, 0)))
    edit_branches(doc, e, e.leaders + [[Point(0, 40), Point(12, 30)]], "Add")
    doc.undo_stack.undo()
    doc.undo_stack.undo()
    assert e.leaders[0][0].as_tuple() == (0, 0)
    doc.undo_stack.redo()
    doc.undo_stack.redo()
    assert e.leaders[0][0].as_tuple() == (-2, 0) and len(e.leaders) == 2


def test_rotate_mirror_scale_and_rotated_extents(qapp):
    doc = Document()
    e = annotation(doc, 2)
    old = document_to_dict(doc)
    e.rotate_around(Point(0, 0), 45)
    e.reflect_across(Point(0, 0), Point(10, 0))
    assert e.rotation == 315
    doc.undo_stack.push(ScaleEntitiesCommand(doc, [e], Point(0, 0), 2))
    assert e.scale == 2 and e.geometry()[2][0][2] == 5
    x0, y0, x1, y1 = e.bbox()
    assert all(
        x0 <= p.x <= x1 and y0 <= p.y <= y1 for poly in e.label_polygons() for p in poly
    )
    doc.undo_stack.undo()
    e.reflect_across(Point(0, 0), Point(10, 0))
    e.rotate_around(Point(0, 0), -45)
    assert e.position.as_tuple() == pytest.approx((30, 12))
    assert e.rotation == old["entities"][0]["data"]["rotation"]


def test_physical_unit_conversion_scales_styles_once_and_undo_grips(qapp):
    doc = Document()
    e = annotation(doc, 2)
    e.scale = 2
    original = document_to_dict(doc)
    doc.undo_stack.push(SetPointCommand(doc, e.position, (30, 12), (35, 15)))
    convert_units(doc, "m")
    assert e.position.as_tuple() == pytest.approx((0.035, 0.015))
    assert e.scale == 2 and e.geometry()[2][0][2] == pytest.approx(0.005)
    assert doc.mleaderstyles["Standard"]["landing_length"] == pytest.approx(0.004)
    doc.undo_stack.undo()
    doc.undo_stack.undo()
    assert document_to_dict(doc) == original
    doc.undo_stack.redo()
    doc.undo_stack.redo()
    assert e.position.x == pytest.approx(0.035)


def test_selection_and_block_roundtrip_retain_named_styles(qapp):
    doc = Document()
    edit_style(doc, "add", "Notes", {**DEFAULT_STYLE, "text_height": 4})
    e = annotation(doc, 2, "Notes")
    selected = selection_document(doc, [e])
    assert selected.entities[0].style_name == "Notes"
    assert selected.mleaderstyles == doc.mleaderstyles
    doc.blocks["Tag"] = BlockDefinition("Tag", [e.clone()])
    ref = BlockReferenceEntity("Tag", Point(100, 0), scale=2)
    doc.entities = [ref]
    doc.sync_associative()
    assert ref.resolved_entities[0].geometry()[2][0][2] == 8
    restored = document_from_dict(document_to_dict(doc))
    assert restored.entities[0].resolved_entities[0].geometry()[2][0][2] == 8


def test_block_editor_carries_styles_and_edits_multileader_grips(main_window):
    from pycad.block_editor import BlockEditorDialog

    w = main_window
    edit_style(w.document, "add", "Notes", {**DEFAULT_STYLE, "text_height": 4})
    e = annotation(w.document, 2, "Notes")
    block = BlockDefinition("Tag", [e.clone()])
    w.document.blocks["Tag"] = block
    editor = BlockEditorDialog(w, "Tag", block)
    try:
        assert editor.document.mleaderstyles == w.document.mleaderstyles
        item = editor.document.entities[0]
        assert item.geometry()[2][0][2] == 4
        editor.document.undo_stack.push(
            SetPointCommand(editor.document, item.position, (30, 12), (35, 15))
        )
        editor.accept()
        assert block.entities[0].position.as_tuple() == (35, 15)
    finally:
        editor.setParent(None)
        editor.deleteLater()


@pytest.mark.parametrize(
    "table,value",
    [
        ("current_mleaderstyle", []),
        ("mleaderstyles", []),
        ("current_mleaderstyle", "Missing"),
        ("mleaderstyles", {"Notes": DEFAULT_STYLE}),
    ],
)
def test_invalid_native_style_tables_rejected(qapp, table, value):
    payload = document_to_dict(Document())
    payload[table] = value
    with pytest.raises(ValueError):
        document_from_dict(payload)


def test_pdf_and_dxf_output_contains_text_arrows_and_style_color(qapp, tmp_path):
    import ezdxf
    import fitz
    from pycad import dxf_io
    from pycad.plotting import export_pdf, plot_bounds

    doc = Document()
    e = annotation(doc, 2)
    e.hyperlink = "https://example.com/note"
    e.transparency = 40
    edit_style(doc, "modify", "Standard", {**DEFAULT_STYLE, "color": "#AA5500"})
    e.rotation = 25
    pdf = tmp_path / "notes.pdf"
    export_pdf(doc, pdf)
    with fitz.open(pdf) as rendered:
        page = rendered[0]
        assert "ROOM" in page.get_text() and "Paint" in page.get_text()
        assert len(page.get_drawings()) >= 8
        assert all(
            page.rect.contains(fitz.Rect(block[:4]))
            for block in page.get_text("blocks")
        )
    assert plot_bounds(doc, e, QFont()) == e.bbox()
    dxf = tmp_path / "notes.dxf"
    dxf_io.export_dxf(doc, dxf)
    entities = list(ezdxf.readfile(dxf).modelspace())
    assert sum(e.dxftype() == "SOLID" for e in entities) == 2
    assert [e.dxf.text for e in entities if e.dxftype() == "TEXT"] == [
        "ROOM 01",
        "Paint finish",
    ]
    assert all(e.dxf.true_color == 0xAA5500 for e in entities)
    assert all(e.get_hyperlink()[0] == "https://example.com/note" for e in entities)
    assert all(e.dxf.hasattr("transparency") for e in entities)
    assert any(
        "branch editing require .pycad" in warning
        for warning in dxf_io.export_warnings(doc)
    )


@pytest.mark.parametrize(
    "arrow_type,arrow_size,fill_count,line_count",
    [
        ("Closed", 2.5, 1, 3),
        ("Open", 2.5, 0, 5),
        ("None", 2.5, 0, 3),
        ("Closed", 0, 0, 3),
    ],
)
def test_arrow_variants_share_geometry(
    qapp, arrow_type, arrow_size, fill_count, line_count
):
    doc = Document()
    e = annotation(doc)
    edit_style(
        doc,
        "modify",
        "Standard",
        {**DEFAULT_STYLE, "arrow_type": arrow_type, "arrow_size": arrow_size},
    )
    lines, fills, _ = e.geometry()
    assert len(lines) == line_count and len(fills) == fill_count


@pytest.mark.parametrize("property", ["visible", "plot"])
def test_hidden_or_nonplotting_multileader_omitted_from_pdf(qapp, tmp_path, property):
    import fitz
    from pycad.geometry import TextEntity
    from pycad.plotting import export_pdf

    doc = Document()
    e = annotation(doc)
    doc.layers.add_layer("Notes")
    e.layer = "Notes"
    doc.layers.layers["Notes"][property] = False
    doc.entities.append(TextEntity(Point(0, 0), "BASE DRAWING", 2.5))
    pdf = tmp_path / "filtered.pdf"
    export_pdf(doc, pdf)
    with fitz.open(pdf) as output:
        assert "BASE DRAWING" in output[0].get_text()
        assert "ROOM" not in output[0].get_text()


def test_style_manager_preview_save_current_apply_and_history(
    main_window, qapp, monkeypatch
):
    from pycad.mleader_ui import MultileaderStyleManager

    w = main_window
    e = annotation(w.document)
    w.canvas.selected_entities = [e]
    dialog = MultileaderStyleManager(w)
    try:
        dialog.show()
        qapp.processEvents()
        assert not dialog.preview.grab().isNull()
        monkeypatch.setattr(QInputDialog, "getText", lambda *a: ("Notes", True))
        dialog.add()
        dialog.fields["text_height"].setValue(5)
        dialog.save()
        dialog.set_current()
        dialog.apply()
        assert w.document.current_mleaderstyle == "Notes" and e.style_name == "Notes"
        assert e.geometry()[2][0][2] == 5
        w.undo()
        assert e.style_name == "Standard"
    finally:
        dialog.close()
        dialog.setParent(None)
        dialog.deleteLater()


def test_ribbon_commands_properties_and_measurement_preview(main_window):
    from pycad.ribbon_catalog import TOOLS

    w = main_window
    e = annotation(w.document)
    w.canvas.selected_entities = [e]
    w.properties_panel.refresh()
    assert w.properties_panel.mleader_text.isEnabled()
    assert "Branches: 1" in w.properties_panel.info.text()
    assert w.properties_panel.info.textFormat() == Qt.TextFormat.PlainText
    assert all(
        TOOLS[name].status != "planned"
        for name in ("MLEADERADD", "MLEADERREMOVE", "MLEADERSTYLE", "MLEADEREDIT")
    )
    assert "MLEADERSTYLE" in w.command_matches("MLEADERS")
    w.set_tool("MLEADER")
    enter(w, "0,0")
    m = measurement_for(w.current_tool, (3, 4))
    assert m.values[0][:2] == ("Arrow leg", 5)
    validate_text("Unicode café — {plain} \\P")
