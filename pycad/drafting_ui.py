"""Compact, six-page drafting panel with reviewed changes."""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QWidget,QListWidget,QStackedWidget,QLabel,QComboBox,QLineEdit,QCheckBox,QFileDialog,QInputDialog
from .workflow_ui import button,form,table,fill,locate
from .editing_ui import review,activate,PointAction
from . import drafting as d,editing
from .geometry import Point,LineEntity,ArcEntity,CircleEntity,PolylineEntity,HatchEntity
from .tools import Tool
PAGES=['Polyline editor','Trim / extend','Hatch boundaries','Drawing search','Drawing templates','Shortcut reference']
NAMES=['POLYEDITOR','TRIMEXTEND','HATCHBOUNDARIES','DRAWSEARCH','DRAWINGTEMPLATES','SHORTCUTREFERENCE']

class FenceTool(Tool):
 name='REVIEWFENCE'
 def __init__(self,mw,cutters,extend):super().__init__(mw);self.cutters=cutters;self.extend=extend;self.stamp=editing.fingerprint(self.document);self.cursor=None
 def status_prompt(self):return 'FENCE: pick crossing points; Enter reviews all targets; Esc cancels'
 def on_click(self,x,y,kind,button):
  if button==Qt.MouseButton.LeftButton.value:self.points.append(Point(x,y));self.mw.update_status()
 def on_move(self,x,y,kind):self.cursor=Point(x,y)
 def complete(self):
  if len(self.points)<2:raise ValueError('Pick at least two fence points')
  if self.mw.document is not self.document or editing.fingerprint(self.document)!=self.stamp:raise ValueError('Drawing changed; restart the fence')
  hits=d.fence_hits(self.document,self.cutters,self.points,self.extend);proposal=d.trim_plan(self.document,self.cutters,hits,self.extend);self.finish();review(self.mw,proposal)
 def on_text_input(self,text):
  if not text.strip():self.complete();return
  pt=self.parse_point(text)
  if pt:self.points.append(pt)
 def on_key(self,key):
  if key in (Qt.Key.Key_Return,Qt.Key.Key_Enter):self.complete()
  else:super().on_key(key)
 def draw_preview(self,painter,canvas):
  from PyQt6.QtGui import QPen,QColor
  painter.save();painter.setPen(QPen(QColor('#65d9b2'),1.5,Qt.PenStyle.DashLine));points=self.points+([self.cursor] if self.cursor else [])
  for a,b in zip(points,points[1:]):painter.drawLine(canvas.world_to_screen(a.x,a.y),canvas.world_to_screen(b.x,b.y))
  painter.restore()

