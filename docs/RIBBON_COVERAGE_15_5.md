# Ribbon coverage — PyCAD 15.5.0

**151 unique commands: 69 available, 53 limited, 29 planned.** Seven tabs and 29 panels retain the original workbook row mapping. The two added ribbon entries are UNITS and DYNMODE. Both are marked limited to describe their scope precisely.

The File workspace additionally exposes AUDIT, RECOVER, PURGE, STATUS, SAVETEMPLATE, NEWTEMPLATE, CLOSE and FILE. These File-only commands are outside the ribbon counts. See `GUIDE_15_5.md` for their scope and the separate File import/export availability table.

Available and limited entries have real handlers. Planned entries remain disabled with explanations; no unsupported format is counted as implemented.

## Home / Draw — spreadsheet row 2

| Tool | Command | Status | Scope |
| --- | --- | --- | --- |
| Line | `LINE` | Available | Implemented within the documented PyCAD model; see workflow guides. |
| Polyline | `PLINE` | Available | Implemented within the documented PyCAD model; see workflow guides. |
| Circle | `CIRCLE` | Available | Implemented within the documented PyCAD model; see workflow guides. |
| Arc | `ARC` | Available | Implemented within the documented PyCAD model; see workflow guides. |
| Rectangle | `RECTANGLE` | Available | Implemented within the documented PyCAD model; see workflow guides. |
| Hatch | `HATCH` | Available | Implemented within the documented PyCAD model; see workflow guides. |
| Spline | `SPLINE` | Available | Implemented within the documented PyCAD model; see workflow guides. |
| Point | `POINT` | Available | Implemented within the documented PyCAD model; see workflow guides. |
| Ellipse | `ELLIPSE` | Available | Implemented within the documented PyCAD model; see workflow guides. |
| Ray | `RAY` | Available | Implemented within the documented PyCAD model; see workflow guides. |
| Construction line | `XLINE` | Available | Implemented within the documented PyCAD model; see workflow guides. |

## Home / Modify — spreadsheet row 3

| Tool | Command | Status | Scope |
| --- | --- | --- | --- |
| Move | `MOVE` | Available | Implemented within the documented PyCAD model; see workflow guides. |
| Copy | `COPY` | Available | Implemented within the documented PyCAD model; see workflow guides. |
| Stretch | `STRETCH` | Limited | Crossing-box stretch of LINE and polyline/spline vertices; fully enclosed supported objects move. No solid stretching. |
| Rotate | `ROTATE` | Available | Implemented within the documented PyCAD model; see workflow guides. |
| Trim | `TRIM` | Available | Implemented within the documented PyCAD model; see workflow guides. |
| Fillet | `FILLET` | Available | Implemented within the documented PyCAD model; see workflow guides. |
| Erase | `ERASE` | Available | Implemented within the documented PyCAD model; see workflow guides. |
| Offset | `OFFSET` | Available | Implemented within the documented PyCAD model; see workflow guides. |
| Mirror | `MIRROR` | Available | Implemented within the documented PyCAD model; see workflow guides. |
| Scale | `SCALE` | Available | Implemented within the documented PyCAD model; see workflow guides. |
| Extend | `EXTEND` | Available | Implemented within the documented PyCAD model; see workflow guides. |
| Chamfer | `CHAMFER` | Available | Implemented within the documented PyCAD model; see workflow guides. |
| Rectangular array | `ARRAYRECT` | Available | Implemented within the documented PyCAD model; see workflow guides. |
| Polar array | `ARRAYPOLAR` | Available | Implemented within the documented PyCAD model; see workflow guides. |
| Select | `SELECT` | Available | Implemented within the documented PyCAD model; see workflow guides. |

## Home / Layers — spreadsheet row 4

