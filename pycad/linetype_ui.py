"""Searchable linetype library with actual dash previews and undoable apply."""
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter,QPen,QColor
from PyQt6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QLineEdit,QListWidget,
    QListWidgetItem,QLabel,QPushButton,QDoubleSpinBox,QWidget,QMessageBox)
from .linetypes import NAMES,DESCRIPTIONS,apply_pen,validate_scale
from .document import SetAttrCommand


def apply_choice(mw,name,scale,target):
    if name not in NAMES:raise ValueError('Choose a library linetype')
    validate_scale(scale)
    doc=mw.document
    selected=[e for e in mw.canvas.selected_entities if e in doc.editable_entities()]
    if target=='selection' and not selected:raise ValueError('Select editable objects on unlocked layers first')
    if target not in ('current','selection','layer'):raise ValueError('Unknown linetype target')
    doc.undo_stack.beginMacro('Linetype settings')
    try:
        if scale!=doc.linetype_scale:
            doc.undo_stack.push(SetAttrCommand(doc,doc,'linetype_scale',doc.linetype_scale,scale,'Linetype scale'))
        if target=='selection':
            for entity in selected:
                if entity.linetype!=name:doc.undo_stack.push(SetAttrCommand(doc,entity,'linetype',entity.linetype,name,'Object linetype'))
        elif target=='layer':doc.edit_layer('linetype',doc.layers.current_layer,name)
        elif doc.current_linetype!=name:
            doc.undo_stack.push(SetAttrCommand(doc,doc,'current_linetype',doc.current_linetype,name,'Current linetype'))
    finally:doc.undo_stack.endMacro()
    mw.linetype_combo.blockSignals(True);mw.linetype_combo.setCurrentText(doc.current_linetype);mw.linetype_combo.blockSignals(False)
    mw.refresh_document_ui();mw.canvas.viewport().update()


class Preview(QWidget):
    def __init__(self,dialog):super().__init__(dialog);self.dialog=dialog;self.setMinimumHeight(90)
    def paintEvent(self,event):
        p=QPainter(self);p.fillRect(self.rect(),QColor('#202832'));p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen=QPen(QColor('#6bd0db'),1.5);apply_pen(pen,self.dialog.choice(),3,self.dialog.scale.value())
        p.setPen(pen);p.drawLine(12,25,self.width()-12,25)
        pen.setWidthF(3);apply_pen(pen,self.dialog.choice(),3,self.dialog.scale.value());p.setPen(pen);p.drawLine(12,60,self.width()-12,60);p.end()


class LinetypeDialog(QDialog):
    def __init__(self,mw):
        super().__init__(mw);self.mw=mw;self.setWindowTitle('Linetypes');self.resize(590,520)
        layout=QVBoxLayout(self)
        self.search=QLineEdit();self.search.setPlaceholderText('Search names or descriptions…');layout.addWidget(self.search)
        self.list=QListWidget();layout.addWidget(self.list,1)
        self.description=QLabel();self.description.setWordWrap(True);layout.addWidget(self.description)
        row=QHBoxLayout();row.addWidget(QLabel('Drawing scale'))
        self.scale=QDoubleSpinBox();self.scale.setDecimals(6);self.scale.setRange(1e-6,1e6);self.scale.setValue(mw.document.linetype_scale);row.addWidget(self.scale);row.addStretch();layout.addLayout(row)
        self.preview=Preview(self);layout.addWidget(self.preview)
        hint=QLabel('51 built-in patterns • 2 = half size • X2 = double size\nDrawing scale affects every patterned object. Preview lengths use 3 pixels per drawing unit.');hint.setWordWrap(True);layout.addWidget(hint)
        self.status=QLabel();self.status.setWordWrap(True);layout.addWidget(self.status)
        buttons=QHBoxLayout();layout.addLayout(buttons)
        for label,target in [('Set current','current'),('Apply to selection','selection'),('Set current layer','layer')]:
            button=QPushButton(label);button.clicked.connect(lambda checked=False,t=target:self.apply(t));buttons.addWidget(button)
        close=QPushButton('Close');close.clicked.connect(self.accept);buttons.addWidget(close)
        self.search.textChanged.connect(self.filter);self.list.currentItemChanged.connect(self.refresh);self.scale.valueChanged.connect(self.refresh)
        self.filter('')
        current=mw.document.current_linetype
        for i in range(self.list.count()):
            if self.list.item(i).data(Qt.ItemDataRole.UserRole)==current:self.list.setCurrentRow(i);break

    def choice(self):
        item=self.list.currentItem();return item.data(Qt.ItemDataRole.UserRole) if item else 'CONTINUOUS'

    def filter(self,text):
        previous=self.choice();self.list.clear()
        for name in NAMES:
            if text.lower() in (name+' '+DESCRIPTIONS[name]).lower():
                item=QListWidgetItem(name+'  ·  '+DESCRIPTIONS[name]);item.setData(Qt.ItemDataRole.UserRole,name);self.list.addItem(item)
                if name==previous:self.list.setCurrentItem(item)
        if self.list.currentRow()<0 and self.list.count():self.list.setCurrentRow(0)
        self.refresh()

    def refresh(self,*args):
        self.description.setText(DESCRIPTIONS.get(self.choice(),''));self.preview.update()

    def apply(self,target):
        if not self.list.currentItem():self.status.setText('No matching linetype; change the search.');return
        try:
            apply_choice(self.mw,self.choice(),self.scale.value(),target)
            self.status.setText('Applied '+self.choice()+' to '+target+'. Undo restores the previous settings.')
        except ValueError as ex:self.status.setText(str(ex))


def show(mw):
    dialog=LinetypeDialog(mw);dialog.exec();dialog.deleteLater()
