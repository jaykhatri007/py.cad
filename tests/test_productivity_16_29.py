import copy,json,math
import pytest
from PyQt6.QtCore import Qt,QTimer
from PyQt6.QtGui import QImage,QPainter,QColor
from PyQt6.QtWidgets import QApplication,QProgressDialog,QTableWidget
from pycad import productivity as p
from pycad.document import Document,AddEntityCommand,SetAttrCommand
from pycad.geometry import Point,LineEntity,PolylineEntity,CircleEntity,TextEntity,BlockDefinition,BlockReferenceEntity
from pycad.native_io import document_to_dict,document_from_dict,save_project,load_project

def rect(x=0,y=0,w=10):return PolylineEntity([Point(x,y),Point(x+w,y),Point(x+w,y+w),Point(x,y+w)],closed=True)
def rule():return dict(base='Base',width_name='Width',height_name='Height',base_width=10.,base_height=10.,width=20.,height=10.,rotation=0.,threshold_x=0.,threshold_y=0.)

@pytest.mark.parametrize('raw,expected',[('=A1+B1',5),('=SUM(A1:B1)',5),('=AVERAGE(A1:B1)',2.5),('=MAX(A1:B1)-MIN(A1:B1)',1),('=A1**2',4),('=-A1/B1',-2/3)])
def test_formulas(raw,expected):assert p.calculate([['2','3',raw]])[0][2]==expected

@pytest.mark.parametrize('cells',[[['=A1']],[['=B1','=A1']],[['=Z9']],[['=1/0']],[['=__import__("os")']],[['=2**999']],[['=SUM()']],[['=A1.__class__']],[['=SUM(A2:A1)']],[['text','=A1+1']]])
def test_formula_rejects(cells):
 with pytest.raises(ValueError):p.calculate(cells)

def test_table_undo_native_and_csv(main_window,tmp_path):
 d=main_window.document;before=document_to_dict(d);p.create_table(d,'Costs',[['2','3','=A1*B1']],(-10,4));assert d.undo_stack.index()==1 and any(e.kind=='TEXT' and e.text=='6' for e in d.blocks['Costs'].entities)
 path=tmp_path/'cost.pycad';save_project(d,path);assert p.state(load_project(path),'tables')['Costs']['cells'][0][2]=='=A1*B1'
 r=copy.deepcopy(p.state(d,'tables')['Costs']);r['cells'][0][0]='4';p.set_table(d,'Costs',r);assert any(e.kind=='TEXT' and e.text=='12' for e in d.blocks['Costs'].entities)
 d.undo_stack.undo();assert any(e.kind=='TEXT' and e.text=='6' for e in d.blocks['Costs'].entities);d.undo_stack.undo();assert document_to_dict(d)==before
 source=tmp_path/'data.csv';source.write_text('\ufeffA,B\n1,2\n3\n');assert p.read_csv(source)==[['A','B'],['1','2'],['3','']]

def test_live_block_schedule(main_window):
 d=main_window.document;d.blocks['Base']=BlockDefinition('Base',[LineEntity(Point(0,0),Point(1,0))]);p.create_table(d,'Count',[['Block','Count']],schedule='Blocks');d.undo_stack.push(AddEntityCommand(d,BlockReferenceEntity('Base',Point(0,0))));assert any(e.kind=='TEXT' and e.text=='Base' for e in d.blocks['Count'].entities)
 d.undo_stack.undo();assert not any(e.kind=='TEXT' and e.text=='Base' for e in d.blocks['Count'].entities)

def test_live_boq_no_recursive_sync(main_window,tmp_path):
 from pycad.boq import tag
 d=main_window.document;line=LineEntity(Point(0,0),Point(2000,0));d.entities=[line];d.sync_associative();tag(d,[line.id],'Measured line',measurement='Length');p.create_table(d,'Quantities',[['Description','Unit','Quantity','Rate','Cost']],schedule='BOQ');assert any(e.kind=='TEXT' and e.text=='2' for e in d.blocks['Quantities'].entities)
 d.undo_stack.push(SetAttrCommand(d,line,'p2',line.p2,Point(3000,0),'Extend'));assert any(e.kind=='TEXT' and e.text=='3' for e in d.blocks['Quantities'].entities);d.undo_stack.undo();assert any(e.kind=='TEXT' and e.text=='2' for e in d.blocks['Quantities'].entities)
 save_project(d,tmp_path/'boq.pycad');assert not load_project(tmp_path/'boq.pycad').productivity_issues