class DraftingDialog(QDialog):
 def __init__(self,mw,index=0):
  super().__init__(mw);self.mw=mw;self.setObjectName('drafting_tools');self.setWindowTitle('PY.cad — drafting tools');self.resize(1000,650);root=QVBoxLayout(self);row=QHBoxLayout();root.addLayout(row,1);self.list=QListWidget();self.list.addItems(PAGES);self.list.setMaximumWidth(190);row.addWidget(self.list);self.stack=QStackedWidget();row.addWidget(self.stack,1);self.pages=[]
  for name in PAGES:w=QWidget();layout=QVBoxLayout(w);self.stack.addWidget(w);self.pages.append(layout)
  for method in (self.polyline,self.trim,self.hatch,self.search,self.templates,self.shortcuts):method()
  self.list.currentRowChanged.connect(self.stack.setCurrentIndex);self.list.setCurrentRow(index);button(self,root,'Close',self.accept)
 @property
 def doc(self):return self.mw.document
 def note(self,layout,text):label=QLabel(text);label.setWordWrap(True);layout.addWidget(label)
 def polyline(self):
  l=self.pages[0];self.note(l,'Select model geometry first. Join accepts connected lines, circular arcs and open polylines of the same style/width. Other operations act on selected polylines. Width is uniform in drawing units; variable segment widths are not supported. Managed/associated sources require their existing editors.')
  operation=QComboBox();operation.addItems(['Join','Close','Open','Reverse','Simplify','Uniform width']);l.addWidget(operation);value=QLineEdit('0.01');l.addWidget(QLabel('Join/simplify tolerance, or width in drawing units'));l.addWidget(value)
  button(self,l,'Review polyline operation',lambda:review(self.mw,d.polyline_plan(self.doc,list(self.mw.canvas.selected_entities),operation.currentText(),float(value.text()))))
  def segment():
   selected=list(self.mw.canvas.selected_entities)
   if len(selected)!=1:raise ValueError('Select one polyline')
   r=form(self,'Edit polyline segment',[('Segment index (starts at 0)',0,None),('Operation','Arc angle',['Arc angle','Straighten','Insert midpoint','Remove start vertex']),('Signed arc angle','90',None)])
   if r:
    from .precision_edit import guard
    guard(self.doc,selected);review(self.mw,editing.segment_plan(self.doc,selected[0],int(r['Segment index (starts at 0)']),r['Operation'],float(r['Signed arc angle'])))
  button(self,l,'Review arc / vertex segment edit…',segment);l.addStretch()
 def trim(self):
  l=self.pages[1];self.note(l,'Select one or more cutting edges before starting. Then pick a target portion, or draw a fence through targets and press Enter. The review window shows the complete result before Apply. Cutting edges extend infinitely; arcs used as cutters use their underlying circle. Reviewed targets: line/arc/circle for trim, line/arc for extend. Curved fence hits use sampled target outlines; trimming intersections are exact.')
  operation=QComboBox();operation.addItems(['Trim','Extend']);l.addWidget(operation)
  def start(fence):
   cutters=list(self.mw.canvas.selected_entities)
   if not cutters or any(not isinstance(e,(LineEntity,CircleEntity,ArcEntity,PolylineEntity)) for e in cutters):raise ValueError('Select supported cutting edges first')
   doc=self.doc;stamp=editing.fingerprint(doc);extend=operation.currentText()=='Extend'
   def point(pt):
    if self.mw.document is not doc or editing.fingerprint(doc)!=stamp:raise ValueError('Drawing changed; restart the operation')
    from .geom_ops import pick_entity
    target=pick_entity([e for e in doc.editable_entities() if isinstance(e,(LineEntity,ArcEntity)) or not extend and isinstance(e,CircleEntity)],pt,self.mw.canvas.snap_radius_px/self.mw.canvas.zoom,exclude=cutters)
    if target is None:raise ValueError('No supported target at that point')
    review(self.mw,d.trim_plan(doc,cutters,[(target.id,pt)],extend))
   self.accept();activate(self.mw,FenceTool(self.mw,cutters,extend) if fence else PointAction(self.mw,point,'Pick target portion to trim / near endpoint to extend; Esc cancels'))
  button(self,l,'Pick one target and review',lambda:start(False));button(self,l,'Fence multiple targets and review',lambda:start(True));l.addStretch()
 def hatch(self):
  l=self.pages[2];self.note(l,'Recreate all stored hatch outer/island loops as independent closed polylines. Bulk settings preserve each hatch’s boundaries, islands and association links. Gap diagnostics inspect selected line/open-polyline endpoints; repair is a separate reviewed action.')
  selected=lambda:[e for e in self.mw.canvas.selected_entities if isinstance(e,HatchEntity)]
  button(self,l,'Review recreated hatch boundaries',lambda:review(self.mw,d.hatch_boundaries_plan(self.doc,selected())))
  def settings():
   from .hatch_ui import HatchDialog
   hatches=selected()
   if not hatches:raise ValueError('Select one or more hatches')
   dialog=HatchDialog(self,hatches[0]);dialog.associative.setEnabled(False);dialog.gap.setEnabled(False)
   if dialog.exec()==QDialog.DialogCode.Accepted:review(self.mw,d.hatch_settings_plan(self.doc,hatches,dialog.values()))
  button(self,l,'Review settings for all selected hatches…',settings);tol=QLineEdit('0.01');l.addWidget(QLabel('Endpoint gap tolerance (drawing units)'));l.addWidget(tol);t=table(l,['Object IDs','Gap','Midpoint'],'hatch_gap_results');rows=[]
  def scan():rows[:]=d.gaps(list(self.mw.canvas.selected_entities),float(tol.text()));fill(t,[[', '.join(r['ids']),r['distance'],r['point']] for r in rows])
  button(self,l,'Find nearby endpoint gaps in selection',scan)
  def locate_gap():
   i=t.currentRow()
   if 0<=i<len(rows):locate(self.mw,rows[i]['ids']);self.accept()
  button(self,l,'Locate highlighted gap objects',locate_gap)
  def repair():review(self.mw,editing.boundary_plan(self.doc,list(self.mw.canvas.selected_entities),float(tol.text())))
  button(self,l,'Review selected straight-boundary repair',repair)
 def search(self):
  l=self.pages[3];self.note(l,'Search top-level model text, placed block attribute values, layers, IDs and block names. Definition internals are excluded. Hidden/locked matches are reported; only editable objects can be selected/replaced. Text replacement converts that text object to plain text. Layer/ID/block-name matches are locate-only.')
  query=QLineEdit();query.setPlaceholderText('Find literal text…');l.addWidget(query);field=QComboBox();field.addItems(['All','Text','Attributes','Layer','ID','Block name']);l.addWidget(field);case=QCheckBox('Case sensitive');whole=QCheckBox('Whole word');l.addWidget(case);l.addWidget(whole);replacement=QLineEdit();replacement.setPlaceholderText('Replacement text');l.addWidget(replacement);t=table(l,['Replace','Object ID','Field','Value','Editable'],'drawing_search');rows=[];stamp={}
  def find():
   rows[:]=d.search(self.doc,query.text(),['Text','Attributes','Layer','ID','Block name'] if field.currentText()=='All' else [field.currentText()],case.isChecked(),whole.isChecked());stamp.update(doc=self.doc,fingerprint=editing.fingerprint(self.doc),query=query.text(),case=case.isChecked(),whole=whole.isChecked());fill(t,[['',r['id'],r['field'],r['value'],r['editable']] for r in rows])
   for i,r in enumerate(rows):
    if r['editable'] and (r['field']=='Text' or r['field'].startswith('Attribute.')):item=t.item(i,0);item.setFlags(item.flags()|Qt.ItemFlag.ItemIsUserCheckable);item.setCheckState(Qt.CheckState.Unchecked)
  def locate_row():
   i=t.currentRow()
   if 0<=i<len(rows):locate(self.mw,[rows[i]['id']]);self.accept()
  def replace():
   if stamp.get('doc') is not self.doc or stamp.get('fingerprint')!=editing.fingerprint(self.doc) or (query.text(),case.isChecked(),whole.isChecked())!=(stamp.get('query'),stamp.get('case'),stamp.get('whole')):raise ValueError('Drawing or search options changed; search again')
   checked=[r for i,r in enumerate(rows) if t.item(i,0).checkState()==Qt.CheckState.Checked];review(self.mw,d.replace_plan(self.doc,checked,query.text(),replacement.text(),case.isChecked(),whole.isChecked()));find()
  button(self,l,'Search drawing',find);button(self,l,'Locate highlighted result',locate_row);button(self,l,'Review replacements for checked results',replace)
 def templates(self):
  from .appsettings import get_settings
  l=self.pages[4];self.note(l,'Templates are data-only .pycadt/.pycad files. Settings-only templates preserve units, layers, styles, paper sheets and title-block metadata. Include geometry to preserve the complete drawing. Opening a template creates an unsaved independent drawing; the template remains unchanged.')
  include=QCheckBox('Include drawing geometry and project metadata');l.addWidget(include);path=QLineEdit(str(get_settings().value('templates/default','')));path.setReadOnly(True);l.addWidget(QLabel('Default template for New'));l.addWidget(path)
  def save():
   filename,_=QFileDialog.getSaveFileName(self,'Save drawing template','drawing-template.pycadt','PY.cad template (*.pycadt);;PY.cad drawing (*.pycad)')
   if filename:
    from pathlib import Path
    if not Path(filename).suffix:filename+='.pycadt'
    d.save_template(self.doc,filename,include.isChecked())
  def open_(default=False):
   filename,_=QFileDialog.getOpenFileName(self,'Choose drawing template','','PY.cad template (*.pycadt);;PY.cad drawing (*.pycad)')
   if not filename:return
   doc=d.open_template(filename)
   if default:
    from .document_lifecycle import dispose_document
    dispose_document(doc);get_settings().setValue('templates/default',filename);path.setText(filename)
   else:self.accept();self.mw.drawing_tabs.add_document(doc)
  def clear():get_settings().remove('templates/default');path.clear()
  for label,callback in [('Save current drawing as template…',save),('New drawing from template…',open_),('Choose default template for New…',lambda:open_(True)),('Reset New to blank drawing',clear)]:button(self,l,label,callback)
  l.addStretch()
 def shortcuts(self):
  from . import shortcut_reference as ref
  l=self.pages[5];self.note(l,'Search command names, aliases, action labels and key sequences. Edit action shortcuts with conflict checks; edits persist on this computer. Command aliases are edited as ALIAS=COMMAND and apply immediately. Reset restores built-in action shortcuts; aliases can be cleared in their editor.')
  query=QLineEdit();query.setPlaceholderText('Search shortcuts and commands…');l.addWidget(query);t=table(l,['Action / Command','Aliases','Shortcut','Description'],'shortcut_reference');visible=[]
  def refresh():
   words=query.text().casefold().split();visible[:]=[r for r in ref.records(self.mw) if all(w in ' '.join(str(v) for v in r.values()).casefold() for w in words)];fill(t,[[r['name'],r['aliases'],r['shortcut'],r['detail']] for r in visible])
  def change():
   i=t.currentRow()
   if not 0<=i<len(visible) or not visible[i]['key']:raise ValueError('Select an action row; command aliases use the alias editor')
   r=visible[i];value,ok=QInputDialog.getText(self,'Edit shortcut','Key sequence (blank clears it)',text=r['shortcut'])
   if ok:ref.assign(self.mw,r['key'],value);refresh()
  def aliases():
   from .ribbon_actions import edit_aliases
   edit_aliases(self.mw);refresh()
  def reset():ref.reset(self.mw);refresh()
  query.textChanged.connect(refresh);button(self,l,'Edit selected action shortcut…',change);button(self,l,'Edit command aliases…',aliases);button(self,l,'Reset all action shortcuts to defaults',reset);refresh()

def show(mw,index=0):return DraftingDialog(mw,index).exec()
def commands(mw):return {'DRAFTINGTOOLS':lambda:show(mw),**{name:lambda i=i:show(mw,i) for i,name in enumerate(NAMES)}}
