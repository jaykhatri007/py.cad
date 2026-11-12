"""Acceptance of the supplied menu guide and the compact interface changes."""

import copy
import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QDialog, QPlainTextEdit
from pycad import appearance, appsettings, textstyles, dxf_io
from pycad.canvas import Snap, CadCanvas
from pycad.document import Document, SetPointCommand
from pycad.geometry import (
    Point,
    LineEntity,
    CircleEntity,
    TextEntity,
    BlockDefinition,
    BlockReferenceEntity,
    DimensionEntity,
)
from pycad.native_io import (
    document_to_dict,
    document_from_dict,
    save_project,
    load_project,
    SCHEMA_VERSION,
)
from pycad.edit_commands import (
    MIME,
    copy_clip,
    prepare_paste,
    PasteCommand,
    find_matches,
    replace_text,
)
from pycad.collaboration import (
    shared_view_html,
    export_shared_view,
    compare_drawings,
    ComparisonDialog,
)
from pycad.constraints import make_constraint, add_constraint, solve, ConstraintError
from pycad.unit_conversion import convert_units
from pycad.managers import LayerPropertiesManager
from pycad.file_workspace import CATEGORIES, purge_candidates, PurgeCommand


def enter(w, text):
    w.command_line.setText(text)
    w._on_command_entered()


def clipboard(w, entities, base=None):
    w.canvas.selected_entities = entities
    copy_clip(w, base=base)
    return bytes(QApplication.clipboard().mimeData().data(MIME))


@pytest.mark.parametrize("theme", appearance.THEMES)
def test_theme_colors_persist_without_changing_drawing(main_window, theme):
    w = main_window
    before = document_to_dict(w.document)
    options = {
        **appearance.DEFAULTS,
        "theme": theme,
        "model": "#123456",
        "paper": "#aabbcc",
        "model3d": "#102030",
        "accent": "#6bb6ee",
    }
    appearance.save(w, options)
    assert appearance.settings() == options
    assert w.canvas.model_background.name() == "#123456"
    assert w.canvas.paper_background.name() == "#aabbcc"
    assert document_to_dict(w.document) == before and not w.document.dirty
    assert ("#172a3d" in w.styleSheet()) == (theme == "Light")


def test_options_cancel_and_apply_snaps(main_window):
    w = main_window
    d = appearance.OptionsDialog(w, True)
    d.theme.setCurrentText("Light")
    d.colors["model"] = "#fafafa"
    d.reject()
    assert appearance.settings() == appearance.DEFAULTS
    d = appearance.OptionsDialog(w, True)
    d.theme.setCurrentText("Midnight")
    d.colors["model"] = "#090a10"
    for name, cb in d.snap_checks.items():
        cb.setChecked(name == "Endpoint")
    d.radius.setValue(8)
    d.spacing.setValue(5)
    d.apply_changes()
    assert w.canvas.snap_modes == {Snap.ENDPOINT} and w.canvas.snap_radius_px == 8
    assert appsettings.get_settings().value("drafting/grid_spacing", type=float) == 5
    d.reject()


def test_menubar_zero_one_and_file_still_accessible(main_window):
    w = main_window
    enter(w, "MENUBAR")
    enter(w, "0")
    assert not w.menuBar().isHidden()
    assert all(not a.isVisible() for a in w.menuBar().actions())
    w.show_file_workspace()
    assert w.file_workspace.isVisible()
    w.file_workspace.hide()
    enter(w, "MENUBAR")
    enter(w, "1")
    assert not w.menuBar().isHidden()
    assert {"Insert", "Format", "Parametric", "Collaborate"} <= {
        a.text().replace("&", "") for a in w.menuBar().actions()
    }


@pytest.mark.parametrize("size", [(1440, 930), (840, 650), (780, 600)])
def test_compact_file_and_layer_panel(main_window, qapp, size):
    w = main_window
    w.resize(*size)
    qapp.processEvents()
    w.show_file_workspace()
    qapp.processEvents()
    p = w.file_workspace
    assert p.width() <= 650 and p.height() <= 490
    assert p.categories.width() <= 145 and p.width() < w.width() - 40
    p.categories.setCurrentRow(CATEGORIES.index("Publish"))
    assert p.scroll.isVisible()
    d = LayerPropertiesManager(w)
    d.show()
    qapp.processEvents()
    assert d.width() <= 760 and d.height() <= 410 and d.table.columnCount() == 9
    assert d.table.verticalHeader().defaultSectionSize() <= 30
    d.reject()


