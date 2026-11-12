# PyCAD 15.9 ribbon coverage

7 tabs, 29 panels, 155 unique commands: 69 available, 63 limited, 23 planned.

MLEADER now creates a persistent native annotation. MLEADERADD and MLEADERREMOVE are enabled. MLEADERSTYLE and MLEADEREDIT are new; legacy LEADER stays a static block. Planned commands remain disabled.

## Home

| Panel | Label | Command | Status | Scope |
| --- | --- | --- | --- | --- |
| Draw | Line | `LINE` | available | Implemented. |
| Draw | Polyline | `PLINE` | available | Implemented. |
| Draw | Circle | `CIRCLE` | available | Implemented. |
| Draw | Arc | `ARC` | available | Implemented. |
| Draw | Rectangle | `RECTANGLE` | available | Implemented. |
| Draw | Hatch | `HATCH` | available | Implemented. |
| Draw | Spline | `SPLINE` | available | Implemented. |
| Draw | Point | `POINT` | available | Implemented. |
| Draw | Ellipse | `ELLIPSE` | available | Implemented. |
| Draw | Ray | `RAY` | available | Implemented. |
| Draw | Construction line | `XLINE` | available | Implemented. |
| Modify | Move | `MOVE` | available | Implemented. |
| Modify | Copy | `COPY` | available | Implemented. |
| Modify | Stretch | `STRETCH` | limited | Crossing-box stretch of LINE and polyline/spline vertices; fully enclosed supported objects move. No solid stretching. |
| Modify | Rotate | `ROTATE` | available | Implemented. |
| Modify | Trim | `TRIM` | available | Implemented. |
| Modify | Fillet | `FILLET` | available | Implemented. |
| Modify | Erase | `ERASE` | available | Implemented. |
| Modify | Offset | `OFFSET` | available | Implemented. |
| Modify | Mirror | `MIRROR` | available | Implemented. |
| Modify | Scale | `SCALE` | available | Implemented. |
| Modify | Extend | `EXTEND` | available | Implemented. |
| Modify | Chamfer | `CHAMFER` | available | Implemented. |
| Modify | Rectangular array | `ARRAYRECT` | available | Implemented. |
| Modify | Polar array | `ARRAYPOLAR` | available | Implemented. |
| Modify | Select | `SELECT` | available | Implemented. |
| Layers | Layer Properties | `LAYER` | available | Implemented. |
| Layers | Layer Isolate | `LAYISO` | available | Implemented. |
| Layers | Layer Turn Off | `LAYOFF` | available | Implemented. |
| Layers | Match Layer | `LAYMCH` | available | Implemented. |
| Layers | All layers on | `LAYON` | available | Implemented. |
| Layers | Undo isolation | `LAYUNISO` | available | Implemented. |
| Annotation | Text | `TEXT` | available | Implemented. |
| Annotation | Multiline Text | `MTEXT` | limited | Plain multiline text; rich text formatting is not supported. DXF export emits MTEXT. |
| Annotation | Dimension | `DIMALIGNED` | available | Implemented. |
| Annotation | Leader | `LEADER` | limited | Creates a static arrow, line and text block. No associative multileader style system. |
| Annotation | Table | `TABLE` | limited | Creates a block of lines and text. No formulas, linked cells or native CAD TABLE semantics. |
| Annotation | Dimension styles | `DIMSTYLE` | available | Implemented. |
| Blocks | Create Block | `BLOCK` | available | Implemented. |
| Blocks | Insert | `INSERT` | available | Implemented. |
| Blocks | Block Editor | `BEDIT` | available | Implemented. |
| Blocks | Attribute Definition | `ATTDEF` | planned | Block attributes need entity, editor and interchange support. |
| Blocks | Clip reference | `XCLIP` | available | Implemented. |
| Properties | Color | `COLOR` | available | Implemented. |
| Properties | Linetype | `LINETYPE` | available | Implemented. |
| Properties | Lineweight | `LWEIGHT` | limited | Edits the selected objects' layer lineweight; all entities on those layers are affected. |
| Properties | Transparency | `TRANSPARENCY` | limited | Object transparency (0–90 percent), preserved by cloning and native files; displayed in 2D/PDF and exported to DXF. Does not control saved 3D solid materials. |
| Properties | Properties | `PROPERTIES` | available | Implemented. |
| Utilities | Measure | `MEASUREGEOM` | limited | Opens the measurement tool palette; MEASURE point placement is not implemented. |
| Utilities | Distance | `DIST` | available | Implemented. |
| Utilities | Radius | `MEASURERADIUS` | available | Implemented. |
| Utilities | Angle | `MEASUREANGLE` | available | Implemented. |
| Utilities | Area | `AREA` | available | Implemented. |
| Utilities | Quick Measure | `QUICKMEASURE` | limited | Click an entity to report its measurements; no live hover overlay. |
| Utilities | Drawing units | `UNITS` | limited | Per-file display settings, with explicit physical unit conversion for model geometry, blocks, constraints, underlays, solids and viewport transforms. Unitless conversion requires assigning a source unit first. |

