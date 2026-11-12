import copy,json
import pytest
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QDialog,QApplication,QPushButton
from pycad.document import Document,AddEntityCommand
from pycad.geometry import Point,LineEntity,TextEntity,DimensionEntity,BlockDefinition,BlockReferenceEntity
from pycad.native_io import document_to_dict,document_from_dict,save_project,load_project
from pycad import production as p

def drawing():
 d=Document();d.units='mm';d.entities=[LineEntity(Point(0,0),Point(100,100))];d.create_layout('Plan');d.create_layout('Details');return d

def test_sheet_order_number_issue_roundtrip_and_undo(qapp,tmp_path):
 d=drawing();p.save_set(d,'Tender',['Details','Plan']);p.renumber(d,['Details','Plan'],'A',10)
 assert d.extensions['sheets']['Details']['number']=='A010'
 index=d.undo_stack.index();p.issue_set(d,'Tender','B','Issue for review','2026-11-01');assert d.undo_stack.index()==index+1
 assert d.extensions['sheets']['Plan']['revision']=='B'
 path=tmp_path/'project.pycad';save_project(d,path);loaded=load_project(path)
 assert p.data(loaded)['sheet_sets']['Tender']['spaces']==['Details','Plan']
 assert p.data(loaded)['sheet_sets']['Tender']['issues'][0]['note']=='Issue for review'
 d.undo_stack.undo();assert not p.data(d)['sheet_sets']['Tender']['issues'];assert d.extensions['sheets']['Plan']['revision']!='B'
 d.undo_stack.redo();assert d.extensions['sheets']['Plan']['revision']=='B'

@pytest.mark.parametrize('spaces',[[],['Plan','Plan'],['Missing']])
def test_invalid_sheet_set_does_not_mutate(qapp,spaces):
 d=drawing();before=document_to_dict(d)
 with pytest.raises(ValueError):p.save_set(d,'Set',spaces)
 assert document_to_dict(d)==before

def test_deleted_sheet_set_requires_repair(qapp):
 d=drawing();p.save_set(d,'Set',['Plan']);d.edit_layout('Plan')
 before=document_to_dict(d)
 with pytest.raises(ValueError):p.issue_set(d,'Set','B')
 assert before==document_to_dict(d)

def test_compare_overlay_retains_old_nested_blocks_without_mutation(qapp):
 a=drawing();line=LineEntity(Point(0,0),Point(10,0));a.blocks['Child']=BlockDefinition('Child',[line]);a.blocks['Parent']=BlockDefinition('Parent',[BlockReferenceEntity('Child',Point(0,0))]);a.entities=[BlockReferenceEntity('Parent',Point(0,0))]
 b=document_from_dict(document_to_dict(a));b.blocks['Child'].entities[0].p2.x=20
 old,new=document_to_dict(a),document_to_dict(b);overlay,result=p.comparison_overlay(a,b)
 assert result['changed']==[b.entities[0].id]
 assert overlay.blocks['OLD_Child'].entities[0].p2.x==10 and overlay.blocks['NEW_Child'].entities[0].p2.x==20
 assert len(overlay.entities)==2 and overlay.entities[0].color=='#e74c3c'
 assert document_to_dict(a)==old and document_to_dict(b)==new

def test_compare_added_removed_changed_context(qapp):
 a=drawing();unchanged=LineEntity(Point(2,2),Point(5,5));a.entities.append(unchanged);b=document_from_dict(document_to_dict(a));b.entities.pop(0);added=TextEntity(Point(0,0),'New');b.entities.append(added)
 overlay,result=p.comparison_overlay(a,b)
 assert result['removed']==[a.entities[0].id] and result['added']==[added.id] and len(overlay.entities)==3
 assert sum(e.color=='#7f8c8d' for e in overlay.entities)==1
 b.units='m'
 with pytest.raises(ValueError):p.comparison_overlay(a,b)

