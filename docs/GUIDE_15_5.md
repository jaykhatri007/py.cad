# PyCAD 15.5 — live drafting and File workspace

This release combines the requested live cursor measurements, drawing units
manager, File left panel and a smaller command bar. Start with the complete ZIP;
the changed-files ZIP upgrades 15.4 only. Run `start_windows.bat` and verify 15.5.0
in the title bar. The full source, tests and actual UI screenshots are included.

## Live measurements

Open `examples/live_measurements.pycad`. Type `L` over the viewport, press Enter
or Space, click the first point and move the cursor. A small panel follows the
cursor with Length, Angle, ΔX and ΔY. The measurement follows the same object-snap
or Ortho-adjusted point as the tool. It stays inside the viewport and moves away
from the command-entry panel; in very small panes command entry takes priority.

**F12**, the **DYN F12** status button, View → Live Measurements, or `DYNMODE`
toggles these readouts. This is a read-only measurement display; `DYNMODE` here is
a toggle, not AutoCAD's multi-value system variable. Command entry remains enabled.

| Operation | Live readout |
| --- | --- |
| LINE / PLINE | Current segment length, angle, ΔX and ΔY; rebases after each point |
| LINE endpoint grip | New overall line length and direction, endpoint deltas |
| Polyline / rectangle vertex grip | Adjacent edge lengths and grip movement |
| CIRCLE / circle radius grip | Radius and diameter |
| RECTANGLE | Width, height, diagonal and perimeter |
| ARC | Radius, then sweep, arc length and end direction; arc endpoint grips supported |
| ELLIPSE | First-axis radius/direction, then both radii |
| MOVE / COPY / body drag | Movement distance, direction and deltas from the base point |
| STRETCH | Base-to-target movement; resulting line length when one line is affected |
| ROTATE | Rotation angle from +X |
| SCALE by reference | Reference distance, then scale factor |
| DIST / RAY / XLINE | Distance to the next point and direction; not infinite object length |
| SPLINE | Next control-point chord; not the fitted curve's arc length |

Angles are measured counterclockwise from the world +X direction. Readouts are
for 2D Model-space tools, not measurements of 3D faces/edges or paper-space layout
editing. A zero-length direction displays zero. Arc sweep is counterclockwise.
Measurements are transient UI and are not drawing entities or plotted annotations.

Grip and command previews remain previews. Constraints solve when the edit is
committed; a conflict may reject it or move other free geometry. F12 during a grip
preview neither commits nor cancels the edit. Esc cancels and hides the readout.

The panel does not provide editable Tab-to-lock distance/angle fields. Existing
coordinate entry continues to work: `x,y`, `@dx,dy` or `@distance<degrees`, followed
by Enter/Space. For example, `@100<45` specifies 100 drawing units at 45 degrees.

## Drawing Units Manager

Open `UNITS`, click the current-unit button at the bottom right, or choose
File → Drawing Utilities → Units. The Home / Utilities ribbon also includes Units.

| Setting | Choices / behavior |
| --- | --- |
| Drawing unit | mm, cm, m, inches, feet or unitless |
| Length display | Decimal, scientific, architectural feet/inches |
| Length precision | 0–8 decimal places; architectural precision from whole inches to 1/256 inch |
| Angle display | Degrees, radians or gradians |
| Angle precision | 0–6 decimals |
| Trailing zeros | Keep or suppress decimal trailing zeros |
| Live measurements | Application-wide visibility preference, also controlled with F12 |

Drawing units and formatting are stored per native drawing and form one undoable
change. Display precision never rounds the stored coordinates. Settings are used
by live readouts, the coordinate display, Properties and `DIST` reports. Ordinary
dimension annotations retain their own `DIMSTYLE` formatting.

**Changing drawing units does not rescale existing geometry.** A coordinate length
of 1000 stays 1000. Changing mm to m reinterprets that length as 1000 m. Physical
unit conversion of a whole project is not part of this manager. Architectural
display converts the selected physical unit to feet/inches for display; 304.8 mm
displays as 1 foot. Architectural display is disabled for unitless drawings.

Angle display settings do not change numeric command input: angles are still
entered in degrees. Typed distances are still numbers in the drawing unit, not
feet/inches text expressions. The manager shows a sample before you accept.
Cancel changes nothing. Paper-space coordinate readouts represent paper millimeters.

Native `.pycad` drawings and `.pycadt` templates preserve all these settings.
DXF/DWG preserves the existing supported drawing-unit metadata, but not PyCAD's
custom display formats/precision; exporting customized display settings reports
that limitation. Import does not add automatic block insertion-unit conversion.

## Slim command bar

The default command bar is a single input row, **29 logical pixels high** in the
tested Qt layout. Its previous dock title and permanently visible history area
are removed. Actual size may vary with platform fonts/display settings.

**F2** or the small arrow/dot button expands or collapses the history. A dot means
new messages have been recorded while history is collapsed. Errors also appear
briefly in the status bar. Input text is retained when toggling history; up/down
recall, Tab completion, Enter/Space and viewport typing continue to work. The
history retains the existing 500-block limit. Expanded state is an app preference.

## File left panel

