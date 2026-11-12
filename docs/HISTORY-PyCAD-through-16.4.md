# PyCAD 16.4 — approved logo, open-source license and automatic setup

![PyCAD logo](assets/pycad-logo.png)

This release integrates the approved PyCAD logo into the compact workspace,
About window, application icon, native setup files and installed shortcuts.
Open **Help → Licenses and Legal** for the offline legal viewer. Original
project material and the combined application are distributed under
**GNU GPL version 3 only**; see [LICENSE](LICENSE), [COPYRIGHT](COPYRIGHT),
[third-party notices](THIRD_PARTY_NOTICES.md) and [license guide](legal/LICENSING.md).
Your drawings remain yours; commercial use is permitted under the license.

The package includes source, rebuild scripts, retained dependency notices,
license/source inventories, privacy/AI information and distribution guidance.
Read [the review and remaining publication checks](legal/RESEARCH.md) before
public distribution; this is not a worldwide legal-compliance certification.
See [UPDATE_16_4.txt](../CHANGELOG.md) and [validation](docs/VALIDATION_16_4.txt).

Open the native setup file for your OS. It detects the system, downloads a
private Python 3.12 runtime, installs the CAD/3D/IFC dependencies, checks startup,
adds an application shortcut and opens PyCAD. Existing system Python and drawing
folders are preserved. First setup needs internet and can require normal OS
security/administrator approval. A local progress page shows installation and
supports logs, cancellation and retry.

| OS | Native setup in `installer/packages` |
|---|---|
| Linux x64 (glibc 2.34+) | `PyCAD-Setup-16.4.0-Linux-x64.run` |
| Windows 10/11 x64 | `PyCAD-Setup-16.4.0-Windows-x64.exe` |
| macOS 13+, Intel/Apple Silicon | `PyCAD-Setup-16.4.0-macOS-Universal.zip` → PyCAD Setup.app |

Read [the current guide](docs/GUIDE_16_4.md) and [automatic setup details](docs/GUIDE_16_3_SETUP.md). Linux may require
**Allow executing file as program** before opening a download. Mac/Windows setup
files are unsigned test builds; native execution on those OSes was not tested.
One engine uses the appropriate executable format for each OS; a single native
file format cannot launch on all three. Full Linux ARM64 is not qualified.

The complete source and prior `start.sh`, `setup_ubuntu.sh` and
`start_windows.bat` workflows remain. Installer source/tests are in `installer`.
See [UPDATE_16_3.txt](../CHANGELOG.md) and
[the validation report](docs/VALIDATION_16_3.txt). The sections below retain the
16.2 feature and manual source workflow documentation.

## Application features retained from 16.2

Python desktop CAD with compact drafting, multiple drawing tabs, sheets and
optional real 3D solids. This release adds levels, slabs/ceilings, four roof
forms, three stair layouts with rails, automatic rooms, whole-building views,
visual materials, detailed drawing-linked BOQ/costs and IFC4 export. Interactive
drafting chat supports immediate offline commands and your own optional AI
service, with reviewed changes applied as one Undo step.

![Actual PyCAD 16.2 model workspace](docs/model-v16.2.png)

Read [the 16.2 guide](docs/GUIDE_16_2.md) for all nine features, quantities,
chat examples, setup and supported boundaries. The existing Dark/Light/Midnight
themes and separate model, paper, 3D, grid and accent colors are in OPTIONS.
File keeps bounded category/action panels; Layers and Properties stay compact.
The ribbon has 205 commands in eight tabs and 31 panels.

## Run

Extract the complete ZIP into a writable folder. In **PyCAD-v15**, Ubuntu users
run `bash setup_ubuntu.sh`, then `bash start.sh`. Windows users run
`start_windows.bat`. These are complete source builds with existing launchers,
not prebuilt executable installers. The core launcher/dependencies are unchanged.
Live solids/building views need `requirements-3d.txt`; IFC export additionally
needs `requirements-bim.txt`, installed in the same launching interpreter.
Optional wheels must support that OS/Python; QA used Ubuntu 24.04/Python 3.12.14.
Ubuntu 26.04/Python 3.14 core setup remains the launcher target, but optional 3D
on that environment and Windows execution were not exercised.