def test_snap_filter_grid_fallback_and_empty_mode(main_window):
    w = main_window
    c = w.canvas
    c.zoom = 10
    c.grid_spacing = 10
    e = LineEntity(Point(1, 1), Point(12, 1))
    w.document.entities = [e]
    c.snap_modes = {Snap.MIDPOINT}
    pt, kind = c.find_snap_point(c.world_to_screen(1, 1))
    assert pt is None
    c.snap_modes = {Snap.ENDPOINT}
    pt, kind = c.find_snap_point(c.world_to_screen(1, 1))
    assert kind == Snap.ENDPOINT
    c.snap_modes = {Snap.GRID}
    pt, kind = c.find_snap_point(c.world_to_screen(20.2, 20.2))
    assert pt.as_tuple() == (20, 20) and kind == Snap.GRID
    c.snap_modes = set()
    assert c.find_snap_point(c.world_to_screen(20, 20)) == (None, None)


def test_malformed_preferences_do_not_prevent_start(main_window):
    s = appsettings.get_settings()
    s.setValue("drafting/snap_radius", "bad")
    s.setValue("drafting/grid_spacing", "nan")
    s.setValue("appearance/theme", "bad")
    s.setValue("appearance/model", "invalid")
    c = CadCanvas(Document())
    assert c.snap_radius_px == 12 and c.grid_spacing == 10
    assert appearance.settings() == appearance.DEFAULTS
    c.deleteLater()


def test_styles_native_legacy_migration_and_unit_conversion(qapp, tmp_path):
    d = Document()
    textstyles.edit_style(
        d,
        "add",
        "Notes",
        {
            **textstyles.DEFAULT_STYLE,
            "font_family": "DejaVu Sans",
            "bold": True,
            "italic": True,
            "width_factor": 1.5,
            "oblique": 15,
            "height": 4,
        },
    )
    textstyles.edit_style(d, "current", "Notes")
    e = textstyles.make_text(d, Point(-10, 4), "café\nRoom 1")
    d.add_entity(e)
    assert e.height == 4 and e.style_name == "Notes"
    path = tmp_path / "styles.pycad"
    save_project(d, path)
    loaded = load_project(path)
    assert document_to_dict(loaded) == document_to_dict(d) and SCHEMA_VERSION == 17
    before = document_to_dict(d)
    convert_units(d, "m")
    assert e.height == pytest.approx(0.004) and d.textstyles["Notes"][
        "height"
    ] == pytest.approx(0.004)
    d.undo_stack.undo()
    assert document_to_dict(d) == before
    legacy = document_to_dict(Document())
    legacy["schema_version"] = 8
    legacy.pop("textstyles")
    legacy.pop("current_textstyle")
    assert document_from_dict(legacy).current_textstyle == "Standard"


@pytest.mark.parametrize(
    "field,value",
    [
        ("height", float("nan")),
        ("width_factor", 0),
        ("oblique", 61),
        ("bold", 1),
        ("font_family", ""),
    ],
)
def test_invalid_text_style_rejected_before_history(qapp, field, value):
    d = Document()
    before = document_to_dict(d)
    with pytest.raises(ValueError):
        textstyles.edit_style(
            d, "add", "Bad", {**textstyles.DEFAULT_STYLE, field: value}
        )
    assert document_to_dict(d) == before and not d.undo_stack.canUndo()


def test_apply_style_delete_in_use_and_undo(main_window):
    w = main_window
    d = w.document
    e = TextEntity(Point(0, 0), "Room")
    d.entities = [e]
    d.sync_associative()
    textstyles.edit_style(
        d, "add", "Wide", {**textstyles.DEFAULT_STYLE, "width_factor": 2}
    )
    w.canvas.selected_entities = [e]
    old = e.bbox()
    textstyles.apply_style(w, "Wide")
    assert e.style_name == "Wide" and e.bbox()[2] > old[2]
    with pytest.raises(ValueError):
        textstyles.edit_style(d, "delete", "Wide")
    w.undo()
    assert e.style_name == "Standard" and e.bbox() == old
    textstyles.edit_style(d, "delete", "Wide")
    assert "Wide" not in d.textstyles


