# PyCAD 15.9 — persistent multileaders

This release adds native multiline annotations with named styles, editable tips
and elbows, and shared text. `MLEADERADD` and `MLEADERREMOVE` are now enabled.
`MLEADERSTYLE` and `MLEADEREDIT` are new. The compact ribbon, command input,
earlier dimensions, units manager and embedded model workspace remain available.

## Install or update

For a new folder, extract **PyCAD-v15-Full.zip** into a writable location. Inside
its `PyCAD-v15` folder run:

```bash
bash setup_ubuntu.sh
bash start.sh
```

For an existing **15.8.0** installation, close PyCAD and merge the complete files
from **PyCAD-v15.9-Updated-Files.zip** into the folder containing `main.py`.
Replace matching files; avoid nesting `PyCAD-v15/PyCAD-v15`. Run `bash start.sh`.
The patch applies only to 15.8.0. Use the full ZIP for an earlier version.
No launchers or runtime dependency requirements changed. An existing configured
`.venv-linux` can be reused. Windows retains `start_windows.bat`.

Keep copies of drawings for older builds. This release reads schemas 1–7 and
writes **schema 8**, which requires **15.9 or later**. Old drawings open directly.

## Try the example

Open `examples/multileader_study.pycad`. It has two native multileaders, each
with two branches, using the named **Room notes** style. Select an annotation
and open Properties to inspect its text, branch count and style. The matching
`examples/multileader_study.pdf` demonstrates the fitted vector plot.

![Actual workspace](workspace-v15.9.png)

## Create an annotation

1. Type `MLEADER` (or `ML`) in the viewport and press Enter or Space.
2. Pick the arrow tip.
3. Pick a distinct elbow point.
4. Pick the text position, then enter one or more lines in the text dialog.

The annotation uses the current multileader style and current layer. Coordinates
accept `x,y`, `@dx,dy` and `@distance<angle`. The live cursor panel shows the
current leg length and angle; F12 toggles cursor measurements. Canceling the
dialog or pressing Escape before committing leaves no partial annotation.

Text is plain Unicode text with line breaks: no rich formatting, fields, block
content or automatic wrapping. Limits are 16,384 characters, 128 lines and 256
characters per line. Tip and elbow must differ. Each native annotation has
between one and 64 branches.

## Edit text and geometry

Select one native multileader, then use **Properties → Multileader → Edit text…**
or type `MLEADEREDIT`. Accepting the dialog creates one undoable text edit.
Cancel leaves the original text intact.

Each branch has an arrow-tip grip and elbow grip. The text-position grip moves
the shared label and its landings while retaining the tips and elbows. Moving,
copying, rotating, mirroring or scaling the whole annotation affects all its
parts. A grip edit that would collapse a tip onto its elbow is ignored.

Leader tips are independent points. Moving the geometry they point to does not
move the tips automatically. A native annotation remains one entity during
branch and text edits. Visible, unlocked layers are required for entity edits.

## Add or remove a branch

| Command | Workflow |
| --- | --- |
| `MLEADERADD` | Select a native annotation, run the command, pick a new arrow tip and elbow. |
| `MLEADERREMOVE` | Select a native annotation, run the command, click a branch near its arrow or elbow. |

If nothing is preselected, the first click selects a native multileader. Adding
a branch shares the existing text position, text and style. Each command ends
after one branch edit. Undo and Redo restore the branch list as a single step.

Click near the branch's distinct tip or elbow when removing it. Where branches
overlap, the nearest path wins, with the first stored branch breaking a tie.
At least one branch remains; use `ERASE` to delete the whole annotation.
Legacy static blocks cannot be selected by these native branch commands.

## Named styles

Type `MLEADERSTYLE`, choose **Annotate → Leaders → Leader Style**, or use the
Dimension menu. The manager provides a live preview and these settings:

| Setting | Meaning |
| --- | --- |
| Text height | Baseline text size in drawing units. |
| Arrow size | Arrow length; zero hides it. Short legs cap arrows at one third of the leg. |
| Landing length | Horizontal landing length beside the label. |
| Text gap | Space between landing edge and label envelope. |
| Annotation scale | Dimensionless multiplier for text, arrows and landings. |
| Arrow type | Closed filled triangle, Open strokes, or None. |
| Color | BYLAYER uses the entity's effective color; otherwise enter #RRGGBB. |

**New…** copies the displayed settings into a uniquely named style.
**Save changes** updates the stored style and every annotation using it,
including annotations in block definitions. **Set current** selects the style
for future annotations. **Apply to selected** assigns the stored style to the
selected editable native multileaders as one undo step. Save edited settings
before applying them. Styles do not change annotation text or branch positions.

Standard, current and referenced styles cannot be deleted. Style-table changes,
current-style changes and application to selection all support Undo/Redo.

![Actual style manager](multileader-styles-v15.9.png)

## Units, native files and output

Native `.pycad` files retain branch points, text, style names and style tables.
Selection exports retain the style table. Multileaders can be stored inside
blocks; the block editor carries the parent drawing's styles and supports their
geometry grips and ordinary modification tools.

Physical unit conversion scales branch/text positions and style lengths once.
Annotation scale and per-entity transform scale remain dimensionless. Leaving
the UNITS conversion option off keeps coordinate numbers unchanged.

Screen, PDF and DXF output share leader geometry. Fitted model PDF bounds include
labels and arrows; paper viewports retain their intentional clipping. Hidden
layers and layers with Plot disabled do not appear in PDF plots. Labels use a
conservative character envelope for fitting and right-side landing placement.

DXF/DWG multileaders export as **LINE/SOLID/TEXT graphics**, with a loss warning.
They do not export as editable native CAD MLEADER records. Style and branch
editing require `.pycad`; importing the exported DXF produces ordinary geometry.
Existing DXF/DWG restrictions, including saved 3D extrusion restrictions, remain.

## Legacy leaders and remaining work

Old `MLEADER` blocks and the `LEADER` command remain static blocks. Edit those
with `BEDIT`, or create a new native multileader with `MLEADER`; there is no
automatic conversion of arbitrary old line/text blocks.

This milestone does not add source associations, spline leaders, block-content
multileaders, automatic text wrapping or a full CAD annotation-scale system.
The ribbon has 155 commands: 69 available, 63 limited and **23 planned**.
See `RIBBON_COVERAGE_15_9.md` for exact scope and `ROADMAP_15_9.md` for the next
milestones. Platform and validation details are in `VALIDATION_15_9.txt`.
