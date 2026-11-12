"""Stateful keyword choices exercise the actual command and viewport paths."""

from PyQt6.QtCore import QPoint, QPointF, Qt
from PyQt6.QtTest import QTest
from pycad import command_options
from pycad.geometry import LineEntity, Point


def enter(w, text):
    w.command_line.setText(text)
    w._on_command_entered()


def choices(w):
    return {o.key: o for o in command_options.options(w)}


def test_line_shows_highlighted_choices_and_stateful_undo_close(main_window):
    w = main_window
    assert w.command_options_scroll.isHidden()
    base_height = w.command_dock.height()
    unrelated = LineEntity(Point(-10, -10), Point(-5, -5))
    w.document.add_entity(unrelated)
    enter(w, "L")
    assert w.current_tool.name == "LINE"
    assert not w.command_options_scroll.isHidden()
    assert "<b><u>U</u></b>ndo" in w.command_options_label.text()
    assert not choices(w)["U"].enabled and not choices(w)["C"].enabled
    assert 'href="U"' not in w.command_options_label.text()
    for text in ("0,0", "10,0", "10,10"):
        enter(w, text)
    assert choices(w)["C"].enabled
    enter(w, "Undo")
    assert len(w.document.entities) == 2 and unrelated in w.document.entities
    assert not choices(w)["C"].enabled
    enter(w, "C")
    assert w.current_tool.name == "LINE" and len(w.document.entities) == 2
    assert "not available" in w.command_history.toPlainText()
    enter(w, "10,10")
    enter(w, "Close")
    assert w.current_tool.name == "SELECT" and len(w.document.entities) == 4
    assert w.command_options_scroll.isHidden()
    assert w.command_dock.height() == base_height


def test_polyline_undo_uses_local_vertices_not_global_document_undo(main_window):
    w = main_window
    enter(w,"PL")
    for point in ("0,0","20,0","20,20"):
        enter(w,point)
    enter(w,"U")
    assert len(w.current_tool.points)==2 and not w.document.entities
    enter(w,"20,20")
    w.trigger_command_option("C")
    assert w.current_tool.name == "SELECT"
    assert len(w.document.entities)==1 and w.document.entities[0].closed


def test_zoom_menu_does_not_fit_until_option_chosen_and_previous_restores(main_window):
    w=main_window
    small=LineEntity(Point(10,10),Point(20,20))
    w.document.add_entity(small)
    w.document.add_entity(LineEntity(Point(1000,1000),Point(2000,2000)))
    w.canvas.selected_entities=[small]
    w.canvas.zoom=3
    w.canvas.pan_offset=QPointF(-5,-6)
    enter(w,"Z")
    assert w.current_tool.name=="ZOOM" and w.canvas.zoom==3
    assert {"W","S","E","A","P","I","O","R"} <= choices(w).keys()
    assert not choices(w)["P"].enabled
    enter(w,"Selected")
    assert w.current_tool.name=="SELECT"
    assert w.canvas.pan_offset==QPointF(15,15) and w.canvas.zoom>3
    enter(w,"Z");enter(w,"P")
    assert w.canvas.zoom==3 and w.canvas.pan_offset==QPointF(-5,-6)
    w.new_file();enter(w,"Z")
    assert not choices(w)["P"].enabled