def test_text_edit_dialog_is_undoable_and_cancel_safe(main_window, monkeypatch):
    w = main_window
    d = w.document
    e = TextEntity(Point(-10, -10), "Old")
    d.entities = [e]
    d.sync_associative()
    w.canvas.selected_entities = [e]
    before = document_to_dict(d)

    def accept(dialog):
        dialog.findChild(QPlainTextEdit).setPlainText("New\nFinish")
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(QDialog, "exec", accept)
    textstyles.edit_text(w)
    assert e.text == "New\nFinish"
    w.undo()
    assert document_to_dict(d) == before
    monkeypatch.setattr(QDialog, "exec", lambda _: QDialog.DialogCode.Rejected)
    textstyles.edit_text(w)
    assert document_to_dict(d) == before


def test_formatted_dxf_export_import_and_vector_plot(qapp, tmp_path):
    import ezdxf

    d = Document()
    d.textstyles["Notes"] = {
        **textstyles.DEFAULT_STYLE,
        "font_family": "DejaVu Sans",
        "bold": True,
        "italic": True,
        "width_factor": 1.25,
        "oblique": 12,
    }
    e = TextEntity(
        Point(-10, 10), "Notes\nFinish", height=3, rotation=20, style_name="Notes"
    )
    d.entities = [e]
    d.sync_associative()
    p = tmp_path / "notes.dxf"
    dxf_io.export_dxf(d, str(p))
    source = ezdxf.readfile(p)
    texts = list(source.modelspace().query("TEXT"))
    assert len(texts) == 2 and texts[0].dxf.width == 1.25 and texts[0].dxf.oblique == 12
    imported = dxf_io.import_dxf(str(p))
    s = imported.textstyles[imported.entities[0].style_name]
    assert (
        s["bold"] and s["italic"] and s["width_factor"] == 1.25 and s["oblique"] == 12
    )
    page = shared_view_html(d)
    assert "Notes" in page and "<svg" in page and "<image" not in page
    from pycad.plotting import export_pdf

    fitz = pytest.importorskip("fitz")
    pdf = tmp_path / "notes.pdf"
    export_pdf(d, str(pdf))
    with fitz.open(pdf) as output:
        assert "Notes" in output[0].get_text() and "Finish" in output[0].get_text()
        for block in output[0].get_text("dict")["blocks"]:
            if block["type"] == 0:
                assert output[0].rect.contains(fitz.Rect(block["bbox"]))


def test_clipboard_paste_fresh_ids_named_tables_and_undo(main_window):
    w = main_window
    d = w.document
    d.textstyles["Notes"] = {**textstyles.DEFAULT_STYLE, "bold": True}
    e = TextEntity(Point(10, 20), "Room", style_name="Notes")
    d.entities = [e]
    d.sync_associative()
    raw = clipboard(w, [e], Point(10, 20))
    d.textstyles["Notes"]["bold"] = False
    before = document_to_dict(d)
    imported, tables = prepare_paste(d, raw, Point(100, 200))
    command = PasteCommand(d, imported, tables)
    d.undo_stack.push(command)
    new = command.items[0]
    assert new.id != e.id and new.position.as_tuple() == (100, 200)
    assert new.style_name == "Notes_1" and d.textstyles["Notes_1"]["bold"]
    d.undo_stack.undo()
    assert document_to_dict(d) == before and d.entities[0] is e
    d.undo_stack.redo()
    assert d.entities[-1] is new


def test_clipboard_cross_units_block_and_association_remapping(main_window):
    w = main_window
    source = w.document
    line = LineEntity(Point(0, 0), Point(1000, 0))
    dim = DimensionEntity(
        Point(0, 0), Point(1000, 0), Point(500, 100), source_line_id=line.id
    )
    source.blocks["Part"] = BlockDefinition("Part", [CircleEntity(Point(0, 0), 100)])
    ref = BlockReferenceEntity("Part", Point(1000, 1000))
    source.entities = [line, dim, ref]
    source.sync_associative()
    raw = clipboard(w, source.entities, Point(0, 0))
    target = Document()
    target.units = "m"
    target.blocks["Part"] = BlockDefinition("Part", [])
    imported, tables = prepare_paste(target, raw, Point(10, 20))
    target.undo_stack.push(PasteCommand(target, imported, tables))
    a, b, c = target.entities
    assert a.p2.as_tuple() == (11, 20) and b.source_line_id == a.id
    assert c.block_name == "Part_1" and c.resolved_entities[0].radius == pytest.approx(
        0.1
    )
    assert document_from_dict(document_to_dict(target))


