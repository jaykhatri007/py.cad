"""Desktop acceptance entry point, executable on real Windows and Ubuntu hosts."""
import argparse,json,sys,tempfile,logging
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


_APPLICATION = None

def run():
    global _APPLICATION
    from PyQt6.QtWidgets import QApplication
    from PyQt6 import QtPdf,QtSvg,QtOpenGLWidgets
    from pycad.main_window import MainWindow
    from pycad.pro_ui import ProDialog
    from pycad.document import Document
    from pycad.geometry import RectangleEntity,Point,HatchEntity
    from PyQt6.QtCore import Qt
    from pycad.native_io import save_project,load_project
    from pycad.plotting import export_pdf
    from pycad.room_planner import plan
    from pycad.automation import apply_proposal
    from pycad._version import __version__
    errors=[]
    class Capture(logging.Handler):
        def emit(self,record):
            if record.levelno>=logging.ERROR:errors.append(record.getMessage())
    handler=Capture();logging.getLogger("pycad").addHandler(handler)
    _APPLICATION=QApplication.instance() or QApplication([])
    app=_APPLICATION
    with tempfile.TemporaryDirectory(prefix='pycad-acceptance-') as temp:
        p=Path(temp);doc=Document();apply_proposal(doc,plan([dict(name='Office',width=6000,depth=4000)]));save_project(doc,p/'drawing.pycad');restored=load_project(p/'drawing.pycad');assert len(restored.entities)==len(doc.entities);export_pdf(restored,str(p/'drawing.pdf'));assert (p/'drawing.pdf').stat().st_size>100
        w=MainWindow();d=ProDialog(w);assert d.stack.count()==10;w.show();app.processEvents();d.close()
        w.document.entities=[RectangleEntity(Point(0,0),Point(10,10)),RectangleEntity(Point(20,0),Point(30,10))];w.canvas.zoom_extents();w.set_tool('HATCH',hatch_configured=True);tool=w.current_tool;tool.options['pattern']='SOLID'
        tool.on_click(5,5,'',Qt.MouseButton.LeftButton.value);tool.on_click(25,5,'',Qt.MouseButton.LeftButton.value);tool.on_key(Qt.Key.Key_Return)
        assert len([e for e in w.document.entities if isinstance(e,HatchEntity)])==2
        w.document.undo_stack.undo();assert len(w.document.entities)==2
        from pycad.productivity_ui import ProductivityDialog
        from pycad import productivity as productivity
        from pycad.geometry import LineEntity,BlockDefinition,PolylineEntity,TextEntity
        from pycad.pdf_vectors import import_page
        from pypdf import PdfWriter
        from pypdf.generic import DecodedStreamObject,NameObject
        panel=ProductivityDialog(w);assert panel.stack.count()==8;panel.close()
        productivity.create_table(w.document,'AcceptanceCosts',[['2','3','=A1*B1']]);assert any(e.kind=='TEXT' and e.text=='6' for e in w.document.blocks['AcceptanceCosts'].entities)
        productivity.create_table(w.document,'AcceptanceBOQ',[['Description','Unit','Quantity','Rate','Cost']],schedule='BOQ')
        w.document.blocks['AcceptanceBase']=BlockDefinition('AcceptanceBase',[LineEntity(Point(0,0),Point(10,0))])
        productivity.define_parameters(w.document,'AcceptanceWide',dict(base='AcceptanceBase',width_name='Width',height_name='Height',base_width=10.,base_height=10.,width=20.,height=10.,rotation=0.,threshold_x=0.,threshold_y=0.));assert w.document.blocks['AcceptanceWide'].entities[0].p2.x==20
        east,north=productivity.utm(75,0,43,True);assert abs(east-500000)<1e-6 and abs(north)<1e-6
        writer=PdfWriter();page=writer.add_blank_page(100,100);stream=DecodedStreamObject();stream.set_data(b'0 0 m 10 0 l S');page[NameObject('/Contents')]=writer._add_object(stream)
        with (p/'vector.pdf').open('wb') as output:writer.write(output)
        paths,details=import_page(p/'vector.pdf');assert len(paths)==1
        w.canvas.boq_overlay_enabled=True;w.canvas.viewport().update();app.processEvents();assert productivity.overlay(w.document)['status']
        save_project(w.document,p/'productivity.pycad');assert productivity.state(load_project(p/'productivity.pycad'),'tables')['AcceptanceCosts']['cells'][0][2]=='=A1*B1'
        from pycad.efficiency_ui import EfficiencyDialog
        from pycad.efficiency import cleanup_plan,apply_cleanup,batch
        from pycad.command_palette import entries,filter_entries
        efficiency_panel=EfficiencyDialog(w);assert efficiency_panel.stack.count()==8;efficiency_panel.close()
        assert filter_entries(entries(w),'line')
        cleanup_doc=Document();cleanup_doc.entities=[LineEntity(Point(0,0),Point(0,0))];plan=cleanup_plan(cleanup_doc);apply_cleanup(cleanup_doc,plan,[('Object',cleanup_doc.entities[0].id)]);assert not cleanup_doc.entities;cleanup_doc.undo_stack.undo();assert len(cleanup_doc.entities)==1
        batch_result=batch(w,[p/'drawing.pycad'],p/'batch-out','PDF');assert batch_result['rows'][0]['status']=='Completed',batch_result
        from pycad.production_ui import ProductionDialog,staged_pdf
        from pycad.production import save_set,issue_set,refresh_quantities,quantity_status,comparison_overlay
        from pycad.sheets import DEFAULT_PRESET
        from pycad.productivity import schedule_cells
        panel=ProductionDialog(w);assert panel.stack.count()==7
        for i in range(7):panel.list.setCurrentRow(i);app.processEvents()
        panel.close()
        w.document.units='mm';w.document.create_layout('ProductionPlan');save_set(w.document,'Issue',['ProductionPlan']);issue_set(w.document,'Issue','A','Acceptance')
        refreshed=refresh_quantities(w.document);assert quantity_status(w.document)=='Current'
        save_project(w.document,p/'production.pycad');roundtrip=load_project(p/'production.pycad');assert quantity_status(roundtrip)=='Current'
        overlay,changes=comparison_overlay(roundtrip,w.document);assert not changes['changed'] and not changes['added']
        assert staged_pdf(w,['ProductionPlan'],DEFAULT_PRESET,p) is not None
        assert schedule_cells(w.document,'Rooms')[0][0]=='Room'
        from pycad.editing_ui import EditingDialog
        from pycad.editing import filter_entities,boundary_plan,apply
        from pycad.drafting_aids import add_point,configure,state,clear
        from pycad.workspace_presets import capture,restore
        panel=EditingDialog(w);assert panel.stack.count()==6
        for i in range(6):panel.list.setCurrentRow(i);app.processEvents()
        panel.close()
        record=capture(w);restore(w,record);assert filter_entities(w.document,{})
        add_point(w.canvas,Point(10,20));configure(w.canvas,100,30);assert state(w.canvas)['distance']==100;clear(w.canvas)
        repair=Document();repair.entities=[LineEntity(Point(0,0),Point(10,0)),LineEntity(Point(10,0),Point(10,10)),LineEntity(Point(10,10),Point(0,10)),LineEntity(Point(0,10),Point(0,0))];apply(repair,boundary_plan(repair,repair.entities,.01));assert len(repair.entities)==1;repair.undo_stack.undo();assert len(repair.entities)==4
        from pycad.desk_jobs import run as desk_run
        result=desk_run(w,'health',dict(distant=1e6),w.document);assert result is not None and 'rows' in result
        from pycad.coordination_ui import CoordinationDialog
        from pycad.coordination import capture_standard,standard_diff,apply_standard,reference_graph,common_properties,block_preview
        from pycad.tutorials import open_sample
        panel=CoordinationDialog(w);assert panel.stack.count()==6
        for i in range(6):panel.list.setCurrentRow(i);app.processEvents()
        panel.close()
        sample=open_sample(w);assert sample.filepath is None and 'Furniture_Chair' in sample.blocks
        preview=block_preview(sample,'Furniture_Desk');assert preview.entities[0].resolved_entities
        shared=[q for q in sample.entities if q.kind=='INSERT' and q.block_name=='Furniture_Desk'];w.canvas.selected_entities=shared;w.refresh_selection_ui()
        from pycad.coordination import MIXED
        assert w.properties_panel.color.text()==MIXED
        editor=w.properties_panel.shared_editor;row=editor.keys.index('scale');editor.table.item(row,0).setCheckState(Qt.CheckState.Checked);editor.table.item(row,2).setText('1.5');editor.apply();assert all(sample.find_by_id(q.id).scale==1.5 for q in shared);sample.undo_stack.undo()
        profile=capture_standard(sample);profile['textstyles']['Standard']['height']=3.;candidate,changes=standard_diff(sample,profile);assert changes;apply_standard(sample,profile);sample.undo_stack.undo()
        from pycad.desk_jobs import run as desk_job
        measurements=desk_job(w,'stability',dict(repeats=1),sample);assert measurements['original_unchanged'] and not measurements['render_errors']
        from pycad.block_library import BlockLibrary
        browser=BlockLibrary(w);browser.search.setText('Furniture');browser.next_icon();assert browser.list.count()==2;browser.close()
        from pycad.drafting_ui import DraftingDialog
        from pycad import drafting,editing
        panel=DraftingDialog(w);assert panel.stack.count()==6;panel.close()
        draft=Document();draft.entities=[PolylineEntity([Point(0,0),Point(5,0),Point(10,0)],width=2),TextEntity(Point(0,0),'Drafting sample')]
        editing.apply(draft,drafting.polyline_plan(draft,[draft.entities[0]],'Simplify',.01));assert len(draft.entities[0].points)==2 and draft.entities[0].width==2
        rows=drafting.search(draft,'sample',['Text']);editing.apply(draft,drafting.replace_plan(draft,rows,'sample','checked'));assert draft.entities[1].text=='Drafting checked';draft.undo_stack.undo();assert draft.entities[1].text=='Drafting sample'
        template=p/'draft-template.pycad';drafting.save_template(draft,template);assert not drafting.open_template(template).entities
        for s in w.drawing_tabs.sessions:s['doc'].mark_saved()
        w.close()
        from pycad.document_lifecycle import dispose_documents,drain_deferred_deletes
        for widget in app.topLevelWidgets():widget.close();widget.deleteLater()
        dispose_documents();drain_deferred_deletes()
        logging.getLogger("pycad").removeHandler(handler)
        if errors:raise ValueError("Desktop/rendering errors: "+"; ".join(errors))
        return dict(version=__version__,platform=sys.platform,python=sys.version.split()[0],native_project_and_pdf=True,multi_area_hatch=True,desktop_and_ten_workspaces=True,eight_productivity_pages=True,formula_table_native=True,live_BOQ_schedule=True,block_parameters=True,UTM_reference=True,PDF_vectors=True,BOQ_overlay=True,eight_efficiency_pages=True,command_palette=True,reviewed_cleanup_undo=True,batch_export_worker=True,seven_production_pages=True,persistent_sheet_sets=True,source_quantity_evidence=True,publication_preview_pdf=True,six_editing_pages=True,selection_filters=True,reviewed_boundary_undo=True,workspace_capture_restore=True,health_worker=True,six_coordination_pages=True,mixed_properties=True,block_library_preview=True,project_standards_undo=True,tutorial_sample_copy=True,stability_worker=True,six_drafting_pages=True,polyline_width_native=True,reviewed_search_undo=True,data_only_templates=True,physical_gpu_verified=False,runtime=sys.executable)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--report');args=parser.parse_args();value=run();raw=json.dumps(value,indent=2);print(raw)
    if args.report:Path(args.report).write_text(raw+'\n')
