# PyCAD — v15.2 roadmap checkpoint

Date: 27 September 2026. This release prioritizes the user's request for
professional drafting controls, standard views and free orbit.

## Delivered

The 15.2 update adds cursor-adjacent command feedback in every viewport,
Enter/Space activation, repeat at the idle prompt, explicit Tab completion and
context-aware spaces for text/block names. The 66-pixel icon ribbon replaces the
large labeled tool groups, and duplicate quick-access actions are removed.
Twenty-two new Qt cases cover keyboard workflows, small-pane prompt bounds,
focus, text handling, ribbon tools and retained File menu actions.

The 15.1 update embeds model views in the main application. Compact navigation
controls are present at startup, in every model pane and after document changes.
Layers/Properties/Model browser share a dock, while session camera state survives
layout changes. Regression checks now exercise the real MainWindow entry points
as well as the individual model widgets. The full professional-readiness gates
below remain the roadmap for future releases.

| Request | v15 implementation | Acceptance evidence |
| --- | --- | --- |
| Dimension Style Manager | Named persistent style table; four configuration tabs; live graphic preview; current/apply/delete; shared screen/PDF/DXF graphics | Existing dimensions update, undo restores, native reopen retains names/values, PDF and DXF text match |
| Layer Properties Manager | Searchable properties grid, visibility/freeze/lock/color/linetype/weight/plot, isolate/show all | Layer edits undo, supported DXF/native properties round-trip, no-plot PDF omits content |
| Front/Left/Top/Bottom views | All six standard views plus Isometric | Known-axis projection checks for each standard view |
| Free orbit and multiple viewports | Four independent orthographic model panes, active-pane selection, single pane, orbit/pan/zoom/fit, shaded/wireframe display | Mouse-driven orbit test, orthonormality through poles, switching views and maximizing panes |
| Meaningful 3D content | Native saved extrusion snapshots; height/name edits, delete/undo; optional STEP/STL regeneration | Native reopen, undo/redo, valid solid and exact expected volume, invalid-profile checks |
| File integrity | Schema-3 migration; guarded dimension/layer references; explicit refusal of unsupported 3D DXF/DWG export | Invalid data rejected; rejected export preserves destination |

## Next: exact geometry and production-grade viewing

1. Bulged polylines and true B-spline/NURBS storage, robust curve intersections,
   exact trim/extend/offset and boundaries with islands. Gate: tiny and large
   coordinate fixtures and fidelity round-trips.
2. GPU depth buffer, robust triangulation and face/edge picking, saved named
   cameras, perspective and UCS. Gate: occlusion fixtures, camera reopen,
   real hardware screenshots and frame-time measurements.
3. Kernel-backed persistent features: placements/elevations, profile editing,
   revolve, Boolean, sweep/loft, shell and edge fillets. Gate: valid topology,
   volume/area checks, failed-operation recovery and STEP reopen.
4. Annotation completion: text fonts, automatic fit, alternate units,
   tolerances, annotative scales, MTEXT, leaders, tables, angular/ordinate
   dimensions and editable DXF DIMENSIONs. Gate: independent reader comparison
   and plot measurements.
5. Layer states, property filters, transparency, full ByBlock inheritance and
   per-viewport overrides; richer sheet viewports and plot styles. Gate:
   nested-block and multi-sheet drawing corpus.
6. Performance qualification, background imports, multi-document workflow,
   installers, clean-machine checks and platform/GPU tests. Gate: measured
   budgets on 1k/10k/100k drawings; successful install/edit/save/recover/plot on
   supported Windows/Linux/macOS versions.

AutoCAD's complete toolsets, compatibility layers and specialist verticals are
separate long-term modules. This build is a tested development milestone;
professional readiness requires the remaining acceptance gates, not only the UI.
