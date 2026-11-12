# Ribbon coverage — PyCAD 15.3.0

Source: `AutoCAD_Tabs_and_Tools.xlsx`, sheet **AutoCAD Tabs & Tools**. All 7 tabs and 29 panel rows are represented. The screenshot supplied with the workbook guided the visual grouping. `etc.` is not treated as a specification of additional unnamed AutoCAD tools.

The catalog contains **149 unique commands** across **158 placements**: **69 available**, **31 limited**, **49 planned**. Counts include pre-existing commands and extra retained tools; they do not mean 100 newly implemented tools.

- **Available**: callable in this build within the existing PyCAD geometry model. This does not imply every AutoCAD command option is supported.
- **Limited**: callable with the scope stated below.
- **Planned**: disabled and unimplemented; shown so the spreadsheet inventory is complete.

Generated from the same `pycad/ribbon_catalog.py` used by the UI. Open Manage → Tool coverage for a searchable version. Read `RIBBON_GUIDE_15_3.md` for workflows and `ROADMAP_15_3.md` for acceptance gates.

## Home / Draw — spreadsheet row 2

Workbook tools: Line, Polyline, Circle, Arc, Rectangle, Hatch, etc.

| Tool | Command | Status | Scope |
| --- | --- | --- | --- |
| Line | `LINE` | Available | Available in the existing PyCAD model; see workflow guide for options. |
| Polyline | `PLINE` | Available | Available in the existing PyCAD model; see workflow guide for options. |
| Circle | `CIRCLE` | Available | Available in the existing PyCAD model; see workflow guide for options. |
| Arc | `ARC` | Available | Available in the existing PyCAD model; see workflow guide for options. |
| Rectangle | `RECTANGLE` | Available | Available in the existing PyCAD model; see workflow guide for options. |
| Hatch | `HATCH` | Available | Available in the existing PyCAD model; see workflow guide for options. |
| Spline | `SPLINE` | Available | Available in the existing PyCAD model; see workflow guide for options. |
| Point | `POINT` | Available | Available in the existing PyCAD model; see workflow guide for options. |
| Ellipse | `ELLIPSE` | Available | Available in the existing PyCAD model; see workflow guide for options. |
| Ray | `RAY` | Available | Available in the existing PyCAD model; see workflow guide for options. |
| Construction line | `XLINE` | Available | Available in the existing PyCAD model; see workflow guide for options. |

## Home / Modify — spreadsheet row 3

Workbook tools: Move, Copy, Stretch, Rotate, Trim, Fillet, Erase, etc.

| Tool | Command | Status | Scope |
| --- | --- | --- | --- |
| Move | `MOVE` | Available | Available in the existing PyCAD model; see workflow guide for options. |
| Copy | `COPY` | Available | Available in the existing PyCAD model; see workflow guide for options. |
| Stretch | `STRETCH` | Limited | Crossing-box stretch of LINE and polyline/spline vertices; fully enclosed supported objects move. No solid stretching. |
| Rotate | `ROTATE` | Available | Available in the existing PyCAD model; see workflow guide for options. |
| Trim | `TRIM` | Available | Available in the existing PyCAD model; see workflow guide for options. |
| Fillet | `FILLET` | Available | Available in the existing PyCAD model; see workflow guide for options. |
| Erase | `ERASE` | Available | Available in the existing PyCAD model; see workflow guide for options. |
| Offset | `OFFSET` | Available | Available in the existing PyCAD model; see workflow guide for options. |
| Mirror | `MIRROR` | Available | Available in the existing PyCAD model; see workflow guide for options. |
| Scale | `SCALE` | Available | Available in the existing PyCAD model; see workflow guide for options. |
| Extend | `EXTEND` | Available | Available in the existing PyCAD model; see workflow guide for options. |
| Chamfer | `CHAMFER` | Available | Available in the existing PyCAD model; see workflow guide for options. |
| Rectangular array | `ARRAYRECT` | Available | Available in the existing PyCAD model; see workflow guide for options. |
| Polar array | `ARRAYPOLAR` | Available | Available in the existing PyCAD model; see workflow guide for options. |
| Select | `SELECT` | Available | Available in the existing PyCAD model; see workflow guide for options. |

