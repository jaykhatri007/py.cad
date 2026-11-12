"""Semantic UI colors. Drawing entity colors and branding are separate data."""

THEMES = {
    'Dark': dict(base='#484c52', surface='#393e44', raised='#595e65', text='#f0f2f5', muted='#c9cfd6', border='#747c86'),
    'Light': dict(base='#edf1f5', surface='#ffffff', raised='#dce4ed', text='#172a3d', muted='#465b70', border='#94a7bb'),
    'Midnight': dict(base='#182535', surface='#111d2b', raised='#293e55', text='#e1edf8', muted='#aabed3', border='#4b637c'),
}

# key, readable name, category, preset source (or explicit Dark/Light/Midnight).
ROLES = [
 ('ui_base','Window background','General','base'),
 ('ui_text','Main font color','General','text'),
 ('ui_muted','Secondary font color','General','muted'),
 ('ui_disabled','Disabled font color','General',('#a1a7ae','#707b86','#8294a8')),
 ('ui_border','Borders and separators','General','border'),
 ('ui_hover','Hover background','General',('#6b747f','#cedfed','#36566e')),
 ('ui_hover_text','Hover font color','General','text'),
 ('ui_selected','Selected / checked background','General',('#236784','#b9dbed','#175b7c')),
 ('ui_selected_text','Selected / checked font color','General',('#ffffff','#123347','#ffffff')),
 ('ui_error','Error messages','General',('#ffb0a8','#a32926','#ffaaa3')),
 ('ui_warning','Warning messages','General',('#ffe0a0','#805300','#f4d291')),
 ('ui_success','Information / success messages','General',('#aee5bf','#21633a','#9cdbb5')),
 ('ui_link','Links','General',('#9bdeff','#005ca8','#89d5ff')),
 ('ui_ribbon_top','Ribbon gradient — light end','Ribbon and tabs',('#686d74','#f9fbfd','#30465e')),
 ('ui_ribbon_bottom','Ribbon gradient — dark end','Ribbon and tabs',('#484d54','#dfe7ef','#1e3044')),
 ('ui_ribbon_text','Ribbon tool font color','Ribbon and tabs','text'),
 ('ui_caption_bg','Ribbon group caption background','Ribbon and tabs','base'),
 ('ui_caption_text','Ribbon group caption font color','Ribbon and tabs','muted'),
 ('ui_tab','Inactive tab background','Ribbon and tabs','surface'),
 ('ui_tab_text','Inactive tab font color','Ribbon and tabs','muted'),
 ('ui_tab_selected','Active tab background','Ribbon and tabs','raised'),
 ('ui_tab_selected_text','Active tab font color','Ribbon and tabs','text'),
 ('ui_menu','Menu background','Menus and status','surface'),
 ('ui_menu_text','Menu font color','Menus and status','text'),
 ('ui_status','Status bar background','Menus and status','base'),
 ('ui_status_text','Status bar font color','Menus and status','text'),
 ('ui_tooltip','Tooltip background','Menus and status','surface'),
 ('ui_tooltip_text','Tooltip font color','Menus and status','text'),
 ('ui_panel','Panel background','Panels and tables','surface'),
 ('ui_panel_header','Panel heading background','Panels and tables','raised'),
 ('ui_panel_text','Panel heading font color','Panels and tables','text'),
 ('ui_table','Table / list background','Panels and tables','surface'),
 ('ui_table_alt','Alternate table row','Panels and tables','base'),
 ('ui_table_text','Table / list font color','Panels and tables','text'),
 ('ui_header','Table header background','Panels and tables','raised'),
 ('ui_header_text','Table header font color','Panels and tables','text'),
 ('ui_gridline','Table grid lines','Panels and tables','border'),
 ('ui_input','Input background','Inputs and buttons','surface'),
 ('ui_input_text','Input font color','Inputs and buttons','text'),
 ('ui_placeholder','Placeholder font color','Inputs and buttons','muted'),
 ('ui_button_top','Button gradient — light end','Inputs and buttons','raised'),
 ('ui_button_bottom','Button gradient — dark end','Inputs and buttons','base'),
 ('ui_button_text','Button font color','Inputs and buttons','text'),
 ('ui_scrollbar','Scrollbar track','Inputs and buttons','surface'),
 ('ui_scrollbar_handle','Scrollbar handle','Inputs and buttons','border'),
 ('ui_command','Command bar / history background','Commands and overlays','surface'),
 ('ui_command_text','Command bar / history font color','Commands and overlays','text'),
 ('ui_command_prompt','Command prompt font color','Commands and overlays','muted'),
 ('ui_command_option','Command shortcut font color','Commands and overlays',('#9bdeff','#005ca8','#89d5ff')),
 ('ui_command_disabled','Unavailable command font color','Commands and overlays','muted'),
 ('ui_overlay','Cursor input / measurement background','Commands and overlays','surface'),
 ('ui_overlay_text','Cursor input / measurement font color','Commands and overlays','text'),
 ('ui_navigation','Navigation panel background','Navigation and icons','base'),
 ('ui_nav_face','Navigation cube face','Navigation and icons','raised'),
 ('ui_nav_face_alt','Navigation cube alternate face','Navigation and icons','surface'),
 ('ui_nav_text','Navigation font color','Navigation and icons','text'),
 ('ui_icon','Primary icon strokes','Navigation and icons',('#a2dff5','#245a83','#a2dff5')),
 ('ui_icon_text','Text / neutral icon strokes','Navigation and icons','text'),
 ('ui_icon_secondary','Secondary icon strokes','Navigation and icons',('#f2d18b','#805300','#f2d18b')),
 ('ui_icon_tertiary','Constraint / extra icon strokes','Navigation and icons',('#a3dfce','#246952','#a3dfce')),
 ('ui_icon_fill','Icon fill','Navigation and icons',('#bc9db7','#8a5381','#bc9db7')),
 ('ui_selection','Drawing selection outline','Viewport guides',('#00aeff','#005eb8','#27bcff')),
 ('ui_preview','Drafting preview','Viewport guides',('#6cdaa6','#176b47','#6cdaa6')),
 ('ui_grip','Grip fill','Viewport guides','surface'),
 ('ui_snap','Snap marker','Viewport guides',('#ffd34f','#8a5300','#ffd34f')),
 ('ui_axis','2D grid axes','Viewport guides',('#a5a58a','#7a7955','#8f9eae')),
 ('ui_page_border','Paper / inactive viewport border','Viewport guides','border'),
 ('ui_3d_grid','3D navigation grid','Viewport guides',('#464d56','#d1d9e3','#23344a')),
 ('ui_3d_text','3D hint font color','Viewport guides','muted'),
 ('ui_3d_edge','3D default edge','Viewport guides',('#c2d4e1','#334d65','#abc6da')),
 ('ui_axis_x','3D X axis','Viewport guides',('#f59a9b','#b43236','#ef7f80')),
 ('ui_axis_y','3D Y axis','Viewport guides',('#a0d9ad','#247142','#90d19e')),
 ('ui_axis_z','3D Z axis','Viewport guides',('#95c6fa','#2468aa','#68aaf2')),
]
ROLE_KEYS = tuple(row[0] for row in ROLES)


