"""Compact forms for diagnostics, precision, references, sheets, recovery and takeoff."""
import copy
import json
from pathlib import Path
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QTabWidget,QWidget,QLabel,QPushButton,QPlainTextEdit,QTableWidget,QTableWidgetItem,QHeaderView,QComboBox,QCheckBox,QLineEdit,QDoubleSpinBox,QSpinBox,QDialogButtonBox,QFileDialog,QInputDialog,QAbstractItemView)
from .feature_helpers import safe_action
from . import workflow_data as data

TITLES=['Diagnostics','Performance','DWG quality','Precision','References','Sheets / pens','Recovery','Takeoff / rates','AI drafting']


def button(parent,layout,text,callback,name=None):
    b=QPushButton(text);b.setObjectName(name or text);b.clicked.connect(safe_action(parent,callback));layout.addWidget(b);return b


def form(parent,title,fields):
    d=QDialog(parent);d.setWindowTitle(title);root=QVBoxLayout(d);f=QFormLayout();root.addLayout(f);widgets={}
    for name,value,options in fields:
        if isinstance(options,list):
            w=QComboBox();w.addItems(options);w.setCurrentText(str(value))
        elif type(value) is bool:w=QCheckBox();w.setChecked(value)
        elif isinstance(value,(float,int)):
            w=QDoubleSpinBox();w.setRange(0,1e12);w.setDecimals(8);w.setValue(value)
        else:w=QLineEdit(str(value))
        widgets[name]=w;f.addRow(name,w)
    buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(d.accept);buttons.rejected.connect(d.reject);root.addWidget(buttons)
    if d.exec()!=QDialog.DialogCode.Accepted:return None
    result={}
    for name,w in widgets.items():
        result[name]=w.currentText() if isinstance(w,QComboBox) else w.isChecked() if isinstance(w,QCheckBox) else w.value() if isinstance(w,QDoubleSpinBox) else w.text()
    return result


def table(layout,headers,name):
    t=QTableWidget(0,len(headers));t.setObjectName(name);t.setHorizontalHeaderLabels(headers)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows);t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    layout.addWidget(t);return t


def fill(t,rows):
    t.setRowCount(len(rows))
    for i,row in enumerate(rows):
        for j,v in enumerate(row):t.setItem(i,j,QTableWidgetItem(str(v)))


def locate(mw,ids):
    mw.document.current_space="Model";mw.viewport_stack.setCurrentWidget(mw.canvas)
    mw.canvas.selected_entities=[e for key in ids if (e:=mw.document.find_by_id(key)) is not None and mw.document.is_editable(e)]
    mw.refresh_selection_ui()
    if mw.canvas.selected_entities:
        boxes=[e.bbox() for e in mw.canvas.selected_entities];x0=min(b[0] for b in boxes);x1=max(b[2] for b in boxes);y0=min(b[1] for b in boxes);y1=max(b[3] for b in boxes)
        from PyQt6.QtCore import QPointF
        mw.canvas.zoom=min(mw.canvas.viewport().width()/max(1,x1-x0),mw.canvas.viewport().height()/max(1,y1-y0))*.7
        mw.canvas.pan_offset=QPointF((x0+x1)/2,(y0+y1)/2);mw.canvas.viewport().update()


