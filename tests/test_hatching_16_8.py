import copy
import math
import time
import pytest
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QImage,QPainter,QPen,QColor
from pycad.geometry import Point,HatchEntity,PolylineEntity,CircleEntity
from pycad.hatching import (pattern_names,definitions,segments,read_pat,paint,
                           validate_definition,island_loops)
from pycad.document import Document,AddEntityCommand,SetAttrCommand
from pycad.native_io import document_to_dict,document_from_dict,entity_to_dict,entity_from_dict


def box(x=0,y=0,size=50):
    return [Point(x,y),Point(x+size,y),Point(x+size,y+size),Point(x,y+size)]


def test_library_has_real_families_and_dash_patterns():
    assert len(pattern_names())>=175
    for name in ('ANSI31','ANSI37','AR-CONC','BRICK','GRAVEL','STEEL','WOOD1','DOTS'):
        hatch=HatchEntity(box(),pattern=name,angle=0)
        rows=definitions(hatch)
        assert rows
        assert list(segments(hatch,(0,0,50,50)))


@pytest.mark.parametrize('pattern',pattern_names())
def test_every_library_pattern_native_roundtrip(pattern):
    hatch=HatchEntity(box(),pattern=pattern,pattern_scale=2.5,angle=22,
        origin=Point(3,7),double=True,background_color='#123456',transparency=30)
    doc=Document();doc.add_entity(hatch)
    assert document_to_dict(document_from_dict(document_to_dict(doc)))==document_to_dict(doc)


def test_custom_pat_dashes_dots_and_phase(tmp_path):
    path=tmp_path/'custom.pat'
    path.write_text('*MY_TILE,Own test\n0, 0,0, 0,5, 2,-2,0,-1\n90, 0,0, 0,10\n')
    rows=read_pat(path)['MY_TILE'];h=HatchEntity(box(),pattern='MY_TILE',pattern_definition=rows,angle=0)
    strokes=list(segments(h,(0,0,10,10)))
    assert any(p==q for p,q in strokes)
    horizontal=[(p,q) for p,q in strokes if p.y==q.y==0]
    assert any(p.as_tuple()==(0,0) and q.as_tuple()==(2,0) for p,q in horizontal)
    assert any(p.as_tuple()==(5,0) and q.as_tuple()==(7,0) for p,q in horizontal)
    shifted=list(segments(h,(5,0,10,10)))
    assert any(p.as_tuple()==(5,0) and q.as_tuple()==(7,0) for p,q in shifted)


@pytest.mark.parametrize('rows',[[[0,[0,0],[1,0],[]]],[[0,[0,0],[0,1],[0,0]]],[[0,[0,0],[0,float('nan')],[]]],[[0,[0,0],[0,1],[1]*129]]])
def test_bad_pat_rejected(rows):
    with pytest.raises(ValueError):validate_definition(rows)


@pytest.mark.parametrize('key,value',[('pattern_scale',0),('pattern_scale',float('inf')),('island_style','bad'),('double',1),('background_color','red'),('origin','bad'),('pattern','missing')])
def test_native_options_rejected(key,value):
    doc=Document();doc.add_entity(HatchEntity(box()));data=document_to_dict(doc)
    data['entities'][0]['data'][key]=value
    with pytest.raises((ValueError,TypeError)):document_from_dict(data)


def test_old_hatch_records_load_with_defaults():
    h=HatchEntity(box());record=entity_to_dict(h)
    from pycad.hatching import EXTRA_FIELDS
    for key in EXTRA_FIELDS:record['data'].pop(key)
    old=entity_from_dict(record)
    assert old.pattern_scale==1 and old.origin==Point(0,0)


def test_dense_pattern_budget_is_bounded():
    h=HatchEntity(box(),spacing=1e-9)
    start=time.monotonic()
    with pytest.raises(ValueError,match='dense'):list(segments(h,(0,0,1e9,1e9),1000))
    assert time.monotonic()-start<1


def test_transform_moves_pattern_origin_and_scale():
    h=HatchEntity(box(),pattern='ANSI33',angle=0,origin=Point(2,3))
    original=definitions(h)
    h.translate(10,20);h.rotate_around(Point(0,0),90);h.scale_from(Point(0,0),2)
    rows=definitions(h)
    for before,after in zip(original,rows):
        assert after[1]==pytest.approx((-2*(before[1][1]+20),2*(before[1][0]+10)))
        assert after[2]==pytest.approx((-2*before[2][1],2*before[2][0]))


def test_nested_island_modes_and_selected_creation(main_window):
    from pycad.hatch_ui import create_selected
    w=main_window
    shapes=[PolylineEntity(box(size=50),closed=True),PolylineEntity(box(10,10,30),closed=True),PolylineEntity(box(20,20,10),closed=True),CircleEntity(Point(80,20),10)]
    for e in shapes:w.document.add_entity(e)
    hatches=create_selected(w,shapes,{'pattern':'ANSI37','angle':0})
    assert len(hatches)==2 and len(hatches[0].holes)==2
    hatch=hatches[0];assert len(island_loops(hatch))==2
    hatch.island_style='outer';assert len(island_loops(hatch))==1
    hatch.island_style='ignore';assert not island_loops(hatch)
    hatch.island_style='normal'
    w.document.undo_stack.push(SetAttrCommand(w.document,shapes[1],'points',copy.deepcopy(shapes[1].points),box(12,12,25),'Move island'))
    assert hatch.holes[0][0]==Point(12,12)
    w.document.undo_stack.undo();assert hatch.holes[0][0]==Point(10,10)
    document_from_dict(document_to_dict(w.document))