| Tool | Command | Status | Scope |
| --- | --- | --- | --- |
| Layer Properties | `LAYER` | Available | Implemented within the documented PyCAD model; see workflow guides. |
| Layer Isolate | `LAYISO` | Available | Implemented within the documented PyCAD model; see workflow guides. |
| Layer Turn Off | `LAYOFF` | Available | Implemented within the documented PyCAD model; see workflow guides. |
| Match Layer | `LAYMCH` | Available | Implemented within the documented PyCAD model; see workflow guides. |
| All layers on | `LAYON` | Available | Implemented within the documented PyCAD model; see workflow guides. |
| Undo isolation | `LAYUNISO` | Available | Implemented within the documented PyCAD model; see workflow guides. |

## Home / Annotation — spreadsheet row 5

| Tool | Command | Status | Scope |
| --- | --- | --- | --- |
| Text | `TEXT` | Available | Implemented within the documented PyCAD model; see workflow guides. |
| Multiline Text | `MTEXT` | Limited | Plain multiline text; rich text formatting is not supported. DXF export emits MTEXT. |
| Dimension | `DIMALIGNED` | Available | Implemented within the documented PyCAD model; see workflow guides. |
| Leader | `LEADER` | Limited | Creates a static arrow, line and text block. No associative multileader style system. |
| Table | `TABLE` | Limited | Creates a block of lines and text. No formulas, linked cells or native CAD TABLE semantics. |
| Dimension styles | `DIMSTYLE` | Available | Implemented within the documented PyCAD model; see workflow guides. |

## Home / Blocks — spreadsheet row 6

| Tool | Command | Status | Scope |
| --- | --- | --- | --- |
| Create Block | `BLOCK` | Available | Implemented within the documented PyCAD model; see workflow guides. |
| Insert | `INSERT` | Available | Implemented within the documented PyCAD model; see workflow guides. |
| Block Editor | `BEDIT` | Available | Implemented within the documented PyCAD model; see workflow guides. |
| Attribute Definition | `ATTDEF` | Planned | Block attributes need entity, editor and interchange support. |
| Clip reference | `XCLIP` | Available | Implemented within the documented PyCAD model; see workflow guides. |

## Home / Properties — spreadsheet row 7

| Tool | Command | Status | Scope |
| --- | --- | --- | --- |
| Color | `COLOR` | Available | Implemented within the documented PyCAD model; see workflow guides. |
| Linetype | `LINETYPE` | Available | Implemented within the documented PyCAD model; see workflow guides. |
| Lineweight | `LWEIGHT` | Limited | Edits the selected objects' layer lineweight; all entities on those layers are affected. |
| Transparency | `TRANSPARENCY` | Limited | Object transparency (0–90 percent), preserved by cloning and native files; displayed in 2D/PDF and exported to DXF. Does not control saved 3D solid materials. |
| Properties | `PROPERTIES` | Available | Implemented within the documented PyCAD model; see workflow guides. |

## Home / Utilities — spreadsheet row 8

| Tool | Command | Status | Scope |
| --- | --- | --- | --- |
| Measure | `MEASUREGEOM` | Limited | Opens the measurement tool palette; MEASURE point placement is not implemented. |
| Distance | `DIST` | Available | Implemented within the documented PyCAD model; see workflow guides. |
| Radius | `MEASURERADIUS` | Available | Implemented within the documented PyCAD model; see workflow guides. |
| Angle | `MEASUREANGLE` | Available | Implemented within the documented PyCAD model; see workflow guides. |
| Area | `AREA` | Available | Implemented within the documented PyCAD model; see workflow guides. |
| Quick Measure | `QUICKMEASURE` | Limited | Click an entity to report its measurements; no live hover overlay. |
| Drawing units | `UNITS` | Limited | Per-file units, length/angle formats and precision; existing coordinates are not rescaled. Native persistence; dimension styles remain separate. |

## Insert / Block — spreadsheet row 9

