import hashlib
import pytest
from PyQt6.QtGui import QColor, QImage, QPainter, QPen
from PyQt6.QtCore import QPointF, Qt
from pycad.document import Document
from pycad.geometry import LineEntity, Point
from pycad.native_io import document_from_dict, document_to_dict, save_project, load_project
from pycad.office_data import (OfficeSheet, door_recipe, linetype_recipe, load_project_set,
                               pdf_notes, save_project_set)
from pycad.office_tools import (apply_door, catalog_payload, door_params, edit_review,
                               export_office_block, insert_catalog, publish_project, save_linetype)

def test_independent_door_edit_undo_reload(qapp):
    doc=Document()
    initial=door_recipe(900,90,'Left','In')
    first=apply_door(doc,initial,Point(1,2))
    other=apply_door(doc,initial,Point(3,4))
    first.rotation=36
    edited=door_recipe(1050,45,'Right','Out')
    apply_door(doc,edited,ref=first)
    assert first.rotation==36 and first.insertion_point.x==1
    assert door_params(doc,first)==edited and door_params(doc,other)==initial
    assert first.resolved_entities[0].length()==pytest.approx(1050)
    doc.undo_stack.undo()
    assert door_params(doc,first)==initial
    doc.undo_stack.redo()
    loaded=document_from_dict(document_to_dict(doc))
    assert door_params(loaded,loaded.entities[0])==edited

def test_office_block_collision_and_unit_conversion(qapp,tmp_path):
    src=Document();src.units='mm'
    door=apply_door(src,door_recipe(900,90,'Left','In'),Point(0,0))
    path=tmp_path/'Door.officeblock';export_office_block(src,door.block_name,path)
    raw=catalog_payload(load_project(path))
    dest=Document();dest.units='cm'
    first=insert_catalog(dest,raw,Point(50,20))
    second=insert_catalog(dest,raw,Point(80,20))
    existing=insert_catalog(dest,raw,Point(0,0),use_existing=True)
    assert door_params(dest,first)['width']==pytest.approx(90)
    assert first.insertion_point.x==50 and first.block_name!=second.block_name
    assert existing.block_name==first.block_name
    dest.undo_stack.undo()
    assert len(dest.entities)==2
    dest.undo_stack.undo()
    assert len(dest.blocks)==1

def test_project_sheet_order_revision_and_source_untouched(qapp,tmp_path):
    from pypdf import PdfReader
    rows=[];originals={}
    for name,width in [('West',210),('East',300)]:
        doc=Document();doc.add_layout(name,width,200)
        file=tmp_path/(name+'.pycad');save_project(doc,file)
        originals[file]=hashlib.sha256(file.read_bytes()).hexdigest()
        rows.append(OfficeSheet(str(file),name,name))
    path=tmp_path/'Project.pycadsheets'
    save_project_set(path,rows,'R03')
    loaded,rev=load_project_set(path)
    assert loaded==rows and rev=='R03'
    output=tmp_path/'Combined.pdf'
    publish_project(rows,rev,output)
    pages=PdfReader(output).pages
    assert len(pages)==2 and pages[0].mediabox.width<pages[1].mediabox.width
    assert 'R03' in pages[0].extract_text() and 'R03' in pages[1].extract_text()
    with pytest.raises(ValueError,match='Duplicate'):publish_project([rows[0],rows[0]],rev,output)
    assert all(hashlib.sha256(p.read_bytes()).hexdigest()==h for p,h in originals.items())

def test_pdf_review_annotation_persists_and_resolves(qapp,tmp_path):
    from pypdf import PdfWriter
    from pypdf.annotations import Text
    from pycad.underlays import read_underlay
    writer=PdfWriter();writer.add_blank_page(200,200)
    writer.add_annotation(0,Text(rect=(10,10,30,30),text='Confirm grid spacing'))
    pdf=tmp_path/'Review.pdf';writer.write(pdf);writer.close()
    notes=pdf_notes(pdf,0)
    assert notes==[dict(text='Confirm grid spacing',author='',x=.1,y=.1,resolved=False)]
    doc=Document();doc.add_layout('Plan')
    record=read_underlay(pdf);record['plot']=False
    edit_review(doc,record,dict(notes=notes,space='Plan'))
    edit_review(doc,record,dict(notes=[{**notes[0],'resolved':True}],space='Plan'))
    loaded=document_from_dict(document_to_dict(doc))
    assert loaded.extensions['office_reviews'][record['id']]['notes'][0]['resolved']
    doc.undo_stack.undo()
    assert not doc.extensions['office_reviews'][record['id']]['notes'][0]['resolved']

def test_custom_linetype_native_persistent_render_and_undo(qapp,tmp_path):
    from pycad.office_ink import draw_custom
    from pycad.async_display import SnapshotCanvas,SnapshotDocument
    from pycad.persistent_scene import record_vector
    from pycad.appearance import colors
    from PyQt6.QtGui import QFont
    doc=Document()
    recipe=linetype_recipe('GAS',20,20,'G',8)
    save_linetype(doc,recipe,'0')
    doc.entities=[LineEntity(Point(5,0),Point(155,0),linetype='BYLAYER')]
    clone=document_from_dict(document_to_dict(doc))
    assert clone.entity_linetype(clone.entities[0])=='GAS'
    image=QImage(160,42,QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    snap=SnapshotCanvas(SnapshotDocument(clone),(1,0,0,160,42),{})
    snap.world_to_screen=lambda x,y:QPointF(x,20-y)
    p=QPainter(image);p.setPen(QPen(QColor('white'),1))
    try:assert draw_custom(snap,p,clone.entities[0])
    finally:p.end()
    assert image.pixelColor(12,20).alpha()>0
    assert image.pixelColor(27,20).alpha()==0
    assert any(image.pixelColor(x,y).alpha()>0 for x in range(29,40) for y in range(15,20))
    snapshot=SnapshotDocument(clone)
    record_vector(snapshot,clone.entities,dict(colors=colors(),hints=0,font=QFont().toString()))
    doc.undo_stack.undo()
    assert doc.layers.layers['0']['linetype']=='CONTINUOUS'
