"""Workflow checks for the spreadsheet-driven ribbon and additional commands."""

import csv
import io
import zipfile
import pytest
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QToolButton, QMenu, QInputDialog, QFileDialog, QDialog

from pycad.geometry import (
    Point,
    LineEntity,
    CircleEntity,
    TextEntity,
    DimensionEntity,
    BlockDefinition,
    BlockReferenceEntity,
)
from pycad.document import Document
from pycad.native_io import (
    document_to_dict,
    document_from_dict,
    save_project,
    load_project,
)
from pycad.ribbon_catalog import PANELS, TABS, TOOLS
from pycad import ribbon_actions as actions, dxf_io
from pycad.drafting_extras import table_geometry, entity_metrics


def click(w, x, y):
    w.current_tool.on_click(x, y, "", Qt.MouseButton.LeftButton.value)


def enter(w, text):
    w.command_line.setText(text)
    w._on_command_entered()


def test_spreadsheet_tabs_panels_and_support_matrix(main_window, qapp):
    w = main_window
    assert tuple(w.ribbon.tabText(i) for i in range(w.ribbon.count())) == TABS
    assert len(PANELS) == 31 and {r for _, _, r, _ in PANELS} == set(range(2, 33))
    assert w.ribbon.height() == 112
    represented = {
        b.property("command")
        for b in w.ribbon.findChildren(QToolButton)
        if b.property("command")
    }
    represented |= {a.data() for m in w.ribbon.findChildren(QMenu) for a in m.actions()}
    assert represented == set(TOOLS)
    from pycad.constraint_ui import commands as constraint_commands
    from pycad.project_tools import commands as project_commands
    from pycad.underlays import commands as underlay_commands
    from pycad.mleader_ui import commands as mleader_commands
    from pycad.appearance import commands as appearance_commands
    from pycad.edit_commands import commands as edit_commands
    from pycad.collaboration import commands as collaboration_commands
    from pycad.feature_ui import commands as feature_commands
    from pycad.productivity_ui import commands as productivity_commands
    handlers = set(productivity_commands(w)) | set(feature_commands(w)) | set(appearance_commands(w)) | set(edit_commands(w)) | set(collaboration_commands(w)) | {'STYLE', 'TEXTEDIT'} | set(mleader_commands(w)) | set(underlay_commands(w)) | set(actions.commands(w)) | set(constraint_commands(w)) | set(project_commands(w)) | set(
        __import__("pycad.main_window", fromlist=["TOOL_REGISTRY"]).TOOL_REGISTRY
    )
    builtins = {
        "UNITS",
        "DYNMODE",
        "LAYER",
        "DIMSTYLE",
        "ERASE",
        "EXTRUDE",
        "VPORTS",
        "3DORBIT",
        "PLAN",
        "TOP",
        "BOTTOM",
        "FRONT",
        "BACK",
        "LEFT",
        "RIGHT",
        "ISOMETRIC",
    }
    assert {k for k, v in TOOLS.items() if v.status != "planned"} <= handlers | builtins
    for button in w.ribbon.findChildren(QToolButton):
        if button.property("command"):
            assert button.isEnabled() == (
                TOOLS[button.property("command")].status != "planned"
            )
            assert button.toolTip() and button.accessibleName()
    w.ribbon.setCurrentIndex(3)
    enter(w, "CUI")
    assert "full CUI editor" in w.command_history.toPlainText()
    assert not w.document.entities


def test_ribbon_overflow_and_compact_persistence(main_window, qapp):
    w = main_window
    w.resize(780, 600)
    qapp.processEvents()
    assert w.ribbon.widget(0).horizontalScrollBar().maximum() > 0
    w.ribbon.set_compact(True)
    qapp.processEvents()
    assert w.ribbon.height() == 66
    from pycad.ribbon import Ribbon

    other = Ribbon(w)
    assert other.compact
    other.deleteLater()
    w.ribbon.set_compact(False)
    assert w.ribbon.height() == 112


