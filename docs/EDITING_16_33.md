# PY.cad 16.33 — precision editing and workspace tools

Open **Workflow → Editing**, type `EDITING`, or search the command palette with
Ctrl+Shift+P. Six pages extend the existing editing and navigation tools.

| Command | Function |
| --- | --- |
| SELECTFILTER | Combined property filters and selection set operations |
| ADVGRIPS | Multiple-vertex stretch, polyline segment operations and arc reshaping |
| BOUNDARYREPAIR | Staged small-gap/duplicate boundary repair with approval and Undo |
| DRAFTINGAIDS | Temporary tracking references and viewport distance/angle locks |
| WORKSPACEPRESETS | Local ribbon/panel/shortcut/color/drafting presets |
| DRAWINGHEALTH | Cancellable read-only geometry/reference/cleanup diagnosis |
| TRACKPOINT | Pick a temporary reference directly in the viewport |
| CLEARTRACKING | Clear all temporary references and drafting locks |

## Selection filters

Combine type, layer, stored color, block name, linetype, text substring and
minimum/maximum curve length with AND. Blank length fields mean unrestricted;
lengths use drawing units. Supported measured kinds are lines, arcs, circles
and polylines. Text matching ignores case. Colors match stored values, so
BYLAYER is distinct from an explicit color that happens to look identical.

Search all editable model objects or the current selection. Preview reports the
number of matches without changing selection. Apply uses Replace, Add, Subtract
or Intersect. Hidden, isolated-away and locked objects remain excluded. Blocks
remain top-level objects; this does not select their nested child geometry.

## Advanced grips

Select lines/polylines/rectangles before opening ADVGRIPS. Refresh selected grips,
check any combination of vertices, then stretch by dx,dy or choose the viewport
stretch. Viewport stretch asks for a base and target point and draws a ghost of
the selected geometry. Absolute x,y and relative @dx,dy entries are accepted.
Esc cancels. A separate original/proposal preview still requires Apply; that
creates one Undo step. Coordinates, styles, IDs and existing bulges are retained.
Linked sources keep their IDs so existing associative tools can update them.

For one polyline, use a zero-based segment index to insert an exact midpoint,
remove the start vertex, straighten the segment or set a signed arc angle.
Splitting an arc preserves its path with two half-angle bulges. A rectangle with
an inserted vertex becomes a general polyline with the same ID. Removing a vertex
between curved segments is rejected until those segments are straightened.

For one ARC, choose Reshape through viewport point. The ghost follows the cursor;
click the point the arc should pass through, then review it. The endpoint
positions remain fixed, although their start/end order can reverse to represent
the chosen counterclockwise arc. Collinear points are rejected. Existing ordinary
single-grip dragging continues to work.

All previews validate a complete native candidate. Apply rejects intervening
model changes and targets that are no longer editable. Repairing geometry does
not rewrite the original imported DWG/DXF file; save/export normally when ready.

## Boundary repair

Select one straight polyline or one closed chain of straight lines. Enter a small
gap tolerance in drawing units. Preview can close a near end gap, remove repeated
adjacent vertices, merge endpoint clusters and remove duplicate/zero segments
when joining a line chain. Every point in an endpoint cluster must remain within
the tolerance of every other point; ambiguous/transitive bridges are rejected.
The result must enclose a simple nonzero area.

Apply replaces the selected geometry with a closed polyline, preserving the
first source ID and drawing styles; one Undo restores the original objects.
Styles must match across a line chain. Groups, managed/associated source geometry
and externally linked geometry are protected from this replacement operation.
Use the existing source-edit tools when changing those boundaries.

Crossings, touching/non-simple loops, adjacent backtracking, branches, separate
loops, collapsed short segments and unresolved gaps are rejected rather than
silently trimmed. Curved boundaries use the arc/segment tools before straight
boundary repair. Detailed line-chain repair supports up to 2,000 selected lines;
this is an inspection-work limit, not a drawing import/size limit. Repair separate
regions individually in a large drawing.

## Drafting aids

TRACKPOINT picks an object-snapped temporary reference without adding geometry.
You can also add x,y coordinates through the page. During LINE, PLINE and WALL
mouse drafting, nearby horizontal/vertical alignments to those references show
tracking guides and Track X / Track Y labels. Normal object snaps take precedence
over tracking; explicit distance/angle locks override the hovered object snap
once the tool has an anchor. Distance is in drawing units and angle in degrees.

The same adjustment is used for viewport hover and click, so committed points
match the preview. Object-snap labels are displayed for supported drafting tools.
Typed explicit coordinates keep their normal tool behavior. These are temporary
cursor aids, not persistent geometric constraints or a replacement solver.

References/locks stay available while switching tools in the same document.
CLEARTRACKING clears both. Switching to another document resets them. Up to 20
temporary references are supported; none enters saved native geometry.

## Workspace presets

Save a baseline before customizing. A local preset captures panel docking and
visibility, window geometry, ribbon tab/compact mode, UI colors, action shortcuts,
grid/snap/ortho settings, grid spacing, snap radius and snap modes. Customize an
action shortcut through the page, then save the workspace to retain it. A shortcut
already assigned to another action must be cleared there before reassignment.

Presets live in application preferences, not native drawing files. Restore does
not modify model geometry, drawing file paths, graphics drivers or AI credentials.
Qt docking/geometry data is validated; rejected docking states roll back. Different
application versions or screen arrangements can change the available dock layout.
This is a workspace capture system, not a ribbon-command layout designer.

## Drawing health

Run the cancellable worker scan. It reports native validation failures, zero-length
lines, closed straight-boundary crossings/backtracking, missing associations,
objects far from the median drawing center, and cleanup candidates. The UI adds
missing drawing/CSV references and unavailable font-family diagnostics. Embedded
image/PDF underlays do not require the original external image path.

The distance threshold is in drawing units. Distant geometry may be intentional,
especially survey coordinates; the scan never deletes or moves it. Curved and
very large boundaries are not exhaustively checked by this straight-boundary
inspection. Boundaries above 2,000 vertices receive an explicit detailed-check
skipped notice. Locate highlights current editable sources; JSON export retains
the report. Rerun the scan after edits because a report is a snapshot.

Boundary repair, Cleanup preview and References open the existing reviewed edit
workflows. No automatic fix is applied by a scan. Native validation failure may
stop detailed checks and return the error for review. File import and drawing
size limits are not changed by these diagnostic bounds.

## Compatibility and scope

Native schema remains **16**, as in 16.32; schemas 1–15 remain readable. The new
editing results use existing entity types. Workspace presets and temporary aids
are application state, not executable native data. No application dependencies,
logo or licensing terms are changed. Windows/macOS installers are built together
with Linux; see VALIDATION_16_33.txt for the native-host checks actually run.
