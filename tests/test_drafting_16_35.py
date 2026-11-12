import copy,hashlib,json,math
import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLineEdit,QTableWidget,QComboBox
from pycad.document import Document
from pycad.geometry import Point,LineEntity,ArcEntity,CircleEntity,PolylineEntity,RectangleEntity,HatchEntity,TextEntity,BlockDefinition,BlockReferenceEntity
from pycad.native_io import document_to_dict,document_from_dict,save_project
from pycad import drafting as d,editing

def poly():return PolylineEntity([Point(0,0),Point(5,0),Point(10,0),Point(10,10)],bulges=[0,0,.5,0],width=2)

def test_width_roundtrip_bbox_scale_pick_and_legacy(qapp):
 from pycad.geom_ops import distance_to_entity
 doc=Document();e=poly();doc.entities=[e];value=document_to_dict(doc);assert value['schema_version']==17
 restored=document_from_dict(value).entities[0];assert restored.width==2 and restored.clone().width==2
 assert distance_to_entity(Point(3,.8),restored)==0
 box=restored.bbox();assert box[0]==-1
 restored.scale_from(Point(0,0),3);assert restored.width==6
 value['schema_version']=16;value['entities'][0]['data'].pop('width');assert document_from_dict(value).entities[0].width==0
 for width in [-1,float('inf'),True]:
  with pytest.raises(ValueError):PolylineEntity([Point(0,0),Point(1,0)],width=width)


def test_width_dxf_rectangle_and_segment_preservation(qapp,tmp_path):
 from pycad.dxf_io import export_dxf,import_dxf
 doc=Document();e=RectangleEntity(Point(0,0),Point(10,10),width=2.5);doc.entities=[e];path=tmp_path/'wide.dxf';export_dxf(doc,str(path));loaded=import_dxf(str(path));assert loaded.entities[0].width==2.5
 assert document_from_dict(document_to_dict(doc)).entities[0].width==2.5
 editing.apply(doc,editing.segment_plan(doc,e,0,'Insert midpoint'));assert doc.entities[0].width==2.5


def test_reverse_arc_geometry_and_simplify_undo(qapp):
 from pycad.precision import polyline_measure
 doc=Document();e=poly();doc.entities=[e];before=document_to_dict(doc);length=polyline_measure(e)[0]
 editing.apply(doc,d.polyline_plan(doc,[e],'Reverse'));r=doc.entities[0];assert polyline_measure(r)[0]==pytest.approx(length) and r.width==2
 editing.apply(doc,d.polyline_plan(doc,[r],'Reverse'));assert [(p.x,p.y) for p in doc.entities[0].points]==[(p.x,p.y) for p in e.points] and doc.entities[0].bulges==e.bulges
 doc.undo_stack.undo();doc.undo_stack.undo();assert document_to_dict(doc)==before
 editing.apply(doc,d.polyline_plan(doc,[e],'Simplify',.01));assert len(doc.entities[0].points)==3 and .5 in doc.entities[0].bulges
 doc.undo_stack.undo();assert document_to_dict(doc)==before

@pytest.mark.parametrize('operation',['Close','Open','Uniform width'])
def test_polyline_operations(qapp,operation):
 doc=Document();e=poly();doc.entities=[e];editing.apply(doc,d.polyline_plan(doc,[e],operation,7));r=doc.entities[0]
 assert r.width==(7 if operation=='Uniform width' else 2)
 assert r.closed==(operation=='Close')


def test_join_added_objects_and_atomic_undo(qapp):
 doc=Document();a=LineEntity(Point(0,0),Point(5,0));b=LineEntity(Point(5,0),Point(10,0));doc.entities=[a,b];before=document_to_dict(doc);p=d.polyline_plan(doc,[a,b],'Join',.01);assert document_to_dict(doc)==before
 editing.apply(doc,p);assert len(doc.entities)==1 and isinstance(doc.entities[0],PolylineEntity)
 doc.undo_stack.undo();assert document_to_dict(doc)==before;doc.undo_stack.redo();assert len(doc.entities)==1
 a=poly();b=LineEntity(Point(10,10),Point(20,10));doc.entities=[a,b]
 with pytest.raises(ValueError,match='width'):d.polyline_plan(doc,[a,b],'Join',.01)


