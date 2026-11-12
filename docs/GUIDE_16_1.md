# PyCAD 16.1 — connected architectural editing

This complete source release builds on 16.0. It adds automatic wall joins, live wall models, linked sections/elevations, typed editing in the existing compact Properties dock, and drawing checks. The nine 16.0 feature areas, themes/colors, compact File panels and launchers remain included.

![Connected plan and linked views](workspace-v16.1.png)

| Feature | Entry point | Behavior |
|---|---|---|
| Wall joins | `WALL` | Connected straight walls receive bounded corner miters. Plan outlines remove interior seams at T, cross and collinear joins. T branches stop at the through-wall face in 3D. Wall centre lines stay authoritative. |
| Live 3D | `ARCH3D` | Generate or update models for selected walls, or all walls. Existing live model IDs are reused. Changes to wall position, rotation, thickness, height or openings update their solids after a committed edit. One Undo also restores derived geometry. |
| Linked views | `SOLIDTOOLS`, `VIEWSECTION`, `VIEWBASE` | Sections and Top/Front/Right projections retain one source solid/extrusion and rebuild after it changes. Their placement stays independent. Plane axis/position or projection can be edited in Properties. |
| Compact editing | `PROPERTIES` | Common appearance controls plus a 180-pixel property grid for coordinates, dimensions, wall material, opening parameters, room names/finishes, block values and view planes. Double-click values, then Apply; Reset reloads current values. One Apply is one Undo step. |
| Checks | `CHECKDRAWING` | Free/disconnected wall ends, opening overlaps/bounds, missing hosts, invalid room boundaries, zero-length lines and stale links. Select an issue, inspect screen marks, or export a JSON report. |
| Refresh | `UPDATELINKS` | Recheck model/view source links and report regeneration failures. Current links reuse cached geometry. |

The new commands are in **Tools → Architecture** and ribbon dropdowns. The existing Layer/Properties dock tabs share the same right-side space. In 3D, **Edit source wall…** selects the linked wall and opens its Properties in drafting.

## Start and first example

Extract `PyCAD-v15-Full.zip` to a writable location. The original `PyCAD-v15` folder name is retained for existing shortcuts. Ubuntu users run `bash setup_ubuntu.sh` followed by `bash start.sh`; Windows users use `start_windows.bat`.

Open `examples/v16_1_connected.pycad`. It contains a two-room plan, joined corners, a T-junction partition, doors/window, five live wall models, two linked views and two physical-scale layouts.

1. Select the bottom wall and open PROPERTIES. Change **Height** from 3000 to 3600, then **Apply**. Its saved solid and linked Front view update.
2. Change wall **Width**, or select a door and edit its opening width/station. Inspect the plan and model; Undo returns both to the previous geometry.
3. Select the section block on the right. Change **Plane position** from 1200 to 2500. The section above the door head differs from the section through the door opening.
4. Open the saved model views and select a wall solid. **Edit source wall…** brings its parameters into the shared Properties dock.
5. Run CHECKDRAWING. The supplied plan has no reported issues. Move one perimeter wall away from its neighbours and rerun to see disconnected-end marks. Those free ends are warnings and can be intentional.
6. Publish the A101 Plan and A201 Front layouts. `examples/v16_1_sheets.pdf` and `v16_1_finishes.csv` are supplied outputs. `generate_connected_16_1.py` recreates the example with the optional kernel installed.

![Compact typed property editor](properties-v16.1.png)
![Live wall model browser](model-v16.1.png)
![Read-only drawing checks](checks-v16.1.png)

## Regeneration, Undo and cached results

Source links and cached B-rep/mesh/view geometry are saved in the native drawing. Native schema 11 reads schemas 1–10. New saves require 16.1 or later; keep originals if an earlier build must read them.

Live regeneration requires the optional CadQuery dependencies in `requirements-3d.txt`. Unchanged saved models/views open and display without the kernel. If the kernel is missing or regeneration fails, the last valid result remains visible and its link is marked **Stale**. Source deletion hides the linked wall model; a linked view keeps its last valid graphics and reports the missing source. CHECKDRAWING and Properties show these conditions.

Stale wall models cannot be used for a solid operation or STEP/STL export. PDF publishing rejects stale linked views that lie inside a printed viewport; an unaffected plan sheet can still print. Restore the source/kernel and run UPDATELINKS, or explicitly **Detach link** to retain an independent snapshot. Deleting a saved model removes its wall link so it is not silently regenerated. Detach/Delete support Undo.

Identifier, material or finish-only edits do not require rebuilding a solid. Derived model/view updates share the original edit's Undo step. Unit conversion scales source parameters, solid geometry, view plane positions and placed views together; Undo restores the original data.

Recognised generated Front/Top/Right or `Section X/Y/Z=offset` views in schema-10 and older files migrate to live links and refresh when the kernel is available. Old architectural solids without a stored source ID remain snapshots: delete obsolete copies, then use ARCH3D to create live models. A view explicitly detached and saved in schema 11 stays detached on reopen.

Clipboard transfer carries the supported architectural parameters from 16.0. A generated view copied by itself is independent block graphics in the destination drawing. Live solid/view relationships are preserved when saving/reopening the complete native drawing.

## Checks and current boundaries

Checks do not repair or delete objects. Free wall ends are warnings; they can represent intentionally separate walls. Edits clear old screen marks, so rerun after changing the drawing. Checks are geometric diagnostics, without structural analysis, building-code verification or automatic room extraction.

Wall joining uses coincident centre lines, with a small thickness-relative tolerance. It does not move or snap nearby but disconnected walls automatically. Wall-axis endpoint/midpoint snaps help you draw connected segments. Miters are bounded; very shallow angles, complex multi-branch nodes and arbitrary curved walls do not have a general junction solver. Cross/T outline cleanup is supported; separate crossing solid components can overlap unless you combine them with Union. Openings should stay clear of complicated junctions.

Each linked section/projection has one solid or extrusion source. Views show projected edges with bounded curve sampling; they do not provide general hidden-line removal or an entire-building BIM drawing engine. Floors, roofs, stairs, IFC/BIM semantics, automatic wall-driven rooms and material textures remain later features. Material/finish values here are descriptive architectural fields.

The [16.0 guide](GUIDE_16_0.md) covers the existing nine areas and their broader scope. [Full ribbon coverage](RIBBON_COVERAGE_16_1.md) records available, limited and planned commands.

## Check your Ubuntu environment

The release was tested on Linux using Qt's offscreen backend and Python 3.12. Native Ubuntu 26.04, Wayland/DPI, a physical GPU/printer and Windows execution were not exercised here. The existing launcher supports CPython 3.11–3.14; Python 3.12 is recommended for the optional CadQuery environment.

After setup, from the folder containing `main.py`, run the checker with the same interpreter used by PyCAD:

```bash
.venv-linux/bin/python scripts/check_environment.py --gui
```

It checks imports and an optional solid-kernel cube, then opens/closes a small PyCAD window using private temporary preferences. It reports the actual Qt platform and interpreter. Without a desktop, use `--offscreen`; that checks window construction rather than your compositor. The script does not install dependencies or alter your drawings.
