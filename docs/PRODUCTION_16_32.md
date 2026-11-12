# PY.cad 16.32 — drawing production

Open **Workflow → Production** or type `PRODUCTION`. Seven compact pages extend
existing drafting tools. Ctrl+Shift+P also finds the new commands.

| Command | Workflow |
| --- | --- |
| SHEETSETS | Ordered paper-layout sets, numbering, title fields and issue history |
| DRAWCOMPARE | Previous/current native, DXF or DWG comparison, overlay and JSON report |
| PUBLISHPREVIEW | Actual vector PDF preview, ordered set publication and batch plotting |
| ANNOTATIONTOOLS | Paper text/dimension sizing, dimension spacing and viewport multipliers |
| ARCHDRAFT | Walls, hosted doors/windows, rooms and live room-area schedules |
| BOQTRACE | Persisted source quantities, highlighting and freshness checks |
| AIPREVIEW | Drafting chat with validated preview, changes overlay, approval and Undo |

## Sheet sets

Create paper layouts, check and drag them into order, then Save set. Sets belong
to the native drawing, not a separate global project database. Choose All layouts
to add layouts to a replacement set. Title fields edit project, drawing title,
number, revision and author. Renumber applies a prefix and zero-padded sequence
to the checked sheets in their displayed order.

Issue set updates the saved set's title-block revisions and appends a dated
note to its history, as one Undo step. It is a drawing revision log, not a digital
signature or immutable document-control service. Renamed/deleted layouts appear
as missing; repair/resave the set before issuing or publishing it. An issue does
not itself export a PDF. Select that set in Preview / publish to produce it.

## Drawing comparison

Load a previous .pycad, DXF or DWG. The current workspace remains unchanged.
Persistent native IDs identify additions, removals and modifications; nested
block-definition changes and relevant layer/text/dimension-style changes mark
affected instances. Independent DXF/DWG imports can have different IDs and may
appear as remove/add rather than matched geometry. This is identity comparison,
not fuzzy geometric registration or a DWG binary diff.

The separate canvas shows old changed/removed objects in red, current
changed/added objects in green and unchanged current geometry in grey. Before
and after blocks retain separate definitions and text/dimension style libraries.
The overlay is a diagnostic view of model geometry, not a merged editable drawing
or a published sheet comparison. Underlays, external 3D models, per-layout paper
geometry and all annotation/link styling are not independently diffed. Normalize
drawing units before overlaying. Previous/current views remain available. Export
change report writes IDs, definition changes and settings flags as JSON.

## Preview and publishing

Choose Model, all layouts or a saved ordered set, and a plot preset. Preview is
the generated PDF itself, displayed with Qt's PDF renderer. Save this PDF writes
those exact previewed bytes. PDF generation runs in a cancellable worker; a
cancelled preview does not alter the drawing or publish a partial output.

Layouts keep their own physical paper dimensions and viewport scales; the preset
paper size and fit/1:N scale apply to Model output. Monochrome/color, margins,
layer plot flags, existing lineweights and title blocks use the same existing
plot engine. Edit page/plot presets here and layout sizes through the existing
layout tools. This extends existing plotting rather than adding CTB/STB format
compatibility. Batch convert / plot opens BATCHDRAWINGS, which processes multiple
input drawings with cancellation, existing-output protection and per-file results.
It publishes each drawing using that batch tool's supported settings; it does
not automatically apply the active drawing's sheet set to other files.

## Annotation tools

Select editable text; enter paper height in mm and scale denominator N to set
model height = paper height × N / millimetres per drawing unit. Dimensions use
new independent named styles for selected objects, so other users of the original
style remain unchanged. Arrow proportions and the rest of the source dimension
style are retained. These operations each use one Undo step.

Select two or more parallel linear dimensions of the same orientation to space
their dimension lines by a model-unit gap. The lowest projected line stays fixed.
This positions dimension lines; it does not infer a complete collision-free
annotation layout. Existing text/dimension style managers remain available.

Viewport annotation scale is the existing multiplier for text, dimensions and
leaders in paper viewports and PDF. It is separate from physical text sizing;
use 1 to avoid multiplying a size you already set for that viewport scale.
This is not AutoCAD's per-object multi-scale annotative representation system.

## Architecture and area schedules

Wall / walls from lines uses the existing wall tool. Select one architectural
wall to place a door or window at a station with width, height and sill; existing
host, overlap and height validation applies. Use dimensions in the current
physical drawing units. Select a closed boundary to label a room. The room table
and CSV show areas/perimeters in drawing units. Click a room row to locate its
source label.

Place automatic room area schedule creates an ordinary native formula-table
block linked to room records. Existing synchronization updates its values after
room-boundary edits, room creation/removal and unit changes. Physical units
produce m² and m; unitless drawings are explicitly labelled drawing units. Native
save/reopen retains the link. CSV exports are snapshots; the placed native
schedule stays linked. The room planner remains available for a reviewed layout
proposal. These are drafting/measurement tools, not building-code checks.

## BOQ evidence

Recalculate / capture source evidence records each source ID, description,
measurement method, adjusted quantity and unit, plus currency and a timestamp.
Click a row to highlight its current editable source. Check freshness compares
a conservative fingerprint of model geometry/definitions, layers, units and
measurement/model settings with the capture. Editing geometry, rates or relevant
settings makes it outdated. The page checks on entry and on Check freshness;
it does not continuously hash a large drawing in the background.

Native files retain the capture; updating it is undoable. Removed sources remain
visible in old evidence until recalculation, with a clear missing-source message.
The fingerprint may also flag changes that do not affect a particular quantity.
Existing rates, deductions, waste and unmeasured/unpriced notices still apply.
No rates are invented and a current capture is not certification of a complete
or independently verified estimate.

## AI drafting review

Open drafting chat with the instruction entered here. The established local
parser works without a model; an optional configured local/remote provider can
produce whitelisted structured actions. No new service or bundled API key is
required. External model usage still depends on the user's configured service.

Preview / Apply validates the proposal against a staged copy, shows the exact
action list and quantity impacts, and now offers a red/green changes overlay.
Show original restores the before view. Cancel leaves the drawing unchanged;
Apply checks for intervening edits and commits one Undo step. AI does not bypass
approval or execute arbitrary Python/shell commands through this path.

## Native compatibility

New saves use schema **16**, adding validated production records and live room
schedules. This release reads schemas 1–15 as well. Older releases can reject a
schema-16 file; keep a backup before replacing a native project. DXF interchange
does not preserve these native production tables or the full audit history.
The original logo, licenses and legal notices are retained. No new dependencies
are introduced in this release.
