import copy
import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QFileDialog, QMessageBox, QPushButton
from pycad.document import Document
from pycad.geometry import (
    Point,
    LineEntity,
    BlockDefinition,
    BlockReferenceEntity,
    DimensionEntity,
)
from pycad.file_workspace import (
    CATEGORIES,
    entries,
    audit_document,
    purge_candidates,
    PurgeCommand,
    save_template,
    load_as_new,
    recover,
)
from pycad.native_io import document_to_dict, save_project, load_project
from pycad.dimstyles import DEFAULT_STYLE


def test_file_panel_groups_resize_escape_and_actions(main_window, qapp):
    w = main_window
    w.show_file_workspace()
    panel = w.file_workspace
    assert panel.isVisible() and panel.window() is w
    assert (
        tuple(panel.categories.item(i).text() for i in range(panel.categories.count()))
        == CATEGORIES
    )
    panel.categories.setCurrentRow(CATEGORIES.index("Drawing Utilities"))
    assert all(b.isEnabled() for b in panel.scroll.findChildren(QPushButton))
    panel.categories.setCurrentRow(CATEGORIES.index("Import"))
    buttons = panel.scroll.findChildren(QPushButton)
    assert next(b for b in buttons if b.text().startswith("DXF drawing")).isEnabled()
    assert not next(b for b in buttons if b.text().startswith("IFC")).isEnabled()
    assert (
        "Not yet implemented"
        in next(b for b in buttons if b.text().startswith("PDF to editable")).toolTip()
    )
    assert next(b for b in buttons if b.text().startswith('PDF underlay')).isEnabled()
    assert next(b for b in buttons if b.text().startswith('Image underlay')).isEnabled()
    w.resize(840, 650)
    qapp.processEvents()
    assert (
        panel.width() < w.width()
        and panel.height() < w.height() - w.menuBar().height()
    )
    QTest.keyClick(panel.categories, Qt.Key.Key_Escape)
    assert not panel.isVisible()


def test_slim_command_bar_and_history_toggle_preserves_input(main_window, qapp):
    w = main_window
    assert not w.command_history.isVisible()
    assert w.command_dock.height() <= 36
    height = w.canvas.viewport().height()
    w.command_line.setText("@100<45")
    w.command_history.appendPlainText("Example history message")
    QTest.keyClick(w.command_line, Qt.Key.Key_F2)
    qapp.processEvents()
    assert w.command_history.isVisible()
    assert w.command_dock.height() > 65
    assert w.command_line.text() == "@100<45"
    QTest.mouseClick(w.history_button, Qt.MouseButton.LeftButton)
    qapp.processEvents()
    assert not w.command_history.isVisible() and w.command_dock.height() <= 36
    assert w.canvas.viewport().height() >= height
    assert "Example history message" in w.command_history.toPlainText()


def test_native_template_save_does_not_change_current_document(
    main_window, tmp_path, monkeypatch
):
    w = main_window
    w.document.entities = [LineEntity(Point(1, 2), Point(3, 4))]
    w.document.unit_settings["length_precision"] = 5
    before = document_to_dict(w.document)
    path = tmp_path / "studio.pycadt"
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", lambda *a, **k: (str(path), "Template")
    )
    assert save_template(w)
    assert document_to_dict(w.document) == before and w.document.filepath is None
    assert load_project(path).unit_settings["length_precision"] == 5
    w.document.mark_saved()
    assert load_as_new(w, str(path))
    assert w.document.filepath is None and len(w.document.entities) == 1
    assert w.document.unit_settings["length_precision"] == 5


def test_recover_valid_backup_as_unsaved_and_reject_corrupt(
    main_window, tmp_path, monkeypatch
):
    w = main_window
    doc = Document()
    doc.entities = [LineEntity(Point(0, 0), Point(10, 0))]
    path = tmp_path / "recovery.pycad.bak"
    save_project(doc, path)
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", lambda *a, **k: (str(path), "Backup")
    )
    assert recover(w)
    assert w.document.filepath is None and w.document.dirty
    before = document_to_dict(w.document)
    path.write_text("corrupt", encoding="utf-8")
    monkeypatch.setattr(w, "_confirm_save_changes", lambda: True)
    errors = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: errors.append(a[2]))
    assert not recover(w)
    assert errors and document_to_dict(w.document) == before


def test_purge_retains_nested_blocks_used_layers_styles_and_undo(qapp):
    doc = Document()
    for n in ("Geometry", "Unused", "Xref", "Required"):
        doc.layers.add_layer(n)
    doc.dimstyles["Kept"] = copy.deepcopy(DEFAULT_STYLE)
    doc.dimstyles["Unused"] = copy.deepcopy(DEFAULT_STYLE)
    line = LineEntity(Point(0, 0), Point(10, 0), layer="Geometry")
    dim = DimensionEntity(Point(0, 0), Point(10, 0), Point(5, 2), style_name="Kept")
    doc.blocks["Leaf"] = BlockDefinition("Leaf", [line, dim])
    doc.blocks["Parent"] = BlockDefinition(
        "Parent", [BlockReferenceEntity("Leaf", Point(0, 0))]
    )
    doc.blocks["Unused"] = BlockDefinition("Unused", [])
    doc.blocks["Reference"] = BlockDefinition(
        "Reference", [LineEntity(Point(0, 1), Point(3, 1), layer="Xref")], "ref.dxf"
    )
    ref = BlockReferenceEntity("Parent", Point(0, 0))
    doc.entities = [ref]
    doc.cad_standard = {
        "format": "PyCAD-Standards-1",
        "units": "mm",
        "layers": {
            n: {k: doc.layers.layers[n][k] for k in ("color", "linetype", "lineweight")}
            for n in ("0", "Required")
        },
    }
    doc.sync_associative()
    before = document_to_dict(doc)
    candidates = purge_candidates(doc)
    assert candidates == {
        "blocks": ["Unused"],
        "layers": ["Unused"],
        "styles": ["Unused"],
        "textstyles": [],
        "mleaderstyles": [],
    }
    doc.undo_stack.push(PurgeCommand(doc, candidates))
    assert "Unused" not in doc.blocks and "Unused" not in doc.layers.layers
    assert doc.blocks["Leaf"].entities[0] is line and doc.entities[0] is ref
    assert audit_document(doc).startswith("PASS")
    doc.undo_stack.undo()
    assert document_to_dict(doc) == before and doc.blocks["Leaf"].entities[0] is line
    doc.undo_stack.redo()
    assert "Unused" not in doc.dimstyles


def test_audit_rejects_bad_native_data_without_editing(qapp):
    doc = Document()
    doc.entities = [LineEntity(Point(0, 0), Point(10, 0))]
    doc.entities[0].layer = "Missing"
    before = document_to_dict(doc)
    with pytest.raises(ValueError):
        audit_document(doc)
    assert document_to_dict(doc) == before


def test_close_drawing_respects_cancel_and_file_shortcuts(main_window, monkeypatch):
    w = main_window
    w.document.entities = [LineEntity(Point(0, 0), Point(10, 0))]
    before = document_to_dict(w.document)
    close = entries(w)["Close"][0][2]
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *a, **k: QMessageBox.StandardButton.Cancel
    )
    assert not close()
    assert document_to_dict(w.document) == before
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *a, **k: QMessageBox.StandardButton.Discard
    )
    assert close()
    assert not w.document.entities
    assert {"Ctrl+N", "Ctrl+O", "Ctrl+S", "Ctrl+Shift+S", "Ctrl+P", "Ctrl+Q"} <= {
        a.shortcut().toString() for a in w.file_shortcuts
    }
