"""Compact professional workflows with reviewed edits and readable reports."""
import copy,json
from pathlib import Path
from PyQt6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QListWidget,QStackedWidget,QWidget,QLabel,QFileDialog,QInputDialog,QPlainTextEdit
from .workflow_ui import button,form,table,fill

PAGES=['Regional cache','GPU geometry','Associations','Block variants','Revision comparison','Sheet viewports','Architecture checks','BOQ changes','Room planner','Packages / releases']


def report(parent,title,value):
    d=QDialog(parent);d.setWindowTitle(title);d.resize(850,520);root=QVBoxLayout(d)
    if isinstance(value,list):rows=value
    else:
        rows=value.get('rows',[]) if isinstance(value.get('rows'),list) else None
        if rows is None:rows=[{'Item':k,'Value':v} for k,v in value.items()]
        else:
            note=QLabel(' · '.join(str(value[k]) for k in ('currency','note') if k in value));note.setWordWrap(True);root.addWidget(note)
    if rows:
        columns=list(dict.fromkeys(k for r in rows for k in r));t=table(root,columns,'pro_report')
        fill(t,[[json.dumps(r.get(k,''),ensure_ascii=False) if isinstance(r.get(k),(list,dict)) else str(r.get(k,'')) for k in columns] for r in rows])
    else:root.addWidget(QLabel('No issues or entries.'))
    def export():
        from .native_io import atomic_write
        path,_=QFileDialog.getSaveFileName(d,'Export full report','report.json','JSON (*.json)')
        if path:atomic_write(path,lambda p:Path(p).write_text(json.dumps(value,indent=2,ensure_ascii=False),encoding='utf-8'))
    button(d,root,'Export full report',export);button(d,root,'Close',d.accept);d.exec()


def load_copy(parent):
    path,_=QFileDialog.getOpenFileName(parent,'Choose previous drawing','','Drawings (*.pycad *.dxf *.dwg)')
    if not path:return None
    if path.lower().endswith('.dwg'):
        from .dwg_ui import load_dwg
        return load_dwg(parent,path)
    if path.lower().endswith('.dxf'):
        from .import_ui import load_dxf
        return load_dxf(parent,path)
    from .native_io import load_project
    return load_project(path)