def test_reviewed_multi_cutter_trim_fence_extend(qapp):
 doc=Document();cutters=[LineEntity(Point(3,-10),Point(3,10)),LineEntity(Point(7,-10),Point(7,10))];targets=[LineEntity(Point(0,y),Point(10,y)) for y in (0,2)];doc.entities=cutters+targets;before=document_to_dict(doc)
 hits=d.fence_hits(doc,cutters,[Point(5,-1),Point(5,3)]);assert len(hits)==2
 p=d.trim_plan(doc,cutters,hits);assert document_to_dict(doc)==before;editing.apply(doc,p);assert len(doc.entities)==6
 assert sorted((e.p1.x,e.p2.x) for e in doc.entities if e.id not in {q.id for q in cutters})==[(0,3),(0,3),(7,10),(7,10)]
 doc.undo_stack.undo();assert document_to_dict(doc)==before
 doc.entities=[cutters[0],LineEntity(Point(0,0),Point(1,0))];target=doc.entities[-1];editing.apply(doc,d.trim_plan(doc,[cutters[0]],[(target.id,Point(1,0))],True));assert doc.entities[-1].p2.x==3


def test_stale_and_protected_trim(qapp):
 doc=Document();a=LineEntity(Point(3,-2),Point(3,2));b=LineEntity(Point(0,0),Point(10,0));doc.entities=[a,b]
 proposal=d.trim_plan(doc,[a],[(b.id,Point(1,0))]);b.p2.x=11
 with pytest.raises(ValueError):editing.apply(doc,proposal)
 doc.extensions['groups']={'group':[a.id,b.id]}
 with pytest.raises(ValueError):d.trim_plan(doc,[a],[(b.id,Point(1,0))])


def hatch():return HatchEntity([Point(0,0),Point(20,0),Point(20,20),Point(0,20)],holes=[[Point(5,5),Point(10,5),Point(10,10),Point(5,10)]])

def test_hatch_bulk_preserves_holes_links_recreate_undo(qapp):
 doc=Document();h=hatch();h2=hatch();h2.translate(30,0);doc.entities=[h,h2];before=document_to_dict(doc)
 editing.apply(doc,d.hatch_settings_plan(doc,[h,h2],dict(pattern='ANSI31',pattern_scale=2,angle=30)));assert all(q.pattern=='ANSI31' and len(q.holes)==1 for q in doc.entities)
 doc.undo_stack.undo();assert document_to_dict(doc)==before
 editing.apply(doc,d.hatch_boundaries_plan(doc,[h,h2]));assert len(doc.entities)==6 and all(q.closed for q in doc.entities[2:]);doc.undo_stack.undo();assert document_to_dict(doc)==before
 with pytest.raises(ValueError):d.hatch_settings_plan(doc,[h],dict(pattern_scale=-1))


def test_gap_scan_and_search_replace_literal_undo(qapp):
 doc=Document();a=LineEntity(Point(0,0),Point(5,0));b=LineEntity(Point(5.001,0),Point(10,0));text=TextEntity(Point(0,0),'Office office offices');doc.entities=[a,b,text];before=document_to_dict(doc);assert len(d.gaps([a,b],.01))==1
 rows=d.search(doc,'office',['Text'],whole=True);assert len(rows)==1;editing.apply(doc,d.replace_plan(doc,rows,'office',r'Room\1',whole=True));assert doc.entities[-1].text==r'Room\1 Room\1 offices'
 doc.undo_stack.undo();assert document_to_dict(doc)==before
 with pytest.raises(ValueError):d.replace_plan(doc,d.search(doc,'0',['Layer']),'0','NEW')


def test_templates_independent_settings_sheets_titleblocks(qapp,tmp_path):
 from pycad.layout import Layout
 from pycad.sheets import title_block
 doc=Document();doc.units='m';doc.entities=[poly()];doc.layouts['Plan']=Layout('Plan');title_block(doc,'Plan',project='My project',title='Plan',number='A1',revision='A',author='Jay');before=document_to_dict(doc)
 path=tmp_path/'template.pycad';d.save_template(doc,path);digest=hashlib.sha256(path.read_bytes()).hexdigest();loaded=d.open_template(path)
 assert not loaded.entities and loaded.units=='m' and 'Plan' in loaded.layouts and loaded.extensions['sheets']['Plan']['author']=='Jay' and loaded.filepath is None and loaded.dirty
 loaded.entities.append(poly());assert hashlib.sha256(path.read_bytes()).hexdigest()==digest and document_to_dict(doc)==before
 full=tmp_path/'full.pycad';d.save_template(doc,full,True);assert len(d.open_template(full).entities)==1


def test_six_page_hub_routes_and_search_ui(main_window):
 from pycad.drafting_ui import DraftingDialog,commands,NAMES
 mw=main_window;mw.document.entities=[TextEntity(Point(0,0),'Find me')];dialog=DraftingDialog(mw);assert dialog.stack.count()==6
 assert set(NAMES)|{'DRAFTINGTOOLS'}<=set(mw.canonical_commands)
 from pycad.command_palette import entries
 assert all(any(r['label']==name for r in entries(mw)) for name in NAMES)
 dialog.close();dialog.deleteLater()


