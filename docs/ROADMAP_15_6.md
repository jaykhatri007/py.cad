# PyCAD roadmap after 15.6

The current build is an editable Python CAD application, not complete AutoCAD
feature parity. Use incremental working releases, with declared limitations and
interchange checks, to grow it toward professional use.

| Stage | Work | Acceptance gate |
| --- | --- | --- |
| Delivered: 15.6 | Cursor length/angle entry; physical unit conversion; angular/arc-length annotations; calibrated PDF/image references | 356 tests passed; native persistence and undo; reviewed Qt screenshots |
| Next: Windows release hardening | Run launcher and packaging CI; test DPI scaling, Unicode paths, hardware orbit, multi-monitor use; sign/package an installer when distribution is ready | Clean Windows setup and offline restart; sample drawings render and save correctly; no missing QtPdf/GPU plugins |
| Annotation and drafting depth | Two-line angular dimensions; richer associations; annotation scales; improved grips; more complete object snaps and tracking; native dimension interchange where feasible | Dimension edits survive source changes, undo, native reopen and documented export round trips |
| Sheets and printing | Per-layout plot settings, title blocks, viewport scale controls, batch plot review and printer integration | Measured plotted scales, predictable lineweights and clipping across multi-sheet output |
| Exchange and references | Editable PDF geometry import; standards for supported DWG conversion; deeper DXF coverage; robust reference reload and dependency packaging | Representative real drawings compared geometrically; unsupported content reported, not silently discarded |
| 3D model editing | Solid primitives, booleans, transforms, fillets/chamfers and generated orthographic sections using a suitable geometry kernel | Valid solids, undo/reopen, reproducible STEP/STL export and real GPU tests |
| Production scale | Spatial-index tuning, incremental redraw, memory limits, recovery stress tests and large-document profiling | Published performance targets and a benchmark corpus; interrupted saves preserve prior files |
| Advanced systems | Dynamic blocks, richer tables/leaders, extensibility and additional industry formats | Each subsystem gets a working data model, UI, tests, interchange policy and a defined release scope |

Do not enable a planned command until its supported workflow actually works.
Keep the ribbon catalog, File-menu availability, release guide and regression
tests synchronized. Changing native schema requires migration coverage and
explicit backward-compatibility notes. Autodesk-specific formats/features may
require separate licensed SDKs and cannot be promised by adding a menu item.
