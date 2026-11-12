# PyCAD roadmap after 15.9

Delivered: native multileader entities, plain multiline text, named styles and
preview, branch add/remove, grips, undo/redo, schema-8 persistence, unit conversion,
block/selection preservation, fitted PDF output and reported DXF graphic export.
MLEADERADD and MLEADERREMOVE are enabled. Launchers and requirements are preserved.

| Priority | Next work | Acceptance gate |
| --- | --- | --- |
| Reusable architecture | Block attribute definitions, per-insert values and schedules | ATTDEF and attribute edits survive native/DXF exchange, copies and block edits |
| Sheets | Named plot settings, title blocks, controlled viewport scales, combined PDFs | Measured paper/model scales, predictable clipping and undoable settings |
| Annotation | Source-linked multileader tips, richer content and editable DXF annotations | Source changes/undo, loss reporting and independent DXF-reader checks |
| CAD geometry | Bulged polylines, B-spline/NURBS storage, exact intersections and regions with islands | Small/large coordinates, round-trip corpus and degeneracy fixtures |
| Compatibility | Deeper references and detailed interchange reports | Representative drawing corpus and explicit losses |
| Platforms | Ubuntu 26.04 smoke run, native Wayland/DPI, hardware and Windows setup | Actual desktop open/edit/save/recover/plot and orbit checks |
| 3D | Persistent features, more solid operations and generated associative views | Valid topology, recovery and export/reopen fixtures |

The next coherent implementation milestone is block attributes. Enable planned
commands only after their operation, history, persistence and output paths work.
Distribution installers follow clean-machine and platform checks.
See RIBBON_COVERAGE_15_9.md for the 23 planned commands and limited implementations.
