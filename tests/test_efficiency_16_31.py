import copy,json,hashlib,os
from pathlib import Path
import pytest
from PyQt6.QtCore import Qt,QPointF,QEvent,QTimer
from PyQt6.QtGui import QKeyEvent,QImage,QPainter
from PyQt6.QtWidgets import QApplication,QProgressDialog
from pycad.document import Document,AddEntityCommand,SetAttrCommand
from pycad.geometry import Point,LineEntity,HatchEntity,BlockDefinition,BlockReferenceEntity,TextEntity
from pycad.native_io import document_to_dict,save_project,load_project
from pycad import efficiency as e


def cache_input(tmp_path):
 source=tmp_path/'input.dwg';source.write_bytes(b'AC1027 test data');d=Document();d.entities=[LineEntity(Point(0,0),Point(10,0))];raw=json.dumps(document_to_dict(d)).encode();return source,raw,dict(version='test',policy='auto',readers=[])

def test_cache_roundtrip_source_content_and_policy(qapp,tmp_path):
 from pycad.import_cache import lookup,store,digest_source
 source,raw,policy=cache_input(tmp_path);root=tmp_path/'cache';miss=lookup(root,source,policy);assert not miss['hit'];assert store(root,source,policy,miss['source_digest'],raw)['stored'];hit=lookup(root,source,policy);assert hit['hit'] and hit['raw'].encode()==raw
 source.touch();assert lookup(root,source,policy)['hit'];assert not lookup(root,source,{**policy,'policy':'direct'})['hit']
 old=source.stat();source.write_bytes(b'AC1027 changed!!');os.utime(source,ns=(old.st_atime_ns,old.st_mtime_ns));assert not lookup(root,source,policy)['hit']
 assert not store(root,source,policy,miss['source_digest'],raw)['stored']

@pytest.mark.parametrize('corruption',['data','metadata','symlink'])
def test_corrupt_cache_misses(qapp,tmp_path,corruption):
 from pycad.import_cache import lookup,store,digest_source
 source,raw,policy=cache_input(tmp_path);root=tmp_path/'cache';key=store(root,source,policy,digest_source(source),raw)['key'];data=root/(key+'.pycad');meta=root/(key+'.json')
 if corruption=='data':data.write_bytes(b'broken')
 elif corruption=='metadata':meta.write_text('{}')
 else:
  other=tmp_path/'outside';other.write_bytes(raw);data.unlink();data.symlink_to(other)
 assert not lookup(root,source,policy)['hit']

def test_cache_retention_only_owned_files(qapp,tmp_path):
 from pycad.import_cache import store,digest_source
 source,raw,policy=cache_input(tmp_path);root=tmp_path/'cache';root.mkdir();keep=root/'user-notes.pycad';keep.write_text('keep')
 for i in range(12):source.write_bytes(str(i).encode());store(root,source,policy,digest_source(source),raw)
 assert len(list(root.glob('*.pycad')))==11 and keep.read_text()=='keep'

def test_cache_workers_and_cancel(main_window,tmp_path):
 from pycad.desk_jobs import run
 source,raw,policy=cache_input(tmp_path);root=str(tmp_path/'cache');value=run(main_window,'cache_lookup',dict(root=root,source=str(source),policy=policy));assert value['hit'] is False
 def cancel():
  for w in QApplication.topLevelWidgets():
   if isinstance(w,QProgressDialog):w.cancel()
 QTimer.singleShot(20,cancel);assert run(main_window,'cache_lookup',dict(root=root,source=str(source),policy=policy)) is None

def test_import_cache_hit_avoids_uncached_reader(main_window,tmp_path,monkeypatch):
 from pycad import import_cache
 from pycad.appsettings import get_settings
 source,raw,policy=cache_input(tmp_path);root=tmp_path/'cache';monkeypatch.setattr(import_cache,'folder',lambda:root);monkeypatch.setattr(import_cache,'signature',lambda mode:policy);get_settings().setValue('imports/cache_enabled',True);calls=[]
 def reader():calls.append(1);return Document()
 first=import_cache.load(main_window,source,'auto',reader);second=import_cache.load(main_window,source,'auto',reader);assert first is not None and second is not None and len(calls)==1
 get_settings().setValue('imports/cache_enabled',False);import_cache.load(main_window,source,'auto',reader);assert len(calls)==2