Click **File** to open the panel inside the main window. The left side contains
all requested groups. The right side shows actions and their scope. Open includes
recent drawings. **Back to drawing** or Esc closes the panel. Opening File cancels
the current drawing command or uncommitted grip preview. It does not close the file.

| Group | Working actions | Unavailable entries shown explicitly |
| --- | --- | --- |
| New | Blank drawing, from native template, new layout/sheet | Sheet-set project |
| Open | Native drawing, DXF, DWG through ODA, recent drawings | DWF/DWFx, sheet set |
| Save | Native drawing | — |
| Save As | Native drawing, native template, DXF, DWG through ODA | Autodesk DWT is not the native template format |
| Import | Open DXF/DWG as current drawing; attach DXF reference | PDF, DGN, IFC, STL, image/point-cloud import |
| Export | PDF, DXF, DWG through ODA; selected closed-profile extrusion to STEP/STL with CadQuery | DWF, DWFx, FBX, 3D DWF |
| Publish | Local eTransmit ZIP with direct DXF references | Integrated email/send and 3D print service upload |
| Print | Vector PDF plot, preview, page setup, batch PDF ZIP | Direct physical printer selection remains outside this workflow |
| Drawing Utilities | Audit, Recover, Purge, Units, Status | Corrupt DWG repair is not provided |
| Close | Close current drawing to a blank document; Exit | Multi-document Close All is not applicable to the current single-document app |

Disabled format entries are availability indicators, not working import/export
commands. This release adds the File organization and native utilities; it does
not implement every listed external format or service. Sharing creates a local
package; nothing is emailed, uploaded or sent to a print service automatically.

Keyboard shortcuts remain: Ctrl+N New, Ctrl+O Open, Ctrl+S Save, Ctrl+Shift+S Save
As, Ctrl+P Plot/PDF, Ctrl+Q Exit. Unsaved-change prompts remain active for document
replacement and exit. `FILE` opens the panel; `CLOSE` closes the current drawing.

## Templates and drawing utilities

- **Native template:** Save As → Drawing template, or `SAVETEMPLATE`, creates a
  `.pycadt` file with the current geometry, units, styles, layers and layouts.
  It does not change the current drawing's filename or save state. New → Drawing
  from template, or `NEWTEMPLATE`, loads it as a new unnamed document. These are
  PyCAD templates, not Autodesk `.dwt` files. Relative external references are
  resolved to absolute paths so loading from another folder preserves their location.
- **AUDIT:** validates native structure, supported geometry, internal references,
  layers/styles and constraint consistency. It does not modify the drawing or
  certify engineering validity, external files or proprietary DWG internals.
- **RECOVER:** opens a valid `.pycad` or native `.bak` as an unsaved document,
  leaving the backup untouched. Invalid/corrupt files are rejected while retaining
  the current document. This is backup restoration, not arbitrary file repair.
- **PURGE:** previews unused local blocks, layers and dimension styles. Confirm
  removal, then use Undo to restore them. Referenced/nested blocks, external
  references, used/current layers/styles, layer 0, Standard, extrusion layers and
  layers required by an active native standard are protected. Object identities
  remain intact for earlier undo steps.
- **STATUS:** shows filename/save state, drawing units, current layer, object type
  counts, layers, blocks, layouts, extrusions and constraints.

## Compatibility and verification

Version **15.5.0** writes native **schema 5** and reads schemas 1–4. Older PyCAD
versions cannot read new schema-5 drawings; keep original copies when upgrading.
The full ZIP includes every source file. The update ZIP contains every new/changed
file compared with 15.4 plus launcher/dependency support files. No deletions or new
runtime dependencies are needed. Follow `UPDATE_15_5.txt` for installation.

**323 tests passed, one Windows-only test skipped**, on Linux/Python 3.12 with Qt
offscreen. Checks include real viewport events, snap/Ortho, grip undo/constraints,
panel bounds/input overlap, native unit persistence and malformed settings, File
panel navigation, templates, recover failure preservation, purge dependencies/undo,
the slim bar and F2 behavior. Actual Qt screenshots are in `docs/*-v15.5.png`.
Real Windows startup, macOS, a GPU context, ODA conversion and physical printing
were not exercised here. This is a source development release.

The current ribbon has 151 unique commands: 69 available, 53 limited and 29
planned. `RIBBON_COVERAGE_15_5.md` records the scopes. File-only utilities are
additional to those ribbon counts. The larger CAD roadmap in `ROADMAP_15_4.md`
still applies, including unsupported formats, richer annotation and solid modeling.

Reference behavior was researched in official Autodesk documentation:
[Dynamic input](https://help.autodesk.com/cloudhelp/2026/ENU/AutoCAD-DidYouKnow/files/GUID-683349C0-E5C2-4E16-8846-5523E71172A9.htm)
and [Drawing units](https://help.autodesk.com/view/ACDLT/2026/ENU/?caas=caas%2Fdocumentation%2FACD%2F2014%2FENU%2Ffiles%2FGUID-75419F91-18B8-47EE-9272-3196ACC95977-htm.html).
PyCAD implements the explicitly described subset above, not full product equivalence.
