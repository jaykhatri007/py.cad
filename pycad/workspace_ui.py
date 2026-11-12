"""Original PyCAD workspace controls, icons and property inspector."""

from PyQt6.QtCore import Qt, QPointF, QRectF
from PyQt6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap, QPainterPath, QPolygonF
from PyQt6.QtWidgets import (
    QWidget,
    QDockWidget,
    QFormLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QColorDialog,
)
from .document import SetAttrCommand

STYLE = """
QMainWindow, QDockWidget, QWidget { background: #202630; color: #dde5ef; font-family: 'Segoe UI'; font-size: 12px; }
QMenuBar, QToolBar, QStatusBar { background: #181e27; spacing: 5px; }
QMenuBar::item { padding: 6px 10px; }
QMenuBar::item:selected, QMenu::item:selected { background: #34475b; }
QMenu { border: 1px solid #45566c; padding: 4px; }
QMenu::item { padding: 5px 28px; }
QDockWidget::title { background: #2a3340; padding: 8px; font-weight: bold; }
QTableWidget { background:#141b24; gridline-color:#344354; selection-background-color:#245573; }
QHeaderView::section { background:#2a3748; color:#c9dfef; padding:7px; border:1px solid #344354; }
QDoubleSpinBox, QSpinBox { background:#141b24; padding:5px; border:1px solid #3a4657; }
QLineEdit, QPlainTextEdit, QListWidget, QComboBox { background: #141b24; border: 1px solid #3a4657; padding: 5px; selection-background-color: #176c99; }
QToolButton { border: 1px solid transparent; padding: 5px; border-radius: 3px; }
QToolButton:hover, QPushButton:hover { background: #344b61; border-color: #529dc3; }
QPushButton { background: #2c394a; border: 1px solid #45556a; padding: 5px 9px; border-radius: 3px; }
QPushButton:checked, QToolButton:checked { background: #145875; color: white; }
QTabWidget::pane { border: 1px solid #344354; }
QTabBar::tab { padding: 7px 18px; background: #1c2430; border-bottom: 2px solid transparent; }
QTabBar::tab:selected { background: #2c394a; border-bottom: 2px solid #5ac8ec; }
QGroupBox { border: 0; border-right: 1px solid #3c4654; margin-top: 0px; margin-bottom: 17px; }
QGroupBox::title { subcontrol-origin: margin; subcontrol-position: bottom center; color: #9baec4; padding-top: 3px; }
QLabel#brand { color: #72d5f2; font-size: 16px; font-weight: bold; padding: 4px 12px; }
QScrollBar:vertical { width: 10px; background: #18212c; }
QScrollBar::handle:vertical { background: #4a6075; min-height: 24px; }
QToolTip { color: #f5faff; background: #304359; border: 1px solid #5c7287; }
"""


