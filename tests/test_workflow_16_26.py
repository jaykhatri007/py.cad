"""Nine-area integration: model fidelity, quantities, undo, rendering and recovery."""
import copy
import json
import math
from pathlib import Path

import pytest
from PyQt6.QtCore import QPointF,QTimer,Qt
from PyQt6.QtGui import QImage,QPainter,QColor,QPen
from PyQt6.QtWidgets import QApplication,QDialog,QProgressDialog,QPushButton
from pycad.document import Document
from pycad.geometry import Point,LineEntity,ArcEntity,PolylineEntity,HatchEntity,BlockDefinition,BlockReferenceEntity
from pycad.native_io import document_to_dict,document_from_dict,save_project,load_project
from pycad import workflow_data as data


@pytest.fixture(autouse=True)
def private_history(tmp_path,monkeypatch):
    from pycad import applog
    monkeypatch.setattr(applog,'APP_DIR',str(tmp_path/'profile'))


def rules(doc):
    table={'takeoff_rules':{'01 walls':dict(layer='Walls*',kind='LINE',measurement='Length',factor=1,description='Wall run',material='Concrete',specification='M25')}}
    data.save(doc,table)
    return table


def test_all_nine_pages_are_connected(main_window):
    from pycad.workflow_ui import WorkflowDialog,commands
    d=WorkflowDialog(main_window);assert d.tabs.count()==9
    assert set(commands(main_window))=={'WORKFLOW','DIAGNOSTICS','PERFORMANCE','DWGREPORT','PRECISIONEDIT','XREFMANAGER','SHEETLIBRARY','RECOVERYHISTORY','TAKEOFFRULES','AIDRAFT','JOIN','BREAKAT','BIND','BINDMISSING'}
    assert d.findChild(QPushButton,'Preview rule takeoff')
    d.deleteLater()


def test_workflow_native_roundtrip_and_schema(qapp,tmp_path):
    doc=Document();rules(doc);p=tmp_path/'project.pycad';save_project(doc,p)
    loaded=load_project(p)
    assert document_to_dict(loaded)['schema_version']==17
    assert loaded.extensions['workflow']==doc.extensions['workflow']
    legacy=document_to_dict(doc);legacy['schema_version']=12;legacy['extensions']={}
    assert document_from_dict(legacy).entities==[]


@pytest.mark.parametrize('value',[{'unknown':{}},{'pen_styles':{'0':{'color':'bad','width':.2,'plot':True}}},{'takeoff_rules':[]},{'xref_unloaded':{'a':{'cache':'../bad'}}}])
def test_malformed_workflow_rejected(value):
    with pytest.raises(ValueError):data.validate(value)


def test_rule_preview_does_not_mutate_then_one_undo(qapp):
    doc=Document();doc.layers.add_layer('Walls');line=LineEntity(Point(0,0),Point(3000,0),layer='Walls');doc.entities=[line];rules(doc)
    before=document_to_dict(doc);tags,specs,result=data.proposed_tags(doc)
    assert document_to_dict(doc)==before and result['items'][0]['quantity']==3
    assert specs[line.id]=='M25'
    start=doc.undo_stack.index();data.apply_tags(doc,tags,specs);assert doc.undo_stack.index()==start+1
    from pycad.boq import report
    assert report(doc)['items'][0]['specification']=='M25'
    doc.undo_stack.undo();assert document_to_dict(doc)==before


def test_rules_skip_locked_and_explicit_tags(qapp):
    from pycad.boq import tag
    doc=Document();doc.layers.add_layer('Walls');a=LineEntity(Point(0,0),Point(1,0),layer='Walls');doc.entities=[a];rules(doc)
    tag(doc,[a.id],'Explicit',measurement='Length')
    assert data.proposed_tags(doc)[0]=={}
    doc.extensions['boq']['tags']={};doc.layers.set_locked('Walls',True)
    assert data.proposed_tags(doc)[0]=={}


