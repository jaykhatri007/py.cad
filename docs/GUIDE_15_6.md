# PyCAD 15.6 user guide

This release adds precise cursor input, physical unit conversion, curved
dimensions and embedded reference images to the existing desktop application.
The compact ribbon, in-viewport navigation, layer and dimension-style managers,
File workspace and slim command bar remain available.

## Install or upgrade

Extract `PyCAD-v15-Full.zip` into a new folder. Open the extracted `PyCAD-v15`
folder and run `start_windows.bat`. Do not run from inside the ZIP. The launcher
uses an installed compatible 64-bit Python or offers installation when missing.
See `WINDOWS_START_HERE.txt` for setup and diagnostics. On Linux, use `start.sh`.

Check **15.6.0** in the title bar or F2 startup history. The changed-files ZIP is
only for 15.5.0: follow `UPDATE_15_6.txt`, replace every matching file and keep a
backup. There are no added runtime dependencies; PDF rendering uses QtPdf supplied
with PyQt6. No executable or installer is included.

Native `.pycad` drawings and `.pycadt` templates write **schema 6**. This release
reads schemas 1–6; earlier releases cannot open new saves. Preserve originals
when an older application must still use them.

## Try the included drawing

Open `examples/precision_drafting.pycad`. It contains an original embedded
reference plan, traced linework, a 60° angular dimension, an associative arc-length
dimension, layers and a Reference sheet layout. The reference starts locked with
28% opacity. Its original PNG and generator are included, but native loading does
not need the external image.

## Type exact lengths beside the cursor

1. Ensure **DYN / F12** is on. Start `LINE` or type `L` in the viewport and Enter.
2. Choose the first point and move the mouse. The live readout appears.
3. Type `100`; the small editor opens at the cursor. Press **Tab** to lock 100.
4. Type `30` in the angle field and press **Enter** or **Space**. The next point
   is exactly 100 drawing units from the base at 30° counterclockwise from +X.
5. Continue the next segment or press **Esc** to cancel the active command.

Tab can also open the editor after the first point. Tab locks a field only if
you entered a value; an empty field continues to follow the mouse. Tab cycles
the fields and selects text so you can replace it. Clearing a field frees that
value. Enter, Space or a viewport click accepts the current point. Invalid values
leave the command active and display a correction message.

| Tool/stage | Editable fields |
| --- | --- |
| LINE, PLINE, RAY, XLINE, SPLINE next point; DIST second point | Length, angle |
| RECTANGLE second corner | Width, height; mouse selects the quadrant |
| CIRCLE after center | Radius |
| ARC after center, first endpoint | Radius/length, start angle |
| ELLIPSE first axis endpoint | Axis length, angle |
| ELLIPSE second radius | Radius |
| MOVE/COPY after base point; STRETCH displacement | Distance, angle |

Lengths are in drawing units; typed angles are always degrees, even when angle
display uses radians or gradians. Explicit values control the point when they
conflict with snapping/Ortho. Free values continue to follow the effective mouse
position. Coordinates such as `12,34`, `@10,20` and `@100<45` still work through
command input. F12 off clears active input locks without committing a point.

Grip measurements remain read-only. Rotate/scale input and the final ARC sweep
stage retain their existing command workflows. Spline input measures the next
control-point chord, not the curved path length. Dynamic fields are for 2D Model
drafting; they are not a 3D solid parameter editor.

## Convert a drawing's physical units

Open `UNITS` (also the status-bar unit button or File → Drawing Utilities → Units).
Choose the target unit, check **Convert geometry to preserve physical size**,
review the conversion preview and accept. For example, 1000 mm becomes 1 m.

Leaving the checkbox off keeps coordinate numbers unchanged and reinterprets
their unit. Changing only display precision never rounds stored geometry.
Unitless geometry has no physical conversion factor: assign its actual source
unit first, then convert to the target unit.

Conversion updates model geometry, nested local blocks, block insertions,
dimension/text sizes, hatch spacing, fixed and driving constraint distances,
saved extrusion profiles/heights, underlay positions/sizes, and layout viewport
centers/scales. Linked DXF block reloads retain the conversion factor. Paper page
sizes, paper viewport rectangles and lineweights remain in millimeters. Angle
values remain unchanged. Solver tolerance is scaled within its supported range.

Conversion is validated before application and is a single Undo step. Undo/Redo
restores geometry and settings; Zoom Extents can reframe the view afterward.
Stored standards profiles and the embedded original imported DXF archive do not
change; a standards check may therefore report the new drawing unit.
Dimension annotation appearance is configured separately with `DIMSTYLE`.

## Angular and arc-length dimensions

**DIMANGULAR — from an arc:** run the command, click a circular ARC, then click
the dimension arc location. The annotation follows edits to the source arc.

**DIMANGULAR — from points:** run the command, click the vertex away from an
existing arc, click a point on the first ray, click a point on the second ray,
then place the annotation. The sweep is counterclockwise from the first ray to
the second; reversing their order changes which sweep is measured. Reflex
angles are supported. Zero-length arms and zero/full-circle angles are rejected.
Typed coordinates also work. These points are independent of nearby linework;
selecting two lines and maintaining line associations is future work.

