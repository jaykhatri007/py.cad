"""External duplicate tags are import aliases; native tags remain strict."""
import hashlib,os,copy,collections
from pathlib import Path
import pytest,ezdxf
from pycad.import_attributes import AttributeTags
from pycad.native_io import save_project,load_project,document_to_dict
from pycad.dxf_io import import_dxf,export_dxf

@pytest.mark.parametrize('tags,expected',[
 (['A','A'],['A','A__2']),(['A','a','A__2'],['A','a__3','A__2']),
 (['X__2','X','X','x'],['X__2','X','X__3','x__4']),
 (['Width','Height'],['Width','Height']),
])
def test_aliases(tags,expected):
 m=AttributeTags(tags);assert m.aliases==expected;assert len({v.casefold() for v in m.aliases})==len(tags)

def test_long_tags():
 tag='A'*255;m=AttributeTags([tag,tag]);assert len(m.aliases[1])==255 and m.aliases[1].endswith('__2')

def test_values_all_occurrences_and_case():
 m=AttributeTags(['SIZE','size','SIZE__2']);values,changes=m.values([('Size','first'),('SIZE','second'),('size__2','real suffix')]);assert values=={'SIZE':'first','size__3':'second','SIZE__2':'real suffix'}
 assert m.values([('SIZE','another'),('size','different')])[0]=={'SIZE':'another','size__3':'different'}

@pytest.mark.parametrize('pairs',[[('A__2','orphan'),('A','first'),('a','second')],[('A','first'),('a','second'),('A__2','orphan')]])
def test_orphan_collision_no_overwrite(pairs):
 values,_=AttributeTags(['A','A']).values(pairs);assert values['A']=='first' and values['A__2']=='second' and values['A__2__2']=='orphan' and len(values)==3

def test_extra_and_orphan_values():
 values,_=AttributeTags(['A']).values([('A','one'),('A','two'),('X','three'),('x','four')]);assert len(values)==4 and list(values.values())==['one','two','three','four']

def source_dxf(path):
 doc=ezdxf.new();block=doc.blocks.new('Repeated',base_point=(10,0));block.add_line((10,0),(15,0));block.add_attdef('SIZE',insert=(10,0),text='default1',height=1);block.add_attdef('size',insert=(12,0),text='default2',height=1);block.add_attdef('SIZE__2',insert=(14,0),text='reserved',height=1)
 for x,values in [(100,('one','two','real')),(200,('three','four','suffix'))]:
  insert=doc.modelspace().add_blockref('Repeated',(x,0));insert.add_attrib('SIZE',values[0],(x,0));insert.add_attrib('size',values[1],(x+2,0));insert.add_attrib('SIZE__2',values[2],(x+4,0))
 doc.saveas(path);return doc

def test_import_values_render_native_export_roundtrip(qapp,tmp_path):
 source=tmp_path/'repeated.dxf';source_dxf(source);sha=hashlib.sha256(source.read_bytes()).hexdigest();doc=import_dxf(str(source));block=doc.blocks['Repeated'];assert [a['tag'] for a in block.attributes]==['SIZE','size__3','SIZE__2'];assert [a['default'] for a in block.attributes]==['default1','default2','reserved'];assert doc.entities[0].attributes=={'SIZE':'one','size__3':'two','SIZE__2':'real'};assert doc.entities[1].attributes['size__3']=='four'
 assert [e.text for e in doc.entities[0].resolved_entities if e.kind=='TEXT']==['one','two','real'];assert [e.position.x for e in doc.entities[0].resolved_entities if e.kind=='TEXT']==[100,102,104]
 assert any('Duplicate attribute tags' in w for w in doc.import_warnings);native=tmp_path/'copy.pycad';save_project(doc,native);restored=load_project(native);assert document_to_dict(restored)==document_to_dict(doc)
 out=tmp_path/'copy.dxf';export_dxf(restored,str(out));again=import_dxf(str(out));assert again.entities[0].attributes==doc.entities[0].attributes;assert len(again.blocks['Repeated'].attributes)==3;assert hashlib.sha256(source.read_bytes()).hexdigest()==sha

def test_duplicate_native_still_rejected(qapp,tmp_path):
 source=tmp_path/'native.dxf';source_dxf(source);doc=import_dxf(str(source));doc.blocks['Repeated'].attributes[1]['tag']='SIZE'
 with pytest.raises(ValueError,match='Duplicate attribute tag'):save_project(doc,tmp_path/'bad.pycad')

def test_user_dwg(qapp,tmp_path):
 source=os.environ.get('PYCAD_ATTRIBUTE_DWG_FIXTURE')
 if not source:pytest.skip('Supply private DWG fixture via environment; it is not shipped')
 from pycad.dxf_io import import_dwg
 before=hashlib.sha256(Path(source).read_bytes()).hexdigest();doc=import_dwg(source);assert len(doc.blocks)==85 and sum(len(b.attributes) for b in doc.blocks.values())==171;assert sum(len(b.entities) for b in doc.blocks.values())==8150
 for block in doc.blocks.values():assert len(block.attributes)==len({a['tag'].casefold() for a in block.attributes})
 save_project(doc,tmp_path/'actual.pycad');assert document_to_dict(load_project(tmp_path/'actual.pycad'))==document_to_dict(doc);assert hashlib.sha256(Path(source).read_bytes()).hexdigest()==before