def test_stale_takeoff_targets_rejected(qapp):
    doc=Document();doc.layers.add_layer('Walls');a=LineEntity(Point(0,0),Point(1,0),layer='Walls');doc.entities=[a];rules(doc)
    tags,specs,_=data.proposed_tags(doc);doc.entities=[]
    with pytest.raises(ValueError,match='changed'):data.apply_tags(doc,tags,specs)


def test_rate_library_and_specification_matching(qapp):
    from pycad.boq import report,rate_key
    doc=Document();doc.layers.add_layer('Walls');a=LineEntity(Point(0,0),Point(2000,0),layer='Walls');doc.entities=[a];table=rules(doc)
    tags,specs,_=data.proposed_tags(doc);data.apply_tags(doc,tags,specs)
    table=copy.deepcopy(doc.extensions['workflow']);table['rate_library']={rate_key('Wall run','Concrete','m'):dict(description='Wall run',material='Concrete',unit='m',rate=120,currency='INR',specification='M25')};data.save(doc,table);data.apply_rates(doc)
    assert report(doc)['priced_total']==240
    doc.extensions['workflow']['takeoff_specs'][a.id]='M30'
    assert report(doc)['unpriced_items']==1 and report(doc)['priced_total']==0


def test_mixed_rate_currencies_rejected(qapp):
    doc=Document();values={}
    for currency in ('INR','USD'):values[currency]=dict(description=currency,material='Steel',unit='m',rate=1,currency=currency,specification='')
    data.save(doc,dict(rate_library=values))
    with pytest.raises(ValueError,match='currency'):data.apply_rates(doc)


def test_hatch_net_area_and_disconnected_regions(qapp):
    from pycad.takeoff_geometry import hatch_area
    def square(x,y,s):return [Point(x,y),Point(x+s,y),Point(x+s,y+s),Point(x,y+s)]
    h=HatchEntity(square(0,0,10),holes=[square(2,2,2),square(20,0,10)],boundary_mode='evenodd',loop_flags=[1,0,1])
    assert hatch_area(h)==196
    h.island_style='ignore';assert hatch_area(h)==200


@pytest.mark.parametrize('other',[[Point(0,2),Point(2,2),Point(2,4),Point(0,4)],[Point(9,2),Point(12,2),Point(12,4),Point(9,4)]])
def test_touching_or_crossing_hatch_not_priced(qapp,other):
    from pycad.takeoff_geometry import hatch_area
    h=HatchEntity([Point(0,0),Point(10,0),Point(10,10),Point(0,10)],holes=[other],boundary_mode='evenodd')
    with pytest.raises(ValueError,match='touching'):hatch_area(h)


def test_hatch_quantity_and_arc_length(qapp):
    from pycad.boq import tag,report
    doc=Document();h=HatchEntity([Point(0,0),Point(1000,0),Point(1000,1000),Point(0,1000)])
    a=ArcEntity(Point(0,0),1000,0,90);doc.entities=[h,a]
    tag(doc,[h.id],'Area',measurement='Area');tag(doc,[a.id],'Curve',measurement='Length')
    quantities={r['description']:r['quantity'] for r in report(doc)['items']}
    assert quantities['Area']==1 and quantities['Curve']==pytest.approx(math.pi/2)


def test_join_line_arc_retains_bulge_and_undo(qapp):
    from pycad.precision_edit import join
    from pycad.precision import polyline_measure
    doc=Document();line=LineEntity(Point(0,0),Point(10,0));arc=ArcEntity(Point(10,5),5,270,360);doc.entities=[line,arc]
    result=join(doc,[line,arc]);assert result.bulges[1]==pytest.approx(math.tan(math.pi/8))
    assert polyline_measure(result)[0]==pytest.approx(10+5*math.pi/2)
    doc.undo_stack.undo();assert doc.entities==[line,arc]
    doc.undo_stack.redo();assert doc.entities==[result]


