"""One compact hub for cache, recovery, selection, cleanup, batch and diagnostics."""
import copy,json,time
from pathlib import Path
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QWidget,QListWidget,QStackedWidget,QLabel,QFileDialog,QInputDialog,QCheckBox,QProgressDialog,QApplication,QTableWidgetItem
from .workflow_ui import button,form,table,fill,locate
from .pro_ui import report
from . import efficiency as e
PAGES=['Reopening cache','Crash recovery','Overlap selection','Command palette','Cleanup preview','Batch drawings','Reference diagnostics','Performance dashboard']
NAMES=['IMPORTCACHE','RECOVERYCENTER','SELECTCYCLE','COMMANDPALETTE','CLEANUPPREVIEW','BATCHDRAWINGS','REFDIAGNOSTICS','PERFDASHBOARD']

class EfficiencyDialog(QDialog):
    def __init__(self,mw,index=0):
        super().__init__(mw);self.mw=mw;self.setWindowTitle('PY.cad — efficiency tools');self.setObjectName('efficiency_tools');self.resize(960,620);root=QVBoxLayout(self);row=QHBoxLayout();root.addLayout(row,1);self.list=QListWidget();self.list.addItems(PAGES);self.list.setMaximumWidth(190);row.addWidget(self.list);self.stack=QStackedWidget();row.addWidget(self.stack,1);self.pages=[]
        for name in PAGES:w=QWidget();l=QVBoxLayout(w);self.stack.addWidget(w);self.pages.append(l)
        for method in (self.cache,self.recovery,self.selection,self.palette,self.cleanup,self.batch,self.references,self.performance):method()
        self.list.currentRowChanged.connect(self.stack.setCurrentIndex);self.list.setCurrentRow(index);button(self,root,'Close',self.accept)
    @property
    def doc(self):return self.mw.document
    def note(self,l,text):label=QLabel(text);label.setWordWrap(True);l.addWidget(label)
    def cache(self):
        l=self.pages[0];self.note(l,'Reopen unchanged DWGs from a private validated import snapshot. Source content, import policy, reader identity and build version are checked. Display construction still takes time. Changed/corrupt/missing entries fall back to normal import. Retains up to 10 imports / 512 MiB; originals and current drawing are never overwritten.')
        from .appsettings import get_settings
        enabled=QCheckBox('Enable faster DWG reopening');enabled.setChecked(get_settings().value('imports/cache_enabled',True,type=bool));enabled.toggled.connect(lambda value:get_settings().setValue('imports/cache_enabled',value));l.addWidget(enabled)
        def inspect():
            from .import_cache import folder
            files=list(folder().glob('*.pycad'));report(self,'Import cache',dict(entries=len(files),bytes=sum(p.stat().st_size for p in files),path=str(folder())))
        def clear():
            from .import_cache import clear
            report(self,'Import cache cleared',dict(files_removed=clear()))
        button(self,l,'Cache usage',inspect);button(self,l,'Clear disposable import cache',clear);l.addStretch()
    def recovery(self):
        l=self.pages[1];self.note(l,'Unsaved edits are checkpointed after a pause and on the regular autosave timer. After an interrupted session, validated snapshots reopen as unsaved copies by default. Original drawing files are unchanged. Keep Automatic restore off for the existing recovery question. History entries open as separate copies.')
        from .appsettings import get_settings
        automatic=QCheckBox('Automatically restore validated interrupted sessions');automatic.setChecked(get_settings().value('recovery/automatic_restore',True,type=bool));automatic.toggled.connect(lambda value:get_settings().setValue('recovery/automatic_restore',value));l.addWidget(automatic);t=table(l,['Created','Source','Snapshot'],'recovery_entries');records=[]
        def refresh():
            from .recovery_history import entries
            records[:]=entries();fill(t,[[time.strftime('%Y-%m-%d %H:%M:%S',time.localtime(r['created'])),r['source'],r['file']] for r in records])
        def restore():
            from .recovery_history import restore
            row=t.currentRow()
            if row<0:raise ValueError('Choose a snapshot')
            doc=restore(records[row]);self.mw.drawing_tabs.add_document(doc);self.mw.refresh_document_ui()
        button(self,l,'Checkpoint current unsaved tabs now',self.mw._do_autosave);button(self,l,'Refresh recovery history',refresh);button(self,l,'Open selected snapshot as unsaved copy',restore)
    def selection(self):
        l=self.pages[2];self.note(l,'While Select is active and the command line is empty, hold the cursor over overlapping geometry and press Tab / Shift+Tab to cycle editable hits. Geometry is not changed. A right-click choice list is also available; locked, hidden and isolated-away objects are excluded.')
        from .selection_cycle import cycle,choose
        button(self,l,'Cycle next overlap at cursor',lambda:cycle(self.mw));button(self,l,'Choose from overlap list',lambda:choose(self.mw));l.addStretch()
    def palette(self):
        l=self.pages[3];self.note(l,'Ctrl+Shift+P opens a searchable command palette. Search by tool name, canonical command, alias, shortcut or catalog description. Planned ribbon items are excluded; disabled actions stay disabled.')
        from .command_palette import show
        button(self,l,'Open command palette…',lambda:show(self.mw));l.addStretch()
    def cleanup(self):
        l=self.pages[4];self.note(l,'Build a review list of exact duplicate primitives, zero-length lines and unused block/layer/text/dimension definitions. Style/link differences are preserved. Managed and associated geometry is protected. Tick only entries to remove; Apply validates dependencies and uses one Undo.')
        t=table(l,['Remove','Type','Object / definition','Reason'],'cleanup_preview');plan={}
        def refresh():
            plan.clear();plan.update(e.cleanup_plan(self.doc));fill(t,[['',r['kind'],r['name'],r['reason']] for r in plan['rows']])
            for i in range(t.rowCount()):
                item=QTableWidgetItem();item.setFlags(Qt.ItemFlag.ItemIsEnabled|Qt.ItemFlag.ItemIsUserCheckable);item.setCheckState(Qt.CheckState.Unchecked);t.setItem(i,0,item)
        def selected():return [(r['kind'],r['name']) for i,r in enumerate(plan.get('rows',[])) if t.item(i,0).checkState()==Qt.CheckState.Checked]
        def highlight():locate(self.mw,[name for kind,name in selected() if kind=='Object'])
        def apply():e.apply_cleanup(self.doc,plan,selected());self.mw.refresh_document_ui();refresh()
        button(self,l,'Build / refresh cleanup preview',refresh);button(self,l,'Highlight checked objects',highlight);button(self,l,'Apply checked cleanup',apply)
    def batch(self):
        l=self.pages[5];self.note(l,'Choose DWG/DXF/native drawings and a destination folder. Output Native, DXF, or model/all-sheet PDF. Existing outputs and inputs are never overwritten. Each file gets a status/error; Cancel stops the active read/export and leaves completed results. A JSON report is saved with every batch.')
        def run():
            sources,_=QFileDialog.getOpenFileNames(self,'Batch input drawings','','Drawings (*.dwg *.dxf *.pycad)')
            if not sources:return
            destination=QFileDialog.getExistingDirectory(self,'Output directory')
            if not destination:return
            options=form(self,'Batch output',[('Format','PDF',['PDF','DXF','Native']),('Include all paper sheets in PDF',False,None)])
            if not options:return
            progress=QProgressDialog('Starting batch…','Cancel batch',0,len(sources),self);progress.setMinimumDuration(0);progress.setWindowModality(Qt.WindowModality.WindowModal)
            def update(index,total,name):progress.setValue(index);progress.setLabelText(f'{index+1} / {total} · {name}');QApplication.processEvents()
            try:value=e.batch(self,sources,destination,options['Format'],options['Include all paper sheets in PDF'],progress=update,cancelled=progress.wasCanceled)
            finally:progress.close();progress.deleteLater()
            report(self,'Batch results',value)
        button(self,l,'Convert / plot multiple drawings…',run);l.addStretch()
    def references(self):
        l=self.pages[6];self.note(l,'Check external drawing paths, installed font families and linked CSV tables. Raster/PDF underlays are embedded in native drawings and do not require original image files. Original SHX names are not always retained; font checks cover stored Qt families. Relinking a drawing reloads its geometry for review through existing import notices.')
        t=table(l,['Kind','Name','Path / font','Status'],'reference_diagnostics');records=[]
        def refresh():records[:]=e.reference_report(self.doc);fill(t,[[r[k] for k in ('kind','name','path','status')] for r in records])
        def relink():
            row=t.currentRow()
            if row<0:raise ValueError('Select a reference or font')
            r=records[row]
            if r['kind']=='Font':
                from PyQt6.QtGui import QFontDatabase
                family,ok=QInputDialog.getItem(self,'Substitute font','Installed family',QFontDatabase.families(),0,False)
                if ok:e.substitute_font(self.doc,r['name'],family)
            elif r['kind']=='Drawing':
                path,_=QFileDialog.getOpenFileName(self,'Relink drawing','','Drawings (*.dxf *.dwg)')
                if path:
                    from .xref_manager import reload_gui
                    reload_gui(self.mw,r['name'],path)
            elif r['kind']=='CSV table':
                path,_=QFileDialog.getOpenFileName(self,'Relink CSV','','CSV (*.csv)')
                if path:
                    from .productivity import state,set_table
                    value=copy.deepcopy(state(self.doc,'tables')[r['name']]);value['csv_path']=path;set_table(self.doc,r['name'],value)
            else:raise ValueError('This image/PDF is embedded. Use UNDERLAYS to replace or manage it.')
            self.mw.refresh_document_ui();refresh()
        button(self,l,'Scan references / fonts / images',refresh);button(self,l,'Relink / substitute selected…',relink);button(self,l,'Embedded underlay manager',lambda:self.mw.run_ribbon_command('UNDERLAYS'))
    def performance(self):
        l=self.pages[7];self.note(l,'Inspect current object counts, large blocks, memory, recent import/cache stages and grouped frame timings. Cached/preview frames are separated from full redraws. Recommendations use observed drawing data; physical GPU performance is not assumed.')
        summary=QLabel('Refresh to inspect this drawing.');summary.setWordWrap(True);l.addWidget(summary)
        def refresh():
            value=e.dashboard(self.doc,self.mw.canvas);summary.setText(f"Objects: {value['entities']} · Blocks: {value['blocks']} · Process memory: {value['process_resident_bytes']} bytes\n"+'\n'.join(f"{kind}: median {r['median_ms']:.2f} ms / p95 {r['p95_ms']:.2f} ms ({r['samples']} samples)" for kind,r in value['timing_groups'].items()))
        button(self,l,'Refresh live dashboard',refresh)
        button(self,l,'Inspect / export performance dashboard',lambda:report(self,'Performance dashboard',e.dashboard(self.doc,self.mw.canvas)));button(self,l,'Use cached drawing / navigation',lambda:self.mw.graphics.set_drawing_path('cached'));button(self,l,'Use progressive drawing',lambda:self.mw.graphics.set_drawing_path('progressive'));button(self,l,'CPU / GPU settings',self.mw.graphics_dialog);button(self,l,'Regional inspection cache',lambda:self.mw.run_ribbon_command('REGIONALCACHE'));l.addStretch()

def show(mw,index=0):return EfficiencyDialog(mw,index).exec()
def commands(mw):
    from .command_palette import show as palette
    from .selection_cycle import cycle
    return {'EFFICIENCY':lambda:show(mw),**{name:(lambda i=i:show(mw,i)) for i,name in enumerate(NAMES)},'COMMANDPALETTE':lambda:palette(mw),'SELECTCYCLE':lambda:cycle(mw)}