def resolve(options):
    theme = options['theme']
    preset = THEMES[theme]
    index = tuple(THEMES).index(theme)
    result = dict(options)
    for key, _, _, source in ROLES:
        result[key] = options.get(key) or (preset[source] if isinstance(source, str) else source[index])
    return result


def gradient(top, bottom):
    return f'qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 {top},stop:1 {bottom})'


def ribbon_stylesheet(c):
    r = gradient(c['ui_ribbon_top'], c['ui_ribbon_bottom'])
    return f'''
QTabWidget#workspace_ribbon::pane, QWidget[ribbonPanel="true"] {{ background:{r}; border-color:{c['ui_border']}; }}
QTabWidget#workspace_ribbon QToolButton {{ color:{c['ui_ribbon_text']}; }}
QTabWidget#workspace_ribbon QToolButton:disabled {{ color:{c['ui_disabled']}; }}
QTabWidget#workspace_ribbon QToolButton:hover {{ color:{c['ui_hover_text']}; }}
QTabWidget#workspace_ribbon QToolButton:checked {{ color:{c['ui_selected_text']}; }}
QLabel[ribbonCaption="true"] {{ background:{c['ui_caption_bg']}; color:{c['ui_caption_text']}; }}
'''


def stylesheet(c):
    r = gradient(c['ui_ribbon_top'], c['ui_ribbon_bottom'])
    b = gradient(c['ui_button_top'], c['ui_button_bottom'])
    return f'''
QWidget {{ background:{c['ui_base']}; color:{c['ui_text']}; }}
QLabel {{ background:transparent; }}
QWidget:disabled {{ color:{c['ui_disabled']}; }}
QMainWindow, QDialog, QDockWidget {{ background:{c['ui_base']}; }}
QDockWidget > QWidget {{ background:{c['ui_panel']}; }}
QMessageBox[messageSeverity="error"] QLabel#qt_msgbox_label {{ color:{c['ui_error']}; }}
QMessageBox[messageSeverity="warning"] QLabel#qt_msgbox_label {{ color:{c['ui_warning']}; }}
QMessageBox[messageSeverity="information"] QLabel#qt_msgbox_label {{ color:{c['ui_success']}; }}
QMenuBar, QToolBar {{ background:{r}; color:{c['ui_menu_text']}; }}
QMenuBar::item {{ background:transparent; color:{c['ui_menu_text']}; }}
QMenu {{ background:{c['ui_menu']}; color:{c['ui_menu_text']}; border:1px solid {c['ui_border']}; }}
QMenu::item {{ color:{c['ui_menu_text']}; }}
QMenu::item:disabled {{ color:{c['ui_disabled']}; }}
QMenuBar::item:selected, QMenu::item:selected {{ background:{c['ui_selected']}; color:{c['ui_selected_text']}; }}
QStatusBar, QStatusBar QLabel, QStatusBar QToolButton {{ background:{c['ui_status']}; color:{c['ui_status_text']}; }}
QDockWidget::title {{ background:{c['ui_panel_header']}; color:{c['ui_panel_text']}; }}
QFrame#file_workspace {{ background:{c['ui_panel']}; }}
QTableView, QTableWidget, QListView, QListWidget, QTreeView, QTreeWidget {{ background:{c['ui_table']}; alternate-background-color:{c['ui_table_alt']}; color:{c['ui_table_text']}; gridline-color:{c['ui_gridline']}; selection-background-color:{c['ui_selected']}; selection-color:{c['ui_selected_text']}; }}
QHeaderView::section {{ background:{c['ui_header']}; color:{c['ui_header_text']}; border:1px solid {c['ui_border']}; }}
QLineEdit, QPlainTextEdit, QTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{ background:{c['ui_input']}; color:{c['ui_input_text']}; border-color:{c['ui_border']}; selection-background-color:{c['ui_selected']}; selection-color:{c['ui_selected_text']}; placeholder-text-color:{c['ui_placeholder']}; }}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus {{ border-color:{c['accent']}; }}
QComboBox QAbstractItemView {{ background:{c['ui_menu']}; color:{c['ui_menu_text']}; selection-background-color:{c['ui_selected']}; selection-color:{c['ui_selected_text']}; }}
QPushButton {{ background:{b}; color:{c['ui_button_text']}; border-color:{c['ui_border']}; }}
QToolButton {{ background:transparent; color:{c['ui_button_text']}; }}
QPushButton:hover, QToolButton:hover {{ background:{c['ui_hover']}; color:{c['ui_hover_text']}; border-color:{c['accent']}; }}
QPushButton:checked, QToolButton:checked, QPushButton:pressed, QToolButton:pressed {{ background:{c['ui_selected']}; color:{c['ui_selected_text']}; }}
QPushButton:disabled, QToolButton:disabled, QLineEdit:disabled {{ color:{c['ui_disabled']}; }}
QTabBar::tab {{ background:{c['ui_tab']}; color:{c['ui_tab_text']}; }}
QTabBar::tab:selected {{ background:{c['ui_tab_selected']}; color:{c['ui_tab_selected_text']}; border-bottom-color:{c['accent']}; }}
QTabWidget#workspace_ribbon::pane, QWidget[ribbonPanel="true"] {{ background:{r}; border-color:{c['ui_border']}; }}
QTabWidget#workspace_ribbon QToolButton {{ color:{c['ui_ribbon_text']}; }}
QTabWidget#workspace_ribbon QToolButton:disabled {{ color:{c['ui_disabled']}; }}
QTabWidget#workspace_ribbon QToolButton:hover {{ color:{c['ui_hover_text']}; }}
QTabWidget#workspace_ribbon QToolButton:checked {{ color:{c['ui_selected_text']}; }}
QLabel[ribbonCaption="true"] {{ background:{c['ui_caption_bg']}; color:{c['ui_caption_text']}; }}
QGroupBox {{ border-color:{c['ui_border']}; }}
QGroupBox::title {{ color:{c['ui_muted']}; }}
QScrollBar {{ background:{c['ui_scrollbar']}; }}
QScrollBar::handle {{ background:{c['ui_scrollbar_handle']}; }}
QToolTip {{ background:{c['ui_tooltip']}; color:{c['ui_tooltip_text']}; border:1px solid {c['ui_border']}; }}
QFrame#viewport_navigation {{ background:{c['ui_navigation']}; border-color:{c['ui_border']}; }}
QFrame#viewport_navigation QComboBox {{ background:{c['ui_navigation']}; color:{c['ui_nav_text']}; }}
QFrame#viewport_command_prompt, QFrame#dynamic_dimension_input, QFrame#live_measurements_overlay {{ background:{c['ui_overlay']}; border-color:{c['accent']}; }}
QFrame#viewport_command_prompt QLabel, QFrame#dynamic_dimension_input QLabel, QFrame#live_measurements_overlay QLabel {{ color:{c['ui_overlay_text']}; }}
QFrame#dynamic_dimension_input QLineEdit {{ background:{c['ui_overlay']}; color:{c['ui_overlay_text']}; }}
QLabel#dynamic_command_text {{ background:{c['ui_overlay']}; color:{c['ui_overlay_text']}; border-color:{c['ui_border']}; }}
QWidget#command_bar, QPlainTextEdit#command_history, QLineEdit#command_line, QScrollArea#command_options_row, QLabel#command_options {{ background:{c['ui_command']}; color:{c['ui_command_text']}; }}
QLabel#command_prompt {{ color:{c['ui_command_prompt']}; }}
'''
