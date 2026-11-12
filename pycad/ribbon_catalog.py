"""Spreadsheet-traceable ribbon specification and honest capability descriptions.

Rows refer to AutoCAD_Tabs_and_Tools.xlsx / AutoCAD Tabs & Tools.  This
catalog is shared by the ribbon, searchable tool browser and release report.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolSpec:
    label: str
    command: str
    status: str = "available"
    detail: str = ""


def tool(label, command, detail=""):
    return ToolSpec(label, command, "limited" if detail else "available", detail)


def pending(label, command, reason):
    return ToolSpec(label, command, "planned", reason)


CONSTRAINTS = "Requires a persistent constraint solver; drawing dimensions do not constrain geometry."
STATIC = "Creates ordinary editable geometry; not associative with the source."
TABLE = "Creates a block of lines and text. No formulas, linked cells or native CAD TABLE semantics."
LEADER = "Creates a static arrow, line and text block. No associative multileader style system."
IMPORT = "This format is not supported by the current importer. Use DXF for supported 2D geometry."

PANELS = [
    (
        "Home",
        "Draw",
        2,
        [
            tool("Line", "LINE"),
            tool("Polyline", "PLINE"),
            tool("Circle", "CIRCLE"),
            tool("Arc", "ARC"),
            tool("Rectangle", "RECTANGLE"),
            tool("Hatch", "HATCH"),
            tool("Spline", "SPLINE"),
            tool("Point", "POINT"),
            tool("Ellipse", "ELLIPSE"),
            tool("Ray", "RAY"),
            tool("Construction line", "XLINE"),
        ],
    ),
    (
        "Home",
        "Modify",
        3,
        [
            tool("Move", "MOVE"),
            tool("Copy", "COPY"),
            tool(
                "Stretch",
                "STRETCH",
                "Crossing-box stretch of LINE and polyline/spline vertices; fully enclosed supported objects move. No solid stretching.",
            ),
            tool("Rotate", "ROTATE"),
            tool("Trim", "TRIM"),
            tool("Fillet", "FILLET"),
            tool("Erase", "ERASE"),
            tool("Offset", "OFFSET"),
            tool("Mirror", "MIRROR"),
            tool("Scale", "SCALE"),
            tool("Extend", "EXTEND"),
            tool("Chamfer", "CHAMFER"),
            tool("Rectangular array", "ARRAYRECT"),
            tool("Polar array", "ARRAYPOLAR"),
            tool("Select", "SELECT"),
        ],
    ),
    (
        "Home",
        "Layers",
        4,
        [
            tool("Layer Properties", "LAYER"),
            tool("Layer Isolate", "LAYISO"),
            tool("Layer Turn Off", "LAYOFF"),
            tool("Match Layer", "LAYMCH"),
            tool("All layers on", "LAYON"),
            tool("Undo isolation", "LAYUNISO"),
        ],
    ),
    (
        "Home",
        "Annotation",
        5,
        [
            tool("Text", "TEXT"),
            tool(
                "Multiline Text",
                "MTEXT",
                "Plain multiline text; rich text formatting is not supported. DXF export emits MTEXT.",
            ),
            tool("Dimension", "DIMALIGNED"),
            tool("Leader", "LEADER", LEADER),
            tool("Table", "TABLE", TABLE),
            tool("Dimension styles", "DIMSTYLE"),
        ],
    ),
    (
        "Home",
        "Blocks",
        6,
        [
            tool("Create Block", "BLOCK"),
            tool("Insert", "INSERT"),
            tool("Block Editor", "BEDIT"),
            tool("Explode", "EXPLODE", "One-level decomposition; splines become sampled lines. Lines are already primitive."),
            tool("Select Similar", "SELECTSIMILAR", "Same object type and layer; INSERTs also match block name."),
            tool("Isolate Objects", "ISOLATEOBJECTS"),
            tool("End Isolation", "UNISOLATEOBJECTS"),
            pending(
                "Attribute Definition",
                "ATTDEF",
                "Block attributes need entity, editor and interchange support.",
            ),
            tool("Clip reference", "XCLIP"),
        ],
    ),
    (
        "Home",
        "Properties",
        7,
        [
            tool("Color", "COLOR"),
            tool("Linetype", "LINETYPE"),
            tool(
                "Lineweight",
                "LWEIGHT",
                "Edits the selected objects' layer lineweight; all entities on those layers are affected.",
            ),
            pending(
                "Transparency",
                "TRANSPARENCY",
                "Per-object transparency and its file/rendering support are not implemented.",
            ),
            tool("Properties", "PROPERTIES"),
        ],
    ),
    (
        "Home",
        "Utilities",
        8,
        [
            tool(
                "Measure",
                "MEASUREGEOM",
                "Opens the measurement tool palette; MEASURE point placement is not implemented.",
            ),
            tool("Distance", "DIST"),
            tool("Radius", "MEASURERADIUS"),
            tool("Angle", "MEASUREANGLE"),
            tool("Area", "AREA"),
            tool(
                "Quick Measure",
                "QUICKMEASURE",
                "Click an entity to report its measurements; no live hover overlay.",
            ),
        ],
    ),
    (
        "Insert",
        "Block",
        9,
        [
            tool("Create Block", "BLOCK"),
            tool(
                "Write Block",
                "WBLOCK",
                "Writes selected model-space entities and their block/layer/style dependencies to a native project or 2D DXF.",
            ),
            tool("Insert", "INSERT"),
            tool("Block Editor", "BEDIT"),
            tool("Explode", "EXPLODE", "One-level decomposition; splines become sampled lines. Lines are already primitive."),
            tool("Select Similar", "SELECTSIMILAR", "Same object type and layer; INSERTs also match block name."),
            tool("Isolate Objects", "ISOLATEOBJECTS"),
            tool("End Isolation", "UNISOLATEOBJECTS"),
        ],
    ),
    (
        "Insert",
        "Reference",
        10,
        [
            pending(
                "Attach DWG",
                "ATTACHDWG",
                "DWG opening is available through an optional ODA converter. Linked DWG references are not implemented.",
            ),
            tool("Attach PDF", "PDFATTACH", 'Embeds one PDF page as a raster underlay (up to 150 dpi / 4096 pixels). Placement, opacity, locking, calibration and PDF plots; no vector import or PDF snapping.'),
            pending("Attach DGN", "DGNATTACH", IMPORT),
            tool(
                "Attach Image",
                "IMAGEATTACH",
                "Embedded raster underlay with placement, rotation, opacity, locking, scale calibration and PDF plotting. No raster-to-vector conversion.",
            ),
            tool('Underlays', 'UNDERLAYS', 'Manage embedded image/PDF references and start two-point scale calibration.'),
            pending(
                "Attach Point Cloud",
                "POINTCLOUDATTACH",
                "Requires a point-cloud importer and spatial rendering engine.",
            ),
            tool(
                "External References",
                "XREF",
                "Lists cached DXF references, reloads or relinks moved files, and stores relinked paths relative to saved drawings. Nested-reference dependency packaging is not implemented.",
            ),
            tool(
                "Attach DXF",
                "DXFATTACH",
                "2D DXF references only; inspect import warnings before use.",
            ),
        ],
    ),
    (
        "Insert",
        "Import",
        11,
        [
            tool("PDF Import", "PDFIMPORT", "Import editable vector paths with calibration, review and explicit limitations."),
            pending("DGN Import", "DGNIMPORT", IMPORT),
            pending(
                "Markup Import",
                "MARKUPIMPORT",
                "Markup recognition and association are not implemented.",
            ),
        ],
    ),
    (
        "Insert",
        "Data",
        12,
        [
            tool(
                "Data Extraction",
                "DATAEXTRACTION",
                "Exports a static CSV of selected or visible model entities and their measured properties.",
            ),
            tool("Extract Data table", "DATATABLE", TABLE),
            pending(
                "Hyperlink",
                "HYPERLINK",
                "Persistent entity hyperlinks are not implemented.",
            ),
        ],
    ),
    (
        "Annotate",
        "Text",
        13,
        [
            tool("Single Line Text", "TEXT"),
            tool(
                "Multiline Text",
                "MTEXT",
                "Plain multiline text; no inline rich formatting.",
            ),
            pending(
                "Spell Check", "SPELL", "Requires a dictionary-backed spelling engine."
            ),
        ],
    ),
    (
        "Annotate",
        "Dimensions",
        14,
        [
            tool("Linear", "DIMHORIZONTAL"),
            tool("Aligned", "DIMALIGNED"),
            tool(
                "Angular",
                "DIMANGULAR",
                "Associative two-LINE or circular-arc angle; independent three-point angles. Choose a two-line sector by placement. Native links, placement grips and undo; DXF exports graphics.",
            ),
            tool(
                "Arc Length",
                "DIMARC",
                "Associative circular ARC length annotation with placement grip and shared dimension styles. No polyline/spline arc-length annotations; DXF exports graphics.",
            ),
            tool("Radius", "DIMRADIUS"),
            tool("Ordinate", "DIMORDINATE", "Signed X/Y coordinates relative to an explicit per-annotation datum. LINE endpoints, POINTs and circular centers can stay linked. World axes only; DXF exports graphics."),
            tool(
                "Continue",
                "DIMCONTINUE",
                "Select a linear dimension, then specify extension points. New dimensions are independent.",
            ),
            tool(
                "Baseline",
                "DIMBASELINE",
                "Select a linear dimension, then specify extension points. New dimensions are independent.",
            ),
            tool("Vertical", "DIMVERTICAL"),
            tool("Diameter", "DIMDIAMETER"),
            tool("Dimension styles", "DIMSTYLE"),
        ],
    ),
    (
        "Annotate",
        "Centerlines",
        15,
        [
            tool("Centerline", "CENTERLINE", STATIC + " Pick two parallel lines."),
            tool("Center Mark", "CENTERMARK", STATIC + " Pick a circle or arc."),
        ],
    ),
    (
        "Annotate",
        "Leaders",
        16,
        [
            tool("Multileader", "MLEADER", "Native plain-text annotation with named styles and up to 64 branches. Pick tip, elbow, text position. Tips are independent of source geometry; DXF exports graphics."),
            tool("Add Leader", "MLEADERADD", "Select a native multileader, then pick new arrow tip and elbow; shared text and style."),
            tool("Remove Leader", "MLEADERREMOVE", "Select a native multileader and pick a branch. Retains at least one branch; ERASE deletes the annotation."),
            tool("Leader Style", "MLEADERSTYLE", "Named native styles with live preview, current style and apply to selection; shared changes are undoable."),
            tool("Edit Leader Text", "MLEADEREDIT", "Select one native multileader to edit multiline plain text with undo/redo."),
        ],
    ),
    (
        "Annotate",
        "Tables",
        17,
        [
            tool("Table", "TABLE", TABLE),
            tool(
                "Table Style",
                "TABLESTYLE",
                "Sets cell size and text height for newly created static table blocks; not a named CAD style table.",
            ),
        ],
    ),
    (
        "Parametric",
        "Geometric",
        18,
        [
            pending(label, "GC" + key, CONSTRAINTS)
            for label, key in [
                ("Coincident", "COINCIDENT"),
                ("Collinear", "COLLINEAR"),
                ("Concentric", "CONCENTRIC"),
                ("Fixed", "FIX"),
                ("Parallel", "PARALLEL"),
                ("Perpendicular", "PERPENDICULAR"),
            ]
        ],
    ),
    (
        "Parametric",
        "Dimensional",
        19,
        [
            pending(label, "DC" + key, CONSTRAINTS)
            for label, key in [
                ("Linear", "LINEAR"),
                ("Aligned", "ALIGNED"),
                ("Angular", "ANGULAR"),
                ("Radius", "RADIUS"),
                ("Diameter", "DIAMETER"),
            ]
        ],
    ),
    (
        "Parametric",
        "Manage",
        20,
        [
            pending("Show/Hide All", "CONSTRAINTBAR", CONSTRAINTS),
            pending("Delete Constraints", "DELCONSTRAINT", CONSTRAINTS),
            pending("Settings", "CONSTRAINTSETTINGS", CONSTRAINTS),
        ],
    ),
    (
        "View",
        "Navigation",
        21,
        [
            tool("Pan", "PAN"),
            tool("Zoom Extents", "ZOOMEXTENTS"),
            tool(
                "Zoom Window",
                "ZOOMWINDOW",
                "Two-corner window in the 2D drafting viewport.",
            ),
            tool(
                "Zoom Realtime",
                "ZOOMREALTIME",
                "Drag vertically in the 2D viewport; 3D also supports wheel zoom.",
            ),
            tool("Orbit", "3DORBIT"),
            tool(
                "SteeringWheel",
                "NAVWHEEL",
                "PY.cad's compact in-viewport navigation rail and view selector; not Autodesk's SteeringWheel.",
            ),
            tool("Four views", "VPORTS"),
            tool("Top", "TOP"),
            tool("Front", "FRONT"),
            tool("Left", "LEFT"),
            tool("Right", "RIGHT"),
            tool("Bottom", "BOTTOM"),
            tool("Back", "BACK"),
            tool("Isometric", "ISOMETRIC"),
            tool("2D drafting", "PLAN"),
        ],
    ),
    (
        "View",
        "Views",
        22,
        [
            pending(
                "Base View",
                "VIEWBASE",
                "Generated associative drawing views from solids are not implemented.",
            ),
            pending(
                "Projected View",
                "VIEWPROJ",
                "Generated drawing views are not the same as the existing model camera presets.",
            ),
            pending(
                "Section",
                "VIEWSECTION",
                "Requires solid sectioning and drawing-view generation.",
            ),
            pending(
                "Detail", "VIEWDETAIL", "Requires associative drawing-view generation."
            ),
            tool("Paper viewport", "ADDVIEWPORT"),
            tool("New layout", "NEWLAYOUT"),
        ],
    ),
    (
        "View",
        "Visual Styles",
        23,
        [
            tool("2D Wireframe", "2DWIREFRAME"),
            pending(
                "Conceptual",
                "CONCEPTUAL",
                "A conceptual material/edge renderer is not implemented.",
            ),
            pending(
                "Realistic",
                "REALISTIC",
                "Material, texture, lighting and shadow rendering are not implemented.",
            ),
            tool(
                "Shaded",
                "SHADED",
                "Software shaded faces with edges; no material lighting.",
            ),
            tool(
                "X-Ray",
                "XRAY",
                "Transparent faces and edges in the embedded model viewport.",
            ),
            tool("Extrude", "EXTRUDE"),
        ],
    ),
    (
        "View",
        "Palettes",
        24,
        [
            tool("Properties", "PROPERTIES"),
            tool(
                "Tool Palettes",
                "TOOLPALETTES",
                "Searchable command/capability palette; no drag-and-drop reusable block library.",
            ),
            pending(
                "Sheet Set Manager",
                "SHEETSET",
                "Sheet-set databases, publishing and drawing links are not implemented.",
            ),
            tool("Command Line", "COMMANDLINE"),
        ],
    ),
    (
        "Manage",
        "CAD Standards",
        25,
        [
            pending(
                "Check",
                "CHECKSTANDARDS",
                "DWS CAD standards checking is not implemented.",
            ),
            pending(
                "Configure",
                "CONFIGURESTANDARDS",
                "DWS CAD standards configuration is not implemented.",
            ),
            pending("Standards", "STANDARDS", "DWS standards files are not supported."),
            pending(
                "Layer Translator",
                "LAYTRANS",
                "Batch layer mapping and saved translation standards are not implemented.",
            ),
        ],
    ),
    (
        "Manage",
        "Customization",
        26,
        [
            pending(
                "User Interface (CUI)",
                "CUI",
                "A full CUI editor is not implemented. Use the Compact ribbon toggle and Edit Aliases.",
            ),
            pending(
                "Action Recorder",
                "ACTRECORD",
                "Replayable command/coordinate recording is not implemented.",
            ),
            tool("Edit Aliases", "ALIASEDIT"),
            tool("Tool coverage", "TOOLCOVERAGE"),
        ],
    ),
    (
        "Manage",
        "Applications",
        27,
        [
            pending(
                "Load Application (AutoLISP/VBA)",
                "APPLOAD",
                "AutoLISP and VBA runtimes are not implemented. Python console remains available from the menu.",
            ),
            pending(
                "Visual Basic Editor", "VBAIDE", "No VBA runtime or editor is included."
            ),
            pending(
                "Action Macro",
                "ACTMACRO",
                "Command macro recording/replay is not implemented.",
            ),
        ],
    ),
    (
        "Output",
        "Plot",
        28,
        [
            tool(
                "Plot",
                "PLOT",
                "Vector PDF plotting with model scale or paper layouts. Direct physical-printer selection is not implemented.",
            ),
            tool(
                "Batch Plot",
                "BATCHPLOT",
                "Exports one PDF per paper layout into a ZIP (or Model when no layouts exist).",
            ),
            tool(
                "Plot Preview",
                "PLOTPREVIEW",
                "Preview of the current space using the same PDF renderer as export.",
            ),
            tool(
                "Page Setup",
                "PAGESETUP",
                "Changes the current paper layout's width/height in millimetres; Model uses A4 landscape.",
            ),
        ],
    ),
    (
        "Output",
        "Export",
        29,
        [
            tool("Export to PDF", "EXPORTPDF"),
            pending("DWF", "EXPORTDWF", "A DWF exporter is not implemented."),
            tool(
                "DXF",
                "EXPORTDXF",
                "Supported 2D entities only; dimensions export as lines/text. 3D extrusion export is rejected.",
            ),
            tool(
                "STL",
                "EXPORTSTL",
                "Exports one selected closed 2D profile with a prompted extrusion height; requires optional CadQuery.",
            ),
            pending("FBX", "EXPORTFBX", "An FBX scene exporter is not implemented."),
        ],
    ),
    (
        "Output",
        "Send",
        30,
        [
            pending(
                "Email",
                "EMAIL",
                "Email account integration is not implemented. Save an eTransmit package and attach it manually.",
            ),
            tool(
                "Transmittal (eTransmit)",
                "ETRANSMIT",
                "Creates a local ZIP of the native drawing and direct DXF reference files with a manifest; missing references abort packaging.",
            ),
        ],
    ),
]

CONSTRAINT_SUPPORT = {
    'GCTANGENT': 'Persistent tangency between a LINE and CIRCLE or two CIRCLEs. Initial placement selects line side or internal/external tangency; arc segments are excluded.',
    "GCCOINCIDENT": "Persistent coincidence of LINE endpoints, POINTs or CIRCLE/ARC centers.",
    "GCCOLLINEAR": "Persistent collinearity between two LINE entities.",
    "GCCONCENTRIC": "Persistent common center for CIRCLE/ARC entities.",
    "GCFIX": "Locks the complete position/shape of a LINE, POINT, CIRCLE or ARC.",
    "GCPARALLEL": "Maintains parallel LINE directions after committed edits.",
    "GCPERPENDICULAR": "Maintains perpendicular LINE directions after committed edits.",
    "DCLINEAR": "Driving X or Y distance between LINE endpoints, POINTs or CIRCLE/ARC centers. Enter X/Y to choose the component.",
    "DCALIGNED": "Driving distance between supported endpoints/centers.",
    "DCANGULAR": "Driving angle between LINE entities, greater than 0 and less than 180 degrees.",
    "DCRADIUS": "Driving CIRCLE/ARC radius.",
    "DCDIAMETER": "Driving CIRCLE/ARC diameter.",
    "CONSTRAINTBAR": "Shows/hides persistent constraint labels in drafting; labels are not printed.",
    "DELCONSTRAINT": "Removes constraints involving selected objects, or asks before removing all. Undo restores them.",
    "CONSTRAINTSETTINGS": "Constraint manager: edit driving values, delete relations, view remaining degrees of freedom, and configure tolerance/labels.",
}
PANELS = [(tab,panel,row,[tool(t.label,t.command,CONSTRAINT_SUPPORT[t.command] + " Native .pycad persistence; bounded 2D solver, no polyline segments, blocks, solids or expression parameters.") if t.command in CONSTRAINT_SUPPORT else t for t in items]) for tab,panel,row,items in PANELS]
PROJECT_SUPPORT = {
    "TRANSPARENCY":"Object transparency (0–90 percent), preserved by cloning and native files; displayed in 2D/PDF and exported to DXF. Does not control saved 3D solid materials.",
    "HYPERLINK":"Edit/remove HTTP(S) entity links and explicitly open them. Native and supported DXF entities preserve links; file paths and executable URL schemes are excluded.",
    "LAYTRANS":"Merge a source layer into an existing target, including block geometry and saved extrusion layer references. Undo restores both tables and objects. No saved mapping-file library.",
    "CHECKSTANDARDS":"Check drawing units and layer names/colors/linetypes/lineweights against a configured native JSON profile. No Autodesk DWS support or automatic repair.",
    "CONFIGURESTANDARDS":"Capture/load/save a native PY.cad standards profile; the active profile persists in .pycad. DWS files are not supported.",
    "STANDARDS":"Manage a persistent PY.cad JSON standards profile and run a drawing check. Not an Autodesk DWS engine.",
}
PANELS=[(tab,panel,row,[tool(t.label,t.command,PROJECT_SUPPORT[t.command]) if t.command in PROJECT_SUPPORT else t for t in items]) for tab,panel,row,items in PANELS]
TABS = tuple(dict.fromkeys(tab for tab, _, _, _ in PANELS))
PANELS = [(tab, panel, row, items + ([
    tool("Drawing units", "UNITS", "Per-file display settings, with explicit physical unit conversion for model geometry, blocks, constraints, underlays, solids and viewport transforms. Unitless conversion requires assigning a source unit first.")
] if (tab, panel) == ("Home", "Utilities") else [
    tool("Live measurements", "DYNMODE", "F12 toggles cursor readouts and editable length/angle or width/height fields for supported 2D point tools. Tab switches fields; Enter or Space accepts. Grip readouts remain read-only.")
] if (tab, panel) == ("View", "Palettes") else [])) for tab, panel, row, items in PANELS]
PANELS = [(tab,panel,row,items + ([
    tool('Text styles','STYLE','Named font family, bold/italic, width factor, oblique angle and default new-text height. Native/PDF formatting; receiving CAD fonts may be substituted.'),
    tool('Edit / format text','TEXTEDIT','Select one TEXT annotation to edit multiline plain text, style, height and rotation with Undo.')
] if (tab,panel)==('Annotate','Text') else [
    tool('Options / Theme','OPTIONS','Saved Dark/Light/Midnight themes and model, paper, 3D, grid and accent colors.'),
    tool('Object Snaps','OSNAP','Configure running snap types, radius and grid spacing.'),
    tool('Classic menus','MENUBAR','Enter 1 to show menus, 0 to hide. File remains accessible from Quick Access.')
] if (tab,panel)==('View','Palettes') else [
    tool('Tangent','GCTANGENT',CONSTRAINT_SUPPORT['GCTANGENT'])
] if (tab,panel)==('Parametric','Geometric') else [])) for tab,panel,row,items in PANELS]
PANELS.insert(2,('Home','Clipboard',32,[
    tool('Cut','CUTCLIP','Copy native editable 2D selection to system clipboard, then remove with Undo.'),
    tool('Copy','COPYCLIP','Native geometry, required blocks, styles and supported internal links/constraints.'),
    tool('Paste','PASTECLIP','Pick or enter insertion point. Fresh IDs, collision-safe tables, unit scaling and Undo.'),
    tool('Find / Replace','FIND','Find TEXT/MLEADER annotation text; replace editable matches with one Undo.')]))
PANELS.append(('Collaborate','Sharing & Review',31,[
    tool('Shared Views','SHAREDVIEWS','Self-contained read-only HTML/SVG 2D snapshot with pan, zoom and print. Save/share manually or upload to configured cloud.'),
    tool('Cloud Files','CLOUD','Configured WebDAV listing, explicit native/view upload and file download. HTTPS, session-only password, ETag revision guards; no hosted account is included.'),
    tool('Drawing Compare','COMPARE','Read-only native/DXF comparison, colored 2D overlay and JSON report. Same units required; tables and solids reported separately.')]))
V16_SUPPORT={
 'ATTDEF':'Native editable block attribute definitions, per-instance ATTRIB values and DXF interchange. Not dynamic-block constraints.',
 'VIEWBASE':'Generate static Top/Front/Right projections from saved CadQuery solids. All projected edges are shown; no hidden-line removal.',
 'VIEWPROJ':'Generate static projected 2D line/curve blocks from saved solids; regenerate through the solid manager.',
 'VIEWSECTION':'Intersect a saved solid with an X/Y/Z plane and place the resulting 2D section edges. Requires optional CadQuery.',
 'SHEETSET':'Manage native paper layouts, title blocks, plot presets and ordered combined vector PDF publishing.',
 'ACTRECORD':'Record committed primitive geometry edits, including additions, transformations and deletions. Drawing-specific edit IDs; no menu, block, architecture or file-command recording.',
 'ACTMACRO':'Import/export saved native JSON action macros; inspect a drawing preview before applying one Undo transaction.',
 'APPLOAD':'Explicitly load a trusted local Python plugin defining register(api). Python command registration and reviewed proposals; no AutoLISP or VBA runtime.',
 'MTEXT':'Multiline text; RICHTEXT adds bold/italic/underline/color runs and a drawing-unit wrap width. Native/PDF preserve formatting; DXF currently exports plain multiline content.'
}
PANELS=[(tab,panel,row,[tool('Load Python plugin' if t.command=='APPLOAD' else t.label,t.command,V16_SUPPORT[t.command]) if t.command in V16_SUPPORT else t for t in items]) for tab,panel,row,items in PANELS]
V16_TOOLS={
 ('Home','Draw'):[tool('Architectural wall','WALL','Straight parametric walls from clicked points or selected lines.'),tool('Door','DOOR','Click a host architectural wall to place a door opening.'),tool('Window','WINDOW','Click a host wall to place a sill/head window opening.'),tool('Room / Area label','ROOM','Select a simple closed boundary for associative area, room name and finish labels.')],
 ('Home','Modify'):[tool('Curve controls','CURVEEDIT','Native bulges and rational B-spline degree, knots and weights.')],
 ('Home','Layers'):[tool('Layer states','LAYERSTATE'),tool('Viewport overrides','VPLAYER','Selected paper viewport: hide layers and override colors.')],
 ('Home','Annotation'):[tool('Rich text','RICHTEXT','Mixed bold/italic/underline/color and wrap width for selected text.'),tool('Leader source link','LEADERLINK','Link first multileader tip to a selected source anchor.'),tool('Hatch islands','HATCHISLAND','Select the outer boundary and non-overlapping inner closed loops.')],
 ('Home','Blocks'):[tool('Edit attributes','ATTEDIT'),tool('Block schedules','BLOCKSCHEDULE','Live attribute/architecture quantities, saved definitions and CSV exports.')],
 ('View','Visual Styles'):[tool('Solid tools','SOLIDTOOLS','Exact union/subtract/intersect, sections and elevations; optional CadQuery.'),tool('Revolve','REVOLVE','Closed polyline/circle profile about X/Y axis; optional CadQuery.'),tool('Sweep','SWEEP','Circular section along an open line/polyline/spline path; optional CadQuery.'),tool('3D architectural walls','ARCH3D','Generate real wall solids with hosted door/window cuts; optional CadQuery.')],
 ('Manage','Applications'):[tool('Drawing assistant','ASSIST','Offline instructions or JSON proposals, with preview and one-step Undo.'),tool('AI proposals','AIPROPOSE','Optional user-configured compatible AI endpoint; session-only key and reviewed actions.')],
 ('Output','Plot'):[tool('Publish sheet set','PUBLISH','Ordered combined vector PDF from checked native paper layouts.')],
 ('Home','Utilities'):[tool('Architectural parameters','ARCHITECTURE','Edit walls, openings and rooms; export finish schedules.')]
}
PANELS=[(tab,panel,row,items+V16_TOOLS.get((tab,panel),[])) for tab,panel,row,items in PANELS]
TABS = tuple(dict.fromkeys(tab for tab, _, _, _ in PANELS))
V16_1_SUPPORT = {
    'WALL':'Straight parametric walls with automatic bounded corner miters and cleaned T/cross junction outlines.',
    'ARCH3D':'Generate or update linked wall solids with joined footprints and hosted opening cuts. Source edits update stable model IDs; optional CadQuery.',
    'VIEWBASE':'Generate linked Top/Front/Right edge projections from one solid. Source changes refresh the view; no hidden-line removal.',
    'VIEWPROJ':'Linked 2D projected edge blocks from one source solid. Placement is independent of regeneration.',
    'VIEWSECTION':'Linked X/Y/Z plane section from one solid; editable plane position and cached last-valid geometry.',
    'PROPERTIES':'Compact shared dock: appearance, typed positions/dimensions, architectural material/finish, block values and view plane, with one-step Undo.'
}
PANELS=[(tab,panel,row,[tool(t.label,t.command,V16_1_SUPPORT[t.command]) if t.command in V16_1_SUPPORT else t for t in items]) for tab,panel,row,items in PANELS]
PANELS=[(tab,panel,row,items+([
    tool('Refresh linked models / views','UPDATELINKS','Refresh live source links; cached geometry is retained and stale results reported when the optional kernel is unavailable.'),
    tool('Drawing checks','CHECKDRAWING','Free wall ends, hosted opening conflicts, invalid room boundaries and stale links; read-only screen marks and JSON report.')
] if (tab,panel)==('Home','Utilities') else [])) for tab,panel,row,items in PANELS]
BUILDING_TOOLS = {
    ('Home', 'Draw'): [tool('Slab','SLAB','Closed straight-edge boundary, editable thickness and holes, level and live model.'),tool('Ceiling','CEILING','Level-relative closed boundary and thickness.'),tool('Roof','ROOF','Rectangular Flat/Shed/Gable/Hip roof, slope and overhang.'),tool('Stair / Railing','STAIR','Straight/L/U solid-step stairs, landings and flight handrails.')],
    ('Home', 'Utilities'): [tool('Building tools','BUILDING','Compact creation forms, levels and live model tools.'),tool('Levels / Storeys','LEVELS','Saved floor elevations/heights, assignments and visibility.'),tool('Detect rooms','AUTOROOM','Enclosed wall spaces with seeded live room boundaries.'),tool('Quantity tags','QUANTITYTAG','Explicit Length/Area/Volume/Count measurement for plain geometry.'),tool('Slab / Ceiling opening','SLABHOLE','Select one object and one enclosed hole boundary.')],
    ('View', 'Visual Styles'): [tool('Building models','BUILD3D','Real live wall/slab/ceiling/roof/stair models; optional CadQuery.'),tool('Building drawings','BUILDVIEW','Multi-object linked sections, hatching and kernel hidden-line projections.'),tool('Materials','MATERIALS','Surface color/opacity, tile patterns and embedded image textures in software model previews.')],
    ('Manage', 'Applications'): [tool('Drafting chat','DRAFTCHAT','Conversational dock, offline commands or configured AI, validated previews and one-step Undo.')],
    ('Output', 'Export'): [tool('IFC4 export','IFCEXPORT','Typed building objects, storeys, opening relationships, materials and quantities; optional requirements-bim.txt.')],
    ('Output', 'Plot'): [tool('Bill of quantities','BOQ','Drawing-linked net quantities, explicit rates/allowance, source selection and CSV/JSON exports.')],
}
PANELS=[(tab,panel,row,items+BUILDING_TOOLS.get((tab,panel),[])) for tab,panel,row,items in PANELS]
PANELS.append(("Office", "Drafting and production", 32, [
    tool("Office blocks", "OFFICEBLOCKS", "Search and insert reusable blocks from a shared folder."),
    tool("Parametric door", "PARAMETRICDOOR", "Place a 2D door and edit width, angle, swing and handing in Properties."),
    tool("PDF review", "PDFREVIEW", "Align a PDF review overlay and track annotation status."),
    tool("Project sheets", "PROJECTSHEETS", "Publish a single PDF from saved layouts across drawings."),
    tool("Custom linetype", "LINETYPEDESIGN", "Design repeated text and dash patterns with a preview.")
]))
TABS = tuple(dict.fromkeys(tab for tab, _, _, _ in PANELS))
TOOLS = {item.command: item for _, _, _, items in PANELS for item in items}
