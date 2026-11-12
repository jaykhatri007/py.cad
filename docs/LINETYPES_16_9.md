# Linetypes — PY.cad 16.9

The shared library now offers **51 types**, plus **BYLAYER** and **BYBLOCK**
inheritance choices. No separate load step is needed.

Open **Format → Linetypes…**, use the **…** button next to the quick-access
linetype picker, or enter **LINETYPE**. The Home ribbon's Linetype command opens
the same compact manager. Search names or descriptions and inspect the two
preview strokes. **LTSCALE** also opens this manager.

| Family | Choices |
| --- | --- |
| Solid | CONTINUOUS |
| General dashed | DASHED, LONGDASH, SHORTDASH |
| Hidden geometry | HIDDEN |
| Center lines | CENTER |
| Alternate positions | PHANTOM |
| Dash/dot combinations | DASHDOT, DASHDOTDOT, DASH3DOT |
| Dots | DOTTED |
| Borders/divisions | BORDER, DIVIDE |
| ISO metric dash sequences | ACAD_ISO02W100 through ACAD_ISO15W100 |

Each of the twelve named families has the base pattern, a **2** suffix for
half-size spacing, and an **X2** suffix for double-size spacing. The 14 ISO
sequences and continuous line bring the total to 51. They are simple repeated
dash/gap/dot patterns; text labels and SHX shape symbols are not implemented.
The ISO sequences come from the existing ezdxf library under retained MIT
notices. No Autodesk LIN file, SHX font or SDK is bundled.

## Apply a linetype

- **Set current:** use the chosen type for new geometry.
- **Apply to selection:** change selected editable objects. Locked layers are
  excluded; a selection with no editable objects is rejected.
- **Set current layer:** change the current layer's linetype. Objects using
  BYLAYER follow that layer.
- The quick-access, Properties and Layer Manager dropdowns include preview
  swatches for the same library. Layer states and drawing standards accept
  these types too.

**Drawing scale** multiplies all pattern lengths: 2 doubles every dash/gap;
0.5 halves them. It applies throughout the drawing, including objects not
selected. The pattern starts at each object's path start. It is expressed in
drawing coordinates, so zoom changes displayed spacing. Lineweight changes
stroke thickness without changing dash spacing. Unit conversion adjusts scale
so physical pattern dimensions remain consistent. Apply operations and scale
changes are undoable.

BYBLOCK children inherit an INSERT's pen; BYLAYER children on layer 0 also use
the INSERT pen. Explicit child linetypes are painted independently. Full
AutoCAD block-property inheritance and per-object linetype scale are not added
in this release. Copying into another drawing adopts the target's drawing-wide
scale.

## Save, plot and DXF

Native files retain type names, layer assignments and the drawing scale. Older
records without scale load with 1.0. Schema 12 is retained, but earlier PY.cad
versions may reject the new optional field or unfamiliar layer type names;
use 16.9 or later for these files.

DXF export writes actual definitions for all 51 types, correct object/layer
references, BYLAYER/BYBLOCK flags and $LTSCALE. DOTTED maps to DXF DOT (with DOT2
and DOTX2 variants). Native/DXF/PDF examples are in
`examples/linetype_study_16_9.*`.

The native renderer and vector PDF use the same dash definitions. Very dense
on-screen patterns merge to a continuous preview at less than two pixels per
cycle; PDF keeps vector dash spacing. Dots use round pen caps and can differ
slightly between raster engines or receiving CAD applications.

Foreign DXF files can define different patterns under the same name. This
release uses its built-in definition and reports a warning when a used source
definition differs. Unknown custom/complex types still display as continuous
with a warning; arbitrary LIN import and text/shape patterns are not included.
Imported per-object DXF linetype scales are approximated using the drawing-wide
scale with a warning. Keep the original DXF when exact foreign styling matters.

![Actual linetype manager](PYcad-16.9-Linetype-Manager.png)

![Pattern catalogue using the production renderer](PYcad-16.9-Linetype-Catalog.png)
