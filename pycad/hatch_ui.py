"""Compact hatch creation/editor with a real shared-engine preview."""
import copy
import json
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import QPainter, QPen, QColor
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QComboBox, QDoubleSpinBox, QCheckBox, QPushButton, QLabel, QWidget,
    QDialogButtonBox, QFileDialog, QColorDialog, QMessageBox, QLineEdit)
from .geometry import HatchEntity, Point, PolylineEntity, CircleEntity
from .hatching import pattern_names, read_pat, validate_options

OPTIONS = ('pattern','angle','spacing','pattern_scale','origin','double',
           'island_style','pattern_definition','background_color','gradient_color',
           'color','transparency')


def defaults():
    from .appsettings import get_settings
    try:
        data=json.loads(get_settings().value('hatch/options','{}'))
        if 'origin' in data:data['origin']=Point(*data['origin'])
        validate_options(data)
        return {k:v for k,v in data.items() if k in OPTIONS}
    except (ValueError,TypeError,KeyError):return {}


def remember(values):
    from .appsettings import get_settings
    data=copy.deepcopy(values);data['origin']=data['origin'].as_tuple()
    get_settings().setValue('hatch/options',json.dumps(data))


class Preview(QWidget):
    def __init__(self,dialog):
        super().__init__();self.dialog=dialog;self.setMinimumSize(220,180)
        self.zoom=3

    def world_to_screen(self,x,y):return QPointF(12+x*self.zoom,self.height()-12-y*self.zoom)
    def viewport(self):return self

    def paintEvent(self,event):
        p=QPainter(self);p.fillRect(self.rect(),QColor('#252b32'))
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        try:
            values=self.dialog.values();color=values['color']
            p.setPen(QPen(QColor('#eeeeee' if color=='BYLAYER' else color),1))
            p.setOpacity(1-values['transparency']/100)
            width=(self.width()-24)/self.zoom;height=(self.height()-24)/self.zoom
            boundary=[Point(0,0),Point(width,0),Point(width,height),Point(0,height)]
            holes=[[Point(width*.3,height*.3),Point(width*.7,height*.3),Point(width*.7,height*.7),Point(width*.3,height*.7)]]
            hatch=HatchEntity(boundary,holes=holes,**values)
            from .hatching import paint
            paint(self,p,hatch)
        except (ValueError,TypeError):pass
        finally:p.end()


