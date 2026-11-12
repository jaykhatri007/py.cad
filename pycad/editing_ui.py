"""Compact selection, grips, boundary review, tracking, workspace and health hub."""
import copy,json,math
from pathlib import Path
from PyQt6.QtCore import Qt,QTimer
from PyQt6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QWidget,QListWidget,QStackedWidget,QLabel,QComboBox,QLineEdit,QCheckBox,QInputDialog,QFileDialog,QTableWidgetItem
from .workflow_ui import button,form,table,fill,locate
from .geometry import Point
from . import editing as e
from .tools import Tool
PAGES=['Selection filters','Advanced grips','Boundary repair','Drafting aids','Workspace presets','Drawing health']
NAMES=['SELECTFILTER','ADVGRIPS','BOUNDARYREPAIR','DRAFTINGAIDS','WORKSPACEPRESETS','DRAWINGHEALTH']

def review(mw,proposal):
 from .canvas import CadCanvas
 candidate=e.proposed(mw.document,proposal);doc=mw.document;selected=[q.id for q in mw.canvas.selected_entities]
 d=QDialog(mw);d.setWindowTitle('Review '+proposal['label']);d.resize(900,600);root=QVBoxLayout(d);label=QLabel(proposal.get('note','Preview staged geometry; Apply creates one Undo step.'));label.setWordWrap(True);root.addWidget(label);canvas=CadCanvas(candidate);root.addWidget(canvas,1);bar=QHBoxLayout();root.addLayout(bar)
 def before():canvas.document=doc if canvas.document is candidate else candidate;canvas.zoom_extents();canvas.viewport().update()
 button(d,bar,'Toggle original / proposal',before);button(d,bar,'Apply changes',d.accept);button(d,bar,'Cancel',d.reject);QTimer.singleShot(0,canvas.zoom_extents)
 if d.exec()!=QDialog.DialogCode.Accepted:return False
 if mw.document is not doc:raise ValueError('Active drawing changed; rebuild the preview')
 e.apply(doc,proposal);mw.canvas.selected_entities=[q for key in selected if (q:=doc.find_by_id(key)) is not None];mw.refresh_document_ui();mw.refresh_selection_ui();return True

class PointAction(Tool):
 name='PRECISIONPOINT'
 def __init__(self,mw,callback,prompt,preview=None):super().__init__(mw);self.callback=callback;self.prompt=prompt;self.preview=preview;self.cursor=None
 def on_click(self,x,y,snap_kind,button):
  if button==Qt.MouseButton.LeftButton.value:
   self.finish();self.callback(Point(x,y))
 def on_text_input(self,text):
  pt=self.parse_point(text)
  if pt:self.on_click(pt.x,pt.y,'',Qt.MouseButton.LeftButton.value)
 def on_move(self,x,y,kind):self.cursor=Point(x,y)
 def draw_preview(self,painter,canvas):
  if self.preview is not None and self.cursor is not None:self.preview(painter,canvas,self.cursor)

class StretchVertices(Tool):
 name='VERTEXSTRETCH'
 def __init__(self,mw,vertices):
  super().__init__(mw);self.vertices=copy.deepcopy(vertices);self.stamp=e.fingerprint(self.document);self.cursor=None
  self.copies=[copy.deepcopy(self.document.find_by_id(key)) for key in vertices]
 def status_prompt(self):return 'STRETCH VERTICES: pick base point' if not self.points else 'STRETCH VERTICES: pick target point; Esc cancels'
 def on_move(self,x,y,kind):self.cursor=Point(x,y)
 def on_click(self,x,y,kind,button):
  if button!=Qt.MouseButton.LeftButton.value:return
  if not self.points:self.points=[Point(x,y)];self.mw.update_status();return
  if self.mw.document is not self.document or e.fingerprint(self.document)!=self.stamp:raise ValueError('Drawing changed; restart vertex stretch')
  base=self.points[0];proposal=e.vertex_plan(self.document,self.vertices,x-base.x,y-base.y);self.finish();review(self.mw,proposal)
 def on_text_input(self,text):
  pt=self.parse_point(text,self.points[-1] if self.points else None)
  if pt:self.on_click(pt.x,pt.y,'',Qt.MouseButton.LeftButton.value)
 def draw_preview(self,painter,canvas):
  from PyQt6.QtGui import QPen,QColor
  if not self.points or self.cursor is None:return
  painter.save();painter.setPen(QPen(QColor('#65d9b2'),1.5,Qt.PenStyle.DashLine))
  try:
   dx,dy=self.cursor.x-self.points[0].x,self.cursor.y-self.points[0].y
   for source in self.copies:
    clone=copy.deepcopy(source);grips=dict(clone.grip_points())
    for kind in self.vertices[source.id]:grips[kind].x+=dx;grips[kind].y+=dy
    canvas._draw_entity(painter,clone)
  finally:painter.restore()

