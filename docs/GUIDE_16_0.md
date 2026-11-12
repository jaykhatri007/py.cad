# PyCAD 16.0 — nine feature areas

This release adds working versions of all nine requested areas to the 15.10 build. The existing theme/color settings, compact File panels, drafting navigation, annotations, constraints, clipboard, DXF support and launchers remain included.

![Actual workspace](workspace-v16.png)

| Area | How to use it | Supported scope |
|---|---|---|
| 1. Smart blocks and schedules | `ATTDEF`, `ATTEDIT`, `BLOCKSCHEDULE` | Define tags, prompts, defaults, local label positions, heights and visibility; edit each insert's values; group quantities; save schedule definitions; export CSV. Architectural IDs, room names, finishes and areas appear in schedules. Native files and DXF ATTDEF/ATTRIB preserve block values. |
| 2. Precise geometry | `CURVEEDIT`, `TRIM`, `OFFSET`, `HATCHISLAND` | Native circular polyline bulges, exact circular extents/length/area and mirror behavior; true fit B-splines or rational NURBS with degree/knots/weights; exact line/arc polyline trim and joined circular offsets; solid/line hatches with non-overlapping inner loops. DXF preserves polyline arcs, spline construction and polyline hatch islands. |
| 3. Drawing sheets | `SHEETSET` / `PUBLISH`, File → Publish → Drawing sheet set PDF | Paper layouts, editable title fields, physical viewport scales, saved model plot presets and checked/reordered layouts in one vector PDF. Title blocks reserve a strip below the viewport. Paper dimensions are mm, independent of model units. |
| 4. Advanced layers | `LAYER`, `LAYERSTATE`, `VPLAYER` | Compact nine-column manager with name/property filters; save/restore/delete states; selected paper viewport visibility/color overrides. Uncheck **Pin layers** to auto-hide the dock; **Layers** brings it back. |
| 5. Rich annotations | `RICHTEXT`, `LEADERLINK` | Bold/italic/underline/color runs, drawing-unit wrapping, native/PDF formatting; short linear dimensions fit labels/arrows outside; first multileader tip follows a selected line/point/circle/arc anchor. |
| 6. Architectural tools | `WALL`, `DOOR`, `WINDOW`, `ROOM`, `ARCHITECTURE`, `ARCH3D` | Draw straight walls or generate them from selected lines; click a wall for a hosted opening; name/number/finish a selected simple closed room boundary; automatic area labels and finish CSV; edit parameters; generate real wall solids with door/window sill/head cuts. |
| 7. Multiple drawings | Ctrl+N, Ctrl+O, drawing tabs above the viewport | Independent documents, file paths, Undo stacks and zoom/pan/space/selection. Copy/paste between tabs preserves supported links, attributes, hosted architecture and physical size. Close one tab with its × or `CLOSETAB`; closing the app checks every drawing. Recovery includes inactive dirty tabs. |
| 8. Stronger 3D | `SOLIDTOOLS`, `REVOLVE`, `SWEEP`, `ARCH3D`, `VIEWSECTION` | Real CadQuery union/subtract/intersect, revolved profiles, circular-section sweeps, X/Y/Z plane sections and static Top/Front/Right projections. Persisted B-rep solids have STEP/STL export, software views, volume, rename/delete and Undo. |
| 9. Automation / AI | `ACTRECORD`, `ACTMACRO`, `APPLOAD`, `ASSIST`, `AIPROPOSE` | Record committed primitive geometry edits; import/export/review action macros; load trusted local Python plugins; use offline instructions or a user-configured compatible AI service. Each proposal has an original/proposed preview, explicit Apply/Cancel and one Undo step. |

All of these commands are searchable through command entry and the tool palette. New tools are also in ribbon dropdowns and **Tools → Architecture / Advanced / Automation**.

## Start and examples

Unzip the complete build to a writable folder. In `PyCAD-v15`, Ubuntu users run:

```bash
bash setup_ubuntu.sh
bash start.sh
```

Windows users run `start_windows.bat`. This is a complete source distribution. Optional 3D operations require the existing `requirements-3d.txt` dependencies in the same Python environment used to launch PyCAD. The QA environment used Python 3.12.14 and CadQuery 2.7.0. The core Ubuntu launcher retains its 26.04/Python 3.14 setup target; optional CadQuery depends on compatible platform/Python wheels.

Open these included files:

- `examples/v16_architecture.pycad`: walls, openings, room, editable furniture attributes, linked note, layouts and saved states/macros.
- `examples/v16_precision.pycad`: native circular segments, rational quarter-circle spline and a hatch island.
- `examples/v16_solids.pycad`: wall/opening solids, boolean result, revolve and sweep; cached views open without the optional kernel, while editing/export requires it.
- `examples/v16_sheet_set.pdf`: combined Plan and Detail sheets.
- `examples/v16_block_schedule.csv` and `v16_finish_schedule.csv`: exported schedules.
- `examples/v16_sample_plugin.py`: load with APPLOAD and type SAMPLEGRID to review a circle grid.

## Useful workflows

