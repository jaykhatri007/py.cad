# PY.cad 16.35 — drafting tools

Open **Workflow → Drafting tools**, type `DRAFTINGTOOLS`, or search Ctrl+Shift+P.
The compact panel provides all six additions. Existing drafting commands remain available.

| Command | What it does |
| --- | --- |
| POLYEDITOR | Join lines/arcs/open polylines; close/open, reverse, simplify, uniform width, arc/vertex segment editing |
| TRIMEXTEND | Multiple selected cutters, picked target or crossing fence, reviewed result |
| HATCHBOUNDARIES | Recreate every stored outer/island loop, bulk hatch settings, endpoint gap diagnostics and repair preview |
| DRAWSEARCH | Literal text, placed attributes, layer, object ID and block-name search; checked text/attribute replacement |
| DRAWINGTEMPLATES | Settings-only or complete templates; unsaved copies; local default for New |
| SHORTCUTREFERENCE | Search actions/commands/aliases/shortcuts; persistent edits, conflicts and reset |

## Reviewed edits

Select model objects before opening a page. Build a proposal, toggle the original/proposal in the review window, then Apply or Cancel. Apply is one Undo step. Drawing changes invalidate stale proposals. Locked/hidden objects cannot be changed. Geometry that participates in groups, constraints or managed associations is rejected by the polyline and reviewed trim tools; use its specialized editor.

Polyline Join accepts one connected, unbranched chain of equal-style, equal-width lines/arcs/open polylines. Simplify removes only nearly collinear forward straight vertices within the chosen drawing-unit tolerance; it preserves curved segments. Reverse preserves signed bulges. Opening removes the closing segment. Closing adds a straight closing segment. Width is a single nonnegative model-unit stroke width, preserved in native files, clones, scale operations and DXF constant-width polylines. Variable start/end segment widths are not implemented. Existing variable-width DXF data cannot be promised a lossless roundtrip.

Native schema is now **17**, and this reader also accepts schemas 1–16. Keep backups before editing an older file; older PY.cad readers cannot read schema 17. Native and DXF exports preserve constant width; polygon offset/explode and other conversions should be reviewed for the intended result.

## Trim and extend

Select multiple line/arc/circle/polyline cutting edges. Start a picked-target operation or draw a fence with at least two points, then Enter to review. Trim supports line/arc/circle targets; extend supports line/arc targets. A fence processes each crossed target once at its first crossing. Cutters are treated as infinite supporting lines/circles. Curve sampling is used to identify fence crossings; actual trim/extend intersections use the existing analytic engine. Existing ordinary TRIM also handles polyline targets. The new reviewed fence tool does not claim every AutoCAD trim mode.

## Hatches and gaps

Select one or more hatches to apply a shared HatchDialog configuration. Their outer loops, islands and source links remain intact. Recreate Boundaries creates independent closed polylines for all stored loops; it leaves the hatch intact. Gap scanning reports nearby, noncoincident endpoints of selected lines/open polylines, with distances and IDs. Locate a result or review a straight boundary repair. It is an endpoint diagnostic, not a proof that arbitrary curved boundaries are watertight.

## Search

Search top-level model text, placed INSERT attribute values, layer names, IDs and block names with case/whole-word options. Hidden/locked matches are reported, but only editable matches can be selected or replaced. Check text/attribute results and review replacement. Replacement text is literal (backslashes are not regex substitutions). Replacing a rich text object converts it to plain text so stale formatting markup cannot override the new value. Layer/ID/block-name results are locate-only. Nested definition internals are excluded.

## Templates

Save a `.pycadt` or `.pycad` data file. Settings-only copies preserve units, layers, styles, layouts, title-block metadata, plot presets, layer states and saved views, while excluding model objects, block definitions, underlays, constraints and managed project links. Complete templates include geometry and project data. Choose a local default for New, or reset New to blank. Every opened template is an independent unsaved drawing; save it to a new drawing filename. Missing/invalid default templates show a warning and open a blank drawing. Referenced block paths are made absolute relative to their source; templates do not embed unrelated external files.

## Shortcuts

Search by command, alias, action label or key sequence. Edit an action row; conflicting/prefix shortcuts and bare typing letters are rejected. Changes persist locally. Reset restores the application's built-in action shortcuts. Command aliases use the existing `ALIAS=COMMAND` editor, now supporting all registered canonical command routes; canonical command names are reserved. Clear alias lines to return to built-ins. Workspace presets can still override the active shortcut layout.

## Installation and validation scope

Use the included native Linux `.run`, Windows `.exe`, or macOS universal ZIP. Linux installers update the managed install; the source ZIP also supports `bash start.sh` on Ubuntu. The source/legal/logo files remain included and no application dependencies were added for these features.

Regression, Linux managed-install update, recovery, installed desktop launch and real-project measurements are recorded in `VALIDATION_16_35*` and the release report. Windows and macOS binaries are cross-built and payload-checked here; running them on those native hosts and physical GPU testing remain unverified.
