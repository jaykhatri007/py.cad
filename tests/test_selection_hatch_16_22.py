"""Modifier selection through real mouse events and dialog-first hatch entry."""
import pytest
from PyQt6.QtCore import Qt,QPointF
from PyQt6.QtGui import QMouseEvent
from PyQt6.QtWidgets import QDialog
from pycad.geometry import Point,LineEntity,RectangleEntity,HatchEntity,BlockDefinition
from pycad.tools import SelectTool,HatchTool
from pycad.hatch_ui import HatchDialog,defaults


def mouse(mw,x,y,mods=Qt.KeyboardModifier.NoModifier):
    canvas=mw.canvas;pos=canvas.world_to_screen(x,y)
    event=QMouseEvent(QMouseEvent.Type.MouseButtonPress,pos,pos,Qt.MouseButton.LeftButton,Qt.MouseButton.LeftButton,mods)
    canvas.mousePressEvent(event)
    release=QMouseEvent(QMouseEvent.Type.MouseButtonRelease,pos,pos,Qt.MouseButton.LeftButton,Qt.MouseButton.NoButton,mods)
    canvas.mouseReleaseEvent(release)


def shapes(mw):
    a=LineEntity(Point(-20,0),Point(-10,0));b=LineEntity(Point(0,0),Point(10,0));c=LineEntity(Point(20,0),Point(30,0))
    mw.document.entities=[a,b,c];mw.document.sync_associative()
    return a,b,c


def test_ctrl_add_alt_subtract_repeat_and_plain_replace(main_window):
    mw=main_window;a,b,c=shapes(mw)
    mouse(mw,-15,0);mouse(mw,5,0,Qt.KeyboardModifier.ControlModifier)
    assert mw.canvas.selected_entities==[a,b]
    mouse(mw,5,0,Qt.KeyboardModifier.ControlModifier)
    assert mw.canvas.selected_entities==[a,b]
    mouse(mw,-15,0,Qt.KeyboardModifier.AltModifier)
    assert mw.canvas.selected_entities==[b]
    mouse(mw,25,0);assert mw.canvas.selected_entities==[c]
    assert mw.document.undo_stack.count()==0
    assert a.p1.as_tuple()==(-20,0) and b.p1.as_tuple()==(0,0)


def test_modifiers_skip_grips_and_do_not_move(main_window):
    mw=main_window;a,b,c=shapes(mw);mw.canvas.selected_entities=[a]
    mouse(mw,-20,0,Qt.KeyboardModifier.AltModifier)
    assert not mw.canvas.selected_entities and mw.current_tool.grip_entity is None
    mouse(mw,0,0,Qt.KeyboardModifier.ControlModifier)
    assert mw.canvas.selected_entities==[b] and mw.current_tool.grip_entity is None
    assert mw.document.undo_stack.count()==0


def test_modifier_empty_click_keeps_selection_and_alt_wins(main_window):
    mw=main_window;a,b,c=shapes(mw);mw.canvas.selected_entities=[a,b]
    mouse(mw,0,20,Qt.KeyboardModifier.ControlModifier);assert mw.canvas.selected_entities==[a,b]
    mouse(mw,0,20,Qt.KeyboardModifier.AltModifier);assert mw.canvas.selected_entities==[a,b]
    mouse(mw,5,0,Qt.KeyboardModifier.ControlModifier|Qt.KeyboardModifier.AltModifier)
    assert mw.canvas.selected_entities==[a]
    mouse(mw,0,20);assert not mw.canvas.selected_entities


def test_group_and_locked_layer_selection(main_window):
    mw=main_window;a,b,c=shapes(mw)
    mw.document.extensions={'groups':{'Pair':[a.id,b.id]}}
    mouse(mw,25,0);mouse(mw,-15,0,Qt.KeyboardModifier.ControlModifier)
    assert mw.canvas.selected_entities==[c,a,b]
    mouse(mw,5,0,Qt.KeyboardModifier.AltModifier);assert mw.canvas.selected_entities==[c]
    mw.document.layers.set_locked('0',True)
    mouse(mw,-15,0,Qt.KeyboardModifier.ControlModifier)
    assert a not in mw.canvas.selected_entities and b not in mw.canvas.selected_entities


def test_modifier_box_selection_adds_and_subtracts(main_window):
    mw=main_window;a,b,c=shapes(mw);mw.canvas.selected_entities=[a]
    tool=mw.current_tool
    for mode,expected in [('add',[a,b]),('remove',[a])]:
        tool.box_selection_mode=mode
        mw.canvas.rubber_band_start=mw.canvas.world_to_screen(-1,1)
        mw.canvas.rubber_band_end=mw.canvas.world_to_screen(11,-1)
        tool.finish_drag();assert mw.canvas.selected_entities==expected