Use **PyCAD-v15-Full.zip** for a fresh install. The replacement-file patch is
for exactly 16.1.0; see [UPDATE_16_2.txt](../CHANGELOG.md). Native schema 12 reads
schemas 1–11; new saves require 16.2 or later. Keep original drawing backups.

## Example and verification

Start with **examples/v16_2_building.pycad**: two storeys, fourteen live solids,
three linked rooms, two building views and two sheets. Its reproducible generator,
BOQ CSV/JSON, IFC4 and two-page PDF are included. Rates are blank for your project
prices. Historical examples, tests and documentation are retained.

The [validation report](docs/VALIDATION_16_2.txt) records Linux/Qt regression
and fresh-package checks. Full AutoCAD/BIM parity is not claimed. Simple roof /
stair geometry is not structural design; imported linework needs measurement
tags for BOQ. Unchanged cached 3D displays without CadQuery; changed sources need
it to regenerate. Offline chat uses a bounded parser. Broader AI chat uses your
compatible provider/local model; no account, credits or model weights are bundled.

The sections below document historical releases.

## New in 15.6

- **Editable cursor measurements:** start LINE, choose a base point, type a
  length, press Tab, type an angle and press Enter or Space. The point is exact;
  the 300 × 68 pixel editor stays inside the drafting viewport. Rectangle inputs
  use width/height. Circle input uses radius. F12 toggles dynamic input.
- **Physical unit conversion:** UNITS now offers an explicit conversion option.
  For example, 1000 mm becomes 1 m. Geometry, blocks, constraints, annotations,
  saved extrusions, underlays and layout transforms convert together. One Undo
  restores the change. Leaving the option off keeps coordinate numbers unchanged.
- **Angular and arc-length dimensions:** DIMANGULAR accepts a circular arc or
  a vertex and two ray points; DIMARC annotates a circular arc's length. Arc-based
  annotations follow their source arc, use DIMSTYLE and have a placement grip.
- **PDF and image references:** PDFATTACH embeds a rendered PDF page; IMAGEATTACH
  embeds an image. UNDERLAYS manages position, width, rotation, opacity, plot
  visibility and locking. Calibrate a reference using two points and a known
  distance. Native files retain the image even if the original is moved.
- **Reliability fixes:** Qt event-filter cleanup no longer raises errors when
  windows are collected; reopening the Underlay Manager uses a fresh dialog;
  autosave creates the directory for its configured recovery path.

The compact ribbon and 29-pixel command bar remain. Open
`examples/precision_drafting.pycad` for a complete reference-and-dimensions demo.
Read [the 15.6 guide](docs/GUIDE_15_6.md) for exact workflows and limitations.

Extract **PyCAD-v15-Full.zip** to a fresh folder and run **start_windows.bat**.
The title bar/F2 startup history must show **15.6.0**. The update ZIP is only for
15.5.0; follow `UPDATE_15_6.txt`. Native drawings/templates now use **schema 6**.
This build reads schemas 1–6; older builds cannot read its new saves. Keep originals.

Validation: **356 tests passed, 1 Windows-only test skipped**, Linux/Qt offscreen.
All seven ribbon tabs and 29 panels remain: **152 unique commands**, comprising
69 available, 58 with defined limitations, and 25 planned. See
`docs/RIBBON_COVERAGE_15_6.md` for the actual command inventory.

PDF references are raster images, not editable PDF geometry. DXF/DWG export omits
underlays with a warning and exports curved dimensions as graphics. No Windows
executable is included, and Windows startup was not run here. This remains a
source development release; full AutoCAD parity is unfinished.

## Release history

The following sections describe their historical releases; use the 16.1
installation and format instructions at the top for this build.

## New in 15.5

- **Live cursor measurements:** length, angle and ΔX/ΔY while drawing a line or
  polyline; new length during line endpoint stretches; shape-specific radius,
  diameter, width/height, arc sweep and movement readouts. Values follow the same
  snapped/Ortho-adjusted coordinates as the preview. **F12** toggles the panel.
