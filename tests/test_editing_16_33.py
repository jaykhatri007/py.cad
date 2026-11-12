import copy,json,math
import pytest
from PyQt6.QtCore import Qt,QTimer,QPointF
from PyQt6.QtWidgets import QApplication,QDialog,QProgressDialog
from pycad.document import Document
from pycad.geometry import Point,LineEntity,PolylineEntity,RectangleEntity,ArcEntity,TextEntity,BlockDefinition,BlockReferenceEntity
from pycad.native_io import document_to_dict,document_from_dict
from pycad import editing as e

def lines():
 d=Document();d.entities=[LineEntity(Point(0,0),Point(10,0)),LineEntity(Point(0,1),Point(20,1)),TextEntity(Point(0,0),'Office')];return d

def test_filters_and_selection_modes_respect_editability(main_window):
 mw=main_window;d=mw.document;d.entities=lines().entities;a,b,text=d.entities;b.color='#ff0000'
 assert e.filter_entities(d,dict(kind='LINE',min_length=15,color='#ff0000'))==[b]
 assert e.filter_entities(d,dict(text='office'))==[text]
 e.select(mw,[a]);e.select(mw,[b],'Add');assert mw.canvas.selected_entities==[a,b]
 e.select(mw,[a],'Subtract');assert mw.canvas.selected_entities==[b]
 e.select(mw,[a],'Intersect');assert not mw.canvas.selected_entities
 d.layers.layers['0']['locked']=True;assert not e.filter_entities(d,{})

@pytest.mark.parametrize('criteria',[{'min_length':-1},{'min_length':3,'max_length':2},{'min_length':float('nan')},{'unknown':1}])
def test_invalid_filters(qapp,criteria):
 with pytest.raises(ValueError):e.filter_entities(lines(),criteria)

def test_vertex_stretch_preserves_ids_bulges_and_undo(qapp):
 d=lines();poly=PolylineEntity([Point(0,0),Point(10,0),Point(10,10)],False,bulges=[.2,0,0]);d.entities.append(poly);a=d.entities[0];before=document_to_dict(d)
 proposal=e.vertex_plan(d,{a.id:['p2'],poly.id:['pt0','pt1']},2,3);assert document_to_dict(d)==before
 candidate=e.proposed(d,proposal);assert candidate.find_by_id(a.id).p2.x==12
 e.apply(d,proposal);assert d.find_by_id(poly.id).bulges==[.2,0,0] and d.find_by_id(poly.id).points[0].y==3
 d.undo_stack.undo();assert document_to_dict(d)==before;d.undo_stack.redo();assert d.find_by_id(a.id).p2.x==12

def test_stale_preview_and_locked_target_rejected(qapp):
 d=lines();a=d.entities[0];proposal=e.vertex_plan(d,{a.id:['p1']},2,0);a.p2.x=11
 with pytest.raises(ValueError):e.apply(d,proposal)
 d.layers.layers['0']['locked']=True
 with pytest.raises(ValueError):e.vertex_plan(d,{a.id:['p1']},2,0)

def test_segment_split_preserves_curved_path_and_rectangle_conversion(qapp):
 from pycad.precision import polyline_measure
 d=Document();poly=PolylineEntity([Point(0,0),Point(10,0)],False,bulges=[.5,0]);d.entities=[poly];before=polyline_measure(poly)[0]
 e.apply(d,e.segment_plan(d,poly,0,'Insert midpoint'));changed=d.find_by_id(poly.id);assert len(changed.points)==3 and polyline_measure(changed)[0]==pytest.approx(before)
 with pytest.raises(ValueError):e.segment_plan(d,changed,1,'Remove start vertex')
 rectangle=RectangleEntity(Point(0,0),Point(10,10));d.entities=[rectangle];e.apply(d,e.segment_plan(d,rectangle,0,'Insert midpoint'));assert d.find_by_id(rectangle.id).kind=='LWPOLYLINE' and len(d.find_by_id(rectangle.id).points)==5

def test_arc_reshape_fixed_endpoints_and_undo(qapp):
 d=Document();arc=ArcEntity(Point(0,0),10,0,180);d.entities=[arc];endpoints={(round(p.x,6),round(p.y,6)) for p in arc.endpoints()};before=document_to_dict(d)
 e.apply(d,e.arc_plan(d,arc,Point(0,5)));result=d.find_by_id(arc.id)
 assert {(round(p.x,6),round(p.y,6)) for p in result.endpoints()}==endpoints
 assert result.center.distance_to(Point(0,5))==pytest.approx(result.radius)
 d.undo_stack.undo();assert document_to_dict(d)==before
 with pytest.raises(ValueError):e.arc_plan(d,arc,Point(0,0))