def test_stretch_crossing_vertices_locked_objects_and_undo(main_window):
    w = main_window
    d = w.document
    line = LineEntity(Point(0, 0), Point(10, 0))
    circle = CircleEntity(Point(10, 2), 0.5)
    d.layers.add_layer("Locked")
    d.layers.layers["Locked"]["locked"] = True
    locked = LineEntity(Point(0, 1), Point(10, 1), layer="Locked")
    d.entities = [line, circle, locked]
    before = document_to_dict(d)
    enter(w, "S")
    for value in ("9,-1", "11,3", "0,0", "@5,2"):
        enter(w, value)
    assert line.p1.as_tuple() == (0, 0) and line.p2.as_tuple() == (15, 2)
    assert circle.center.as_tuple() == (15, 4) and locked.p2.as_tuple() == (10, 1)
    assert d.undo_stack.count() == 1
    d.undo_stack.undo()
    assert document_to_dict(d) == before
    d.undo_stack.redo()
    assert line.p2.as_tuple() == (15, 2)


def test_stretch_cancel_has_no_geometry_side_effects(main_window):
    w = main_window
    w.document.entities = [LineEntity(Point(0, 0), Point(10, 0))]
    before = document_to_dict(w.document)
    w.run_ribbon_command("STRETCH")
    click(w, 9, -1)
    click(w, 11, 1)
    w.cancel_command()
    assert document_to_dict(w.document) == before and w.document.undo_stack.count() == 0


def test_layer_isolate_restore_and_match(main_window):
    w = main_window
    d = w.document
    d.layers.add_layer("A")
    d.layers.add_layer("B")
    a = LineEntity(Point(0, 0), Point(10, 0), layer="A")
    b = CircleEntity(Point(20, 0), 5, layer="B")
    d.entities = [a, b]
    w.canvas.selected_entities = [a]
    w.run_ribbon_command("LAYISO")
    assert d.layers.is_visible("A") and not d.layers.is_visible("B")
    w.run_ribbon_command("LAYUNISO")
    assert d.layers.is_visible("B")
    w.canvas.selected_entities = [a]
    w.run_ribbon_command("LAYMCH")
    click(w, 25, 0)
    assert a.layer == "B"
    d.undo_stack.undo()
    assert a.layer == "A"
    w.canvas.selected_entities = [a]
    w.run_ribbon_command("LAYOFF")
    assert not d.layers.is_visible("A")
    w.run_ribbon_command("LAYON")
    assert d.layers.is_visible("A")


def test_multiline_text_native_dxf_and_rotated_bounds(
    main_window, monkeypatch, tmp_path
):
    w = main_window
    monkeypatch.setattr(
        QInputDialog,
        "getMultiLineText",
        lambda *a, **k: ("First line\nSecond {literal} \\ path", True),
    )
    w.run_ribbon_command("MTEXT")
    click(w, 10, 20)
    e = w.document.entities[0]
    assert "\n" in e.text
    e.rotation = 90
    bounds = e.bbox()
    assert bounds[0] < 10 and bounds[2] > 10 and bounds[3] > 20
    path = tmp_path / "text.pycad"
    save_project(w.document, path)
    assert load_project(path).entities[0].text == e.text
    path = tmp_path / "text.dxf"
    dxf_io.export_dxf(w.document, str(path))
    loaded = dxf_io.import_dxf(str(path)).entities[0]
    assert loaded.text == e.text and loaded.rotation == 90
    assert loaded.position.x == pytest.approx(
        e.position.x
    ) and loaded.position.y == pytest.approx(e.position.y)


def test_table_and_leader_blocks_are_editable_and_roundtrip(
    main_window, monkeypatch, tmp_path
):
    w = main_window
    monkeypatch.setattr(
        QInputDialog, "getMultiLineText", lambda *a, **k: ("Part,Qty\nBracket,4", True)
    )
    w.run_ribbon_command("TABLE")
    click(w, 0, 0)
    assert isinstance(w.document.entities[0], BlockReferenceEntity)
    assert len(w.document.blocks) == 1
    before = document_to_dict(w.document)
    w.run_ribbon_command("LEADER")
    click(w, 20, -30)
    click(w, 40, -10)
    assert len(w.document.blocks) == 2 and len(w.document.entities) == 2
    w.document.undo_stack.undo()
    assert document_to_dict(w.document) == before
    w.document.undo_stack.redo()
    restored = document_from_dict(document_to_dict(w.document))
    assert all(e.resolved_entities for e in restored.entities)
    path = tmp_path / "annotations.dxf"
    dxf_io.export_dxf(restored, str(path))
    loaded = dxf_io.import_dxf(str(path))
    assert len(loaded.entities) == 2 and all(
        e.resolved_entities for e in loaded.entities
    )