## Home / Layers — spreadsheet row 4

Workbook tools: Layer Properties, Layer Isolate, Layer Turn Off, Match Layer

| Tool | Command | Status | Scope |
| --- | --- | --- | --- |
| Layer Properties | `LAYER` | Available | Available in the existing PyCAD model; see workflow guide for options. |
| Layer Isolate | `LAYISO` | Available | Available in the existing PyCAD model; see workflow guide for options. |
| Layer Turn Off | `LAYOFF` | Available | Available in the existing PyCAD model; see workflow guide for options. |
| Match Layer | `LAYMCH` | Available | Available in the existing PyCAD model; see workflow guide for options. |
| All layers on | `LAYON` | Available | Available in the existing PyCAD model; see workflow guide for options. |
| Undo isolation | `LAYUNISO` | Available | Available in the existing PyCAD model; see workflow guide for options. |

## Home / Annotation — spreadsheet row 5

Workbook tools: Text, Multiline Text, Dimension, Leader, Table

| Tool | Command | Status | Scope |
| --- | --- | --- | --- |
| Text | `TEXT` | Available | Available in the existing PyCAD model; see workflow guide for options. |
| Multiline Text | `MTEXT` | Limited | Plain multiline text; rich text formatting is not supported. DXF export emits MTEXT. |
| Dimension | `DIMALIGNED` | Available | Available in the existing PyCAD model; see workflow guide for options. |
| Leader | `LEADER` | Limited | Creates a static arrow, line and text block. No associative multileader style system. |
| Table | `TABLE` | Limited | Creates a block of lines and text. No formulas, linked cells or native CAD TABLE semantics. |
| Dimension styles | `DIMSTYLE` | Available | Available in the existing PyCAD model; see workflow guide for options. |

## Home / Blocks — spreadsheet row 6

Workbook tools: Create Block, Insert, Block Editor, Attribute Definition

| Tool | Command | Status | Scope |
| --- | --- | --- | --- |
| Create Block | `BLOCK` | Available | Available in the existing PyCAD model; see workflow guide for options. |
| Insert | `INSERT` | Available | Available in the existing PyCAD model; see workflow guide for options. |
| Block Editor | `BEDIT` | Available | Available in the existing PyCAD model; see workflow guide for options. |
| Attribute Definition | `ATTDEF` | Planned | Block attributes need entity, editor and interchange support. |
| Clip reference | `XCLIP` | Available | Available in the existing PyCAD model; see workflow guide for options. |

## Home / Properties — spreadsheet row 7

Workbook tools: Color, Linetype, Lineweight, Transparency

| Tool | Command | Status | Scope |
| --- | --- | --- | --- |
| Color | `COLOR` | Available | Available in the existing PyCAD model; see workflow guide for options. |
| Linetype | `LINETYPE` | Available | Available in the existing PyCAD model; see workflow guide for options. |
| Lineweight | `LWEIGHT` | Limited | Edits the selected objects' layer lineweight; all entities on those layers are affected. |
| Transparency | `TRANSPARENCY` | Planned | Per-object transparency and its file/rendering support are not implemented. |
| Properties | `PROPERTIES` | Available | Available in the existing PyCAD model; see workflow guide for options. |

## Home / Utilities — spreadsheet row 8

Workbook tools: Measure, Distance, Radius, Angle, Area, Quick Measure

| Tool | Command | Status | Scope |
| --- | --- | --- | --- |
| Measure | `MEASUREGEOM` | Limited | Opens the measurement tool palette; MEASURE point placement is not implemented. |
| Distance | `DIST` | Available | Available in the existing PyCAD model; see workflow guide for options. |
| Radius | `MEASURERADIUS` | Available | Available in the existing PyCAD model; see workflow guide for options. |
| Angle | `MEASUREANGLE` | Available | Available in the existing PyCAD model; see workflow guide for options. |
| Area | `AREA` | Available | Available in the existing PyCAD model; see workflow guide for options. |
| Quick Measure | `QUICKMEASURE` | Limited | Click an entity to report its measurements; no live hover overlay. |

## Insert / Block — spreadsheet row 9