def test_overlap_cycle_tab_and_reverse(main_window):
 from pycad.selection_cycle import cycle,hits
 d=main_window.document;a=LineEntity(Point(0,0),Point(10,0));b=LineEntity(Point(0,0),Point(10,0));h=HatchEntity([Point(-1,-1),Point(11,-1),Point(11,1),Point(-1,1)],pattern='SOLID');d.entities=[a,b,h];d.sync_associative();main_window.current_world_pos=(5,0);main_window.set_tool('SELECT');assert hits(d,Point(5,0),1)==[a,b,h]
 before=document_to_dict(d);cycle(main_window);assert main_window.canvas.selected_entities==[a];cycle(main_window);assert main_window.canvas.selected_entities==[b];cycle(main_window,True);assert main_window.canvas.selected_entities==[a]
 key=QKeyEvent(QEvent.Type.KeyPress,Qt.Key.Key_Tab,Qt.KeyboardModifier.NoModifier);assert main_window.route_viewport_key(main_window.canvas,key);assert main_window.canvas.selected_entities==[b];assert document_to_dict(d)==before
 main_window.command_line.setText('L');assert not main_window.route_viewport_key(main_window.canvas,QKeyEvent(QEvent.Type.KeyPress,Qt.Key.Key_Tab,Qt.KeyboardModifier.NoModifier))

def test_cycle_excludes_locked_hidden_and_invalidates(main_window):
 from pycad.selection_cycle import cycle
 d=main_window.document;d.layers.add_layer('Locked');d.layers.set_locked('Locked',True);a=LineEntity(Point(0,0),Point(10,0));b=LineEntity(Point(0,0),Point(10,0),layer='Locked');d.entities=[a,b];d.sync_associative();main_window.current_world_pos=(5,0);cycle(main_window,True);assert main_window.canvas.selected_entities==[a]
 d.entities=[];d.sync_associative();cycle(main_window);assert main_window.canvas._cycle_items==[]

def test_palette_searches_alias_and_skips_planned(main_window):
 from pycad.command_palette import entries,filter_entries
 records=entries(main_window);assert any('LINE' in r['label'] for r in filter_entries(records,'line'));assert filter_entries(records,'Ctrl+Shift+P')==[] # self-action excluded
 assert all('planned' not in r['detail'].lower() for r in records if r['label'].endswith(' · LINE'))
 assert filter_entries([dict(search='Line LINE L draw',enabled=True)],'line l')

def test_cleanup_duplicates_styles_protected_and_undo(main_window):
 d=main_window.document;a=LineEntity(Point(0,0),Point(10,0));b=LineEntity(Point(10,0),Point(0,0));different=LineEntity(Point(0,0),Point(10,0),linetype='DASHED');zero=LineEntity(Point(1,1),Point(1,1));d.entities=[a,b,different,zero];d.blocks['Unused']=BlockDefinition('Unused',[LineEntity(Point(0,0),Point(1,0))]);d.layers.add_layer('UnusedLayer');d.sync_associative();before=document_to_dict(d);plan=e.cleanup_plan(d);keys={(r['kind'],r['name']) for r in plan['rows']};assert ('Object',b.id) in keys and ('Object',different.id) not in keys and ('Object',zero.id) in keys and ('Block','Unused') in keys
 e.apply_cleanup(d,plan,[('Object',b.id),('Object',zero.id),('Block','Unused'),('Layer','UnusedLayer')]);assert d.entities==[a,different] and 'Unused' not in d.blocks;assert d.undo_stack.index()==1;d.undo_stack.undo();assert document_to_dict(d)==before;d.undo_stack.redo();assert len(d.entities)==2

def test_cleanup_stale_rejected_before_changes(main_window):
 d=main_window.document;a=LineEntity(Point(0,0),Point(0,0));d.entities=[a];plan=e.cleanup_plan(d);d.entities.append(LineEntity(Point(0,0),Point(1,0)));before=document_to_dict(d)
 with pytest.raises(ValueError,match='changed'):e.apply_cleanup(d,plan,[('Object',a.id)])
 assert document_to_dict(d)==before