| Tool | Command | Status | Scope |
| --- | --- | --- | --- |
| Create Block | `BLOCK` | Available | Implemented within the documented PyCAD model; see workflow guides. |
| Write Block | `WBLOCK` | Limited | Writes selected model-space entities and their block/layer/style dependencies to a native project or 2D DXF. |
| Insert | `INSERT` | Available | Implemented within the documented PyCAD model; see workflow guides. |
| Block Editor | `BEDIT` | Available | Implemented within the documented PyCAD model; see workflow guides. |

## Insert / Reference — spreadsheet row 10

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

| Tool | Command | Status | Scope |
| --- | --- | --- | --- |
| PDF Import | `PDFIMPORT` | Planned | This format is not supported by the current importer. Use DXF for supported 2D geometry. |
| DGN Import | `DGNIMPORT` | Planned | This format is not supported by the current importer. Use DXF for supported 2D geometry. |
| Markup Import | `MARKUPIMPORT` | Planned | Markup recognition and association are not implemented. |

## Insert / Data — spreadsheet row 12

| Tool | Command | Status | Scope |
| --- | --- | --- | --- |
| Data Extraction | `DATAEXTRACTION` | Limited | Exports a static CSV of selected or visible model entities and their measured properties. |
| Extract Data table | `DATATABLE` | Limited | Creates a block of lines and text. No formulas, linked cells or native CAD TABLE semantics. |
| Hyperlink | `HYPERLINK` | Limited | Edit/remove HTTP(S) entity links and explicitly open them. Native and supported DXF entities preserve links; file paths and executable URL schemes are excluded. |

## Annotate / Text — spreadsheet row 13

| Tool | Command | Status | Scope |
| --- | --- | --- | --- |
| Single Line Text | `TEXT` | Available | Implemented within the documented PyCAD model; see workflow guides. |
| Multiline Text | `MTEXT` | Limited | Plain multiline text; no inline rich formatting. |
| Spell Check | `SPELL` | Planned | Requires a dictionary-backed spelling engine. |

## Annotate / Dimensions — spreadsheet row 14

| Tool | Command | Status | Scope |
| --- | --- | --- | --- |
| Linear | `DIMHORIZONTAL` | Available | Implemented within the documented PyCAD model; see workflow guides. |
| Aligned | `DIMALIGNED` | Available | Implemented within the documented PyCAD model; see workflow guides. |
| Angular | `DIMANGULAR` | Planned | Angular dimension entities, editing and interchange are not implemented. |
| Arc Length | `DIMARC` | Planned | Arc-length dimension entities are not implemented. |
| Radius | `DIMRADIUS` | Available | Implemented within the documented PyCAD model; see workflow guides. |
| Continue | `DIMCONTINUE` | Limited | Select a linear dimension, then specify extension points. New dimensions are independent. |
| Baseline | `DIMBASELINE` | Limited | Select a linear dimension, then specify extension points. New dimensions are independent. |
| Vertical | `DIMVERTICAL` | Available | Implemented within the documented PyCAD model; see workflow guides. |
| Diameter | `DIMDIAMETER` | Available | Implemented within the documented PyCAD model; see workflow guides. |
| Dimension styles | `DIMSTYLE` | Available | Implemented within the documented PyCAD model; see workflow guides. |

## Annotate / Centerlines — spreadsheet row 15

| Tool | Command | Status | Scope |
| --- | --- | --- | --- |
| Centerline | `CENTERLINE` | Limited | Creates ordinary editable geometry; not associative with the source. Pick two parallel lines. |
| Center Mark | `CENTERMARK` | Limited | Creates ordinary editable geometry; not associative with the source. Pick a circle or arc. |

## Annotate / Leaders — spreadsheet row 16

| Tool | Command | Status | Scope |
| --- | --- | --- | --- |
| Multileader | `MLEADER` | Limited | Creates a static arrow, line and text block. No associative multileader style system. One leader branch. |
| Add Leader | `MLEADERADD` | Planned | Persistent multileader branch editing is not implemented. |
| Remove Leader | `MLEADERREMOVE` | Planned | Persistent multileader branch editing is not implemented. |