**Block values:** create a block normally, run ATTDEF to add an ID or finish tag, select an instance and run ATTEDIT. Definitions are shared; instance values are independent. Re-run ATTDEF with the same tag to modify its definition. Invisible attributes still appear in schedules. The schedule selector can open a saved definition or filter one block type.

**Circular polyline:** select a polyline, run CURVEEDIT and enter one bulge per vertex. `0` is straight; `1` is a 180° arc; use `tan(angle/4)` for another signed sweep. The last bulge of an open path is zero. Native circular segments stay circular through transformations, trimming and DXF export. Curve drawing and spline/section displays use bounded tessellation.

**Rooms:** draw a closed polyline or rectangle, select it and run ROOM. Edit the source boundary to update the area. Use ARCHITECTURE to change names/finishes, wall dimensions or opening IDs/stations/sill/head dimensions. Hosted openings follow wall transforms. Generated 3D solids are snapshots; after architectural edits, regenerate with ARCH3D and remove the obsolete solids.

**Sheets:** open SHEETSET, create/select a layout, enter title fields and choose a viewport's 1:N scale. Check the layouts, move them up/down and publish. A model drawing in metres uses `1000/N` as its model-to-paper scale. On layouts, each viewport's stored scale controls printing; model plot presets control model pages.

**Text:** select text and run RICHTEXT. Select a character range to format it. Set wrap width in drawing units, or zero for no wrap. TEXTEDIT still edits plain content/style/height/rotation; changing its content clears mixed runs. Find/Replace also clears mixed runs on text it replaces, keeping wrapping. Named fonts are not embedded.

**Recording:** ACTRECORD starts; perform primitive drawing/edit commands; ACTRECORD again stops and saves. ACTMACRO opens recorded actions for preview/replay. New objects receive fresh IDs; edits/deletes of pre-existing objects retain drawing-specific target IDs. Recording does not capture file/menu operations, blocks, architectural parameter edits, styles or camera movement. Do not switch drawings during recording.

**Offline assistance:** ASSIST accepts examples such as `room 6000x4000`, `rectangle 100x50 at 0,0`, `circle 25 at 40,40`, `line from 0,0 to 100,100`, and `move selection by 10,20`. JSON actions support the same reviewed operations. This local parser does not use a language model.

**AI provider:** AIPROPOSE accepts your endpoint ending in `/v1/chat/completions`, provider model name and session key. HTTPS is required except localhost HTTP for a local model. Generate sends the instruction, drawing units and selected non-block 2D records to that endpoint. Replies must be validated drawing actions; no generated Python executes. Preview and Apply remain mandatory. Endpoint/model preferences persist; the key is cleared when the dialog closes. No account/model/service is bundled.

**Python plugins:** APPLOAD explicitly runs a chosen trusted local Python file. It must define `register(api)`; `api.register_command(name, callback)` adds a command and `api.propose(actions, title)` reviews changes. Python plugins execute with your user permissions. They are never auto-loaded from native drawings.

## Compatibility and current limits

Native schema 10 reads schemas 1–9. Newly saved files need 16.0 or later; keep original drawings for older applications. Native storage validates feature tables and solid checksums. Clipboard/unit conversion understands architectural parameters, block definitions/values, leader links and solid data.

The supported architecture is straight-wall, 2D plan geometry with simple hosted openings and simple closed room boundaries; automatic wall intersections, roofs, stairs, IFC/BIM semantics and curved wall systems are not included. Room area is planar and in m² for unitful drawings. Door/window solids use rectangular cuts; detailed parametric door/window assemblies are not generated.

Offsets reject collapsed/self-intersecting paths and topology splits; the earlier straight-path convex-loop limits still apply. Hatch islands must be inside and disjoint. General curved DXF hatch edge paths, nested hatch islands and arbitrary spline trim/offset remain outside this release. Closed fit splines close positionally, without a periodic tangent guarantee.

Viewport overrides control visibility and color of globally visible layers; they do not thaw globally frozen layers. Title blocks are native paper annotations with editable fields, not arbitrary paper-space block editors. Publishing manages layouts in the current drawing; there is no external DST sheet-set database.

Saved solid operations retain their sources. 3D views use software orthographic rendering, without material textures, photorealistic lighting or general hidden-line elimination. Generated section/projection curves are static sampled 2D edges; regenerate after source edits. Revolve uses X/Y axes through an entered origin (the UI starts at 0,0); sweep uses a circular cross section on an open planar path. STEP/STL preserve real solids; DXF/DWG solid export is rejected.

DXF retains true curved polylines, splines, ATTRIB values and supported hatch islands. Rich text exports as plain TEXT/MTEXT graphics; native constraints, live architecture/schedules, leader links, saved layer states and sheet presets require `.pycad`. Receiving CAD fonts may differ. Full AutoCAD parity, unimplemented formats and AutoLISP/VBA remain separate work.

![Compact layers](layer-manager-v16.png)
![Proposal review](proposal-v16.png)
![Saved solid model views](solids-v16.png)

Technical implementation references: [ezdxf polylines](https://ezdxf.readthedocs.io/en/stable/dxfentities/lwpolyline.html), [block attributes](https://ezdxf.readthedocs.io/en/stable/blocks/insert.html), [CadQuery shape API](https://cadquery.readthedocs.io/en/latest/classreference.html).
