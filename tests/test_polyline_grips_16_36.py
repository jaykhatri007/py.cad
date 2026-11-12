import math,copy
import pytest
from PyQt6.QtCore import Qt
from pycad.geometry import Point,PolylineEntity,RectangleEntity,HatchEntity
from pycad.native_io import document_to_dict,document_from_dict
from pycad import polyline_grips as g
from pycad.precision import polyline_measure

def setup(w,bulge=0,closed=False):
 e=PolylineEntity([Point(0,0),Point(20,0),Point(20,20)],closed,bulges=[bulge,0,0],width=2,color='#ff5500');w.document.entities=[e];w.document.spatial_index.invalidate();w.canvas.selected_entities=[e];w.set_tool('SELECT');return e

def test_vertex_and_midpoint_grips_and_context(main_window):
 w=main_window;e=setup(w);values=dict(g.grips(e,w.document.render_revision));assert set(values)=={'pt0','pt1','pt2','mid0','mid1'} and values['mid0']==Point(10,0)
 assert g.grips(e,w.document.render_revision) is g.grips(e,w.document.render_revision)
 menu=g.context(w,Point(10,0));labels=[a.text() for a in menu.actions()];assert 'Insert vertex at midpoint' in labels and 'Convert / reshape segment to arc' in labels and 'Reverse polyline' in labels;menu.deleteLater()
 assert 'right-click' in w.current_tool.status_prompt()

def test_insert_arc_midpoint_and_delete_preserve_true_arc(main_window):
 w=main_window;e=setup(w,.5);length=polyline_measure(e)[0];before=document_to_dict(w.document);candidate=g.change(e,'insert',0);assert len(candidate.points)==4 and polyline_measure(candidate)[0]==pytest.approx(length)
 g.commit(w,e,candidate,'Insert');assert w.document.entities[0].width==2 and w.document.entities[0].color=='#ff5500'
 merged=g.change(candidate,'delete',1);assert merged.bulges==pytest.approx(e.bulges) and polyline_measure(merged)[0]==pytest.approx(length)
 w.undo();assert document_to_dict(w.document)==before;w.redo();assert len(w.canvas.selected_entities[0].points)==4
 restored=document_from_dict(document_to_dict(w.document));assert restored.entities[0].bulges==candidate.bulges

def test_drag_vertex_preview_cancel_and_absolute_coordinate(main_window):
 w=main_window;e=setup(w);before=document_to_dict(w.document);w.current_tool.on_click(20,0,'',1);tool=w.current_tool;assert tool.name=='POLYGRIP';tool.on_move(25,5,'');assert document_to_dict(w.document)==before and tool.candidate.points[1]==Point(25,5)
 w.cancel_command();assert document_to_dict(w.document)==before
 g.start(w,e,'pt1');w.current_tool.on_text_input('30,10');assert w.document.entities[0].points[1]==Point(30,10);w.undo();assert document_to_dict(w.document)==before

def test_drag_midpoint_moves_only_segment_endpoints(main_window):
 w=main_window;e=setup(w);w.current_tool.on_click(10,0,'',1);tool=w.current_tool;assert tool.name=='POLYGRIP' and tool.operation=='segment';tool.on_move(12,3,'');tool.finish_drag();result=w.document.entities[0]
 assert result.points==[Point(2,3),Point(22,3),Point(20,20)] and result.width==2
 w.undo();assert w.document.entities[0] is e

def test_arc_reshape_straighten_angle_and_no_source_mutation(main_window):
 w=main_window;e=setup(w);candidate=g.change(e,'arc',0,Point(10,-5));assert candidate.bulges[0]==.5 and e.bulges[0]==0
 g.commit(w,e,candidate,'Arc');arc=g.change(candidate,'arc',0,value=90);assert arc.bulges[0]==pytest.approx(math.tan(math.pi/8))
 assert g.change(arc,'straighten',0).bulges[0]==0
 tool=g.start(w,candidate,'mid0','arc');tool.on_text_input('10,5');assert w.document.entities[0].bulges[0]==-.5