## Annotate / Tables — spreadsheet row 17

| Tool | Command | Status | Scope |
| --- | --- | --- | --- |
| Table | `TABLE` | Limited | Creates a block of lines and text. No formulas, linked cells or native CAD TABLE semantics. |
| Table Style | `TABLESTYLE` | Limited | Sets cell size and text height for newly created static table blocks; not a named CAD style table. |

## Parametric / Geometric — spreadsheet row 18

| Tool | Command | Status | Scope |
| --- | --- | --- | --- |
| Coincident | `GCCOINCIDENT` | Limited | Persistent coincidence of LINE endpoints, POINTs or CIRCLE/ARC centers. Native .pycad persistence; bounded 2D solver, no polyline segments, blocks, solids or expression parameters. |
| Collinear | `GCCOLLINEAR` | Limited | Persistent collinearity between two LINE entities. Native .pycad persistence; bounded 2D solver, no polyline segments, blocks, solids or expression parameters. |
| Concentric | `GCCONCENTRIC` | Limited | Persistent common center for CIRCLE/ARC entities. Native .pycad persistence; bounded 2D solver, no polyline segments, blocks, solids or expression parameters. |
| Fixed | `GCFIX` | Limited | Locks the complete position/shape of a LINE, POINT, CIRCLE or ARC. Native .pycad persistence; bounded 2D solver, no polyline segments, blocks, solids or expression parameters. |
| Parallel | `GCPARALLEL` | Limited | Maintains parallel LINE directions after committed edits. Native .pycad persistence; bounded 2D solver, no polyline segments, blocks, solids or expression parameters. |
| Perpendicular | `GCPERPENDICULAR` | Limited | Maintains perpendicular LINE directions after committed edits. Native .pycad persistence; bounded 2D solver, no polyline segments, blocks, solids or expression parameters. |

## Parametric / Dimensional — spreadsheet row 19

| Tool | Command | Status | Scope |
| --- | --- | --- | --- |
| Linear | `DCLINEAR` | Limited | Driving X or Y distance between LINE endpoints, POINTs or CIRCLE/ARC centers. Enter X/Y to choose the component. Native .pycad persistence; bounded 2D solver, no polyline segments, blocks, solids or expression parameters. |
| Aligned | `DCALIGNED` | Limited | Driving distance between supported endpoints/centers. Native .pycad persistence; bounded 2D solver, no polyline segments, blocks, solids or expression parameters. |
| Angular | `DCANGULAR` | Limited | Driving angle between LINE entities, greater than 0 and less than 180 degrees. Native .pycad persistence; bounded 2D solver, no polyline segments, blocks, solids or expression parameters. |
| Radius | `DCRADIUS` | Limited | Driving CIRCLE/ARC radius. Native .pycad persistence; bounded 2D solver, no polyline segments, blocks, solids or expression parameters. |
| Diameter | `DCDIAMETER` | Limited | Driving CIRCLE/ARC diameter. Native .pycad persistence; bounded 2D solver, no polyline segments, blocks, solids or expression parameters. |

## Parametric / Manage — spreadsheet row 20

| Tool | Command | Status | Scope |
| --- | --- | --- | --- |
| Show/Hide All | `CONSTRAINTBAR` | Limited | Shows/hides persistent constraint labels in drafting; labels are not printed. Native .pycad persistence; bounded 2D solver, no polyline segments, blocks, solids or expression parameters. |
| Delete Constraints | `DELCONSTRAINT` | Limited | Removes constraints involving selected objects, or asks before removing all. Undo restores them. Native .pycad persistence; bounded 2D solver, no polyline segments, blocks, solids or expression parameters. |
| Settings | `CONSTRAINTSETTINGS` | Limited | Constraint manager: edit driving values, delete relations, view remaining degrees of freedom, and configure tolerance/labels. Native .pycad persistence; bounded 2D solver, no polyline segments, blocks, solids or expression parameters. |

