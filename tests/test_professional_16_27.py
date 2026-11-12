"""Cross-feature regression tests for the ten professional workflow upgrades."""
import copy,json,math,zipfile,hashlib,stat
from pathlib import Path
import pytest
from PyQt6.QtCore import QTimer,QPointF
from PyQt6.QtGui import QPainter,QImage,QColor
from PyQt6.QtWidgets import QApplication,QProgressDialog
from pycad.document import Document,TranslateEntitiesCommand,DeleteEntitiesCommand,AddEntityCommand
from pycad.geometry import Point,LineEntity,PolylineEntity,RectangleEntity,CircleEntity,ArcEntity,DimensionEntity,HatchEntity,BlockDefinition,BlockReferenceEntity
from pycad.native_io import document_to_dict,document_from_dict,save_project,load_project
from pycad.pro_data import save_section,settings,validate


def test_ten_pages_and_commands(main_window):
    from pycad.pro_ui import ProDialog,commands
    d=ProDialog(main_window);assert d.stack.count()==10 and len(commands(main_window))==11
    assert all(name in main_window.command_names for name in commands(main_window));d.close()


@pytest.mark.parametrize('table',[{'unknown':{}},{'associations':[]},{'associations':{'a':{'kind':'dimension','sources':['b'],'anchors':['p1']}}},{'variants':{'x':{}}},{'viewport_settings':{'x':{'rotation':0,'clip':[[0,0]],'annotation_scale':1}}},{'quantity_adjustments':{'a':dict(deduction=-1,waste_percent=0,reason='x')}},{'quantity_adjustments':{'a':dict(deduction=0,waste_percent=101,reason='x')}}])
def test_invalid_state_rejected(table):
    with pytest.raises(ValueError):validate(table)


def test_schema14_and_legacy13(qapp,tmp_path):
    doc=Document();save_section(doc,'quantity_adjustments',{'a':dict(deduction=0,waste_percent=5,reason='Specification')},'Adjustment');save_project(doc,tmp_path/'x.pycad');new=load_project(tmp_path/'x.pycad');assert settings(new)==settings(doc)
    old=document_to_dict(Document());old['schema_version']=13;assert document_from_dict(old).entities==[]


def linked_dimension():
    from pycad.associations import bind_dimension
    doc=Document();p=RectangleEntity(Point(0,0),Point(10,5));dim=DimensionEntity(Point(99,99),Point(100,99),Point(0,-2));doc.entities=[p,dim]
    before=document_to_dict(doc);bind_dimension(doc,dim,[p.id,p.id],['vertex:0','vertex:1']);return doc,p,dim,before


def test_dimension_bind_move_undo_detach(qapp):
    from pycad.associations import detach
    doc,p,dim,before=linked_dimension();assert dim.measurement()==10 and doc.undo_stack.index()==1
    doc.undo_stack.push(TranslateEntitiesCommand(doc,[p],20,30));assert dim.p1.as_tuple()==(20,30)
    doc.undo_stack.undo();assert dim.p1.as_tuple()==(0,0)
    detach(doc,[dim.id]);doc.undo_stack.push(TranslateEntitiesCommand(doc,[p],2,3));assert dim.p1.as_tuple()==(0,0)
    doc.undo_stack.undo();doc.undo_stack.undo();doc.undo_stack.undo();assert document_to_dict(doc)==before


def test_missing_association_retains_snapshot(qapp,tmp_path):
    doc,p,dim,_=linked_dimension();snapshot=dim.p1.as_tuple();doc.undo_stack.push(DeleteEntitiesCommand(doc,[p]));assert dim.p1.as_tuple()==snapshot and doc.association_issues
    save_project(doc,tmp_path/'x.pycad');new=load_project(tmp_path/'x.pycad');assert new.association_issues
    doc.undo_stack.undo();assert not doc.association_issues


def test_radial_anchors_and_invalid_vertex(qapp):
    from pycad.associations import anchor
    c=CircleEntity(Point(3,4),5);assert anchor(c,'east').as_tuple()==(8,4)
    p=RectangleEntity(Point(0,0),Point(10,5))
    for name in ('vertex:-1','vertex:99','vertex:bad'):
        with pytest.raises(ValueError):anchor(p,name)


