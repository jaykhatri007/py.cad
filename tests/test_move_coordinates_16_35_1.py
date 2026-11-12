import pytest
from PyQt6.QtCore import Qt
from pycad.geometry import Point,LineEntity,CircleEntity,TextEntity,PolylineEntity,BlockReferenceEntity,BlockDefinition
from pycad.tools import MoveTool
from pycad.native_io import document_to_dict

def enter(w,text):w.command_line.setText(text);w._on_command_entered()
def setup(w,entities):w.document.entities=entities;w.document.spatial_index.invalidate();w.canvas.selected_entities=list(entities)

def test_m_origin_immediate_multiple_and_undo(main_window):
 w=main_window;a=LineEntity(Point(20,30),Point(25,35));b=CircleEntity(Point(40,50),2);setup(w,[a,b]);before=document_to_dict(w.document);enter(w,'m');assert isinstance(w.current_tool,MoveTool);assert '20,30' in w.current_tool.status_prompt();enter(w,'0,0');assert a.p1==Point(0,0) and b.center==Point(20,20);assert w.current_tool.name=='SELECT';assert w.document.undo_stack.count()==1
 w.document.undo_stack.undo();assert document_to_dict(w.document)==before;w.document.undo_stack.redo();assert a.p1==Point(0,0)

@pytest.mark.parametrize('entity,attr',[ (CircleEntity(Point(20,30),4),'center'),(TextEntity(Point(20,30),'A'),'position'),(PolylineEntity([Point(20,30),Point(40,50)]),'points') ])
def test_natural_reference(main_window,entity,attr):
 w=main_window;setup(w,[entity]);enter(w,'M');enter(w,'100.5,-50.25');point=getattr(entity,attr);point=point[0] if isinstance(point,list) else point;assert point==Point(100.5,-50.25)

def test_block_insertion_reference(main_window):
 w=main_window;w.document.blocks['Test']=BlockDefinition('Test',[LineEntity(Point(10,10),Point(20,20))]);e=BlockReferenceEntity('Test',Point(30,40));setup(w,[e]);enter(w,'M');enter(w,'0,0');assert e.insertion_point==Point(0,0)

def test_relative_direct_and_clicked_base_absolute(main_window):
 w=main_window;a=LineEntity(Point(20,30),Point(25,35));setup(w,[a]);enter(w,'M');enter(w,'@10,-5');assert a.p1==Point(30,25)
 enter(w,'M');w.current_tool.on_click(30,25,'',1);enter(w,'0,0');assert a.p1==Point(0,0)

def test_explicit_typed_base_and_relative_destination(main_window):
 w=main_window;a=LineEntity(Point(20,30),Point(25,35));setup(w,[a]);enter(w,'M');from pycad.command_options import options
 assert any(o.key=='B' for o in options(w));enter(w,'B');enter(w,'25,35');assert a.p1==Point(20,30);enter(w,'0,0');assert a.p2==Point(0,0)
 enter(w,'M');enter(w,'B');enter(w,'0,0');enter(w,'@2,3');assert a.p2==Point(2,3)

def test_cancel_invalid_and_locked_do_not_mutate(main_window):
 w=main_window;a=LineEntity(Point(20,30),Point(25,35));setup(w,[a]);enter(w,'M');tool=w.current_tool
 with pytest.raises(ValueError):tool.on_text_input('bad coordinates')
 with pytest.raises(ValueError):tool.on_text_input('nan,0')
 enter(w,'B');enter(w,'20,30');w.cancel_command();assert a.p1==Point(20,30) and w.document.undo_stack.count()==0
 w.set_tool('MOVE');w.document.layers.layers['0']['locked']=True
 with pytest.raises(ValueError):w.current_tool.on_text_input('0,0')
 assert a.p1==Point(20,30)

def test_zero_move_and_copy_semantics(main_window):
 w=main_window;a=LineEntity(Point(0,0),Point(5,5));setup(w,[a]);enter(w,'M');enter(w,'0,0');assert w.document.undo_stack.count()==0
 enter(w,'COPY');enter(w,'0,0');assert len(w.document.entities)==1;enter(w,'10,10');assert len(w.document.entities)==2 and a.p1==Point(0,0)
