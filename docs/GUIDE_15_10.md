# PyCAD 15.10 — menu tools, themes and compact panels

This release implements the missing workflows named in the supplied one-page
menu guide and keeps the established drawing tools. It adds native clipboard,
Find/Replace, named text formatting, saved appearance/snap preferences,
persistent tangency and a Collaborate tab. Every guide row is mapped in
[Guide coverage](GUIDE_COVERAGE_15_10.md), including the supported scope.

## Install or update

For a new installation, extract **PyCAD-v15-Full.zip** into a writable folder.
Inside its `PyCAD-v15` folder run:

```bash
bash setup_ubuntu.sh
bash start.sh
```

For an existing **15.9.0** installation, close PyCAD and merge the contents of
**PyCAD-v15.10-Updated-Files.zip** into the folder containing `main.py`. Replace
matching files; avoid nesting `PyCAD-v15/PyCAD-v15`. Run `bash start.sh` and
check **15.10.0** in the title bar. The patch contains complete replacement files
and applies only to 15.9.0. Use the full ZIP for an older build.

Launchers and runtime dependency requirements are unchanged. A configured
`.venv-linux` can be reused. Windows retains `start_windows.bat`.
This release reads native schemas 1–8 and writes **schema 9**. Keep originals
if drawings must still open in an older build; new saves require 15.10 or later.

Open `examples/menu_style_study.pycad` for named text formatting and a persistent
LINE/CIRCLE tangency. `menu_style_reference.pycad` is its comparison reference;
`menu_style_shared.html` is an exported portable view. These are demonstration
drawings, not engineering deliverables.

![Actual workspace and text properties](workspace-v15.10.png)

## Themes and space colors

Open **Tools → Options / Theme**, **View → Palettes → Options**, or type
`OPTIONS` / `THEME`. On Appearance, choose **Dark**, **Light** or **Midnight**.
Click a color swatch for model space, paper sheet, 3D space, grid or accent.
**Apply** saves the choices immediately; **OK** saves and closes. Cancel discards
unapplied choices. Cancel after Apply leaves the applied preferences in place.

Preferences belong to this installation and survive restarting. Drawing layer
and entity colors remain drawing data. The paper-sheet color changes the on-screen
sheet; PDF output keeps its normal plotted paper. A light interface can be used
with a dark model background, or vice versa. Layer names and navigation icons
adjust their contrast for the light interface.

![Appearance controls](options-v15.10.png)

On **Drafting / OSNAP**, enable running snaps and choose Endpoint, Midpoint,
Center, Intersection, Perpendicular, Quadrant, Tangent, Nearest and Grid.
Set the pick radius in pixels and grid spacing in drawing units. Geometry snaps
take precedence; Grid is a fallback within the pick radius. Tangent snap points
need a construction point outside a circle. These running snaps are separate
from persistent `GCTANGENT` constraints. F3 still toggles object snaps.

`MENUBAR` followed by `1` shows classic menus; `0` hides them. The Quick Access
File button remains available. The visibility preference is saved.

## Compact File and Layers

File opens a category panel beside an action panel, bounded to **650 × 490 px**
on larger windows and reduced to fit smaller ones. It does not replace the
entire workspace. Actions use short labels; hover/focus shows the description
at the bottom. Long action lists scroll. Close File or Escape dismisses it.

![Compact File panels](file-panels-v15.10.png)

`LAYER` opens the **740 × 390 px** property dialog with filtering and all nine
columns: current indicator, name, visibility, freeze, lock, color, linetype,
lineweight and plotting. The abbreviated headers have full-name tooltips.
Color swatches open the color picker. New, Rename, Delete, Set current, Isolate
and Show all remain available; changes remain undoable. Protected/in-use layer
deletion rules still apply. The right Layers dock keeps its quick controls and
opens this compact manager through **Manage layers…**.

![Compact layer property dialog](layers-v15.10.png)

## Native clipboard

Select visible unlocked model objects and use **Edit → Copy to Clipboard** or
Ctrl+C. `COPYCLIP` is the equivalent command; `CUTCLIP` / Ctrl+X copies and
removes the selected objects with Undo. `COPY` remains the geometry-copy tool.
Copy uses the lower-left selection bounds as its insertion base.

Use Ctrl+V / `PASTECLIP`, then click or enter an insertion point. Paste imports
geometry, required blocks, named styles and layers, plus supported internal
dimension/hatch links and constraints. It creates fresh IDs, gives conflicting
definitions unique names, and converts physical units when needed. A copied
1000 mm line becomes 1 m in a metre drawing. Unitless/unitful mismatches require
assigning units first. A pasted Xref's cached geometry becomes a local block.