## Insert

| Panel | Label | Command | Status | Scope |
| --- | --- | --- | --- | --- |
| Block | Create Block | `BLOCK` | available | Implemented. |
| Block | Write Block | `WBLOCK` | limited | Writes selected model-space entities and their block/layer/style dependencies to a native project or 2D DXF. |
| Block | Insert | `INSERT` | available | Implemented. |
| Block | Block Editor | `BEDIT` | available | Implemented. |
| Reference | Attach DWG | `ATTACHDWG` | planned | DWG opening is available through an optional ODA converter. Linked DWG references are not implemented. |
| Reference | Attach PDF | `PDFATTACH` | limited | Embeds one PDF page as a raster underlay (up to 150 dpi / 4096 pixels). Placement, opacity, locking, calibration and PDF plots; no vector import or PDF snapping. |
| Reference | Attach DGN | `DGNATTACH` | planned | This format is not supported by the current importer. Use DXF for supported 2D geometry. |
| Reference | Attach Image | `IMAGEATTACH` | limited | Embedded raster underlay with placement, rotation, opacity, locking, scale calibration and PDF plotting. No raster-to-vector conversion. |
| Reference | Underlays | `UNDERLAYS` | limited | Manage embedded image/PDF references and start two-point scale calibration. |
| Reference | Attach Point Cloud | `POINTCLOUDATTACH` | planned | Requires a point-cloud importer and spatial rendering engine. |
| Reference | External References | `XREF` | limited | Lists cached DXF references, reloads or relinks moved files, and stores relinked paths relative to saved drawings. Nested-reference dependency packaging is not implemented. |
| Reference | Attach DXF | `DXFATTACH` | limited | 2D DXF references only; inspect import warnings before use. |
| Import | PDF Import | `PDFIMPORT` | planned | This format is not supported by the current importer. Use DXF for supported 2D geometry. |
| Import | DGN Import | `DGNIMPORT` | planned | This format is not supported by the current importer. Use DXF for supported 2D geometry. |
| Import | Markup Import | `MARKUPIMPORT` | planned | Markup recognition and association are not implemented. |
| Data | Data Extraction | `DATAEXTRACTION` | limited | Exports a static CSV of selected or visible model entities and their measured properties. |
| Data | Extract Data table | `DATATABLE` | limited | Creates a block of lines and text. No formulas, linked cells or native CAD TABLE semantics. |
| Data | Hyperlink | `HYPERLINK` | limited | Edit/remove HTTP(S) entity links and explicitly open them. Native and supported DXF entities preserve links; file paths and executable URL schemes are excluded. |

## Annotate