def test_cleanup_protects_block_dependencies_and_metadata(main_window):
 d=main_window.document;d.blocks['Child']=BlockDefinition('Child',[LineEntity(Point(0,0),Point(1,0))]);d.blocks['Parent']=BlockDefinition('Parent',[BlockReferenceEntity('Child',Point(0,0))]);d.entities=[BlockReferenceEntity('Parent',Point(0,0))];d.sync_associative();assert not any(r['kind']=='Block' for r in e.cleanup_plan(d)['rows'])
 d.entities=[];d.sync_associative();plan=e.cleanup_plan(d);before=document_to_dict(d)
 with pytest.raises(ValueError):e.apply_cleanup(d,plan,[('Block','Child')])
 assert document_to_dict(d)==before

def test_recovery_auto_restores_copy_and_keeps_snapshot(main_window,tmp_path):
 from pycad import appsettings
 from pycad.document_tabs import save_recovery
 d=main_window.document;d.undo_stack.push(AddEntityCommand(d,LineEntity(Point(0,0),Point(10,0))));save_recovery(main_window);base=Path(appsettings.RECOVERY_PATH);raw=base.read_bytes();d.entities=[];d.mark_saved();appsettings.get_settings().setValue('recovery/automatic_restore',True)
 assert e.recover_startup(main_window);assert len(main_window.document.entities)==1 and main_window.document.filepath is None and main_window.document.dirty;assert base.read_bytes()==raw

def test_recovery_debounce_and_clean_save(main_window):
 d=main_window.document;d.undo_stack.push(AddEntityCommand(d,LineEntity(Point(0,0),Point(1,0))));e.schedule_recovery(main_window);assert main_window._recovery_debounce.isActive();d.mark_saved();e.reconcile_saved_recovery(main_window)

def test_history_identical_snapshot_deduplicates(qapp,tmp_path,monkeypatch):
 from pycad import recovery_history as h
 monkeypatch.setattr(h,'folder',lambda:tmp_path);raw=json.dumps(document_to_dict(Document())).encode();a=h.store_bytes(raw,'same');b=h.store_bytes(raw,'same');assert a['file']==b['file'] and len(h.entries())==1

def test_batch_independent_errors_existing_and_cancel(qapp,tmp_path):
 out=tmp_path/'out';out.mkdir();(out/'a.dxf').write_text('existing');sources=[tmp_path/(name+'.pycad') for name in ('a','bad','good','later')]
 for path in sources:path.write_text('source')
 def load(path):
  if path.stem=='bad':raise ValueError('bad drawing')
  return Document()
 calls=[]
 def export(doc,stage,kind,spaces):stage.write_text('exported');calls.append(1);return dict(warnings=['test notice'])
 report=e.batch(None,sources,out,'DXF',loader=load,exporter=export);assert [r['status'] for r in report['rows']]==['Skipped existing output','Failed','Completed','Completed'];assert (out/'a.dxf').read_text()=='existing' and (out/'good.dxf').read_text()=='exported' and Path(report['report_path']).is_file();assert not list(out.glob('.pycad-batch-*'))
 cancelled=e.batch(None,[tmp_path/'fresh.pycad',tmp_path/'unrun.pycad'],out,'Native',loader=load,exporter=lambda *args:None);assert [r['status'] for r in cancelled['rows']]==['Cancelled','Not run / cancelled'] and not (out/'fresh.pycad').exists()

@pytest.mark.parametrize('kind',['Native','DXF','PDF'])
def test_real_batch_export_worker(main_window,tmp_path,kind):
 source=tmp_path/'source.pycad';d=Document();d.entities=[LineEntity(Point(0,0),Point(100,0))];save_project(d,source);before=source.read_bytes();report=e.batch(main_window,[source],tmp_path/'out',kind);assert report['rows'][0]['status']=='Completed',report;output=Path(report['rows'][0]['output']);assert output.stat().st_size>0 and source.read_bytes()==before

def test_reference_diagnostics_and_font_substitution(main_window,tmp_path):
 from pycad.geometry import BlockDefinition
 d=main_window.document;d.blocks['Missing']=BlockDefinition('Missing',[],source_filepath=str(tmp_path/'missing.dxf'));rows=e.reference_report(d);assert any(r['kind']=='Drawing' and r['status']=='Missing' for r in rows);before=copy.deepcopy(d.textstyles);e.substitute_font(d,'Standard','Serif');assert d.textstyles['Standard']['font_family']=='Serif';d.undo_stack.undo();assert d.textstyles==before

