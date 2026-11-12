"""Keyboard and compact workspace acceptance tests through real Qt events."""

import pytest
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QLineEdit, QToolBar, QToolButton, QWidgetAction

from pycad.document import Document
from pycad.geometry import Point, RectangleEntity


def type_keys(qapp, text):
    # Follow actual focus changes after the first character leaves the canvas.
    for char in text:
        QTest.keyClicks(qapp.focusWidget(), char)


def submit(qapp, key=Qt.Key.Key_Return):
    QTest.keyClick(qapp.focusWidget(), key)


@pytest.mark.parametrize("key", [Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space])
@pytest.mark.parametrize("command,tool", [("L", "LINE"), ("circle", "CIRCLE"), ("REC", "RECTANGLE")])
def test_type_anywhere_then_enter_or_space_activates(main_window, qapp, key, command, tool):
    w = main_window
    w.canvas.setFocus()
    QTest.mouseMove(w.canvas.viewport(), QPoint(140, 100))
    type_keys(qapp, command)
    prompt = w.canvas.command_overlay
    assert w.command_line.text() == command
    assert prompt.isVisible() and prompt.window() is w
    assert w.canvas.viewport().rect().contains(prompt.geometry())
    assert w.current_tool.name == "SELECT"
    submit(qapp, key)
    assert w.current_tool.name == tool
    assert w.canvas.hasFocus()
    assert not prompt.isVisible()


def test_space_coordinates_finish_and_repeat_only_command(main_window, qapp):
    w = main_window
    w.canvas.setFocus()
    type_keys(qapp, "L ")
    type_keys(qapp, "0,0 ")
    type_keys(qapp, "@20,10")
    submit(qapp)
    assert len(w.document.entities) == 1
    line = w.document.entities[0]
    assert (line.p1.x, line.p1.y, line.p2.x, line.p2.y) == (0, 0, 20, 10)
    submit(qapp, Qt.Key.Key_Space)
    assert w.current_tool.name == "SELECT"
    submit(qapp)
    assert w.current_tool.name == "LINE" and not w.current_tool.points
    assert w.last_command == "LINE"


def test_text_spaces_are_literal_until_enter(main_window, qapp):
    w = main_window
    w.canvas.setFocus()
    type_keys(qapp, "TEXT ")
    type_keys(qapp, "0,0 ")
    assert w.current_tool.insertion_point == Point(0, 0)
    type_keys(qapp, "Meeting Room A")
    assert w.command_line.text() == "Meeting Room A"
    assert not w.document.entities
    submit(qapp)
    assert w.document.entities[0].text == "Meeting Room A"
    assert w.current_tool.name == "SELECT"


def test_block_names_keep_spaces_when_creating_and_inserting(main_window, qapp):
    w = main_window
    rectangle = RectangleEntity(Point(0, 0), Point(10, 8))
    w.document.add_entity(rectangle)
    w.canvas.selected_entities = [rectangle]
    w.canvas.setFocus()
    type_keys(qapp, "BLOCK ")
    w._on_world_clicked(0, 0, "", Qt.MouseButton.LeftButton.value)
    type_keys(qapp, "Building Core")
    submit(qapp)
    assert "Building Core" in w.document.blocks
    type_keys(qapp, "INSERT ")
    type_keys(qapp, "Building Core")
    assert not w.current_tool.block_name
    submit(qapp)
    assert w.current_tool.block_name == "Building Core"


def test_partial_command_escape_and_unknown_command_keep_document(main_window, qapp):
    w = main_window
    w.canvas.setFocus()
    type_keys(qapp, "LIN")
    submit(qapp, Qt.Key.Key_Escape)
    assert w.command_line.text() == "" and w.command_overlay is None
    assert w.current_tool.name == "SELECT" and w.canvas.hasFocus()
    type_keys(qapp, "NOTACOMMAND ")
    assert "Unknown command: NOTACOMMAND" in w.command_history.toPlainText()
    assert not w.document.entities and w.last_command == ""


def test_editing_tab_completion_and_history_work_in_dynamic_input(main_window, qapp):
    w = main_window
    w.canvas.setFocus()
    type_keys(qapp, "LX")
    submit(qapp, Qt.Key.Key_Backspace)
    assert w.command_line.text() == "L"
    submit(qapp, Qt.Key.Key_Tab)
    assert w.command_line.text() == "LINE"
    submit(qapp)
    submit(qapp, Qt.Key.Key_Escape)
    type_keys(qapp, "X")
    submit(qapp, Qt.Key.Key_Up)
    assert w.command_line.text() == "LINE"
    assert "LINE" in w.command_overlay.entry.text()


@pytest.mark.parametrize("corner", [QPoint(2, 2), QPoint(590, 2), QPoint(2, 270), QPoint(590, 270)])
def test_cursor_prompt_stays_inside_canvas(main_window, qapp, corner):
    w = main_window
    w.canvas.setFocus()
    view = w.canvas.viewport()
    corner = QPoint(min(corner.x(), view.width() - 2), min(corner.y(), view.height() - 2))
    QTest.mouseMove(view, corner)
    type_keys(qapp, "CIRCLE")
    assert view.rect().contains(w.command_overlay.geometry())
    w.resize(850, 600)
    qapp.processEvents()
    assert view.rect().contains(w.command_overlay.geometry())


