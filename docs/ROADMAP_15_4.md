# PyCAD roadmap after 15.4

## Delivered in this release

Twenty commands moved from disabled to working with documented limits: six
geometric constraints, five driving constraints, three constraint controls,
transparency, web hyperlinks, layer translation and three native standards tools.
These include persistent data, validation, command routing, undo/redo and tests.
The 149-command catalog now contains **69 available, 51 limited and 29 planned**.
The full per-command scope is in `RIBBON_COVERAGE_15_4.md`.

This is a staged CAD application project. Completing the 29 disabled commands
alone would not establish full AutoCAD compatibility: many enabled commands
remain deliberately narrower, and solid modeling, file fidelity, annotation and
large-drawing performance need substantial further work.

## Remaining disabled commands and acceptance gates

The order below prioritizes useful editing workflows before specialized formats
and automation. It is an implementation sequence, not a promised delivery date.

| Stage | Disabled commands | Work required before enabling |
| --- | --- | --- |
| 1. Annotation and blocks | `DIMANGULAR`, `DIMARC`, `MLEADERADD`, `MLEADERREMOVE`, `ATTDEF`, `SPELL` | Persistent annotation/attribute records, editable grips and styles, source references where supported, undo, save/reopen, documented DXF/PDF behavior; spelling with an explicit dictionary |
| 2. References and imports | `IMAGEATTACH`, `PDFATTACH`, `PDFIMPORT`, `ATTACHDWG`, `DGNATTACH`, `DGNIMPORT`, `POINTCLOUDATTACH`, `MARKUPIMPORT` | Placement units/transforms, clipping, paths and reloads; conversion reports; cache/recovery; format licensing and fidelity checks; malformed and missing-source handling |
| 3. Drawing views and rendering | `VIEWBASE`, `VIEWPROJ`, `VIEWSECTION`, `VIEWDETAIL`, `CONCEPTUAL`, `REALISTIC` | Solid topology and stable references, hidden-line/section generation, view updates, material/depth rendering, selection and plotting; not just alternative camera presets |
| 4. Project organization and customization | `SHEETSET`, `CUI`, `ACTRECORD`, `ACTMACRO` | Persistent sheet metadata/references; editable command placements and shortcuts; deterministic recorded-command data, replay cancellation and transaction rollback |
| 5. Application integrations | `APPLOAD`, `VBAIDE` | Define the supported runtime/API, dependency packaging and error isolation. A Python plugin API would not by itself implement AutoLISP or VBA compatibility |
| 6. Publishing and communication | `EXPORTDWF`, `EXPORTFBX`, `EMAIL` | Real documented format exporters with round-trip/viewer checks; explicit email account setup, attachment preview and user-controlled send |

These rows cover all **29 unique planned commands**. Some placements reuse the
same command. No placeholder is counted as an implementation.

## Strengthen currently enabled tools

1. Extend the constraint model to polyline segments, tangent/equal/symmetric
   relations and named expressions. Add better conflict explanations and connected
   component solving before increasing sketch-size limits. Preserve exact editing
   targets and document transactions throughout.
2. Replace static table/leader blocks with editable native records and named
   styles. Add annotation scales, tolerances, alternate units and source updates.
3. Extend standards beyond layers/units; add saved layer translation mappings.
   Investigate DWS only as a separate interoperability feature, with test files.
4. Add solid Booleans, face/edge selection and persistent topology using the
   optional geometry kernel. Saved extrusions currently remain independent snapshots.
5. Improve native/DXF/DWG fidelity with reference files and explicit conversion
   reports. Constraints remain native-only until an exchange representation is
   deliberately implemented and verified.
6. Profile large drawings, hit testing, regeneration and solver latency; define
   measurable interactive performance targets from actual project files.

## Release gates

- Every enabled command must produce a real result, handle cancel/invalid input,
  preserve undo/redo and document its geometry/format scope.
- New persistent features must survive save/reopen and reject invalid input
  without overwriting a valid drawing. Export loss must be explained.
- Verify actual Qt interfaces at compact and grouped ribbon sizes, keyboard-only
  use, ordinary Windows display scaling and high-DPI screens.
- Run the full regression suite and the Windows launcher/setup/restart tests on
  Windows. Then test a packaged executable before calling it an installer release.

15.4 currently passes 286 tests on Linux/Qt offscreen. One Windows-specific test
is skipped; real Windows/macOS, GPU, physical printer and ODA converter behavior
remain outside this session's validation.