## View / Navigation — spreadsheet row 21

| Tool | Command | Status | Scope |
| --- | --- | --- | --- |
| Pan | `PAN` | Available | Implemented within the documented PyCAD model; see workflow guides. |
| Zoom Extents | `ZOOMEXTENTS` | Available | Implemented within the documented PyCAD model; see workflow guides. |
| Zoom Window | `ZOOMWINDOW` | Limited | Two-corner window in the 2D drafting viewport. |
| Zoom Realtime | `ZOOMREALTIME` | Limited | Drag vertically in the 2D viewport; 3D also supports wheel zoom. |
| Orbit | `3DORBIT` | Available | Implemented within the documented PyCAD model; see workflow guides. |
| SteeringWheel | `NAVWHEEL` | Limited | PyCAD's compact in-viewport navigation rail and view selector; not Autodesk's SteeringWheel. |
| Four views | `VPORTS` | Available | Implemented within the documented PyCAD model; see workflow guides. |
| Top | `TOP` | Available | Implemented within the documented PyCAD model; see workflow guides. |
| Front | `FRONT` | Available | Implemented within the documented PyCAD model; see workflow guides. |
| Left | `LEFT` | Available | Implemented within the documented PyCAD model; see workflow guides. |
| Right | `RIGHT` | Available | Implemented within the documented PyCAD model; see workflow guides. |
| Bottom | `BOTTOM` | Available | Implemented within the documented PyCAD model; see workflow guides. |
| Back | `BACK` | Available | Implemented within the documented PyCAD model; see workflow guides. |
| Isometric | `ISOMETRIC` | Available | Implemented within the documented PyCAD model; see workflow guides. |
| 2D drafting | `PLAN` | Available | Implemented within the documented PyCAD model; see workflow guides. |

## View / Views — spreadsheet row 22

| Tool | Command | Status | Scope |
| --- | --- | --- | --- |
| Base View | `VIEWBASE` | Planned | Generated associative drawing views from solids are not implemented. |
| Projected View | `VIEWPROJ` | Planned | Generated drawing views are not the same as the existing model camera presets. |
| Section | `VIEWSECTION` | Planned | Requires solid sectioning and drawing-view generation. |
| Detail | `VIEWDETAIL` | Planned | Requires associative drawing-view generation. |
| Paper viewport | `ADDVIEWPORT` | Available | Implemented within the documented PyCAD model; see workflow guides. |
| New layout | `NEWLAYOUT` | Available | Implemented within the documented PyCAD model; see workflow guides. |

## View / Visual Styles — spreadsheet row 23

| Tool | Command | Status | Scope |
| --- | --- | --- | --- |
| 2D Wireframe | `2DWIREFRAME` | Available | Implemented within the documented PyCAD model; see workflow guides. |
| Conceptual | `CONCEPTUAL` | Planned | A conceptual material/edge renderer is not implemented. |
| Realistic | `REALISTIC` | Planned | Material, texture, lighting and shadow rendering are not implemented. |
| Shaded | `SHADED` | Limited | Software shaded faces with edges; no material lighting. |
| X-Ray | `XRAY` | Limited | Transparent faces and edges in the embedded model viewport. |
| Extrude | `EXTRUDE` | Available | Implemented within the documented PyCAD model; see workflow guides. |

## View / Palettes — spreadsheet row 24

| Tool | Command | Status | Scope |
| --- | --- | --- | --- |
| Properties | `PROPERTIES` | Available | Implemented within the documented PyCAD model; see workflow guides. |
| Tool Palettes | `TOOLPALETTES` | Limited | Searchable command/capability palette; no drag-and-drop reusable block library. |
| Sheet Set Manager | `SHEETSET` | Planned | Sheet-set databases, publishing and drawing links are not implemented. |
| Command Line | `COMMANDLINE` | Available | Implemented within the documented PyCAD model; see workflow guides. |
| Live measurements | `DYNMODE` | Limited | Toggle read-only length/angle and tool-specific preview measurements in 2D drafting (F12); does not disable command entry. |

