"""Hatch double-click editing and honest CPU/GPU rendering controls."""
import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QMouseEvent,QImage,QPainter
from PyQt6.QtWidgets import QDialog
from pycad.geometry import Point,HatchEntity,LineEntity,BlockDefinition
from pycad.hatch_ui import HatchDialog
from pycad.graphics_ui import GraphicsDialog


def hatch():return HatchEntity([Point(0,0),Point(20,0),Point(20,20),Point(0,20)],pattern='ANSI31',pattern_scale=2)


def double(canvas,x=10,y=10,mods=Qt.KeyboardModifier.NoModifier):
    pos=canvas.world_to_screen(x,y)
    event=QMouseEvent(QMouseEvent.Type.MouseButtonDblClick,pos,pos,Qt.MouseButton.LeftButton,Qt.MouseButton.LeftButton,mods)
    canvas.mouseDoubleClickEvent(event)


def test_double_click_hatch_opens_current_settings_and_undo(main_window,monkeypatch):
    mw=main_window;h=hatch();mw.document.entities=[h];mw.document.sync_associative();opened=[]
    def execute(dialog):
        opened.append(dialog.pattern.currentText())
        assert dialog.controls['pattern_scale'].value()==2
        dialog.controls['pattern_scale'].setValue(4)
        return QDialog.DialogCode.Accepted
    monkeypatch.setattr(HatchDialog,'exec',execute)
    double(mw.canvas)
    assert opened==['ANSI31'] and mw.canvas.selected_entities==[h] and h.pattern_scale==4
    mw.document.undo_stack.undo();assert h.pattern_scale==2


def test_double_click_hatch_cancel_is_non_destructive(main_window,monkeypatch):
    mw=main_window;h=hatch();mw.document.entities=[h];mw.document.sync_associative();mw.document.mark_saved()
    monkeypatch.setattr(HatchDialog,'exec',lambda self:QDialog.DialogCode.Rejected)
    double(mw.canvas)
    assert h.pattern_scale==2 and mw.document.undo_stack.count()==0 and not mw.document.dirty


@pytest.mark.parametrize('mods',[Qt.KeyboardModifier.ControlModifier,Qt.KeyboardModifier.AltModifier])
def test_modifier_double_click_does_not_edit_hatch(main_window,monkeypatch,mods):
    h=hatch();main_window.document.entities=[h];main_window.document.sync_associative()
    monkeypatch.setattr(HatchDialog,'exec',lambda *_:pytest.fail('modifier selection must not edit'))
    double(main_window.canvas,mods=mods)
    assert h.pattern_scale==2


def test_hatch_hole_and_locked_layer_do_not_edit(main_window,monkeypatch):
    mw=main_window;h=hatch();h.holes=[[Point(5,5),Point(15,5),Point(15,15),Point(5,15)]]
    mw.document.entities=[h];mw.document.sync_associative()
    monkeypatch.setattr(HatchDialog,'exec',lambda *_:pytest.fail('not an editable hatch hit'))
    double(mw.canvas)
    mw.document.layers.set_locked('0',True);double(mw.canvas,2,2)


def test_hatch_editing_inside_block_editor(main_window,monkeypatch):
    from pycad.block_editor import BlockEditorDialog
    h=hatch();block=BlockDefinition('Symbol',[h]);main_window.document.blocks['Symbol']=block
    editor=BlockEditorDialog(main_window,'Symbol',block);opened=[]
    monkeypatch.setattr(HatchDialog,'exec',lambda self:opened.append(self) or QDialog.DialogCode.Rejected)
    double(editor.canvas)
    assert len(opened)==1 and block.entities[0].pattern_scale==2
    editor.reject();editor.deleteLater()


def test_processor_dialog_applies_mode_path_and_reports_cpu_work(main_window):
    mw=main_window;dialog=GraphicsDialog(mw)
    assert [dialog.mode.itemData(i) for i in range(3)]==['auto','hardware','software']
    assert 'GPU' in dialog.mode.itemText(1) and 'CPU' in dialog.mode.itemText(2)
    dialog.mode.setCurrentIndex(2);dialog.drawing_path.setCurrentIndex(1);dialog.apply()
    assert mw.graphics.mode=='software' and mw.canvas.drawing_path=='direct'
    from pycad import appsettings
    assert appsettings.get_settings().value('graphics/drawing_path')=='direct'
    report=mw.graphics.report();assert report['drawing_path']=='direct'
    assert report['process_execution']['DWG/DXF reading and conversion']=='CPU'
    assert report['process_execution']['Hatch boundaries and pattern generation']=='CPU'
    assert dialog.processes.rowCount()==6
    dialog.close();dialog.deleteLater()


def test_unavailable_gpu_reports_fallback_with_cpu_calculations(main_window):
    ctl=main_window.graphics;ctl.set_mode('hardware')
    assert ctl.mode=='hardware' and ctl.backend=='software'  # offscreen Qt has no GPU widget
    ctl.set_drawing_path('direct');report=ctl.report()
    assert report['requested_mode']=='hardware' and report['active_backend']=='software'
    assert all(value.startswith('CPU') for value in report['process_execution'].values())
    with pytest.raises(ValueError):ctl.set_drawing_path('cuda')


def test_direct_path_uses_active_painter_and_cached_path_reuses_images(main_window,monkeypatch):
    mw=main_window;mw.document.entities=[LineEntity(Point(0,0),Point(10,0))]
    calls=[];original=mw.canvas._draw_entities
    def draw(p,*a,**kw):calls.append(p.device());return original(p,*a,**kw)
    monkeypatch.setattr(mw.canvas,'_draw_entities',draw)
    image=QImage(600,400,QImage.Format.Format_ARGB32);image.fill(Qt.GlobalColor.transparent);p=QPainter(image)
    mw.graphics.set_drawing_path('direct')
    mw.canvas._draw_cached_entities(p);mw.canvas._draw_cached_entities(p)
    assert calls==[image,image]
    mw.graphics.set_drawing_path('cached');calls.clear()
    mw.canvas._draw_cached_entities(p);mw.canvas._draw_cached_entities(p);p.end()
    assert len(calls)==1


@pytest.mark.parametrize('command,expected',[('CPU','software'),('GPU','hardware')])
def test_quick_processor_commands(main_window,command,expected):
    main_window.command_line.setText(command);main_window._on_command_entered()
    assert main_window.graphics.mode==expected