- **Drawing Units Manager:** `UNITS`, the status-bar unit button, or File →
  Drawing Utilities → Units. Choose mm/cm/m/in/ft/unitless, decimal/scientific/
  architectural length display, length precision, angle units/precision and
  trailing-zero suppression. Native drawings retain these settings; undo restores
  the previous settings. Units changes keep existing coordinate numbers unchanged.
- **File workspace:** click File to open the in-window left panel with New, Open,
  Save, Save As, Import, Export, Publish, Print, Drawing Utilities and Close.
  Native templates (`.pycadt`), Audit, validated backup recovery, undoable Purge and
  Status now work. Requested formats without an importer/exporter are explicitly
  marked unavailable; no placeholder is presented as a working converter.
- **Slim command bar:** one input row, 29 logical pixels in the tested layout.
  History is collapsed by default; **F2** or the small arrow/dot button expands it.
  Command history remains recorded. Errors also appear temporarily in the status bar.

Open `examples/live_measurements.pycad`, type `L`, choose a first point and move
the cursor. Press Esc to finish. See `docs/GUIDE_15_5.md` for supported workflows,
File actions, format availability and upgrade details.

Extract the full ZIP to a fresh folder and run `start_windows.bat`. Verify
**PyCAD 15.5.0** in the title bar (or F2 startup history). Apply the update ZIP only
to 15.4 using `UPDATE_15_5.txt`. New native files use **schema 5**; 15.5 reads older
schemas 1–4, but older apps cannot open new saves. Keep original drawings.

Validation: **323 passed, 1 Windows-only test skipped**, Linux / Qt offscreen.
The ribbon retains seven tabs and 29 panels, with 151 unique commands: 69 available,
53 limited and 29 planned. File-only commands and additional File format entries
are documented separately in the 15.5 guide. This is still a source development
release, not a complete AutoCAD replacement or a packaged Windows executable.

## Earlier: 15.4 constraints and standards

**20 formerly disabled commands now work within the scopes below.** The ribbon
still follows the supplied workbook's seven tabs and 29 panels. Parametric tools
now have distinct icons and persistent relationships in the existing viewport.

- Six geometric constraints: coincident, collinear, concentric, fixed, parallel
  and perpendicular.
- Five driving constraints: linear X/Y distance, aligned distance, line angle,
  radius and diameter. Change a driving value in `CONSTRAINTSETTINGS` to change
  the sketch. `CONSTRAINTBAR` toggles labels; `DELCONSTRAINT` removes relations.
- Object transparency and HTTP(S) hyperlinks, preserved in native files and
  supported DXF entities; layer translation with undo.
- `STANDARDS`, `CONFIGURESTANDARDS` and `CHECKSTANDARDS` capture/load/save and check
  native JSON profiles for units and layer properties. Autodesk DWS is not supported.

Constraints solve after committed edits, reject conflicts without adding an undo
step, and survive save/reopen. Supported entities are LINE, POINT, CIRCLE and ARC;
the solver is bounded to 80 relations / 256 scalar parameters. Polyline segments,
blocks, solid constraints, expressions and auto-inference remain future work.
Live drag previews may be temporarily unconstrained. Undo cancels active previews.
Copying geometry does not duplicate its constraints. Constraint labels do not plot.

Open `examples/constrained_sketch.pycad` to try nine working relations. Read
`docs/COMMANDS_15_4.md` for all new command workflows and file-format limits.
The 15.4 catalog had **149 unique commands: 69 available, 51 limited and
29 planned**. Limited commands are enabled with explicit scope; planned commands
remain disabled. See `docs/RIBBON_COVERAGE_15_4.md` and `docs/ROADMAP_15_4.md`.

`UPDATE_15_4.txt` describes the historical update to 15.4. That release wrote
schema 4. Use the 15.5 instructions above for the current update.
DXF/DWG exports include current geometry but omit persistent constraints and native
standards profiles. The constraint loss is reported before export.