def test_open_close_reverse_rectangle_conversion_and_minimum(main_window):
 w=main_window;e=setup(w);closed=g.change(e,'close');assert closed.closed;reverse=g.change(closed,'reverse');assert polyline_measure(reverse)[0]==pytest.approx(polyline_measure(closed)[0]);assert not g.change(closed,'open').closed
 rect=RectangleEntity(Point(0,0),Point(20,20),width=3);w.document.entities=[rect];w.canvas.selected_entities=[rect];insert=g.change(rect,'insert',0);g.commit(w,rect,insert,'Insert');assert w.document.entities[0].kind=='LWPOLYLINE' and len(insert.points)==5 and insert.width==3
 short=PolylineEntity([Point(0,0),Point(10,0)])
 with pytest.raises(ValueError):g.change(short,'delete',0)
 assert g.change(short,'close').closed

def test_protected_locked_stale_and_invalid_edit_rejected(main_window):
 w=main_window;e=setup(w);w.document.layers.layers['0']['locked']=True
 with pytest.raises(ValueError):g.start(w,e,'pt1')
 w.document.layers.layers['0']['locked']=False;h=HatchEntity([Point(0,0),Point(20,0),Point(20,20)],source_entity_id=e.id);w.document.entities.append(h)
 with pytest.raises(ValueError):g.start(w,e,'pt1')
 w.document.entities.remove(h);tool=g.start(w,e,'pt1');w.document.dirty=True
 with pytest.raises(ValueError):tool.on_text_input('30,0')
 w.cancel_command();tool=g.start(w,e,'pt1');before=document_to_dict(w.document);tool.on_move(float('nan'),0,'')
 with pytest.raises(ValueError):tool.finish_drag()
 assert document_to_dict(w.document)==before


def test_two_vertex_closed_arc_polyline_is_editable(main_window):
 w=main_window;e=PolylineEntity([Point(-10,0),Point(10,0)],closed=True,bulges=[1,1]);w.document.entities=[e];w.canvas.selected_entities=[e]
 split=g.change(e,'insert',0);assert polyline_measure(split)[0]==pytest.approx(20*math.pi)
 merged=g.change(split,'delete',1);assert len(merged.points)==2 and merged.closed and merged.bulges==pytest.approx([1,1])
 g.commit(w,e,split,'Insert circle vertex');assert document_from_dict(document_to_dict(w.document)).entities[0].closed


def test_vertex_pick_radius_uses_staged_editor(main_window):
 w=main_window;e=setup(w);w.canvas.zoom=10;w.canvas.snap_radius_px=12;w.current_tool.on_click(20.8,0,'',1);assert w.current_tool.name=='POLYGRIP' and w.current_tool.operation=='vertex';w.cancel_command();assert e.points[1]==Point(20,0)


def test_associated_vertex_retains_existing_drag_tool(main_window):
 w=main_window;e=setup(w,closed=True);h=HatchEntity([Point(0,0),Point(20,0),Point(20,20)],source_entity_id=e.id);w.document.entities.append(h);w.current_tool.on_click(20,0,'',1);assert w.current_tool.name=='SELECT' and w.current_tool.grip_entity is e;w.cancel_command()


def test_pedit_alias_and_palette_route(main_window,monkeypatch):
 from pycad import drafting_ui
 from pycad.command_palette import entries,filter_entries
 w=main_window;setup(w);seen=[];monkeypatch.setattr(drafting_ui,'show',lambda mw,index=0:seen.append(index));w.run_ribbon_command('PEDIT');assert seen==[0]
 assert any(r['label']=='POLYEDITOR' for r in filter_entries(entries(w),'PEDIT'))


def test_grip_readout_uses_true_adjacent_arc_length(main_window):
 from pycad.measurements import measurement_for
 from pycad.precision import arc_data
 w=main_window;e=setup(w,.5);tool=g.start(w,e,'pt1');tool.on_move(21,1,'');candidate=tool.candidate;data=arc_data(candidate.points[0],candidate.points[1],candidate.bulges[0]);values={label:value for label,value,kind in measurement_for(tool,(21,1)).values};assert values['Previous edge']==pytest.approx(abs(data[1]*data[3]));w.cancel_command()