def tool_icon(name):
    """Small original vector-style icons rendered locally; no external assets."""
    if name in ("3DORBIT","PAN","NAVWHEEL","ZOOMEXTENTS","ZOOMWINDOW","ZOOMREALTIME"):
        from .navigation import navigation_icon
        return navigation_icon({"3DORBIT":"orbit","PAN":"pan","NAVWHEEL":"orbit","ZOOMEXTENTS":"fit","ZOOMWINDOW":"+","ZOOMREALTIME":"+"}[name])
    from .appearance import colors
    ui = colors()
    pix = QPixmap(32, 32)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor(ui['ui_icon']), 1.7))
    if name in ('CUTCLIP', 'COPYCLIP', 'PASTECLIP'):
        if name == 'CUTCLIP':
            p.drawEllipse(QRectF(3, 20, 8, 8)); p.drawEllipse(QRectF(20, 20, 8, 8))
            p.drawLine(7, 24, 25, 4); p.drawLine(24, 24, 8, 4)
        else:
            p.drawRect(4, 4, 17, 21); p.drawRect(12, 10, 17, 20)
            if name == 'PASTECLIP':
                p.setBrush(QColor(ui['ui_icon_secondary'])); p.drawRect(8, 2, 13, 5)
    elif name in ('FIND', 'COMPARE'):
        p.drawEllipse(QRectF(4, 3, 18, 18)); p.drawLine(20, 20, 29, 29)
        if name == 'COMPARE':
            p.drawLine(9, 12, 17, 12); p.drawLine(13, 8, 13, 16)
    elif name == 'CLOUD':
        path = QPainterPath(); path.moveTo(6, 25)
        path.cubicTo(-2, 22, 1, 12, 9, 13); path.cubicTo(6, 1, 25, 1, 24, 13)
        path.cubicTo(33, 10, 33, 25, 25, 25); path.closeSubpath(); p.drawPath(path)
        p.drawLine(16, 28, 16, 13); p.drawLine(11, 18, 16, 13); p.drawLine(21, 18, 16, 13)
    elif name == 'SHAREDVIEWS':
        p.drawRect(2, 4, 28, 21); p.drawLine(12, 29, 20, 29); p.drawLine(16, 25, 16, 29)
        p.drawEllipse(QRectF(10, 10, 12, 9)); p.drawEllipse(QRectF(14, 12, 4, 4))
    elif name in ('OPTIONS', 'OSNAP', 'MENUBAR'):
        for y, x in ((7, 11), (16, 23), (25, 15)):
            p.drawLine(3, y, 29, y); p.drawRect(x - 2, y - 3, 4, 6)
    elif name.startswith("LAY") or name == "LAYER":
        for y in (3, 10, 17):
            p.drawPolygon(QPolygonF([
                QPointF(4, y + 5), QPointF(16, y), QPointF(28, y + 5), QPointF(16, y + 10)]))
        if name != "LAYER":
            p.setPen(QPen(QColor(ui['ui_icon_secondary']),2))
            p.drawLine(21,22,29,22)
            if name not in ("LAYOFF","LAYISO"):p.drawLine(25,18,25,26)
    elif name in ("TABLE","TABLESTYLE","DATATABLE","DATAEXTRACTION"):
        p.setPen(QPen(QColor(ui['ui_icon_secondary']),1.6)); p.drawRect(3,5,26,22)
        p.drawLine(3,12,29,12); p.drawLine(3,20,29,20)
        p.drawLine(12,5,12,27); p.drawLine(22,5,22,27)
    elif name in ("TEXT","MTEXT","STYLE","TEXTEDIT","LEADER","MLEADER","MLEADERADD","MLEADERREMOVE","MLEADERSTYLE","MLEADEREDIT"):
        p.setPen(QPen(QColor(ui['ui_icon_text']),2))
        if name in ("TEXT","MTEXT","STYLE","TEXTEDIT"):
            p.drawLine(8,6,26,6); p.drawLine(17,6,17,26); p.drawLine(12,26,22,26)
            if name == "MTEXT":p.drawLine(3,14,9,14); p.drawLine(3,20,9,20)
        else:
            p.drawLine(4,26,15,13); p.drawLine(15,13,29,13); p.drawLine(4,26,5,19); p.drawLine(4,26,11,25)
            p.drawLine(20,4,20,10); p.drawLine(17,4,24,4)
            if name in ('MLEADERADD','MLEADERREMOVE','MLEADERSTYLE','MLEADEREDIT'):
                p.setPen(QColor(ui['ui_icon_secondary']))
                font = p.font(); font.setPixelSize(12); p.setFont(font)
                label = {'MLEADERADD':'+','MLEADERREMOVE':'−','MLEADERSTYLE':'S','MLEADEREDIT':'E'}[name]
                p.drawText(QRectF(21,18,10,13), Qt.AlignmentFlag.AlignCenter, label)
    elif name in ("CENTERMARK","CENTERLINE","MEASURERADIUS","MEASUREANGLE","MEASUREGEOM","QUICKMEASURE"):
        p.setPen(QPen(QColor(ui['ui_icon_secondary']),1.5))
        if name == "MEASUREANGLE":
            p.drawLine(4,27,28,27); p.drawLine(4,27,22,5); p.drawArc(QRectF(-6,17,20,20),0,50*16)
        else:
            p.drawEllipse(QRectF(6,6,20,20)); p.drawLine(2,16,30,16); p.drawLine(16,2,16,30)
    elif name == "STRETCH":
        p.drawRect(3,9,17,19); p.setPen(QPen(QColor(ui['ui_icon_secondary']),1.5,Qt.PenStyle.DashLine)); p.drawRect(12,3,17,19)
        p.setPen(QPen(QColor(ui['ui_icon_text']),2)); p.drawLine(12,16,28,6); p.drawLine(21,6,28,6)
    elif name == "ERASE":
        p.setBrush(QColor(ui['ui_icon_fill'])); p.drawPolygon(QPolygonF([QPointF(4,21),QPointF(18,5),QPointF(28,14),QPointF(14,29)]))
    elif name in ("COLOR","LINETYPE","LWEIGHT","TRANSPARENCY","PROPERTIES"):
        for y,color,width in ((7,ui['ui_icon'],1),(16,ui['ui_icon_secondary'],2),(25,ui['ui_icon_tertiary'],3)):
            p.setPen(QPen(QColor(color),width)); p.drawLine(4,y,28,y)
    elif name.startswith(("EXPORT","PDF","DGN","IMAGE","ATTACH","DXF")) or name in ("PLOT","BATCHPLOT","PLOTPREVIEW","PAGESETUP","ETRANSMIT","EMAIL","XREF","WBLOCK","NEWLAYOUT"):
        p.setPen(QPen(QColor(ui['ui_icon_text']),1.5)); p.drawRect(6,3,20,26)
        p.setPen(QPen(QColor(ui['ui_icon_secondary']),2)); p.drawLine(11,13,21,13); p.drawLine(11,19,21,19)
        p.drawLine(16,7,16,24)
    elif name in ("2DWIREFRAME","SHADED","XRAY","CONCEPTUAL","REALISTIC","TOP","FRONT","LEFT","RIGHT","BOTTOM","BACK","ISOMETRIC","VIEWBASE","VIEWPROJ","VIEWSECTION","VIEWDETAIL"):
        if name in ("SHADED","XRAY","REALISTIC"):p.setBrush(QColor(ui['ui_icon_fill']))
        p.drawPolygon(QPolygonF([QPointF(4,9),QPointF(17,3),QPointF(28,10),QPointF(28,25),QPointF(16,30),QPointF(4,23)]))
        p.drawLine(4,9,16,16); p.drawLine(16,16,28,10); p.drawLine(16,16,16,30)
    elif name == "DIMORDINATE":
        p.setPen(QPen(QColor(ui['ui_icon_secondary']), 1.6))
        p.drawLine(5, 27, 29, 27); p.drawLine(5, 27, 5, 4)
        p.drawLine(17, 22, 17, 10); p.drawLine(17, 10, 28, 10)
        p.drawLine(14, 22, 20, 22); p.drawEllipse(QRectF(14, 19, 6, 6))
        p.drawLine(25, 7, 25, 13); p.drawLine(22, 7, 28, 7)
    elif name.startswith(("GC","DC","CONSTRAINT")) or name == "DELCONSTRAINT":
        p.setPen(QPen(QColor(ui['ui_icon_tertiary']), 1.8))
        if name == "GCPARALLEL":
            p.drawLine(5, 24, 15, 5); p.drawLine(17, 27, 27, 8)
        elif name == "GCPERPENDICULAR":
            p.drawLine(4, 25, 29, 25); p.drawLine(15, 4, 15, 25)
            p.drawRect(15, 19, 6, 6)
        elif name == "GCCOINCIDENT":
            p.drawLine(4, 26, 16, 15); p.drawLine(16, 15, 28, 5)
            p.setBrush(QColor(ui['ui_icon_tertiary'])); p.drawEllipse(QRectF(12, 11, 8, 8))
        elif name == "GCCOLLINEAR":
            p.drawLine(3, 25, 12, 18); p.drawLine(20, 12, 29, 5)
            p.setPen(QPen(QColor(ui['ui_icon_text']), 1, Qt.PenStyle.DotLine)); p.drawLine(3, 25, 29, 5)
        elif name == "GCCONCENTRIC":
            p.drawEllipse(QRectF(4, 4, 24, 24)); p.drawEllipse(QRectF(11, 11, 10, 10))
        elif name == 'GCTANGENT':
            p.drawEllipse(QRectF(7, 4, 18, 18)); p.drawLine(2, 22, 30, 22)
        elif name in ("DCRADIUS", "DCDIAMETER"):
            p.drawEllipse(QRectF(4, 4, 24, 24)); p.setPen(QPen(QColor(ui['ui_icon_secondary']), 1.8))
            p.drawLine(5 if name == "DCDIAMETER" else 16, 16, 27, 16)
            p.drawLine(23, 12, 27, 16); p.drawLine(23, 20, 27, 16)
        elif name == "DCANGULAR":
            p.drawLine(4, 27, 29, 27); p.drawLine(4, 27, 24, 4)
            p.setPen(QPen(QColor(ui['ui_icon_secondary']), 1.8)); p.drawArc(QRectF(-11, 12, 30, 30), 0, 49 * 16)
        elif name in ("DCLINEAR", "DCALIGNED"):
            if name == "DCALIGNED":
                p.translate(16, 16); p.rotate(-25); p.translate(-16, -16)
            p.drawLine(5, 7, 5, 26); p.drawLine(27, 7, 27, 26)
            p.setPen(QPen(QColor(ui['ui_icon_secondary']), 1.8)); p.drawLine(5, 16, 27, 16)
            p.drawLine(5, 16, 10, 12); p.drawLine(27, 16, 22, 20)
        elif name == "CONSTRAINTBAR":
            p.drawEllipse(QRectF(3, 9, 26, 14)); p.drawEllipse(QRectF(12, 12, 8, 8))
        elif name == "DELCONSTRAINT":
            p.drawEllipse(QRectF(4, 10, 15, 10)); p.drawEllipse(QRectF(13, 10, 15, 10))
            p.setPen(QPen(QColor(ui['ui_error']), 2.5)); p.drawLine(8, 27, 24, 5)
        elif name == "CONSTRAINTSETTINGS":
            for y, x in ((7, 11), (16, 23), (25, 15)):
                p.drawLine(3, y, 29, y); p.drawRect(x - 2, y - 3, 4, 6)
        else:
            p.drawRect(8, 14, 17, 14); p.drawArc(QRectF(11, 3, 11, 20), 0, 180 * 16)
    elif name in ("TOOLPALETTES","TOOLCOVERAGE","COMMANDLINE","ALIASEDIT","CUI","CHECKSTANDARDS","CONFIGURESTANDARDS","STANDARDS","APPLOAD","ACTRECORD","ACTMACRO","VBAIDE","SHEETSET","SPELL","HYPERLINK","BEDIT","ATTDEF","MARKUPIMPORT"):
        p.drawRect(4,4,24,24)
        p.setPen(QPen(QColor(ui['ui_icon_secondary']),1.7))
        for y in (10,16,22):p.drawLine(13,y,24,y); p.drawRect(7,y-1,2,2)
    elif name == "EXTRUDE":
        p.drawRect(5, 12, 16, 15)
        p.drawLine(5, 12, 12, 5)
        p.drawLine(21, 12, 28, 5)
        p.drawLine(12, 5, 28, 5)
        p.drawLine(28, 5, 28, 20)
        p.drawLine(28, 20, 21, 27)
    elif name == "VPORTS":
        p.drawRect(3, 5, 26, 22)
        p.drawLine(16, 5, 16, 27)
        p.drawLine(3, 16, 29, 16)
    elif name == "POINT":
        p.drawLine(5, 16, 27, 16)
        p.drawLine(16, 5, 16, 27)
        p.drawEllipse(QRectF(13, 13, 6, 6))
    elif name == "ELLIPSE":
        p.drawEllipse(QRectF(3, 8, 26, 16))
        p.drawLine(3, 16, 29, 16)
    elif name in ("RAY", "XLINE"):
        p.drawLine(4, 26, 27, 4)
        p.drawLine(20, 4, 27, 4)
        p.drawLine(27, 4, 27, 11)
        if name == "XLINE":
            p.drawLine(4, 19, 4, 26)
            p.drawLine(4, 26, 11, 26)
        else:
            p.drawEllipse(QRectF(2, 24, 4, 4))
    elif name in ("CIRCLE", "ARC", "ROTATE", "ARRAYPOLAR"):
        if name == "ARC":
            p.drawArc(QRectF(5, 5, 22, 22), 0, 240 * 16)
        else:
            p.drawEllipse(QRectF(5, 5, 22, 22))
        p.drawLine(16, 13, 16, 19)
        p.drawLine(13, 16, 19, 16)
    elif name in ("RECTANGLE", "BLOCK", "INSERT", "ADDVIEWPORT", "XCLIP"):
        p.drawRect(QRectF(4, 7, 24, 18))
        p.drawLine(4, 7, 10, 13)
    elif name in (
        "LINE",
        "PLINE",
        "SPLINE",
        "TRIM",
        "EXTEND",
        "OFFSET",
        "FILLET",
        "CHAMFER",
    ):
        path = QPainterPath(QPointF(5, 26))
        path.lineTo(13, 7)
        if name in ("SPLINE", "FILLET"):
            path.cubicTo(25, 0, 18, 28, 28, 9)
        else:
            path.lineTo(27, 16)
        p.drawPath(path)
        p.setBrush(QColor(ui['ui_icon_secondary']))
        p.drawRect(3, 24, 4, 4)
        p.drawRect(25, 14, 4, 4)
    elif name in ("COPY", "SCALE", "ARRAYRECT", "MIRROR", "MOVE"):
        p.drawRect(4, 11, 15, 16)
        p.drawRect(13, 4, 15, 16)
    elif name == "HATCH":
        p.drawRect(4, 4, 24, 24)
        for x in range(4, 24, 5):
            p.drawLine(x, 27, 27, x)
    elif name in ("DIST", "UNITS", "DYNMODE"):
        p.drawLine(5, 16, 27, 16)
        p.drawLine(5, 11, 5, 21)
        p.drawLine(27, 11, 27, 21)
        p.drawLine(9, 13, 5, 16)
        p.drawLine(9, 19, 5, 16)
        p.drawLine(23, 13, 27, 16)
        p.drawLine(23, 19, 27, 16)
    elif name == "AREA":
        path = QPainterPath(QPointF(5, 24))
        path.lineTo(10, 7)
        path.lineTo(26, 10)
        path.lineTo(23, 25)
        path.closeSubpath()
        p.drawPath(path)
        p.drawLine(8, 20, 23, 12)
    elif name.startswith("DIM"):
        p.drawLine(5, 8, 5, 25)
        p.drawLine(27, 8, 27, 25)
        p.drawLine(5, 16, 27, 16)
        p.drawLine(5, 16, 10, 12)
        p.drawLine(27, 16, 22, 20)
    elif name == "SELECT":
        path = QPainterPath(QPointF(8, 4))
        path.lineTo(8, 27)
        path.lineTo(15, 19)
        path.lineTo(24, 19)
        path.closeSubpath()
        p.drawPath(path)
    else:
        font = p.font()
        font.setPixelSize(21)
        font.setBold(True)
        p.setFont(font)
        p.drawText(
            pix.rect(),
            Qt.AlignmentFlag.AlignCenter,
            "T" if name == "TEXT" else name[:1],
        )
    p.end()
    return QIcon(pix)