def test_table_limits_and_long_values():
    with pytest.raises(ValueError):
        table_geometry([])
    with pytest.raises(ValueError):
        table_geometry([["x"]] * 201)
    with pytest.raises(ValueError):
        table_geometry([["x"]], 10, 2, 3)
    text = next(e for e in table_geometry([["x" * 100]]) if isinstance(e, TextEntity))
    assert text.height < 2.5 and len(text.text) == 100


def test_center_annotations_and_measurements(main_window):
    w = main_window
    d = w.document
    d.entities = [
        CircleEntity(Point(0, 0), 10),
        LineEntity(Point(30, 0), Point(50, 0)),
        LineEntity(Point(50, 10), Point(30, 10)),
    ]
    w.run_ribbon_command("CENTERMARK")
    click(w, 10, 0)
    assert len(d.entities) == 5 and all(
        e.linetype == "DASHDOT" for e in d.entities[-2:]
    )
    w.run_ribbon_command("CENTERLINE")
    click(w, 40, 0)
    click(w, 40, 10)
    assert d.entities[-1].p1.as_tuple() == (30, 5) and d.entities[-1].p2.as_tuple() == (
        50,
        5,
    )
    w.run_ribbon_command("MEASURERADIUS")
    click(w, 10, 0)
    assert "RADIUS = 10.000000" in w.command_history.toPlainText()
    w.run_ribbon_command("MEASUREANGLE")
    for value in ("0,0", "10,0", "0,10"):
        enter(w, value)
    assert "ANGLE = 90.000000" in w.command_history.toPlainText()
    assert entity_metrics(d.entities[0])["area"] == pytest.approx(314.1592653589793)


@pytest.mark.parametrize("command", ["DIMCONTINUE", "DIMBASELINE"])
def test_chain_dimensions_are_independent_and_undoable(main_window, command):
    w = main_window
    d = w.document
    source = DimensionEntity(
        Point(0, 0), Point(10, 0), Point(5, 5), dim_style="horizontal"
    )
    d.entities = [source]
    w.run_ribbon_command(command)
    click(w, 5, 5)
    click(w, 20, 0)
    assert len(d.entities) == 2
    new = d.entities[-1]
    assert new.p1.x == (0 if command == "DIMBASELINE" else 10)
    assert new.measurement() == (20 if command == "DIMBASELINE" else 10)
    d.undo_stack.undo()
    assert d.entities == [source]


def test_zoom_window_realtime_pan_xray_and_escape(main_window, qapp):
    w = main_window
    w.run_ribbon_command("ZOOMWINDOW")
    click(w, 100, 100)
    click(w, 200, 200)
    assert w.canvas.pan_offset.x() == 150 and w.canvas.pan_offset.y() == 150
    view = w.canvas.viewport()
    center = w.canvas.world_to_screen(150, 150)
    assert center.x() == pytest.approx(view.width() / 2)
    w.run_ribbon_command("ZOOMREALTIME")
    z = w.canvas.zoom
    QTest.mousePress(view, Qt.MouseButton.LeftButton, pos=QPoint(100, 150))
    QTest.mouseMove(view, QPoint(100, 100))
    QTest.mouseRelease(view, Qt.MouseButton.LeftButton, pos=QPoint(100, 100))
    assert w.canvas.zoom > z
    QTest.keyClick(w.canvas, Qt.Key.Key_Escape)
    assert not w.canvas.navigation_zoom
    w.run_ribbon_command("XRAY")
    assert w.model_workspace.visual.currentText() == "X-Ray"
    w.run_ribbon_command("PAN")
    assert w.model_workspace.active.interaction_mode == "pan"
    w.run_ribbon_command("PLAN")
    assert w.viewport_stack.currentWidget() is w.canvas


def test_write_block_dependency_closure(main_window, tmp_path):
    w = main_window
    d = w.document
    inner = BlockDefinition("Inner", [CircleEntity(Point(0, 0), 2)])
    outer = BlockDefinition("Outer", [BlockReferenceEntity("Inner", Point(3, 4))])
    d.blocks = {"Inner": inner, "Outer": outer, "Unused": BlockDefinition("Unused", [])}
    ref = BlockReferenceEntity("Outer", Point(10, 20))
    d.entities = [ref, LineEntity(Point(0, 0), Point(1, 1))]
    d.sync_associative()
    subset = actions.selection_document(d, [ref])
    assert len(subset.entities) == 1 and set(subset.blocks) == {"Inner", "Outer"}
    assert subset.entities[0].resolved_entities
    path = tmp_path / "selection.pycad"
    save_project(subset, path)
    assert len(load_project(path).entities) == 1


