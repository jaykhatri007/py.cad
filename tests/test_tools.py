"""Tests for pycad.tools - draw and edit tool state machines.
Uses `main_window` fixture (see conftest.py) which needs a QApplication."""
import pytest
from pycad.geometry import Point, LineEntity, CircleEntity, ArcEntity, RectangleEntity
from pycad.document import AddEntityCommand


def test_line_tool_draws_line(main_window):
    w = main_window
    w.set_tool("LINE")
    w.current_tool.on_click(0, 0, "", 1)
    w.current_tool.on_click(10, 0, "", 1)
    w.current_tool.on_key(16777220)  # Enter
    assert len(w.document.entities) == 1
    assert w.document.entities[0].kind == "LINE"


def test_circle_tool(main_window):
    w = main_window
    w.set_tool("CIRCLE")
    w.current_tool.on_click(0, 0, "", 1)
    w.current_tool.on_click(5, 0, "", 1)
    assert len(w.document.entities) == 1
    assert w.document.entities[0].radius == pytest.approx(5)


def test_select_and_delete(main_window):
    w = main_window
    line = LineEntity(Point(0, 0), Point(10, 0))
    w.document.undo_stack.push(AddEntityCommand(w.document, line, "t"))
    w.set_tool("SELECT")
    w.current_tool.on_click(5, 0, "", 1)
    assert line in w.canvas.selected_entities
    w.current_tool.on_key(16777223)  # Delete
    assert len(w.document.entities) == 0


def test_fillet_line_line_creates_arc_and_trims(main_window):
    w = main_window
    la = LineEntity(Point(0, 0), Point(10, 0))
    lb = LineEntity(Point(10, 0), Point(10, 10))
    w.document.undo_stack.push(AddEntityCommand(w.document, la, "t"))
    w.document.undo_stack.push(AddEntityCommand(w.document, lb, "t"))
    w.set_tool("FILLET")
    w.current_tool.on_click(2, 0, "", 1)
    w.current_tool.on_click(10, 8, "", 1)
    w.current_tool.on_text_input("2")
    kinds = [e.kind for e in w.document.entities]
    assert "ARC" in kinds
    assert la.p2.x == pytest.approx(8)


def test_trim_line_against_line_boundary(main_window):
    w = main_window
    boundary = LineEntity(Point(5, -5), Point(5, 5))
    target = LineEntity(Point(0, 0), Point(10, 0))
    w.document.undo_stack.push(AddEntityCommand(w.document, boundary, "t"))
    w.document.undo_stack.push(AddEntityCommand(w.document, target, "t"))
    w.set_tool("TRIM")
    w.current_tool.on_click(5, 0, "", 1)
    w.current_tool.on_key(16777220)  # Enter -> stop picking boundaries
    w.current_tool.on_click(8, 0, "", 1)  # click the part to remove
    assert target.p1.x == pytest.approx(0)
    assert target.p2.x == pytest.approx(5)


def test_trim_splits_line_between_two_interior_cuts(main_window):
    w = main_window
    b1 = LineEntity(Point(3, -5), Point(3, 5))
    b2 = LineEntity(Point(7, -5), Point(7, 5))
    target = LineEntity(Point(0, 0), Point(10, 0))
    for e in (b1, b2, target):
        w.document.undo_stack.push(AddEntityCommand(w.document, e, "t"))
    w.set_tool("TRIM")
    w.current_tool.on_click(3, 0, "", 1)
    w.current_tool.on_click(7, 0, "", 1)
    w.current_tool.on_key(16777220)
    w.current_tool.on_click(5, 0, "", 1)
    lines_after = [e for e in w.document.entities if isinstance(e, LineEntity) and e not in (b1, b2)]
    assert len(lines_after) == 2


def test_offset_line(main_window):
    w = main_window
    line = LineEntity(Point(0, 0), Point(10, 0))
    w.document.undo_stack.push(AddEntityCommand(w.document, line, "t"))
    w.set_tool("OFFSET")
    w.current_tool.on_text_input("5")
    w.current_tool.on_click(5, 0, "", 1)
    w.current_tool.on_click(5, 5, "", 1)
    assert len(w.document.entities) == 2
    offset_line = w.document.entities[-1]
    assert offset_line.p1.y == pytest.approx(5)


def test_mirror_with_erase_source(main_window):
    w = main_window
    line = LineEntity(Point(0, 0), Point(10, 0))
    w.document.undo_stack.push(AddEntityCommand(w.document, line, "t"))
    w.canvas.selected_entities = [line]
    w.set_tool("MIRROR")
    w.current_tool.on_click(0, 0, "", 1)
    w.current_tool.on_click(0, 10, "", 1)
    w.current_tool.on_text_input("Y")
    assert len(w.document.entities) == 1  # original erased, mirror copy remains
    mirrored = w.document.entities[0]
    assert mirrored.p2.x == pytest.approx(-10)