Validation: **286 passed, 1 Windows-only test skipped** on Linux / Qt offscreen.
This remains a source release, without a prebuilt Windows executable. Full AutoCAD
compatibility and all remaining commands are not complete.

## Earlier: 15.3 reference ribbon

The supplied spreadsheet defines **Home, Insert, Annotate, Parametric, View,
Manage and Output**, with **29 panels**. This release uses that tab and panel
order, with original vector icons, larger primary actions, three rows of small
secondary actions, panel captions and additional-tool menus. The grouped ribbon
is 112 logical pixels high; **Compact** restores the 66-pixel icon-only strip.
Both modes scroll horizontally when needed. The setting persists between runs.
The in-viewport navigation rail, view cube, embedded orbit/four-view workspace
and viewport command entry from the previous release remain available.

New working commands include crossing-box stretch; isolate/off/restore/match
layers; plain multiline text; static center marks, parallel centerlines, tables
and leaders; continue/baseline dimensions; radius/angle/quick measurements;
window/realtime zoom; X-Ray display; selected-geometry export; CSV extraction;
DXF reference management; command aliases; page setup; PDF preview/batch export;
and local transmittal ZIP packaging. See `docs/RIBBON_GUIDE_15_3.md` for usage.
Table and leader blocks can be edited with the existing Block Editor.

**Every spreadsheet entry is represented, but every feature is not implemented.**
At the 15.3 release, the expanded catalog contained 149 unique commands: 69 available,
31 with stated limitations and 49 planned. Those counts included existing and extra commands,
not just new tools. Planned tools are disabled, with explanations in tooltips
and **Manage → Tool coverage**. Typing a planned command also explains the gap.
The then-planned constraints, rich associative annotation, DGN/PDF/point-cloud import,
AutoLISP/VBA, generated solid drawing views and other advanced subsystems remain
future work. `docs/RIBBON_COVERAGE_15_3.md` maps every panel to its spreadsheet row,
and `docs/ROADMAP_15_3.md` defines the remaining work and acceptance gates.

`UPDATE_15_3.txt` describes the historical 15.2-to-15.3 update; use the 15.5
instructions above for this release.

The application remains a source-code development release, not a complete
AutoCAD replacement or a prebuilt Windows executable.

## Earlier: 15.2 command input

Type directly from the drawing or any model pane. A small prompt appears near
the cursor, and **Enter, numeric-keypad Enter or Space** starts the command.
Aliases such as `L`, `C`, `REC` and `PL` work. After accepting input, keyboard
focus returns to the active viewport so you can immediately type the next value
or click a point. The bottom command line shows the same input and history.

For example: `L` Space, `0,0` Space, `@100,50` Enter draws a line. Press Enter
or Space with an empty entry to finish the active command where supported;
at the idle prompt it repeats the last command. Esc cancels input. Tab completes
a command suggestion; Up/Down recalls history. Spaces remain literal when
entering drawing text or a block name; use Enter to accept those strings.
Coordinate syntax is unchanged: `x,y` is absolute and `@dx,dy` is relative.

Compact mode uses **22-pixel icons** in 30-pixel buttons. Duplicate
New/Open/Save/Undo/Redo/Fit buttons beside the logo remain removed; menus and
keyboard shortcuts remain available.

## New in 15.1

Orbit and standard views now occupy the main drawing area. A 36-pixel navigation
rail, orientation cube and view selector appear inside the drafting canvas and
every model pane. Small panes use a horizontal rail to keep every button visible.
The previous modal model-view window has been removed.

The right dock groups Layers, Properties and the Model browser into tabs. Camera
orientations, pan and zoom remain intact when switching to drafting or changing
between single/four panes. Drawing commands return to the existing 2D canvas.
The Fit command now centers asymmetric models using their projected bounds.

## Start

