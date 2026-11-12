"""Actual Qt appearance persistence, text pigments, dialogs and reset behavior."""
import copy
import pytest
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QDialog, QLabel, QLineEdit, QPushButton, QVBoxLayout
from pycad import appearance, appsettings
from pycad.theme_palette import ROLES, resolve
from pycad.native_io import document_to_dict


def test_default_is_lighter_neutral_grey_and_uses_gradient(main_window):
    c=resolve(appearance.DEFAULTS)
    for key in ('ui_base','ui_ribbon_top','ui_ribbon_bottom'):
        color=QColor(c[key])
        assert color.lightness()>65 and max(color.red(),color.green(),color.blue())-min(color.red(),color.green(),color.blue())<25
    assert 'qlineargradient' in main_window.styleSheet()
    assert c['ui_ribbon_top'] in main_window.ribbon.styleSheet()
    assert c['ui_ribbon_bottom'] in main_window.ribbon.styleSheet()


def test_all_roles_are_editable_and_searchable(main_window,qapp):
    d=appearance.OptionsDialog(main_window);d.show();qapp.processEvents()
    assert set(d.color_buttons)==set(appearance.DEFAULTS)-{'theme'}
    assert len(ROLES)>60
    d.color_category.setCurrentText('Commands and overlays')
    d.color_search.setText('font')
    assert d.color_buttons['ui_command_text'].isVisible()
    assert not d.color_buttons['ui_ribbon_top'].isVisible()
    d.reject()


def test_color_picker_edits_draft_until_apply(main_window,monkeypatch):
    d=appearance.OptionsDialog(main_window)
    monkeypatch.setattr(appearance.QColorDialog,'getColor',lambda *args:QColor('#aabb33'))
    d.choose_color('ui_text',d.color_buttons['ui_text'])
    assert d.colors['ui_text']=='#aabb33'
    assert appearance.settings()['ui_text']==''
    d.reject()
    assert appearance.settings()['ui_text']==''


def test_reset_single_all_cancel_and_persistence(main_window):
    w=main_window
    custom={**appearance.DEFAULTS,'ui_text':'#e8dbb2','ui_button_text':'#bbf9ce','model':'#343f54'}
    appearance.save(w,custom)
    d=appearance.OptionsDialog(w)
    d.reset_color('ui_text')
    assert d.colors['ui_text']=='' and d.colors['ui_button_text']=='#bbf9ce'
    d.reset_colors();assert d.colors==appearance.DEFAULTS
    d.reject();assert appearance.settings()==custom
    d=appearance.OptionsDialog(w);d.reset_colors();d.apply_changes();d.reject()
    assert appearance.settings()==appearance.DEFAULTS
    assert w.palette().color(QPalette.ColorRole.WindowText).name()==resolve(appearance.DEFAULTS)['ui_text']


def test_reset_follows_selected_preset_and_does_not_change_drafting(main_window):
    w=main_window;d=appearance.OptionsDialog(w)
    old_snaps=set(w.canvas.snap_modes);old_spacing=w.canvas.grid_spacing
    d.colors['ui_text']='#123456';d.theme.setCurrentText('Light');d.reset_colors()
    assert resolve(d.colors)['ui_text']=='#172a3d'
    d.apply_changes();d.reject()
    assert appearance.settings()['theme']=='Light' and appearance.settings()['ui_text']==''
    assert w.canvas.snap_modes==old_snaps and w.canvas.grid_spacing==old_spacing


def test_font_colors_reach_real_controls_and_future_dialogs(main_window,qapp):
    w=main_window
    options={**appearance.DEFAULTS,'ui_text':'#ffe190','ui_input_text':'#8bffd0',
             'ui_button_text':'#ffbbdd','ui_command_text':'#b5caff','ui_selected_text':'#ffdddd'}
    appearance.save(w,options)
    dialog=QDialog(w);layout=QVBoxLayout(dialog)
    label=QLabel('Readable label');edit=QLineEdit('Editable font');button=QPushButton('Readable button')
    for item in (label,edit,button):layout.addWidget(item)
    dialog.show();qapp.processEvents()
    assert label.palette().color(QPalette.ColorRole.WindowText).name()=='#ffe190'
    assert edit.palette().color(QPalette.ColorRole.Text).name()=='#8bffd0'
    assert button.palette().color(QPalette.ColorRole.ButtonText).name()=='#ffbbdd'
    assert w.command_line.palette().color(QPalette.ColorRole.Text).name()=='#b5caff'
    options['ui_text']='#c4f1a0';appearance.save(w,options);qapp.processEvents()
    assert label.palette().color(QPalette.ColorRole.WindowText).name()=='#c4f1a0'
    # Verify real raster text has the requested pigment, not just a CSS string.
    image=button.grab().toImage()
    pigment=QColor('#ffbbdd')
    assert sum(max(abs(image.pixelColor(x,y).red()-pigment.red()),
                   abs(image.pixelColor(x,y).green()-pigment.green()),
                   abs(image.pixelColor(x,y).blue()-pigment.blue()))<20
               for x in range(image.width()) for y in range(image.height()))>10
    dialog.close();dialog.deleteLater()