def test_undo_redo_via_main_window(main_window):
    w = main_window
    w.set_tool("LINE")
    w.current_tool.on_click(0, 0, "", 1)
    w.current_tool.on_click(10, 0, "", 1)
    w.current_tool.on_key(16777220)
    assert len(w.document.entities) == 1
    w.undo()
    assert len(w.document.entities) == 0
    w.redo()
    assert len(w.document.entities) == 1


def test_copy_tool_keeps_original_and_allows_multiple_copies(main_window):
    w = main_window
    line = LineEntity(Point(0, 0), Point(10, 0))
    w.document.undo_stack.push(AddEntityCommand(w.document, line, "t"))
    w.canvas.selected_entities = [line]
    w.set_tool("COPY")
    w.current_tool.on_click(0, 0, "", 1)
    w.current_tool.on_click(5, 5, "", 1)
    w.current_tool.on_click(10, 10, "", 1)
    assert len(w.document.entities) == 3  # original + 2 copies
    assert line.p1.x == 0  # original untouched


def test_rotate_tool_by_angle_and_undo(main_window):
    w = main_window
    line = LineEntity(Point(10, 0), Point(20, 0))
    w.document.undo_stack.push(AddEntityCommand(w.document, line, "t"))
    w.canvas.selected_entities = [line]
    w.set_tool("ROTATE")
    w.current_tool.on_click(0, 0, "", 1)
    w.current_tool.on_text_input("90")
    assert line.p1.x == pytest.approx(0, abs=1e-9)
    assert line.p1.y == pytest.approx(10)
    w.undo()
    assert line.p1.x == pytest.approx(10)
    assert line.p1.y == pytest.approx(0, abs=1e-9)


def test_scale_tool_by_factor_and_undo(main_window):
    w = main_window
    line = LineEntity(Point(0, 0), Point(10, 0))
    w.document.undo_stack.push(AddEntityCommand(w.document, line, "t"))
    w.canvas.selected_entities = [line]
    w.set_tool("SCALE")
    w.current_tool.on_click(0, 0, "", 1)
    w.current_tool.on_text_input("2")
    assert line.p2.x == pytest.approx(20)
    w.undo()
    assert line.p2.x == pytest.approx(10)


def test_scale_tool_by_reference_points(main_window):
    w = main_window
    line = LineEntity(Point(0, 0), Point(10, 0))
    w.document.undo_stack.push(AddEntityCommand(w.document, line, "t"))
    w.canvas.selected_entities = [line]
    w.set_tool("SCALE")
    w.current_tool.on_click(0, 0, "", 1)   # base
    w.current_tool.on_click(5, 0, "", 1)   # reference distance = 5
    w.current_tool.on_click(15, 0, "", 1)  # new distance = 15 -> factor 3
    assert line.p2.x == pytest.approx(30)


def test_spline_tool_creates_entity_through_points(main_window):
    w = main_window
    w.set_tool("SPLINE")
    w.current_tool.on_click(0, 0, "", 1)
    w.current_tool.on_click(5, 10, "", 1)
    w.current_tool.on_click(10, 0, "", 1)
    w.current_tool.on_key(16777220)
    assert len(w.document.entities) == 1
    spline = w.document.entities[0]
    assert spline.kind == "SPLINE"
    assert len(spline.points) == 3


def test_dim_radius_and_diameter(main_window):
    w = main_window
    circle = CircleEntity(Point(0, 0), 5)
    w.document.undo_stack.push(AddEntityCommand(w.document, circle, "t"))
    w.set_tool("DIMRADIUS")
    w.current_tool.on_click(5, 0, "", 1)
    w.current_tool.on_click(8, 3, "", 1)
    dim = w.document.entities[-1]
    assert dim.label_text() == "R5.00"

    circle2 = CircleEntity(Point(20, 0), 5)
    w.document.undo_stack.push(AddEntityCommand(w.document, circle2, "t"))
    w.set_tool("DIMDIAMETER")
    w.current_tool.on_click(25, 0, "", 1)
    w.current_tool.on_click(28, 3, "", 1)
    dim2 = w.document.entities[-1]
    assert dim2.label_text() == "\u230010.00"


def test_ortho_mode_locks_to_horizontal(main_window):
    w = main_window
    w.canvas.ortho_enabled = True
    w.canvas.snap_enabled = False
    w.set_tool("LINE")
    w.current_tool.on_click(0, 0, "", 1)
    # simulate the ortho-adjusted coordinate the canvas would compute for a
    # cursor position that's mostly horizontal from the first point
    wx, wy = w.canvas._apply_ortho(10, 0.7)
    assert wy == pytest.approx(0)  # locked to the reference point's y
    wx2, wy2 = w.canvas._apply_ortho(0.7, 10)
    assert wx2 == pytest.approx(0)  # locked to the reference point's x


