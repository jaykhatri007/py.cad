import copy,json,hashlib
from pathlib import Path
import pytest
from PyQt6.QtCore import Qt,QTimer
from PyQt6.QtWidgets import QApplication,QDialog,QProgressDialog
from pycad.document import Document
from pycad.geometry import Point,LineEntity,CircleEntity,TextEntity,BlockDefinition,BlockReferenceEntity
from pycad.native_io import document_to_dict,document_from_dict,save_project,load_project
from pycad import coordination as c

def drawing():
 d=Document();d.entities=[CircleEntity(Point(0,0),10,color='#ff0000'),CircleEntity(Point(30,0),20,color='#00ff00')];return d

def test_shared_properties_mixed_atomic_apply_undo(qapp):
 from pycad.editing import apply
 d=drawing();before=document_to_dict(d);values=c.common_properties(d,d.entities);assert values['radius']==c.MIXED and values['color']==c.MIXED
 proposal=c.properties_plan(d,d.entities,dict(radius='15',color='#112233'));assert document_to_dict(d)==before;apply(d,proposal);assert all(q.radius==15 and q.color=='#112233' for q in d.entities)
 d.undo_stack.undo();assert document_to_dict(d)==before

@pytest.mark.parametrize('changes',[dict(radius='-1'),dict(radius='nan'),dict(layer='Missing'),dict(transparency='200'),dict(color='bad'),dict(radius=c.MIXED)])
def test_invalid_shared_changes_do_not_mutate(qapp,changes):
 d=drawing();before=document_to_dict(d)
 with pytest.raises(ValueError):c.properties_plan(d,d.entities,changes)
 assert document_to_dict(d)==before

def test_shared_property_dock_mixed_and_checked_fields(main_window):
 mw=main_window;mw.document.entities=drawing().entities;mw.canvas.selected_entities=list(mw.document.entities);mw.refresh_selection_ui();panel=mw.properties_panel;assert panel.color.text()==c.MIXED and panel.layer.currentText()=='0'
 widget=panel.shared_editor;i=widget.keys.index('radius');widget.table.item(i,0).setCheckState(Qt.CheckState.Checked);widget.table.item(i,2).setText('12');widget.apply();assert [q.radius for q in mw.document.entities]==[12,12] and mw.document.entities[0].color!=mw.document.entities[1].color
 mw.document.undo_stack.undo();mw.canvas.selected_entities=[mw.document.entities[0]];mw.refresh_selection_ui();assert not widget.isVisible() and panel.color.text()=='#ff0000'

def test_standard_roundtrip_diff_apply_preserves_visibility_and_undo(qapp,tmp_path):
 d=drawing();d.layers.add_layer('Walls','#123456');d.layers.layers['Walls']['lineweight']=.5;d.textstyles['Standard']['height']=4;profile=c.capture_standard(d);path=tmp_path/'standard.json';path.write_text(json.dumps(profile));profile=c.read_standard(path)
 target=drawing();target.layers.add_layer('Walls','#ffffff');target.layers.layers['Walls']['visible']=False;before=document_to_dict(target);candidate,rows=c.standard_diff(target,profile);assert rows and not candidate.layers.layers['Walls']['visible'];assert c.apply_standard(target,profile);assert target.textstyles['Standard']['height']==4 and not target.layers.layers['Walls']['visible']
 target.undo_stack.undo();assert document_to_dict(target)==before
 target.units='m'
 with pytest.raises(ValueError):c.apply_standard(target,profile)

@pytest.mark.parametrize('mutate',[lambda p:p.update(units='bad'),lambda p:p['layers']['0'].update(lineweight=-1),lambda p:p['textstyles']['Standard'].update(height=-1),lambda p:p.update(extra='bad')])
def test_invalid_standards(qapp,mutate):
 profile=c.capture_standard(drawing());mutate(profile)
 with pytest.raises(ValueError):c.validate_standard(profile)