def test_parameters_regenerate_undo_native(main_window,tmp_path):
 d=main_window.document;line=LineEntity(Point(0,0),Point(10,0));d.blocks['Base']=BlockDefinition('Base',[line]);p.define_parameters(d,'Wide',rule());assert d.blocks['Wide'].entities[0].p2.x==20
 d.undo_stack.push(AddEntityCommand(d,BlockReferenceEntity('Wide',Point(100,100))));insert=d.entities[-1];assert insert.resolved_entities[0].p2.x==120
 ids=[e.id for e in d.blocks['Wide'].entities];d.sync_associative();assert [e.id for e in d.blocks['Wide'].entities]==ids
 d.undo_stack.push(SetAttrCommand(d,line,'p2',line.p2,Point(15,0),'Base edit'));assert insert.resolved_entities[0].p2.x==125;d.undo_stack.undo();assert insert.resolved_entities[0].p2.x==120
 r=rule();r.update(width=30,rotation=90);p.define_parameters(d,'Wide',r);assert d.blocks['Wide'].entities[0].p2.y==pytest.approx(30);save_project(d,tmp_path/'p.pycad');assert load_project(tmp_path/'p.pycad').blocks['Wide'].entities[0].p2.y==pytest.approx(30)
 d.undo_stack.undo();assert d.blocks['Wide'].entities[0].p2.x==20

def test_attributes_follow_parameters(main_window):
 d=main_window.document;spec=dict(tag='NAME',prompt='Name',default='A',position=[10,0],height=2.5,rotation=0.,visible=True,layer='0',style_name='Standard');d.blocks['Base']=BlockDefinition('Base',[LineEntity(Point(0,0),Point(10,0))],attributes=[spec]);r=rule();r['rotation']=90;p.define_parameters(d,'Wide',r);assert d.blocks['Wide'].attributes[0]['position']==pytest.approx([0,20])

def test_invalid_parameter_atomic(main_window):
 d=main_window.document;d.blocks['Base']=BlockDefinition('Base',[CircleEntity(Point(10,0),2)]);before=document_to_dict(d)
 with pytest.raises(ValueError):p.define_parameters(d,'Wide',rule())
 assert document_to_dict(d)==before

def test_standards_readonly(main_window):
 d=main_window.document;r=p.office_standard(d);assert p.check_standard(d,r)==[];d.entities=[TextEntity(Point(0,0),'Wrong',height=5)];before=document_to_dict(d);assert p.check_standard(d,r)[0]['kind']=='Text height';assert document_to_dict(d)==before
 r['layers']['0']['color']='#ff0000';assert any(v['kind']=='color' for v in p.check_standard(d,r))

def test_survey_roundtrip_utm_bearing():
 cfg=p.survey_config();cfg.update(origin_e=500000,origin_n=2100000,scale=.001,rotation=30);point=p.to_drawing(500001,2100002,cfg);assert p.to_survey(point,cfg)==pytest.approx((500001,2100002))
 result=p.bearing(p.to_drawing(500000,2100000,cfg),p.to_drawing(500001,2100000,cfg),cfg);assert result['distance']==pytest.approx(1) and result['azimuth_degrees']==pytest.approx(90)
 assert p.utm(75,0,43,True)==pytest.approx((500000,0));e,n=p.utm(3,-45,31,False);assert e==pytest.approx(500000) and n==pytest.approx(5017049.6,abs=.1)

@pytest.mark.parametrize('args',[(75,85,43,True),(75,-20,43,True),(20,20,43,True),(75,0,0,True)])
def test_invalid_survey(args):
 with pytest.raises(ValueError):p.utm(*args)

def test_survey_import_atomic(main_window):
 cfg=p.survey_config();cfg.update(crs='WGS84 UTM',zone=43,origin_e=500000,scale=.001);out=p.survey_entities([['P1','75','0','12.4']],cfg,True);assert len(out)==2 and '12.400' in out[1].text
 from pycad.productivity_ui import apply_entities
 before=document_to_dict(main_window.document);apply_entities(main_window,out,'Survey');main_window.document.undo_stack.undo();assert document_to_dict(main_window.document)==before
 with pytest.raises(ValueError):p.survey_entities([['A','1','2'],['A','2','3']],cfg)