def test_join_closed_and_reject_branch(qapp):
    from pycad.precision_edit import join
    doc=Document();edges=[LineEntity(Point(0,0),Point(1,0)),LineEntity(Point(1,0),Point(0,1)),LineEntity(Point(0,1),Point(0,0))];doc.entities=edges
    assert join(doc,edges).closed
    doc.undo_stack.undo();extra=LineEntity(Point(0,0),Point(-1,0));doc.entities.append(extra)
    with pytest.raises(ValueError,match='Branched'):join(doc,edges+[extra])


def test_linked_and_locked_precision_edits_rejected(qapp):
    from pycad.precision_edit import break_at
    doc=Document();a=LineEntity(Point(0,0),Point(10,0));b=LineEntity(Point(0,1),Point(10,1));doc.entities=[a,b];doc.extensions={'groups':{'Pair':[a.id,b.id]}}
    with pytest.raises(ValueError,match='unlinked'):break_at(doc,a,.5)


def test_break_arc_preserves_radius_and_undo(qapp):
    from pycad.precision_edit import break_at
    doc=Document();a=ArcEntity(Point(1,2),7,270,90);doc.entities=[a]
    parts=break_at(doc,a,.5);assert all(p.radius==7 for p in parts) and parts[0].end_angle==360
    doc.undo_stack.undo();assert doc.entities==[a]


def test_nested_block_snap_and_cache_not_serialized(main_window):
    from pycad.precision_edit import snap_candidates
    doc=main_window.document;doc.blocks['Inner']=BlockDefinition('Inner',[LineEntity(Point(0,0),Point(10,0))]);doc.blocks['Outer']=BlockDefinition('Outer',[BlockReferenceEntity('Inner',Point(5,0))]);ref=BlockReferenceEntity('Outer',Point(10,0),scale=2);doc.entities=[ref];doc.sync_associative()
    candidates=snap_candidates([ref],(39,-1,41,1),doc);assert any(isinstance(e,LineEntity) for e in candidates)
    payload=document_to_dict(doc);assert '_snap_index' not in str(payload)
    assert document_from_dict(payload).entities[0].kind=='INSERT'
    ref.translate(100,0);doc.dirty=True
    assert any(isinstance(e,LineEntity) for e in snap_candidates([ref],(139,-1,141,1),doc))


def test_precise_clip_keeps_crossing_line_and_plot_region(qapp):
    from pycad.canvas import CadCanvas
    from pycad.geom_ops import distance_to_entity
    doc=Document();doc.blocks['Cross']=BlockDefinition('Cross',[LineEntity(Point(0,0),Point(100,0))]);ref=BlockReferenceEntity('Cross',Point(0,0),clip_boundary=[Point(20,-1),Point(30,-1),Point(30,1),Point(20,1)]);doc.entities=[ref];doc.sync_associative();assert len(ref.resolved_entities)==1
    assert math.isinf(distance_to_entity(Point(10,0),ref,1))
    canvas=CadCanvas(doc);canvas.world_to_screen=lambda x,y:QPointF(x,y+50);image=QImage(110,100,QImage.Format.Format_ARGB32);image.fill(QColor('white'));p=QPainter(image);p.setPen(QPen(QColor('black')));canvas._draw_entity(p,ref);p.end()
    assert image.pixelColor(25,50)!=QColor('white') and image.pixelColor(10,50)==QColor('white');canvas.deleteLater()


def test_xref_unload_cache_restore_and_undo(qapp,tmp_path):
    from pycad.xref_manager import unload,restore_cache
    doc=Document();doc.blocks['Ref']=BlockDefinition('Ref',[LineEntity(Point(0,0),Point(10,0))],source_filepath='reference.dxf');doc.entities=[BlockReferenceEntity('Ref',Point(0,0))];doc.sync_associative()
    unload(doc,'Ref');assert doc.blocks['Ref'].entities==[]
    p=tmp_path/'unloaded.pycad';save_project(doc,p);loaded=load_project(p);assert loaded.blocks['Ref'].entities==[]
    restore_cache(doc,'Ref');assert len(doc.blocks['Ref'].entities)==1
    doc.undo_stack.undo();assert doc.blocks['Ref'].entities==[]
    doc.undo_stack.undo();assert len(doc.blocks['Ref'].entities)==1


