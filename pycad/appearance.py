"""Persistent appearance and drafting options, independent of drawing content."""

import re
from PyQt6.QtCore import QObject, QEvent
from PyQt6.QtGui import QColor, QPalette, QBrush
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QGridLayout,
    QFormLayout,
    QTabWidget,
    QWidget,
    QComboBox,
    QPushButton,
    QColorDialog,
    QCheckBox,
    QSpinBox,
    QDoubleSpinBox,
    QLabel,
    QDialogButtonBox, QScrollArea, QLineEdit, QHBoxLayout, QApplication, QMessageBox,
)
from . import appsettings

from .theme_palette import THEMES, ROLES, ROLE_KEYS, resolve, stylesheet, ribbon_stylesheet

DEFAULTS = dict(theme='Dark', model='#393d43', paper='#ebebeb',
                model3d='#363c45', grid='#4a5058', accent='#69c9ee',
                **dict.fromkeys(ROLE_KEYS, ''))
SPACE_LABELS = [('model','Model space'),('paper','Paper space'),('model3d','3D space'),
                ('grid','Drafting grid'),('accent','Accent / focus border')]
LEGACY_DEFAULTS = dict(model='#1e1e20', model3d='#111a25', grid='#2d2d30', accent='#5ac8ec')
_ACTIVE_COLORS = None

SNAPS = (
    "Endpoint",
    "Midpoint",
    "Center",
    "Intersection",
    "Perpendicular",
    "Quadrant",
    "Tangent",
    "Nearest",
    "Grid",
)


