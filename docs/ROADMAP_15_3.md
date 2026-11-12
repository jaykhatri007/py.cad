# Remaining AutoCAD-like capabilities

This roadmap describes engineering work, not enabled tools. The catalog and
coverage report are the current source of truth for implementation status.

| Stage | Work | Acceptance gate |
| --- | --- | --- |
| 1 — Complete annotation model | Native angular/arc-length dimensions, associative centerlines/marks, rich multiline text, multileader branches/styles, table cells/styles/formulas, block attributes | Editing source geometry updates annotations; undo/redo and native save/reopen preserve associations; DXF exports correct entity semantics or explicitly warns. |
| 2 — Persistent constraints | Geometric and dimensional solver, degrees of freedom, conflict/overconstraint handling, constraint visibility/settings | Coincident, collinear, concentric, fixed, parallel and perpendicular relations survive edits. Driving dimensions change geometry. Conflicts leave the drawing unchanged. |
| 3 — References/import and properties | Object transparency, linked raster/PDF/DWG/DGN/point clouds, PDF/DGN import, hyperlinks, spelling, standards/layer translation | Curated real-format fixtures open and round-trip with explicit loss reports. Large-file cancellation, coordinate transforms, clipping and layer properties are verified. |
| 4 — CAD model and derived views | Robust B-rep editing, booleans, materials, base/projected/section/detail drawing views | Topology remains valid after edits; generated views update from solids and export/plot consistently. GPU depth and large-model performance have measured budgets. |
| 5 — Customization and automation | Full ribbon/CUI editor, recordable/replayable actions; separately scoped AutoLISP/VBA compatibility | Reloadable configuration, stable command API, deterministic replay, versioned settings and documented language compatibility. Do not claim AutoLISP/VBA without their runtimes. |
| 6 — Publishing and exchange | Sheet sets, direct printers, plot styles, DWF/FBX, complete dependency transmittals, optional user-authorized email integration | Multi-sheet publishing preserves paper scale and references; exchange fixtures validate in target applications; no silent data loss or automatic sending. |
| 7 — Production qualification | Windows/macOS CI, installer/signing, migration corpus, crash recovery, large-drawing performance, high-DPI/accessibility tests | Passing native-platform gates and reproducible packaging; no unverified claims of full AutoCAD compatibility. |

The next highest-value milestone is stage 1: replacing static annotation blocks
with explicit persistent entity types. It improves everyday drafting and reduces
interchange loss before more ribbon features are enabled.

## Research informing this release

- Autodesk's [About the Ribbon](https://help.autodesk.com/view/ACD/2024/ENU/?guid=GUID-D20EF1D7-4135-48A7-B68E-65BF3BFF3D70) describes tabs, panels and logical command groups. This release follows the supplied workbook's ordering and screenshot's primary/secondary icon hierarchy using original PyCAD artwork.
- Autodesk's [STRETCH](https://help.autodesk.com/cloudhelp/2024/ENU/AutoCAD-LT/files/GUID-F000A502-D39E-4D31-A8E2-4A626473FB72.htm) distinguishes crossing-selected vertices from wholly enclosed objects. PyCAD now implements that distinction for its supported 2D types.
- Autodesk's [associative center marks and centerlines](https://www.autodesk.com/blogs/autocad/have-you-tried-create-associative-center-marks-and-centerlines-in-autocad/) update with geometry. PyCAD's new static construction lines are therefore explicitly marked limited.
- Autodesk's [parametric drawing overview](https://help.autodesk.com/view/ACD/2024/ENU/?guid=GUID-899E008D-B422-4DF2-AC8D-1A4F5701ED4E) describes maintained relationships. One-time geometry adjustments and measurement labels are not treated as a constraint solver.

Sources reviewed for the September 2026 ribbon update. The user workbook is the
tab/panel inventory; the provided screenshot is a visual reference, not a claim
that every AutoCAD release has the same interface or that its full capabilities
are present here.