| Panel | Label | Command | Status | Scope |
| --- | --- | --- | --- | --- |
| Text | Single Line Text | `TEXT` | available | Implemented. |
| Text | Multiline Text | `MTEXT` | limited | Plain multiline text; no inline rich formatting. |
| Text | Spell Check | `SPELL` | planned | Requires a dictionary-backed spelling engine. |
| Dimensions | Linear | `DIMHORIZONTAL` | available | Implemented. |
| Dimensions | Aligned | `DIMALIGNED` | available | Implemented. |
| Dimensions | Angular | `DIMANGULAR` | limited | Associative two-LINE or circular-arc angle; independent three-point angles. Choose a two-line sector by placement. Native links, placement grips and undo; DXF exports graphics. |
| Dimensions | Arc Length | `DIMARC` | limited | Associative circular ARC length annotation with placement grip and shared dimension styles. No polyline/spline arc-length annotations; DXF exports graphics. |
| Dimensions | Radius | `DIMRADIUS` | available | Implemented. |
| Dimensions | Ordinate | `DIMORDINATE` | limited | Signed X/Y coordinates relative to an explicit per-annotation datum. LINE endpoints, POINTs and circular centers can stay linked. World axes only; DXF exports graphics. |
| Dimensions | Continue | `DIMCONTINUE` | limited | Select a linear dimension, then specify extension points. New dimensions are independent. |
| Dimensions | Baseline | `DIMBASELINE` | limited | Select a linear dimension, then specify extension points. New dimensions are independent. |
| Dimensions | Vertical | `DIMVERTICAL` | available | Implemented. |
| Dimensions | Diameter | `DIMDIAMETER` | available | Implemented. |
| Dimensions | Dimension styles | `DIMSTYLE` | available | Implemented. |
| Centerlines | Centerline | `CENTERLINE` | limited | Creates ordinary editable geometry; not associative with the source. Pick two parallel lines. |
| Centerlines | Center Mark | `CENTERMARK` | limited | Creates ordinary editable geometry; not associative with the source. Pick a circle or arc. |
| Leaders | Multileader | `MLEADER` | limited | Native plain-text annotation with named styles and up to 64 branches. Pick tip, elbow, text position. Tips are independent of source geometry; DXF exports graphics. |
| Leaders | Add Leader | `MLEADERADD` | limited | Select a native multileader, then pick new arrow tip and elbow; shared text and style. |
| Leaders | Remove Leader | `MLEADERREMOVE` | limited | Select a native multileader and pick a branch. Retains at least one branch; ERASE deletes the annotation. |
| Leaders | Leader Style | `MLEADERSTYLE` | limited | Named native styles with live preview, current style and apply to selection; shared changes are undoable. |
| Leaders | Edit Leader Text | `MLEADEREDIT` | limited | Select one native multileader to edit multiline plain text with undo/redo. |
| Tables | Table | `TABLE` | limited | Creates a block of lines and text. No formulas, linked cells or native CAD TABLE semantics. |
| Tables | Table Style | `TABLESTYLE` | limited | Sets cell size and text height for newly created static table blocks; not a named CAD style table. |

## Parametric