def settings():
    s = appsettings.get_settings()
    result = {k: s.value('appearance/' + k, v) for k, v in DEFAULTS.items()}
    if result['theme'] not in THEMES:
        result['theme'] = 'Dark'
    for key in DEFAULTS.keys() - {'theme'}:
        value = result[key]
        if not isinstance(value, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', value):
            result[key] = DEFAULTS[key]
    # Upgrade only stock colors from the older dark default. User-picked
    # colors and old presets remain available, and explicit new saves opt out.
    if not s.contains('appearance/palette_revision') and result['theme'] == 'Dark':
        for key, value in LEGACY_DEFAULTS.items():
            if result[key] == value:
                result[key] = DEFAULTS[key]
    return result


def colors(widget=None):
    current = widget
    while current is not None:
        value = getattr(current, 'appearance_colors', None)
        if value is not None:
            return value
        current = current.parentWidget() if isinstance(current, QWidget) else None
    return _ACTIVE_COLORS or resolve(settings())


def themed_qss(source, options, scope=''):
    """Recolor local styles by selector/property, preserving geometry and fonts."""
    c = resolve(options)
    def rule(match):
        selector, body = match.group(1), match.group(2)
        lower = selector.lower()
        def declaration(m):
            prop, value = m.group(1), m.group(2)
            p = prop.strip().lower()
            role = 'ui_base'
            if 'border' in p or p == 'gridline-color':
                role = 'accent' if ':focus' in lower or ':hover' in lower else 'ui_border'
            elif p == 'selection-background-color': role = 'ui_selected'
            elif p == 'selection-color': role = 'ui_selected_text'
            elif p == 'color':
                role = 'ui_text'
                if ':disabled' in lower: role = 'ui_disabled'
                elif ':selected' in lower or ':checked' in lower: role = 'ui_selected_text'
                elif 'ribboncaption' in lower: role = 'ui_caption_text'
                elif 'filedescription' in lower: role = 'ui_muted'
                elif scope in ('viewport_command_prompt','dynamic_dimension_input','live_measurements_overlay'): role = 'ui_overlay_text'
                elif scope == 'viewport_navigation': role = 'ui_nav_text'
                elif scope == 'workspace_ribbon': role = 'ui_ribbon_text'
                elif 'qlineedit' in lower or 'qcombobox' in lower: role = 'ui_input_text'
                elif 'viewport_command' in lower or 'dynamic_command' in lower or 'dynamic_dimension' in lower: role = 'ui_overlay_text'
                elif 'qpushbutton' in lower or 'qtoolbutton' in lower: role = 'ui_button_text'
                elif re.search(r'#(?:ec9a96|ff[0-9a-f]{4}|e[0-9a-f]4[0-9a-f]{3})', value, re.I): role = 'ui_error'
            elif p.startswith('background'):
                if ':hover' in lower: role = 'ui_hover'
                elif ':selected' in lower or ':checked' in lower: role = 'ui_selected'
                elif scope in ('viewport_command_prompt','dynamic_dimension_input','live_measurements_overlay'): role = 'ui_overlay'
                elif 'ribboncaption' in lower: role = 'ui_caption_bg'
                elif 'ribbonpanel' in lower or 'workspace_ribbon' in lower: role = 'ui_ribbon_bottom'
                elif 'viewport_navigation' in lower: role = 'ui_navigation'
                elif 'viewport_command' in lower or 'dynamic_dimension' in lower or 'dynamic_command' in lower: role = 'ui_overlay'
                elif any(x in lower for x in ('qlineedit','qcombobox','qplaintextedit','qtextedit')): role = 'ui_input'
                elif 'qpushbutton' in lower: role = 'ui_button_bottom'
                elif 'qlist' in lower or 'qtable' in lower or 'qtree' in lower: role = 'ui_table'
                elif 'file_workspace' in lower: role = 'ui_panel'
                elif 'qscrollbar::handle' in lower: role = 'ui_scrollbar_handle'
                elif 'qscrollbar' in lower: role = 'ui_scrollbar'
            else:
                return m.group()
            value = re.sub(r'#[0-9a-fA-F]{6}\b|\b(?:white|black)\b', c[role], value)
            return prop + ':' + value + ';'
        return selector + '{' + re.sub(r'([\w-]+)\s*:\s*([^;{}]+);?', declaration, body) + '}'
    return re.sub(r'([^{}]+)\{([^{}]*)\}', rule, source)


def style_children(root, options):
    c = resolve(options)
    for widget in root.findChildren(QWidget):
        current = widget.styleSheet()
        if not current or widget.property('appearanceSwatch'):
            continue
        # Small button styles are drawing-color/PAT swatches, not UI surfaces.
        if isinstance(widget, QPushButton) and len(current) < 75:
            continue
        original = getattr(widget, '_appearance_qss', current)
        widget._appearance_qss = original
        scope = ''
        ancestor = widget
        while ancestor is not None:
            if ancestor.objectName() in ('viewport_command_prompt','dynamic_dimension_input',
                                         'live_measurements_overlay','viewport_navigation','workspace_ribbon'):
                scope = ancestor.objectName()
                break
            ancestor = ancestor.parentWidget()
        local = themed_qss(original, options, scope)
        if widget.objectName() == 'workspace_ribbon':
            local += ribbon_stylesheet(c)
        widget.setStyleSheet(local)


def palette_for(options):
    c = resolve(options)
    palette = QPalette()
    roles = {'Window':'ui_base', 'Base':'ui_input', 'AlternateBase':'ui_table_alt',
             'WindowText':'ui_text', 'Text':'ui_input_text', 'Button':'ui_button_bottom',
             'ButtonText':'ui_button_text', 'Highlight':'ui_selected',
             'HighlightedText':'ui_selected_text', 'ToolTipBase':'ui_tooltip',
             'ToolTipText':'ui_tooltip_text', 'Link':'ui_link', 'LinkVisited':'ui_link',
             'PlaceholderText':'ui_placeholder', 'Light':'ui_ribbon_top', 'Mid':'ui_border',
             'Dark':'ui_panel'}
    for role, key in roles.items():
        palette.setColor(getattr(QPalette.ColorRole, role), QColor(c[key]))
    for role in ('WindowText','Text','ButtonText','PlaceholderText'):
        palette.setColor(QPalette.ColorGroup.Disabled, getattr(QPalette.ColorRole,role), QColor(c['ui_disabled']))
    return palette


class _ThemeFilter(QObject):
    def eventFilter(self, widget, event):
        if event.type() == QEvent.Type.Show and isinstance(widget, QWidget) and widget.isWindow():
            owner = widget.parentWidget()
            while owner is not None and not hasattr(owner, 'appearance_options'):
                owner = owner.parentWidget()
            if owner is not None:
                options = owner.appearance_options
                if isinstance(widget, QMessageBox):
                    widget.setProperty('messageSeverity', {
                        QMessageBox.Icon.Critical:'error', QMessageBox.Icon.Warning:'warning',
                        QMessageBox.Icon.Information:'information',
                    }.get(widget.icon(), 'normal'))
                raw = getattr(widget, '_appearance_qss', widget.styleSheet())
                widget._appearance_qss = raw
                widget.setStyleSheet(themed_qss(raw, options) + stylesheet(resolve(options)))
                widget.setPalette(palette_for(options))
                style_children(widget, options)
        return False


def apply(window, options=None):
    global _ACTIVE_COLORS
    options = options or settings()
    c = resolve(options)
    _ACTIVE_COLORS = c
    window.appearance_options = dict(options)
    window.appearance_colors = c
    from .workspace_ui import STYLE, tool_icon
    window._appearance_qss = STYLE
    window.setStyleSheet(themed_qss(STYLE, options) + stylesheet(c))
    window.setPalette(palette_for(options))
    style_children(window, options)
    app=QApplication.instance()
    if not hasattr(app,'_pycad_theme_filter'):
        app._pycad_theme_filter=_ThemeFilter(app);app.installEventFilter(app._pycad_theme_filter)
    window._theme_filter=app._pycad_theme_filter
    window.canvas.model_background = QColor(options['model'])
    window.canvas.paper_background = QColor(options['paper'])
    window.canvas.grid_color = QColor(options['grid'])
    window.canvas.setBackgroundBrush(QBrush(window.canvas.model_background))
    window.canvas.viewport().update()
    from .tools import PREVIEW_COLOR
    PREVIEW_COLOR.setRgb(QColor(c['ui_preview']).rgb())
    if getattr(window, 'layer_panel', None):
        window.layer_panel.refresh()
    if getattr(window, 'model_workspace', None):
        for view in window.model_workspace.views:
            view.update()
    from PyQt6.QtWidgets import QToolButton
    for button in window.findChildren(QToolButton):
        command = button.property('command')
        if command:
            button.setIcon(tool_icon(command))
        nav_icon = button.property('navigationIcon')
        if nav_icon:
            from .navigation import navigation_icon
            button.setIcon(navigation_icon(nav_icon))
    if getattr(window, 'current_tool', None):
        window.render_command_options()
    for widget in window.findChildren(QWidget):
        if widget.isWindow():
            raw = getattr(widget, '_appearance_qss', widget.styleSheet())
            widget._appearance_qss = raw
            widget.setStyleSheet(themed_qss(raw, options) + stylesheet(c))
            widget.setPalette(palette_for(options))
            style_children(widget, options)


def save(window, options):
    if set(options) != set(DEFAULTS) or options['theme'] not in THEMES:
        raise ValueError('Invalid appearance settings')
    for key in DEFAULTS.keys() - {'theme'}:
        value = options[key]
        if (not isinstance(value, str) or
                not (key in ROLE_KEYS and value == '') and not re.fullmatch(r'#[0-9a-fA-F]{6}', value)):
            raise ValueError('Use #RRGGBB colors')
    s = appsettings.get_settings()
    for key, value in options.items():
        s.setValue('appearance/' + key, value)
    s.setValue('appearance/palette_revision', 18)
    apply(window, options)


class OptionsDialog(QDialog):
    def __init__(self, mw, drafting=False):
        super().__init__(mw)
        self.mw = mw
        self.setWindowTitle("PY.cad Options")
        self.resize(650, 590)
        root = QVBoxLayout(self)
        tabs = QTabWidget()
        root.addWidget(tabs)
        display = QWidget()
        display_layout = QVBoxLayout(display)
        self.colors = settings()
        form = QFormLayout()
        self.theme = QComboBox()
        self.theme.addItems(THEMES)
        self.theme.setCurrentText(self.colors['theme'])
        form.addRow('Theme preset', self.theme)
        self.color_category = QComboBox()
        self.color_category.addItems(['All colors', 'Drawing spaces', *dict.fromkeys(r[2] for r in ROLES)])
        form.addRow('Color group', self.color_category)
        self.color_search = QLineEdit()
        self.color_search.setPlaceholderText('Search colors, e.g. font, ribbon or command')
        form.addRow('Find a color', self.color_search)
        display_layout.addLayout(form)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(170)
        body = QWidget()
        grid = QGridLayout(body)
        self.color_buttons = {}
        self.color_rows = []
        records = [(k,label,'Drawing spaces') for k,label in SPACE_LABELS] + [(k,label,group) for k,label,group,_ in ROLES]
        for row, (key,label,group) in enumerate(records):
            text = QLabel(label)
            button = QPushButton()
            button.setProperty('appearanceSwatch', True)
            button.setObjectName('appearance_' + key)
            button.setAccessibleName(label + ' color')
            button.clicked.connect(lambda checked=False,k=key,b=button: self.choose_color(k,b))
            reset = QPushButton('Reset')
            reset.setMaximumWidth(60)
            reset.setToolTip('Use the current preset default for ' + label.lower())
            reset.clicked.connect(lambda checked=False,k=key: self.reset_color(k))
            grid.addWidget(text,row,0);grid.addWidget(button,row,1);grid.addWidget(reset,row,2)
            self.color_buttons[key] = button
            self.color_rows.append((key,label,group,(text,button,reset)))
        grid.setRowStretch(len(records),1)
        grid.setColumnStretch(0,1)
        scroll.setWidget(body)
        display_layout.addWidget(scroll,1)
        self.color_preview = QWidget()
        preview_layout = QHBoxLayout(self.color_preview)
        preview_layout.addWidget(QLabel('Font preview'))
        preview_layout.addWidget(QPushButton('Button'))
        sample = QLineEdit('Input text')
        preview_layout.addWidget(sample)
        display_layout.addWidget(self.color_preview)
        reset_row = QHBoxLayout()
        self.reset_colors_button = QPushButton('Reset all colors')
        self.reset_colors_button.setObjectName('appearance_reset_all')
        self.reset_colors_button.setToolTip('Restore the selected preset and drawing-space defaults. Apply or OK saves; Cancel discards.')
        self.reset_colors_button.clicked.connect(self.reset_colors)
        reset_row.addWidget(self.reset_colors_button)
        self.menus = QCheckBox('Classic menu bar')
        self.menus.setChecked(not mw.menuBar().isHidden())
        reset_row.addStretch();reset_row.addWidget(self.menus)
        display_layout.addLayout(reset_row)
        self.color_category.currentTextChanged.connect(self.filter_colors)
        self.color_search.textChanged.connect(self.filter_colors)
        self.theme.currentTextChanged.connect(self.refresh_colors)
        self.refresh_colors()
        tabs.addTab(display, 'Appearance')
        draft = QWidget()
        df = QFormLayout(draft)
        self.enabled = QCheckBox("Enable object snaps (F3)")
        self.enabled.setChecked(mw.canvas.snap_enabled)
        df.addRow(self.enabled)
        self.snap_checks = {}
        snap_box = QWidget()
        snap_grid = QGridLayout(snap_box)
        snap_grid.setContentsMargins(0, 0, 0, 0)
        for index, name in enumerate(SNAPS):
            cb = QCheckBox(name)
            cb.setChecked(name in mw.canvas.snap_modes)
            self.snap_checks[name] = cb
            snap_grid.addWidget(cb, index // 3, index % 3)
        df.addRow(snap_box)
        self.radius = QSpinBox()
        self.radius.setRange(2, 40)
        self.radius.setValue(mw.canvas.snap_radius_px)
        df.addRow("Pick radius (px)", self.radius)
        self.spacing = QDoubleSpinBox()
        self.spacing.setRange(0.000001, 1e9)
        self.spacing.setDecimals(6)
        self.spacing.setValue(mw.canvas.grid_spacing)
        df.addRow("Grid spacing", self.spacing)
        tabs.addTab(draft, "Drafting / OSNAP")
        graphics = QWidget()
        gf = QFormLayout(graphics)
        self.graphics_mode = QComboBox()
        from .graphics import MODES
        for key, title in MODES.items():
            self.graphics_mode.addItem(title, key)
        self.graphics_mode.setCurrentIndex(list(MODES).index(mw.graphics.mode))
        gf.addRow("Rendering mode", self.graphics_mode)
        details = QPushButton("Graphics settings and diagnostics…")
        details.clicked.connect(self.open_graphics)
        gf.addRow(details)
        info = QLabel("Uses the selected mode for 2D drafting and all 3D panes. OpenGL falls back to software if the graphics check or a viewport fails.")
        info.setWordWrap(True)
        gf.addRow(info)
        tabs.addTab(graphics, "Graphics")
        tabs.setCurrentIndex(1 if drafting else 0)
        note = QLabel(
            "Apply or OK saves colors. Reset uses the selected preset; Cancel discards unapplied edits. Drawing colors and the logo are preserved."
        )
        note.setWordWrap(True)
        root.addWidget(note)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Apply
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(
            self.apply_changes
        )
        root.addWidget(buttons)

    def filter_colors(self, *_args):
        category = self.color_category.currentText()
        query = self.color_search.text().strip().lower()
        for key,label,group,widgets in self.color_rows:
            visible = (category == 'All colors' or group == category) and query in (label + ' ' + group).lower()
            for widget in widgets:
                widget.setVisible(visible)

    def refresh_colors(self, *_args):
        self.colors['theme'] = self.theme.currentText()
        effective = resolve(self.colors)
        for key, button in self.color_buttons.items():
            value = effective[key]
            button.setText(value.upper())
            button.setToolTip('Preset default' if key in ROLE_KEYS and not self.colors[key] else 'Custom color')
            self.color_swatch(button, value)
        self.color_preview.setStyleSheet(stylesheet(effective))
        self.color_preview.setProperty('appearanceSwatch', True)
        self.filter_colors()

    def reset_color(self, key):
        self.colors[key] = DEFAULTS[key]
        self.refresh_colors()

    def reset_colors(self):
        theme = self.theme.currentText()
        self.colors = {**DEFAULTS, 'theme': theme}
        self.refresh_colors()

    def choose_color(self, key, button):
        value = QColorDialog.getColor(QColor(resolve(self.colors)[key]), self,
                                      button.accessibleName(), QColorDialog.ColorDialogOption.DontUseNativeDialog)
        if value.isValid():
            self.colors[key] = value.name()
            self.refresh_colors()

    def open_graphics(self):
        self.mw.graphics_dialog()
        self.graphics_mode.setCurrentIndex(self.graphics_mode.findData(self.mw.graphics.mode))

    @staticmethod
    def color_swatch(button, value):
        color = QColor(value)
        contrast = "#111111" if color.lightnessF() > 0.55 else "#ffffff"
        button.setStyleSheet("background:" + value + ";color:" + contrast + ";")

    def apply_changes(self):
        self.colors["theme"] = self.theme.currentText()
        save(self.mw, self.colors)
        set_menubar(self.mw, int(self.menus.isChecked()))
        c = self.mw.canvas
        c.snap_modes = {name for name, cb in self.snap_checks.items() if cb.isChecked()}
        c.snap_radius_px, c.grid_spacing = self.radius.value(), self.spacing.value()
        c.snap_enabled = self.enabled.isChecked()
        self.mw.snap_action.setChecked(c.snap_enabled)
        s = appsettings.get_settings()
        s.setValue("drafting/snap_modes", sorted(c.snap_modes))
        s.setValue("drafting/snap_radius", c.snap_radius_px)
        s.setValue("drafting/grid_spacing", c.grid_spacing)
        s.setValue("drafting/snap_enabled", c.snap_enabled)
        if self.graphics_mode.currentData() != self.mw.graphics.mode:
            self.mw.graphics.set_mode(self.graphics_mode.currentData())

    def accept(self):
        self.apply_changes()
        super().accept()


def set_menubar(mw, value):
    if value not in (0, 1):
        raise ValueError("MENUBAR accepts 0 or 1")
    # Keep the logo available while hiding the traditional menu labels.
    for action in mw.menuBar().actions():
        action.setVisible(bool(value))
    mw.menuBar().show()
    appsettings.get_settings().setValue("interface/menubar", value)


def options_dialog(mw, drafting=False):
    dialog = OptionsDialog(mw, drafting)
    try:
        dialog.exec()
    finally:
        dialog.setParent(None)
        dialog.deleteLater()


def commands(mw):
    return {
        "OPTIONS": lambda: options_dialog(mw),
        "THEME": lambda: options_dialog(mw),
        "OSNAP": lambda: options_dialog(mw, True),
    }