def test_each_model_pane_accepts_commands_and_focus_returns(main_window, qapp):
    w = main_window
    w.open_model_workspace(four=True)
    qapp.processEvents()
    workspace = w.model_workspace
    for view in workspace.views:
        view.setFocus()
        type_keys(qapp, "LEFT")
        assert w.command_overlay.parentWidget() is view
        assert view.rect().contains(w.command_overlay.geometry())
        submit(qapp, Qt.Key.Key_Space)
        assert workspace.active is view and view.camera.name == "Left"
        assert view.hasFocus()
        # Standard-view commands maximize the active pane; restore all four.
        workspace.layout_mode.setCurrentIndex(0)
        qapp.processEvents()
    type_keys(qapp, "L ")
    assert w.viewport_stack.currentWidget() is w.canvas
    assert w.current_tool.name == "LINE" and w.canvas.hasFocus()


def test_property_fields_do_not_start_commands(main_window, qapp):
    w = main_window
    w.canvas.setFocus()
    type_keys(qapp, "CI")
    other = QLineEdit(w.centralWidget())
    other.show()
    other.setFocus()
    type_keys(qapp, "LINE CIRCLE")
    assert other.text() == "LINE CIRCLE"
    assert w.command_overlay is None and w.command_line.text() == ""
    assert w.current_tool.name == "SELECT"
    other.deleteLater()


def test_new_document_clears_partial_dynamic_input(main_window, qapp):
    w = main_window
    w.start_orbit()
    qapp.processEvents()
    type_keys(qapp, "FRON")
    w._replace_document(Document())
    qapp.processEvents()
    assert w.command_overlay is None and w.command_line.text() == ""
    type_keys(qapp, "L ")
    assert w.current_tool.name == "LINE"


def test_compact_ribbon_keeps_tools_and_file_menu(main_window, qapp):
    w = main_window
    w.ribbon.set_compact(True)
    assert w.ribbon.height() == 66
    buttons = w.ribbon.findChildren(QToolButton)
    tools = [b for b in buttons if b.objectName().startswith("ribbon_")]
    assert len(tools) >= 35
    for button in tools:
        assert button.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly
        assert button.size().width() == 30 and button.size().height() == 30
        assert not button.icon().isNull() and button.toolTip() and button.accessibleName()
    QTest.mouseClick(w.ribbon.findChild(QToolButton, "ribbon_line"), Qt.MouseButton.LeftButton)
    assert w.current_tool.name == "LINE" and w.canvas.hasFocus()
    toolbar = w.findChild(QToolBar, "quick_access")
    assert toolbar is None
    assert not any(a.text() == "&File" for a in w.menuBar().actions())
    QTest.mouseClick(w.findChild(QToolButton, "quick_file_button"), Qt.MouseButton.LeftButton)
    assert w.file_workspace.isVisible() and w.file_workspace.window() is w
    assert {"New", "Open...", "Save", "Save As..."} <= {a.text() for a in w.file_shortcuts}
    w.file_workspace.dismiss()


def test_logo_menu_remains_available_without_menubar(main_window, qapp):
    w = main_window
    from pycad import appearance
    appearance.set_menubar(w, 0)
    logo = w.findChild(QToolButton, "quick_file_button")
    assert logo.isVisible()
    QTest.mouseClick(logo, Qt.MouseButton.LeftButton)
    assert w.file_workspace.isVisible()
    QTest.mouseClick(logo, Qt.MouseButton.LeftButton)
    assert not w.file_workspace.isVisible()
    w.activateWindow()
    logo.setFocus()
    qapp.processEvents()
    QTest.keyClick(logo, Qt.Key.Key_F, Qt.KeyboardModifier.AltModifier)
    QTest.qWait(200)
    qapp.processEvents()
    assert w.file_workspace.isVisible()
    w.file_workspace.dismiss()


def test_home_controls_survive_ribbon_rebuild(main_window, qapp):
    w = main_window
    logo = w.findChild(QToolButton, "quick_file_button")
    assert w.menuBar().cornerWidget(Qt.Corner.TopLeftCorner) is logo
    assert logo.iconSize().width() == 44
    combo = w.linetype_combo
    for compact in (True, False, True):
        w.ribbon.set_compact(compact)
        qapp.processEvents()
        assert w.ribbon.widget(0).isAncestorOf(combo)
        combo.setCurrentText("PHANTOM")
        assert w.document.current_linetype == "PHANTOM"
        w.ribbon.setCurrentIndex(1)
        assert not combo.isVisible()
        w.ribbon.setCurrentIndex(0)
        assert combo.isVisible()
    assert not w.findChildren(QToolBar)
