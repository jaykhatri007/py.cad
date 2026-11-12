"""Compact, grouped ribbon inspired by the supplied drafting workspace reference."""

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import (
    QTabWidget,
    QBoxLayout,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QGridLayout,
    QToolButton,
    QLabel,
    QScrollArea,
    QMenu,
)
from . import appsettings
from .ribbon_catalog import PANELS, TABS


class Ribbon(QTabWidget):
    def __init__(self, mw):
        super().__init__(mw)
        self.mw = mw
        self.setObjectName("workspace_ribbon")
        self.setDocumentMode(True)
        self.setStyleSheet("""
            QTabWidget#workspace_ribbon::pane { border:0; border-bottom:1px solid #475160; background:#29313c; }
            QTabWidget#workspace_ribbon QTabBar::tab { padding:3px 11px; font-size:11px; }
            QTabWidget#workspace_ribbon QToolButton { padding:1px; border-radius:2px; font-size:10px; }
            QTabWidget#workspace_ribbon QToolButton:disabled { color:#657383; }
            QWidget[ribbonPanel="true"] { background:#29313c; border-right:1px solid #414c5b; }
            QLabel[ribbonCaption="true"] { background:#242c36; color:#b9c5d3; font-size:10px; }
            QTabWidget#workspace_ribbon QScrollBar:horizontal { height:6px; background:#202630; }
            QTabWidget#workspace_ribbon QScrollBar::handle:horizontal { background:#647588; min-width:20px; }
            QTabWidget#workspace_ribbon QScrollBar::add-line:horizontal,
            QTabWidget#workspace_ribbon QScrollBar::sub-line:horizontal { width:0; }
        """)
        self.compact_button = QToolButton(self)
        self.compact_button.setText("Compact")
        self.compact_button.setCheckable(True)
        self.compact_button.setObjectName("compact_ribbon_toggle")
        self.compact_button.setToolTip(
            "Toggle single-row icon ribbon / grouped reference ribbon"
        )
        self.compact_button.setAccessibleName("Compact ribbon")
        self.setCornerWidget(self.compact_button)
        self.compact = appsettings.get_settings().value(
            "ribbon/compact", False, type=bool
        )
        self.compact_button.setChecked(self.compact)
        self.compact_button.toggled.connect(self.set_compact)
        self.rebuild()

    def set_compact(self, compact):
        self.compact = bool(compact)
        self.compact_button.blockSignals(True)
        self.compact_button.setChecked(self.compact)
        self.compact_button.blockSignals(False)
        appsettings.get_settings().setValue("ribbon/compact", self.compact)
        self.rebuild()

    def button(self, item, primary=False):
        from .workspace_ui import tool_icon

        button = QToolButton()
        button.setText(item.label)
        button.setObjectName("ribbon_" + item.command.lower())
        button.setProperty("command", item.command)
        button.setProperty("supportStatus", item.status)
        button.setAccessibleName(
            item.label + " (" + item.command + ") — " + item.status
        )
        button.setIcon(tool_icon(item.command))
        button.setToolTip(self.tooltip(item))
        button.setAttribute(Qt.WidgetAttribute.WA_AlwaysShowToolTips)
        button.setEnabled(item.status != "planned")
        if self.compact:
            button.setIconSize(QSize(22, 22))
            button.setFixedSize(30, 30)
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        elif primary:
            button.setIconSize(QSize(29, 29))
            button.setFixedSize(57, 64)
            # Long labels remain in the tooltip; keep the main action readable.
            short = {
                "LAYER": "Layer\nProperties",
                "DIMALIGNED": "Dimension",
                "MEASUREGEOM": "Measure",
                "BLOCK": "Create\nBlock",
                "2DWIREFRAME": "2D\nWireframe",
                "PROPERTIES": "Properties",
                "CHECKSTANDARDS": "Check",
                "CUI": "Customize",
                "APPLOAD": "Load\nApplication",
                "EXPORTPDF": "PDF",
                "EMAIL": "Email",
                "ATTACHDWG": "Attach\nDWG",
                "DATAEXTRACTION": "Extract\nData",
                "VIEWBASE": "Base\nView",
                "TEXT": "Text",
                "MTEXT": "Multiline\nText",
                "CENTERLINE": "Centerline",
                "MLEADER": "Multi\nleader",
                "PDFIMPORT": "PDF\nImport",
                "CONSTRAINTBAR": "Labels",
                "BATCHPLOT": "Batch\nPlot",
            }
            button.setText(
                short.get(
                    item.command,
                    item.label
                    if len(item.label) < 12
                    else item.label.replace(" ", "\n", 1),
                )
            )
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        else:
            button.setIconSize(QSize(19, 19))
            button.setFixedSize(25, 21)
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        button.clicked.connect(
            lambda checked=False, c=item.command: self.mw.run_ribbon_command(c)
        )
        return button

    @staticmethod
    def tooltip(item):
        state = (
            "Not implemented"
            if item.status == "planned"
            else "Limited support"
            if item.status == "limited"
            else "Available"
        )
        return (
            f"{item.label} — {item.command}\n{state}"
            + ("\n" + item.detail if item.detail else "")
            + (
                "\nType the command in the viewport; Enter / Space starts it."
                if item.status != "planned"
                else "\nManage → Tool coverage shows the full implementation status."
            )
        )

    def rebuild(self):
        self.mw.home_drafting_controls.setParent(self)
        self.mw.home_drafting_controls.layout().setDirection(
            QBoxLayout.Direction.LeftToRight if self.compact else QBoxLayout.Direction.TopToBottom
        )
        current = max(0, self.currentIndex())
        while self.count():
            page = self.widget(0)
            self.removeTab(0)
            page.setParent(None)
            page.deleteLater()
        self.setFixedHeight(66 if self.compact else 112)
        for tab in TABS:
            contents = QWidget()
            row = QHBoxLayout(contents)
            row.setContentsMargins(3, 1, 3, 1)
            row.setSpacing(0)
            for title, panel, source_row, items in PANELS:
                if title != tab:
                    continue
                box = QWidget()
                box.setProperty("ribbonPanel", True)
                box.setObjectName(
                    "panel_" + tab.lower() + "_" + panel.lower().replace(" ", "_")
                )
                box.setAccessibleName(tab + " / " + panel)
                box.setProperty("sourceRow", source_row)
                outer = QVBoxLayout(box)
                outer.setContentsMargins(4, 0, 4, 0)
                outer.setSpacing(0)
                grid = QGridLayout()
                grid.setSpacing(1)
                grid.setContentsMargins(0, 0, 2, 0)
                visible = items if self.compact else items[:7]
                for i, item in enumerate(visible):
                    button = self.button(item, primary=i == 0)
                    if self.compact:
                        grid.addWidget(button, 0, i)
                    elif i == 0:
                        grid.addWidget(button, 0, 0, 3, 1)
                    else:
                        grid.addWidget(button, (i - 1) % 3, 1 + (i - 1) // 3)
                if not self.compact and len(items) > 7:
                    more = QToolButton()
                    more.setText("▾")
                    more.setFixedSize(15, 63)
                    more.setAccessibleName(panel + " additional tools")
                    more.setToolTip("More " + panel + " tools")
                    menu = QMenu(more)
                    menu.setToolTipsVisible(True)
                    from .workspace_ui import tool_icon

                    for item in items[7:]:
                        action = menu.addAction(tool_icon(item.command), item.label)
                        action.setData(item.command)
                        action.setToolTip(self.tooltip(item))
                        action.setEnabled(item.status != "planned")
                        action.triggered.connect(
                            lambda checked=False, c=item.command: (
                                self.mw.run_ribbon_command(c)
                            )
                        )
                    more.setMenu(menu)
                    more.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
                    grid.addWidget(more, 0, 3, 3, 1)
                outer.addLayout(grid)
                if not self.compact:
                    label = QLabel(panel)
                    label.setProperty("ribbonCaption", True)
                    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    label.setFixedHeight(15)
                    outer.addWidget(label)
                row.addWidget(box)
            row.addStretch()
            if tab == "Home":
                row.addWidget(self.mw.home_drafting_controls)
            scroll = QScrollArea()
            scroll.setWidget(contents)
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QScrollArea.Shape.NoFrame)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.addTab(scroll, tab)
        self.setCurrentIndex(min(current, self.count() - 1))