| Panel | Label | Command | Status | Scope |
| --- | --- | --- | --- | --- |
| Geometric | Coincident | `GCCOINCIDENT` | limited | Persistent coincidence of LINE endpoints, POINTs or CIRCLE/ARC centers. Native .pycad persistence; bounded 2D solver, no polyline segments, blocks, solids or expression parameters. |
| Geometric | Collinear | `GCCOLLINEAR` | limited | Persistent collinearity between two LINE entities. Native .pycad persistence; bounded 2D solver, no polyline segments, blocks, solids or expression parameters. |
| Geometric | Concentric | `GCCONCENTRIC` | limited | Persistent common center for CIRCLE/ARC entities. Native .pycad persistence; bounded 2D solver, no polyline segments, blocks, solids or expression parameters. |
| Geometric | Fixed | `GCFIX` | limited | Locks the complete position/shape of a LINE, POINT, CIRCLE or ARC. Native .pycad persistence; bounded 2D solver, no polyline segments, blocks, solids or expression parameters. |
| Geometric | Parallel | `GCPARALLEL` | limited | Maintains parallel LINE directions after committed edits. Native .pycad persistence; bounded 2D solver, no polyline segments, blocks, solids or expression parameters. |
| Geometric | Perpendicular | `GCPERPENDICULAR` | limited | Maintains perpendicular LINE directions after committed edits. Native .pycad persistence; bounded 2D solver, no polyline segments, blocks, solids or expression parameters. |
| Dimensional | Linear | `DCLINEAR` | limited | Driving X or Y distance between LINE endpoints, POINTs or CIRCLE/ARC centers. Enter X/Y to choose the component. Native .pycad persistence; bounded 2D solver, no polyline segments, blocks, solids or expression parameters. |
| Dimensional | Aligned | `DCALIGNED` | limited | Driving distance between supported endpoints/centers. Native .pycad persistence; bounded 2D solver, no polyline segments, blocks, solids or expression parameters. |
| Dimensional | Angular | `DCANGULAR` | limited | Driving angle between LINE entities, greater than 0 and less than 180 degrees. Native .pycad persistence; bounded 2D solver, no polyline segments, blocks, solids or expression parameters. |
| Dimensional | Radius | `DCRADIUS` | limited | Driving CIRCLE/ARC radius. Native .pycad persistence; bounded 2D solver, no polyline segments, blocks, solids or expression parameters. |
| Dimensional | Diameter | `DCDIAMETER` | limited | Driving CIRCLE/ARC diameter. Native .pycad persistence; bounded 2D solver, no polyline segments, blocks, solids or expression parameters. |
| Manage | Show/Hide All | `CONSTRAINTBAR` | limited | Shows/hides persistent constraint labels in drafting; labels are not printed. Native .pycad persistence; bounded 2D solver, no polyline segments, blocks, solids or expression parameters. |
| Manage | Delete Constraints | `DELCONSTRAINT` | limited | Removes constraints involving selected objects, or asks before removing all. Undo restores them. Native .pycad persistence; bounded 2D solver, no polyline segments, blocks, solids or expression parameters. |
| Manage | Settings | `CONSTRAINTSETTINGS` | limited | Constraint manager: edit driving values, delete relations, view remaining degrees of freedom, and configure tolerance/labels. Native .pycad persistence; bounded 2D solver, no polyline segments, blocks, solids or expression parameters. |

## View

| Panel | Label | Command | Status | Scope |
| --- | --- | --- | --- | --- |
| Navigation | Pan | `PAN` | available | Implemented. |
| Navigation | Zoom Extents | `ZOOMEXTENTS` | available | Implemented. |
| Navigation | Zoom Window | `ZOOMWINDOW` | limited | Two-corner window in the 2D drafting viewport. |
| Navigation | Zoom Realtime | `ZOOMREALTIME` | limited | Drag vertically in the 2D viewport; 3D also supports wheel zoom. |
| Navigation | Orbit | `3DORBIT` | available | Implemented. |
| Navigation | SteeringWheel | `NAVWHEEL` | limited | PyCAD's compact in-viewport navigation rail and view selector; not Autodesk's SteeringWheel. |
| Navigation | Four views | `VPORTS` | available | Implemented. |
| Navigation | Top | `TOP` | available | Implemented. |
| Navigation | Front | `FRONT` | available | Implemented. |
| Navigation | Left | `LEFT` | available | Implemented. |
| Navigation | Right | `RIGHT` | available | Implemented. |
| Navigation | Bottom | `BOTTOM` | available | Implemented. |
| Navigation | Back | `BACK` | available | Implemented. |
| Navigation | Isometric | `ISOMETRIC` | available | Implemented. |
| Navigation | 2D drafting | `PLAN` | available | Implemented. |
| Views | Base View | `VIEWBASE` | planned | Generated associative drawing views from solids are not implemented. |
| Views | Projected View | `VIEWPROJ` | planned | Generated drawing views are not the same as the existing model camera presets. |
| Views | Section | `VIEWSECTION` | planned | Requires solid sectioning and drawing-view generation. |
| Views | Detail | `VIEWDETAIL` | planned | Requires associative drawing-view generation. |
| Views | Paper viewport | `ADDVIEWPORT` | available | Implemented. |
| Views | New layout | `NEWLAYOUT` | available | Implemented. |
| Visual Styles | 2D Wireframe | `2DWIREFRAME` | available | Implemented. |
| Visual Styles | Conceptual | `CONCEPTUAL` | planned | A conceptual material/edge renderer is not implemented. |
| Visual Styles | Realistic | `REALISTIC` | planned | Material, texture, lighting and shadow rendering are not implemented. |
| Visual Styles | Shaded | `SHADED` | limited | Software shaded faces with edges; no material lighting. |
| Visual Styles | X-Ray | `XRAY` | limited | Transparent faces and edges in the embedded model viewport. |
| Visual Styles | Extrude | `EXTRUDE` | available | Implemented. |
| Palettes | Properties | `PROPERTIES` | available | Implemented. |
| Palettes | Tool Palettes | `TOOLPALETTES` | limited | Searchable command/capability palette; no drag-and-drop reusable block library. |
| Palettes | Sheet Set Manager | `SHEETSET` | planned | Sheet-set databases, publishing and drawing links are not implemented. |
| Palettes | Command Line | `COMMANDLINE` | available | Implemented. |
| Palettes | Live measurements | `DYNMODE` | limited | F12 toggles cursor readouts and editable length/angle or width/height fields for supported 2D point tools. Tab switches fields; Enter or Space accepts. Grip readouts remain read-only. |

