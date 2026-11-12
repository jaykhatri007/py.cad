import pytest
from PyQt6.QtCore import Qt,QEvent,QPointF,QPoint,QSize,QRect
from PyQt6.QtGui import QMouseEvent
from pycad.native_io import document_to_dict

def move(w,qapp,x,y):
 view=w.canvas.viewport();pos=w.canvas.world_to_screen(x,y);event=QMouseEvent(QEvent.Type.MouseMove,pos,QPointF(view.mapToGlobal(pos.toPoint())),Qt.MouseButton.NoButton,Qt.MouseButton.NoButton,Qt.KeyboardModifier.NoModifier);qapp.sendEvent(view,event);qapp.processEvents()

@pytest.mark.parametrize('command,points,cursor,expected',[
 ('LINE',[(0,0)],(3,4),{'Length':'5.000 mm','Angle':'53.13°'}),
 ('CIRCLE',[(0,0)],(3,4),{'Radius':'5.000 mm','Diameter':'10.000 mm'}),
 ('RECTANGLE',[(0,0)],(3,4),{'Width':'3.000 mm','Height':'4.000 mm'}),
 ('PLINE',[(0,0)],(3,4),{'Length':'5.000 mm'}),
])
def test_live_sizes_on_cursor_even_with_f12_off(main_window,qapp,command,points,cursor,expected):
 w=main_window;w.canvas.snap_enabled=False;w.dynamic_action.setChecked(False);w.toggle_measurements();assert w.cursor_dimensions_action.isChecked();w.set_tool(command)
 for p in points:w._on_world_clicked(*p,'',1)
 before=document_to_dict(w.document);move(w,qapp,*cursor);hud=w.canvas.measurement_overlay
 assert hud.isVisible() and w.canvas.viewport().rect().contains(hud.geometry())
 visible={label.text():value.text() for label,value in hud.cells if label.isVisible()}
 for label,text in expected.items():assert visible[label]==text
 assert document_to_dict(w.document)==before
 w.cancel_command();assert not hud.isVisible()

def test_numeric_radius_editor_keeps_radius_diameter_readout(main_window,qapp):
 w=main_window;w.canvas.snap_enabled=False;w.set_tool('CIRCLE');w._on_world_clicked(0,0,'',1);move(w,qapp,30,20);editor=w.canvas.dynamic_input;assert editor.begin('10');qapp.processEvents();hud=w.canvas.measurement_overlay
 assert editor.isVisible() and hud.isVisible() and not editor.geometry().intersects(hud.geometry())
 assert dict(hud.display_values)['Diameter']=='20.000 mm'

def test_cursor_toggle_independent_persistent_and_restorable(main_window,qapp):
 from pycad.appsettings import get_settings
 w=main_window;w.canvas.snap_enabled=False;w.set_tool('LINE');w._on_world_clicked(0,0,'',1);move(w,qapp,3,4);hud=w.canvas.measurement_overlay
 w.run_ribbon_command('CURSORDIMS');assert not hud.isVisible() and not w.cursor_dimensions_action.isChecked()
 settings=get_settings();assert settings.value('drafting/cursor_dimensions',True,type=bool) is False
 w.run_ribbon_command('CURSORDIMS');assert hud.isVisible()
 w.dynamic_action.trigger();assert hud.isVisible()

def test_old_disabled_f12_settings_do_not_disable_new_readout(main_window,qapp):
 from pycad.appsettings import get_settings
 from pycad.main_window import MainWindow
 prefs=get_settings();prefs.setValue('drafting/live_measurements',False);prefs.sync();w=MainWindow();w.resize(1100,750);w.show();qapp.processEvents()
 try:
  assert not w.dynamic_action.isChecked() and w.cursor_dimensions_action.isChecked()
  w.canvas.snap_enabled=False;w.set_tool('CIRCLE');w._on_world_clicked(0,0,'',1);move(w,qapp,3,4);assert w.canvas.measurement_overlay.isVisible()
 finally:
  w.cancel_command()
  for s in w.drawing_tabs.sessions:s['doc'].mark_saved()
  w.close();w.deleteLater();qapp.processEvents()

def test_long_values_not_elided_and_click_does_not_commit_readout(main_window,qapp):
 w=main_window;w.canvas.snap_enabled=False;w.document.unit_settings['length_precision']=6;w.set_tool('LINE');w._on_world_clicked(0,0,'',1);before=document_to_dict(w.document);w.canvas.measurement_overlay.inside=True;w._on_mouse_moved(1234567.123456,0,'');qapp.processEvents();hud=w.canvas.measurement_overlay
 assert hud.isVisible();assert next(value.text() for label,value in hud.cells if label.text()=='Length')==dict(hud.display_values)['Length'];assert document_to_dict(w.document)==before

def test_collision_finds_space_beyond_cursor_quadrants():
 from pycad.measurements import overlay_rect
 avoid=QRect(4,42,300,100);rect=overlay_rect(QPoint(20,20),QSize(160,70),QRect(0,0,445,250),[avoid]);assert rect is not None and not rect.intersects(avoid)