@pytest.mark.parametrize('pattern',['LINES','ANSI33','AR-CONC','DOTS','BRICK','GRADIENT_LINEAR','GRADIENT_RADIAL'])
def test_dxf_preserves_pattern_geometry(tmp_path,pattern):
    from pycad.dxf_io import export_dxf,import_dxf
    h=HatchEntity(box(),pattern=pattern,angle=31,pattern_scale=1.7,origin=Point(3,7),double=True,
        background_color='#122334',color='#ab2345',gradient_color='#00ff55',transparency=25)
    doc=Document();doc.add_entity(h);path=tmp_path/'h.dxf';export_dxf(doc,str(path));imported=import_dxf(str(path));other=imported.entities[0]
    assert other.pattern==h.pattern and not imported.import_warnings
    assert other.angle==pytest.approx(h.angle)
    assert other.background_color.lower()==h.background_color
    assert other.transparency==pytest.approx(25,abs=.5)
    if not pattern.startswith('GRADIENT'):
        for before,after in zip(definitions(h),definitions(other)):
            assert before[0]==pytest.approx(after[0])
            for index in (1,2,3):assert before[index]==pytest.approx(after[index])
    else:
        assert other.color.lower()==h.color and other.gradient_color==h.gradient_color


def test_dxf_edge_path_circle_supported(tmp_path):
    import ezdxf
    from pycad.dxf_io import import_dxf
    d=ezdxf.new();h=d.modelspace().add_hatch();p=h.paths.add_edge_path();p.add_arc((0,0),10,0,360)
    path=tmp_path/'edges.dxf';d.saveas(path);result=import_dxf(str(path))
    assert len(result.entities)==1 and len(result.entities[0].boundary)>30
    document_from_dict(document_to_dict(result))


class Canvas:
    zoom=4
    def __init__(self):self.image=QImage(240,240,QImage.Format.Format_ARGB32);self.image.fill(QColor('#000000'))
    def world_to_screen(self,x,y):return QPointF(20+x*4,220-y*4)
    def viewport(self):return self.image


@pytest.mark.parametrize('pattern',['SOLID','ANSI37','DOTS','GRADIENT_LINEAR','GRADIENT_RADIAL','GRADIENT_CONICAL'])
def test_actual_pixels_clip_islands_and_boundary(qapp,pattern):
    c=Canvas();h=HatchEntity(box(),pattern=pattern,holes=[box(15,15,20)],angle=0)
    p=QPainter(c.image);p.setPen(QPen(QColor('#ffffff'),1));paint(c,p,h);p.end()
    assert c.image.pixelColor(120,120)==QColor('#000000')
    assert c.image.pixelColor(0,0)==QColor('#000000')
    assert any(c.image.pixelColor(x,y)!=QColor('#000000') for x in range(25,70) for y in range(25,70))


def test_dialog_preview_edit_and_undo(main_window,monkeypatch,qapp):
    from pycad.hatch_ui import HatchDialog,edit_hatch
    w=main_window;h=HatchEntity(box());w.document.add_entity(h);w.canvas.selected_entities=[h]
    dialog=HatchDialog(w,h);dialog.pattern.setCurrentText('BRICK');dialog.controls['pattern_scale'].setValue(2)
    dialog.show();qapp.processEvents();assert not dialog.grab().isNull()
    values=dialog.values();dialog.close()
    monkeypatch.setattr(HatchDialog,'exec',lambda self:1)
    monkeypatch.setattr(HatchDialog,'values',lambda self:values)
    edit_hatch(w);assert h.pattern=='BRICK' and h.pattern_scale==2
    w.document.undo_stack.undo();assert h.pattern=='LINES' and h.pattern_scale==1
    w.document.undo_stack.redo();assert h.pattern=='BRICK'


def test_gap_closing_keeps_source_objects():
    from pycad.hatching import bridge_gaps
    from pycad.geometry import LineEntity
    from pycad.geom_ops import flood_fill_boundary
    shapes=[LineEntity(Point(0,0),Point(20,0)),LineEntity(Point(20,0),Point(20,20)),
            LineEntity(Point(20,20),Point(0,20)),LineEntity(Point(0,20),Point(0,2))]
    before=[entity_to_dict(e) for e in shapes]
    assert flood_fill_boundary(shapes,Point(10,10),(-5,-5,25,25)) is None
    joined=bridge_gaps(shapes,2.1)
    assert len(joined)==5 and flood_fill_boundary(joined,Point(10,10),(-5,-5,25,25))
    assert before==[entity_to_dict(e) for e in shapes]


def test_dxf_disjoint_boundaries_split_without_loss(tmp_path):
    import ezdxf
    from pycad.dxf_io import import_dxf
    d=ezdxf.new();h=d.modelspace().add_hatch();h.set_pattern_fill('ANSI33')
    for loop in (box(),box(100,100,20)):
        h.paths.add_polyline_path([p.as_tuple() for p in loop],is_closed=True)
    path=tmp_path/'disjoint.dxf';d.saveas(path);doc=import_dxf(str(path))
    assert len(doc.entities)==1 and doc.entities[0].kind=="HATCH" and not doc.import_warnings
    assert len(doc.entities[0].holes)==1
    document_from_dict(document_to_dict(doc))


def test_send_to_back_and_recreate_boundary_are_undoable(main_window):
    from pycad.hatch_ui import send_to_back,recreate_boundary
    w=main_window;circle=CircleEntity(Point(10,10),5);h=HatchEntity(box(),holes=[box(15,15,10)])
    w.document.add_entity(circle);w.document.add_entity(h);w.canvas.selected_entities=[h]
    send_to_back(w);assert w.document.entities==[h,circle]
    w.document.undo_stack.undo();assert w.document.entities==[circle,h]
    recreate_boundary(w);assert len(w.document.entities)==4
    w.document.undo_stack.undo();assert len(w.document.entities)==2