def test_hatch_outer_and_island_follow_sources(qapp):
    from pycad.associations import bind_hatch
    from pycad.takeoff_geometry import hatch_area
    doc=Document();outer=RectangleEntity(Point(0,0),Point(10,10));hole=CircleEntity(Point(5,5),1);h=HatchEntity([Point(0,0),Point(1,0),Point(0,1)],pattern='SOLID');doc.entities=[outer,hole,h];before=document_to_dict(doc);bind_hatch(doc,h,[outer.id,hole.id]);assert 96<hatch_area(h)<98
    doc.undo_stack.push(TranslateEntitiesCommand(doc,[hole],30,0));assert doc.association_issues and h.holes[0][0].x<10
    doc.undo_stack.undo();doc.undo_stack.undo();assert document_to_dict(doc)==before


def test_hatch_open_boundary_rejected_without_history(qapp):
    from pycad.associations import bind_hatch
    doc=Document();p=PolylineEntity([Point(0,0),Point(3,0),Point(0,3)]);h=HatchEntity(p.points);doc.entities=[p,h];before=document_to_dict(doc)
    with pytest.raises(ValueError):bind_hatch(doc,h,[p.id])
    assert document_to_dict(doc)==before and doc.undo_stack.index()==0


def test_block_variant_visibility_stretch_undo(qapp,tmp_path):
    from pycad.block_variants import define,apply
    doc=Document();doc.layers.add_layer('Detail');doc.blocks['Base']=BlockDefinition('Base',[LineEntity(Point(0,0),Point(10,0)),LineEntity(Point(0,1),Point(10,1),layer='Detail')]);insert=BlockReferenceEntity('Base',Point(0,0));doc.entities=[insert];doc.sync_associative();name=define(doc,'Base','Wide',['Detail'],stretch_x=5,threshold_x=0);assert len(doc.blocks[name].entities)==1 and doc.blocks[name].entities[0].p2.x==15
    apply(doc,insert,name);assert insert.block_name==name;save_project(doc,tmp_path/'block.pycad');assert name in load_project(tmp_path/'block.pycad').blocks
    doc.undo_stack.undo();assert insert.block_name=='Base';doc.undo_stack.undo();assert name not in doc.blocks


def test_curved_stretch_rejected(qapp):
    from pycad.block_variants import define
    doc=Document();doc.blocks['Base']=BlockDefinition('Base',[CircleEntity(Point(0,0),5)])
    with pytest.raises(ValueError):define(doc,'Base','Wide',stretch_x=2)
    assert doc.undo_stack.index()==0


@pytest.mark.parametrize('kind',['Door','Window'])
def test_symbol_has_editable_attributes(qapp,kind):
    from pycad.block_variants import symbol
    doc=Document();name=symbol(doc,kind);assert {a['tag'] for a in doc.blocks[name].attributes}=={'TYPE','WIDTH','HEIGHT'}


def test_revision_ids_and_block_changes(qapp):
    from pycad.revisions import compare
    a=Document();line=LineEntity(Point(0,0),Point(2,0));gone=CircleEntity(Point(0,0),1);a.entities=[line,gone];a.blocks['B']=BlockDefinition('B',[LineEntity(Point(0,0),Point(1,0))]);insert=BlockReferenceEntity('B',Point(2,2));a.entities.append(insert);a.sync_associative();b=document_from_dict(document_to_dict(a));b.entities[0].p2.x=3;b.entities=[e for e in b.entities if e.id!=gone.id];new=CircleEntity(Point(3,0),2);b.entities.append(new);b.blocks['B'].entities[0].p2.x=4;b.sync_associative();r=compare(a,b)
    assert r['added']==[new.id] and r['removed']==[gone.id] and set(r['changed'])=={line.id,insert.id} and r['block_definitions_changed']==['B']


def test_viewport_transform_config_and_undo(qapp,tmp_path):
    from pycad.layout import Layout,Viewport
    from pycad.viewport_plus import set_config,config,paper_point
    doc=Document();layout=Layout('Sheet');vp=Viewport(0,0,100,100,Point(0,0),1);layout.viewports=[vp];doc.layouts['Sheet']=layout
    set_config(doc,'Sheet',0,90,[[10,10],[90,10],[90,90],[10,90]],2);p=paper_point(vp,10,0,90);assert p.x==pytest.approx(50) and p.y==pytest.approx(60)
    save_project(doc,tmp_path/'vp.pycad');assert config(load_project(tmp_path/'vp.pycad'),'Sheet',0)['rotation']==90
    doc.undo_stack.undo();assert config(doc,'Sheet',0)['rotation']==0