**DIMARC:** run the command, select a circular ARC, then place the annotation.
Its value is the circular arc length, prefixed with an arc symbol. It follows
its source arc. Polyline and spline arc-length annotations are not supported.

Both use the current dimension style and a placement grip. Native saves retain
the annotation and arc association. Copies become independent annotations.
PDF plots render the annotation; DXF/DWG exports contain graphics rather than
native associative DIMENSION objects. Arc rendering uses short line segments.

## Attach and calibrate a reference

Use `PDFATTACH` or `IMAGEATTACH`, the Insert ribbon, or File → Import. For PDFs,
select one page if the document has multiple pages. A PDF page is rendered at
up to 150 dpi and scaled to its physical page width in the drawing unit. Images
are embedded PNG references; use the manager to set their intended width.

Run `UNDERLAYS` to select a reference and edit insertion X/Y, width, rotation,
opacity, visibility and PDF plot inclusion. Click **Apply** to commit edits.
**Lock placement and calibration** protects positioning and removal. To change
a locked reference's placement, clear the lock and Apply first. The manager's
Calibrate button selects that reference and returns to the drawing viewport.

1. Choose an unlocked reference in `UNDERLAYS` and click **Calibrate**.
2. Pick the first point of a known length in the reference, then the second.
3. Type the actual distance in drawing units and press Enter.
4. The image scales about the first point. Verify against another known length,
   then lock placement in the manager if desired.

Calibration affects only the reference; existing CAD geometry stays where it
was. Undo restores the previous position/scale. `UNDERLAYCALIBRATE` also starts
directly when exactly one visible, unlocked reference exists. Image pixels do
not supply object snaps; temporarily disable OSNAP to pick image features.

References display behind CAD geometry, participate in Zoom Extents and can be
plotted in Model or layout PDFs. They persist in native drawings/templates even
if the original PDF/image is moved or deleted. Attach, edit, calibrate and remove
operations are undoable. Closing the manager does not undo already-applied edits.

Limits: 20 references per drawing, 50 MiB source file, 4096 pixels per side,
8 MiB embedded PNG per image, approximately 32 MiB total PNG data (before base64) and
32 million decoded pixels. Large source images are reduced. No editable PDF
geometry, PDF/raster object snapping, vectorization, cropping, image relinking,
paper-space-only attachment or 3D underlays are implemented. DXF/DWG omits these
embedded references with an export warning; keep the native drawing or plot PDF.

## What is complete and what remains

The ribbon has seven tabs, 29 panels and 152 unique commands: 69 available,
58 enabled with stated limitations and 25 planned. Four previously planned
commands are now enabled: DIMANGULAR, DIMARC, PDFATTACH and IMAGEATTACH. UNDERLAYS
is an additional manager command. See `RIBBON_COVERAGE_15_6.md` and the in-app
Tool coverage browser for exact scopes. Planned commands remain visibly marked.

Full AutoCAD parity remains a long-term project. Advanced solid editing,
dynamic blocks, rich native annotation, generated drawing views, unsupported
file formats and production Windows packaging still need work. The staged
acceptance gates are in `ROADMAP_15_6.md`.

## Verification and known platform gaps

The full suite passed **356 tests**, with **1 Windows-only test skipped** on
Linux/Python 3.12/Qt offscreen. The 33 new cases cover real Qt cursor typing,
conversion and undo, constraint/block preservation, source-arc updates, native
validation, actual two-page PDF rendering, image orientation, calibration,
manager workflows, exports and PDF plots. Regression tests include existing
geometry, constraints, viewport, command, File and optional CadQuery workflows.

Actual 1440 × 930 screenshots were reviewed. With compact mode, the drafting
viewport is 1148 × 712, the input editor 300 × 68 and the command bar 29 pixels.
Window/dialog cleanup and configured autosave-directory issues found during
testing were corrected. See `TEST_RESULTS.txt` for commands and environment.

Windows startup, real GPU/driver rendering, ODA DWG conversion, physical printers
and macOS were not executed in this session. Test the included Windows workflow
on your machine before relying on this development build for production work.

## Research references

The implementation uses an original PyCAD interface, informed by documented
CAD workflows and Qt's API:

- [Autodesk: Dynamic Input](https://help.autodesk.com/cloudhelp/2026/ENU/AutoCAD-DidYouKnow/files/GUID-683349C0-E5C2-4E16-8846-5523E71172A9.htm)
- [Autodesk: DIMANGULAR](https://help.autodesk.com/cloudhelp/2023/ENU/AutoCAD-Core/files/GUID-6AB63ECB-BBCB-4D0F-B7BE-1674349A1FF9.htm)
- [Autodesk: arc-length dimensions](https://help.autodesk.com/cloudhelp/2026/ENU/AutoCAD-MAC-Core/files/GUID-30FE22ED-D019-4378-AE6F-FF26A1C246EA.htm)
- [Qt: QPdfDocument rendering](https://doc.qt.io/qt-6/qpdfdocument.html)
