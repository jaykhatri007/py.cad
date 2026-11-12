"""Checked, atomic shared-property edits inside the existing Properties dock."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget,QVBoxLayout,QLabel,QTableWidget,QTableWidgetItem,QPushButton,QHeaderView
from .coordination import common_properties,properties_plan,MIXED
from .feature_helpers import safe_action
class SharedProperties(QWidget):
 def __init__(self,mw):
  super().__init__();self.mw=mw;self.items=[];self.keys=[];root=QVBoxLayout(self);root.setContentsMargins(0,2,0,2);root.addWidget(QLabel('Shared fields — check only fields to change'));self.table=QTableWidget(0,3);self.table.setObjectName('shared_properties');self.table.setHorizontalHeaderLabels(['Set','Property','Value']);self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch);self.table.setMinimumHeight(180);root.addWidget(self.table);b=QPushButton('Apply checked shared fields');b.clicked.connect(safe_action(self,self.apply));root.addWidget(b)
 def refresh(self,items):
  self.items=list(items);self.setVisible(len(items)>1)
  values=common_properties(self.mw.document,items) if len(items)>1 else {};self.keys=list(values);self.table.setRowCount(len(values))
  for i,(key,value) in enumerate(values.items()):
   check=QTableWidgetItem();check.setFlags(Qt.ItemFlag.ItemIsEnabled|Qt.ItemFlag.ItemIsUserCheckable);check.setCheckState(Qt.CheckState.Unchecked);self.table.setItem(i,0,check)
   from .object_properties import label_for
   label=QTableWidgetItem(label_for(key));label.setToolTip(key);label.setFlags(Qt.ItemFlag.ItemIsEnabled);self.table.setItem(i,1,label);self.table.setItem(i,2,QTableWidgetItem(str(value)))
 def apply(self):
  from .editing import apply
  doc=self.mw.document;changes={key:self.table.item(i,2).text() for i,key in enumerate(self.keys) if self.table.item(i,0).checkState()==Qt.CheckState.Checked}
  plan=properties_plan(doc,self.items,changes);ids=[q.id for q in self.items];apply(doc,plan);self.mw.canvas.selected_entities=[doc.find_by_id(k) for k in ids];self.mw.refresh_document_ui();self.mw.refresh_selection_ui()