Workbook tools: Create Block, Write Block, Insert, Block Editor

| Tool | Command | Status | Scope |
| --- | --- | --- | --- |
| Create Block | `BLOCK` | Available | Available in the existing PyCAD model; see workflow guide for options. |
| Write Block | `WBLOCK` | Limited | Writes selected model-space entities and their block/layer/style dependencies to a native project or 2D DXF. |
| Insert | `INSERT` | Available | Available in the existing PyCAD model; see workflow guide for options. |
| Block Editor | `BEDIT` | Available | Available in the existing PyCAD model; see workflow guide for options. |

## Insert / Reference — spreadsheet row 10

Workbook tools: Attach (DWG, PDF, DGN, Image, Point Cloud), External References

| Tool | Command | Status | Scope |
| --- | --- | --- | --- |
| Attach DWG | `ATTACHDWG` | Planned | DWG opening is available through an optional ODA converter. Linked DWG references are not implemented. |
| Attach PDF | `PDFATTACH` | Planned | This format is not supported by the current importer. Use DXF for supported 2D geometry. |
| Attach DGN | `DGNATTACH` | Planned | This format is not supported by the current importer. Use DXF for supported 2D geometry. |
| Attach Image | `IMAGEATTACH` | Planned | Raster underlay persistence, transforms and plotting are not implemented. |
| Attach Point Cloud | `POINTCLOUDATTACH` | Planned | Requires a point-cloud importer and spatial rendering engine. |
| External References | `XREF` | Limited | Lists cached DXF references and reloads them. Nested-reference dependency packaging is not implemented. |
| Attach DXF | `DXFATTACH` | Limited | 2D DXF references only; inspect import warnings before use. |

## Insert / Import — spreadsheet row 11

Workbook tools: PDF Import, DGN Import, Markup Import

| Tool | Command | Status | Scope |
| --- | --- | --- | --- |
| PDF Import | `PDFIMPORT` | Planned | This format is not supported by the current importer. Use DXF for supported 2D geometry. |
| DGN Import | `DGNIMPORT` | Planned | This format is not supported by the current importer. Use DXF for supported 2D geometry. |
| Markup Import | `MARKUPIMPORT` | Planned | Markup recognition and association are not implemented. |

## Insert / Data — spreadsheet row 12

Workbook tools: Data Extraction, Extract Data table, Hyperlink

| Tool | Command | Status | Scope |
| --- | --- | --- | --- |
| Data Extraction | `DATAEXTRACTION` | Limited | Exports a static CSV of selected or visible model entities and their measured properties. |
| Extract Data table | `DATATABLE` | Limited | Creates a block of lines and text. No formulas, linked cells or native CAD TABLE semantics. |
| Hyperlink | `HYPERLINK` | Planned | Persistent entity hyperlinks are not implemented. |

## Annotate / Text — spreadsheet row 13

Workbook tools: Single Line Text, Multiline Text, Spell Check

| Tool | Command | Status | Scope |
| --- | --- | --- | --- |
| Single Line Text | `TEXT` | Available | Available in the existing PyCAD model; see workflow guide for options. |
| Multiline Text | `MTEXT` | Limited | Plain multiline text; no inline rich formatting. |
| Spell Check | `SPELL` | Planned | Requires a dictionary-backed spelling engine. |

## Annotate / Dimensions — spreadsheet row 14

Workbook tools: Linear, Aligned, Angular, Arc Length, Radius, Continue, Baseline

| Tool | Command | Status | Scope |
| --- | --- | --- | --- |
| Linear | `DIMHORIZONTAL` | Available | Available in the existing PyCAD model; see workflow guide for options. |
| Aligned | `DIMALIGNED` | Available | Available in the existing PyCAD model; see workflow guide for options. |
| Angular | `DIMANGULAR` | Planned | Angular dimension entities, editing and interchange are not implemented. |
| Arc Length | `DIMARC` | Planned | Arc-length dimension entities are not implemented. |
| Radius | `DIMRADIUS` | Available | Available in the existing PyCAD model; see workflow guide for options. |
| Continue | `DIMCONTINUE` | Limited | Select a linear dimension, then specify extension points. New dimensions are independent. |
| Baseline | `DIMBASELINE` | Limited | Select a linear dimension, then specify extension points. New dimensions are independent. |
| Vertical | `DIMVERTICAL` | Available | Available in the existing PyCAD model; see workflow guide for options. |
| Diameter | `DIMDIAMETER` | Available | Available in the existing PyCAD model; see workflow guide for options. |
| Dimension styles | `DIMSTYLE` | Available | Available in the existing PyCAD model; see workflow guide for options. |