def test_viewport_self_crossing_clip_rejected(qapp):
    from pycad.layout import Layout,Viewport
    from pycad.viewport_plus import set_config
    doc=Document();doc.layouts['S']=Layout('S');doc.layouts['S'].viewports=[Viewport(0,0,100,100,Point(0,0))]
    with pytest.raises(ValueError):set_config(doc,'S',0,0,[[10,10],[90,90],[10,90],[90,10]])
    assert doc.undo_stack.index()==0


def test_rotation_clip_pdf_and_raster(qapp,tmp_path):
    import fitz
    from pycad.canvas import CadCanvas
    from pycad.layout import Layout,Viewport
    from pycad.viewport_plus import set_config
    from pycad.plotting import publish_pdf
    doc=Document();doc.entities=[LineEntity(Point(-60,0),Point(60,0),color='#ff0000')];layout=Layout('S',100,100);layout.viewports=[Viewport(0,0,100,100,Point(0,0),1)];doc.layouts['S']=layout;doc.current_space='S';set_config(doc,'S',0,90,[[40,20],[60,20],[60,80],[40,80]],1)
    publish_pdf(doc,str(tmp_path/'vp.pdf'),['S'],preset=dict(page_width=100,page_height=100,margin=1,monochrome=False,scale_denominator=None));pdf=fitz.open(tmp_path/'vp.pdf');paths=pdf[0].get_drawings();red=[p for p in paths if p.get('color') and p['color'][0]>.8 and p['color'][1]<.2];assert red and all(abs(p['rect'].width)<1 for p in red)
    canvas=CadCanvas(doc);canvas.resize(400,400);canvas.show();qapp.processEvents();image=QImage(canvas.viewport().size(),QImage.Format.Format_ARGB32);image.fill(QColor('white'));p=QPainter(image);canvas._draw_layout_viewports(p);p.end();assert image.width()>0


def test_wall_gap_proposal_preserves_and_one_undo(qapp):
    from pycad.architecture import create_wall
    from pycad.architecture_review import inspect,gap_actions
    from pycad.automation import prepare_proposal,apply_proposal
    doc=Document();a=create_wall(doc,Point(0,0),Point(1000,0),100);b=create_wall(doc,Point(1000.5,0),Point(2000,0),100);before=document_to_dict(doc);actions=gap_actions(doc,1);assert len(actions)==2;trial=prepare_proposal(doc,actions);assert not inspect(trial,1);assert document_to_dict(doc)==before
    index=doc.undo_stack.index();apply_proposal(doc,actions);assert doc.undo_stack.index()==index+1;doc.undo_stack.undo();assert document_to_dict(doc)==before


def measured_doc():
    from pycad.boq import tag,set_rates,rate_key
    doc=Document();line=LineEntity(Point(0,0),Point(10000,0));doc.entities=[line];tag(doc,[line.id],'Wall','Brick','Length',1);set_rates(doc,{rate_key('Wall','Brick','m'):100},'INR',10);return doc,line


def test_quantity_deduction_waste_and_revision(qapp):
    from pycad.revisions import quantity_rows,quantity_delta
    doc,line=measured_doc();before=document_from_dict(document_to_dict(doc));base=quantity_rows(doc)['rows'][0];assert base['adjusted_quantity']==11
    save_section(doc,'quantity_adjustments',{line.id:dict(deduction=2,waste_percent=5,reason='Opening deduction')},'Adjustment');row=quantity_rows(doc)['rows'][0];assert row['net_quantity']==8 and row['adjusted_quantity']==8.4 and row['adjusted_cost']==840
    delta=quantity_delta(before,doc);assert delta['rows'][0]['delta']==pytest.approx(-2.6) and delta['rows'][0]['after_ids']==[line.id]


