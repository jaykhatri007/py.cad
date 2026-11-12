"""Compact review-first UI for the eight drawing productivity workflows."""
import copy,json
from pathlib import Path
from PyQt6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QListWidget,QStackedWidget,QWidget,QLabel,QFileDialog,QInputDialog,QDialogButtonBox,QTableWidget,QTableWidgetItem,QAbstractItemView,QCheckBox)
from .workflow_ui import button,form
from .pro_ui import report
from . import productivity as p
PAGES=['Hatch areas','Vector PDF','Drawing tables','Office standards','Survey / coordinates','Block parameters','BOQ overlay','Drawing explanations']
NAMES=['HATCHAREAS','PDFIMPORT','DRAWTABLE','STANDARDSCHECK','SURVEY','BLOCKPARAMETERS','BOQOVERLAY','AIEXPLAIN']

def apply_entities(mw,entities,label):
    from .native_io import document_to_dict,entity_to_dict
    from .validation import validate_payload
    from .document import AddEntityCommand
    candidate=document_to_dict(mw.document);candidate['entities'].extend(entity_to_dict(e) for e in entities);validate_payload(candidate)
    mw.document.undo_stack.beginMacro(label)
    try:
        for e in entities:mw.document.undo_stack.push(AddEntityCommand(mw.document,e,label))
    finally:mw.document.undo_stack.endMacro()
    mw.refresh_document_ui()

def review_entities(parent,mw,entities,details,label):
    if not entities:report(parent,label,details);return False
    from .document import Document
    from .canvas import CadCanvas
    d=QDialog(parent);d.setWindowTitle(label+' — review');d.resize(900,600);l=QVBoxLayout(d);note=QLabel(json.dumps(details,indent=2,ensure_ascii=False));note.setWordWrap(True);l.addWidget(note)
    doc=Document();doc.entities=copy.deepcopy(entities);doc.sync_associative();canvas=CadCanvas(doc);l.addWidget(canvas,1);buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);buttons.button(QDialogButtonBox.StandardButton.Ok).setText('Add to drawing');buttons.accepted.connect(d.accept);buttons.rejected.connect(d.reject);l.addWidget(buttons);d.show();canvas.zoom_extents()
    if d.exec()!=QDialog.DialogCode.Accepted:return False
    apply_entities(mw,entities,label);return True

def revise_hatch_areas(mw,tool):
    d=QDialog(mw);d.setWindowTitle('Staged hatch areas');d.resize(440,350);l=QVBoxLayout(d);items=QListWidget();items.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection);l.addWidget(items)
    for i,a in enumerate(tool.areas):items.addItem(f"Area {i+1} — {len(a['boundary'])} vertices / {len(a['holes'])} islands")
    removed=set()
    def remove():
        for item in items.selectedItems():removed.add(items.row(item));item.setHidden(True)
    button(d,l,'Remove selected areas',remove);combined=QCheckBox('One combined even-odd hatch');combined.setChecked(tool.combined);l.addWidget(combined);l.addWidget(QLabel('Combined fills store outlines without source links.'));button(d,l,'Apply selection',d.accept);button(d,l,'Cancel',d.reject)
    if d.exec()==QDialog.DialogCode.Accepted:tool.areas[:]=[a for i,a in enumerate(tool.areas) if i not in removed];tool.combined=combined.isChecked();tool._current();mw.canvas.viewport().update()

def edit_cells(parent,cells):
    d=QDialog(parent);d.setWindowTitle('Table values and formulas');d.resize(800,480);l=QVBoxLayout(d);l.addWidget(QLabel('A1 references; =B2*C2; =SUM(C2:C10); MIN, MAX and AVERAGE.'))
    t=QTableWidget(len(cells),len(cells[0]));l.addWidget(t)
    def headers():
        names=[]
        for c in range(t.columnCount()):
            value=c+1;name=''
            while value:value,r=divmod(value-1,26);name=chr(65+r)+name
            names.append(name)
        t.setHorizontalHeaderLabels(names)
    headers()
    for y,row in enumerate(cells):
        for x,value in enumerate(row):t.setItem(y,x,QTableWidgetItem(value))
    def values():return [[t.item(y,x).text() if t.item(y,x) else '' for x in range(t.columnCount())] for y in range(t.rowCount())]
    def add_column():t.insertColumn(t.columnCount());headers()
    row=QHBoxLayout();l.addLayout(row);button(d,row,'Add row',lambda:t.insertRow(t.rowCount()));button(d,row,'Add column',add_column);button(d,row,'Calculate / validate',lambda:report(d,'Calculated values',dict(rows=[{str(i+1):v for i,v in enumerate(row)} for row in p.calculate(values())])))
    result=[]
    def accept():p.calculate(values());result.extend(values());d.accept()
    button(d,l,'Apply cells',accept);button(d,l,'Cancel',d.reject);return result if d.exec()==QDialog.DialogCode.Accepted else None

