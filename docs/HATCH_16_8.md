# Hatch and fill — PY.cad 16.8

Open **Draw → Hatch and fill…**. Select closed circles or polylines first to fill
selected objects; without a selection, apply the settings, click inside an
area, then press Enter. The live preview shows a sample island cutout.

## Patterns and appearance

- 172 named patterns from the installed ezdxf 1.4.4 library: ANSI, ISO, brick,
  concrete, gravel, wood, steel, dots and other architectural/mechanical fills.
- LINES is a user-defined parallel fill; its spacing is in drawing units.
- Scale multiplies every base coordinate, offset and dash in the definition.
  Scale 2 doubles its dimensions. Angle rotates the pattern in degrees.
  A library pattern's built-in angle is added to the requested rotation.
- Origin X/Y sets the world-space pattern anchor. Use the same origin on
  adjacent hatches to align them. The editor can use a boundary's minimum X/Y.
- Double adds a copy rotated 90 degrees about the pattern origin.
- Color accepts BYLAYER or #RRGGBB; optional background accepts #RRGGBB.
  A blank background remains transparent. Object transparency is 0–90 percent.
- Linear, radial and conical gradients have a second color and angle control.
- Search narrows the pattern list. **Import PAT…** reads bounded UTF-8 PAT files,
  including multiple families, dots, dashes, signed gaps and oblique offsets.
  Imported patterns are retained in local settings; the selected definition is
  embedded in the drawing, so recipients do not need the original PAT file.

The library definitions are supplied by ezdxf under its retained MIT notice.
No AutoCAD application, SDK or Autodesk PAT file is bundled. Import only custom
files you have rights to use and redistribute.

## Boundaries and islands

Select multiple closed boundaries for one undoable operation. Separate outer
boundaries produce separate hatches. Contained loops become islands, including
nested loops. Crossing/touching boundaries are rejected.

- **normal:** alternate filled/empty nested regions using the even/odd rule.
- **outer:** exclude the first level of islands and everything inside them.
- **ignore:** fill over all islands while retaining their geometry for editing.

Selected boundary links update after undoable source edits. Delete a source and
its last available outline remains; copied hatches detach unless the clipboard
also includes their source objects. Uncheck the link option in the hatch editor
to detach. Pick-point boundaries assembled from independent edges remain a
snapshot; selected circles/closed polylines can remain linked.

Pick-point detection uses the visible view. Exact closed objects are preferred;
mixed lines/arcs use the existing sampled flood boundary. **Pick gap tolerance**
optionally joins nearby loose endpoints for that detection only; source lines
are never modified. Zero disables joins. Results for mixed boundaries are
approximate and depend on the view's sampling resolution. Separate line/arc
island loops that are not closed objects are not automatically reconstructed.

## Edit and reuse

- **HATCHEDIT:** select one or more editable hatches and change their settings
  together. One undo restores all changed values. Locked layers are excluded.
- **HATCHSETTINGS:** open the full creator/settings dialog.
- **HATCHBOUNDARY:** recreate closed polylines for outer and interior loops.
- **HATCHTOBACK:** send selected editable hatches behind the rest of the drawing.
- **HATCH:** pick an area with remembered settings. Before committing, type
  Settings, a pattern name, SOLID, or angle,spacing; Enter applies the settings.
- Standard copy/paste, move, rotate, scale, mirror, units and undo workflows retain
  pattern information. Custom mirror families preserve their phase/offsets.

![Hatch editor](PYcad-16.8-Hatch-Editor.png)

## Interchange, plotting and limits

Native .pycad files retain all options and custom definitions. Schema 12 readers
from older builds may reject the new hatch fields; open these drawings with
16.8 or newer. Old solid/parallel-line records still load with defaults.

DXF export embeds the actual transformed line-family definitions and retains
island style, colors/background and transparency. Import supports polyline,
arc/ellipse/spline edge paths (curves are sampled to polygon boundaries) and
multiple separate exterior loops. Native boundary associations are not exported
as DXF source-handle links. Third-party CAD applications may interpret gradient
spread differently. Linear/radial gradients map to LINEAR/SPHERICAL. Other DXF
gradient styles are approximated as radial with an import warning. Conical
fills work natively and in PDF; DXF export explicitly asks you to change them
to linear/radial, because DXF HATCH has no matching conical type.

Screen patterns below two pixels per row use a density preview. Excessive
families/dash workloads also use a preview instead of hanging. Vector PDF plots
retain pattern spacing and clipping; an excessive plot is rejected with an
increase-scale message rather than silently thinning it. PAT files, family
counts, dash cycles and stroke generation all have work/size limits. The engine
is an expanded drafting implementation; full AutoCAD hatch parity, annotative
paper-scaled hatches and associative mixed-edge networks are not implemented.

Try `examples/hatch_study_16_8.pycad` and its DXF/PDF companions.