def test_excess_deduction_and_mixed_revision_units_rejected(qapp):
    from pycad.revisions import quantity_rows,quantity_delta
    doc,line=measured_doc();other=document_from_dict(document_to_dict(doc));other.units='m'
    with pytest.raises(ValueError):quantity_delta(doc,other)
    save_section(doc,'quantity_adjustments',{line.id:dict(deduction=20,waste_percent=0,reason='Too much')},'Adjustment')
    with pytest.raises(ValueError):quantity_rows(doc)


def test_multistep_room_plan_preview_undo_and_links(qapp,tmp_path):
    from pycad.room_planner import plan
    from pycad.automation import prepare_proposal,apply_proposal
    from pycad.smart_blocks import schedule_rows
    doc=Document();actions=plan([dict(name='Office',width=6000,depth=4000),dict(name='Store',width=3000,depth=3000)]);before=document_to_dict(doc);trial=prepare_proposal(doc,actions);assert document_to_dict(doc)==before and len(trial.entities)==18
    assert len(settings(trial)['associations'])==4 and any(r.get('Type')=='opening' for r in schedule_rows(trial))
    apply_proposal(doc,actions);assert doc.undo_stack.index()==1;save_project(doc,tmp_path/'plan.pycad');assert len(load_project(tmp_path/'plan.pycad').entities)==18;doc.undo_stack.undo();assert document_to_dict(doc)==before


def test_offline_room_instruction_and_unit_guard(qapp):
    from pycad.drafting_chat import offline
    doc=Document();value=offline(doc,'plan rooms Office 6000x4000; Store 3000x3000');assert len(value['actions'])==2
    doc.units='m'
    with pytest.raises(ValueError):offline(doc,'plan rooms Office 6x4')


@pytest.mark.parametrize('rooms',[[],[dict(name='Bad',width=100,depth=100)],[dict(name='Missing',width=6000)],[dict(name='NaN',width=float('nan'),depth=4000)]])
def test_planning_questions_required(rooms):
    from pycad.room_planner import plan
    with pytest.raises(ValueError):plan(rooms)


def test_regional_cache_loads_only_region_and_bounded_lru(qapp,tmp_path):
    from pycad.paged_drawing import create,Store
    doc=Document();doc.entities=[LineEntity(Point(i*10,0),Point(i*10+1,1)) for i in range(1000)];path=tmp_path/'region.pycaddb';before=document_to_dict(doc);create(doc,path);s=Store(path,cache_entities=3)
    try:
        entities=s.query((0,-1,101,2));assert len(entities)==11 and s.loaded==11 and len(s.cache)==3
        region=s.document((0,-1,21,2));assert len(region.entities)==3 and s.count==1000
    finally:s.close()
    assert document_to_dict(doc)==before


def test_regional_cache_block_once_and_crossing_ray(qapp,tmp_path):
    from pycad.paged_drawing import create,Store
    from pycad.geometry import RayEntity
    doc=Document();doc.blocks['B']=BlockDefinition('B',[LineEntity(Point(0,0),Point(10,0))]);doc.entities=[BlockReferenceEntity('B',Point(100,100)),BlockReferenceEntity('B',Point(200,200)),RayEntity(Point(0,0),Point(1,0))];doc.sync_associative();p=tmp_path/'r.pycaddb';create(doc,p);s=Store(p)
    try:
        assert s.db.execute('SELECT count(*) FROM blocks').fetchone()[0]==1
        region=s.document((99,99,111,101));assert len(region.entities)==2 and len(region.blocks)==1
    finally:s.close()


def test_cache_cancel_preserves_destination(qapp,tmp_path):
    from pycad.paged_drawing import create,Cancelled
    doc=Document();doc.entities=[LineEntity(Point(0,0),Point(1,0))];p=tmp_path/'r.pycaddb';p.write_bytes(b'original')
    with pytest.raises(Cancelled):create(doc,p,cancel=lambda:True)
    assert p.read_bytes()==b'original'