def test_block_tool_creates_definition_and_reference(main_window):
    w = main_window
    la = LineEntity(Point(0, 0), Point(5, 0))
    lb = LineEntity(Point(0, 0), Point(0, 5))
    w.document.undo_stack.push(AddEntityCommand(w.document, la, "t"))
    w.document.undo_stack.push(AddEntityCommand(w.document, lb, "t"))
    w.canvas.selected_entities = [la, lb]
    w.set_tool("BLOCK")
    w.current_tool.on_click(0, 0, "", 1)
    w.current_tool.on_text_input("Bracket")
    assert "Bracket" in w.document.blocks
    assert len(w.document.entities) == 1
    assert w.document.entities[0].kind == "INSERT"
    w.undo()
    assert len(w.document.entities) == 2  # originals restored


def test_insert_block_places_reference_at_click(main_window):
    from pycad.geometry import BlockDefinition
    w = main_window
    w.document.add_block(BlockDefinition("Sym", [LineEntity(Point(0, 0), Point(5, 0))]))
    w.set_tool("INSERT")
    w.current_tool.on_text_input("Sym")
    w.current_tool.on_click(20, 20, "", 1)
    assert len(w.document.entities) == 1
    ref = w.document.entities[0]
    assert ref.kind == "INSERT"
    assert ref.resolved_entities[0].p1.x == 20


def test_block_definition_edit_propagates_to_references(main_window):
    from pycad.geometry import BlockDefinition, BlockReferenceEntity
    w = main_window
    bd = BlockDefinition("Sym", [LineEntity(Point(0, 0), Point(5, 0))])
    w.document.add_block(bd)
    ref1 = BlockReferenceEntity("Sym", Point(0, 0))
    ref1.rebuild(bd)
    ref2 = BlockReferenceEntity("Sym", Point(50, 0))
    ref2.rebuild(bd)
    w.document.undo_stack.push(AddEntityCommand(w.document, ref1, "t"))
    w.document.undo_stack.push(AddEntityCommand(w.document, ref2, "t"))
    bd.entities[0].p2.x = 20
    w.document.sync_associative()
    assert ref1.resolved_entities[0].p2.x == 20
    assert ref2.resolved_entities[0].p2.x == 70


def test_new_layout_adds_tab_and_default_viewport(main_window):
    w = main_window
    w.document.undo_stack.push(AddEntityCommand(w.document, CircleEntity(Point(0, 0), 20), "t"))
    w.document.add_layout("Sheet1")
    assert "Sheet1" in w.document.layouts
    layout = w.document.layouts["Sheet1"]
    assert len(layout.viewports) == 1
    vp = layout.viewports[0]
    assert vp.center.x == pytest.approx(0)
    assert vp.center.y == pytest.approx(0)


def test_add_viewport_tool_adds_second_viewport(main_window):
    w = main_window
    w.document.undo_stack.push(AddEntityCommand(w.document, CircleEntity(Point(0, 0), 20), "t"))
    w.document.add_layout("Sheet1")
    w.space_tabs.addTab("Sheet1")
    w.space_tabs.setCurrentIndex(1)
    layout = w.document.layouts["Sheet1"]
    before = len(layout.viewports)
    w.set_tool("ADDVIEWPORT")
    w.current_tool.on_click(150, 20, "", 1)
    w.current_tool.on_click(280, 100, "", 1)
    assert len(layout.viewports) == before + 1


def test_select_and_delete_viewport(main_window):
    w = main_window
    w.document.undo_stack.push(AddEntityCommand(w.document, CircleEntity(Point(0, 0), 20), "t"))
    w.document.add_layout("Sheet1")
    w.space_tabs.addTab("Sheet1")
    w.space_tabs.setCurrentIndex(1)
    layout = w.document.layouts["Sheet1"]
    default_vp = layout.viewports[0]
    layout.remove_viewport(default_vp)
    w.set_tool("ADDVIEWPORT")
    w.current_tool.on_click(10, 10, "", 1)
    w.current_tool.on_click(100, 90, "", 1)
    vp = layout.viewports[0]
    w.set_tool("SELECT")
    mid = Point(vp.x + vp.width / 2, vp.y + vp.height / 2)
    w.current_tool.on_click(mid.x, mid.y, "", 1)
    assert w.canvas.selected_viewport is vp
    w.current_tool.on_key(16777223)  # Delete
    assert len(layout.viewports) == 0