## Manage / CAD Standards — spreadsheet row 25

| Tool | Command | Status | Scope |
| --- | --- | --- | --- |
| Check | `CHECKSTANDARDS` | Limited | Check drawing units and layer names/colors/linetypes/lineweights against a configured native JSON profile. No Autodesk DWS support or automatic repair. |
| Configure | `CONFIGURESTANDARDS` | Limited | Capture/load/save a native PyCAD standards profile; the active profile persists in .pycad. DWS files are not supported. |
| Standards | `STANDARDS` | Limited | Manage a persistent PyCAD JSON standards profile and run a drawing check. Not an Autodesk DWS engine. |
| Layer Translator | `LAYTRANS` | Limited | Merge a source layer into an existing target, including block geometry and saved extrusion layer references. Undo restores both tables and objects. No saved mapping-file library. |

## Manage / Customization — spreadsheet row 26

| Tool | Command | Status | Scope |
| --- | --- | --- | --- |
| User Interface (CUI) | `CUI` | Planned | A full CUI editor is not implemented. Use the Compact ribbon toggle and Edit Aliases. |
| Action Recorder | `ACTRECORD` | Planned | Replayable command/coordinate recording is not implemented. |
| Edit Aliases | `ALIASEDIT` | Available | Implemented within the documented PyCAD model; see workflow guides. |
| Tool coverage | `TOOLCOVERAGE` | Available | Implemented within the documented PyCAD model; see workflow guides. |

## Manage / Applications — spreadsheet row 27

| Tool | Command | Status | Scope |
| --- | --- | --- | --- |
| Load Application (AutoLISP/VBA) | `APPLOAD` | Planned | AutoLISP and VBA runtimes are not implemented. Python console remains available from the menu. |
| Visual Basic Editor | `VBAIDE` | Planned | No VBA runtime or editor is included. |
| Action Macro | `ACTMACRO` | Planned | Command macro recording/replay is not implemented. |

## Output / Plot — spreadsheet row 28

| Tool | Command | Status | Scope |
| --- | --- | --- | --- |
| Plot | `PLOT` | Limited | Vector PDF plotting with model scale or paper layouts. Direct physical-printer selection is not implemented. |
| Batch Plot | `BATCHPLOT` | Limited | Exports one PDF per paper layout into a ZIP (or Model when no layouts exist). |
| Plot Preview | `PLOTPREVIEW` | Limited | Preview of the current space using the same PDF renderer as export. |
| Page Setup | `PAGESETUP` | Limited | Changes the current paper layout's width/height in millimetres; Model uses A4 landscape. |

## Output / Export — spreadsheet row 29

| Tool | Command | Status | Scope |
| --- | --- | --- | --- |
| Export to PDF | `EXPORTPDF` | Available | Implemented within the documented PyCAD model; see workflow guides. |
| DWF | `EXPORTDWF` | Planned | A DWF exporter is not implemented. |
| DXF | `EXPORTDXF` | Limited | Supported 2D entities only; dimensions export as lines/text. 3D extrusion export is rejected. |
| STL | `EXPORTSTL` | Limited | Exports one selected closed 2D profile with a prompted extrusion height; requires optional CadQuery. |
| FBX | `EXPORTFBX` | Planned | An FBX scene exporter is not implemented. |

## Output / Send — spreadsheet row 30

| Tool | Command | Status | Scope |
| --- | --- | --- | --- |
| Email | `EMAIL` | Planned | Email account integration is not implemented. Save an eTransmit package and attach it manually. |
| Transmittal (eTransmit) | `ETRANSMIT` | Limited | Creates a local ZIP of the native drawing and direct DXF reference files with a manifest; missing references abort packaging. |
