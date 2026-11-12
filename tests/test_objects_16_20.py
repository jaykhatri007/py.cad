"""Large import, hatch fidelity, interactive selection and object commands."""
import math
import time
import ezdxf
import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage,QPainter,QMouseEvent
from pycad.geometry import Point,LineEntity,PolylineEntity,SplineEntity,HatchEntity,BlockDefinition,BlockReferenceEntity,DimensionEntity
from pycad.document import Document,AddEntityCommand
from pycad.native_io import save_project,load_project,document_to_dict,document_from_dict
from pycad.dxf_io import import_dxf,export_dxf
from pycad.object_commands import explode,parts,select_similar,isolate,group,context_menu


def test_large_import_beyond_old_budget(qapp,tmp_path):
    path=tmp_path/'large.dxf'
    with path.open('w') as f:
        f.write('0\nSECTION\n2\nENTITIES\n')
        for i in range(100005):f.write(f'0\nLINE\n8\n0\n10\n{i*10}\n20\n0\n11\n{i*10+1}\n21\n0\n')
        f.write('0\nENDSEC\n0\nEOF\n')
    doc=import_dxf(str(path));assert len(doc.entities)==100005
    doc.rebuild_spatial_index();assert len(doc.query_entities((999990,-1,999992,1)))==1
    native=tmp_path/'large.pycad';save_project(doc,native)
    assert len(load_project(native).entities)==100005


def test_compound_hatch_survives_native_dxf(qapp,tmp_path):
    d=ezdxf.new();h=d.modelspace().add_hatch()
    for loop in ([(0,0),(20,0),(20,20),(0,20)],[(0,4),(8,4),(8,8),(0,8)],[(30,0),(35,0),(35,5),(30,5)]):
        h.paths.add_polyline_path(loop,is_closed=True)
    source=tmp_path/'h.dxf';d.saveas(source);doc=import_dxf(str(source));h=doc.entities[0]
    assert h.kind=='HATCH' and h.boundary_mode=='evenodd' and len(h.holes)==2
    assert h.bbox()==(0,0,35,20)
    from pycad.geom_ops import distance_to_entity
    assert distance_to_entity(Point(32,2),h)==0
    assert math.isinf(distance_to_entity(Point(4,6),h))
    native=tmp_path/'h.pycad';save_project(doc,native)
    loaded=load_project(native);assert loaded.entities[0].boundary_mode=='evenodd'
    out=tmp_path/'copy.dxf';export_dxf(loaded,str(out))
    assert len(ezdxf.readfile(out).modelspace().query('HATCH'))==1


def test_complex_hatch_stays_hatch(qapp,tmp_path):
    d=ezdxf.new();h=d.modelspace().add_hatch()
    h.paths.add_polyline_path([(100*math.cos(i*math.tau/5000),100*math.sin(i*math.tau/5000)) for i in range(5000)],is_closed=True)
    h.paths.add_polyline_path([(0,0),(1,0),(1,1),(0,1)],is_closed=True)
    path=tmp_path/'complex.dxf';d.saveas(path);doc=import_dxf(str(path))
    assert len(doc.entities)==1 and isinstance(doc.entities[0],HatchEntity)
    assert len(doc.entities[0].boundary)==5000
    assert document_from_dict(document_to_dict(doc)).entities[0].kind=='HATCH'


def test_explode_transform_undo_and_native(main_window,tmp_path):
    mw=main_window;doc=mw.document
    doc.blocks['Symbol']=BlockDefinition('Symbol',[LineEntity(Point(0,0),Point(2,0))])
    ref=BlockReferenceEntity('Symbol',Point(10,20),scale=3,rotation=90,color='#ff0000')
    doc.undo_stack.push(AddEntityCommand(doc,ref));mw.canvas.selected_entities=[ref]
    explode(mw);line=doc.entities[0]
    assert line.kind=='LINE' and line.p1.distance_to(Point(10,20))<1e-9
    assert line.p2.distance_to(Point(10,26))<1e-9 and line.color=='#ff0000'
    doc.undo_stack.undo();assert doc.entities==[ref]
    doc.undo_stack.redo();assert doc.entities[0] is line
    path=tmp_path/'exploded.pycad';save_project(doc,path);assert load_project(path).entities[0].kind=='LINE'