def test_page_setup_new_rename_layout_and_batch_plot(
    main_window, monkeypatch, tmp_path
):
    w = main_window
    w.document.entities = [LineEntity(Point(0, 0), Point(100, 20))]
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("Sheet A", True))
    w.run_ribbon_command("NEWLAYOUT")
    assert w.document.current_space == "Sheet A"
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("Sheet B", True))
    w.rename_layout_dialog()
    assert w.document.current_space == "Sheet B"
    monkeypatch.setattr(QInputDialog, "getText", lambda *a, **k: ("420,297", True))
    w.run_ribbon_command("PAGESETUP")
    layout = w.document.layouts["Sheet B"]
    assert (layout.page_width, layout.page_height) == (420, 297)
    w.document.undo_stack.undo()
    assert layout.page_width == 297
    path = tmp_path / "plots.zip"
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", lambda *a, **k: (str(path), "ZIP")
    )
    w.run_ribbon_command("BATCHPLOT")
    with zipfile.ZipFile(path) as archive:
        assert len(archive.namelist()) == 1 and archive.read(
            archive.namelist()[0]
        ).startswith(b"%PDF")
    monkeypatch.setattr(QDialog, "exec", lambda self: 0)
    w.run_ribbon_command("PLOTPREVIEW")
    assert "Command failed" not in w.command_history.toPlainText()


def test_portable_transmittal_missing_refs_and_reload_undo(main_window, tmp_path):
    d = main_window.document
    source = Document()
    source.entities = [CircleEntity(Point(0, 0), 5)]
    dxf_io.export_dxf(source, str(tmp_path / "source.dxf"))
    d.filepath = str(tmp_path / "drawing.pycad")
    d.blocks["Ref"] = BlockDefinition(
        "Ref", [CircleEntity(Point(0, 0), 2)], "source.dxf"
    )
    d.entities = [BlockReferenceEntity("Ref", Point(0, 0))]
    d.sync_associative()
    path = tmp_path / "package.zip"
    actions.transmittal(d, path)
    folder = tmp_path / "extracted"
    with zipfile.ZipFile(path) as archive:
        archive.extractall(folder)
    restored = load_project(folder / "drawing.pycad")
    restored.reload_xref("Ref")
    assert restored.blocks["Ref"].entities[0].radius == 5
    restored.undo_stack.undo()
    assert restored.blocks["Ref"].entities[0].radius == 2
    before = path.read_bytes()
    (tmp_path / "source.dxf").unlink()
    with pytest.raises(ValueError, match="Missing reference"):
        actions.transmittal(d, path)
    assert path.read_bytes() == before


def test_aliases_validation_persistence_and_viewport_entry(
    main_window, monkeypatch, qapp
):
    w = main_window
    monkeypatch.setattr(
        QInputDialog,
        "getMultiLineText",
        lambda *a, **k: ("ST=STRETCH\nCM=CENTERMARK", True),
    )
    w.run_ribbon_command("ALIASEDIT")
    assert actions.load_aliases() == {"ST": "STRETCH", "CM": "CENTERMARK"}
    w.canvas.setFocus()
    QTest.keyClicks(w.canvas, "ST")
    QTest.keyClick(w.command_line, Qt.Key.Key_Space)
    assert w.current_tool.name == "STRETCH"
    w.cancel_command()
    monkeypatch.setattr(
        QInputDialog, "getMultiLineText", lambda *a, **k: ("LINE=CIRCLE", True)
    )
    with pytest.raises(ValueError, match="reserved"):
        actions.edit_aliases(w)
    assert w.user_aliases["ST"] == "STRETCH"


def test_data_extraction_csv_and_palette(main_window, monkeypatch, tmp_path):
    w = main_window
    d = w.document
    d.layers.add_layer("=DANGEROUS()")
    d.entities = [LineEntity(Point(0, 0), Point(3, 4), layer="=DANGEROUS()")]
    path = tmp_path / "data.csv"
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", lambda *a, **k: (str(path), "CSV")
    )
    w.run_ribbon_command("DATAEXTRACTION")
    rows = list(csv.reader(io.StringIO(path.read_text(encoding="utf-8-sig"))))
    assert rows[1][1] == "'=DANGEROUS()" and rows[1][3] == "5.000000"
    w.run_ribbon_command("TOOLCOVERAGE")
    assert w.tool_palette_dock.isVisible()
    w.run_ribbon_command("DATATABLE")
    click(w, 0, 0)
    assert len(d.blocks) == 1
