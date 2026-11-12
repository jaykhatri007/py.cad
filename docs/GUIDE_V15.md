# PyCAD 15.2 — User guide

## Viewport command entry and compact ribbon

Click in the drawing or a model pane and start typing. The input appears near
the cursor, inside that viewport. Press Enter, numeric-keypad Enter or Space to
activate the typed command. You do not need to click the bottom command line.
The cursor prompt and bottom editor share one input, including clipboard editing
and history. The prompt stays inside the pane when typing near an edge.

| Action | Keyboard workflow |
| --- | --- |
| Start Line | `L` or `LINE`, then Space or Enter |
| Enter points | `0,0` Space, then `@100,50` Enter |
| Finish a line/polyline | Empty Enter or Space |
| Repeat at the idle prompt | Empty Enter or Space |
| Cancel typing/tool | Esc |
| Complete a command suggestion | Tab |
| Recall entered commands/values | Up/Down in the command editor |
| Change model angle | `FRONT`, `LEFT`, `TOP`, etc., then Space or Enter |
| Return to drafting | `PLAN`, then Space or Enter |

For text, start `TEXT`, specify the insertion point, then type the content with
normal spaces and press Enter. Block names also accept spaces; finish names with
Enter. Space submits command names, coordinates and numeric values. Type
coordinates without embedded spaces, for example `10,20` or `@50<30`.

The active tool still controls each prompt. For example, after `LINE` it expects
a point; press Esc before starting an unrelated command. Unknown commands appear
in the bottom history. Clicking the drawing or another field cancels an unfinished
typed entry. Property editors keep their normal text input.

The ribbon uses a 66-pixel strip with 22-pixel tool icons and 30-pixel buttons.
Hover to read each tool's name and command. The category tabs retain their text
labels. File actions are in the File menu, undo/redo in Edit, and Fit in View or
the viewport navigation rail. Ctrl+S, Ctrl+Z, Ctrl+Y and Ctrl+0 remain available.

![Cursor command prompt and compact ribbon](viewport-command-v15.2.png)

## Quick tour

1. Extract the complete project and launch with `start_windows.bat`.
2. Open `examples/pavilion_study.pycad`.
3. Open **Manage & Views → Dim styles**. Select **Architecture 1-100**. Change
   precision, arrow type, text height or suffix; inspect the live preview; click
   **Save style changes**. The drawing's dimension updates. Undo reverses it.
4. Open **Manage & Views → Layers**. Filter by `Pavilion`. Toggle visibility,
   lock a layer, or change its color/lineweight. Close to inspect the drawing.
5. Click the orbit icon inside the drawing, or **Manage & Views → Four views**.
   The saved model appears in the main drawing area. The four-view layout has
   Top, Front, Right and Isometric panes. Every pane has compact navigation icons,
   a view selector and a clickable orientation cube.
6. Select **Main studio** in the saved-extrusions list, choose **Change height**,
   enter a new height and inspect the views. Undo restores it. Return to
   drafting and save the project; reopening retains the new height.

![Four embedded model panes](embedded-four-views-v15.1.png)

## Dimension styles

![Style manager](dimension-styles-v15.png)

The style table is independent of dimension type. A horizontal, aligned, radius
or diameter dimension can share one named style. New dimensions use the current
style. Existing dimensions retain their named reference until reassigned.

| Tab | Controls |
| --- | --- |
| Lines | Extension offset from measured geometry and extension beyond the dimension line |
| Symbols & arrows | Closed arrow, open arrow or architectural tick; arrow size |
| Text | Height, gap and color (`BYLAYER` or `#RRGGBB`) |
| Units & scale | Decimal places 0–8, prefix, suffix, trailing zeros, overall annotation scale |

**New from selected** creates a new style from the currently displayed values.
**Set current** changes the default for new dimensions. **Save style changes**
commits edits. **Apply to selected dimensions** applies the style to unlocked
selected dimensions. Standard, current and referenced styles cannot be deleted.
The preview fits the sample to its box; the drawing uses real model-unit sizes.

The scale controls annotation size, not the measured value. Change drawing
units deliberately; changing units does not rescale coordinate values. Text is
horizontal and automatic text/arrow fitting is not implemented. If the label
does not fit, adjust scale or place the dimension farther from the geometry.

## Layer properties

![Layer properties](layer-manager-v15.png)

On/off controls visibility. Freeze also hides a layer in model, 3D and plotted
views. Lock prevents normal selection/editing and extrusion modifications.
Plot off hides a layer from PDF while retaining screen visibility. Entity color
and linetype inherit only when set to BYLAYER. Weight is a standard physical
lineweight in millimetres. **Isolate** shows the selected layer; **Show all**
turns on and thaws all layers. Each is a single undo step.

Layer names are case-insensitively unique when created or renamed. Layer 0 and
layers referenced by entities, block definitions or extrusion records are
protected against deletion. Rename updates those references with undo support.
Saved layer states, filters by property, and per-paper-viewport overrides are
still planned.

## Saved extrusions and model panes

To make a new extrusion, return to drafting, select one circle, rectangle or
simple closed polyline, run `EXTRUDE`, and enter a nonzero height. Negative
height extends below Z=0. The extrusion owns a snapshot of that profile.