def make_ribbon(mw):
    from .ribbon import Ribbon
    return Ribbon(mw)


class PropertiesPanel(QDockWidget):
    def __init__(self, mw):
        super().__init__("Properties", mw)
        self.setObjectName("properties_dock")
        self.mw = mw
        box = QWidget()
        form = self.form = QFormLayout(box)
        form.setContentsMargins(7, 7, 7, 7)
        form.setSpacing(4)
        self.summary = QLabel("No selection")
        self.summary.setWordWrap(True)
        self.layer = QComboBox()
        self.line = QComboBox()
        from .linetypes import populate_combo
        populate_combo(self.line, bylayer=True)
        self.color = QPushButton("By layer")
        self.transparency_button = QPushButton("0%")
        self.hyperlink_button = QPushButton("Add / edit…")
        self.transparency_button.clicked.connect(lambda: self.mw.run_ribbon_command("TRANSPARENCY"))
        self.hyperlink_button.clicked.connect(lambda: self.mw.run_ribbon_command("HYPERLINK"))
        self.info = QLabel()
        self.info.setTextFormat(Qt.TextFormat.PlainText)
        self.info.setWordWrap(True)
        self.mleader_text = QPushButton("Edit text…")
        self.mleader_text.clicked.connect(lambda: self.mw.run_ribbon_command('MLEADEREDIT'))
        self.text_edit = QPushButton("Edit / format…")
        self.text_edit.clicked.connect(lambda: self.mw.run_ribbon_command('TEXTEDIT'))
        form.addRow(self.summary)
        form.addRow("Layer", self.layer)
        form.addRow("Linetype", self.line)
        form.addRow("Color", self.color)
        form.addRow("Transparency", self.transparency_button)
        form.addRow("Hyperlink", self.hyperlink_button)
        form.addRow("Multileader", self.mleader_text)
        form.addRow("Text", self.text_edit)
        self.door_edit = QPushButton("Edit door parameters…")
        from .feature_helpers import safe_action
        from .office_ui import door
        self.door_edit.clicked.connect(safe_action(self,lambda:door(self.mw,edit=True)))
        self.door_edit.hide()
        form.addRow(self.door_edit)
        from .object_properties import ObjectEditor
        self.object_editor = ObjectEditor(mw)
        form.addRow(self.object_editor)
        from .shared_properties import SharedProperties
        self.shared_editor=SharedProperties(mw)
        form.addRow(self.shared_editor)
        form.addRow(self.info)
        self.layer.activated.connect(
            lambda: self.apply("layer", self.layer.currentText())
        )
        self.line.activated.connect(
            lambda: self.apply("linetype", self.line.currentText())
        )
        self.color.clicked.connect(self.choose_color)
        from PyQt6.QtWidgets import QScrollArea
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(box)
        self.setWidget(scroll)
        self.setMinimumWidth(235)

    def refresh(self):
        selected = [
            e
            for e in self.mw.canvas.selected_entities
            if self.mw.document.contains_entity(e) and self.mw.document.is_visible(e)
        ]
        from .office_tools import door_params
        has_door=len(selected)==1 and bool(door_params(self.mw.document,selected[0]))
        self.door_edit.setVisible(has_door)
        self.door_edit.setEnabled(has_door and self.mw.document.is_editable(selected[0]))
        self.object_editor.refresh(selected[0] if len(selected) == 1 else None)
        self.shared_editor.refresh(selected)
        self.layer.blockSignals(True)
        self.mleader_text.setEnabled(len(selected) == 1 and selected[0].kind == 'MLEADER')
        self.text_edit.setEnabled(len(selected) == 1 and selected[0].kind == 'TEXT')
        for button, kind in ((self.mleader_text, 'MLEADER'), (self.text_edit, 'TEXT')):
            visible = len(selected) == 1 and selected[0].kind == kind
            button.setVisible(visible)
            self.form.labelForField(button).setVisible(visible)
        self.line.blockSignals(True)
        from .linetypes import names
        builtin=set(names(True))
        for i in range(self.line.count()-1,-1,-1):
            if self.line.itemText(i) not in builtin:self.line.removeItem(i)
        self.line.addItems(sorted(self.mw.document.extensions.get("office_linetypes",{})))

        from .coordination import MIXED
        if self.line.findText(MIXED)>=0:self.line.removeItem(self.line.findText(MIXED))
        self.layer.clear()
        self.layer.addItems(self.mw.document.layers.names())
        for widget in (self.layer, self.line, self.color, self.transparency_button, self.hyperlink_button):
            widget.setEnabled(bool(selected))
        if selected:
            e = selected[0]
            kinds=sorted({q.kind for q in selected})
            self.summary.setText(f"{len(selected)} selected · {', '.join(kinds)}")
            self.layer.setCurrentText(e.layer)
            self.line.setCurrentText(e.linetype)
            self.color.setText(e.color)
            self.transparency_button.setText(f"{e.transparency:g}%")
            self.hyperlink_button.setText("Edit / open…" if e.hyperlink else "Add / edit…")
            x0, y0, x1, y1 = e.bbox()
            from .units import format_length
            fmt = lambda v: format_length(v, self.mw.document.units, self.mw.document.unit_settings)
            detail = f"Bounds\nX {fmt(x0)} → {fmt(x1)}\nY {fmt(y0)} → {fmt(y1)}"
            if hasattr(e, "radius"):
                detail += f"\nRadius {fmt(e.radius)}"
            if hasattr(e, "length"):
                detail += f"\nLength {fmt(e.length())}"
            if hasattr(e, "measurement"):
                from .dimstyles import dimension_label, style_for
                detail += "\nDimension " + dimension_label(e, style_for(self.mw.document, e))
            if hasattr(e, "association_status"):
                detail += "\n" + e.association_status(self.mw.document)
            if e.kind == 'INSERT':
                detail += f"\nBlock: {e.block_name}\nDouble-click to edit definition"
            if e.kind == 'ORDINATE_DIMENSION':
                detail += f"\nDatum {fmt(e.p1.x)}, {fmt(e.p1.y)} · {e.dim_style[-1].upper()} coordinate"
            if e.kind == 'MLEADER':
                detail += f"\nBranches: {len(e.leaders)} · Style: {e.style_name}\n" + e.text[:300]
            if e.kind == 'TEXT':
                detail += f"\nText style: {e.style_name} · Height: {fmt(e.height)}\n" + e.text[:300]
            if len(selected)>1:
                from .coordination import MIXED
                def shared(attr):return getattr(e,attr) if all(getattr(q,attr)==getattr(e,attr) for q in selected) else MIXED
                for combo,attr in ((self.layer,'layer'),(self.line,'linetype')):
                    value=shared(attr)
                    if combo.findText(MIXED)>=0:combo.removeItem(combo.findText(MIXED))
                    if value==MIXED:combo.insertItem(0,MIXED)
                    combo.setCurrentText(value)
                self.color.setText(shared('color'));value=shared('transparency');self.transparency_button.setText(value if value==MIXED else f'{value:g}%');self.hyperlink_button.setText('Mixed links' if shared('hyperlink')==MIXED else 'Add / edit…')
                bounds=[q.bbox() for q in selected];detail=f"Combined bounds\nX {fmt(min(b[0] for b in bounds))} → {fmt(max(b[2] for b in bounds))}\nY {fmt(min(b[1] for b in bounds))} → {fmt(max(b[3] for b in bounds))}"
            self.info.setText(detail + f"\nUnits: {self.mw.document.units}")
        else:
            self.summary.setText("No selection")
            self.info.setText("Select geometry to inspect or change its properties.")
        self.layer.blockSignals(False)
        self.line.blockSignals(False)

    def apply(self, attr, value):
        doc = self.mw.document
        items = [
            e for e in self.mw.canvas.selected_entities if e in doc.editable_entities()
        ]
        if not items:
            return
        from .coordination import MIXED,properties_plan
        from .editing import apply
        if value==MIXED:return
        ids=[e.id for e in items];apply(doc,properties_plan(doc,items,{attr:value}));self.mw.canvas.selected_entities=[doc.find_by_id(key) for key in ids]
        self.mw.refresh_document_ui()

    def choose_color(self):
        from PyQt6.QtWidgets import QMessageBox

        reply = QMessageBox.question(
            self,
            "Entity color",
            "Use the layer color?",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No
            | QMessageBox.StandardButton.Cancel,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.apply("color", "BYLAYER")
        elif reply == QMessageBox.StandardButton.No:
            color = QColorDialog.getColor(parent=self)
            if color.isValid():
                self.apply("color", color.name())
