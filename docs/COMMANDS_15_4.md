# PyCAD 15.4 command guide

This release implements 20 commands that were disabled in 15.3. All are marked
**Limited support** in the live tool catalog because their scope is smaller than
the corresponding AutoCAD subsystem. The ribbon is still the workbook-based
seven-tab layout. The in-viewport navigation and command entry remain available.

## Start with the included drawing

Open `examples/constrained_sketch.pycad`. The sample contains nine saved relations:
a fixed lower guide and parallel upper guide, concentric rings with driving sizes,
and connected perpendicular lines with a driving length. Drag the upper guide or
move a ring. Use `CONSTRAINTSETTINGS` to edit a driving value. Undo/redo restores
the exact previous/next solved geometry and its relations.

To regenerate the example from source, run `python -m examples.generate_constraints_demo`
from the application folder with the core dependencies installed.

## Constraint commands

Work in Model space / 2D drafting. Type a command over the viewport, then press
Enter or Space, or click its Parametric ribbon icon. Follow the command prompt.
Relations are chosen by picking existing geometry, not by preselecting objects.

| Command | How to use | Supported scope |
| --- | --- | --- |
| `GCCOINCIDENT` | Pick two anchors | LINE endpoints, POINT positions, CIRCLE/ARC centers |
| `GCCOLLINEAR` | Pick two lines | Keeps their infinite supporting lines collinear |
| `GCCONCENTRIC` | Pick two circles/arcs | Keeps centers coincident; sizes remain independent |
| `GCFIX` | Pick one object | Fixes the entire supported entity, including size/arc angles |
| `GCPARALLEL` | Pick two lines | Keeps line directions parallel |
| `GCPERPENDICULAR` | Pick two lines | Keeps line directions perpendicular |
| `DCLINEAR` | Pick two anchors; enter a distance | X distance by default; type `Y` or `X` before the value to change component |
| `DCALIGNED` | Pick two anchors; enter a distance | Straight-line distance between the anchors |
| `DCANGULAR` | Pick two lines; enter degrees | Directed line vectors define an angle greater than 0 and less than 180 |
| `DCRADIUS` | Pick a circle/arc; enter radius | Positive radius in drawing units |
| `DCDIAMETER` | Pick a circle/arc; enter diameter | Positive diameter in drawing units |
| `CONSTRAINTBAR` | Run to toggle | Shows/hides drafting labels; labels are not plotted |
| `DELCONSTRAINT` | Select objects, then run | Deletes their relations; with no selection, asks before deleting all |
| `CONSTRAINTSETTINGS` | Open the manager | Select a relation to edit its driving value or delete it; adjust labels/tolerance/iteration limit |

For dimensional commands, Enter accepts the displayed measured value. Esc cancels.
Endpoint coordinates may be typed in place of clicking an anchor. A driving
dimension is separate from an ordinary `DIM…` annotation: the `DC…` command changes
geometry, while ordinary dimensions measure it.

The solver runs after an edit is committed. A live mouse-drag preview can briefly
violate a relation. On commit, other free parameters can move to satisfy it; a
conflict restores the previous state and writes a reason in command history.
Locked, frozen and hidden constrained objects cannot move indirectly. Explicitly
edited endpoints keep both their X and Y coordinates. Undo/redo cancels an active
grip preview first. Unsatisfied geometry cannot be written to a native file.

Delete geometry to remove its relations; undo restores both. Copies/arrays are
independent geometry and do not inherit constraints. The native selection export
keeps only relations whose referenced objects are all included in the selection.

Current numerical scope: LINE, POINT, CIRCLE and ARC; at most **80 relations** and
**256 scalar parameters** in a drawing. Default tolerance is 0.000001 drawing units
and maximum iteration count is 80. The manager reports the local remaining scalar
degrees of freedom and residual. Redundant but consistent constraints may remain;
the solver does not promise a unique solution or identify a minimal conflicting set.
No polyline segments, block internals, solids, tangent/equal/symmetric relations,
automatic inference, expression variables or cross-document constraints yet.

## Object properties and layer translation

| Command | Workflow | Persistence / limits |
| --- | --- | --- |
| `TRANSPARENCY` | Select editable objects; enter 0–90 percent | Native, cloning, 2D rendering, PDF and supported DXF entities; does not change saved 3D solid materials |
| `HYPERLINK` | Select editable objects; enter a web URL; Save | Native and supported DXF entities; clear to remove; explicit button opens the URL; HTTP/HTTPS only |
| `LAYTRANS` | Choose source layer, then an existing target | Moves model/block geometry and saved extrusion layer references; source layer is removed except layer 0; one source/target per operation |

Transparency and hyperlink controls also appear in the Properties dock. Multiple
selected objects receive the same new property. All three changes are undoable.
Layer translation changes layer references; explicit per-object color/linetype
overrides remain overrides. There is no saved layer-mapping library yet.

## Native standards profiles

`STANDARDS` and `CONFIGURESTANDARDS` open the same manager. Capture the drawing's
current units and layer table, or load a previously saved JSON profile. Save JSON
exports that profile for another project. The active profile is stored in `.pycad`.

`CHECKSTANDARDS` compares the drawing against that active profile and reports
extra/missing layers, drawing units, and layer colors, linetypes and lineweights.
It makes no automatic repairs. Use the existing layer manager to resolve issues,
then run the check again. The sample drawing already has a matching profile.

Profiles use this format; other units/layers can be added through the manager:

```json
{
  "format": "PyCAD-Standards-1",
  "units": "mm",
  "layers": {
    "0": {"color": "#ffffff", "linetype": "CONTINUOUS", "lineweight": 0.25}
  }
}
```

Autodesk DWS files, dimension/text-style checking and automatic standards repair
are not implemented. These commands are native PyCAD standards workflows.

## Save and exchange

New saves use native **schema 4**. This release reads schema 1, 2 and 3 drawings,
but earlier PyCAD apps cannot open schema-4 files. Keep original drawings when
testing the upgrade. Undo history is not serialized.

Native `.pycad` retains constraints, object transparency, web hyperlinks and the
active standards profile. DXF/DWG export preserves the current supported geometry,
but does not serialize native constraint relations or standards profiles. The
export report warns about constraints. Reimporting an exported DXF does not recover
them. Unsupported DXF entity kinds retain the pre-existing importer limitations.

## Research references

The behavior design was checked against Autodesk's official command descriptions.
These sources define reference behavior; they do not certify PyCAD compatibility.

- [GEOMCONSTRAINT](https://help.autodesk.com/view/ACD/2027/ENU/?caas=caas%2Fdocumentation%2FACD%2F2014%2FENU%2Ffiles%2FGUID-D79452FB-DDA7-44C0-A9EA-F4EA656022D2-htm.html)
- [DIMCONSTRAINT](https://help.autodesk.com/view/ACDLT/2026/ENU/?caas=caas%2Fdocumentation%2FACD%2F2014%2FENU%2Ffiles%2FGUID-3208AA9B-A1D0-4541-B045-3D81CF6336C2-htm.html)
- [Applying and deleting geometric constraints](https://help.autodesk.com/view/ACD/2027/ENU/?caas=caas%2Fdocumentation%2FACD%2F2014%2FENU%2Ffiles%2FGUID-54069D14-97BF-42C5-8B42-9087A18C49D8-htm.html)