## Manage

| Panel | Label | Command | Status | Scope |
| --- | --- | --- | --- | --- |
| CAD Standards | Check | `CHECKSTANDARDS` | limited | Check drawing units and layer names/colors/linetypes/lineweights against a configured native JSON profile. No Autodesk DWS support or automatic repair. |
| CAD Standards | Configure | `CONFIGURESTANDARDS` | limited | Capture/load/save a native PyCAD standards profile; the active profile persists in .pycad. DWS files are not supported. |
| CAD Standards | Standards | `STANDARDS` | limited | Manage a persistent PyCAD JSON standards profile and run a drawing check. Not an Autodesk DWS engine. |
| CAD Standards | Layer Translator | `LAYTRANS` | limited | Merge a source layer into an existing target, including block geometry and saved extrusion layer references. Undo restores both tables and objects. No saved mapping-file library. |
| Customization | User Interface (CUI) | `CUI` | planned | A full CUI editor is not implemented. Use the Compact ribbon toggle and Edit Aliases. |
| Customization | Action Recorder | `ACTRECORD` | planned | Replayable command/coordinate recording is not implemented. |
| Customization | Edit Aliases | `ALIASEDIT` | available | Implemented. |
| Customization | Tool coverage | `TOOLCOVERAGE` | available | Implemented. |
| Applications | Load Application (AutoLISP/VBA) | `APPLOAD` | planned | AutoLISP and VBA runtimes are not implemented. Python console remains available from the menu. |
| Applications | Visual Basic Editor | `VBAIDE` | planned | No VBA runtime or editor is included. |
| Applications | Action Macro | `ACTMACRO` | planned | Command macro recording/replay is not implemented. |

## Output

| Panel | Label | Command | Status | Scope |
| --- | --- | --- | --- | --- |
| Plot | Plot | `PLOT` | limited | Vector PDF plotting with model scale or paper layouts. Direct physical-printer selection is not implemented. |
| Plot | Batch Plot | `BATCHPLOT` | limited | Exports one PDF per paper layout into a ZIP (or Model when no layouts exist). |
| Plot | Plot Preview | `PLOTPREVIEW` | limited | Preview of the current space using the same PDF renderer as export. |
| Plot | Page Setup | `PAGESETUP` | limited | Changes the current paper layout's width/height in millimetres; Model uses A4 landscape. |
| Export | Export to PDF | `EXPORTPDF` | available | Implemented. |
| Export | DWF | `EXPORTDWF` | planned | A DWF exporter is not implemented. |
| Export | DXF | `EXPORTDXF` | limited | Supported 2D entities only; dimensions export as lines/text. 3D extrusion export is rejected. |
| Export | STL | `EXPORTSTL` | limited | Exports one selected closed 2D profile with a prompted extrusion height; requires optional CadQuery. |
| Export | FBX | `EXPORTFBX` | planned | An FBX scene exporter is not implemented. |
| Send | Email | `EMAIL` | planned | Email account integration is not implemented. Save an eTransmit package and attach it manually. |
| Send | Transmittal (eTransmit) | `ETRANSMIT` | limited | Creates a local ZIP of the native drawing and direct DXF reference files with a manifest; missing references abort packaging. |