def test_clipboard_internal_fixed_tangent_constraints_translate(main_window):
    w = main_window
    d = w.document
    a = LineEntity(Point(0, 0), Point(10, 0))
    b = CircleEntity(Point(5, 2), 2)
    d.entities = [a, b]
    for kind, items in [("fixed", [a]), ("tangent", [a, b])]:
        assert add_constraint(
            d, make_constraint(d, kind, [{"entity": e.id} for e in items])
        )
    raw = clipboard(w, [a, b], Point(0, 0))
    target = Document()
    imported, tables = prepare_paste(target, raw, Point(100, 200))
    target.undo_stack.push(PasteCommand(target, imported, tables))
    assert len(target.constraints) == 2 and target.constraints[0]["fixed"] == [
        100,
        200,
        110,
        200,
    ]
    assert solve(target, check_only=True)["residual"] < 1e-5


def test_cut_undo_and_typed_paste(main_window):
    w = main_window
    e = LineEntity(Point(0, 0), Point(10, 0))
    w.document.entities = [e]
    w.canvas.selected_entities = [e]
    w.run_ribbon_command("CUTCLIP")
    assert not w.document.entities
    w.undo()
    assert w.document.entities == [e]
    enter(w, "PASTE")
    enter(w, "40,50")
    assert len(w.document.entities) == 2
    assert w.document.entities[-1].p1.as_tuple() == (40, 50)


@pytest.mark.parametrize(
    "raw",
    [b"bad", b"{}", b"[]", b'{"format":"PyCAD clipboard","base":[0,0],"drawing":{}}'],
)
def test_bad_clipboard_atomic(qapp, raw):
    d = Document()
    before = document_to_dict(d)
    with pytest.raises(ValueError):
        prepare_paste(d, raw, Point(0, 0))
    assert document_to_dict(d) == before and not d.undo_stack.canUndo()