def test_performance_groups_and_hub(main_window):
 from pycad.efficiency_ui import EfficiencyDialog,commands,NAMES
 c=main_window.canvas;c._paint_samples=[dict(kind='full redraw',ms=100),dict(kind='navigation preview',ms=1)];value=e.dashboard(main_window.document,c);assert value['timing_groups']['full redraw']['median_ms']==100 and value['timing_groups']['navigation preview']['median_ms']==1
 d=EfficiencyDialog(main_window);assert d.stack.count()==8 and set(NAMES)<=commands(main_window).keys();d.close()

def test_cache_invalid_native_even_when_hash_matches(qapp,tmp_path):
 from pycad.import_cache import lookup,store,digest_source
 source,raw,policy=cache_input(tmp_path);root=tmp_path/'cache';key=store(root,source,policy,digest_source(source),raw)['key'];bad=b'{"format":"not native"}';(root/(key+'.pycad')).write_bytes(bad);meta=root/(key+'.json');value=json.loads(meta.read_text());value['sha256']=hashlib.sha256(bad).hexdigest();meta.write_text(json.dumps(value));assert not lookup(root,source,policy)['hit']

def test_palette_executes_selected_command(main_window):
 from pycad.command_palette import show
 from PyQt6.QtTest import QTest
 from PyQt6.QtWidgets import QLineEdit
 def choose():
  d=QApplication.activeModalWidget();search=d.findChild(QLineEdit);search.setText('LINE HOME DRAW');QTest.keyClick(search,Qt.Key.Key_Return)
 QTimer.singleShot(20,choose);show(main_window);assert main_window.current_tool.name=='LINE'

def test_batch_worker_cancel_no_output_or_temporary_files(main_window,tmp_path):
 def cancel():
  for widget in QApplication.topLevelWidgets():
   if isinstance(widget,QProgressDialog):widget.cancel()
 QTimer.singleShot(20,cancel);report=e.batch(main_window,[tmp_path/'input.dwg'],tmp_path/'out','PDF',loader=lambda path:Document());assert report['rows'][0]['status']=='Cancelled' and not (tmp_path/'out/input.pdf').exists() and not list((tmp_path/'out').glob('.pycad-batch-*'))

def test_overlapping_choice_list_changes_selection_only(main_window,monkeypatch):
 from pycad.selection_cycle import choose
 from PyQt6.QtWidgets import QInputDialog
 a=LineEntity(Point(0,0),Point(10,0));b=LineEntity(Point(0,0),Point(10,0));main_window.document.entities=[a,b];main_window.document.sync_associative();main_window.current_world_pos=(5,0);before=document_to_dict(main_window.document);monkeypatch.setattr(QInputDialog,'getItem',lambda parent,title,label,items,*args:(items[1],True));choose(main_window);assert main_window.canvas.selected_entities==[b] and document_to_dict(main_window.document)==before

def test_recovery_setting_retains_question_mode(main_window,monkeypatch):
 from pycad import appsettings
 monkeypatch.setattr(appsettings,'recovery_file_exists',lambda:True);appsettings.get_settings().setValue('recovery/automatic_restore',False);assert e.recover_startup(main_window) is False

@pytest.mark.parametrize('association',['dimension','hatch'])
def test_cleanup_protects_legacy_association(qapp,association):
 from pycad.geometry import DimensionEntity
 from pycad.precision_edit import protected_ids,guard
 d=Document();a=LineEntity(Point(0,0),Point(10,0));b=LineEntity(Point(0,0),Point(10,0))
 linked=DimensionEntity(Point(0,0),Point(10,0),Point(5,2),source_line_id=b.id) if association=='dimension' else HatchEntity([Point(0,0),Point(10,0),Point(10,10)],source_entity_id=b.id)
 d.entities=[a,b,linked]
 assert b.id in protected_ids(d)
 assert not any(r['kind']=='Object' and r['name']==b.id for r in e.cleanup_plan(d)['rows'])
 with pytest.raises(ValueError):guard(d,[b])