def test_sheet_template_scale_margin_and_undo(qapp):
    doc=Document();settings={'sheet_templates':{'A3':dict(width=420,height=297,margin=12,scale=100,title=dict(project='Test',title='Plan',number='A001',revision='A',author='Jay'))}}
    data.save(doc,settings);index=doc.undo_stack.index();layout=data.create_sheet(doc,'A3','Plan A')
    assert layout.page_width==420 and layout.viewports[0].x==12 and layout.viewports[0].scale==.01
    assert doc.undo_stack.index()==index+1 and doc.extensions['sheets']['Plan A']['author']=='Jay'
    doc.undo_stack.undo();assert 'Plan A' not in doc.layouts
    doc.undo_stack.redo();assert 'Plan A' in doc.layouts


def test_recovery_history_hash_retention_restore(qapp,tmp_path):
    from pycad import recovery_history as history
    doc=Document();doc.filepath=str(tmp_path/'original.pycad')
    for i in range(3):doc.entities.append(LineEntity(Point(i,0),Point(i,1)));entry=history.snapshot(doc,keep=2)
    assert len(history.entries())==2
    restored=history.restore(entry);assert restored.filepath is None and len(restored.entities)==3 and restored.dirty
    history.checked_path(entry).write_bytes(b'corrupt')
    with pytest.raises(ValueError,match='integrity'):history.restore(entry)


def test_audit_repair_preview_and_undo(qapp):
    from pycad.recovery_history import repair_candidates,repair
    doc=Document();a=LineEntity(Point(0,0),Point(1,0));b=LineEntity(Point(1,0),Point(0,0));z=LineEntity(Point(0,0),Point(0,0));doc.entities=[a,b,z]
    proposed=repair_candidates(doc);assert {r['id'] for r in proposed}=={b.id,z.id}
    repair(doc,[r['id'] for r in proposed]);assert doc.entities==[a]
    doc.undo_stack.undo();assert doc.entities==[a,b,z]


def test_ai_array_impact_and_single_undo(qapp):
    from pycad.drafting_chat import offline
    from pycad.automation import prepare_proposal,apply_proposal
    from pycad.proposal_review import impact_report
    doc=Document();a=LineEntity(Point(0,0),Point(1,0));doc.entities=[a]
    proposal=offline(doc,'array selected 2 by 3 spacing 100,200',[a.id]);assert len(proposal['actions'])==5
    staged=prepare_proposal(doc,proposal['actions']);assert len(doc.entities)==1 and impact_report(doc,staged)['added']==5
    index=doc.undo_stack.index();apply_proposal(doc,proposal['actions']);assert len(doc.entities)==6 and doc.undo_stack.index()==index+1
    doc.undo_stack.undo();assert doc.entities==[a]