def activate(mw,tool):mw.cancel_command();mw.current_tool=tool;mw.canvas.set_active_tool(tool);mw.update_status();mw.canvas.setFocus()

class EditingDialog(QDialog):
 def __init__(self,mw,index=0):
  super().__init__(mw);self.mw=mw;self.setObjectName('editing_tools');self.setWindowTitle('PY.cad — precision editing');self.resize(1000,650);root=QVBoxLayout(self);row=QHBoxLayout();root.addLayout(row,1);self.list=QListWidget();self.list.addItems(PAGES);self.list.setMaximumWidth(190);row.addWidget(self.list);self.stack=QStackedWidget();row.addWidget(self.stack,1);self.pages=[]
  for name in PAGES:w=QWidget();l=QVBoxLayout(w);self.stack.addWidget(w);self.pages.append(l)
  for method in (self.filters,self.grips,self.boundary,self.aids,self.workspaces,self.health):method()
  self.list.currentRowChanged.connect(self.stack.setCurrentIndex);self.list.setCurrentRow(index);button(self,root,'Close',self.accept)
 @property
 def doc(self):return self.mw.document
 def note(self,l,text):label=QLabel(text);label.setWordWrap(True);l.addWidget(label)
 def filters(self):
  from PyQt6.QtWidgets import QFormLayout,QDoubleSpinBox
  l=self.pages[0];self.note(l,'Combine filters with AND. Only visible, editable model objects are selected; groups/blocks remain single objects. Colors match stored BYLAYER/BYBLOCK or explicit values. Preview does not alter the selection.')
  f=QFormLayout();l.addLayout(f);fields={}
  choices={'kind':['Any']+sorted({q.kind for q in self.doc.entities}),'layer':['Any']+list(self.doc.layers.layers),'color':['Any']+sorted({q.color for q in self.doc.entities}),'block':['Any']+list(self.doc.blocks),'linetype':['Any']+sorted({q.linetype for q in self.doc.entities})}
  for key,values in choices.items():w=QComboBox();w.addItems(values);w.setObjectName('filter_'+key);f.addRow(key.title(),w);fields[key]=w
  text=QLineEdit();text.setObjectName('filter_text');f.addRow('Text contains',text)
  minimum=QLineEdit();maximum=QLineEdit();f.addRow('Minimum length (blank = any)',minimum);f.addRow('Maximum length (blank = any)',maximum);scope=QComboBox();scope.addItems(['All editable objects','Current selection']);f.addRow('Search',scope);mode=QComboBox();mode.addItems(['Replace','Add','Subtract','Intersect']);f.addRow('Selection operation',mode);status=QLabel();l.addWidget(status)
  def criteria():return {**{k:w.currentText() for k,w in fields.items()},'text':text.text(),'min_length':float(minimum.text()) if minimum.text().strip() else None,'max_length':float(maximum.text()) if maximum.text().strip() else None}
  def matches():return e.filter_entities(self.doc,criteria(),self.mw.canvas.selected_entities if scope.currentIndex()==1 else None)
  def preview():status.setText(f'{len(matches())} matching editable objects')
  def apply():items=matches();e.select(self.mw,items,mode.currentText());status.setText(f'{len(items)} matches; {len(self.mw.canvas.selected_entities)} selected')
  button(self,l,'Preview matches',preview);button(self,l,'Apply selection filter',apply)
 def grips(self):
  l=self.pages[1];self.note(l,'Select lines/polylines before opening this page, then check multiple grips. Stretch by offset or pick base/target points in the viewport with a ghost preview. Review/Apply creates one Undo step. Existing single-grip dragging remains available.')
  t=table(l,['Move','Object ID','Grip','X','Y'],'vertex_grips');entries=[]
  def refresh():
   entries[:]=[(q.id,kind,p) for q in self.mw.canvas.selected_entities if q.kind in ('LINE','LWPOLYLINE','RECTANGLE') for kind,p in q.grip_points()];fill(t,[['',key,kind,p.x,p.y] for key,kind,p in entries])
   for i in range(len(entries)):
    item=t.item(i,0);item.setFlags(item.flags()|Qt.ItemFlag.ItemIsUserCheckable);item.setCheckState(Qt.CheckState.Unchecked)
  def vertices():
   values={}
   for i,(key,kind,p) in enumerate(entries):
    if t.item(i,0).checkState()==Qt.CheckState.Checked:values.setdefault(key,[]).append(kind)
   if not values:raise ValueError('Check one or more grips')
   return values
  def offset():
   r=form(self,'Stretch checked vertices',[('dx,dy','0,0',None)])
   if r:
    dx,dy=map(float,r['dx,dy'].split(','));review(self.mw,e.vertex_plan(self.doc,vertices(),dx,dy));refresh()
  def interactive():tool=StretchVertices(self.mw,vertices());self.accept();activate(self.mw,tool)
  def segment():
   selected=self.mw.canvas.selected_entities
   if len(selected)!=1:raise ValueError('Select one polyline')
   r=form(self,'Polyline segment',[('Segment index (starts at 0)',0,None),('Operation','Insert midpoint',['Insert midpoint','Remove start vertex','Straighten','Arc angle']),('Signed angle degrees (arc only)','90',None)])
   if r:review(self.mw,e.segment_plan(self.doc,selected[0],int(r['Segment index (starts at 0)']),r['Operation'],float(r['Signed angle degrees (arc only)'])));refresh()
  def arc():
   selected=self.mw.canvas.selected_entities
   if len(selected)!=1 or selected[0].kind!='ARC':raise ValueError('Select one arc')
   doc=self.doc;entity=selected[0];stamp=e.fingerprint(doc)
   def point(pt):
    if self.mw.document is not doc or e.fingerprint(doc)!=stamp:raise ValueError('Drawing changed; restart arc reshape')
    review(self.mw,e.arc_plan(doc,entity,pt))
   def ghost(painter,canvas,pt):
    from PyQt6.QtGui import QPen,QColor
    try:arc=e.arc_through(entity,pt)
    except ValueError:return
    painter.save();painter.setPen(QPen(QColor('#65d9b2'),1.5,Qt.PenStyle.DashLine))
    try:canvas._draw_entity(painter,arc)
    finally:painter.restore()
   self.accept();activate(self.mw,PointAction(self.mw,point,'ARC: pick a point for the arc to pass through; endpoints stay fixed',ghost))
  for label,fn in [('Refresh selected grips',refresh),('Stretch checked grips by offset…',offset),('Stretch checked grips in viewport',interactive),('Edit selected polyline segment…',segment),('Reshape selected arc through viewport point',arc)]:button(self,l,label,fn)
  refresh()
 def boundary(self):
  l=self.pages[2];self.note(l,'Repair a selected straight polyline or one unambiguous closed chain of lines. Small endpoint gaps and repeated/duplicate segments are reviewed on a copy. Crossing/touching loops, branches, style mismatches and managed links are rejected; they need an explicit geometry edit.')
  tolerance=QLineEdit('0.01');tolerance.setObjectName('repair_tolerance');l.addWidget(QLabel('Gap tolerance in drawing units'));l.addWidget(tolerance)
  def preview():return review(self.mw,e.boundary_plan(self.doc,list(self.mw.canvas.selected_entities),float(tolerance.text())))
  button(self,l,'Build repair preview…',preview);button(self,l,'Inspect drawing boundaries / health',lambda:self.list.setCurrentRow(5));l.addStretch()
 def aids(self):
  from . import drafting_aids as aids
  l=self.pages[3];self.note(l,'Temporary tracking points supply horizontal/vertical alignments for LINE, PLINE and WALL mouse drafting. Explicit distance/angle locks override the hovered object snap when an anchor exists; typed coordinates retain their normal explicit meaning. These aids never enter the native drawing.')
  t=table(l,['Tracking X','Tracking Y'],'tracking_points')
  def refresh():fill(t,[[p.x,p.y] for p in aids.state(self.mw.canvas)['points']])
  def point():
   self.accept();activate(self.mw,PointAction(self.mw,lambda p:aids.add_point(self.mw.canvas,p),'TRACKPOINT: click a temporary reference point'))
  def coordinate():
   value,ok=QInputDialog.getText(self,'Tracking point','x,y')
   if ok:x,y=map(float,value.split(','));aids.add_point(self.mw.canvas,Point(x,y));refresh()
  def locks():
   state=aids.state(self.mw.canvas);r=form(self,'Viewport drafting locks',[('Lock distance',state['distance'] is not None,None),('Distance',state['distance'] or 100.,None),('Lock angle',state['angle'] is not None,None),('Angle degrees',str(state['angle'] or 0.),None)])
   if r:aids.configure(self.mw.canvas,r['Distance'] if r['Lock distance'] else None,float(r['Angle degrees']) if r['Lock angle'] else None)
  def clear():aids.clear(self.mw.canvas);refresh()
  for text,fn in [('Pick temporary tracking point',point),('Add tracking coordinates…',coordinate),('Set distance / angle locks…',locks),('Clear all temporary points and locks',clear)]:button(self,l,text,fn)
  self.note(l,'The viewport shows tracking/lock labels and guide lines. Object snap labels are shown for supported drafting tools. Points and locks reset when another document is used; clear them here when finished. Up to 20 temporary references are supported.');refresh()
 def workspaces(self):
  from . import workspace_presets as presets
  l=self.pages[4];self.note(l,'Local presets restore panel docking, window geometry, ribbon tab/compact mode, application shortcuts and UI colors. Drawing geometry, file paths and graphics drivers are excluded. Capture a baseline preset before customizing.')
  combo=QComboBox();l.addWidget(combo)
  def refresh():combo.clear();combo.addItems(presets.saved())
  def save():
   name,ok=QInputDialog.getText(self,'Save workspace','Preset name')
   if ok:presets.save(self.mw,name);refresh();combo.setCurrentText(name)
  def restore():
   records=presets.saved()
   if combo.currentText() not in records:raise ValueError('Select a saved workspace')
   presets.restore(self.mw,records[combo.currentText()])
  def remove():presets.remove(combo.currentText());refresh()
  def shortcut():
   records=presets.actions(self.mw);labels=list(records);key,ok=QInputDialog.getItem(self,'Action shortcut','Action',labels,0,False)
   if not ok:return
   value,ok=QInputDialog.getText(self,'Shortcut','Key sequence (blank removes it)',text=records[key].shortcut().toString())
   if ok:
    from PyQt6.QtGui import QKeySequence
    sequence=QKeySequence(value)
    if value and sequence.isEmpty():raise ValueError('Invalid shortcut')
    if value and any(a is not records[key] and a.shortcut()==sequence for a in records.values()):raise ValueError('That shortcut is already assigned; clear the other action first')
    records[key].setShortcut(sequence)
  for text,fn in [('Save current workspace…',save),('Restore selected workspace',restore),('Delete selected workspace',remove),('Customize an action shortcut…',shortcut)]:button(self,l,text,fn)
  l.addStretch();refresh()
 def health(self):
  l=self.pages[5];self.note(l,'Read-only health scan combines invalid native data, zero geometry, closed-boundary crossings, missing associations, distant objects, unused definitions and reference/font availability. Locate entries, export the report, or open a reviewed repair/cleanup tool.')
  threshold=QLineEdit('1000000');l.addWidget(QLabel('Distant-object threshold from median center, in drawing units'));l.addWidget(threshold);t=table(l,['Severity','Code','Message','Object IDs'],'drawing_health');self.health_report=None;rows=[]
  def scan():
   from .desk_jobs import run
   result=run(self.mw,'health',dict(distant=float(threshold.text())),self.doc)
   if result is None:return
   from .efficiency import reference_report
   for r in reference_report(self.doc):
    if r['status'] not in ('Available','Embedded; no external file required'):result['rows'].append(dict(severity='Warning',code='REFERENCE',message=r['kind']+' '+r['name']+': '+r['status']+' '+r['path'],ids=[]))
   self.health_report=result;rows[:]=result['rows'];fill(t,[[r['severity'],r['code'],r['message'],', '.join(r['ids'])] for r in rows])
  def select():
   i=t.currentRow()
   if i>=0:locate(self.mw,rows[i]['ids'])
  def export():
   if self.health_report is None:raise ValueError('Run a health scan first')
   path,_=QFileDialog.getSaveFileName(self,'Health report','drawing-health.json','JSON (*.json)')
   if path:
    from .native_io import atomic_write
    atomic_write(path,lambda p:Path(p).write_text(json.dumps(self.health_report,indent=2)))
  t.cellClicked.connect(lambda *_:select());button(self,l,'Run cancellable health scan',scan);bar=QHBoxLayout();l.addLayout(bar)
  for text,fn in [('Locate issue',select),('Export report…',export),('Boundary repair',lambda:self.list.setCurrentRow(2)),('Cleanup preview',lambda:self.mw.run_ribbon_command('CLEANUPPREVIEW')),('References',lambda:self.mw.run_ribbon_command('REFDIAGNOSTICS'))]:button(self,bar,text,fn)

def show(mw,index=0):return EditingDialog(mw,index).exec()
def commands(mw):
 from . import drafting_aids
 def tracking():activate(mw,PointAction(mw,lambda p:drafting_aids.add_point(mw.canvas,p),'TRACKPOINT: click a temporary reference'))
 return {'EDITING':lambda:show(mw),'TRACKPOINT':tracking,'CLEARTRACKING':lambda:drafting_aids.clear(mw.canvas),**{name:lambda i=i:show(mw,i) for i,name in enumerate(NAMES)}}