def test_explode_curves_dimension_and_primitive(qapp):
    doc=Document();poly=PolylineEntity([Point(0,0),Point(10,0)],bulges=[1,0])
    assert parts(poly,doc)[0].kind=='ARC'
    spline=SplineEntity([Point(0,0),Point(1,3),Point(4,0)])
    assert len(parts(spline,doc))>2 and all(e.kind=='LINE' for e in parts(spline,doc))
    dim=DimensionEntity(Point(0,0),Point(10,0),Point(5,5))
    assert any(e.kind=='TEXT' for e in parts(dim,doc))
    assert parts(LineEntity(Point(0,0),Point(1,0)),doc) is None


def test_group_explode_isolation_and_similar(main_window,tmp_path):
    mw=main_window;doc=mw.document
    a=LineEntity(Point(0,0),Point(5,0));b=LineEntity(Point(0,10),Point(5,10));c=PolylineEntity([Point(20,0),Point(25,0)])
    doc.entities=[a,b,c];doc.sync_associative();mw.canvas.selected_entities=[a]
    select_similar(mw);assert mw.canvas.selected_entities==[a,b]
    group(mw);assert len(doc.extensions['groups'])==1
    path=tmp_path/'group.pycad';save_project(doc,path);assert len(load_project(path).extensions['groups'])==1
    explode(mw);assert not doc.extensions['groups'] and doc.entities==[a,b,c]
    doc.undo_stack.undo();assert len(doc.extensions['groups'])==1
    isolate(mw);assert doc.visible_entities()==[a,b] and not doc.query_entities((19,-1,26,1))
    isolate(mw,True);assert doc.visible_entities()==[a,b,c]
    assert 'isolated_ids' not in document_to_dict(doc)


def test_click_does_not_serialize_and_cache_reused(main_window,monkeypatch):
    mw=main_window;doc=mw.document
    doc.entities=[LineEntity(Point(i*10,0),Point(i*10+5,0)) for i in range(110000)]
    doc.rebuild_spatial_index();mw.canvas.zoom=10
    image=QImage(900,600,QImage.Format.Format_ARGB32);image.fill(Qt.GlobalColor.transparent)
    painter=QPainter(image);mw.canvas._draw_cached_entities(painter);key=mw.canvas._drawing_image_key
    import pycad.native_io as native
    with monkeypatch.context() as patch:
        patch.setattr(native,'document_to_dict',lambda *_:(_ for _ in ()).throw(AssertionError('selection serialized drawing')))
        started=time.perf_counter();mw._on_world_clicked(2,0,'',Qt.MouseButton.LeftButton.value)
        mw.current_tool.finish_drag();mw.refresh_selection_ui();mw.canvas._draw_cached_entities(painter)
        elapsed=time.perf_counter()-started
    painter.end()
    assert mw.canvas.selected_entities==[doc.entities[0]] and mw.canvas._drawing_image_key==key
    assert elapsed<0.5,elapsed


def test_double_click_block_properties_and_context(main_window,monkeypatch):
    mw=main_window;doc=mw.document
    doc.blocks['MyBlock']=BlockDefinition('MyBlock',[LineEntity(Point(0,0),Point(10,0))])
    ref=BlockReferenceEntity('MyBlock',Point(0,0));doc.entities=[ref];doc.sync_associative()
    mw.canvas.selected_entities=[ref];mw.refresh_selection_ui()
    assert 'MyBlock' in mw.properties_panel.info.text()
    opened=[];monkeypatch.setattr(mw,'edit_block_dialog',lambda name=None:opened.append(name))
    pos=mw.canvas.world_to_screen(5,0)
    event=QMouseEvent(QMouseEvent.Type.MouseButtonDblClick,pos,pos,Qt.MouseButton.LeftButton,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier)
    mw.canvas.mouseDoubleClickEvent(event);assert opened==['MyBlock']
    menu=context_menu(mw,pos);labels=[a.text() for a in menu.actions()]
    assert all(label in labels for label in ('Select Similar','Isolate Objects','Block Editor','Explode','Modify','Draw'))
    menu.deleteLater()


def test_dxf_group_import(qapp,tmp_path):
    d=ezdxf.new();m=d.modelspace();a=m.add_line((0,0),(1,0));b=m.add_line((0,1),(1,1))
    d.groups.new('Pair').extend([a,b]);path=tmp_path/'g.dxf';d.saveas(path)
    doc=import_dxf(str(path));assert set(doc.extensions['groups']['Pair'])=={e.id for e in doc.entities}