class HatchDialog(QDialog):
    def __init__(self,parent=None,hatch=None):
        super().__init__(parent);self.setWindowTitle('Hatch and fill');self.resize(590,540)
        from .appsettings import get_settings
        try:
            self.custom=json.loads(get_settings().value('hatch/custom_patterns','{}'))
            if not isinstance(self.custom,dict) or len(self.custom)>512:raise ValueError('Invalid custom library')
            for name,definition in self.custom.items():validate_options({'pattern':name,'pattern_definition':definition})
        except (ValueError,TypeError):self.custom={}
        initial={k:copy.deepcopy(getattr(hatch,k)) for k in OPTIONS} if hatch else defaults()
        if not initial:initial={'pattern':'ANSI31','angle':0}
        if initial.get('pattern_definition'):self.custom[initial['pattern']]=initial['pattern_definition']
        layout=QVBoxLayout(self);columns=QHBoxLayout();layout.addLayout(columns)
        form=QFormLayout();columns.addLayout(form,3)
        self.search=QLineEdit();self.search.setPlaceholderText('Search patterns…');form.addRow('Find',self.search)
        self.pattern=QComboBox();self.pattern.addItems(pattern_names())
        for name in self.custom:
            if self.pattern.findText(name)<0:self.pattern.addItem(name)
        if initial.get('pattern') and self.pattern.findText(initial['pattern'])<0:self.pattern.addItem(initial['pattern'])
        self.pattern.setCurrentText(initial.get('pattern','LINES'));form.addRow('Pattern',self.pattern)
        self.controls={}
        for key,label,value,lo,hi in (
            ('pattern_scale','Scale',1,0.000001,1e9),('angle','Angle °',45,-36000,36000),
            ('spacing','User line spacing',5,0.000001,1e9),('origin_x','Origin X',0,-1e12,1e12),
            ('origin_y','Origin Y',0,-1e12,1e12),('transparency','Transparency %',0,0,90)):
            control=QDoubleSpinBox();control.setDecimals(6);control.setRange(lo,hi)
            origin=initial.get('origin',Point(0,0))
            control.setValue(getattr(origin,key[-1]) if key.startswith('origin_') else initial.get(key,value))
            self.controls[key]=control;form.addRow(label,control);control.valueChanged.connect(self.refresh)
        self.double=QCheckBox('Add perpendicular pattern');self.double.setChecked(initial.get('double',False));form.addRow(self.double)
        self.islands=QComboBox();self.islands.addItems(['normal','outer','ignore']);self.islands.setCurrentText(initial.get('island_style','normal'));form.addRow('Islands',self.islands)
        self.color=QLineEdit(initial.get('color','BYLAYER'));self.background=QLineEdit(initial.get('background_color') or '')
        self.second=QLineEdit(initial.get('gradient_color','#0088ff'))
        for label,control in [('Color',self.color),('Background',self.background),('Gradient color 2',self.second)]:
            row=QHBoxLayout();row.addWidget(control);button=QPushButton('…');button.setMaximumWidth(28)
            button.clicked.connect(lambda checked=False,c=control:self.choose_color(c));row.addWidget(button);form.addRow(label,row)
            control.textChanged.connect(self.refresh)
        self.associative=QCheckBox('Keep links to selected boundaries');self.associative.setChecked(bool(hatch.source_entity_id) if hatch else True)
        form.addRow(self.associative)
        self.gap=QDoubleSpinBox();self.gap.setDecimals(6);self.gap.setRange(0,1e6)
        self.gap.setValue(float(get_settings().value('hatch/gap_tolerance',0)))
        self.gap.setToolTip('Temporary endpoint joins for pick-point boundaries only. Original objects are unchanged. Zero disables joins.')
        form.addRow('Pick gap tolerance',self.gap)
        right=QVBoxLayout();columns.addLayout(right,2);self.preview=Preview(self);right.addWidget(self.preview)
        hint=QLabel('Live preview • drawing units\nScale multiplies the PAT definition.\nSpacing applies to LINES only.\nBlank background = transparent.\nBYLAYER uses the current layer color.');hint.setWordWrap(True);right.addWidget(hint)
        load=QPushButton('Import PAT…');load.clicked.connect(self.import_pat);right.addWidget(load)
        boundary=QPushButton('Origin at boundary minimum');right.addWidget(boundary)
        boundary.clicked.connect(lambda:self.set_origin(hatch.bbox()[:2] if hatch else (0,0)))
        right.addStretch()
        self.error=QLabel();self.error.setWordWrap(True);layout.addWidget(self.error)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept);buttons.rejected.connect(self.reject);layout.addWidget(buttons)
        self.search.textChanged.connect(self.filter_patterns)
        self.pattern.currentTextChanged.connect(self.refresh);self.double.toggled.connect(self.refresh);self.islands.currentTextChanged.connect(self.refresh)
        self.refresh()

    def filter_patterns(self,text):
        current=self.pattern.currentText()
        names=[name for name in dict.fromkeys([*pattern_names(),*self.custom]) if text.lower() in name.lower()]
        self.pattern.blockSignals(True);self.pattern.clear();self.pattern.addItems(names)
        if current in names:self.pattern.setCurrentText(current)
        self.pattern.blockSignals(False);self.refresh()

    def choose_color(self,control):
        color=QColorDialog.getColor(QColor(control.text() if control.text().startswith('#') else '#ffffff'),self)
        if color.isValid():control.setText(color.name())

    def set_origin(self,point):
        self.controls['origin_x'].setValue(point[0]);self.controls['origin_y'].setValue(point[1])

    def import_pat(self):
        path,_=QFileDialog.getOpenFileName(self,'Import hatch patterns','','Hatch patterns (*.pat)')
        if not path:return
        try:
            patterns=read_pat(path)
            combined={**self.custom,**patterns}
            if len(combined)>512 or len(json.dumps(combined))>2*1024*1024:raise ValueError('Custom pattern library exceeds 512 patterns / 2 MiB')
            self.custom=combined
            from .appsettings import get_settings
            get_settings().setValue('hatch/custom_patterns',json.dumps(self.custom))
            for name in patterns:
                if self.pattern.findText(name)<0:self.pattern.addItem(name)
            self.search.clear();self.pattern.setCurrentText(next(iter(patterns)));self.refresh()
        except (OSError,ValueError) as ex:QMessageBox.warning(self,'PAT import',str(ex))

    def values(self):
        result={key:self.controls[key].value() for key in ('angle','spacing','pattern_scale','transparency')}
        result.update(pattern=self.pattern.currentText(),origin=Point(self.controls['origin_x'].value(),self.controls['origin_y'].value()),
            double=self.double.isChecked(),island_style=self.islands.currentText(),
            pattern_definition=copy.deepcopy(self.custom.get(self.pattern.currentText(),[])),
            color=self.color.text().strip(),background_color=self.background.text().strip() or None,
            gradient_color=self.second.text().strip())
        validate_options(result)
        from .validation import color
        color(result['color'])
        return result

    def refresh(self,*args):
        if not hasattr(self,'preview'):return
        self.controls['spacing'].setEnabled(self.pattern.currentText()=='LINES')
        try:self.values();self.error.setText('')
        except (ValueError,TypeError) as ex:self.error.setText(str(ex))
        self.preview.update()

    def accept(self):
        try:values=self.values()
        except (ValueError,TypeError) as ex:self.error.setText(str(ex));return
        from .appsettings import get_settings
        get_settings().setValue('hatch/gap_tolerance',self.gap.value())
        remember(values);super().accept()


