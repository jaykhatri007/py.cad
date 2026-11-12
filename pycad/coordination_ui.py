"""One compact hub linking Properties, blocks, references, standards and lessons."""
import copy,json,tempfile
from pathlib import Path
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QWidget,QListWidget,QStackedWidget,QLabel,QFileDialog,QComboBox,QInputDialog,QPlainTextEdit,QCheckBox,QTreeWidget,QTreeWidgetItem,QProgressDialog,QApplication
from .workflow_ui import button,form,table,fill,locate
from .pro_ui import report
from . import coordination as c
PAGES=['Unified Properties','Block library','Reference coordination','Project standards','Guided tutorials','Release checks']
NAMES=['SHAREDPROPERTIES','BLOCKLIBRARY','REFCOORD','PROJECTSTANDARDS','TUTORIALS','RELEASECHECKS']
class CoordinationDialog(QDialog):
 def __init__(self,mw,index=0):
  super().__init__(mw);self.mw=mw;self.setObjectName('coordination_tools');self.setWindowTitle('PY.cad — coordinated workflows');self.resize(1000,650);root=QVBoxLayout(self);row=QHBoxLayout();root.addLayout(row,1);self.list=QListWidget();self.list.addItems(PAGES);self.list.setMaximumWidth(190);row.addWidget(self.list);self.stack=QStackedWidget();row.addWidget(self.stack,1);self.pages=[]
  for title in PAGES:w=QWidget();layout=QVBoxLayout(w);self.stack.addWidget(w);self.pages.append(layout)
  for method in (self.properties,self.blocks,self.references,self.standards,self.tutorials,self.checks):method()
  self.list.currentRowChanged.connect(self.stack.setCurrentIndex);self.list.setCurrentRow(index);button(self,root,'Close',self.accept)
 @property
 def doc(self):return self.mw.document
 def note(self,l,text):label=QLabel(text);label.setWordWrap(True);l.addWidget(label)
 def properties(self):
  l=self.pages[0];self.note(l,'The existing Properties dock now shows mixed values and combined bounds for multiple objects. Shared geometry/style/attribute fields use checkboxes: only checked explicit values are applied. The complete candidate validates before one Undo step. Specialized architectural/building fields retain their single-object editor.')
  def show():self.mw.properties_panel.show();self.mw.properties_panel.raise_();self.mw.refresh_selection_ui();self.accept()
  button(self,l,'Show unified Properties for current selection',show);l.addStretch()
 def blocks(self):
  l=self.pages[1];self.note(l,'Browse current-drawing block definitions with searchable sampled thumbnails, local name-based categories and favorites. Selected-definition previews include nested blocks. Placement has a scale/rotation ghost and remains undoable. Managed architecture/table definitions use their existing source tools.')
  from .block_library import show
  button(self,l,'Open searchable block library…',lambda:show(self.mw));l.addStretch()
 def references(self):
  l=self.pages[2];self.note(l,'Inspect references and their nested definition parents. Reload affects all instances of that definition. Missing source files retain their last imported geometry. Paths can be repaired using the existing relink/reload operation. Dependency edges describe this drawing, not a recursive scan of external files.')
  t=table(l,['Name','Status','Parents','Source'],'coordinated_references');tree=QTreeWidget();tree.setHeaderLabels(['Definition','Uses nested definition']);l.addWidget(tree);rows=[]
  def refresh():
   graph=c.reference_graph(self.doc);rows[:]=graph['rows'];fill(t,[[r['name'],r['status'],', '.join(r['parents']),r['source']] for r in rows]);tree.clear()
   for edge in graph['edges']:QTreeWidgetItem(tree,[edge['parent'],edge['child']])
   for edge in graph['missing_definitions']:QTreeWidgetItem(tree,[edge['parent'],'MISSING '+edge['child']])
  def selected():
   index=t.currentRow()
   if index<0:raise ValueError('Select an external reference')
   return rows[index]
  def op(kind):
   from . import xref_manager as x
   row=selected();name=row['name']
   if kind=='locate':return locate(self.mw,row['instance_ids'])
   if kind=='reload':x.reload_gui(self.mw,name)
   elif kind=='relink':
    path,_=QFileDialog.getOpenFileName(self,'Relink reference source','','CAD (*.dwg *.dxf)')
    if not path:return
    x.reload_gui(self.mw,name,path)
   elif kind=='unload':x.unload(self.doc,name)
   elif kind=='cached':x.restore_cache(self.doc,name)
   elif kind=='bind':x.bind(self.doc,[name])
   self.mw.refresh_document_ui();refresh()
  def all_reload():
   from .xref_manager import reload_gui
   names=[r['name'] for r in c.reference_graph(self.doc)['rows']];progress=QProgressDialog('Reloading references…','Cancel',0,len(names),self);progress.setWindowModality(Qt.WindowModality.WindowModal);progress.setAutoClose(False);results=[]
   try:
    for i,name in enumerate(names):
     progress.setValue(i);QApplication.processEvents()
     if progress.wasCanceled():break
     ok=True
     try:ok=reload_gui(self.mw,name);results.append(dict(name=name,status='Reloaded' if ok else 'Cancelled'))
     except (ValueError,OSError) as ex:results.append(dict(name=name,status='Failed',message=str(ex)))
     if not ok:break
   finally:progress.close()
   self.mw.refresh_document_ui();refresh();report(self,'Reference reload results',results)
  bar=QHBoxLayout();l.addLayout(bar)
  for text,kind in [('Locate','locate'),('Reload','reload'),('Relink…','relink'),('Unload','unload'),('Cached restore','cached'),('Bind to drawing','bind')]:button(self,bar,text,lambda kind=kind:op(kind))
  button(self,l,'Refresh dependency/status view',refresh);button(self,l,'Reload all with per-reference results',all_reload);refresh()
 def standards(self):
  l=self.pages[3];self.note(l,'Capture layers (color, linetype, lineweight, plot), complete text/dimension styles and plot presets into a portable JSON standard. Existing visibility/lock states remain. Preview differences before applying. Drawing units must match; geometry and original files are not converted.')
  self.profile=None;status=QLabel('No standard loaded');l.addWidget(status);t=table(l,['Kind','Name','Change'],'project_standard_diff')
  def capture():self.profile=c.capture_standard(self.doc);status.setText('Captured current drawing standard')
  def load():
   path,_=QFileDialog.getOpenFileName(self,'Load project standard','','JSON (*.json)')
   if path:self.profile=c.read_standard(path);status.setText(Path(path).name)
  def save():
   if self.profile is None:raise ValueError('Capture or load a standard')
   path,_=QFileDialog.getSaveFileName(self,'Save project standard','project-standard.json','JSON (*.json)')
   if path:
    from .native_io import atomic_write
    c.validate_standard(self.profile);atomic_write(path,lambda p:Path(p).write_text(json.dumps(self.profile,indent=2)))
  def preview():
   if self.profile is None:raise ValueError('Capture or load a standard')
   candidate,rows=c.standard_diff(self.doc,self.profile);fill(t,[[r['kind'],r['name'],r['change']] for r in rows]);return rows
  def apply():
   preview()
   from PyQt6.QtWidgets import QMessageBox
   if QMessageBox.question(self,'Apply project standard','Apply these standard changes as one Undo step?')!=QMessageBox.StandardButton.Yes:return
   c.apply_standard(self.doc,self.profile);self.mw.refresh_document_ui();preview()
  def batch():
   if self.profile is None:raise ValueError('Capture or load a standard')
   paths,_=QFileDialog.getOpenFileNames(self,'Choose native drawings','','PY.cad (*.pycad)')
   if not paths:return
   output=QFileDialog.getExistingDirectory(self,'New standard outputs directory')
   if not output:return
   from .desk_jobs import run
   with tempfile.TemporaryDirectory(prefix='.pycad-standards-',dir=output) as stage:
    value=run(self.mw,'standards_batch',dict(paths=paths,profile=self.profile,output=output,stage=stage))
   if value is not None:report(self,'Standards batch results',value)
  bar=QHBoxLayout();l.addLayout(bar)
  for text,fn in [('Capture current',capture),('Load…',load),('Export…',save),('Preview differences',preview),('Apply reviewed standard',apply)]:button(self,bar,text,fn)
  button(self,l,'Apply to native files as new outputs…',batch)
 def tutorials(self):
  from .tutorials import LESSONS,open_sample
  from .appsettings import get_settings
  l=self.pages[4];self.note(l,'Open a sample as a separate unsaved drawing copy. The existing drawing stays in its tab. Lesson completion is a manual local checklist, not an automatic grade. No AI service or API key is required for the local drafting lesson.')
  lessons=QComboBox();lessons.addItems([r[0] for r in LESSONS]);l.addWidget(lessons);steps=QPlainTextEdit();steps.setReadOnly(True);l.addWidget(steps);complete=QCheckBox('I completed this lesson');l.addWidget(complete)
  def refresh():
   i=lessons.currentIndex();steps.setPlainText('\n\n'.join(f'{j+1}. {v}' for j,v in enumerate(LESSONS[i][2])));complete.blockSignals(True);complete.setChecked(get_settings().value('tutorials/'+str(i),False,type=bool));complete.blockSignals(False)
  lessons.currentIndexChanged.connect(refresh);complete.toggled.connect(lambda value:get_settings().setValue('tutorials/'+str(lessons.currentIndex()),value))
  def sample():open_sample(self.mw)
  def start():command=LESSONS[lessons.currentIndex()][1];self.accept();self.mw.run_ribbon_command(command)
  button(self,l,'Open architectural sample copy',sample);button(self,l,'Open lesson tool',start);refresh()
 def checks(self):
  l=self.pages[5];self.note(l,'Run repeatable native roundtrip, software viewport capture and indexed selection measurements on a private snapshot. This excludes DWG/DXF import time; the release_stability.py script measures original-file imports separately. Timings are measurements, not a universal speed guarantee. Windows/macOS native checks are available as opt-in CI and remain unverified until run there.')
  self.last_check=None
  def run():
   from .desk_jobs import run
   value=run(self.mw,'stability',dict(repeats=3),self.doc)
   if value is not None:self.last_check=value;report(self,'Current drawing stability measurements',value)
  button(self,l,'Run cancellable current-drawing measurements',run);button(self,l,'Open drawing-health scan',lambda:self.mw.run_ribbon_command('DRAWINGHEALTH'));l.addStretch()

def show(mw,index=0):return CoordinationDialog(mw,index).exec()
def commands(mw):
 from .block_library import show as blocks
 return {'COORDINATION':lambda:show(mw),'BLOCKLIBRARY':lambda:blocks(mw),**{name:lambda i=i:show(mw,i) for i,name in enumerate(NAMES) if name!='BLOCKLIBRARY'}}