def square(gap=.001):
 d=Document();d.entities=[LineEntity(Point(0,0),Point(10,0)),LineEntity(Point(10+gap,0),Point(10,10)),LineEntity(Point(10,10),Point(0,10)),LineEntity(Point(0,10),Point(0,gap))];return d

def test_boundary_gap_repair_preview_and_undo(qapp):
 d=square();before=document_to_dict(d);proposal=e.boundary_plan(d,list(d.entities),.01);assert document_to_dict(d)==before;e.apply(d,proposal)
 assert len(d.entities)==1 and d.entities[0].closed and e.simple_polygon(d.entities[0].points)>99.9
 d.undo_stack.undo();assert document_to_dict(d)==before

@pytest.mark.parametrize('kind',['crossing','branch','disconnected','style','linked','gap'])
def test_ambiguous_boundary_rejected_without_mutation(qapp,kind):
 d=square(0)
 if kind=='crossing':d.entities=[PolylineEntity([Point(0,0),Point(10,10),Point(0,10),Point(10,0)],True)]
 elif kind=='branch':d.entities.append(LineEntity(Point(0,0),Point(-10,0)))
 elif kind=='disconnected':d.entities.extend([LineEntity(Point(100,0),Point(110,0)),LineEntity(Point(110,0),Point(105,10)),LineEntity(Point(105,10),Point(100,0))])
 elif kind=='style':d.entities[1].color='#ff0000'
 elif kind=='linked':d.extensions['groups']={'group':[d.entities[0].id,d.entities[1].id]}
 elif kind=='gap':d=square(1)
 before=document_to_dict(d)
 with pytest.raises(ValueError):e.boundary_plan(d,list(d.entities),.01)
 assert document_to_dict(d)==before

def test_polyline_boundary_cleanup_repeated_vertex(qapp):
 d=Document();poly=PolylineEntity([Point(0,0),Point(10,0),Point(10,0),Point(10,10),Point(0,10),Point(0,.001)],False);d.entities=[poly]
 e.apply(d,e.boundary_plan(d,[poly],.01));assert d.entities[0].closed and len(d.entities[0].points)==4

def test_drafting_tracking_locks_and_document_reset(main_window):
 from pycad import drafting_aids as a
 from pycad.tools import LineTool
 mw=main_window;c=mw.canvas;mw.current_tool=LineTool(mw);c.set_active_tool(mw.current_tool);c.zoom=10;a.add_point(c,Point(10,20))
 assert a.adjust(c,10.1,20.2,'')[:2]==(10,20)
 assert a.adjust(c,10.1,20.2,'Endpoint')[:2]==(10.1,20.2)
 mw.current_tool.points=[Point(0,0)];a.configure(c,100,30);x,y,label=a.adjust(c,10,20,'Endpoint');assert x==pytest.approx(100*math.cos(math.pi/6)) and y==pytest.approx(50) and 'Locked' in label
 c.document=Document();assert a.state(c)['points']==[] and a.state(c)['distance'] is None

@pytest.mark.parametrize('distance,angle',[(0,None),(-1,30),(float('nan'),None),(None,float('inf'))])
def test_invalid_drafting_locks(main_window,distance,angle):
 from pycad.drafting_aids import configure
 with pytest.raises(ValueError):configure(main_window.canvas,distance,angle)

def test_workspace_roundtrip_preserves_drawing_and_local_settings(main_window):
 from pycad import workspace_presets as p
 mw=main_window;before=document_to_dict(mw.document);record=p.save(mw,'Drafting');compact=record['compact'];mw.ribbon.set_compact(not compact);p.restore(mw,p.saved()['Drafting']);assert mw.ribbon.compact==compact and document_to_dict(mw.document)==before
 p.remove('Drafting');assert 'Drafting' not in p.saved()
 bad=copy.deepcopy(record);bad['state']='badhex'
 with pytest.raises(ValueError):p.restore(mw,bad)
 assert document_to_dict(mw.document)==before

def test_health_scan_combines_geometry_distance_and_cleanup(qapp):
 d=lines();d.entities.extend([LineEntity(Point(1e8,1e8),Point(1e8+10,1e8)),LineEntity(Point(0,0),Point(0,0)),PolylineEntity([Point(0,0),Point(10,10),Point(0,10),Point(10,0)],True)])
 before=document_to_dict(d);report=e.health(d,1000);codes={r['code'] for r in report['rows']};assert {'DISTANT','ZERO_LENGTH','BOUNDARY','CLEANUP'}<=codes;assert document_to_dict(d)==before