def test_hatch_path_flags_keep_disconnected_external_regions(qapp,tmp_path):
    from pycad.hatching import render_loops
    d=ezdxf.new();h=d.modelspace().add_hatch();h.dxf.hatch_style=2
    for x,flags in ((0,1),(2,0),(30,1)):
        h.paths.add_polyline_path([(x,0),(x+1,0),(x+1,1),(x,1)],is_closed=True,flags=flags)
    path=tmp_path/'flags.dxf';d.saveas(path);doc=import_dxf(str(path));h=doc.entities[0]
    assert len(render_loops(h))==2
    assert len(document_from_dict(document_to_dict(doc)).entities[0].loop_flags)==3
    out=tmp_path/'out.dxf';export_dxf(doc,str(out))
    assert sorted(p.path_type_flags & 1 for p in ezdxf.readfile(out).modelspace().query('HATCH')[0].paths)==[0,1,1]


def test_dxf_group_export_and_clipboard_remap(qapp,tmp_path):
    from pycad.feature_interop import selection_extensions,remap_extensions
    doc=Document();a=LineEntity(Point(0,0),Point(1,0));b=LineEntity(Point(0,1),Point(1,1))
    doc.entities=[a,b];doc.extensions={'groups':{'Pair':[a.id,b.id]}}
    out=tmp_path/'groups.dxf';export_dxf(doc,str(out))
    assert len(import_dxf(str(out)).extensions['groups']['Pair'])==2
    subset=selection_extensions(doc,{a.id,b.id},set())
    remapped=remap_extensions(subset,{a.id:'new-a',b.id:'new-b'}, {})
    assert list(remapped['groups'].values())==[['new-a','new-b']]


def test_selection_cache_invalidates_after_geometry_change(main_window):
    mw=main_window;line=LineEntity(Point(0,0),Point(1,0));mw.document.entities=[line]
    image=QImage(900,600,QImage.Format.Format_ARGB32);p=QPainter(image)
    mw.canvas._draw_cached_entities(p);old=mw.canvas._drawing_image_key
    from pycad.document import TranslateEntitiesCommand
    mw.document.undo_stack.push(TranslateEntitiesCommand(mw.document,[line],10,0))
    mw.canvas._draw_cached_entities(p);p.end();assert mw.canvas._drawing_image_key!=old


def test_selection_drops_removed_object_on_undo(main_window):
    mw=main_window;line=LineEntity(Point(0,0),Point(1,0))
    mw.document.undo_stack.push(AddEntityCommand(mw.document,line));mw.canvas.selected_entities=[line]
    mw.refresh_selection_ui();assert mw.document.is_editable(line)
    mw.document.undo_stack.undo();mw.refresh_selection_ui()
    assert not mw.document.is_editable(line) and not mw.canvas.selected_entities


def test_large_block_pick_cache_moves_and_is_not_saved(qapp):
    from pycad.geom_ops import pick_entity
    doc=Document();block=BlockDefinition('Large',[LineEntity(Point(i*10,0),Point(i*10+2,0)) for i in range(2000)])
    doc.blocks['Large']=block;ref=BlockReferenceEntity('Large',Point(0,0));doc.entities=[ref];doc.sync_associative()
    assert pick_entity([ref],Point(1,0),.1) is ref
    index=ref._pick_index
    assert pick_entity([ref],Point(51,0),.1) is ref and ref._pick_index is index
    ref.translate(100,100)
    assert pick_entity([ref],Point(101,100),.1) is ref and ref._pick_index is not index
    record=document_to_dict(doc)['entities'][0]['data']
    assert not any(key.startswith('_pick') for key in record)
    assert document_from_dict(document_to_dict(doc)).entities[0].kind=='INSERT'


def test_selected_geometry_paint_is_cached(main_window,monkeypatch):
    mw=main_window;line=LineEntity(Point(0,0),Point(1,0));mw.document.entities=[line]
    mw.canvas.selected_entities=[line]
    calls=[];original=mw.canvas._draw_entity
    def draw(p,e): calls.append(e.id);return original(p,e)
    monkeypatch.setattr(mw.canvas,'_draw_entity',draw)
    image=QImage(900,600,QImage.Format.Format_ARGB32);p=QPainter(image)
    mw.canvas._draw_cached_entities(p);count=len(calls)
    mw.canvas._draw_cached_entities(p);p.end()
    assert len(calls)==count and count>=2
