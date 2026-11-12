# PyCAD roadmap after 15.8

Delivered in this milestone: two-line associative angular annotations, signed
X/Y ordinate annotations with per-annotation origins and supported source
anchors, cursor previews, native schema 7, undo/source recovery and dimension
text-aware model PDF fitting. Ubuntu and Windows launchers are preserved.

| Priority | Next work | Acceptance gate |
| --- | --- | --- |
| Annotation | Persistent multileader entities, styles and branch add/remove | Enable MLEADERADD/MLEADERREMOVE only after native persistence, branch editing, undo and plot coverage |
| Reusable architecture | Block attribute definitions, per-insert values and schedules | ATTDEF/attribute editing must survive native/DXF exchange and block edits |
| Sheets | Named plot settings, title blocks, controlled viewport scales, combined multi-page PDFs | Measured paper/model scales, predictable clipping and undoable per-layout settings |
| CAD geometry | Bulged polylines, B-spline/NURBS storage, exact trim/intersections/offsets and regions with islands | Small/large coordinates, representative round-trip corpus and degeneracy fixtures |
| Compatibility | Editable DXF dimensions, deeper references and detailed interchange reports | Independent DXF reader comparison and loss reporting |
| Platforms | Ubuntu 26.04 new-feature smoke run, native Wayland/DPI, physical hardware and Windows clean setup | Reproducible open/edit/save/recover/plot and orbit results on actual supported desktops |
| 3D | Persistent features, more solid operations and generated associative views | Valid topology, failed-operation recovery and export/reopen fixtures |

Keep improving command completeness in coherent subsystems. Do not enable
unfinished ribbon buttons before their operations, undo, persistence and output
paths work. Distribution packaging follows clean-machine and platform checks.
See RIBBON_COVERAGE_15_8.md for all 25 planned commands and limited implementations.
