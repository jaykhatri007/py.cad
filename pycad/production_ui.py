"""Seven production workflows using the existing drawing and publishing engines."""
import copy,json,tempfile
from pathlib import Path
from PyQt6.QtCore import Qt,QTimer
from PyQt6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QListWidget,QListWidgetItem,QStackedWidget,QWidget,QLabel,QFileDialog,QInputDialog,QComboBox,QAbstractItemView,QPlainTextEdit,QPushButton
from .workflow_ui import button,form,table,fill,locate
from .feature_helpers import safe_action
from . import production as p
PAGES=['Sheet sets','Drawing comparison','Preview / publish','Annotations','Architecture','BOQ evidence','AI drafting review']
NAMES=['SHEETSETS','DRAWCOMPARE','PUBLISHPREVIEW','ANNOTATIONTOOLS','ARCHDRAFT','BOQTRACE','AIPREVIEW']

def compare_dialog(parent,before,after):
 from .canvas import CadCanvas
 overlay,result=p.comparison_overlay(before,after)
 d=QDialog(parent);d.setWindowTitle('Drawing comparison — red old / green new');d.resize(1050,700);root=QVBoxLayout(d)
 note=QLabel(f"Added {len(result['added'])} · Removed {len(result['removed'])} · Modified {len(result['changed'])}. {result['matching']}. Units match: {result['units_match']}");note.setWordWrap(True);root.addWidget(note)
 mode=QComboBox();mode.addItems(['Changes overlay','Previous drawing','Current drawing']);root.addWidget(mode);canvas=CadCanvas(overlay);root.addWidget(canvas,1)
 def switch(index):canvas.document=[overlay,before,after][index];canvas.zoom_extents();canvas.viewport().update()
 mode.currentIndexChanged.connect(switch);button(d,root,'Close',d.accept);QTimer.singleShot(0,canvas.zoom_extents);d.exec()
 return result

def staged_pdf(mw,spaces,preset,directory):
 from .desk_jobs import run
 path=Path(directory)/'publish.pdf';result=run(mw,'export',dict(stage=str(path),format='PDF',spaces=spaces,preset=preset),mw.document)
 return path if result is not None else None

def pdf_preview(parent,path):
 from PyQt6.QtPdf import QPdfDocument
 from PyQt6.QtPdfWidgets import QPdfView
 d=QDialog(parent);d.setWindowTitle('Publication preview — actual generated PDF');d.resize(1000,750);root=QVBoxLayout(d);document=QPdfDocument(d)
 if document.load(str(path))!=QPdfDocument.Error.None_:raise ValueError('Generated PDF could not be opened')
 view=QPdfView(d);view.setDocument(document);view.setPageMode(QPdfView.PageMode.MultiPage);view.setZoomMode(QPdfView.ZoomMode.FitToWidth);root.addWidget(view)
 root.addWidget(QLabel(f'{document.pageCount()} pages · preview uses the same PDF as publication'))
 def save():
  target,_=QFileDialog.getSaveFileName(d,'Save previewed PDF','sheet-set.pdf','PDF (*.pdf)')
  if target:
   from .native_io import atomic_write
   raw=Path(path).read_bytes();atomic_write(target,lambda stage:Path(stage).write_bytes(raw))
 button(d,root,'Save this PDF…',save);button(d,root,'Close',d.accept);d.exec();document.close()

