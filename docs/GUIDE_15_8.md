# PyCAD 15.8 — associative drafting dimensions

This release builds on your working Ubuntu 26.04 installation. It adds two-line
angular annotations and signed X/Y ordinate annotations. The compact ribbon,
slim command bar, cursor command input, units manager and embedded orbit remain.

## Install on Ubuntu

For a new application folder, extract the full source ZIP and run inside its
`PyCAD-v15` folder:

```bash
bash setup_ubuntu.sh
bash start.sh
```

For an already configured **15.7.0** installation, close PyCAD and merge the
update ZIP's `PyCAD-v15` contents into the existing folder containing `main.py`.
Replace matching files without creating a nested `PyCAD-v15/PyCAD-v15` directory.
Then run `bash start.sh`. This update adds no runtime dependencies, so the
existing `.venv-linux` can be reused. Setup and launch scripts are unchanged.
The full source ZIP also retains `start_windows.bat` for Windows.

Keep copies of your drawings. This release reads native schemas 1–6 and writes
**schema 7** for the new annotations and source metadata. Newly saved drawings
need **15.8 or later**; 15.7 cannot read schema 7. No conversion is needed to open
older `.pycad` files here. DXF exports retain the established fidelity warnings.

## Try the supplied drawing

Open `examples/setting_out_study.pycad`. It contains a 45-degree partition angle,
X ordinates of 0 and 120, and a Y ordinate of 70, all in millimetres. Select an
annotation and open the Properties tab to see its datum, value and link status.
Grip-edit the angled partition's endpoint: its angle updates after the edit is
committed. Move a linked boundary endpoint: its ordinate updates. Undo restores
the source geometry and the annotation. Save and reopen to retain the links.

## Angular dimension from two lines

1. Type `DIMANGULAR` in the viewport and press Enter or Space.
2. Pick the first LINE, then a different LINE.
3. Move the cursor into the angle sector you want to annotate and click.

Placement selects one of the four sectors made by the infinite supporting
lines. This works even when the finite segments do not meet. Moving to another
sector before placement changes between the acute and obtuse angle. The live
cursor panel shows the selected angle and annotation radius; F12 toggles it.
Two preselected LINE entities also start directly at placement.

The saved link retains two directed rays. Subsequent endpoint edits follow those
rays; a change that crosses their order can produce a reflex counterclockwise
angle. Move the dimension's placement grip to change its radius, not its saved
sector. To choose a different sector, create a new two-line annotation.

`Points` (or `P`) switches to an independent vertex/two-ray workflow.
`Lines` (or `L`) explicitly requests line selection. `Arc` (or `A`) requests a
circular arc. Keywords reset the unfinished selection. Explicit coordinate input
at the first step uses independent points even over existing geometry. Arc-based
angles and DIMARC retain their existing behavior.

Only model-space LINE entities support the two-line link. Polyline segments,
block internals, construction lines and 3D edges are not selectable sources.
Zero-length lines and parallel lines are rejected. The nearly parallel cutoff
is an absolute sine of 1e-10; intersections outside ±1e12 units are rejected.

If a linked source later disappears or becomes invalid, the last valid angle
is retained. Properties reports the reason. Restoring the source, including
Undo, resumes updates. Check that status before relying on a frozen measurement.

## X/Y ordinate dimensions

1. Type `DIMORDINATE` and press Enter or Space.
2. Optionally type `Origin` (or `O`), then pick or enter the datum coordinate.
   The default origin is world `0,0`, independently for each new annotation.
3. Type `X` or `Y` to choose the coordinate axis, or leave it automatic.
4. Pick the feature point, then place the leader endpoint.

With no explicit axis, a predominantly vertical leader measures X and a
predominantly horizontal leader measures Y. The axis can be changed with X/Y
before placement. The value is signed: feature `75,90` relative to origin
`100,100` measures **X = -25** or **Y = -10**. This is a coordinate from the
datum; changing the leader's length does not change that measurement.

Click near a LINE endpoint, a POINT or a CIRCLE/ARC center to link to that anchor.
Typed coordinates create independent feature points. Unsnapped free points are
also supported. Coordinates accept `x,y`, `@dx,dy` and `@distance<angle`.
The cursor readout shows the selected coordinate and both datum coordinates.

Each annotation stores its own fixed datum and world X/Y axis. There is no UCS
or rotated datum system yet. Its placement grip edits the leader endpoint.
Copies are independent annotations. Source deletion retains the last coordinate
and shows a missing-source status; restoring the source resumes updates.

## Styles, units and interchange

DIMSTYLE controls annotation text size, precision, prefix/suffix and extension
offset. Ordinate leaders use a two-segment dogleg without arrows. All new
annotations support color, transparency, layer visibility/locking, native
save/reopen, undo/redo, selection export and explicit physical unit conversion.
Angular measurements stay in degrees during conversion; ordinate coordinates,
their datums and leader positions rescale with the drawing.

PDF uses the shared annotation renderer. Model-space fitted plots now include
dimension labels and arrows in their bounds to prevent edge clipping. Paper
viewports still apply their intentional clipping rectangles.

DXF/DWG export emits dimension graphics and text, **not editable associative
DIMENSION objects**. Native `.pycad` files preserve the links. A selected
dimension exported without its sources becomes an independent snapshot; a
selection containing all required sources keeps those links.

## Remaining work

The ribbon has 153 commands: 69 available, 59 with defined limitations and
25 planned. This release expands annotation, but does not claim those 25 planned
commands are implemented. See `RIBBON_COVERAGE_15_8.md` for exact scope and
`ROADMAP_15_8.md` for the next milestones.

Regression and UI checks here use Linux/Qt's offscreen backend. Windows execution,
native Wayland, physical GPU/printer testing and a fresh Ubuntu 26.04 hardware
run of this new release remain outstanding. Your successful 15.7 Ubuntu smoke
check is the platform baseline, not a test of the new annotations.