def test_shortcut_conflicts_persistence_and_reset(main_window):
 from pycad import shortcut_reference as ref
 from pycad.workspace_presets import actions
 from pycad.appsettings import get_settings
 mw=main_window;records=actions(mw);key=next(iter(records));old=records[key].shortcut().toString();ref.assign(mw,key,'Ctrl+Alt+Shift+9');assert 'Ctrl+Alt+Shift+9' in str(get_settings().value('commands/shortcuts'))
 other=next(k for k in records if k!=key)
 with pytest.raises(ValueError):ref.assign(mw,other,'Ctrl+Alt+Shift+9')
 with pytest.raises(ValueError):ref.assign(mw,key,'L')
 ref.reset(mw);assert records[key].shortcut().toString()==old

def test_search_placed_attributes_and_locked_targets(qapp):
 doc=Document();spec=dict(tag='MARK',prompt='Mark',default='D01',position=[0,0],height=2.5,rotation=0.,visible=True,layer='0',style_name='Standard');doc.blocks['Door']=BlockDefinition('Door',[LineEntity(Point(0,0),Point(1,0))],attributes=[spec]);ref=BlockReferenceEntity('Door',Point(0,0),attributes={'MARK':'D01'});doc.entities=[ref]
 rows=d.search(doc,'D01',['Attributes']);assert rows[0]['field']=='Attribute.MARK';editing.apply(doc,d.replace_plan(doc,rows,'D01','D02'));assert doc.entities[0].attributes['MARK']=='D02';doc.undo_stack.undo();assert doc.entities[0].attributes['MARK']=='D01'
 doc.entities[0].attributes={};default_rows=d.search(doc,'D01',['Attributes']);assert default_rows
 editing.apply(doc,d.replace_plan(doc,default_rows,'D01','D04'));assert doc.entities[0].attributes['MARK']=='D04' and doc.blocks['Door'].attributes[0]['default']=='D01';doc.undo_stack.undo()
 doc.layers.layers['0']['locked']=True
 with pytest.raises(ValueError):d.replace_plan(doc,rows,'D01','D03')


def test_closed_reverse_preserves_path(qapp):
 from pycad.precision import polyline_measure
 doc=Document();e=PolylineEntity([Point(0,0),Point(10,0),Point(0,10)],closed=True,bulges=[.2,0,.3]);doc.entities=[e];measure=polyline_measure(e)
 editing.apply(doc,d.polyline_plan(doc,[e],'Reverse'));result=polyline_measure(doc.entities[0]);assert result[0]==pytest.approx(measure[0]) and abs(result[1])==pytest.approx(abs(measure[1]))


def test_new_uses_independent_default_template(main_window,tmp_path):
 from pycad.appsettings import get_settings
 path=tmp_path/'default.pycadt';main_window.document.units='m';d.save_template(main_window.document,path);prefs=get_settings();prefs.setValue('templates/default',str(path));prefs.sync();assert main_window.new_file();assert main_window.document.units=='m' and main_window.document.filepath is None
 get_settings().remove('templates/default')


def test_fence_tool_reviews_without_mutating_source(main_window,monkeypatch):
 from pycad import drafting_ui as ui
 mw=main_window;doc=mw.document;a=LineEntity(Point(3,-10),Point(3,10));b=LineEntity(Point(7,-10),Point(7,10));target=LineEntity(Point(0,0),Point(10,0));doc.entities=[a,b,target];before=document_to_dict(doc);seen=[];monkeypatch.setattr(ui,'review',lambda mw,p:seen.append(p));tool=ui.FenceTool(mw,[a,b],False);tool.points=[Point(5,-1),Point(5,1)];tool.complete();assert seen and document_to_dict(doc)==before;editing.apply(doc,seen[0]);assert len(doc.entities)==4

def test_alias_editor_accepts_new_registered_commands(main_window,monkeypatch):
 from pycad import ribbon_actions
 from PyQt6.QtWidgets import QInputDialog
 monkeypatch.setattr(QInputDialog,'getMultiLineText',lambda *a,**k:('PE=POLYEDITOR\nDS=DRAWSEARCH',True));ribbon_actions.edit_aliases(main_window)
 assert main_window.user_aliases['PE']=='POLYEDITOR' and 'DS' in main_window.command_names
 assert ribbon_actions.load_aliases()['DS']=='DRAWSEARCH'

def test_simplify_does_not_accumulate_tolerance_error(qapp):
 from pycad.geom_ops import point_segment_distance
 doc=Document();points=[Point(i,math.sin(i/10)) for i in range(100)];polyline=PolylineEntity(points);doc.entities=[polyline];editing.apply(doc,d.polyline_plan(doc,[polyline],'Simplify',.01));result=doc.entities[0].points
 assert all(min(point_segment_distance(p,a,b) for a,b in zip(result,result[1:]))<=.010000001 for p in points)