def test_quantity_freshness_rate_geometry_and_native_roundtrip(qapp,tmp_path):
 from pycad.boq import tag,set_rates
 d=drawing();line=d.entities[0];tag(d,[line.id],'Line','Steel','Length',1)
 snapshot=p.refresh_quantities(d);assert p.quantity_status(d)=='Current' and snapshot['rows'][0]['source_id']==line.id
 path=tmp_path/'takeoff.pycad';save_project(d,path);d=load_project(path);assert p.quantity_status(d)=='Current'
 d.entities[0].p2.x+=1;assert p.quantity_status(d).startswith('Outdated');p.refresh_quantities(d);assert p.quantity_status(d)=='Current'
 set_rates(d,{},'USD',5);assert p.quantity_status(d).startswith('Outdated')
 p.refresh_quantities(d);d.undo_stack.undo();assert p.quantity_status(d).startswith('Outdated')

def test_spacing_parallel_dimensions_and_undo(qapp):
 d=Document();a=DimensionEntity(Point(0,0),Point(10,0),Point(5,2));b=DimensionEntity(Point(0,0),Point(15,0),Point(7,3));c=DimensionEntity(Point(0,0),Point(20,0),Point(10,9));d.entities=[c,a,b]
 before=document_to_dict(d);p.space_dimensions(d,[c,a,b],5);assert [a.dim_point.y,b.dim_point.y,c.dim_point.y]==[2,7,12]
 d.undo_stack.undo();assert document_to_dict(d)==before
 b.p2=Point(10,10)
 with pytest.raises(ValueError):p.space_dimensions(d,[a,b],5)

def test_paper_text_height_units_and_undo(qapp):
 d=Document();d.units='m';a=TextEntity(Point(0,0),'Label',height=1);d.entities=[a];p.text_paper_height(d,[a],2.5,100);assert a.height==.25
 d.undo_stack.undo();assert a.height==1
 with pytest.raises(ValueError):p.text_paper_height(d,[a],0,100)

def test_schema16_and_old15_readable(qapp):
 d=drawing();p.save_set(d,'Set',['Plan']);value=document_to_dict(d);assert value['schema_version']==17;assert p.data(document_from_dict(value))==p.data(d)
 old=document_to_dict(Document());old['schema_version']=15;assert not document_from_dict(old).entities
 value['extensions']['production']['sheet_sets']['Set']['spaces'].append('Plan')
 with pytest.raises(ValueError):document_from_dict(value)

def test_production_hub_and_commands(main_window):
 from pycad.production_ui import ProductionDialog,commands,NAMES
 from pycad.command_palette import entries
 d=ProductionDialog(main_window);assert d.stack.count()==7
 for i in range(7):d.list.setCurrentRow(i);QApplication.processEvents();assert d.stack.currentIndex()==i
 assert set(NAMES)<=set(main_window.command_names)
 assert any(r['label']=='PRODUCTION' for r in entries(main_window));d.close()

def test_staged_pdf_preview_and_preset_worker(main_window,tmp_path):
 from pycad.production_ui import staged_pdf,pdf_preview
 from pycad.sheets import DEFAULT_PRESET
 from pypdf import PdfReader
 main_window.document.units='mm';main_window.document.entities=[LineEntity(Point(0,0),Point(100,100))]
 preset={**DEFAULT_PRESET,'page_width':420.,'page_height':297.,'monochrome':False}
 path=staged_pdf(main_window,['Model'],preset,tmp_path);pdf=PdfReader(path);assert float(pdf.pages[0].mediabox.width)==pytest.approx(420/25.4*72,abs=.6)
 QTimer.singleShot(100,lambda:[w.accept() for w in QApplication.topLevelWidgets() if isinstance(w,QDialog) and w.windowTitle().startswith('Publication preview')]);pdf_preview(main_window,path)