def test_health_worker_and_cancel(main_window):
 from pycad.desk_jobs import run
 main_window.document.entities=lines().entities;report=run(main_window,'health',dict(distant=1000),main_window.document);assert report['objects']==3
 QTimer.singleShot(10,lambda:[w.cancel() for w in QApplication.topLevelWidgets() if isinstance(w,QProgressDialog)]);assert run(main_window,'health',dict(distant=1000),main_window.document) is None

def test_editing_hub_commands_and_interactive_ghost(main_window,monkeypatch):
 from pycad.editing_ui import EditingDialog,StretchVertices,activate
 from pycad.command_palette import entries
 mw=main_window;mw.document.entities=lines().entities;entity=mw.document.entities[0];mw.canvas.selected_entities=[entity];dialog=EditingDialog(mw);assert dialog.stack.count()==6
 for i in range(6):dialog.list.setCurrentRow(i);QApplication.processEvents()
 assert any(r['label']=='EDITING' for r in entries(mw));dialog.close()
 tool=StretchVertices(mw,{entity.id:['p2']});activate(mw,tool);before=document_to_dict(mw.document);tool.on_click(0,0,'',Qt.MouseButton.LeftButton.value);tool.on_move(2,3,'');mw.canvas.viewport().update();QApplication.processEvents();assert document_to_dict(mw.document)==before
 mw.cancel_command();assert document_to_dict(mw.document)==before

def test_review_cancel_then_apply(main_window):
 from pycad.editing_ui import review
 mw=main_window;mw.document.entities=lines().entities;a=mw.document.entities[0];before=document_to_dict(mw.document);proposal=e.vertex_plan(mw.document,{a.id:['p2']},2,0)
 def finish(accept):
  for w in QApplication.topLevelWidgets():
   if isinstance(w,QDialog) and w.windowTitle().startswith('Review Stretch'):w.accept() if accept else w.reject()
 QTimer.singleShot(60,lambda:finish(False));assert not review(mw,proposal);assert document_to_dict(mw.document)==before
 QTimer.singleShot(60,lambda:finish(True));assert review(mw,proposal);assert mw.document.find_by_id(a.id).p2.x==12
 mw.document.undo_stack.undo();assert document_to_dict(mw.document)==before

def test_adjacent_backtracking_boundary_rejected(qapp):
 d=Document();d.entities=[PolylineEntity([Point(0,0),Point(10,0),Point(5,0),Point(10,10),Point(0,10)],True)]
 with pytest.raises(ValueError):e.boundary_plan(d,d.entities,.001)
 assert any(r['code']=='BOUNDARY' for r in e.health(d)['rows'])

def test_drafting_locks_reach_canvas_click_path(main_window):
 from pycad.tools import LineTool
 from pycad.drafting_aids import configure
 from PyQt6.QtGui import QMouseEvent
 from PyQt6.QtCore import QEvent
 mw=main_window;tool=LineTool(mw);mw.current_tool=tool;mw.canvas.set_active_tool(tool);tool.points=[Point(0,0)];configure(mw.canvas,100,30)
 event=QMouseEvent(QEvent.Type.MouseButtonPress,QPointF(300,200),QPointF(300,200),Qt.MouseButton.LeftButton,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier);mw.canvas.mousePressEvent(event)
 assert len(mw.document.entities)==1;line=mw.document.entities[0];assert line.p2.x==pytest.approx(100*math.cos(math.pi/6)) and line.p2.y==pytest.approx(50)

def test_workspace_restores_panels_colors_shortcuts_and_drafting(main_window):
 from pycad.workspace_presets import capture,restore,actions
 from pycad.appearance import settings,save
 mw=main_window;QApplication.processEvents();mw.command_dock.show();mw.canvas.grid_enabled=False;mw.canvas.grid_spacing=25
 action=next(a for a in actions(mw).values() if a.shortcut().toString());original=action.shortcut().toString();baseline=capture(mw)
 mw.command_dock.hide();mw.canvas.grid_enabled=True;mw.canvas.grid_spacing=10;action.setShortcut('');colors=settings();colors['model']='#112233';save(mw,colors)
 restore(mw,baseline);QApplication.processEvents()
 assert not mw.command_dock.isHidden() and not mw.canvas.grid_enabled and mw.canvas.grid_spacing==25
 assert action.shortcut().toString()==original and settings()['model']==baseline['appearance']['model']