def test_hatch_separate_combined_islands(main_window,tmp_path):
 from pycad.hatch_areas import from_selected,apply
 from pycad.hatching import render_loops
 d=main_window.document;out=from_selected(d,[rect(),rect(30),rect(2,2,2)],dict(pattern='SOLID'));assert len(out)==2 and len(out[0].holes)==1
 h=from_selected(d,[rect(0,0,20),rect(3,3,10),rect(5,5,2),rect(40,0,20)],dict(pattern='SOLID'),True)[0];assert h.loop_flags==[1,16,0,1] and len(render_loops(h))==4;h.island_style='ignore';assert len(render_loops(h))==2;h.island_style='outer';assert len(render_loops(h))==3
 apply(d,[h]);save_project(d,tmp_path/'h.pycad');assert load_project(tmp_path/'h.pycad').entities[0].boundary_mode=='evenodd';d.undo_stack.undo();assert not d.entities

@pytest.mark.parametrize('entities',[[rect(),rect(5)],[rect(),rect(10)],[rect(),rect()],[LineEntity(Point(0,0),Point(1,0))]])
def test_bad_hatch(entities):
 from pycad.hatch_areas import from_selected
 with pytest.raises(ValueError):from_selected(Document(),entities,dict(pattern='SOLID'),True)

def test_pick_combined(main_window,monkeypatch):
 from tests.test_hatch_multi_16_28 import mock_regions
 mock_regions(monkeypatch);mw=main_window;mw.set_tool('HATCH',hatch_configured=True);tool=mw.current_tool;tool.on_click(5,5,'',1);tool.on_click(35,5,'',1);tool.on_text_input('C');tool.on_key(Qt.Key.Key_Return);assert len(mw.document.entities)==1 and mw.document.entities[0].boundary_mode=='evenodd'

def make_pdf(path,content):
 from pypdf import PdfWriter
 from pypdf.generic import DecodedStreamObject,NameObject
 writer=PdfWriter();page=writer.add_blank_page(200,200);stream=DecodedStreamObject();stream.set_data(content);page[NameObject('/Contents')]=writer._add_object(stream)
 with path.open('wb') as f:writer.write(f)

def test_pdf_transform_cleanup_calibration(tmp_path):
 from pycad.pdf_vectors import import_page
 path=tmp_path/'sample.pdf';make_pdf(path,b'q 2 0 0 2 10 20 cm 1 0 0 RG 0 0 m 10 0 l S Q 0 0 m 0 10 l S 0 0 m 0 10 l S 1 1 2 2 re f');out,r=import_page(path,scale=3,offset=(1,2));assert len(out)==3 and r['removed_degenerate_or_duplicate']==1 and out[0].points[0].as_tuple()==(31,62) and out[0].points[1].as_tuple()==(91,62) and out[0].color=='#ff0000' and r['warnings']
 with pytest.raises(ValueError):import_page(path,2)

def test_pdf_curves_warnings(tmp_path):
 from pycad.pdf_vectors import import_page
 path=tmp_path/'curve.pdf';make_pdf(path,b'0 0 m 0 10 10 10 10 0 c S 0 0 1 1 re W n BT (Hi) Tj ET /X Do');out,r=import_page(path,curve_steps=8);assert len(out[0].points)==9 and len(r['warnings'])==3

def test_pdf_worker_cancel(main_window,tmp_path):
 from pycad.workflow_jobs import run
 path=tmp_path/'worker.pdf';make_pdf(path,b'0 0 m 20 0 l S');params=dict(path=str(path),page_number=1,scale=1,offset=[0,0],curve_steps=8,cleanup_tolerance=1e-7)
 result=run(main_window,main_window.document,'pdf_vectors',parameters=params);assert result['details']['objects']==1
 def cancel():
  for w in QApplication.topLevelWidgets():
   if isinstance(w,QProgressDialog):w.cancel()
 QTimer.singleShot(20,cancel);before=document_to_dict(main_window.document);assert run(main_window,main_window.document,'pdf_vectors',parameters=params) is None and document_to_dict(main_window.document)==before