class WorkflowDialog(QDialog):
    def __init__(self,mw,index=0):
        super().__init__(mw);self.mw=mw;self.setObjectName('workflow_hub');self.setWindowTitle('Drawing workflow');self.resize(940,590)
        root=QVBoxLayout(self);self.tabs=QTabWidget();root.addWidget(self.tabs)
        self.pages=[]
        for title in TITLES:
            page=QWidget();layout=QVBoxLayout(page);self.tabs.addTab(page,['Diagnostics','Display','DWG','Edit','Xrefs','Sheets','Recovery','BOQ','AI'][len(self.pages)]);self.tabs.setTabToolTip(len(self.pages),title);self.pages.append(layout)
        self.diagnostics();self.performance();self.exchange();self.precision();self.references();self.sheets();self.recovery();self.takeoff();self.ai()
        self.tabs.setCurrentIndex(index);button(self,root,'Close',self.accept)

    def note(self,layout,text):
        label=QLabel(text);label.setWordWrap(True);layout.addWidget(label)

    def diagnostics(self):
        from .drawing_diagnostics import report,write_report
        l=self.pages[0];self.note(l,'Object counts, memory and recent file-open stages. Memory is for this process; driver/GPU memory is not inferred.')
        view=QPlainTextEdit();view.setObjectName('drawing_diagnostics');view.setReadOnly(True);view.setPlaceholderText('Click Refresh diagnostics to collect drawing and import details.');l.addWidget(view)
        def refresh():view.setPlainText(json.dumps(report(self.mw.document,self.mw.canvas),indent=2,ensure_ascii=False))
        def export():
            p,_=QFileDialog.getSaveFileName(self,'Export diagnostics','drawing-diagnostics.json','JSON (*.json)')
            if p:write_report(self.mw.document,p,self.mw.canvas)
        bar=QHBoxLayout();l.addLayout(bar);button(self,bar,'Refresh diagnostics',refresh);button(self,bar,'Export diagnostics',export)
        # Avoid scanning the drawing merely because another workflow page opened.
        button(self,l,'Inspect drawing now',refresh)

    def performance(self):
        from .persistent_scene import enabled,regenerate
        if enabled(self.mw.canvas):
            l=self.pages[1];self.note(l,'Layer-aware batches keep unchanged geometry ready. Supported edits repair only damaged image regions. Global or dependent changes can require preparation; REFRESH or REGEN rebuilds everything.')
            lod=QCheckBox('Simplify subpixel display features');lod.setChecked(getattr(self.mw.canvas,'progressive_lod',True));lod.setToolTip('Use already prepared point previews for features smaller than 1.5 pixels. Disable for full outlines. Model geometry and exports are unchanged.');l.addWidget(lod)
            def apply_scene():
                from .appsettings import get_settings
                self.mw.canvas.progressive_lod=lod.isChecked();get_settings().setValue('graphics/progressive_lod',lod.isChecked());self.mw.canvas.viewport().update()
            button(self,l,'Apply display profile',apply_scene)
            button(self,l,'Regenerate drawing display',lambda:regenerate(self.mw.canvas))
            button(self,l,'CPU / GPU settings',self.mw.graphics_dialog);l.addStretch();return
        l=self.pages[1];self.note(l,'Progressive draws the visible region in cooperative 8 ms chunks. Tiny unselected features may use subpixel previews. Selection, snapping and PDF exports keep model geometry. One complex object can exceed the chunk budget; files still load into memory.')
        from .graphics import DRAWING_PATHS
        mode=QComboBox();mode.setObjectName('workflow_display_path')
        for key,value in DRAWING_PATHS.items():mode.addItem(value,key)
        mode.setCurrentIndex(mode.findData(self.mw.graphics.drawing_path));l.addWidget(mode)
        lod=QCheckBox('Simplify subpixel display features');lod.setToolTip('Adaptive point previews below 1.5 pixels in background-rendered mixed batches. Disable for full outline display. Source and export geometry are unchanged.');lod.setChecked(getattr(self.mw.canvas,'progressive_lod',True));l.addWidget(lod)
        reuse=QCheckBox('Reuse display across nearby zoom levels');reuse.setChecked(getattr(self.mw.canvas,'reuse_nearby_zooms',True));reuse.setToolTip('Reuse the raster view within a 0.8–1.25 zoom ratio; disable for exact raster outlines at every scale. Model geometry and exports stay precise.');l.addWidget(reuse)
        def apply():
            from .appsettings import get_settings
            self.mw.canvas.reuse_nearby_zooms=reuse.isChecked();get_settings().setValue('graphics/reuse_nearby_zooms',reuse.isChecked())
            self.mw.canvas.progressive_lod=lod.isChecked();get_settings().setValue('graphics/progressive_lod',lod.isChecked());self.mw.graphics.set_drawing_path(mode.currentData())
        button(self,l,'Apply display profile',apply)
        button(self,l,'CPU / GPU settings',self.mw.graphics_dialog);l.addStretch()

    def exchange(self):
        l=self.pages[2];self.note(l,'The direct DWG adapter now includes supported fit/control-point splines. Unsupported structures use Auto compatibility fallback. R2000 export checks structure and model extents before replacing the destination; this is not lossless modern DWG editing.')
        button(self,l,'DWG reader settings',self.mw.show_dwg_support)
        button(self,l,'Import / failure diagnostics',lambda:self.tabs.setCurrentIndex(0))
        output=QPlainTextEdit();output.setReadOnly(True);l.addWidget(output)
        def compare():
            from .dwg_ui import load_dwg
            from .import_ui import load_dxf
            from .exchange_quality import compare_documents
            p,_=QFileDialog.getOpenFileName(self,'Compare drawing copy','','CAD (*.dwg *.dxf)')
            if not p:return
            doc=(load_dwg if p.lower().endswith('.dwg') else load_dxf)(self,p)
            if doc:output.setPlainText(json.dumps(compare_documents(self.mw.document,doc),indent=2))
        button(self,l,'Compare a DWG / DXF copy',compare)

    def precision(self):
        l=self.pages[3];self.note(l,'Exact JOIN keeps circular arc bulges. BREAKAT divides a line/arc at a fraction. Linked/grouped/managed or locked objects are protected. Nearby nested block geometry now participates in snapping.')
        def join():
            from .precision_edit import join
            value,ok=QInputDialog.getDouble(self,'Join tolerance','Drawing-unit tolerance',.000001,.000000001,1e6,9)
            if ok:
                e=join(self.mw.document,self.mw.canvas.selected_entities,value);self.mw.canvas.selected_entities=[e];self.mw.refresh_document_ui()
        def split():
            from .precision_edit import break_at
            if len(self.mw.canvas.selected_entities)!=1:raise ValueError('Select one line or arc')
            value,ok=QInputDialog.getDouble(self,'Break at','Fraction along curve',.5,.000001,.999999,6)
            if ok:break_at(self.mw.document,self.mw.canvas.selected_entities[0],value);self.mw.refresh_document_ui()
        button(self,l,'Join selected curves',join);button(self,l,'Break selected curve',split)
        for name in ('TRIM','EXTEND','FILLET','CHAMFER','OFFSET','STRETCH'):
            def start(c=name):self.accept();self.mw.run_ribbon_command(c)
            button(self,l,name.title(),start)
        l.addStretch()

    def references(self):
        from . import xref_manager as refs
        l=self.pages[4];self.note(l,'DXF / DWG references retain a cached definition. Unload is undoable and saves a private cache; undo history can retain memory. Restore cache is explicit and may be stale. Exact display/plot clipping keeps crossing strokes; DXF clip export remains limited.')
        t=table(l,['Reference','Source','Status','Objects'],'workflow_xrefs');records=[]
        def refresh():
            records[:]=refs.status(self.mw.document);fill(t,[[r[k] for k in ('name','source','status','entities')] for r in records])
        def selected():
            if t.currentRow()<0:raise ValueError('Select a reference')
            return records[t.currentRow()]['name']
        def run(action):action();refresh();self.mw.refresh_document_ui()
        bar=QHBoxLayout();l.addLayout(bar)
        button(self,bar,'Refresh',refresh);button(self,bar,'Attach',self.mw.attach_xref)
        button(self,bar,'Reload source',lambda:run(lambda:refs.reload_gui(self.mw,selected())))
        def relink():
            name=selected();p,_=QFileDialog.getOpenFileName(self,'Relink reference','','CAD (*.dwg *.dxf)')
            if p:run(lambda:refs.reload_gui(self.mw,name,p))
        button(self,bar,'Relink',relink)
        button(self,bar,'Unload',lambda:run(lambda:refs.unload(self.mw.document,selected())))
        button(self,bar,'Restore cache',lambda:run(lambda:refs.restore_cache(self.mw.document,selected())))
        button(self,bar,'Bind to drawing',lambda:run(lambda:refs.bind(self.mw.document,[selected()])))
        button(self,l,'Bind all missing cached references',lambda:run(lambda:refs.bind_gui(self.mw,True)))
        button(self,l,'Clip selected drawing instance',lambda:(self.accept(),self.mw.set_tool('XCLIP')))
        refresh()

    def sheets(self):
        l=self.pages[5];self.note(l,'Reusable physical sheet templates include scale, margins and title fields. Pen styles apply to PDF output, leaving drafting colors unchanged. Select sheets in Sheet manager to batch-publish one PDF.')
        t=table(l,['Template','Paper mm','Scale'],'workflow_sheets')
        def refresh():fill(t,[(n,f"{r['width']} × {r['height']}",f"1:{r['scale']}") for n,r in self.mw.document.extensions.get('workflow',{}).get('sheet_templates',{}).items()])
        def add():
            values=form(self,'Sheet template',[(n,v,None) for n,v in dict(Name='A3 landscape',width=420.,height=297.,margin=10.,scale=100.,project='',title='',number='A001',revision='A',author='').items()])
            if not values:return
            name=values.pop('Name');title={k:values.pop(k) for k in ('project','title','number','revision','author')};values['title']=title
            table=copy.deepcopy(self.mw.document.extensions.get('workflow',{}));table.setdefault('sheet_templates',{})[name]=values;data.save(self.mw.document,table,'Sheet template');refresh()
        def create():
            if t.currentRow()<0:raise ValueError('Select a template')
            name,ok=QInputDialog.getText(self,'New sheet','Sheet name')
            if ok:data.create_sheet(self.mw.document,t.item(t.currentRow(),0).text(),name);self.mw.refresh_document_ui()
        bar=QHBoxLayout();l.addLayout(bar);button(self,bar,'Add template',add);button(self,bar,'Create sheet',create)
        from .sheets import sheets_dialog
        button(self,bar,'Sheet manager / batch PDF',lambda:sheets_dialog(self.mw))
        def pen():
            values=form(self,'PDF pen style',[('Layer',self.mw.document.layers.current_layer,list(self.mw.document.layers.layers)),('color','#17202A',None),('width',.25,None),('plot',True,None)])
            if values:
                name=values.pop('Layer');table=copy.deepcopy(self.mw.document.extensions.get('workflow',{}));table.setdefault('pen_styles',{})[name]=values;data.save(self.mw.document,table,'PDF pen style')
        button(self,l,'Set layer PDF pen',pen)
        button(self,l,'Clear PDF pen overrides',lambda:self.save_section('pen_styles',{}))
        def transfer(importing):
            current=copy.deepcopy(self.mw.document.extensions.get('workflow',{}))
            if importing:
                p,_=QFileDialog.getOpenFileName(self,'Import sheet / pen library','','JSON (*.json)')
                if p:
                    value=json.loads(Path(p).read_text());data.validate(value)
                    if set(value)-{'sheet_templates','pen_styles'}:raise ValueError('Choose a sheet / pen library')
                    current.update(value);data.save(self.mw.document,current,'Import sheet library');refresh()
            else:
                p,_=QFileDialog.getSaveFileName(self,'Export sheet / pen library','sheet-library.json','JSON (*.json)')
                if p:
                    from .native_io import atomic_write
                    value={k:current[k] for k in ('sheet_templates','pen_styles') if k in current}
                    atomic_write(p,lambda f:Path(f).write_text(json.dumps(value,indent=2,ensure_ascii=False),encoding='utf-8'))
        row=QHBoxLayout();l.addLayout(row);button(self,row,'Import sheet library',lambda:transfer(True));button(self,row,'Export sheet library',lambda:transfer(False))
        refresh()

    def recovery(self):
        from . import recovery_history as history
        from .appsettings import get_settings
        l=self.pages[6];self.note(l,'Recovery snapshots are hash-checked and restored into a new unsaved tab. Audit repair previews remove only unlinked zero-length lines and exact duplicates; unsupported corruption is reported rather than guessed.')
        t=table(l,['Created','Source','Snapshot'],'workflow_history');records=[]
        def refresh():
            import datetime
            records[:]=history.entries();fill(t,[(datetime.datetime.fromtimestamp(r['created']).isoformat(timespec='seconds'),r['source'],r['file']) for r in records])
        def snapshot():history.snapshot(self.mw.document,int(get_settings().value('recovery/history_count',20)));refresh()
        def restore():
            if t.currentRow()<0:raise ValueError('Select a recovery snapshot')
            self.mw.drawing_tabs.add_document(history.restore(records[t.currentRow()]));self.accept()
        bar=QHBoxLayout();l.addLayout(bar);button(self,bar,'Snapshot now',snapshot);button(self,bar,'Refresh history',refresh);button(self,bar,'Restore as new tab',restore)
        def settings():
            v=form(self,'Recovery policy',[('Interval minutes',self.mw.autosave_timer.interval()/60000,None),('Snapshots per drawing',float(get_settings().value('recovery/history_count',20)),None)])
            if v:
                if not 1<=v['Interval minutes']<=120 or not 1<=v['Snapshots per drawing']<=2000:raise ValueError('Use 1–120 minutes and 1–2000 snapshots')
                get_settings().setValue('recovery/interval_minutes',v['Interval minutes']);get_settings().setValue('recovery/history_count',int(v['Snapshots per drawing']));self.mw.autosave_timer.setInterval(int(v['Interval minutes']*60000))
        button(self,l,'Recovery interval / history retention',settings)
        def repair():
            proposed=history.repair_candidates(self.mw.document)
            d=QDialog(self);d.setWindowTitle('Review audit repair');root=QVBoxLayout(d);self.note(root,f'{len(proposed)} safe removal candidates. Apply is one Undo step.')
            rows=table(root,['Object','Reason'],'audit_repair_preview');fill(rows,[(r['id'],r['reason']) for r in proposed])
            button(d,root,'Apply reviewed removals',d.accept);button(d,root,'Cancel',d.reject)
            if d.exec()==QDialog.DialogCode.Accepted and proposed:history.repair(self.mw.document,[r['id'] for r in proposed]);self.mw.refresh_document_ui()
        button(self,l,'Preview audit repair',repair)
        from .drawing_checks import dialog
        button(self,l,'Full drawing checks',lambda:dialog(self.mw));refresh()

    def save_section(self,key,value):
        settings=copy.deepcopy(self.mw.document.extensions.get('workflow',{}));settings[key]=value;data.save(self.mw.document,settings)

    def takeoff(self):
        l=self.pages[7];self.note(l,'Rules match layer patterns and object kinds in name order. Explicit tags and building objects take priority. Preview quantities before applying. Volume factors are thickness in metres; rates are user-entered, with no currency conversion.')
        t=table(l,['Rule','Layer / type','Measure','Material / specification'],'workflow_rules')
        def refresh():fill(t,[(n,r['layer']+' / '+r['kind'],r['measurement'],r['material']+' / '+r['specification']) for n,r in self.mw.document.extensions.get('workflow',{}).get('takeoff_rules',{}).items()])
        def add():
            selected=self.mw.canvas.selected_entities
            v=form(self,'Takeoff rule',[('Name','01 Quantity rule',None),('layer',selected[0].layer if selected else '*',None),('kind',selected[0].kind if selected else '*',['*','LINE','ARC','CIRCLE','LWPOLYLINE','RECTANGLE','HATCH','INSERT']),('measurement','Length',['Length','Area','Volume','Count']),('factor',1.,None),('description','Measured item',None),('material','Unspecified',None),('specification','',None)])
            if v:
                name=v.pop('Name');settings=copy.deepcopy(self.mw.document.extensions.get('workflow',{}));settings.setdefault('takeoff_rules',{})[name]=v;data.save(self.mw.document,settings,'Takeoff rule');refresh()
        def remove():
            if t.currentRow()>=0:
                values=copy.deepcopy(self.mw.document.extensions.get('workflow',{}).get('takeoff_rules',{}));values.pop(t.item(t.currentRow(),0).text());self.save_section('takeoff_rules',values);refresh()
        def preview():
            from .workflow_jobs import takeoff,fingerprint
            calculated=takeoff(self,self.mw.document)
            if calculated is None:return
            tags,specs,result=calculated['tags'],calculated['specs'],calculated['report']
            d=QDialog(self);d.setWindowTitle('Review takeoff quantities');d.resize(780,440);root=QVBoxLayout(d)
            self.note(root,f'{len(tags)} new measurement tags. {result["unpriced_items"]} items unpriced. '+ '; '.join(result['warnings']))
            rows=table(root,['Source','Description','Specification','Quantity','Unit'],'takeoff_preview')
            items=[r for r in result['items'] if r['source_id'] in tags];fill(rows,[(r['source_id'],r['description'],r['specification'],r['quantity'],r['unit']) for r in items])
            rows.cellDoubleClicked.connect(lambda row,col:locate(self.mw,[items[row]['source_id']]))
            button(d,root,'Apply reviewed tags',d.accept);button(d,root,'Cancel',d.reject)
            if d.exec()==QDialog.DialogCode.Accepted and tags:
                if fingerprint(self.mw.document)!=calculated['fingerprint']:raise ValueError('Drawing changed during review; preview again')
                data.apply_tags(self.mw.document,tags,specs);self.mw.refresh_document_ui()
        bar=QHBoxLayout();l.addLayout(bar);button(self,bar,'Add rule',add);button(self,bar,'Remove rule',remove);button(self,bar,'Preview rule takeoff',preview)
        def rate():
            v=form(self,'Rate library item',[('description','Measured item',None),('material','Unspecified',None),('unit','m',['m','m2','m3','No.']),('rate',0.,None),('currency','INR',None),('specification','',None)])
            if v:
                from .boq import rate_key
                settings=copy.deepcopy(self.mw.document.extensions.get('workflow',{}));settings.setdefault('rate_library',{})[rate_key(v['description'],v['material'],v['unit'])]=v;data.save(self.mw.document,settings,'Rate library item')
        button(self,l,'Add / replace rate library item',rate)
        button(self,l,'Apply rate library to BOQ',lambda:data.apply_rates(self.mw.document))
        from .boq_ui import dialog
        button(self,l,'BOQ report / locate sources / export',lambda:dialog(self.mw))
        def transfer(importing):
            settings=copy.deepcopy(self.mw.document.extensions.get('workflow',{}))
            if importing:
                p,_=QFileDialog.getOpenFileName(self,'Import takeoff / rate library','','JSON (*.json)')
                if p:
                    value=json.loads(Path(p).read_text());data.validate(value)
                    if set(value)-{'takeoff_rules','rate_library'}:raise ValueError('Choose a quantity / rate library file')
                    settings.update(value);data.save(self.mw.document,settings,'Import quantity library');refresh()
            else:
                p,_=QFileDialog.getSaveFileName(self,'Export quantity library','quantity-library.json','JSON (*.json)')
                if p:
                    from .native_io import atomic_write
                    value={k:settings[k] for k in ('takeoff_rules','rate_library') if k in settings}
                    atomic_write(p,lambda f:Path(f).write_text(json.dumps(value,indent=2,ensure_ascii=False),encoding='utf-8'))
        bar=QHBoxLayout();l.addLayout(bar);button(self,bar,'Import quantity library',lambda:transfer(True));button(self,bar,'Export quantity library',lambda:transfer(False));refresh()

    def ai(self):
        l=self.pages[8];self.note(l,'Drafting chat supports offline instructions and an optional configured model. Every proposal is validated, previewed and applied as one Undo step. The review shows geometry and quantity changes and can export a plan. Try: array selected 2 by 3 spacing 100,200.')
        def chat():
            from .drafting_chat import show as toggle
            self.accept();toggle(self.mw)
        button(self,l,'Open drafting chat',chat)
        def load():
            from .automation import review_proposal,validate_actions
            p,_=QFileDialog.getOpenFileName(self,'Load drafting plan','','JSON (*.json)')
            if p:
                value=json.loads(Path(p).read_text());review_proposal(self.mw,validate_actions(value['actions']),'Review imported drafting plan')
        button(self,l,'Load and review drafting plan',load)
        l.addStretch()


def show(mw,index=0):
    dialog=WorkflowDialog(mw,index);return dialog.exec()


def commands(mw):
    names={'WORKFLOW':0,'DIAGNOSTICS':0,'PERFORMANCE':1,'DWGREPORT':2,'PRECISIONEDIT':3,'XREFMANAGER':4,'SHEETLIBRARY':5,'RECOVERYHISTORY':6,'TAKEOFFRULES':7,'AIDRAFT':8}
    result={name:(lambda i=index:show(mw,i)) for name,index in names.items()}
    def join():
        from .precision_edit import join
        e=join(mw.document,mw.canvas.selected_entities);mw.canvas.selected_entities=[e];mw.refresh_document_ui()
    def split():
        from .precision_edit import break_at
        if len(mw.canvas.selected_entities)!=1:raise ValueError('Select a single line or arc')
        v,ok=QInputDialog.getDouble(mw,'Break curve','Fraction',.5,.000001,.999999,6)
        if ok:break_at(mw.document,mw.canvas.selected_entities[0],v);mw.refresh_document_ui()
    from .xref_manager import bind_gui
    result.update(JOIN=join,BREAKAT=split,BIND=lambda:bind_gui(mw),BINDMISSING=lambda:bind_gui(mw,True));return result