class ProductivityDialog(QDialog):
    def __init__(self,mw,index=0):
        super().__init__(mw);self.mw=mw;self.setObjectName('productivity_workflows');self.setWindowTitle('PY.cad — drawing tools');self.resize(900,570);root=QVBoxLayout(self);row=QHBoxLayout();root.addLayout(row,1);self.list=QListWidget();self.list.addItems(PAGES);self.list.setMaximumWidth(190);row.addWidget(self.list);self.stack=QStackedWidget();row.addWidget(self.stack,1);self.pages=[]
        for name in PAGES:w=QWidget();l=QVBoxLayout(w);self.stack.addWidget(w);self.pages.append(l)
        for method in (self.hatch,self.pdf,self.tables,self.standards,self.survey,self.parameters,self.boq,self.explanations):method()
        self.list.currentRowChanged.connect(self.stack.setCurrentIndex);self.list.setCurrentRow(index);button(self,root,'Close',self.accept)
    @property
    def doc(self):return self.mw.document
    def note(self,l,text):label=QLabel(text);label.setWordWrap(True);l.addWidget(label)
    def choose(self,key):
        names=list(p.state(self.doc,key))
        if not names:raise ValueError('Create a '+key+' record first')
        name,ok=QInputDialog.getItem(self,key,'Name',names,0,False);return name if ok else None
    def hatch(self):
        l=self.pages[0];self.note(l,'Select closed circles/polylines before opening. Remove unwanted boundaries, choose settings, and create separate linked hatches or a combined fill. Pick-point HATCH also supports A to manage individual areas, C to combine, Separate, U to undo a pick, and Enter to apply.')
        def selected():
            from .geometry import CircleEntity,PolylineEntity
            from .hatch_ui import HatchDialog
            from .hatch_areas import from_selected,apply
            entities=list(self.mw.canvas.selected_entities)
            if not entities or any(not (isinstance(e,CircleEntity) or isinstance(e,PolylineEntity) and e.closed) for e in entities):raise ValueError('Select closed circles / polylines')
            d=QDialog(self);d.setWindowTitle('Boundary selection');root=QVBoxLayout(d);items=QListWidget();items.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection);root.addWidget(items)
            for e in entities:items.addItem(f'{e.kind} · {e.layer} · {e.id}')
            removed=set()
            def remove():
                for item in items.selectedItems():removed.add(items.row(item));item.setHidden(True)
            button(d,root,'Remove selected boundaries',remove);combined=QCheckBox('One combined hatch (source links disabled)');root.addWidget(combined);button(d,root,'Choose settings',d.accept);button(d,root,'Cancel',d.reject)
            if d.exec()!=QDialog.DialogCode.Accepted:return
            settings=HatchDialog(self)
            if settings.exec()!=QDialog.DialogCode.Accepted:return
            hatches=from_selected(self.doc,[e for i,e in enumerate(entities) if i not in removed],settings.values(),combined.isChecked(),settings.associative.isChecked());apply(self.doc,hatches);self.mw.refresh_document_ui()
        button(self,l,'Hatch selected boundaries…',selected);button(self,l,'Pick enclosed areas…',lambda:self.mw.run_ribbon_command('HATCH'));l.addStretch()
    def pdf(self):
        l=self.pages[1];self.note(l,'Editable PDF vector paths, one page at a time, with calibration and a cancellable parser. Curves are approximated. Text, images, Form XObjects and clipping are reported limitations. Use PDFATTACH for the full page appearance.')
        def load():
            path,_=QFileDialog.getOpenFileName(self,'Vector PDF','','PDF (*.pdf)')
            if not path:return
            from .units import UNIT_MM
            v=form(self,'PDF calibration',[('Page','1',None),('Units per PDF point',25.4/72/UNIT_MM.get(self.doc.units,1),None),('Known drawing length',0.,None),('Measured PDF point length',0.,None),('Insert X','0',None),('Insert Y','0',None),('Curve segments','24',None),('Cleanup tolerance',.000001,None)])
            if not v:return
            if bool(v['Known drawing length'])!=bool(v['Measured PDF point length']):raise ValueError('Provide both calibration lengths or leave both zero')
            scale=v['Known drawing length']/v['Measured PDF point length'] if v['Known drawing length'] else v['Units per PDF point']
            from .workflow_jobs import run,fingerprint
            from .native_io import entity_from_dict
            value=run(self,self.doc,'pdf_vectors',parameters=dict(path=path,page_number=int(v['Page']),scale=scale,offset=[float(v['Insert X']),float(v['Insert Y'])],curve_steps=int(v['Curve segments']),cleanup_tolerance=v['Cleanup tolerance']))
            if value is None:return
            if fingerprint(self.doc)!=value['fingerprint']:raise ValueError('Drawing changed during import; run again')
            review_entities(self,self.mw,[entity_from_dict(e) for e in value['entities']],value['details'],'Import PDF vectors')
        button(self,l,'Import / calibrate PDF…',load);l.addStretch()
    def tables(self):
        l=self.pages[2];self.note(l,'Formula cells generate ordinary line/text blocks. BOQ and block schedules update after drawing edits. CSV reload is explicit and reviewable. Native files preserve formulas and links; DWG/DXF retains the generated geometry.')
        def create(kind=''):
            cells=[['Item','Quantity','Rate','Total'],['Part','2','100','=B2*C2'],['Total','','','=SUM(D2:D2)']];path=''
            if kind=='CSV':
                path,_=QFileDialog.getOpenFileName(self,'Linked CSV','','CSV (*.csv)')
                if not path:return
                cells=p.read_csv(path)
            elif kind:cells=p.schedule_cells(self.doc,kind)
            if kind not in ('BOQ','Blocks'):
                cells=edit_cells(self,cells)
                if cells is None:return
            v=form(self,'Place table',[('Name','Table_'+str(len(p.state(self.doc,'tables'))+1),None),('X','0',None),('Y','0',None),('Column width',35.,None),('Row height',8.,None)])
            if v:p.create_table(self.doc,v['Name'],cells,(float(v['X']),float(v['Y'])),v['Column width'],v['Row height'],path,kind if kind in ('BOQ','Blocks') else '');self.mw.refresh_document_ui()
        def edit(reload=False):
            name=self.choose('tables')
            if not name:return
            r=copy.deepcopy(p.state(self.doc,'tables')[name])
            if r['schedule']:raise ValueError('Edit the BOQ / block sources for this live schedule')
            if reload:
                if not r['csv_path']:raise ValueError('No linked CSV')
                from .xref import reference_path
                r['cells']=p.read_csv(reference_path(self.doc,r['csv_path']))
            cells=edit_cells(self,r['cells'])
            if cells is not None:r['cells']=cells;p.set_table(self.doc,name,r);self.mw.refresh_document_ui()
        button(self,l,'Create formula table…',create);button(self,l,'Create / link CSV…',lambda:create('CSV'));button(self,l,'Insert live BOQ schedule…',lambda:create('BOQ'));button(self,l,'Insert live block schedule…',lambda:create('Blocks'));button(self,l,'Edit table cells…',edit);button(self,l,'Reload linked CSV for review…',lambda:edit(True));l.addStretch()
    def standards(self):
        l=self.pages[3];self.note(l,'Office standards use JSON: allowed layer names, colors, lineweights, text height, dimension styles and tolerance. Checks report deviations and object IDs without changing geometry.')
        def capture():p.save(self.doc,'standards',{'office':p.office_standard(self.doc)},'Capture office standard')
        def load():
            path,_=QFileDialog.getOpenFileName(self,'Office standard','','JSON (*.json)')
            if path:p.save(self.doc,'standards',{'office':json.loads(Path(path).read_text())},'Import office standard')
        def export():
            r=p.state(self.doc,'standards').get('office')
            if r is None:raise ValueError('Capture or import a standard first')
            path,_=QFileDialog.getSaveFileName(self,'Office standard','office-standard.json','JSON (*.json)')
            if path:
                from .native_io import atomic_write
                atomic_write(path,lambda dest:Path(dest).write_text(json.dumps(r,indent=2)))
        def check():
            r=p.state(self.doc,'standards').get('office')
            if r is None:raise ValueError('Capture or import a standard first')
            report(self,'Standard deviations',p.check_standard(self.doc,r))
        button(self,l,'Capture current drawing standard',capture);button(self,l,'Import standard…',load);button(self,l,'Export / edit standard JSON…',export);button(self,l,'Check drawing',check);l.addStretch()
    def survey(self):
        l=self.pages[4];self.note(l,'Headerless CSV: ID,Easting,Northing[,Elevation], or ID,Longitude,Latitude[,Elevation]. Supports local affine grids and WGS84 UTM. Scale = survey units per drawing unit: metres with mm drawings use 0.001. Elevation is labeled metadata; import is 2D.')
        def configure():
            r=p.state(self.doc,'survey').get('drawing',p.survey_config());v=form(self,'Survey coordinates',[('CRS',r['crs'],['Local','WGS84 UTM']),('UTM zone',str(r['zone']),None),('Northern hemisphere',r['north'],None),('Origin Easting',str(r['origin_e']),None),('Origin Northing',str(r['origin_n']),None),('Scale',r['scale'],None),('Rotation',str(r['rotation']),None)])
            if v:p.save(self.doc,'survey',{'drawing':dict(crs=v['CRS'],zone=int(v['UTM zone']),north=v['Northern hemisphere'],origin_e=float(v['Origin Easting']),origin_n=float(v['Origin Northing']),scale=v['Scale'],rotation=float(v['Rotation']))},'Survey coordinate system')
        def load(geo=False):
            cfg=p.state(self.doc,'survey').get('drawing')
            if cfg is None:raise ValueError('Configure coordinates first')
            path,_=QFileDialog.getOpenFileName(self,'Survey CSV','','CSV (*.csv)')
            if not path:return
            height,ok=QInputDialog.getDouble(self,'Survey labels','Height in drawing units',2.5,.000001,1e8,6)
            if ok:
                entities=p.survey_entities(p.read_csv(path),cfg,geo,height);review_entities(self,self.mw,entities,dict(points=len(entities)//2,coordinate_system=cfg),'Import survey points')
        def selected():
            from .geometry import PointEntity
            entities=self.mw.canvas.selected_entities
            if not entities or any(not isinstance(e,PointEntity) for e in entities):raise ValueError('Select POINT objects')
            return entities,p.state(self.doc,'survey').get('drawing',p.survey_config())
        def bearing():
            entities,cfg=selected()
            if len(entities)!=2:raise ValueError('Select two POINT objects in from/to order')
            report(self,'Bearing / distance',p.bearing(entities[0].point,entities[1].point,cfg))
        def labels():
            from .geometry import TextEntity,Point
            entities,cfg=selected();out=[]
            for e in entities:
                east,north=p.to_survey(e.point,cfg);out.append(TextEntity(Point(e.point.x,e.point.y),f'E {east:.3f} N {north:.3f}'))
            apply_entities(self.mw,out,'Coordinate labels')
        button(self,l,'Configure coordinates…',configure);button(self,l,'Import Easting / Northing CSV…',load);button(self,l,'Import longitude / latitude CSV…',lambda:load(True));button(self,l,'Label selected points',labels);button(self,l,'Bearing / distance',bearing);l.addStretch()
    def parameters(self):
        l=self.pages[5];self.note(l,'Named width / height and rotation states for ordinary local blocks. Thresholds define which coordinates stretch. Straight lines, straight polylines, text and attributes are supported. Base or parameter changes regenerate state instances. Native states export as ordinary blocks, not AutoCAD dynamic blocks.')
        def define(existing=False):
            names=[n for n,b in self.doc.blocks.items() if not b.is_xref and n not in p.state(self.doc,'parameters') and n not in p.state(self.doc,'tables')]
            if not names:raise ValueError('Create a local base block first')
            name=self.choose('parameters') if existing else 'Param_'+str(len(p.state(self.doc,'parameters'))+1)
            if not name:return
            r=p.state(self.doc,'parameters').get(name,dict(base=names[0],width_name='Width',height_name='Height',base_width=100.,base_height=100.,width=100.,height=100.,rotation=0.,threshold_x=0.,threshold_y=0.))
            v=form(self,'Block parameters',[('State name',name,None),('Base',r['base'],names),('Width name',r['width_name'],None),('Height name',r['height_name'],None)]+[(k,str(r[k]),None) for k in ('base_width','base_height','width','height','rotation','threshold_x','threshold_y')])
            if not v:return
            if existing and name!=v['State name']:raise ValueError('Keep the state name when editing')
            rule=dict(base=v['Base'],width_name=v['Width name'],height_name=v['Height name'],**{k:float(v[k]) for k in ('base_width','base_height','width','height','rotation','threshold_x','threshold_y')});p.define_parameters(self.doc,v['State name'],rule);self.mw.refresh_document_ui()
        def apply():
            from .document import SetAttrCommand
            name=self.choose('parameters')
            if not name:return
            r=p.state(self.doc,'parameters')[name];entities=self.mw.canvas.selected_entities
            if not entities or any(e.kind!='INSERT' or e.block_name not in (name,r['base']) or not self.doc.is_editable(e) for e in entities):raise ValueError('Select editable matching base/state block instances')
            self.doc.undo_stack.beginMacro('Apply parameters')
            try:
                for e in entities:self.doc.undo_stack.push(SetAttrCommand(self.doc,e,'block_name',e.block_name,name,'Block parameters'))
            finally:self.doc.undo_stack.endMacro()
            self.mw.refresh_document_ui()
        button(self,l,'Define named parameters…',define);button(self,l,'Edit parameters / regenerate…',lambda:define(True));button(self,l,'Apply to selected blocks…',apply);button(self,l,'Regeneration issues',lambda:report(self,'Issues',getattr(self.doc,'productivity_issues',[])));l.addStretch()
    def boq(self):
        l=self.pages[6];self.note(l,'Green = measured / priced, amber = measured / unpriced, red = unmeasured. Session overlay refreshes after edits. Selection highlight takes priority; saved object colors and PDF output are unchanged.')
        def enable():p.overlay(self.doc);self.mw.canvas.boq_overlay_enabled=True;self.mw.canvas.viewport().update()
        def disable():self.mw.canvas.boq_overlay_enabled=False;self.mw.canvas.viewport().update()
        def inspect():
            r=p.overlay(self.doc);report(self,'BOQ coverage',dict(rows=[dict(source_id=k,status=v) for k,v in r['status'].items()],warnings=r['warnings']))
        button(self,l,'Enable quantity overlay',enable);button(self,l,'Disable quantity overlay',disable);button(self,l,'Coverage / missing rates report',inspect);l.addStretch()
    def explanations(self):
        l=self.pages[7];self.note(l,'Grounded offline explanations use selected geometry and actual BOQ arithmetic. No drawing is sent anywhere. Drafting chat also accepts “explain selected” and “explain quantities”; its existing optional provider mode receives the same evidence.')
        def selected():report(self,'Drawing explanation',p.explain(self.doc,self.mw.canvas.selected_entities))
        def failure():
            error=getattr(self.mw,'last_command_failure','')
            if not error:error,ok=QInputDialog.getText(self,'Command failure','Exact error');error=error if ok else ''
            if error:report(self,'Command failure',p.explain(self.doc,self.mw.canvas.selected_entities,failure=error))
        from .drafting_chat import show
        button(self,l,'Explain selected objects / quantities',selected);button(self,l,'Explain command failure',failure);button(self,l,'Open drafting chat',lambda:show(self.mw));l.addStretch()

def show(mw,index=0):return ProductivityDialog(mw,index).exec()
def commands(mw):return {'DRAWINGTOOLS':lambda:show(mw),**{name:(lambda i=i:show(mw,i)) for i,name in enumerate(NAMES)}}