class ProductionDialog(QDialog):
 def __init__(self,mw,index=0):
  super().__init__(mw);self.mw=mw;self.setObjectName('production_tools');self.setWindowTitle('PY.cad — drawing production');self.resize(1000,660);root=QVBoxLayout(self);row=QHBoxLayout();root.addLayout(row,1);self.list=QListWidget();self.list.addItems(PAGES);self.list.setMaximumWidth(190);row.addWidget(self.list);self.stack=QStackedWidget();row.addWidget(self.stack,1);self.pages=[]
  for name in PAGES:w=QWidget();layout=QVBoxLayout(w);self.stack.addWidget(w);self.pages.append(layout)
  for method in (self.sheets,self.compare,self.publish,self.annotations,self.architecture,self.quantities,self.ai):method()
  self.list.currentRowChanged.connect(self.stack.setCurrentIndex);self.list.setCurrentRow(index);button(self,root,'Close',self.accept)
 @property
 def doc(self):return self.mw.document
 def note(self,l,text):label=QLabel(text);label.setWordWrap(True);l.addWidget(label)
 def changed(self):self.mw.refresh_document_ui()
 def sheets(self):
  l=self.pages[0];self.note(l,'Drag sheets to order them; check the sheets to include. Save the set into this drawing. Title fields and issue history survive native save/reopen. Rename/delete warnings are shown when a saved set needs repair.')
  sets=QComboBox();sets.setObjectName('sheet_set_names');l.addWidget(sets);items=QListWidget();items.setObjectName('ordered_sheets');items.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove);l.addWidget(items)
  def refresh():
   sets.blockSignals(True);old=sets.currentText();sets.clear();sets.addItem('All layouts');sets.addItems(p.data(self.doc).get('sheet_sets',{}));sets.setCurrentText(old);sets.blockSignals(False);load()
  def load():
   record=p.data(self.doc).get('sheet_sets',{}).get(sets.currentText());spaces=record['spaces'] if record else list(self.doc.layouts);items.clear()
   for s in spaces:
    title=self.doc.extensions.get('sheets',{}).get(s,{});item=QListWidgetItem(f"{s}  |  {title.get('number','')}  {title.get('title','')}  Rev {title.get('revision','')}"+(' [MISSING]' if s not in self.doc.layouts else ''));item.setData(Qt.ItemDataRole.UserRole,s);item.setFlags(item.flags()|Qt.ItemFlag.ItemIsUserCheckable);item.setCheckState(Qt.CheckState.Checked);items.addItem(item)
  def selected():return [items.item(i).data(Qt.ItemDataRole.UserRole) for i in range(items.count()) if items.item(i).checkState()==Qt.CheckState.Checked]
  def save():
   name,ok=QInputDialog.getText(self,'Save sheet set','Set name',text='' if sets.currentText()=='All layouts' else sets.currentText())
   if ok:p.save_set(self.doc,name,selected());self.changed();refresh();sets.setCurrentText(name)
  def new():
   r=form(self,'New paper sheet',[('Name','Layout',None),('Width mm',297.,None),('Height mm',210.,None)])
   if r:self.doc.create_layout(r['Name'],r['Width mm'],r['Height mm']);self.changed();refresh()
  def title():
   current=items.currentItem()
   if current is None:raise ValueError('Choose a sheet')
   space=current.data(Qt.ItemDataRole.UserRole);old=self.doc.extensions.get('sheets',{}).get(space,dict(project='Project',title=space,number='A001',revision='A',author=''))
   r=form(self,'Title block',[(k,v,None) for k,v in old.items()])
   if r:
    from .sheets import title_block
    title_block(self.doc,space,**r);self.changed();load()
  def renumber():
   r=form(self,'Renumber checked sheets',[('Prefix','A',None),('Start',1,None)])
   if r:p.renumber(self.doc,selected(),r['Prefix'],int(r['Start']));self.changed();load()
  def issue():
   r=form(self,'Issue saved set',[('Revision','A',None),('Note','',None)])
   if r:p.issue_set(self.doc,sets.currentText(),r['Revision'],r['Note']);self.changed();load()
  def history():
   from .pro_ui import report
   report(self,'Sheet issue history',p.data(self.doc).get('sheet_sets',{}).get(sets.currentText(),{}).get('issues',[]))
  sets.currentTextChanged.connect(load);bar=QHBoxLayout();l.addLayout(bar)
  for text,fn in [('New sheet',new),('Title fields',title),('Renumber',renumber),('Save set',save),('Issue set',issue),('History',history),('Refresh',refresh)]:button(self,bar,text,fn)
  refresh()
 def compare(self):
  l=self.pages[1];self.note(l,'Compare a previous native/DXF/DWG drawing with the current drawing. Added, removed and modified objects are colored in a separate read-only comparison canvas. Native IDs give reliable identity; independent imports can appear as remove/add. Old and new nested block definitions stay separate.')
  self.previous=None;status=QLabel('No previous drawing loaded');status.setWordWrap(True);l.addWidget(status)
  def load():
   from .pro_ui import load_copy
   previous=load_copy(self)
   if previous is not None:self.previous=previous;status.setText(f'Previous drawing: {len(previous.entities)} objects')
  def show():
   if self.previous is None:raise ValueError('Choose a previous drawing')
   return compare_dialog(self,self.previous,self.doc)
  def export():
   if self.previous is None:raise ValueError('Choose a previous drawing')
   path,_=QFileDialog.getSaveFileName(self,'Export comparison','drawing-changes.json','JSON (*.json)')
   if path:
    from .native_io import atomic_write
    raw=json.dumps(p.comparison(self.previous,self.doc),indent=2);atomic_write(path,lambda stage:Path(stage).write_text(raw))
  button(self,l,'Choose previous drawing…',load);button(self,l,'Show visual comparison',show);button(self,l,'Export change report…',export);l.addStretch()
 def publish(self):
  l=self.pages[2];self.note(l,'Preview the actual vector PDF before saving. Saved sheet sets retain their order; each layout uses its physical paper size and viewport scales. Model-only output uses the selected preset. Layer plot flags and lineweights use the existing plot engine.')
  sets=QComboBox();sets.setObjectName('publish_sets');l.addWidget(sets);presets=QComboBox();l.addWidget(presets)
  def refresh():
   sets.clear();sets.addItems(['Model','All layouts']);sets.addItems(p.data(self.doc).get('sheet_sets',{}));presets.clear();presets.addItem('Default');presets.addItems(self.doc.extensions.get('plot_presets',{}))
  def preview():
   key=sets.currentText();spaces=['Model'] if key=='Model' else list(self.doc.layouts) if key=='All layouts' else p.data(self.doc).get('sheet_sets',{}).get(key,{}).get('spaces',[])
   from .sheets import DEFAULT_PRESET
   preset=self.doc.extensions.get('plot_presets',{}).get(presets.currentText(),DEFAULT_PRESET)
   with tempfile.TemporaryDirectory(prefix='pycad-preview-') as directory:
    path=staged_pdf(self.mw,spaces,preset,directory)
    if path:pdf_preview(self,path)
  def setup():
   from .sheets import DEFAULT_PRESET,save_preset
   old=self.doc.extensions.get('plot_presets',{}).get(presets.currentText(),DEFAULT_PRESET)
   r=form(self,'Page / plot preset',[('Name','Production',None),('Width mm',old['page_width'],None),('Height mm',old['page_height'],None),('Margin mm',old['margin'],None),('Monochrome',old['monochrome'],None),('Scale denominator (0 = fit)',old['scale_denominator'] or 0.,None)])
   if r:save_preset(self.doc,r['Name'],dict(page_width=r['Width mm'],page_height=r['Height mm'],margin=r['Margin mm'],monochrome=r['Monochrome'],scale_denominator=r['Scale denominator (0 = fit)'] or None));self.changed();refresh();presets.setCurrentText(r['Name'])
  button(self,l,'Refresh available sets / presets',refresh);button(self,l,'Page and plot settings…',setup);button(self,l,'Preview / save ordered PDF…',preview)
  from .efficiency_ui import show
  button(self,l,'Batch convert / plot drawing files…',lambda:show(self.mw,5));l.addStretch();refresh()
 def annotations(self):
  l=self.pages[3];self.note(l,'Set selected text to a chosen paper height at 1:N; space selected parallel linear dimensions in one Undo step. Per-viewport annotation multipliers apply consistently in display and PDF. Existing text and dimension style managers remain available.')
  def height():
   r=form(self,'Paper text size',[('Paper height mm',2.5,None),('Scale denominator',100.,None)])
   if r:p.text_paper_height(self.doc,self.mw.canvas.selected_entities,r['Paper height mm'],r['Scale denominator']);self.changed()
  def dimension_size():
   r=form(self,'Paper dimension size',[('Paper height mm',2.5,None),('Scale denominator',100.,None)])
   if r:p.dimension_paper_size(self.doc,self.mw.canvas.selected_entities,r['Paper height mm'],r['Scale denominator']);self.changed()
  def spacing():
   value,ok=QInputDialog.getDouble(self,'Dimension spacing','Gap in model units',10.,.000001,1e9,6)
   if ok:p.space_dimensions(self.doc,self.mw.canvas.selected_entities,value);self.changed()
  def viewport():
   from .viewport_plus import config,set_config
   layouts=[s for s in self.doc.layouts if self.doc.layouts[s].viewports]
   if not layouts:raise ValueError('Create a paper viewport first')
   space,ok=QInputDialog.getItem(self,'Annotation scale','Paper layout',layouts,0,False)
   if not ok:return
   index,ok=QInputDialog.getInt(self,'Viewport','Viewport number',1,1,len(self.doc.layouts[space].viewports))
   if not ok:return
   cfg=config(self.doc,space,index-1);value,ok=QInputDialog.getDouble(self,'Annotation multiplier','Text / dimensions / leader multiplier',cfg['annotation_scale'],.000001,1e6,6)
   if ok:set_config(self.doc,space,index-1,cfg['rotation'],cfg['clip'],value);self.changed()
  button(self,l,'Selected text: paper height…',height);button(self,l,'Selected dimensions: paper size…',dimension_size);button(self,l,'Space selected dimensions…',spacing);button(self,l,'Viewport annotation scale…',viewport)
  button(self,l,'Dimension style manager…',lambda:self.mw.run_ribbon_command('DIMSTYLE'));button(self,l,'Text style manager…',lambda:self.mw.run_ribbon_command('STYLE'));l.addStretch()
 def architecture(self):
  l=self.pages[4];self.note(l,'Use existing associative walls, hosted doors/windows and room boundaries. Opening widths are checked against their host. Area schedules recalculate from room geometry; quantities require physical drawing units. A previewed room plan can create a complete labeled arrangement.')
  from .architecture import create_from_selection,create_opening,room_metrics
  from .geometry import BlockReferenceEntity
  def wall():self.accept();create_from_selection(self.mw,'wall')
  def opening(kind):
   selected=self.mw.canvas.selected_entities
   if len(selected)!=1:raise ValueError('Select one architectural wall')
   r=form(self,kind.title(),[('Station',1000.,None),('Width',900. if kind=='door' else 1200.,None),('Height',2100. if kind=='door' else 1200.,None),('Sill',0. if kind=='door' else 900.,None),('Identifier','D01' if kind=='door' else 'W01',None)])
   if r:create_opening(self.doc,selected[0],r['Station'],r['Width'],r['Height'],kind,r['Identifier'],r['Sill']);self.changed()
  def room():create_from_selection(self.mw,'room');self.changed()
  schedule=table(l,['Room','Number','Area (drawing units²)','Perimeter (drawing units)'],'room_production_schedule');records=[]
  def refresh():
   self.doc.sync_associative();records[:]=[(key,r,room_metrics(self.doc,r)) for key,r in self.doc.extensions.get('architecture',{}).items() if r['kind']=='room'];fill(schedule,[[r['name'],r['number'],round(metrics[1],6),round(metrics[2],6)] for key,r,metrics in records])
  def select():
   i=schedule.currentRow()
   if i>=0:locate(self.mw,[records[i][0]])
  schedule.cellClicked.connect(lambda *_:select())
  for label,fn in [('Wall / walls from selected lines…',wall),('Door on selected wall…',lambda:opening('door')),('Window on selected wall…',lambda:opening('window')),('Room from selected closed boundary…',room),('Refresh room areas',refresh),('Preview room planner…',lambda:self.mw.run_ribbon_command('ROOMPLANNER'))]:button(self,l,label,fn)
  def export():
   refresh();path,_=QFileDialog.getSaveFileName(self,'Room schedule','room-schedule.csv','CSV (*.csv)')
   if path:
    import csv
    from .native_io import atomic_write
    def write(stage):
     with open(stage,'w',newline='',encoding='utf-8-sig') as f:
      w=csv.writer(f);w.writerow(['Source ID','Room','Number','Area ('+self.doc.units+'²)','Perimeter ('+self.doc.units+')']);w.writerows([[key,r['name'],r['number'],m[1],m[2]] for key,r,m in records])
    atomic_write(path,write)
  button(self,l,'Export area schedule…',export)
  def live():
   from .productivity import create_table,schedule_cells
   r=form(self,'Live room schedule',[('Block name','Room schedule',None),('Position x,y','0,0',None),('Column width',45.,None),('Row height',8.,None)])
   if r:
    position=[float(v) for v in r['Position x,y'].split(',')]
    create_table(self.doc,r['Block name'],schedule_cells(self.doc,'Rooms'),position,r['Column width'],r['Row height'],schedule='Rooms');self.changed()
  button(self,l,'Place automatic room area schedule…',live)

 def quantities(self):
  l=self.pages[5];status=QLabel();status.setWordWrap(True);l.addWidget(status);self.note(l,'Capture source-level quantities, then click any row to highlight its drawing source. A conservative fingerprint flags model, rate or measurement changes as outdated. Captures persist in native files. Refresh replaces the capture with one Undo step; no rates are invented.')
  t=table(l,['Description','Unit','Quantity','Source ID','Method'],'quantity_evidence');rows=[]
  def refresh():
   state=p.data(self.doc).get('quantity_snapshot',{});rows[:]=state.get('rows',[]);fill(t,[[r['description'],r['unit'],r['quantity'],r['source_id'],r['method']] for r in rows]);status.setText(p.quantity_status(self.doc)+' · '+state.get('created',''))
  def capture():p.refresh_quantities(self.doc);self.changed();refresh()
  def select():
   i=t.currentRow()
   if i>=0:
    if self.doc.find_by_id(rows[i]['source_id']) is None:raise ValueError('Source removed; quantity evidence is outdated')
    locate(self.mw,[rows[i]['source_id']])
  t.cellClicked.connect(lambda *_:safe_action(self,select)());button(self,l,'Recalculate / capture source evidence',capture);button(self,l,'Check freshness',refresh);button(self,l,'Highlight source',select);button(self,l,'Rates and full BOQ…',lambda:self.mw.run_ribbon_command('BOQ'))
  # Do not hash large drawings on every UI tick; explicit Check freshness is immediate.
  self.list.currentRowChanged.connect(lambda index:refresh() if index==5 else None);refresh()
 def ai(self):
  l=self.pages[6];self.note(l,'Drafting chat supports local rule-based instructions and an optional configured model. Every action proposal is validated on a copy, visually compared with the original, and applied only after approval. Apply creates one Undo step. Model services are optional; no API key is bundled.')
  prompt=QPlainTextEdit('room 6m x 4m at 0,0');prompt.setMaximumHeight(130);l.addWidget(prompt)
  # Keep the established chat parser/provider path for prompts and missing dimensions.
  def chat():
   from .drafting_chat import show
   show(self.mw);self.mw.drafting_chat.prompt.setPlainText(prompt.toPlainText());self.accept()
  button(self,l,'Open drafting chat with this instruction',chat)
  self.note(l,'Examples: room 6m x 4m at 0,0; wall from 0,0 to 6000,0 width 200 height 3000; explain quantities. Preview / Apply now includes a red/green changes overlay and the exact action list.');l.addStretch()

def show(mw,index=0):return ProductionDialog(mw,index).exec()
def commands(mw):return {'PRODUCTION':lambda:show(mw),**{name:lambda i=i:show(mw,i) for i,name in enumerate(NAMES)}}