def edit_hatch(mw):
    selected=[e for e in mw.canvas.selected_entities if isinstance(e,HatchEntity) and e in mw.document.editable_entities()]
    if not selected:raise ValueError('Select an editable hatch first')
    dialog=HatchDialog(mw,selected[0])
    if dialog.exec()!=QDialog.DialogCode.Accepted:return
    from .document import SetAttrCommand
    values=dialog.values();doc=mw.document
    doc.undo_stack.beginMacro('Edit hatch')
    try:
        for hatch in selected:
            for key,value in values.items():doc.undo_stack.push(SetAttrCommand(doc,hatch,key,copy.deepcopy(getattr(hatch,key)),copy.deepcopy(value),'Edit hatch'))
            if not dialog.associative.isChecked():
                for key,value in [('source_entity_id',None),('source_hole_ids',[])]:
                    doc.undo_stack.push(SetAttrCommand(doc,hatch,key,getattr(hatch,key),value,'Detach hatch boundary'))
    finally:doc.undo_stack.endMacro()
    mw.canvas.viewport().update()


def create_hatch(mw):
    dialog=HatchDialog(mw)
    buttons=dialog.findChild(QDialogButtonBox)
    if buttons is not None:
        button=buttons.button(QDialogButtonBox.StandardButton.Ok)
        button.setText('Pick areas…')
        button.setToolTip('Accept these settings, then click inside each area. Enter applies all previews; U removes the last area.')
    if dialog.exec()!=QDialog.DialogCode.Accepted:return
    options=dialog.values()
    associative=dialog.associative.isChecked()
    mw.set_tool('HATCH',hatch_configured=True)
    mw.current_tool.options=options
    mw.current_tool.associative=associative
    if hasattr(mw,'update_status'):mw.update_status()
    elif hasattr(mw,'_update_status'):mw._update_status()
    mw.canvas.viewport().update()



def loop_for(entity):
    from .geom_ops import circle_to_polygon
    if isinstance(entity,CircleEntity):return circle_to_polygon(entity.center,entity.radius)
    points=entity.sample_points()
    return [Point(p.x,p.y) for p in (points[:-1] if points[-1].distance_to(points[0])<1e-9 else points)]


