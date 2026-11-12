"""No fixed drawing quotas; corruption checks and deep block operations remain."""
import json
import ezdxf
import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage,QPainter
from pycad.document import Document
from pycad.geometry import Point,LineEntity,PolylineEntity,BlockDefinition,BlockReferenceEntity
from pycad.native_io import document_to_dict,save_project,load_project,entity_to_dict
from pycad.validation import validate_payload
from pycad.block_budget import block_order,check_expansion


def test_native_file_above_old_100_mib_limit_loads(qapp,tmp_path):
    path=tmp_path/'large.pycad'
    with path.open('w') as f:
        for _ in range(101):f.write(' '*1024*1024)
        json.dump(document_to_dict(Document()),f)
    assert path.stat().st_size>100*1024*1024 and load_project(path).entities==[]


def test_dxf_above_old_100_mib_limit_opens(qapp,tmp_path):
    from pycad.dxf_io import import_dxf
    path=tmp_path/'large.dxf';source=ezdxf.new();source.modelspace().add_line((0,0),(1,0));source.saveas(path)
    raw=path.read_bytes();prefix=b'999\n'+b'x'*(1024*1024-5)+b'\n'
    with path.open('wb') as f:
        for _ in range(101):f.write(prefix)
        f.write(raw)
    assert path.stat().st_size>100*1024*1024 and len(import_dxf(str(path)).entities)==1


def test_validator_accepts_more_than_old_entity_and_vertex_counts(qapp):
    payload=document_to_dict(Document());record=entity_to_dict(LineEntity(Point(0,0),Point(1,0)))
    payload['entities']=[{'kind':'LINE','data':{**record['data'],'id':str(i)}} for i in range(500001)]
    validate_payload(payload);payload['entities']=[]
    poly=entity_to_dict(PolylineEntity([Point(0,0),Point(1,0)]))
    poly['data']['points']=[{'point':[0,0]}]*1000001;poly['data']['bulges']=[0]*1000001
    payload['entities']=[poly];validate_payload(payload)


def test_graph_has_no_expansion_or_depth_quota(qapp):
    blocks={'B0':BlockDefinition('B0',[])}
    for i in range(1,5000):blocks[f'B{i}']=BlockDefinition(f'B{i}',[BlockReferenceEntity(f'B{i-1}',Point(0,0))])
    refs=[BlockReferenceEntity('B4999',Point(0,0))]
    assert len(check_expansion(blocks,refs))==5000
    branching={'B0':BlockDefinition('B0',[])}
    for i in range(1,24):branching[f'B{i}']=BlockDefinition(f'B{i}',[BlockReferenceEntity(f'B{i-1}',Point(0,0)) for _ in range(2)])
    check_expansion(branching,[BlockReferenceEntity('B23',Point(0,0))])
    blocks['B0'].entities=[BlockReferenceEntity('B4999',Point(0,0))]
    with pytest.raises(ValueError,match='Cyclic'):check_expansion(blocks,refs)


def test_native_nested_blocks_past_32_are_complete_and_round_trip(qapp,tmp_path):
    doc=Document();doc.blocks['B0']=BlockDefinition('B0',[LineEntity(Point(0,0),Point(1,0))])
    for i in range(1,65):doc.blocks[f'B{i}']=BlockDefinition(f'B{i}',[BlockReferenceEntity(f'B{i-1}',Point(1,0))])
    doc.entities=[BlockReferenceEntity('B64',Point(10,0))];doc.sync_associative()
    assert doc.entities[0].bbox()==(74,0,75,0)
    path=tmp_path/'deep.pycad';save_project(doc,path)
    assert load_project(path).entities[0].bbox()==(74,0,75,0)


def test_deep_display_tree_clone_transform_pick_and_paint_do_not_recurse(qapp):
    from pycad.geom_ops import pick_entity
    from pycad.canvas import CadCanvas
    root=BlockReferenceEntity('unused',Point(0,0));node=root
    for _ in range(1500):
        child=BlockReferenceEntity('unused',Point(0,0));node.resolved_entities=[child];node=child
    node.resolved_entities=[LineEntity(Point(0,0),Point(1,0))]
    import copy
    snapshot=copy.deepcopy(root);assert snapshot.id==root.id and snapshot.bbox()==root.bbox()
    clone=root.clone();clone.translate(2,3);clone.rotate_around(Point(0,0),90);clone.scale_from(Point(0,0),2)
    assert clone.bbox()==pytest.approx((-6,4,-6,6))
    assert pick_entity([clone],Point(-6,5),.1) is clone
    canvas=CadCanvas(Document());image=QImage(300,300,QImage.Format.Format_ARGB32);image.fill(Qt.GlobalColor.transparent)
    painter=QPainter(image)
    try:canvas._draw_entity(painter,clone)
    finally:painter.end()
    assert root.bbox()==(0,0,1,0)


def test_invalid_data_still_rejected(qapp):
    payload=document_to_dict(Document());line=entity_to_dict(LineEntity(Point(0,0),Point(1,0)))
    line['data']['p1']['point'][0]=float('nan');payload['entities']=[line]
    with pytest.raises(ValueError):validate_payload(payload)
    with pytest.raises(ValueError,match='Missing'):block_order({'A':BlockDefinition('A',[BlockReferenceEntity('missing',Point(0,0))])})


def test_real_native_save_larger_than_old_byte_cap_round_trips(qapp,tmp_path):
    from pycad.geometry import TextEntity
    doc=Document();text='x'*22000
    doc.entities=[TextEntity(Point(i,0),text) for i in range(5000)]
    path=tmp_path/'large-save.pycad';save_project(doc,path)
    assert path.stat().st_size>100*1024*1024
    loaded=load_project(path)
    assert len(loaded.entities)==5000 and loaded.entities[-1].text==text


def test_dwg_staging_and_output_have_no_byte_cap(tmp_path):
    from pycad.dwg_support import stage_source,checked_output
    path=tmp_path/'large.dwg'
    with path.open('wb') as f:f.write(b'AC1032');f.truncate(101*1024*1024)
    target=tmp_path/'stage';target.mkdir()
    assert stage_source(path,target).stat().st_size==path.stat().st_size
    converted=target/'drawing.dxf'
    with converted.open('wb') as f:f.write(b'0\nEOF\n');f.truncate(101*1024*1024)
    assert checked_output(target,0)==converted