def test_ai_overlay_cancel_then_apply_one_undo(main_window):
 from pycad.automation import review_proposal
 mw=main_window;before=document_to_dict(mw.document);actions=[dict(op='line',start=[0,0],end=[10,0])]
 def cancel():
  for w in QApplication.topLevelWidgets():
   if isinstance(w,QDialog) and w.windowTitle()=='Review proposed changes':
    next(b for b in w.findChildren(QPushButton) if b.text()=='Show changes overlay').click();w.reject()
 QTimer.singleShot(150,cancel);assert not review_proposal(mw,actions);assert document_to_dict(mw.document)==before
 QTimer.singleShot(150,lambda:[w.accept() for w in QApplication.topLevelWidgets() if isinstance(w,QDialog) and w.windowTitle()=='Review proposed changes']);assert review_proposal(mw,actions)
 assert len(mw.document.entities)==1;mw.document.undo_stack.undo();assert document_to_dict(mw.document)==before

def test_architecture_hosted_openings_live_area_schedule(qapp,tmp_path):
 from pycad.architecture import create_wall,create_opening,create_room
 from pycad.geometry import RectangleEntity
 from pycad.productivity import create_table,schedule_cells
 d=Document();d.units='mm';wall=create_wall(d,Point(0,0),Point(6000,0),200,3000);door=create_opening(d,wall,1000,900,2100,'door','D01',0);window=create_opening(d,wall,3000,1200,1200,'window','W01',900)
 assert d.extensions['architecture'][door.id]['type']=='door' and d.extensions['architecture'][window.id]['type']=='window'
 boundary=RectangleEntity(Point(0,0),Point(6000,4000));d.entities.append(boundary);create_room(d,boundary,'Office','101','Paint');cells=schedule_cells(d,'Rooms');assert float(cells[1][2])==24
 create_table(d,'Areas',cells,schedule='Rooms');boundary.points[1].x=8000;boundary.points[2].x=8000;d.sync_associative();assert float(schedule_cells(d,'Rooms')[1][2])==32
 assert any(e.kind=='TEXT' and e.text=='32' for e in d.blocks['Areas'].entities)
 path=tmp_path/'rooms.pycad';save_project(d,path);loaded=load_project(path);assert float(schedule_cells(loaded,'Rooms')[1][2])==32

def test_style_only_revision_is_highlighted(qapp):
 a=drawing();a.entities=[TextEntity(Point(0,0),'Label')];b=document_from_dict(document_to_dict(a));b.textstyles['Standard']['font_family']='Serif'
 result=p.comparison(a,b);assert result['changed']==[a.entities[0].id] and result['settings_changed']

@pytest.mark.parametrize('mutate',[lambda r:r['sheet_sets']['Set'].update(spaces=[[]]),lambda r:r.update(quantity_snapshot={}),lambda r:r['sheet_sets']['Set'].update(issues=[dict(revision='A',date='bad',note='')])])
def test_invalid_production_native_data_rejected(qapp,mutate):
 d=drawing();p.save_set(d,'Set',['Plan']);value=document_to_dict(d);mutate(value['extensions']['production'])
 with pytest.raises(ValueError):document_from_dict(value)

def test_dimension_paper_size_does_not_change_other_dimensions(qapp):
 d=Document();d.units='mm';a=DimensionEntity(Point(0,0),Point(10,0),Point(5,2));b=DimensionEntity(Point(0,0),Point(10,0),Point(5,4));d.entities=[a,b];before=document_to_dict(d)
 p.dimension_paper_size(d,[a],3.5,100);assert a.style_name!=b.style_name and d.dimstyles[a.style_name]['text_height']==3.5 and d.dimstyles[a.style_name]['scale']==100
 d.undo_stack.undo();assert document_to_dict(d)==before

@pytest.mark.parametrize('name',['Model','All layouts'])
def test_reserved_sheet_set_name_rejected(qapp,name):
 d=drawing();before=document_to_dict(d)
 with pytest.raises(ValueError):p.save_set(d,name,['Plan'])
 assert document_to_dict(d)==before