The model workspace renders saved extrusions without the optional solid kernel.
Select an extrusion through the list to edit its name/height or delete it.
Selection highlighting appears in every visible pane. Hidden/frozen layers
hide solids, and locked layers prevent edits. Undo/Redo affects the document.

Navigation controls appear inside both the initial drafting canvas and the model
panes. The icon rail is 36 pixels wide; short panes use a horizontal rail along
the bottom. Its actions are Orbit, Pan, Zoom in, Zoom out, Fit and Isometric.
Tooltips explain every icon. Choose Orbit or Pan and left-drag inside the pane;
Shift+middle-drag also orbits, middle/right-drag pan, and Shift+left-drag temporarily
pans. The Pan button works in drafting too; Esc ends drafting pan mode.

The upper-left selector offers all six standard views plus Isometric, Free orbit,
Single view, Four views and 2D drafting. Click a face of the upper-right cube to
align the camera, drag it to orbit, or double-click for Isometric. A cube drag in
the drafting canvas switches to its resulting model angle when released.

Wheel zooms. Double-click the model, press Home or use Ctrl+0 to fit the active
pane. Fit all fits every pane. Camera positions survive switching layouts and
returning to drafting, so use Fit after resizing when you want to frame everything.
Esc in a model pane, Return to drafting, the 2D drafting selector entry or `PLAN`
returns to drafting. Drawing/edit commands automatically restore the 2D canvas.
Typing in a model pane starts command-line input, including `FRONT` or `3DORBIT`.
Opening a new document resets the model workspace and its cameras.

Camera controls apply to the active pane. Top is the XY plane, Front looks from
negative Y, Right from positive X, and Left from negative X. Bottom and Back are
opposite views. Free orbit maintains an orthonormal camera basis without a
vertical-angle lock. Single view maximizes the active camera. All cameras use
parallel projection. These model panes are not paper-space sheet viewports.

For STEP/STL, install `requirements-3d.txt` and choose **Export STEP / STL** from
the workspace. The exact stored circle or polygon and height regenerate a solid
using CadQuery/OCP. The display mesh is not the exported B-rep. No third-party
CAD renderer, drawing or artwork is bundled.

## Native compatibility and release boundaries

Schema 3 loads earlier schema-1/2 projects and supplies missing style/layer
settings. Save upgraded projects under a new filename if you need the old
version. v14 cannot load schema 3. Legacy dimensions now use model-unit styling;
use the style scale to restore the intended annotation size.

3D face depth sorting is approximate for overlapping/intersecting models;
wireframe is available to inspect them. The 3D viewer shows supported plan
outlines automatically when there are no visible solids, and optionally over
shaded solids. It does not show 2D text/hatches/dimensions. No surface picking, arbitrary
3D solids import, Booleans or professional hidden-line computation is claimed.
DXF dimension graphics remain exploded. Projects with saved extrusions refuse
DXF/DWG export rather than omit the features.

## Research references

Workflow references consulted 27 September 2026. These informed the control
organization; the implemented subset above is the release contract.

- [Autodesk: dimension primary units](https://help.autodesk.com/view/ACD/2026/ENU/?caas=caas%2Fdocumentation%2FCIV3D%2F2014%2FENU%2FfilesACD%2FGUID-2D1177AB-3130-4522-A631-AA28493529DC-htm.html)
- [Autodesk: symbols and arrows](https://help.autodesk.com/cloudhelp/2022/ENU/AutoCAD-LT/files/GUID-E063AF30-6F14-42D6-B0AB-0CF5C47B5897.htm)
- [Autodesk: layer properties](https://help.autodesk.com/view/ACD/2026/ENU/?caas=caas%2Fdocumentation%2FACDLT%2F2014%2FENU%2Ffiles%2FGUID-B297EBD9-D68C-47E1-87CE-1B3798496599-htm.html)
- [Autodesk: viewing 3D objects](https://help.autodesk.com/cloudhelp/2020/ENU/AutoCAD-Core/files/GUID-08F8CD88-6263-48B5-BA32-1C49F17AD17C.htm)
- [Autodesk: 3DORBIT](https://help.autodesk.com/cloudhelp/2022/ENU/AutoCAD-Core/files/GUID-85CE824C-0AF4-4890-8487-ADBC92BF08F1.htm)
- [Autodesk: navigation bar](https://help.autodesk.com/cloudhelp/2022/ENU/AutoCAD-Core/files/GUID-17225A0F-7A50-41B9-8404-7D415518DEFB.htm)
- [Autodesk: positioning navigation controls](https://help.autodesk.com/cloudhelp/2022/ENU/AutoCAD-Core/files/GUID-5625958B-0559-4E10-9A86-41FE362429E1.htm)
- [Qt: QStackedWidget](https://doc.qt.io/qt-6.8/qstackedwidget.html)
- [Qt: event filters](https://doc.qt.io/qt-6/eventsandfilters.html)
- [Autodesk: dynamic input](https://www.autodesk.com/learn/ondemand/tutorial/dynamic-input-in-autocad)
- [Qt: QLineEdit](https://doc.qt.io/qt-6/qlineedit.html)