def test_overlay_cache_chat_no_mutation(main_window):
 from pycad.boq import rate_key
 from pycad.drafting_chat import offline,context_for
 d=main_window.document;e=LineEntity(Point(0,0),Point(1000,0));d.entities=[e];d.sync_associative();assert p.overlay(d)['status'][e.id]=='Unmeasured'
 d.extensions['boq']={'tags':{e.id:dict(description='Line',material='Steel',measurement='Length',factor=1)},'rates':{rate_key('Line','Steel','m'):10}};d.sync_associative();assert p.overlay(d)['status'][e.id]=='Measured / priced';assert 'Gross' in offline(d,'explain quantities',[e.id])['message'];assert context_for(d,[e.id])['selected_explanations']['rows'][0]['source_id']==e.id
 c=main_window.canvas;c.zoom_extents();c.drawing_path='cached';im=QImage(c.viewport().size(),QImage.Format.Format_ARGB32);im.fill(QColor('white'));painter=QPainter(im);before=document_to_dict(d);c._draw_cached_entities(painter);key=c._drawing_image_key;c.boq_overlay_enabled=True;c._draw_cached_entities(painter);assert c._drawing_image_key!=key and c._boq_overlay['colors'][e.id]=='#45b882';c.boq_overlay_enabled=False;c._draw_cached_entities(painter);assert c._drawing_image_key==key and document_to_dict(d)==before;painter.end()

def test_copy_remap_units(main_window):
 from pycad.feature_interop import selection_extensions,remap_extensions,merge_extensions,scale_extensions
 d=main_window.document;p.create_table(d,'Costs',[['2','=A1*3']]);d.blocks['Base']=BlockDefinition('Base',[LineEntity(Point(0,0),Point(10,0))]);p.define_parameters(d,'Wide',rule());ext=selection_extensions(d,{e.id for e in d.entities},{'Costs','Wide','Base'});assert set(ext['productivity'])=={'tables','parameters'}
 mapped=remap_extensions(ext,{},dict(Costs='Costs2',Wide='Wide2',Base='Base2'));assert mapped['productivity']['parameters']['Wide2']['base']=='Base2';assert set(merge_extensions(d.extensions,mapped)['productivity']['tables'])=={'Costs','Costs2'}
 cfg=p.survey_config();cfg['scale']=.001;d.extensions['productivity']['survey']={'drawing':cfg};scale_extensions(d,.001);assert p.state(d,'parameters')['Wide']['width']==.02 and p.state(d,'survey')['drawing']['scale']==1

def test_csv_package(main_window,tmp_path):
 from pycad.project_bundle import pack,unpack
 from pycad.xref import reference_path
 source=tmp_path/'quantities.csv';source.write_text('2,3,=A1*B1\n');p.create_table(main_window.document,'CSV',p.read_csv(source),csv_path=str(source));archive=tmp_path/'project.pycadpack';pack(main_window.document,archive);doc=load_project(unpack(archive,tmp_path/'unpacked'));assert reference_path(doc,p.state(doc,'tables')['CSV']['csv_path']).read_text()==source.read_text()

def test_ui_schema_theme(main_window,qapp):
 from pycad.productivity_ui import ProductivityDialog,commands,NAMES
 dialog=ProductivityDialog(main_window);assert dialog.stack.count()==8 and set(NAMES)<=commands(main_window).keys();dialog.close();assert main_window._theme_filter.parent() is qapp
 assert document_to_dict(main_window.document)['schema_version']==17;old=document_to_dict(main_window.document);old['schema_version']=14;assert not document_from_dict(old).entities
 assert p.explain(main_window.document,[],failure='Hatch island crosses boundary')['next_check']

def test_oversized_table_atomic(main_window):
 before=document_to_dict(main_window.document)
 with pytest.raises(ValueError):p.create_table(main_window.document,'Large',[['1','2']],cell_width=1e12)
 assert document_to_dict(main_window.document)==before

def test_cell_editor_letters(main_window):
 from pycad.productivity_ui import edit_cells
 names=[]
 def inspect():
  d=QApplication.activeModalWidget();t=d.findChild(QTableWidget);names.extend(t.horizontalHeaderItem(i).text() for i in range(t.columnCount()));d.reject()
 QTimer.singleShot(10,inspect);assert edit_cells(main_window,[['1','2','=A1+B1']]) is None and names==['A','B','C']