def test_command_links_and_icons_use_overrides(main_window,qapp):
    w=main_window
    options={**appearance.DEFAULTS,'ui_command_option':'#f4be88','ui_command_disabled':'#bbbbaa','ui_icon':'#ff4444'}
    appearance.save(w,options)
    w.command_line.setText('L');w._on_command_entered();qapp.processEvents()
    assert '#f4be88' in w.command_options_label.text() and '#bbbbaa' in w.command_options_label.text()
    from pycad.workspace_ui import tool_icon
    image=tool_icon('LINE').pixmap(32,32).toImage()
    assert any(image.pixelColor(x,y).red()>240 and 50<image.pixelColor(x,y).green()<90 and image.pixelColor(x,y).alpha()>100
               for x in range(32) for y in range(32))


def test_theme_changes_do_not_mutate_drawings_or_layer_colors(main_window):
    w=main_window
    from pycad.geometry import LineEntity,Point
    w.document.add_entity(LineEntity(Point(0,0),Point(10,0),color='#fefefe'))
    before=copy.deepcopy(document_to_dict(w.document))
    options={**appearance.DEFAULTS,**{key:'#747e89' for key,_,_,_ in ROLES}}
    appearance.save(w,options)
    assert document_to_dict(w.document)==before


def test_legacy_defaults_upgrade_but_custom_colors_survive(main_window):
    s=appsettings.get_settings()
    s.remove('appearance')
    for key,value in appearance.LEGACY_DEFAULTS.items():s.setValue('appearance/'+key,value)
    s.setValue('appearance/paper','#fef3e0')
    result=appearance.settings()
    assert result['model']==appearance.DEFAULTS['model'] and result['paper']=='#fef3e0'
    result['model']='#1e1e20';appearance.save(main_window,result)
    assert appearance.settings()['model']=='#1e1e20'


def test_invalid_stored_colors_fall_back_and_cannot_inject_styles(main_window):
    s=appsettings.get_settings();s.setValue('appearance/ui_text','white; background:red')
    assert appearance.settings()['ui_text']==''
    options=appearance.settings();options['ui_text']='white; background:red'
    with pytest.raises(ValueError):appearance.save(main_window,options)


def test_repeated_theme_switches_do_not_accumulate_css(main_window):
    w=main_window
    appearance.save(w,appearance.DEFAULTS);before=w.styleSheet();ribbon=w.ribbon.styleSheet()
    appearance.save(w,{**appearance.DEFAULTS,'theme':'Light'})
    appearance.save(w,appearance.DEFAULTS)
    assert w.styleSheet()==before and w.ribbon.styleSheet()==ribbon


def test_message_font_roles_apply_to_real_dialogs(main_window,qapp):
    from PyQt6.QtWidgets import QMessageBox
    options={**appearance.DEFAULTS,'ui_error':'#ff9988','ui_warning':'#ffee99','ui_success':'#aaffbb'}
    appearance.save(main_window,options)
    for icon,role in ((QMessageBox.Icon.Critical,'ui_error'),
                      (QMessageBox.Icon.Warning,'ui_warning'),
                      (QMessageBox.Icon.Information,'ui_success')):
        box=QMessageBox(icon,'Theme test','Readable message',parent=main_window)
        box.show();qapp.processEvents()
        label=box.findChild(QLabel,'qt_msgbox_label')
        assert label.palette().color(QPalette.ColorRole.WindowText).name()==options[role]
        box.close();box.deleteLater()