Windows: extract the whole archive into a writable folder and double-click
`start_windows.bat` beside `main.py`. The repaired launcher searches for an
installed 64-bit CPython 3.11–3.14, preferring 3.12 for a new environment.
If none is found, it offers to install Python 3.12 using WinGet.
First launch downloads the core dependencies. A working environment is reused
on later launches; an unusable `.venv` is preserved as a backup before repair.
See `WINDOWS_START_HERE.txt` for troubleshooting and manual installation.
Python 3.12 remains recommended for the optional solid-modeling kernel.
The Windows launcher and 3.13/3.14 app compatibility need real Windows testing;
the included Windows CI smoke test covers setup and restart when run there.

For manual setup with an installed Python 3.12:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe main.py
```

Linux/macOS: use `sh start.sh` in a working desktop session or run `python main.py`
in your Python environment. The default renderer uses Qt software painting.

Open `examples/pavilion_study.pycad`, then **Manage & Views → Four views** to
inspect five saved extrusions. `examples/studio_plan.pycad` is the 2D drafting
sample. These are illustrative designs, not construction documents.

The 3D viewer and saved extrusions work with the core dependencies. To export
real STEP/STL solids, install the optional kernel:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-3d.txt
```

## New in v15

| Workflow | Access | Implemented controls |
| --- | --- | --- |
| Dimension Style Manager | `DIMSTYLE` or `D`; Dimension menu; Manage & Views ribbon | Named styles, create from selected, modify, set current, apply to selected dimensions, guarded delete; text height/gap/color, extension offset/overshoot, arrow type/size, decimal precision, prefix/suffix, trailing-zero suppression, overall scale; live preview |
| Layer Properties Manager | `LAYER` or `LA`; Tools menu; Layers dock; Manage & Views ribbon | Search, new/rename/delete/current, on/off, freeze/thaw, lock, color, linetype, standard lineweight, plot toggle, isolate/show all |
| Saved 3D extrusions | Select one circle/rectangle/simple closed polyline, then `EXTRUDE` | Independent profile snapshot and signed height, saved in `.pycad`; rename, height edit, delete, undo/redo, STEP/STL export |
| Standard views | View menu or viewport selector | Top, Bottom, Front, Back, Left, Right, Isometric |
| Multiple model panes | `VPORTS` | Four independent viewing cameras, single-pane mode, active-pane border, fit all |
| Free orbit | `3DORBIT` or drag in any model pane | Unrestricted orbit, pan, zoom, axis triad, shaded faces/edges or wireframe |

All style, layer and extrusion changes use the document undo history. The
current dimension style affects new dimensions; editing a named style updates
existing dimensions that reference it. Click **Save style changes** to commit
manager fields. **Apply to selected dimensions** assigns the chosen style to
editable dimensions selected before opening the manager.

Dimension sizes are in drawing units multiplied by the style scale. For a
millimetre drawing intended for 1:100, a text height of 2.5 and scale of 100 gives
250 model units. Legacy dimensions migrate to Standard (2.5 units, scale 1);
adjust its scale if an older drawing's dimensions appear small. Display, PDF
and exploded DXF graphics use the same annotation primitives.

Lineweight is in paper millimetres. Layer linetypes affect entities whose
linetype is **BYLAYER**; this is the default for new drawing commands. Frozen
layers disappear from drawing/model views and plots. A non-plot layer stays
visible on screen but is omitted from PDF. Layer 0 and layers containing model,
block or saved 3D geometry cannot be deleted; the current layer cannot freeze.

## 3D navigation

- The navigation controls are already visible when the application starts.
- Click the orbit icon on the right edge of the drawing to enter the embedded
  model view, then left-drag over the model. No separate viewer opens.
- Click a pane to activate it; its border turns cyan.
- The small icon rail contains Orbit, Pan, Zoom in/out, Fit and Isometric.
  Hover over a button for its tooltip. Orbit is selected by default in model views.
- In Orbit mode, Shift+middle-drag also rotates. Middle-drag and right-drag pan;
  Shift+left-drag temporarily pans. The Pan button makes left-drag pan.
- The selector in each pane's upper-left corner offers Top, Bottom, Front, Back,
  Left, Right, Isometric, Free orbit, Single view, Four views and 2D drafting.
- Click a visible face of the upper-right cube to align with that face. Drag the
  cube to orbit; double-click it for Isometric. In drafting, releasing a cube drag
  opens the resulting model angle.