## Annotate / Centerlines — spreadsheet row 15

Workbook tools: Centerline, Center Mark

| Tool | Command | Status | Scope |
| --- | --- | --- | --- |
| Centerline | `CENTERLINE` | Limited | Creates ordinary editable geometry; not associative with the source. Pick two parallel lines. |
| Center Mark | `CENTERMARK` | Limited | Creates ordinary editable geometry; not associative with the source. Pick a circle or arc. |

## Annotate / Leaders — spreadsheet row 16

Workbook tools: Multileader, Add Leader, Remove Leader

| Tool | Command | Status | Scope |
| --- | --- | --- | --- |
| Multileader | `MLEADER` | Limited | Creates a static arrow, line and text block. No associative multileader style system. One leader branch. |
| Add Leader | `MLEADERADD` | Planned | Persistent multileader branch editing is not implemented. |
| Remove Leader | `MLEADERREMOVE` | Planned | Persistent multileader branch editing is not implemented. |

## Annotate / Tables — spreadsheet row 17

Workbook tools: Table, Table Style

| Tool | Command | Status | Scope |
| --- | --- | --- | --- |
| Table | `TABLE` | Limited | Creates a block of lines and text. No formulas, linked cells or native CAD TABLE semantics. |
| Table Style | `TABLESTYLE` | Limited | Sets cell size and text height for newly created static table blocks; not a named CAD style table. |

## Parametric / Geometric — spreadsheet row 18

Workbook tools: Coincident, Collinear, Concentric, Fixed, Parallel, Perpendicular

| Tool | Command | Status | Scope |
| --- | --- | --- | --- |
| Coincident | `GCCOINCIDENT` | Planned | Requires a persistent constraint solver; drawing dimensions do not constrain geometry. |
| Collinear | `GCCOLLINEAR` | Planned | Requires a persistent constraint solver; drawing dimensions do not constrain geometry. |
| Concentric | `GCCONCENTRIC` | Planned | Requires a persistent constraint solver; drawing dimensions do not constrain geometry. |
| Fixed | `GCFIX` | Planned | Requires a persistent constraint solver; drawing dimensions do not constrain geometry. |
| Parallel | `GCPARALLEL` | Planned | Requires a persistent constraint solver; drawing dimensions do not constrain geometry. |
| Perpendicular | `GCPERPENDICULAR` | Planned | Requires a persistent constraint solver; drawing dimensions do not constrain geometry. |

## Parametric / Dimensional — spreadsheet row 19

Workbook tools: Linear, Aligned, Angular, Radius, Diameter

| Tool | Command | Status | Scope |
| --- | --- | --- | --- |
| Linear | `DCLINEAR` | Planned | Requires a persistent constraint solver; drawing dimensions do not constrain geometry. |
| Aligned | `DCALIGNED` | Planned | Requires a persistent constraint solver; drawing dimensions do not constrain geometry. |
| Angular | `DCANGULAR` | Planned | Requires a persistent constraint solver; drawing dimensions do not constrain geometry. |
| Radius | `DCRADIUS` | Planned | Requires a persistent constraint solver; drawing dimensions do not constrain geometry. |
| Diameter | `DCDIAMETER` | Planned | Requires a persistent constraint solver; drawing dimensions do not constrain geometry. |

## Parametric / Manage — spreadsheet row 20

Workbook tools: Show/Hide All, Delete Constraints, Settings

| Tool | Command | Status | Scope |
| --- | --- | --- | --- |
| Show/Hide All | `CONSTRAINTBAR` | Planned | Requires a persistent constraint solver; drawing dimensions do not constrain geometry. |
| Delete Constraints | `DELCONSTRAINT` | Planned | Requires a persistent constraint solver; drawing dimensions do not constrain geometry. |
| Settings | `CONSTRAINTSETTINGS` | Planned | Requires a persistent constraint solver; drawing dimensions do not constrain geometry. |