def test_delete_viewport_is_undoable(main_window):
    w = main_window
    w.document.undo_stack.push(AddEntityCommand(w.document, CircleEntity(Point(0, 0), 20), "t"))
    w.document.add_layout("Sheet1")
    w.space_tabs.addTab("Sheet1")
    w.space_tabs.setCurrentIndex(1)
    layout = w.document.layouts["Sheet1"]
    vp = layout.viewports[0]
    w.set_tool("SELECT")
    mid = Point(vp.x + vp.width / 2, vp.y + vp.height / 2)
    w.current_tool.on_click(mid.x, mid.y, "", 1)
    w.current_tool.on_key(16777223)
    assert len(layout.viewports) == 0
    w.document.undo_stack.undo()
    assert len(layout.viewports) == 1
    assert layout.viewports[0] is vp


def test_add_viewport_is_undoable(main_window):
    w = main_window
    w.document.undo_stack.push(AddEntityCommand(w.document, CircleEntity(Point(0, 0), 20), "t"))
    w.document.add_layout("Sheet1")
    w.space_tabs.addTab("Sheet1")
    w.space_tabs.setCurrentIndex(1)
    layout = w.document.layouts["Sheet1"]
    before = len(layout.viewports)
    w.set_tool("ADDVIEWPORT")
    w.current_tool.on_click(10, 10, "", 1)
    w.current_tool.on_click(100, 90, "", 1)
    assert len(layout.viewports) == before + 1
    w.document.undo_stack.undo()
    assert len(layout.viewports) == before
    w.document.undo_stack.redo()
    assert len(layout.viewports) == before + 1


def test_move_viewport_via_drag_and_undo(main_window):
    w = main_window
    w.document.undo_stack.push(AddEntityCommand(w.document, CircleEntity(Point(0, 0), 20), "t"))
    w.document.add_layout("Sheet1")
    w.space_tabs.addTab("Sheet1")
    w.space_tabs.setCurrentIndex(1)
    layout = w.document.layouts["Sheet1"]
    vp = layout.viewports[0]
    old_rect = (vp.x, vp.y, vp.width, vp.height)
    w.set_tool("SELECT")
    st = w.current_tool
    mid = Point(vp.x + vp.width / 2, vp.y + vp.height / 2)
    st.on_click(mid.x, mid.y, "", 1)
    assert st.vp_drag_kind == "move"
    st.on_move(mid.x + 20, mid.y + 10, "")
    st.finish_drag()
    assert vp.x == pytest.approx(old_rect[0] + 20)
    w.document.undo_stack.undo()
    assert (vp.x, vp.y, vp.width, vp.height) == old_rect


def test_resize_viewport_via_corner_drag_and_undo(main_window):
    w = main_window
    w.document.undo_stack.push(AddEntityCommand(w.document, CircleEntity(Point(0, 0), 20), "t"))
    w.document.add_layout("Sheet1")
    w.space_tabs.addTab("Sheet1")
    w.space_tabs.setCurrentIndex(1)
    layout = w.document.layouts["Sheet1"]
    vp = layout.viewports[0]
    old_rect = (vp.x, vp.y, vp.width, vp.height)
    w.set_tool("SELECT")
    st = w.current_tool
    w.canvas.selected_viewport = vp
    tr = Point(vp.x + vp.width, vp.y + vp.height)
    st.on_click(tr.x, tr.y, "", 1)
    assert st.vp_drag_kind == "resize"
    st.on_move(tr.x + 30, tr.y + 20, "")
    st.finish_drag()
    assert vp.width > old_rect[2]
    w.document.undo_stack.undo()
    assert vp.width == pytest.approx(old_rect[2])


def test_space_tab_switch_updates_current_space(main_window):
    w = main_window
    w.document.add_layout("Sheet1")
    w.space_tabs.addTab("Sheet1")
    w.space_tabs.setCurrentIndex(1)
    assert w.document.current_space == "Sheet1"
    w.space_tabs.setCurrentIndex(0)
    assert w.document.current_space == "Model"


def test_xclip_tool_filters_reference_entities(main_window):
    from pycad.geometry import BlockDefinition, BlockReferenceEntity
    w = main_window
    entities = [LineEntity(Point(0, 0), Point(2, 0)), LineEntity(Point(50, 50), Point(52, 50))]
    bd = BlockDefinition("Test", entities)
    w.document.add_block(bd)
    ref = BlockReferenceEntity("Test", Point(0, 0))
    ref.rebuild(bd)
    w.document.undo_stack.push(AddEntityCommand(w.document, ref, "t"))

    w.canvas.selected_entities = [ref]
    w.set_tool("XCLIP")
    w.current_tool.on_click(0, 0, "", 1)     # picks the selected reference
    w.current_tool.on_click(-5, -5, "", 1)   # first corner
    w.current_tool.on_click(5, 5, "", 1)     # second corner -> commits
    assert len(ref.resolved_entities) == 1