- Wheel zooms. Double-click the model, Home or Ctrl+0 fits the active pane;
  Fit all fits every pane. Changing layouts preserves zoom; use Fit when needed.
- Select an extrusion in the list to highlight, rename, change its height,
  delete it or export it. Locked layers prevent edits.
- Esc in a model pane, the 2D drafting selector entry, Return to drafting, or the
  `PLAN` command returns to 2D. Typing in a model pane starts command-line input.
- The Pan button also works in 2D; Esc restores normal drawing/selection.

These are orthographic model inspection panes, separate from printable
paper-space viewports. A flat 2D drawing lies at Z=0 and looks edge-on from
Front/Left/Right; saved extrusions supply height. Text, dimensions and hatches
remain in the 2D workspace. Plan outlines are shown automatically when no visible
solids exist. The optional 2D outline overlay draws them on top of shaded solids.
Camera positions/layout persist during this document session and are not saved
in the project.

## Existing drafting tools

Line, Point, Polyline, Circle, Arc, Ellipse, Ray, XLine, Rectangle, fit-point
Spline, Text, Hatch; Move, Copy, Rotate, Scale, Mirror, Trim, Extend, Offset,
Fillet, Chamfer, rectangular/polar arrays; supported geometry varies by command.

Snaps include endpoint, midpoint, center, intersection, perpendicular, quadrant,
tangent and nearest. F3 toggles snaps; F7 grid; F8 Ortho. Enter `x,y`, `@dx,dy`
or `@distance<angle` when a tool requests points. Esc cancels. DIST and AREA
report measurements. Click selection uses distance; crossing selection remains
bounding-box based. Single-object grips, properties, blocks, cached xrefs,
layouts and vector PDF export remain available.

## Save, export and recovery

Save editable work as **`.pycad`**. Schema 5 preserves dimensions and style
references, layer settings, blocks, layouts, independent extrusion records,
persistent constraints, object properties, unit formatting and the native standards profile.
The loader also accepts schemas 1–4; earlier apps cannot open schema 5.
Native saves use atomic replacement and a validated `.bak` file. Autosave
recovery is under `~/.pycad/recovery.pycad`.

DXF/DWG export supports a 2D subset. Dimension appearance exports as LINE/TEXT/
SOLID graphics, not editable DXF DIMENSION objects; DXF dimension import still
uses graphics. Layer properties round-trip for the supported linetypes and
standard lineweights. Unsupported imports are reported and protected from
unsafe source overwrite. DWG requires an external ODA File Converter.

**Drawings containing saved extrusions block DXF/DWG export** to prevent silently
losing their 3D content. Save `.pycad` or export each extrusion to STEP/STL from
the model workspace. Each extrusion owns an independent profile snapshot;
editing its original 2D profile does not update the extrusion. Exact circular
profiles are retained for solid export even though the viewer tessellates them.

## Limits and next steps

The software viewer uses depth-sorted polygons, not a GPU depth buffer;
intersecting solids can show occlusion artifacts. This release does not provide
Boolean operations, arbitrary B-rep editing/import, perspective, UCS editing,
face/edge picking, persistent camera layouts or 3D drawing tools. Dimension
styles do not yet include automatic fit, alternate units, tolerances,
annotative scales, font families or advanced dimension types. Layer states,
per-viewport overrides, layer transparency and complete ByBlock inheritance remain
future work. See `docs/ROADMAP_V15.md` for acceptance gates.

## Validation and packaging

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m PyInstaller packaging/pycad.spec
```

`docs/TEST_RESULTS.txt` records actual local checks. Windows/macOS, real GPU
execution, real DWG conversion and an installer have not been validated in this
session. This download is the complete source project, not a Windows EXE.

See `docs/GUIDE_V15.md`, `docs/ROADMAP_V15.md`, `docs/CHANGE_MANIFEST.json` and
`DEPENDENCIES_AND_LICENSES.md` for workflow details, provenance and dependency
notes. The local Python console runs code with your user's permissions.