## View / Navigation — spreadsheet row 21

Workbook tools: Pan, Zoom (Extents, Window, Realtime), Orbit, SteeringWheel

| Tool | Command | Status | Scope |
| --- | --- | --- | --- |
| Pan | `PAN` | Available | Available in the existing PyCAD model; see workflow guide for options. |
| Zoom Extents | `ZOOMEXTENTS` | Available | Available in the existing PyCAD model; see workflow guide for options. |
| Zoom Window | `ZOOMWINDOW` | Limited | Two-corner window in the 2D drafting viewport. |
| Zoom Realtime | `ZOOMREALTIME` | Limited | Drag vertically in the 2D viewport; 3D also supports wheel zoom. |
| Orbit | `3DORBIT` | Available | Available in the existing PyCAD model; see workflow guide for options. |
| SteeringWheel | `NAVWHEEL` | Limited | PyCAD's compact in-viewport navigation rail and view selector; not Autodesk's SteeringWheel. |
| Four views | `VPORTS` | Available | Available in the existing PyCAD model; see workflow guide for options. |
| Top | `TOP` | Available | Available in the existing PyCAD model; see workflow guide for options. |
| Front | `FRONT` | Available | Available in the existing PyCAD model; see workflow guide for options. |
| Left | `LEFT` | Available | Available in the existing PyCAD model; see workflow guide for options. |
| Right | `RIGHT` | Available | Available in the existing PyCAD model; see workflow guide for options. |
| Bottom | `BOTTOM` | Available | Available in the existing PyCAD model; see workflow guide for options. |
| Back | `BACK` | Available | Available in the existing PyCAD model; see workflow guide for options. |
| Isometric | `ISOMETRIC` | Available | Available in the existing PyCAD model; see workflow guide for options. |
| 2D drafting | `PLAN` | Available | Available in the existing PyCAD model; see workflow guide for options. |

## View / Views — spreadsheet row 22

Workbook tools: Base View, Projected View, Section, Detail

| Tool | Command | Status | Scope |
| --- | --- | --- | --- |
| Base View | `VIEWBASE` | Planned | Generated associative drawing views from solids are not implemented. |
| Projected View | `VIEWPROJ` | Planned | Generated drawing views are not the same as the existing model camera presets. |
| Section | `VIEWSECTION` | Planned | Requires solid sectioning and drawing-view generation. |
| Detail | `VIEWDETAIL` | Planned | Requires associative drawing-view generation. |
| Paper viewport | `ADDVIEWPORT` | Available | Available in the existing PyCAD model; see workflow guide for options. |
| New layout | `NEWLAYOUT` | Available | Available in the existing PyCAD model; see workflow guide for options. |

## View / Visual Styles — spreadsheet row 23

Workbook tools: 2D Wireframe, Conceptual, Realistic, Shaded, X-Ray

| Tool | Command | Status | Scope |
| --- | --- | --- | --- |
| 2D Wireframe | `2DWIREFRAME` | Available | Available in the existing PyCAD model; see workflow guide for options. |
| Conceptual | `CONCEPTUAL` | Planned | A conceptual material/edge renderer is not implemented. |
| Realistic | `REALISTIC` | Planned | Material, texture, lighting and shadow rendering are not implemented. |
| Shaded | `SHADED` | Limited | Software shaded faces with edges; no material lighting. |
| X-Ray | `XRAY` | Limited | Transparent faces and edges in the embedded model viewport. |
| Extrude | `EXTRUDE` | Available | Available in the existing PyCAD model; see workflow guide for options. |

## View / Palettes — spreadsheet row 24

Workbook tools: Properties, Tool Palettes, Sheet Set Manager, Command Line