def test_progressive_paint_finishes_without_modifying_model(main_window,qapp):
    mw=main_window;doc=mw.document;doc.entities=[LineEntity(Point(i%100,i//100),Point(i%100+1,i//100+1)) for i in range(1000)];doc.sync_associative();before=document_to_dict(doc);mw.canvas.zoom_extents();mw.graphics.set_drawing_path('progressive')
    image=QImage(mw.canvas.viewport().size(),QImage.Format.Format_ARGB32)
    for _ in range(100):
        p=QPainter(image);mw.canvas._draw_cached_entities(p);p.end()
        if mw.canvas.progressive_stats['complete']:break
    assert mw.canvas.progressive_stats['complete'] and mw.canvas.progressive_stats['painted']==1000
    assert document_to_dict(doc)==before


def test_id_lookup_cache_rebuilds_on_edit(qapp):
    doc=Document();a=LineEntity(Point(0,0),Point(1,0));doc.entities=[a];assert doc.find_by_id(a.id) is a
    cache=doc._id_lookup;assert doc.find_by_id(a.id) is a and doc._id_lookup is cache
    doc.entities=[];assert doc.find_by_id(a.id) is None


def test_background_source_staging_can_cancel(main_window,tmp_path,monkeypatch):
    import time
    from pycad.import_staging import stage
    from pycad import dwg_support
    def slow(source,directory,cancel=None,progress=None):
        while not cancel():time.sleep(.01)
        raise InterruptedError('cancelled')
    monkeypatch.setattr(dwg_support,'stage_source',slow)
    def cancel():
        dialog=next(w for w in QApplication.topLevelWidgets() if isinstance(w,QProgressDialog) and w.isVisible())
        dialog.canceled.emit()
    QTimer.singleShot(80,cancel);assert stage(main_window,'source.dwg',tmp_path) is False


@pytest.mark.parametrize('version',['2000','2004','2007','2010','2013','2018'])
def test_direct_spline_matches_compatibility(qapp,version):
    import os
    from pycad.dxf_io import import_dwg
    root=os.environ.get('PYCAD_DWG_FIXTURES')
    if not root:pytest.skip('Set PYCAD_DWG_FIXTURES')
    path=str(Path(root)/version/'Spline.dwg')
    a=import_dwg(path,mode='direct');b=import_dwg(path,mode='compatibility')
    assert [e.kind for e in a.entities]==[e.kind for e in b.entities]
    assert a.entities[0].bbox()==pytest.approx(b.entities[0].bbox())


def test_real_xref_attach_reload_units_and_change_detection(main_window,tmp_path):
    import ezdxf
    from pycad.xref_manager import attach_gui,reload_gui,status
    source=tmp_path/'reference ü.dxf';drawing=ezdxf.new();drawing.units=6;drawing.modelspace().add_line((0,0),(2,0));drawing.saveas(source)
    name=attach_gui(main_window,source);block=main_window.document.blocks[name]
    assert block.source_scale==1000 and block.entities[0].p2.x==2000
    assert status(main_window.document)[0]['status']=='Available'
    drawing.modelspace().add_line((0,1),(2,1));drawing.saveas(source)
    assert 'Changed' in status(main_window.document)[0]['status']
    assert reload_gui(main_window,name) and len(block.entities)==2
    assert status(main_window.document)[0]['status']=='Available'
    assert document_from_dict(document_to_dict(main_window.document)).blocks[name].source_scale==1000


def test_corrupt_xref_cache_cannot_replace_definition(qapp):
    from pycad.xref_manager import unload,restore_cache,cache_folder
    doc=Document();doc.blocks['Ref']=BlockDefinition('Ref',[LineEntity(Point(0,0),Point(1,0))],source_filepath='source.dxf');doc.entities=[BlockReferenceEntity('Ref',Point(0,0))];doc.sync_associative();unload(doc,'Ref')
    state=doc.extensions['workflow']['xref_unloaded']['Ref'];(cache_folder()/(state['cache']+'.json')).write_bytes(b'bad')
    before=document_to_dict(doc)
    with pytest.raises(ValueError,match='integrity'):restore_cache(doc,'Ref')
    assert document_to_dict(doc)==before


def test_layer_pdf_pen_does_not_change_drafting_color(qapp,tmp_path):
    import fitz
    from pycad.plotting import publish_pdf
    doc=Document();line=LineEntity(Point(0,0),Point(20,0),color='#123456');doc.entities=[line]
    data.save(doc,dict(pen_styles={'0':dict(color='#ff0000',width=2.,plot=True)}))
    path=tmp_path/'pens.pdf';publish_pdf(doc,path,['Model'],preset={'monochrome':False})
    pdf=fitz.open(path);drawings=pdf[0].get_drawings();assert any(r.get('color')==(1.,0.,0.) and r['width']==pytest.approx(2*72/25.4,rel=.001) for r in drawings)
    assert line.color=='#123456';pdf.close()


def test_exchange_quality_detects_same_count_wrong_scale(qapp):
    from pycad.exchange_quality import compare_documents,verify_export_extents
    import ezdxf
    a=Document();a.entities=[LineEntity(Point(0,0),Point(10,0))];b=Document();b.entities=[LineEntity(Point(0,0),Point(100,0))]
    report=compare_documents(a,b);assert report['kinds_equal'] and not report['extents_equal']
    x,y=ezdxf.new(),ezdxf.new();x.modelspace().add_line((0,0),(10,0));y.modelspace().add_line((0,0),(100,0))
    with pytest.raises(ValueError,match='extents changed'):verify_export_extents(x,y)


def test_diagnostics_records_worker_counts_and_open_failure(main_window,tmp_path,monkeypatch):
    import ezdxf
    from pycad.import_ui import load_dxf
    from pycad.drawing_diagnostics import EVENTS,report
    from PyQt6.QtWidgets import QMessageBox
    p=tmp_path/'two.dxf';drawing=ezdxf.new();drawing.modelspace().add_line((0,0),(1,0));drawing.modelspace().add_circle((5,5),1);drawing.saveas(p)
    doc=load_dxf(main_window,p)
    assert len(doc.entities)==2 and any(e['stage']=='import.worker' and e['entities']==2 for e in EVENTS)
    bad=tmp_path/'invalid.pycad';bad.write_text('bad JSON');monkeypatch.setattr(QMessageBox,'critical',lambda *a,**k:None)
    assert not main_window._open_path(str(bad),confirm=False)
    assert any(e['stage']=='open.failed' and e.get('error') for e in report(main_window.document)['events'])


def test_lookup_is_not_quadratic(qapp):
    class CountingList(list):
        iterations=0
        def __iter__(self):self.iterations+=1;return super().__iter__()
    doc=Document();doc.entities=CountingList(LineEntity(Point(i,0),Point(i,1)) for i in range(10000))
    ids=[doc.entities[i].id for i in range(0,10000,10)]
    for key in ids:assert doc.find_by_id(key) is not None
    assert doc.entities.iterations==1


def test_ai_review_cancel_preserves_source(main_window):
    from pycad.automation import review_proposal
    before=document_to_dict(main_window.document)
    def cancel():
        d=next(w for w in QApplication.topLevelWidgets() if isinstance(w,QDialog) and w.windowTitle()=='Review proposed changes')
        d.reject()
    QTimer.singleShot(30,cancel)
    assert review_proposal(main_window,[dict(op='line',start=[0,0],end=[10,0])]) is False
    assert document_to_dict(main_window.document)==before


def test_history_skips_malformed_metadata(qapp):
    from pycad.recovery_history import folder,entries
    token='0'*32;(folder()/(token+'.json')).write_text(json.dumps(dict(format='PY.cad history 1',file=token+'.pycad',created=None)))
    assert entries()==[]


def test_isolated_takeoff_preserves_live_model(qapp):
    from pycad.workflow_jobs import takeoff,fingerprint
    doc=Document();doc.layers.add_layer('Walls');doc.entities=[LineEntity(Point(0,0),Point(3000,0),layer='Walls')];rules(doc)
    before=document_to_dict(doc);value=takeoff(None,doc,timeout_ms=30000)
    assert value['report']['items'][0]['quantity']==3
    assert value['fingerprint']==fingerprint(doc)
    assert document_to_dict(doc)==before
    doc.entities[0].p2=Point(4000,0)
    assert value['fingerprint']!=fingerprint(doc)


def test_isolated_takeoff_can_cancel(qapp):
    from pycad.workflow_jobs import takeoff
    doc=Document();before=document_to_dict(doc)
    def cancel():
        for widget in QApplication.topLevelWidgets():
            if isinstance(widget,QProgressDialog):widget.canceled.emit()
    QTimer.singleShot(20,cancel)
    assert takeoff(None,doc,timeout_ms=30000) is None
    assert document_to_dict(doc)==before