def test_background_cache_artifact_and_cancel(qapp,tmp_path):
    from pycad.workflow_jobs import run
    doc=Document();doc.entities=[LineEntity(Point(0,0),Point(1,0))];p=tmp_path/'r.pycaddb';before=document_to_dict(doc);r=run(None,doc,'regional_cache',artifact=p);assert p.is_file() and r['entities']==1 and document_to_dict(doc)==before
    original=p.read_bytes()
    def cancel():
        for w in QApplication.topLevelWidgets():
            if isinstance(w,QProgressDialog):w.canceled.emit()
    QTimer.singleShot(10,cancel);assert run(None,doc,'regional_cache',artifact=p) is None;assert p.read_bytes()==original


def test_bundle_roundtrip_with_xref_fonts_and_hash(qapp,tmp_path):
    from pycad.project_bundle import pack,unpack
    doc=Document();source=tmp_path/'ref.dxf';source.write_bytes(b'original source');doc.blocks['X']=BlockDefinition('X',[LineEntity(Point(0,0),Point(10,0))],source_filepath=str(source));doc.entities=[BlockReferenceEntity('X',Point(0,0))];doc.sync_associative();font=tmp_path/'font.ttf';font.write_bytes(b'user supplied font');before=document_to_dict(doc);p=tmp_path/'project.pycadpack';m=pack(doc,p,[font]);new=unpack(p,tmp_path/'project');restored=load_project(new)
    from pycad.xref import reference_path
    assert reference_path(restored,restored.blocks['X'].source_filepath).read_bytes()==source.read_bytes();assert document_to_dict(doc)==before and len(m['files'])==3


def test_missing_reference_does_not_publish(qapp,tmp_path):
    from pycad.project_bundle import pack
    doc=Document();doc.blocks['X']=BlockDefinition('X',[],source_filepath=str(tmp_path/'missing.dxf'));p=tmp_path/'p.zip';p.write_bytes(b'original')
    with pytest.raises(ValueError):pack(doc,p)
    assert p.read_bytes()==b'original'


@pytest.mark.parametrize('name',['../x','/tmp/x','C:/x','a\\b','CON.txt','folder./x'])
def test_bundle_traversal_refused(tmp_path,name):
    from pycad.project_bundle import checked_files
    p=tmp_path/'bad.zip'
    with zipfile.ZipFile(p,'w') as z:z.writestr(name,'bad')
    with pytest.raises(ValueError):checked_files(p)


def test_bundle_hash_tamper_refused(qapp,tmp_path):
    from pycad.project_bundle import pack,unpack
    p=tmp_path/'x.zip';pack(Document(),p)
    with zipfile.ZipFile(p) as z:files={n:z.read(n) for n in z.namelist()}
    files['drawing.pycad']+=b' '
    with zipfile.ZipFile(p,'w') as z:
        for n,v in files.items():z.writestr(n,v)
    with pytest.raises(ValueError):unpack(p,tmp_path/'out')
    assert not (tmp_path/'out').exists()


def release_zip(path,version):
    with zipfile.ZipFile(path,'w') as z:
        z.writestr('PY.cad/pycad/_version.py',f'__version__ = "{version}"\n');z.writestr('PY.cad/start.sh','echo test');z.writestr('PY.cad/LICENSE','GPL')
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_portable_update_and_rollback_preserve_data(tmp_path):
    from pycad.release_manager import stage,select,rollback
    root=tmp_path/'versions';p=tmp_path/'release.zip';sha=release_zip(p,'16.26.0');assert stage(p,sha,root)=='16.26.0';select(root,'16.26.0');(root/'private-data').write_text('keep')
    sha=release_zip(p,'16.27.0');stage(p,sha,root);select(root,'16.27.0');assert rollback(root)==root/'16.26.0' and (root/'private-data').read_text()=='keep'
    with pytest.raises(ValueError):stage(p,'0'*64,root)
    assert (root/'16.27.0/start.sh').is_file()


def test_gpu_geometry_shapes_and_fallback(qapp):
    from pycad.gpu_geometry import vertices,benchmark
    from pycad.canvas import CadCanvas
    assert vertices(LineEntity(Point(0,0),Point(1,0)))==(1,[(0,0),(1,0)])
    assert vertices(CircleEntity(Point(0,0),10))[0]==1
    h=HatchEntity([Point(0,0),Point(10,0),Point(10,10),Point(0,10)],pattern='SOLID');assert vertices(h)[0]==4
    h.holes=[[Point(2,2),Point(3,2),Point(2,3)]];assert vertices(h) is None
    assert not benchmark(CadCanvas(Document()))['verified']