def test_zoom_window_clickable_option_coordinates_and_invalid_corner(main_window,qapp):
    w=main_window
    enter(w,"Z")
    label=w.command_options_label
    QTest.mouseClick(label,Qt.MouseButton.LeftButton,pos=QPoint(5,label.height()//2))
    qapp.processEvents()
    assert w.current_tool.mode=="window"
    old=w.canvas.zoom
    enter(w,"0,0");enter(w,"0,10")
    assert w.current_tool.name=="ZOOM" and len(w.current_tool.points)==1
    assert w.canvas.zoom==old
    enter(w,"10,10")
    assert w.current_tool.name=="SELECT" and w.canvas.pan_offset==QPointF(5,5)


def test_zoom_selected_allows_picking_after_menu(main_window):
    w=main_window
    line=LineEntity(Point(0,0),Point(100,0));w.document.add_entity(line)
    enter(w,"Z");enter(w,"S")
    assert w.current_tool.mode=="selected"
    assert not choices(w)["ENTER"].enabled
    w.current_tool.on_click(50,0,"",Qt.MouseButton.LeftButton.value)
    w.update_status()
    assert choices(w)["ENTER"].enabled
    w.trigger_command_option("ENTER")
    assert w.current_tool.name=="SELECT" and w.canvas.pan_offset.x()==50


def test_viewport_shortcut_options_are_not_global_command_aliases(main_window,qapp):
    w=main_window
    viewport=w.canvas.viewport()
    viewport.setFocus()
    QTest.keyClick(viewport,Qt.Key.Key_Z)
    QTest.keyClick(w.command_line,Qt.Key.Key_Return)
    assert w.current_tool.name=="ZOOM"
    QTest.keyClick(viewport,Qt.Key.Key_W)
    QTest.keyClick(w.command_line,Qt.Key.Key_Space)
    assert w.current_tool.mode=="window"
    assert w.command_matches("s")[0]=="Selected"
    w.trigger_command_option("ESC")
    assert w.current_tool.name=="SELECT" and w.command_options_scroll.isHidden()


def test_existing_angular_and_ordinate_keywords_use_context(main_window):
    w=main_window
    enter(w,"DIMANGULAR")
    assert {"P","L","A"}<=choices(w).keys()
    enter(w,"Lines")
    assert w.current_tool.name=="DIMANGULAR" and w.current_tool.mode=="lines"
    w.cancel_command();enter(w,"DIMORDINATE")
    assert {"X","Y","O"}<=choices(w).keys()
    enter(w,"Origin")
    assert w.current_tool.origin_pending


def test_text_stays_literal_and_escape_clears_options(main_window):
    w=main_window
    enter(w,"TEXT")
    w.current_tool.on_click(0,0,"",Qt.MouseButton.LeftButton.value)
    enter(w,"Close")
    assert w.document.entities[-1].text=="Close"
    assert w.current_tool.name=="SELECT" and w.command_options_scroll.isHidden()


def test_zoom_invalid_factor_keeps_view_and_options(main_window):
    w=main_window
    before=(w.canvas.zoom,QPointF(w.canvas.pan_offset))
    enter(w,"Z");enter(w,"-2")
    assert w.current_tool.name=="ZOOM" and w.command_options_scroll.isVisible()
    assert (w.canvas.zoom,w.canvas.pan_offset)==before
    enter(w,"2x")
    assert w.current_tool.name=="SELECT" and w.canvas.zoom==before[0]*2


def test_mirror_confirmation_choices_only_appear_at_confirmation(main_window):
    w=main_window
    line=LineEntity(Point(1,0),Point(2,0));w.document.add_entity(line)
    w.canvas.selected_entities=[line]
    enter(w,"MIRROR")
    assert "Y" not in choices(w)
    w.current_tool.on_click(0,0,"",Qt.MouseButton.LeftButton.value)
    w.current_tool.on_click(0,10,"",Qt.MouseButton.LeftButton.value)
    w.update_status()
    assert {"Y","N"} <= choices(w).keys()
    w.trigger_command_option("N")
    assert w.current_tool.name=="SELECT" and len(w.document.entities)==2
    assert line in w.document.entities


def test_zoom_realtime_keeps_cancel_choice(main_window):
    w=main_window
    enter(w,"Z");enter(w,"R")
    assert w.canvas.navigation_zoom
    assert choices(w)["ESC"].enabled and w.command_options_scroll.isVisible()
    w.trigger_command_option("ESC")
    assert not w.canvas.navigation_zoom and w.command_options_scroll.isHidden()


def test_zoom_preserves_3d_mode_and_history(main_window):
    w=main_window
    w.open_model_workspace("Top",False)
    view=w.model_workspace.active
    before=view.camera.scale
    enter(w,"Z")
    assert w.viewport_stack.currentWidget() is w.model_workspace
    assert "W" not in choices(w) and "S" not in choices(w)
    enter(w,"I")
    assert view.camera.scale==before*2
    enter(w,"Z");enter(w,"P")
    assert view.camera.scale==before
    assert w.viewport_stack.currentWidget() is w.model_workspace