| Tool | Command | Status | Scope |
| --- | --- | --- | --- |
| Properties | `PROPERTIES` | Available | Available in the existing PyCAD model; see workflow guide for options. |
| Tool Palettes | `TOOLPALETTES` | Limited | Searchable command/capability palette; no drag-and-drop reusable block library. |
| Sheet Set Manager | `SHEETSET` | Planned | Sheet-set databases, publishing and drawing links are not implemented. |
| Command Line | `COMMANDLINE` | Available | Available in the existing PyCAD model; see workflow guide for options. |

## Manage / CAD Standards — spreadsheet row 25

Workbook tools: Check, Configure, Standards, Layer Translator

| Tool | Command | Status | Scope |
| --- | --- | --- | --- |
| Check | `CHECKSTANDARDS` | Planned | DWS CAD standards checking is not implemented. |
| Configure | `CONFIGURESTANDARDS` | Planned | DWS CAD standards configuration is not implemented. |
| Standards | `STANDARDS` | Planned | DWS standards files are not supported. |
| Layer Translator | `LAYTRANS` | Planned | Batch layer mapping and saved translation standards are not implemented. |

## Manage / Customization — spreadsheet row 26

Workbook tools: User Interface (CUI), Action Recorder, Edit Aliases

| Tool | Command | Status | Scope |
| --- | --- | --- | --- |
| User Interface (CUI) | `CUI` | Planned | A full CUI editor is not implemented. Use the Compact ribbon toggle and Edit Aliases. |
| Action Recorder | `ACTRECORD` | Planned | Replayable command/coordinate recording is not implemented. |
| Edit Aliases | `ALIASEDIT` | Available | Available in the existing PyCAD model; see workflow guide for options. |
| Tool coverage | `TOOLCOVERAGE` | Available | Available in the existing PyCAD model; see workflow guide for options. |

## Manage / Applications — spreadsheet row 27

Workbook tools: Load Application (AutoLISP/VBA), Visual Basic Editor, Action Macro

| Tool | Command | Status | Scope |
| --- | --- | --- | --- |
| Load Application (AutoLISP/VBA) | `APPLOAD` | Planned | AutoLISP and VBA runtimes are not implemented. Python console remains available from the menu. |
| Visual Basic Editor | `VBAIDE` | Planned | No VBA runtime or editor is included. |
| Action Macro | `ACTMACRO` | Planned | Command macro recording/replay is not implemented. |

## Output / Plot — spreadsheet row 28

Workbook tools: Plot, Batch Plot, Plot Preview, Page Setup

| Tool | Command | Status | Scope |
| --- | --- | --- | --- |
| Plot | `PLOT` | Limited | Vector PDF plotting with model scale or paper layouts. Direct physical-printer selection is not implemented. |
| Batch Plot | `BATCHPLOT` | Limited | Exports one PDF per paper layout into a ZIP (or Model when no layouts exist). |
| Plot Preview | `PLOTPREVIEW` | Limited | Preview of the current space using the same PDF renderer as export. |
| Page Setup | `PAGESETUP` | Limited | Changes the current paper layout's width/height in millimetres; Model uses A4 landscape. |

## Output / Export — spreadsheet row 29

Workbook tools: Export to PDF, DWF, DXF, STL, FBX

| Tool | Command | Status | Scope |
| --- | --- | --- | --- |
| Export to PDF | `EXPORTPDF` | Available | Available in the existing PyCAD model; see workflow guide for options. |
| DWF | `EXPORTDWF` | Planned | A DWF exporter is not implemented. |
| DXF | `EXPORTDXF` | Limited | Supported 2D entities only; dimensions export as lines/text. 3D extrusion export is rejected. |
| STL | `EXPORTSTL` | Limited | Exports one selected closed 2D profile with a prompted extrusion height; requires optional CadQuery. |
| FBX | `EXPORTFBX` | Planned | An FBX scene exporter is not implemented. |

## Output / Send — spreadsheet row 30

Workbook tools: Email, Transmittal (eTransmit)

| Tool | Command | Status | Scope |
| --- | --- | --- | --- |
| Email | `EMAIL` | Planned | Email account integration is not implemented. Save an eTransmit package and attach it manually. |
| Transmittal (eTransmit) | `ETRANSMIT` | Limited | Creates a local ZIP of the native drawing and direct DXF reference files with a manifest; missing references abort packaging. |