class ProDialog(QDialog):
    def __init__(self,mw,index=0):
        super().__init__(mw);self.mw=mw;self.setObjectName('professional_workflows');self.setWindowTitle('PY.cad — professional workflows');self.resize(940,620)
        root=QVBoxLayout(self);row=QHBoxLayout();root.addLayout(row,1);self.list=QListWidget();self.list.addItems(PAGES);self.list.setMaximumWidth(190);row.addWidget(self.list);self.stack=QStackedWidget();row.addWidget(self.stack,1);self.pages=[]
        for name in PAGES:w=QWidget();l=QVBoxLayout(w);self.stack.addWidget(w);self.pages.append(l)
        for method in (self.regional,self.gpu,self.associations,self.blocks,self.revisions,self.viewports,self.architecture,self.boq,self.planner,self.packages):method()
        self.list.currentRowChanged.connect(self.stack.setCurrentIndex);self.list.setCurrentRow(index);button(self,root,'Close',self.accept)
    def note(self,l,text):w=QLabel(text);w.setWordWrap(True);l.addWidget(w)
    def refresh(self):self.mw.refresh_document_ui()
    def regional(self):
        l=self.pages[0];self.note(l,'Create a disk-backed inspection cache, then load only the visible region. Initial import/cache creation still needs RAM; editing stays in the original drawing. Definitions are stored once; inspection omits project links and underlays.')
        def create():
            path,_=QFileDialog.getSaveFileName(self,'Create regional cache','drawing.pycaddb','Regional cache (*.pycaddb)')
            if path:
                from .workflow_jobs import run
                result=run(self,self.mw.document,'regional_cache',artifact=path)
                if result:report(self,'Regional cache created',dict(path=path,objects=result['entities']))
        def open_cache():
            path,_=QFileDialog.getOpenFileName(self,'Open regional cache','','Regional cache (*.pycaddb)')
            if path:
                from .paged_drawing import viewer
                viewer(self,path)
        button(self,l,'Create cache from current drawing',create);button(self,l,'Open regional inspection cache',open_cache);l.addStretch()
    def gpu(self):
        l=self.pages[1];self.note(l,'Experimental cached vertex buffers for eligible continuous thin linework, curves and convex solid hatches. Other content uses QPainter. Enable GPU display and the Direct path, then benchmark this drawing on your graphics system.')
        def enable():
            self.mw.graphics.set_drawing_path('direct');self.mw.canvas.gpu_geometry_enabled=True;self.mw.canvas._gpu_geometry_error=None;self.mw.canvas.viewport().update()
        def disable():self.mw.canvas.gpu_geometry_enabled=False;self.mw.canvas.viewport().update()
        def benchmark():
            from .gpu_geometry import benchmark
            report(self,'CPU / GPU drawing benchmark',benchmark(self.mw.canvas))
        button(self,l,'CPU / GPU display settings',self.mw.graphics_dialog);button(self,l,'Enable cached GPU geometry for this session',enable);button(self,l,'Disable cached GPU geometry',disable);button(self,l,'Benchmark with pixel readback',benchmark)
        button(self,l,'Buffer statistics',lambda:report(self,'GPU geometry',dict(stats=getattr(self.mw.canvas,'gpu_geometry_stats',{}),error=getattr(self.mw.canvas,'_gpu_geometry_error',None))));l.addStretch()
    def associations(self):
        l=self.pages[2];self.note(l,'Dimension anchors: p1, p2, center, point, east, arc start/end, or polyline vertex:0 etc. Hatch sources must be closed polylines/circles; select the outer boundary first. Broken sources retain the last valid geometry.')
        def dimension():
            from .geometry import DimensionEntity
            from .associations import bind_dimension
            selected=self.mw.canvas.selected_entities;dims=[e for e in selected if type(e) is DimensionEntity];sources=[e for e in selected if type(e) is not DimensionEntity]
            if len(dims)!=1 or not 1<=len(sources)<=2:raise ValueError('Select one linear/radial dimension and one or two sources')
            v=form(self,'Dimension anchors',[('First anchor','p1',None),('Second anchor','p2',None)])
            if v:bind_dimension(self.mw.document,dims[0],[sources[0].id,sources[-1].id],[v['First anchor'],v['Second anchor']]);self.refresh()
        def hatch():
            from .geometry import HatchEntity
            from .associations import bind_hatch
            selected=self.mw.canvas.selected_entities;h=[e for e in selected if isinstance(e,HatchEntity)];sources=[e.id for e in selected if not isinstance(e,HatchEntity)]
            if len(h)!=1 or not sources:raise ValueError('Select one hatch and its closed boundaries, outer first')
            bind_hatch(self.mw.document,h[0],sources);self.refresh()
        def detach():
            from .associations import detach
            detach(self.mw.document,[e.id for e in self.mw.canvas.selected_entities]);self.refresh()
        button(self,l,'Link selected dimension',dimension);button(self,l,'Link selected hatch',hatch);button(self,l,'Detach selected links',detach);button(self,l,'Inspect broken associations',lambda:report(self,'Association status',getattr(self.mw.document,'association_issues',[])));l.addStretch()
    def blocks(self):
        l=self.pages[3];self.note(l,'Define visibility by layer and threshold-based X/Y stretch states. States are ordinary derived blocks, not AutoCAD dynamic blocks. Refresh a state after changing its base. Straight lines/polylines and text can stretch; curved content uses the block editor.')
        def define():
            from .block_variants import define
            from .pro_data import settings
            names=[n for n,b in self.mw.document.blocks.items() if not b.is_xref and n not in settings(self.mw.document).get('variants',{})]
            if not names:raise ValueError('Create a local base block first')
            v=form(self,'Block state',[('Base',names[0],names),('State','Wide',None),('Hidden layers','',None),('Stretch X','0',None),('Stretch Y','0',None),('Threshold X','0',None),('Threshold Y','0',None)])
            if v:define(self.mw.document,v['Base'],v['State'],[s.strip() for s in v['Hidden layers'].split(',') if s.strip()],*[float(v[k]) for k in ('Stretch X','Stretch Y','Threshold X','Threshold Y')]);self.refresh()
        def apply():
            from .block_variants import apply
            from .pro_data import settings
            names=list(settings(self.mw.document).get('variants',{}));items=self.mw.canvas.selected_entities
            if len(items)!=1 or not names:raise ValueError('Select one block and define a matching state')
            name,ok=QInputDialog.getItem(self,'Block state','State',names,0,False)
            if ok:apply(self.mw.document,items[0],name);self.refresh()
        def symbol():
            from .block_variants import symbol
            v=form(self,'Reusable symbol',[('Kind','Door',['Door','Window']),('Width',900.,None),('Height',2100.,None)])
            if v:name=symbol(self.mw.document,v['Kind'],v['Width'],v['Height']);self.refresh();report(self,'Symbol created',dict(block=name,next='Place with INSERT; edit attributes with ATTEDIT'))
        button(self,l,'Define / refresh block state',define);button(self,l,'Apply state to selected block',apply);button(self,l,'Create door / window symbol',symbol)
        from .smart_blocks import attribute_dialog,schedule_dialog
        button(self,l,'Define block attributes',lambda:attribute_dialog(self.mw,True));button(self,l,'Edit block attributes',lambda:attribute_dialog(self.mw));button(self,l,'Live block schedule',lambda:schedule_dialog(self.mw));l.addStretch()
    def revisions(self):
        l=self.pages[4];self.note(l,'Native-ID comparison highlights added, removed and modified objects, including definition changes. Independent DWG/DXF imports may use different IDs; use native revisions for reliable matching.')
        def compare():
            before=load_copy(self)
            if before is None:return
            from .revisions import compare
            from .canvas import CadCanvas
            from .native_io import document_to_dict,document_from_dict
            value=compare(before,self.mw.document);d=QDialog(self);d.setWindowTitle('Prior revision / current drawing');d.resize(1100,650);root=QVBoxLayout(d);root.addWidget(QLabel(f"Added {len(value['added'])} · Removed {len(value['removed'])} · Modified {len(value['changed'])}"));row=QHBoxLayout();root.addLayout(row,1);canvases=[]
            for doc,ids,color in [(before,value['removed']+value['changed'],'#e76f51'),(self.mw.document,value['added']+value['changed'],'#2ec4b6')]:
                clone=document_from_dict(document_to_dict(doc));c=CadCanvas(clone);c._comparison_color=color
                for e in clone.entities:e.color=color if e.id in ids else '#68717c'
                row.addWidget(c);canvases.append(c)
            button(d,root,'Detailed comparison report',lambda:report(d,'Revision changes',value));button(d,root,'Close',d.accept);d.show()
            for c in canvases:c.zoom_extents()
            d.exec()
        button(self,l,'Compare current drawing with prior revision',compare);l.addStretch()
    def viewports(self):
        l=self.pages[5];self.note(l,'Select a paper viewport. Set rotation, annotation size multiplier and optional polygon clip in paper coordinates. Existing per-viewport layer visibility/colors are retained. These native settings also apply to PDF output.')
        def edit():
            from .viewport_plus import config,set_config
            doc=self.mw.document;space=doc.current_space;layout=doc.layouts.get(space);vp=self.mw.canvas.selected_viewport
            if layout is None or vp not in layout.viewports:raise ValueError('Select a paper viewport')
            index=layout.viewports.index(vp);old=config(doc,space,index);v=form(self,'Viewport settings',[('Rotation',str(old['rotation']),None),('Annotation multiplier',old['annotation_scale'],None),('Paper clip x,y; x,y','; '.join(','.join(map(str,p)) for p in old['clip']),None)])
            if v:points=[[float(n) for n in pair.split(',')] for pair in v['Paper clip x,y; x,y'].split(';') if pair.strip()];set_config(doc,space,index,float(v['Rotation']),points,v['Annotation multiplier']);self.refresh()
        from .layers_plus import viewport_override_dialog
        button(self,l,'Edit selected viewport settings',edit);button(self,l,'Viewport layer visibility / colors',lambda:viewport_override_dialog(self.mw));l.addStretch()
    def architecture(self):
        l=self.pages[6];self.note(l,'Check small wall endpoint gaps and overlapping hosted openings. Gap alignment proposes wall position, angle and length changes for review, validates the result, and applies with one Undo. Existing mitered joins, openings and linked rooms remain available.')
        def check():
            from .architecture_review import inspect
            tolerance,ok=QInputDialog.getDouble(self,'Architecture checks','Gap tolerance in drawing units',1,.000001,1e8,6)
            if ok:report(self,'Architecture issues',inspect(self.mw.document,tolerance))
        def align():
            from .architecture_review import gap_actions
            from .automation import review_proposal
            tolerance,ok=QInputDialog.getDouble(self,'Close small gaps','Maximum gap in drawing units',1,.000001,1e8,6)
            if ok:
                actions=gap_actions(self.mw.document,tolerance)
                if not actions:report(self,'Wall gaps',dict(message='No eligible gaps'));return
                review_proposal(self.mw,actions,'Review wall endpoint alignment');self.refresh()
        from .architecture import architecture_dialog
        from .smart_blocks import schedule_dialog
        button(self,l,'Check wall gaps / hosted openings',check);button(self,l,'Preview endpoint alignment',align);button(self,l,'Walls / openings / rooms',lambda:architecture_dialog(self.mw));button(self,l,'Linked schedules',lambda:schedule_dialog(self.mw));l.addStretch()
    def boq(self):
        l=self.pages[7];self.note(l,'Review source-linked deductions, wastage and quantity changes between revisions. Per-source waste replaces global waste for that source. The adjusted report is separate from the base BOQ; calculations retain source IDs and methods.')
        def adjust():
            from .pro_data import settings,save_section
            from .revisions import quantity_rows
            from .native_io import document_from_dict,document_to_dict
            items=self.mw.canvas.selected_entities
            if len(items)!=1:raise ValueError('Select one measured source')
            key=items[0].id;old=settings(self.mw.document).get('quantity_adjustments',{}).get(key,dict(deduction=0.,waste_percent=0.,reason='Project adjustment'));v=form(self,'Quantity adjustment',[(k,value,None) for k,value in old.items()])
            if v:
                values=copy.deepcopy(settings(self.mw.document).get('quantity_adjustments',{}));values[key]=v;trial=document_from_dict(document_to_dict(self.mw.document));save_section(trial,'quantity_adjustments',values,'Validate adjustment');rows=quantity_rows(trial)['rows']
                if not any(r['source_id']==key for r in rows):raise ValueError('Source has no measurable BOQ row')
                save_section(self.mw.document,'quantity_adjustments',values,'Quantity adjustment');self.refresh()
        def current():
            from .revisions import quantity_rows
            report(self,'Adjusted quantities',quantity_rows(self.mw.document))
        def delta():
            before=load_copy(self)
            if before is not None:
                from .revisions import quantity_delta
                report(self,'Quantity changes',quantity_delta(before,self.mw.document))
        button(self,l,'Selected source deduction / wastage',adjust);button(self,l,'Adjusted quantities and calculations',current);button(self,l,'Compare quantities with prior drawing',delta);l.addStretch()
    def planner(self):
        l=self.pages[8];self.note(l,'Millimetre room modules: walls, optional hosted doors, room labels and linked dimensions. Each row is name, width, depth. Answer the remaining questions before visual review. Modules are separated by a gap; this does not solve a whole-building layout.')
        text=QPlainTextEdit('Office, 6000, 4000\nStore, 3000, 3000');text.setObjectName('planner_rooms');l.addWidget(text)
        def preview():
            from .room_planner import plan
            from .automation import review_proposal
            if self.mw.document.units!='mm':raise ValueError('Planner currently requires millimetre drawing units')
            v=form(self,'Planning questions',[('Start X','0',None),('Start Y','0',None),('Separation',500.,None),('Wall thickness',200.,None),('Wall height',3000.,None),('Add doors',True,None),('Linked dimensions',True,None)])
            if v:
                rooms=[]
                for line in text.toPlainText().splitlines():
                    if not line.strip():continue
                    parts=[p.strip() for p in line.split(',')]
                    if len(parts)!=3:raise ValueError('Enter room name, width, depth on every row')
                    rooms.append(dict(name=parts[0],width=float(parts[1]),depth=float(parts[2])))
                actions=plan(rooms,(float(v['Start X']),float(v['Start Y'])),v['Separation'],v['Wall thickness'],v['Wall height'],v['Add doors'],v['Linked dimensions']);review_proposal(self.mw,actions,'Review rooms, hosted doors and dimensions');self.refresh()
        from .drafting_chat import show
        button(self,l,'Answer planning questions / preview',preview);button(self,l,'Open drafting chat',lambda:show(self.mw));l.addStretch()
    def packages(self):
        l=self.pages[9];self.note(l,'Bundle the native drawing and available xrefs with hashes; native underlays stay embedded. Fonts are optional and explicitly chosen. Portable release staging checks an independent SHA256, keeps older versions, and never replaces the running installation.')
        def pack():
            from .project_bundle import pack
            path,_=QFileDialog.getSaveFileName(self,'Package project','project.pycadpack','Project bundle (*.pycadpack)')
            if path:
                fonts,_=QFileDialog.getOpenFileNames(self,'Optional redistributable fonts — Cancel to omit','','Fonts (*.ttf *.otf *.shx)');report(self,'Project packaged',pack(self.mw.document,path,fonts))
        def unpack():
            from .project_bundle import unpack,load_fonts
            path,_=QFileDialog.getOpenFileName(self,'Extract project bundle','','Project bundle (*.pycadpack)')
            if not path:return
            parent=QFileDialog.getExistingDirectory(self,'Parent for a new project folder')
            if parent:
                name,ok=QInputDialog.getText(self,'Project folder','New folder name',text=Path(path).stem)
                if ok:
                    from .project_bundle import safe_name
                    safe_name(name)
                    if len(Path(name).parts)!=1:raise ValueError('Use a simple new folder name')
                    drawing=unpack(path,Path(parent)/name);fonts=load_fonts(drawing.parent);report(self,'Project extracted',dict(drawing=str(drawing),fonts=fonts))
        def root():
            value=QFileDialog.getExistingDirectory(self,'Portable release storage');return Path(value) if value else None
        def stage():
            from .release_manager import stage,select
            archive,_=QFileDialog.getOpenFileName(self,'Complete release ZIP','','ZIP (*.zip)')
            if not archive:return
            sha,ok=QInputDialog.getText(self,'Release integrity','SHA256 from the release publisher')
            if ok:
                folder=root()
                if folder:version=stage(archive,sha.strip(),folder);target=select(folder,version);report(self,'Portable release staged',dict(version=version,path=str(target),next='Close PY.cad, then run start.sh or start_windows.bat from this directory. Previous versions are retained.'))
        def rollback():
            from .release_manager import rollback
            folder=root()
            if folder:report(self,'Previous release selected',dict(path=str(rollback(folder)),next='Close PY.cad and launch the selected version. Separate user data is unchanged.'))
        button(self,l,'Package drawing and dependencies',pack);button(self,l,'Verify / extract project package',unpack);button(self,l,'Verify and stage portable release',stage);button(self,l,'Select previous portable release',rollback);l.addStretch()


def show(mw,index=0):return ProDialog(mw,index).exec()


def commands(mw):
    names=['REGIONALCACHE','GPUBUFFERS','ASSOCIATIONS','BLOCKVARIANTS','REVISIONS','VIEWPORTPLUS','ARCHREVIEW','BOQCHANGES','ROOMPLANNER','PROJECTPACKAGE']
    return {'PROWORKFLOW':lambda:show(mw),**{name:(lambda i=i:show(mw,i)) for i,name in enumerate(names)}}
