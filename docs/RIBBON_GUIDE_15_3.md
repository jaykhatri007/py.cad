# PyCAD 15.3 workflow guide

Type a command from the drafting viewport or any model pane and press Enter or
Space. Ribbon buttons use the same command dispatcher. Esc cancels. Idle Enter
repeats the last command. Tab completes names. Menus retain the earlier commands.

## Ribbon and navigation

Home, Insert, Annotate, Parametric, View, Manage and Output follow the supplied
spreadsheet. Hover an icon for its name, command and support scope. Small down
arrows reveal additional tools. Compact toggles the one-row icon layout. A
horizontal scrollbar appears if the tools exceed the available width.

View → Navigation includes pan, window/realtime zoom, orbit and camera presets.
Orbit and presets use the embedded model viewport. The in-viewport rail/cube
remain available. `ZOOMWINDOW` picks two corners in drafting. `ZOOMREALTIME`
uses left-button vertical dragging in drafting; Esc ends it. `XRAY` uses
transparent shaded model faces. It is a display style, not a material renderer.

Manage → Tool coverage (also View → Tool Palettes) searches every listed tool,
its command, location, status and limits. Double-click an available row to run
it. Disabled ribbon actions have no hidden implementation.

## Drafting additions

| Command | Workflow and scope |
| --- | --- |
| `STRETCH` / `S` | Pick two crossing-box corners, a base point and a target point. LINE endpoints and polyline/spline vertices inside the box move; wholly enclosed supported entities translate. Locked/hidden layers are excluded. One undo step. No solid stretching. |
| `LAYISO`, `LAYOFF` | Preselect objects, then isolate or turn off their layers. Isolation makes a selected layer current. |
| `LAYUNISO`, `LAYON` | Restore the last session isolation visibility/current layer, or turn all layers on. LAYON does not thaw frozen layers. Layer changes are undoable. |
| `LAYMCH` | Preselect target objects, start the command, then pick the source object whose layer should be used. |
| `MTEXT` / `MT` | Pick a text insertion point and enter plain multiline text in the editor. No inline fonts, rich formatting or automatic wrapping. DXF export uses MTEXT. |
| `CENTERMARK` | Pick a circle/arc. Creates two ordinary DASHDOT lines through its center. Not associative. |
| `CENTERLINE` | Pick two parallel nonzero lines. Creates their static midline, handling reversed line directions. |
| `TABLE` | Enter CSV/tab-separated rows, then pick the top-left insertion point. Creates an editable block of lines/text. Maximum 200 rows × 30 columns; long values shrink to fit. No formulas or linked cells. |
| `TABLESTYLE` | Set width,height,text-height defaults for new static tables. These are application defaults, not named CAD table styles. |
| `LEADER`, `MLEADER` / `ML` | Pick arrow tip and text landing, then enter text. Creates a static block with one leader branch. Additional/removable associative branches remain planned. |
| `DIMCONTINUE` / `DC` | Pick a linear dimension, then click additional extension origins. New independent dimensions continue from the previous endpoint. Enter/Esc finishes. |
| `DIMBASELINE` / `DB` | Pick a linear dimension, then additional origins. Uses the original first point, with 5 drawing units between dimension lines. Enter/Esc finishes. |
| `MEASURERADIUS` | Pick a circle/arc; reports radius and diameter in command history. |
| `MEASUREANGLE` | Pick vertex, first ray point and second ray point; reports the smaller included angle. |
| `QUICKMEASURE` | Click entities for supported lengths, radii, areas and bounding-box sizes. Esc finishes. No continuous hover overlay. |
| `LWEIGHT` | Choose a standard lineweight for selected objects' layers, or the current layer if nothing is selected. Affects all objects on those layers. |

New tables/leaders are normal named blocks: `BEDIT` edits their constituent
geometry. They do not become native associative AutoCAD TABLE/MLEADER entities.
Center annotations do not move or resize when the original source is edited.
Save native `.pycad` files; DXF interchange has the documented approximations.

## Data, references and customization

`WBLOCK` writes selected objects and their nested block dependencies to a native
project or 2D DXF. Coordinates are preserved. It excludes unrelated model
objects, layouts and saved 3D extrusions. Layer and dimension-style tables are
retained. Exporting selected profile geometry does not export its solid feature.

`DATAEXTRACTION` exports a CSV of selected editable objects, or all visible model
objects if there is no editable selection. `DATATABLE` places the same data as a
static table block. Measurements are in drawing units; area is in square units.
CSV strings beginning with formula characters are escaped for spreadsheet use.

`DXFATTACH` attaches cached 2D DXF geometry; nested blocks are flattened inside
the reference definition. `XREF` lists reference paths/status and reloads the
selected reference with undo support. Source warnings remain visible. Missing
references keep cached geometry. DWG opening through the optional ODA converter
does not imply support for linked DWG references.

`ALIASEDIT` accepts lines such as `ST=STRETCH` and `CM=CENTERMARK`. Aliases persist,
cannot replace full command names, and must target an available command.
Built-in abbreviations can be overridden; removing a custom override restores
the built-in abbreviation. Full CUI and action recording remain planned.

## Output

`NEWLAYOUT` creates and selects a paper sheet. `PAGESETUP` changes its page width
and height in millimetres; existing viewports keep their positions and scales.
Check their fit after changing paper size. The Model PDF page is A4 landscape.

`PLOT` / `EXPORTPDF` uses the existing vector PDF exporter. `PLOTPREVIEW` renders
the current space with the same exporter. `BATCHPLOT` writes a ZIP containing
one PDF per paper layout, or Model if there are no layouts. Direct printer
selection and professional plot-style tables are not implemented.

`EXPORTDXF` exports supported 2D content, with warnings; saved extrusion models
are rejected to avoid silent loss. `EXPORTSTL` requires one selected closed
profile and an extrusion height plus optional CadQuery. Existing saved solids
can also be exported from the embedded model browser. It is not a general FBX,
DWF or arbitrary B-rep exporter.

`ETRANSMIT` creates a local ZIP with `drawing.pycad`, direct DXF reference files
and a manifest. Extract the entire package together; reference paths reload
relative to the extracted drawing. Missing files abort packaging and leave any
existing output intact. Nested external dependencies/fonts are not gathered.
Nothing is emailed or uploaded by this command.
