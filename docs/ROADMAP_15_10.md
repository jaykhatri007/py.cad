# PyCAD roadmap after 15.10

Delivered this release: the supplied guide's missing clipboard/Find, text-style
and formatting, Options/OSNAP/MENUBAR, tangent, sharing/cloud/comparison workflows;
compact File/layer interfaces and independent saved appearance colors. See
GUIDE_COVERAGE_15_10.md for the implementation scope of every source row.

| Area | Remaining work | Acceptance gate |
| --- | --- | --- |
| Reusable architecture | Native block attributes, per-insert values, schedules | Attribute definition/editing survives native/DXF, copies and block editing |
| Annotation | Mixed formatting, wrapping, source-linked multileader tips, editable DXF annotations | Layout fidelity, propagation/undo and explicit interchange loss reporting |
| Sheets | Named printer/plot profiles, title blocks, combined PDFs | Measured paper/model scales and representative physical-printer checks |
| Geometry | Bulged polylines, NURBS, regions/islands, arc/spline tangent constraints | Exact geometry corpus, degeneracy checks and round-trip fixtures |
| References | Linked DWG/deeper references and corpus-based interoperability | External converter/provider checks and per-feature loss reporting |
| Collaboration | Multi-user merge/history, provider presets, layout/3D shared views | Conflict/revision tests against real providers; browser and privacy review |
| Platforms | Clean Ubuntu 26.04/Python 3.14, Wayland/DPI, Windows, hardware GPU | Actual install/open/edit/save/recover/plot/orbit checks |
| 3D | More persistent solid features and associative generated views | Valid topology, history/recovery and export/reopen tests |

The earlier spreadsheet still has 23 planned commands, visibly disabled.
Future commands become enabled after their operation, undo, persistence and
interchange paths are implemented. Full AutoCAD parity and prebuilt installers
remain separate milestones.