def test_standards_batch_new_outputs_failures_and_existing(qapp,tmp_path):
 from pycad.standards_batch import run
 d=drawing();source=tmp_path/'input.pycad';save_project(d,source);before=source.read_bytes();profile=c.capture_standard(d);profile['textstyles']['Standard']['height']=7
 wrong=tmp_path/'wrong.pycad';other=drawing();other.units='m';save_project(other,wrong);out=tmp_path/'out';stage=out/'stage';result=run([str(source),str(wrong)],profile,str(out),str(stage));assert [r['status'] for r in result['rows']]==['Completed','Failed'];assert source.read_bytes()==before and load_project(out/'input-standard.pycad').textstyles['Standard']['height']==7
 assert run([str(source)],profile,str(out),str(stage))['rows'][0]['status']=='Skipped'

def test_reference_graph_nested_status_and_missing_source(qapp,tmp_path):
 d=Document();d.blocks['External']=BlockDefinition('External',[LineEntity(Point(0,0),Point(10,0))],source_filepath=str(tmp_path/'missing.dxf'));d.blocks['Parent']=BlockDefinition('Parent',[BlockReferenceEntity('External',Point(0,0))]);root=BlockReferenceEntity('Parent',Point(0,0));d.entities=[root];before=document_to_dict(d);graph=c.reference_graph(d);assert graph['rows'][0]['parents']==['Parent'] and graph['rows'][0]['instance_ids']==[root.id] and 'Missing' in graph['rows'][0]['status'];assert document_to_dict(d)==before

def test_reference_reload_nested_updates_and_undo(main_window,tmp_path):
 from pycad.dxf_io import export_dxf
 from pycad.xref_manager import reload_gui
 mw=main_window;d=mw.document;source=Document();source.entities=[LineEntity(Point(0,0),Point(50,0))];path=tmp_path/'source.dxf';export_dxf(source,str(path));before=path.read_bytes();d.blocks['External']=BlockDefinition('External',[LineEntity(Point(0,0),Point(10,0))],source_filepath=str(path));d.blocks['Parent']=BlockDefinition('Parent',[BlockReferenceEntity('External',Point(0,0))]);d.entities=[BlockReferenceEntity('Parent',Point(0,0))];d.sync_associative();assert reload_gui(mw,'External');assert d.blocks['External'].entities[0].p2.x==50;d.undo_stack.undo();assert d.blocks['External'].entities[0].p2.x==10 and path.read_bytes()==before

def blocks():
 d=Document();d.blocks['Child']=BlockDefinition('Child',[LineEntity(Point(0,0),Point(10,0))]);d.blocks['Parent']=BlockDefinition('Parent',[BlockReferenceEntity('Child',Point(20,0),scale=2)]);return d

def test_nested_block_preview_thumbnail_and_metadata(qapp,tmp_path,monkeypatch):
 from PyQt6.QtCore import QSettings
 import pycad.appsettings as settings
 monkeypatch.setattr(settings,'get_settings',lambda:QSettings(str(tmp_path/'settings.ini'),QSettings.Format.IniFormat));d=blocks();before=document_to_dict(d);preview=c.block_preview(d,'Parent',2,90);assert preview.entities[0].bbox()[3]>70;thumb=c.thumbnail_document(d,'Parent');assert len(thumb.entities)==1 and thumb.entities[0].p1.x==20 and thumb.entities[0].p2.x==40;assert document_to_dict(d)==before
 c.set_block_metadata('Parent',category='Furniture',favorite=True);assert c.block_metadata()['Parent']==dict(category='Furniture',favorite=True)

