# PyCAD 16.2 ribbon coverage

205 unique commands, 8 tabs, 31 panels. Status: 70 available, 120 limited, 15 planned.

| Tab | Panel | Command | Status | Scope |
|---|---|---|---|---|
| Home | Draw | `LINE` | available |  |
| Home | Draw | `PLINE` | available |  |
| Home | Draw | `CIRCLE` | available |  |
| Home | Draw | `ARC` | available |  |
| Home | Draw | `RECTANGLE` | available |  |
| Home | Draw | `HATCH` | available |  |
| Home | Draw | `SPLINE` | available |  |
| Home | Draw | `POINT` | available |  |
| Home | Draw | `ELLIPSE` | available |  |
| Home | Draw | `RAY` | available |  |
| Home | Draw | `XLINE` | available |  |
| Home | Draw | `WALL` | limited | Straight parametric walls with automatic bounded corner miters and cleaned T/cross junction outlines. |
| Home | Draw | `DOOR` | limited | Click a host architectural wall to place a door opening. |
| Home | Draw | `WINDOW` | limited | Click a host wall to place a sill/head window opening. |
| Home | Draw | `ROOM` | limited | Select a simple closed boundary for associative area, room name and finish labels. |
| Home | Draw | `SLAB` | limited | Closed straight-edge boundary, editable thickness and holes, level and live model. |
| Home | Draw | `CEILING` | limited | Level-relative closed boundary and thickness. |
| Home | Draw | `ROOF` | limited | Rectangular Flat/Shed/Gable/Hip roof, slope and overhang. |
| Home | Draw | `STAIR` | limited | Straight/L/U solid-step stairs, landings and flight handrails. |
| Home | Modify | `MOVE` | available |  |
| Home | Modify | `COPY` | available |  |
| Home | Modify | `STRETCH` | limited | Crossing-box stretch of LINE and polyline/spline vertices; fully enclosed supported objects move. No solid stretching. |
| Home | Modify | `ROTATE` | available |  |
| Home | Modify | `TRIM` | available |  |
| Home | Modify | `FILLET` | available |  |
| Home | Modify | `ERASE` | available |  |
| Home | Modify | `OFFSET` | available |  |
| Home | Modify | `MIRROR` | available |  |
| Home | Modify | `SCALE` | available |  |
| Home | Modify | `EXTEND` | available |  |
| Home | Modify | `CHAMFER` | available |  |
| Home | Modify | `ARRAYRECT` | available |  |
| Home | Modify | `ARRAYPOLAR` | available |  |
| Home | Modify | `SELECT` | available |  |
| Home | Modify | `CURVEEDIT` | limited | Native bulges and rational B-spline degree, knots and weights. |
| Home | Clipboard | `CUTCLIP` | limited | Copy native editable 2D selection to system clipboard, then remove with Undo. |
| Home | Clipboard | `COPYCLIP` | limited | Native geometry, required blocks, styles and supported internal links/constraints. |
| Home | Clipboard | `PASTECLIP` | limited | Pick or enter insertion point. Fresh IDs, collision-safe tables, unit scaling and Undo. |
| Home | Clipboard | `FIND` | limited | Find TEXT/MLEADER annotation text; replace editable matches with one Undo. |
| Home | Layers | `LAYER` | available |  |
| Home | Layers | `LAYISO` | available |  |
| Home | Layers | `LAYOFF` | available |  |
| Home | Layers | `LAYMCH` | available |  |
| Home | Layers | `LAYON` | available |  |
| Home | Layers | `LAYUNISO` | available |  |
| Home | Layers | `LAYERSTATE` | available |  |
| Home | Layers | `VPLAYER` | limited | Selected paper viewport: hide layers and override colors. |
| Home | Annotation | `TEXT` | available |  |
| Home | Annotation | `MTEXT` | limited | Multiline text; RICHTEXT adds bold/italic/underline/color runs and a drawing-unit wrap width. Native/PDF preserve formatting; DXF currently exports plain multiline content. |
| Home | Annotation | `DIMALIGNED` | available |  |
| Home | Annotation | `LEADER` | limited | Creates a static arrow, line and text block. No associative multileader style system. |
| Home | Annotation | `TABLE` | limited | Creates a block of lines and text. No formulas, linked cells or native CAD TABLE semantics. |
| Home | Annotation | `DIMSTYLE` | available |  |
| Home | Annotation | `RICHTEXT` | limited | Mixed bold/italic/underline/color and wrap width for selected text. |
| Home | Annotation | `LEADERLINK` | limited | Link first multileader tip to a selected source anchor. |
| Home | Annotation | `HATCHISLAND` | limited | Select the outer boundary and non-overlapping inner closed loops. |
| Home | Blocks | `BLOCK` | available |  |
| Home | Blocks | `INSERT` | available |  |
| Home | Blocks | `BEDIT` | available |  |
| Home | Blocks | `ATTDEF` | limited | Native editable block attribute definitions, per-instance ATTRIB values and DXF interchange. Not dynamic-block constraints. |
| Home | Blocks | `XCLIP` | available |  |
| Home | Blocks | `ATTEDIT` | available |  |
| Home | Blocks | `BLOCKSCHEDULE` | limited | Live attribute/architecture quantities, saved definitions and CSV exports. |
| Home | Properties | `COLOR` | available |  |
| Home | Properties | `LINETYPE` | available |  |
| Home | Properties | `LWEIGHT` | limited | Edits the selected objects' layer lineweight; all entities on those layers are affected. |
| Home | Properties | `TRANSPARENCY` | limited | Object transparency (0–90 percent), preserved by cloning and native files; displayed in 2D/PDF and exported to DXF. Does not control saved 3D solid materials. |
| Home | Properties | `PROPERTIES` | limited | Compact shared dock: appearance, typed positions/dimensions, architectural material/finish, block values and view plane, with one-step Undo. |
| Home | Utilities | `MEASUREGEOM` | limited | Opens the measurement tool palette; MEASURE point placement is not implemented. |
| Home | Utilities | `DIST` | available |  |
| Home | Utilities | `MEASURERADIUS` | available |  |
| Home | Utilities | `MEASUREANGLE` | available |  |
| Home | Utilities | `AREA` | available |  |
| Home | Utilities | `QUICKMEASURE` | limited | Click an entity to report its measurements; no live hover overlay. |
| Home | Utilities | `UNITS` | limited | Per-file display settings, with explicit physical unit conversion for model geometry, blocks, constraints, underlays, solids and viewport transforms. Unitless conversion requires assigning a source unit first. |
| Home | Utilities | `ARCHITECTURE` | limited | Edit walls, openings and rooms; export finish schedules. |
| Home | Utilities | `UPDATELINKS` | limited | Refresh live source links; cached geometry is retained and stale results reported when the optional kernel is unavailable. |
| Home | Utilities | `CHECKDRAWING` | limited | Free wall ends, hosted opening conflicts, invalid room boundaries and stale links; read-only screen marks and JSON report. |
| Home | Utilities | `BUILDING` | limited | Compact creation forms, levels and live model tools. |
| Home | Utilities | `LEVELS` | limited | Saved floor elevations/heights, assignments and visibility. |
| Home | Utilities | `AUTOROOM` | limited | Enclosed wall spaces with seeded live room boundaries. |
| Home | Utilities | `QUANTITYTAG` | limited | Explicit Length/Area/Volume/Count measurement for plain geometry. |
| Home | Utilities | `SLABHOLE` | limited | Select one object and one enclosed hole boundary. |
| Insert | Block | `BLOCK` | available |  |
| Insert | Block | `WBLOCK` | limited | Writes selected model-space entities and their block/layer/style dependencies to a native project or 2D DXF. |
| Insert | Block | `INSERT` | available |  |
| Insert | Block | `BEDIT` | available |  |
| Insert | Reference | `ATTACHDWG` | planned | DWG opening is available through an optional ODA converter. Linked DWG references are not implemented. |
| Insert | Reference | `PDFATTACH` | limited | Embeds one PDF page as a raster underlay (up to 150 dpi / 4096 pixels). Placement, opacity, locking, calibration and PDF plots; no vector import or PDF snapping. |
| Insert | Reference | `DGNATTACH` | planned | This format is not supported by the current importer. Use DXF for supported 2D geometry. |
| Insert | Reference | `IMAGEATTACH` | limited | Embedded raster underlay with placement, rotation, opacity, locking, scale calibration and PDF plotting. No raster-to-vector conversion. |
| Insert | Reference | `UNDERLAYS` | limited | Manage embedded image/PDF references and start two-point scale calibration. |
| Insert | Reference | `POINTCLOUDATTACH` | planned | Requires a point-cloud importer and spatial rendering engine. |
| Insert | Reference | `XREF` | limited | Lists cached DXF references, reloads or relinks moved files, and stores relinked paths relative to saved drawings. Nested-reference dependency packaging is not implemented. |
| Insert | Reference | `DXFATTACH` | limited | 2D DXF references only; inspect import warnings before use. |
| Insert | Import | `PDFIMPORT` | planned | This format is not supported by the current importer. Use DXF for supported 2D geometry. |
| Insert | Import | `DGNIMPORT` | planned | This format is not supported by the current importer. Use DXF for supported 2D geometry. |
| Insert | Import | `MARKUPIMPORT` | planned | Markup recognition and association are not implemented. |
| Insert | Data | `DATAEXTRACTION` | limited | Exports a static CSV of selected or visible model entities and their measured properties. |
| Insert | Data | `DATATABLE` | limited | Creates a block of lines and text. No formulas, linked cells or native CAD TABLE semantics. |
| Insert | Data | `HYPERLINK` | limited | Edit/remove HTTP(S) entity links and explicitly open them. Native and supported DXF entities preserve links; file paths and executable URL schemes are excluded. |
| Annotate | Text | `TEXT` | available |  |
| Annotate | Text | `MTEXT` | limited | Multiline text; RICHTEXT adds bold/italic/underline/color runs and a drawing-unit wrap width. Native/PDF preserve formatting; DXF currently exports plain multiline content. |
| Annotate | Text | `SPELL` | planned | Requires a dictionary-backed spelling engine. |
| Annotate | Text | `STYLE` | limited | Named font family, bold/italic, width factor, oblique angle and default new-text height. Native/PDF formatting; receiving CAD fonts may be substituted. |
| Annotate | Text | `TEXTEDIT` | limited | Select one TEXT annotation to edit multiline plain text, style, height and rotation with Undo. |
| Annotate | Dimensions | `DIMHORIZONTAL` | available |  |
| Annotate | Dimensions | `DIMALIGNED` | available |  |
| Annotate | Dimensions | `DIMANGULAR` | limited | Associative two-LINE or circular-arc angle; independent three-point angles. Choose a two-line sector by placement. Native links, placement grips and undo; DXF exports graphics. |
| Annotate | Dimensions | `DIMARC` | limited | Associative circular ARC length annotation with placement grip and shared dimension styles. No polyline/spline arc-length annotations; DXF exports graphics. |
| Annotate | Dimensions | `DIMRADIUS` | available |  |
| Annotate | Dimensions | `DIMORDINATE` | limited | Signed X/Y coordinates relative to an explicit per-annotation datum. LINE endpoints, POINTs and circular centers can stay linked. World axes only; DXF exports graphics. |
| Annotate | Dimensions | `DIMCONTINUE` | limited | Select a linear dimension, then specify extension points. New dimensions are independent. |
| Annotate | Dimensions | `DIMBASELINE` | limited | Select a linear dimension, then specify extension points. New dimensions are independent. |
| Annotate | Dimensions | `DIMVERTICAL` | available |  |
| Annotate | Dimensions | `DIMDIAMETER` | available |  |
| Annotate | Dimensions | `DIMSTYLE` | available |  |
| Annotate | Centerlines | `CENTERLINE` | limited | Creates ordinary editable geometry; not associative with the source. Pick two parallel lines. |
| Annotate | Centerlines | `CENTERMARK` | limited | Creates ordinary editable geometry; not associative with the source. Pick a circle or arc. |
| Annotate | Leaders | `MLEADER` | limited | Native plain-text annotation with named styles and up to 64 branches. Pick tip, elbow, text position. Tips are independent of source geometry; DXF exports graphics. |
| Annotate | Leaders | `MLEADERADD` | limited | Select a native multileader, then pick new arrow tip and elbow; shared text and style. |
| Annotate | Leaders | `MLEADERREMOVE` | limited | Select a native multileader and pick a branch. Retains at least one branch; ERASE deletes the annotation. |
| Annotate | Leaders | `MLEADERSTYLE` | limited | Named native styles with live preview, current style and apply to selection; shared changes are undoable. |
| Annotate | Leaders | `MLEADEREDIT` | limited | Select one native multileader to edit multiline plain text with undo/redo. |
| Annotate | Tables | `TABLE` | limited | Creates a block of lines and text. No formulas, linked cells or native CAD TABLE semantics. |
| Annotate | Tables | `TABLESTYLE` | limited | Sets cell size and text height for newly created static table blocks; not a named CAD style table. |
| Parametric | Geometric | `GCCOINCIDENT` | limited | Persistent coincidence of LINE endpoints, POINTs or CIRCLE/ARC centers. Native .pycad persistence; bounded 2D solver, no polyline segments, blocks, solids or expression parameters. |
| Parametric | Geometric | `GCCOLLINEAR` | limited | Persistent collinearity between two LINE entities. Native .pycad persistence; bounded 2D solver, no polyline segments, blocks, solids or expression parameters. |
| Parametric | Geometric | `GCCONCENTRIC` | limited | Persistent common center for CIRCLE/ARC entities. Native .pycad persistence; bounded 2D solver, no polyline segments, blocks, solids or expression parameters. |
| Parametric | Geometric | `GCFIX` | limited | Locks the complete position/shape of a LINE, POINT, CIRCLE or ARC. Native .pycad persistence; bounded 2D solver, no polyline segments, blocks, solids or expression parameters. |
| Parametric | Geometric | `GCPARALLEL` | limited | Maintains parallel LINE directions after committed edits. Native .pycad persistence; bounded 2D solver, no polyline segments, blocks, solids or expression parameters. |
| Parametric | Geometric | `GCPERPENDICULAR` | limited | Maintains perpendicular LINE directions after committed edits. Native .pycad persistence; bounded 2D solver, no polyline segments, blocks, solids or expression parameters. |
| Parametric | Geometric | `GCTANGENT` | limited | Persistent tangency between a LINE and CIRCLE or two CIRCLEs. Initial placement selects line side or internal/external tangency; arc segments are excluded. |
| Parametric | Dimensional | `DCLINEAR` | limited | Driving X or Y distance between LINE endpoints, POINTs or CIRCLE/ARC centers. Enter X/Y to choose the component. Native .pycad persistence; bounded 2D solver, no polyline segments, blocks, solids or expression parameters. |
| Parametric | Dimensional | `DCALIGNED` | limited | Driving distance between supported endpoints/centers. Native .pycad persistence; bounded 2D solver, no polyline segments, blocks, solids or expression parameters. |
| Parametric | Dimensional | `DCANGULAR` | limited | Driving angle between LINE entities, greater than 0 and less than 180 degrees. Native .pycad persistence; bounded 2D solver, no polyline segments, blocks, solids or expression parameters. |
| Parametric | Dimensional | `DCRADIUS` | limited | Driving CIRCLE/ARC radius. Native .pycad persistence; bounded 2D solver, no polyline segments, blocks, solids or expression parameters. |
| Parametric | Dimensional | `DCDIAMETER` | limited | Driving CIRCLE/ARC diameter. Native .pycad persistence; bounded 2D solver, no polyline segments, blocks, solids or expression parameters. |
| Parametric | Manage | `CONSTRAINTBAR` | limited | Shows/hides persistent constraint labels in drafting; labels are not printed. Native .pycad persistence; bounded 2D solver, no polyline segments, blocks, solids or expression parameters. |
| Parametric | Manage | `DELCONSTRAINT` | limited | Removes constraints involving selected objects, or asks before removing all. Undo restores them. Native .pycad persistence; bounded 2D solver, no polyline segments, blocks, solids or expression parameters. |
| Parametric | Manage | `CONSTRAINTSETTINGS` | limited | Constraint manager: edit driving values, delete relations, view remaining degrees of freedom, and configure tolerance/labels. Native .pycad persistence; bounded 2D solver, no polyline segments, blocks, solids or expression parameters. |
| View | Navigation | `PAN` | available |  |
| View | Navigation | `ZOOMEXTENTS` | available |  |
| View | Navigation | `ZOOMWINDOW` | limited | Two-corner window in the 2D drafting viewport. |
| View | Navigation | `ZOOMREALTIME` | limited | Drag vertically in the 2D viewport; 3D also supports wheel zoom. |
| View | Navigation | `3DORBIT` | available |  |
| View | Navigation | `NAVWHEEL` | limited | PyCAD's compact in-viewport navigation rail and view selector; not Autodesk's SteeringWheel. |
| View | Navigation | `VPORTS` | available |  |
| View | Navigation | `TOP` | available |  |
| View | Navigation | `FRONT` | available |  |
| View | Navigation | `LEFT` | available |  |
| View | Navigation | `RIGHT` | available |  |
| View | Navigation | `BOTTOM` | available |  |
| View | Navigation | `BACK` | available |  |
| View | Navigation | `ISOMETRIC` | available |  |
| View | Navigation | `PLAN` | available |  |
| View | Views | `VIEWBASE` | limited | Generate linked Top/Front/Right edge projections from one solid. Source changes refresh the view; no hidden-line removal. |
| View | Views | `VIEWPROJ` | limited | Linked 2D projected edge blocks from one source solid. Placement is independent of regeneration. |
| View | Views | `VIEWSECTION` | limited | Linked X/Y/Z plane section from one solid; editable plane position and cached last-valid geometry. |
| View | Views | `VIEWDETAIL` | planned | Requires associative drawing-view generation. |
| View | Views | `ADDVIEWPORT` | available |  |
| View | Views | `NEWLAYOUT` | available |  |
| View | Visual Styles | `2DWIREFRAME` | available |  |
| View | Visual Styles | `CONCEPTUAL` | planned | A conceptual material/edge renderer is not implemented. |
| View | Visual Styles | `REALISTIC` | planned | Material, texture, lighting and shadow rendering are not implemented. |
| View | Visual Styles | `SHADED` | limited | Software shaded faces with edges; no material lighting. |
| View | Visual Styles | `XRAY` | limited | Transparent faces and edges in the embedded model viewport. |
| View | Visual Styles | `EXTRUDE` | available |  |
| View | Visual Styles | `SOLIDTOOLS` | limited | Exact union/subtract/intersect, sections and elevations; optional CadQuery. |
| View | Visual Styles | `REVOLVE` | limited | Closed polyline/circle profile about X/Y axis; optional CadQuery. |
| View | Visual Styles | `SWEEP` | limited | Circular section along an open line/polyline/spline path; optional CadQuery. |
| View | Visual Styles | `ARCH3D` | limited | Generate or update linked wall solids with joined footprints and hosted opening cuts. Source edits update stable model IDs; optional CadQuery. |
| View | Visual Styles | `BUILD3D` | limited | Real live wall/slab/ceiling/roof/stair models; optional CadQuery. |
| View | Visual Styles | `BUILDVIEW` | limited | Multi-object linked sections, hatching and kernel hidden-line projections. |
| View | Visual Styles | `MATERIALS` | limited | Surface color/opacity, tile patterns and embedded image textures in software model previews. |
| View | Palettes | `PROPERTIES` | limited | Compact shared dock: appearance, typed positions/dimensions, architectural material/finish, block values and view plane, with one-step Undo. |
| View | Palettes | `TOOLPALETTES` | limited | Searchable command/capability palette; no drag-and-drop reusable block library. |
| View | Palettes | `SHEETSET` | limited | Manage native paper layouts, title blocks, plot presets and ordered combined vector PDF publishing. |
| View | Palettes | `COMMANDLINE` | available |  |
| View | Palettes | `DYNMODE` | limited | F12 toggles cursor readouts and editable length/angle or width/height fields for supported 2D point tools. Tab switches fields; Enter or Space accepts. Grip readouts remain read-only. |
| View | Palettes | `OPTIONS` | limited | Saved Dark/Light/Midnight themes and model, paper, 3D, grid and accent colors. |
| View | Palettes | `OSNAP` | limited | Configure running snap types, radius and grid spacing. |
| View | Palettes | `MENUBAR` | limited | Enter 1 to show menus, 0 to hide. File remains accessible from Quick Access. |
| Manage | CAD Standards | `CHECKSTANDARDS` | limited | Check drawing units and layer names/colors/linetypes/lineweights against a configured native JSON profile. No Autodesk DWS support or automatic repair. |
| Manage | CAD Standards | `CONFIGURESTANDARDS` | limited | Capture/load/save a native PyCAD standards profile; the active profile persists in .pycad. DWS files are not supported. |
| Manage | CAD Standards | `STANDARDS` | limited | Manage a persistent PyCAD JSON standards profile and run a drawing check. Not an Autodesk DWS engine. |
| Manage | CAD Standards | `LAYTRANS` | limited | Merge a source layer into an existing target, including block geometry and saved extrusion layer references. Undo restores both tables and objects. No saved mapping-file library. |
| Manage | Customization | `CUI` | planned | A full CUI editor is not implemented. Use the Compact ribbon toggle and Edit Aliases. |
| Manage | Customization | `ACTRECORD` | limited | Record committed primitive geometry edits, including additions, transformations and deletions. Drawing-specific edit IDs; no menu, block, architecture or file-command recording. |
| Manage | Customization | `ALIASEDIT` | available |  |
| Manage | Customization | `TOOLCOVERAGE` | available |  |
| Manage | Applications | `APPLOAD` | limited | Explicitly load a trusted local Python plugin defining register(api). Python command registration and reviewed proposals; no AutoLISP or VBA runtime. |
| Manage | Applications | `VBAIDE` | planned | No VBA runtime or editor is included. |
| Manage | Applications | `ACTMACRO` | limited | Import/export saved native JSON action macros; inspect a drawing preview before applying one Undo transaction. |
| Manage | Applications | `ASSIST` | limited | Offline instructions or JSON proposals, with preview and one-step Undo. |
| Manage | Applications | `AIPROPOSE` | limited | Optional user-configured compatible AI endpoint; session-only key and reviewed actions. |
| Manage | Applications | `DRAFTCHAT` | limited | Conversational dock, offline commands or configured AI, validated previews and one-step Undo. |
| Output | Plot | `PLOT` | limited | Vector PDF plotting with model scale or paper layouts. Direct physical-printer selection is not implemented. |
| Output | Plot | `BATCHPLOT` | limited | Exports one PDF per paper layout into a ZIP (or Model when no layouts exist). |
| Output | Plot | `PLOTPREVIEW` | limited | Preview of the current space using the same PDF renderer as export. |
| Output | Plot | `PAGESETUP` | limited | Changes the current paper layout's width/height in millimetres; Model uses A4 landscape. |
| Output | Plot | `PUBLISH` | limited | Ordered combined vector PDF from checked native paper layouts. |
| Output | Plot | `BOQ` | limited | Drawing-linked net quantities, explicit rates/allowance, source selection and CSV/JSON exports. |
| Output | Export | `EXPORTPDF` | available |  |
| Output | Export | `EXPORTDWF` | planned | A DWF exporter is not implemented. |
| Output | Export | `EXPORTDXF` | limited | Supported 2D entities only; dimensions export as lines/text. 3D extrusion export is rejected. |
| Output | Export | `EXPORTSTL` | limited | Exports one selected closed 2D profile with a prompted extrusion height; requires optional CadQuery. |
| Output | Export | `EXPORTFBX` | planned | An FBX scene exporter is not implemented. |
| Output | Export | `IFCEXPORT` | limited | Typed building objects, storeys, opening relationships, materials and quantities; optional requirements-bim.txt. |
| Output | Send | `EMAIL` | planned | Email account integration is not implemented. Save an eTransmit package and attach it manually. |
| Output | Send | `ETRANSMIT` | limited | Creates a local ZIP of the native drawing and direct DXF reference files with a manifest; missing references abort packaging. |
| Collaborate | Sharing & Review | `SHAREDVIEWS` | limited | Self-contained read-only HTML/SVG 2D snapshot with pan, zoom and print. Save/share manually or upload to configured cloud. |
| Collaborate | Sharing & Review | `CLOUD` | limited | Configured WebDAV listing, explicit native/view upload and file download. HTTPS, session-only password, ETag revision guards; no hosted account is included. |
| Collaborate | Sharing & Review | `COMPARE` | limited | Read-only native/DXF comparison, colored 2D overlay and JSON report. Same units required; tables and solids reported separately. |
