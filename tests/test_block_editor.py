"""Tests for pycad.block_editor - editing a block definition in place."""
import pytest
from pycad.geometry import Point, LineEntity, BlockDefinition, BlockReferenceEntity
from pycad.document import AddEntityCommand
from pycad.block_editor import BlockEditorDialog


def test_editor_loads_block_entities_as_clones(qapp, main_window):
    bd = BlockDefinition("Sym", [LineEntity(Point(0, 0), Point(5, 0))])
    main_window.document.add_block(bd)
    dialog = BlockEditorDialog(main_window, "Sym", bd)
    assert len(dialog.document.entities) == 1
    # editing the dialog's copy must not touch the live definition
    dialog.document.entities[0].p2.x = 999
    assert bd.entities[0].p2.x == 5


def test_save_writes_back_and_propagates(qapp, main_window):
    bd = BlockDefinition("Sym", [LineEntity(Point(0, 0), Point(5, 0))])
    main_window.document.add_block(bd)
    ref = BlockReferenceEntity("Sym", Point(50, 0))
    ref.rebuild(bd)
    main_window.document.undo_stack.push(AddEntityCommand(main_window.document, ref, "t"))

    dialog = BlockEditorDialog(main_window, "Sym", bd)
    dialog.set_tool("LINE")
    dialog.current_tool.on_click(0, 0, "", 1)
    dialog.current_tool.on_click(0, 8, "", 1)
    dialog.current_tool.on_key(16777220)
    dialog.accept()

    assert len(bd.entities) == 2
    main_window.document.sync_associative()
    assert len(ref.resolved_entities) == 2


def test_cancel_discards_changes(qapp, main_window):
    bd = BlockDefinition("Sym", [LineEntity(Point(0, 0), Point(5, 0))])
    main_window.document.add_block(bd)
    dialog = BlockEditorDialog(main_window, "Sym", bd)
    dialog.set_tool("LINE")
    dialog.current_tool.on_click(0, 0, "", 1)
    dialog.current_tool.on_click(0, 8, "", 1)
    dialog.current_tool.on_key(16777220)
    dialog.reject()
    assert len(bd.entities) == 1


def test_editor_supports_modify_tools_like_fillet(qapp, main_window):
    bd = BlockDefinition("Bracket", [])
    main_window.document.add_block(bd)
    dialog = BlockEditorDialog(main_window, "Bracket", bd)

    dialog.set_tool("LINE")
    dialog.current_tool.on_click(0, 0, "", 1)
    dialog.current_tool.on_click(10, 0, "", 1)
    dialog.current_tool.on_key(16777220)
    dialog.set_tool("LINE")
    dialog.current_tool.on_click(10, 0, "", 1)
    dialog.current_tool.on_click(10, 10, "", 1)
    dialog.current_tool.on_key(16777220)

    dialog.set_tool("FILLET")
    dialog.current_tool.on_click(2, 0, "", 1)
    dialog.current_tool.on_click(10, 8, "", 1)
    dialog.current_tool.on_text_input("2")
    kinds = [e.kind for e in dialog.document.entities]
    assert "ARC" in kinds


def test_editor_preserves_selection_for_copy_tool(qapp, main_window):
    bd = BlockDefinition("Bracket", [LineEntity(Point(0, 0), Point(10, 0))])
    main_window.document.add_block(bd)
    dialog = BlockEditorDialog(main_window, "Bracket", bd)
    line = dialog.document.entities[0]
    dialog.canvas.selected_entities = [line]
    dialog.set_tool("COPY")
    assert dialog.canvas.selected_entities == [line]
    dialog.current_tool.on_click(0, 0, "", 1)
    dialog.current_tool.on_click(20, 20, "", 1)
    assert len(dialog.document.entities) == 2