def configure(monkeypatch,accepted=True):
    calls=[]
    def execute(dialog):
        calls.append(dialog)
        assert not isinstance(dialog.parent().current_tool,HatchTool)
        return QDialog.DialogCode.Accepted if accepted else QDialog.DialogCode.Rejected
    monkeypatch.setattr(HatchDialog,'exec',execute)
    monkeypatch.setattr(HatchDialog,'values',lambda self:{**defaults(),'pattern':'ANSI31','angle':35,'pattern_scale':2})
    return calls


@pytest.mark.parametrize('route',['h','HATCH','HATCHSETTINGS','ribbon','direct'])
def test_hatch_routes_open_settings_before_area_picking(main_window,monkeypatch,route):
    mw=main_window;rect=RectangleEntity(Point(0,0),Point(20,20));mw.document.entities=[rect]
    mw.canvas.selected_entities=[rect];calls=configure(monkeypatch)
    if route=='ribbon':mw.run_ribbon_command('HATCH')
    elif route=='direct':mw.set_tool('HATCH')
    else:mw.command_line.setText(route);mw._on_command_entered()
    assert len(calls)==1 and isinstance(mw.current_tool,HatchTool)
    assert mw.current_tool.options['pattern']=='ANSI31' and mw.current_tool.options['pattern_scale']==2
    assert mw.document.entities==[rect] and mw.current_tool.boundary_points is None
    assert 'Pick inside' in mw.current_tool.status_prompt()
    mw.current_tool.on_key(Qt.Key.Key_Escape)
    assert mw.document.entities==[rect]


def test_cancel_hatch_dialog_keeps_selection_and_history(main_window,monkeypatch):
    mw=main_window;a,b,c=shapes(mw);mw.canvas.selected_entities=[a,b]
    configure(monkeypatch,False);old=mw.current_tool
    mw.set_tool('HATCH')
    assert mw.current_tool is old and mw.canvas.selected_entities==[a,b]
    assert mw.document.undo_stack.count()==0


def test_confirmed_settings_used_only_after_pick_and_enter(main_window,monkeypatch):
    mw=main_window;rect=RectangleEntity(Point(0,0),Point(20,20));mw.document.entities=[rect]
    configure(monkeypatch)
    mw.set_tool('HATCH');tool=mw.current_tool
    import pycad.geom_ops as geom
    monkeypatch.setattr(geom,'flood_fill_boundary',lambda *a,**kw:[Point(0,0),Point(20,0),Point(20,20),Point(0,20)])
    tool.on_click(10,10,'',Qt.MouseButton.LeftButton.value)
    assert mw.document.entities==[rect] and tool.boundary_points
    tool.on_key(Qt.Key.Key_Return)
    hatch=mw.document.entities[-1]
    assert isinstance(hatch,HatchEntity) and hatch.pattern=='ANSI31' and hatch.angle==35 and hatch.pattern_scale==2
    mw.document.undo_stack.undo();assert mw.document.entities==[rect]


def test_block_editor_uses_same_dialog_first_flow(main_window,monkeypatch):
    from pycad.block_editor import BlockEditorDialog
    dialog=BlockEditorDialog(main_window,'Symbol',BlockDefinition('Symbol',[]))
    calls=configure(monkeypatch);dialog.set_tool('HATCH')
    assert len(calls)==1 and isinstance(dialog.current_tool,HatchTool) and not dialog.document.entities
    dialog.reject();dialog.deleteLater()


def test_modifier_double_click_does_not_open_block_editor(main_window,monkeypatch):
    from pycad.geometry import BlockReferenceEntity
    mw=main_window
    mw.document.blocks['Symbol']=BlockDefinition('Symbol',[LineEntity(Point(0,0),Point(10,0))])
    ref=BlockReferenceEntity('Symbol',Point(0,0));mw.document.entities=[ref];mw.document.sync_associative()
    opened=[];monkeypatch.setattr(mw,'edit_block_dialog',lambda *a:opened.append(True))
    for mods,expected in [(Qt.KeyboardModifier.ControlModifier,[ref]),(Qt.KeyboardModifier.AltModifier,[])]:
        mouse(mw,5,0,mods)
        pos=mw.canvas.world_to_screen(5,0)
        event=QMouseEvent(QMouseEvent.Type.MouseButtonDblClick,pos,pos,Qt.MouseButton.LeftButton,Qt.MouseButton.LeftButton,mods)
        mw.canvas.mouseDoubleClickEvent(event)
        assert mw.canvas.selected_entities==expected and not opened