def test_block_browser_insert_ghost_cancel_and_commit(main_window):
 from pycad.block_library import BlockLibrary,LibraryInsert
 from pycad.editing_ui import activate
 mw=main_window;mw.document.blocks=blocks().blocks;before=document_to_dict(mw.document);dialog=BlockLibrary(mw);dialog.search.setText('parent');assert dialog.list.count()==1;dialog.next_icon();dialog.close();tool=LibraryInsert(mw,'Parent',2,90);activate(mw,tool);tool.on_move(100,200,'');mw.canvas.viewport().update();QApplication.processEvents();mw.cancel_command();assert document_to_dict(mw.document)==before
 tool=LibraryInsert(mw,'Parent',2,90);activate(mw,tool);tool.on_click(100,200,'',Qt.MouseButton.LeftButton.value);ref=mw.document.entities[0];assert ref.insertion_point==Point(100,200) and ref.scale==2 and ref.rotation==90
 mw.document.undo_stack.undo();assert document_to_dict(mw.document)==before

def test_tutorial_opens_separate_unsaved_copy(main_window):
 from pycad.tutorials import open_sample,LESSONS
 mw=main_window;old=mw.document;before=document_to_dict(old);doc=open_sample(mw);assert mw.document is doc and doc is not old and doc.filepath is None and doc.dirty and len(LESSONS)==6 and document_to_dict(old)==before
 assert 'Furniture_Desk' in doc.blocks and len(doc.layouts)==2

def test_coordination_hub_and_command_palette(main_window):
 from pycad.coordination_ui import CoordinationDialog,NAMES
 from pycad.command_palette import entries
 dialog=CoordinationDialog(main_window);assert dialog.stack.count()==6
 for i in range(6):dialog.list.setCurrentRow(i);QApplication.processEvents()
 assert set(NAMES)<=set(main_window.command_names) and any(r['label']=='COORDINATION' for r in entries(main_window));dialog.close()

def test_stability_worker_does_not_change_source(main_window):
 from pycad.desk_jobs import run
 mw=main_window;mw.document.entities=drawing().entities;before=document_to_dict(mw.document);result=run(mw,'stability',dict(repeats=2),mw.document);assert result['original_unchanged'] and not result['render_errors'] and all(r['native_roundtrip'] and r['render_nonempty'] for r in result['rows']);assert document_to_dict(mw.document)==before

def test_standards_worker_cancel_leaves_no_partial_output(main_window,tmp_path):
 from pycad.desk_jobs import run
 import tempfile
 doc=drawing();source=tmp_path/'source.pycad';save_project(doc,source);before=source.read_bytes();out=tmp_path/'out';out.mkdir()
 with tempfile.TemporaryDirectory(dir=out) as stage:
  QTimer.singleShot(10,lambda:[w.cancel() for w in QApplication.topLevelWidgets() if isinstance(w,QProgressDialog)])
  value=run(main_window,'standards_batch',dict(paths=[str(source)],profile=c.capture_standard(doc),output=str(out),stage=stage));assert value is None
 assert source.read_bytes()==before and not list(out.iterdir())

def test_properties_mixed_layer_returns_to_single_selection(main_window):
 mw=main_window;mw.document.entities=drawing().entities;mw.document.layers.add_layer('Other');mw.document.entities[1].layer='Other';mw.canvas.selected_entities=list(mw.document.entities);mw.refresh_selection_ui();assert mw.properties_panel.layer.currentText()==c.MIXED
 mw.canvas.selected_entities=[mw.document.entities[0]];mw.refresh_selection_ui();assert mw.properties_panel.layer.findText(c.MIXED)<0

def test_private_document_disposal_is_idempotent_and_keeps_geometry(qapp):
 from pycad.document_lifecycle import dispose_document,drain_deferred_deletes
 from pycad.document import AddEntityCommand
 from PyQt6 import sip
 d=Document();d.undo_stack.push(AddEntityCommand(d,LineEntity(Point(0,0),Point(10,0))));before=document_to_dict(d);stack=d.undo_stack;dispose_document(d);drain_deferred_deletes();dispose_document(d);assert sip.isdeleted(stack) and document_to_dict(d)==before