Paste is one undoable operation. Rejected input leaves the drawing unchanged.
Selected 2D model entities are supported; whole layouts, underlays and saved
solids are outside clipboard selection. The clipboard format is PyCAD-native,
not AutoCAD's clipboard format. Text fields retain their normal text clipboard
shortcuts. The payload limit is 32 MiB.

## Find and format text

`FIND` / Ctrl+F searches model TEXT and native MLEADER annotations. Choose Match
case or Include hidden layers, then double-click a match to locate it. Replace
all editable performs literal replacement with one Undo. Hidden/frozen/locked
objects are excluded from replacement even when included in search results.
Block-definition annotations are not searched recursively.

`STYLE` opens named text styles. Choose font family, bold/italic, width factor,
oblique angle and default height for newly created text. New copies the displayed
settings; Save updates the selected style; Current makes it the creation style;
Apply selected assigns it to selected editable TEXT. Standard/current/referenced
styles cannot be deleted. Font/width/oblique changes affect existing references;
changing the default height does not resize existing text.

Select one TEXT and use **Properties → Text → Edit / format…** or `TEXTEDIT`.
Edit plain multiline text, style, object height and rotation with Undo. Use
`MLEADEREDIT` for a native multileader's shared text and `MLEADERSTYLE` for its
arrow/landing/text style. All content remains plain Unicode text. Mixed formatting
runs, fields, columns and automatic wrapping are outside this release.

![Named text styles](text-styles-v15.10.png)

Native saves retain editable formatting. PDF uses vector text. DXF carries
font-family metadata, but fonts are not embedded and the receiving program may
substitute them. Width/oblique multiline annotations export as separate TEXT
rows. Existing dimension/multileader graphic-export limitations remain reported.

## Persistent tangency

Use **Parametric → Tangent** / `GCTANGENT`, then pick a LINE and CIRCLE or two
CIRCLEs. Initial placement chooses the line side or internal/external circle
relationship. Lines use their supporting line for tangency; the contact point
need not lie within the finite segment. Internal tangency requires different
radii. Arc segments and spline/solid tangency are not supported.

The relationship survives native saves, geometry edits and Undo/Redo. The
bounded sketch solver uses existing layer/locked-coordinate guards; conflicting
edits are rejected without entering history. DXF/DWG does not retain persistent
constraints, so use `.pycad` for the editable relationship.

## Shared views, comparison and cloud files

**Collaborate → Shared Views** / `SHAREDVIEWS` exports a single HTML file with
embedded SVG and images. Open it in a browser, drag to pan, wheel or buttons to
zoom, change the background, or print. It is a read-only snapshot of visible
model-space 2D content, without external scripts/resources. Fonts can still be
substituted by the viewer. It does not export an interactive solid model or
paper-layout viewer. Save/share the file yourself or upload it through Cloud.

**Drawing Compare** / `COMPARE` opens a native `.pycad` or `.dxf` reference in the
same units. It lists added, removed and changed objects, displays green/red/amber
2D overlays, and saves a JSON report. Closing clears the overlay without editing
the current drawing. Native IDs identify modifications; identical foreign-ID
geometry is paired, while other imports appear as added/removed. Layer/style
differences affect comparisons. Tables, block definitions, layouts, underlays,
constraints, units display settings and saved solids are also reported separately.

![Comparison panel](compare-panel-v15.10.png)

**Cloud Files** / `CLOUD` connects to a WebDAV collection URL you configure. Enter
its username and password, then Refresh. It can list files, upload a native
snapshot or shared view, and download `.pycad`, `.html` or `.zip` copies. HTTPS
is required except for localhost development. URL and username are saved;
password is session-only and cleared on close. Network work runs outside the
Qt UI thread. There is no bundled hosted account or live co-editing service.

New uploads use a create-only guard. Replacing a listed file uses its strong
server revision tag; if the server copy changed, the upload is rejected. Refresh
after uploading to get the new revision. Servers without strong tags require a
new filename. Downloads are bounded to 32 MiB and native drawings are validated
before being saved. Redirecting servers require their final collection URL.

## Validation and remaining work

The Linux/Qt offscreen regression suite reports **508 passed, 2 skipped**.
There are 56 new acceptance cases, including actual localhost WebDAV requests.
Rendered UI inspection includes 1440 × 930 and 840 × 650 windows. The validation
report records package checks and platform limits. Windows execution, a physical
GPU/printer and a production WebDAV provider were not exercised here.

The ribbon has eight tabs, 31 panels and 168 commands: 69 available, 76 limited,
23 planned. [Full coverage](RIBBON_COVERAGE_15_10.md) and
[the roadmap](ROADMAP_15_10.md) distinguish implemented scope from future work.