def create_selected(mw,selected,options,associative=True):
    from .geom_ops import point_in_polygon, line_line_intersection
    from .document import AddEntityCommand
    loops=[loop_for(e) for e in selected]
    if sum(map(len,loops))>10000:raise ValueError('Selected hatch boundaries exceed 10,000 vertices')
    areas=[abs(sum(a.x*b.y-b.x*a.y for a,b in zip(loop,loop[1:]+loop[:1])))/2 for loop in loops]
    if any(a<=1e-12 for a in areas):raise ValueError('Hatch boundaries must enclose an area')
    parents=[next(iter(sorted((j for j,other in enumerate(loops) if j!=i and areas[j]>areas[i] and point_in_polygon(loop[0],other)),key=lambda j:areas[j])),None) for i,loop in enumerate(loops)]
    edges=[list(zip(loop,loop[1:]+loop[:1])) for loop in loops]
    work=0
    for i,parts in enumerate(edges):
        for j,other in enumerate(edges[:i+1]):
            for n,(a,b) in enumerate(parts):
                for m,(c,d) in enumerate(other):
                    if i==j and (m<=n or m==n+1 or n==0 and m==len(parts)-1):continue
                    if max(a.x,b.x)<min(c.x,d.x) or max(c.x,d.x)<min(a.x,b.x) or max(a.y,b.y)<min(c.y,d.y) or max(c.y,d.y)<min(a.y,b.y):continue
                    work+=1
                    if work>1000000:raise ValueError('Boundary intersections exceed the work limit; simplify the selection')
                    if line_line_intersection(a,b,c,d,True):raise ValueError('Boundaries must not cross or touch')
    roots=[i for i,parent in enumerate(parents) if parent is None]
    hatches=[]
    for i in roots:
        def root(j):
            while parents[j] is not None:j=parents[j]
            return j
        islands=[j for j in range(len(loops)) if j!=i and root(j)==i]
        hatches.append(HatchEntity(loops[i],holes=[loops[j] for j in islands],
            source_entity_id=selected[i].id if associative else None,
            source_hole_ids=[selected[j].id for j in islands] if associative else [],
            layer=mw.document.layers.current_layer,**copy.deepcopy(options)))
    # Validate the whole operation before putting anything on the undo stack.
    from .native_io import entity_to_dict,document_to_dict
    from .validation import validate_payload
    candidate=document_to_dict(mw.document);candidate['entities'] += [entity_to_dict(h) for h in hatches];validate_payload(candidate)
    mw.document.undo_stack.beginMacro('Hatch selected boundaries')
    try:
        for hatch in hatches:mw.document.undo_stack.push(AddEntityCommand(mw.document,hatch,'Hatch'))
    finally:mw.document.undo_stack.endMacro()
    mw.canvas.viewport().update()
    return hatches


def recreate_boundary(mw):
    from .document import AddEntityCommand
    selected=[e for e in mw.canvas.selected_entities if isinstance(e,HatchEntity)]
    if not selected:raise ValueError('Select a hatch first')
    mw.document.undo_stack.beginMacro('Recreate hatch boundaries')
    try:
        for hatch in selected:
            for loop in [hatch.boundary,*hatch.holes]:
                mw.document.undo_stack.push(AddEntityCommand(mw.document,PolylineEntity(copy.deepcopy(loop),closed=True,layer=mw.document.layers.current_layer),'Hatch boundary'))
    finally:mw.document.undo_stack.endMacro()


def send_to_back(mw):
    from PyQt6.QtGui import QUndoCommand
    doc=mw.document
    selected=[e for e in mw.canvas.selected_entities if isinstance(e,HatchEntity) and e in doc.editable_entities()]
    if not selected:raise ValueError('Select editable hatches to place behind the drawing')
    class OrderCommand(QUndoCommand):
        def __init__(self):
            super().__init__('Send hatches to back');self.before=list(doc.entities)
            self.after=[e for e in self.before if e in selected]+[e for e in self.before if e not in selected]
        def redo(self):doc.entities[:]=self.after;mw.canvas.viewport().update()
        def undo(self):doc.entities[:]=self.before;mw.canvas.viewport().update()
    doc.undo_stack.push(OrderCommand())
