"""Guided lessons and an editable sample copy, independent of users' drawings."""
from pathlib import Path
LESSONS=[
 ('Drafting and snaps','LINE',['Open the sample copy or a new drawing.','Turn on the endpoint/intersection snaps in drafting options.','Draw a line using two viewport points; try @1000,0 coordinate entry.','Undo, then compare tracking with TRACKPOINT and DRAFTINGAIDS.']),
 ('Hatches and multiple areas','HATCH',['Select or draw two closed boundaries.','Open HATCH and choose pattern, scale, angle and island settings.','Pick both areas, then press Enter to finish.','Double-click a hatch to edit its settings; use Undo to compare.']),
 ('Sheets and publishing','PRODUCTION',['Choose Sheet sets and create or inspect the sample layouts.','Edit title fields and save an ordered set.','Choose Preview / publish and select that set.','Inspect the generated PDF before saving it.']),
 ('BOQ source evidence','BOQTRACE',['Open the architectural sample copy.','Recalculate / capture source evidence.','Click a quantity row to highlight its source geometry.','Edit a room boundary or a rate and check freshness again.']),
 ('AI reviewed drafting','AIPREVIEW',['Start with the sample or a new millimetre drawing.','Use the local instruction: room 6m x 4m at 0,0.','Preview the proposal, inspect exact actions and changes overlay.','Cancel first, then repeat and Apply; confirm Undo restores the drawing.']),
 ('Properties, blocks and standards','COORDINATION',['Select two differently colored objects and inspect mixed Properties.','Check one shared field and apply an explicit value; Undo it.','Browse Furniture blocks; favorite and place one with a preview.','Capture a project standard, preview its changes in another drawing and apply it.'])]

def open_sample(mw):
 from .native_io import load_project
 path=Path(__file__).resolve().parents[1]/'examples/coordination_studio.pycad';doc=load_project(path);doc.filepath=None;doc._force_dirty=True;mw.drawing_tabs.add_document(doc);mw.refresh_document_ui();return doc