def test_line_edit_copy_paste_keeps_native_text_shortcuts(main_window, qapp):
    w = main_window
    e = LineEntity(Point(0, 0), Point(10, 0))
    w.document.entities = [e]
    w.canvas.selected_entities = [e]
    w.command_line.setText("typed input")
    w.command_line.setFocus()
    w.command_line.selectAll()
    qapp.processEvents()
    QTest.keyClick(w.command_line, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
    assert (
        QApplication.clipboard().text() == "typed input"
        and not QApplication.clipboard().mimeData().hasFormat(MIME)
    )
    w.command_line.clear()
    QTest.keyClick(w.command_line, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
    assert w.command_line.text() == "typed input" and w.document.entities == [e]


def test_find_replace_unicode_literal_and_locked_layer_undo(main_window):
    w = main_window
    d = w.document
    d.layers.add_layer("Locked")
    d.layers.layers["Locked"]["locked"] = True
    a = TextEntity(Point(-10, -10), "Café Room ROOM")
    b = TextEntity(Point(0, 0), "room", layer="Locked")
    d.entities = [a, b]
    d.sync_associative()
    assert find_matches(d, "ROOM") == [a, b]
    before = document_to_dict(d)
    assert (
        replace_text(w, "room", r"\1 literal") == 1
        and a.text == r"Café \1 literal \1 literal"
        and b.text == "room"
    )
    w.undo()
    assert document_to_dict(d) == before


def test_purge_text_and_mleader_styles_and_undo(qapp):
    from pycad.mleaders import DEFAULT_STYLE as MLSTYLE

    d = Document()
    d.textstyles["Unused"] = copy.deepcopy(textstyles.DEFAULT_STYLE)
    d.mleaderstyles["Unused"] = copy.deepcopy(MLSTYLE)
    before = document_to_dict(d)
    c = purge_candidates(d)
    assert c["textstyles"] == ["Unused"] and c["mleaderstyles"] == ["Unused"]
    d.undo_stack.push(PurgeCommand(d, c))
    assert "Unused" not in d.textstyles and "Unused" not in d.mleaderstyles
    d.undo_stack.undo()
    assert document_to_dict(d) == before


@pytest.mark.parametrize("pair", [("line", False), ("circle", False), ("circle", True)])
def test_tangent_solver_persists_and_undoes_edits(qapp, tmp_path, pair):
    kind, internal = pair
    d = Document()
    a = (
        LineEntity(Point(0, 0), Point(10, 0))
        if kind == "line"
        else CircleEntity(Point(0, 0), 5)
    )
    b = (
        CircleEntity(Point(4, 3), 2)
        if kind == "line"
        else CircleEntity(Point(2 if internal else 9, 0), 2)
    )
    d.entities = [a, b]
    c = make_constraint(d, "tangent", [{"entity": a.id}, {"entity": b.id}])
    assert add_constraint(d, c)
    assert c["mode"] == (
        "left" if kind == "line" else "internal" if internal else "external"
    )
    before = document_to_dict(d)
    d.undo_stack.push(
        SetPointCommand(
            d, b.center, b.center.as_tuple(), (b.center.x + 1, b.center.y + 1)
        )
    )
    assert solve(d, check_only=True)["residual"] < 1e-5
    d.undo_stack.undo()
    assert document_to_dict(d) == before
    p = tmp_path / "tangent.pycad"
    save_project(d, p)
    assert load_project(p).constraints == d.constraints


def test_degenerate_internal_tangent_rejected(qapp):
    d = Document()
    a = CircleEntity(Point(0, 0), 5)
    b = CircleEntity(Point(0, 0), 5)
    d.entities = [a, b]
    with pytest.raises(ConstraintError):
        make_constraint(d, "tangent", [{"entity": a.id}, {"entity": b.id}])
    assert not d.constraints and not d.undo_stack.canUndo()


def test_shared_html_escape_self_contained_and_unchanged(qapp, tmp_path):
    from PyQt6.QtGui import QImage, QColor
    from pycad.underlays import read_underlay

    d = Document()
    d.entities = [
        TextEntity(Point(0, 0), "<script> & __UNITS__"),
        LineEntity(Point(0, 0), Point(10, 10)),
    ]
    image = QImage(20, 20, QImage.Format.Format_RGB32)
    image.fill(QColor("#cc5500"))
    image_path = tmp_path / "embedded.png"
    assert image.save(str(image_path))
    d.underlays = [read_underlay(image_path)]
    image_path.unlink()
    d.sync_associative()
    before = document_to_dict(d)
    page = shared_view_html(d, "<script>Title</script>")
    assert (
        "<title>&lt;script&gt;Title&lt;/script&gt;</title>" in page and "<svg" in page
    )
    assert "__UNITS__" in page and 'src="http' not in page and 'href="http' not in page
    assert "<text" in page and "&lt;script&gt;" in page
    assert "<image" in page and "data:image/png;base64," in page
    assert "<title>__SVG__</title>" in shared_view_html(d, "__SVG__")
    p = tmp_path / "view.html"
    export_shared_view(d, p)
    assert p.stat().st_size > 1000
    assert document_to_dict(d) == before and not d.undo_stack.canUndo()


def test_compare_added_removed_changed_foreign_ids_and_cleanup(main_window):
    w = main_window
    d = w.document
    line = LineEntity(Point(0, 0), Point(10, 0))
    text = TextEntity(Point(0, 10), "old")
    d.entities = [line, text]
    d.sync_associative()
    old = document_from_dict(document_to_dict(d))
    text.text = "new"
    d.entities.append(CircleEntity(Point(20, 20), 3))
    d.sync_associative()
    before = document_to_dict(d)
    r = compare_drawings(d, old)
    assert r["changed"] == [text.id] and len(r["added"]) == 1 and not r["removed"]
    dialog = ComparisonDialog(w, old)
    assert len(w.canvas.comparison_overlay) == 2
    dialog.reject()
    assert not w.canvas.comparison_overlay and document_to_dict(d) == before
    foreign = Document()
    foreign.entities = [e.clone() for e in d.entities]
    foreign.sync_associative()
    r = compare_drawings(d, foreign)
    assert not r["added"] and not r["removed"] and len(r["unchanged"]) == 3
    foreign.units = "m"
    with pytest.raises(ValueError):
        compare_drawings(d, foreign)