def test_cpu_renderer_remains_full_geometry(qapp):
    from pycad.canvas import CadCanvas
    doc=Document();doc.entities=[LineEntity(Point(-10,0),Point(10,0),color='#ff0000')];canvas=CadCanvas(doc);canvas.resize(300,300);canvas.show();qapp.processEvents();canvas.gpu_geometry_enabled=True;before=document_to_dict(doc);image=QImage(canvas.viewport().size(),QImage.Format.Format_ARGB32);image.fill(QColor('white'));p=QPainter(image);canvas._draw_entities(p);p.end();assert document_to_dict(doc)==before and not getattr(canvas,'_gpu_geometry_error',None)


def test_rectangle_arc_and_nested_blocks_render_without_errors(qapp,caplog):
    import logging
    from pycad.canvas import CadCanvas
    doc=Document();doc.entities=[RectangleEntity(Point(-4,-4),Point(4,4),color="#ff0000"),ArcEntity(Point(0,0),3,0,180,color="#ff0000")];doc.blocks['B']=BlockDefinition('B',[ArcEntity(Point(0,0),2,0,90)]);doc.entities.append(BlockReferenceEntity('B',Point(0,0)));doc.sync_associative();canvas=CadCanvas(doc);canvas.resize(300,300);canvas.show();qapp.processEvents();image=QImage(canvas.viewport().size(),QImage.Format.Format_ARGB32);image.fill(QColor('white'));p=QPainter(image)
    with caplog.at_level(logging.ERROR,logger='pycad.canvas'):canvas._draw_entities(p)
    p.end();assert not [r for r in caplog.records if r.levelno>=logging.ERROR];assert any(image.pixelColor(x,y)!=QColor('white') for x in range(0,image.width(),2) for y in range(0,image.height(),2))


def test_professional_clipboard_remaps_and_merges(qapp):
    from pycad.feature_interop import selection_extensions,remap_extensions,merge_extensions
    doc,p,dim,_=linked_dimension();values=selection_extensions(doc,{p.id,dim.id},set());assert dim.id in values['professional']['associations'];assert not selection_extensions(doc,{dim.id},set()).get('professional')
    remapped=remap_extensions(values,{dim.id:'newdim',p.id:'newpoly'},{});assert remapped['professional']['associations']['newdim']['sources']==['newpoly','newpoly']
    current={'professional':{'associations':{'existing':dict(kind='dimension',sources=['a','b'],anchors=['p1','p2'])}}};merged=merge_extensions(current,remapped);assert set(merged['professional']['associations'])=={'existing','newdim'}


def test_variant_parameters_follow_physical_unit_conversion(qapp):
    from pycad.feature_interop import scale_extensions
    save=Document();save_section(save,'variants',{'V':dict(base='B',state='Wide',hidden_layers=[],stretch_x=200,stretch_y=0,threshold_x=100,threshold_y=0)},'State');scale_extensions(save,.001);r=settings(save)['variants']['V'];assert r['stretch_x']==.2 and r['threshold_x']==.1


def test_nested_block_revision_marks_parent_instances(qapp):
    from pycad.revisions import compare
    doc=Document();doc.blocks['Child']=BlockDefinition('Child',[LineEntity(Point(0,0),Point(1,0))]);doc.blocks['Parent']=BlockDefinition('Parent',[BlockReferenceEntity('Child',Point(0,0))]);insert=BlockReferenceEntity('Parent',Point(0,0));doc.entities=[insert];doc.sync_associative();new=document_from_dict(document_to_dict(doc));new.blocks['Child'].entities[0].p2.x=5;new.sync_associative();assert compare(doc,new)['changed']==[insert.id]


def test_project_bundle_preserves_original_source_archive(qapp,tmp_path):
    import base64
    from pycad.project_bundle import pack,unpack
    doc=Document();raw=b'Original imported drawing bytes';doc.source_archive=dict(filename='original.dxf',sha256=hashlib.sha256(raw).hexdigest(),data_base64=base64.b64encode(raw).decode());p=tmp_path/'project.pycadpack';pack(doc,p);restored=load_project(unpack(p,tmp_path/'restored'));assert restored.source_archive==doc.source_archive
