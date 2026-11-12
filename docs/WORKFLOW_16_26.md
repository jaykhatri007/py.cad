# PY.cad 16.26 workflow guide

Type `WORKFLOW` or use the Workflow menu. Nine compact pages connect the new tools with existing CAD tools. Changes to drawing settings and geometry use Undo where noted below; diagnostics and preview reports do not change the drawing.

| Workspace | Command | Added behavior |
| --- | --- | --- |
| Diagnostics | `DIAGNOSTICS` | Import timings, failures, counts, block sizes, process memory when available, display timings and JSON report export |
| Display | `PERFORMANCE` | Progressive viewport painting, optional tiny-object display simplification, existing CPU/GPU selection |
| DWG | `DWGREPORT` | Drawing comparison reports, reader settings, direct spline coverage and stronger export checks |
| Edit | `PRECISIONEDIT` | Exact `JOIN` and `BREAKAT`, nested-block snaps, access to existing editing tools |
| Xrefs | `XREFMANAGER` | Attach, relink, reload, unload, cached restore, changed-source status and clipping |
| Sheets | `SHEETLIBRARY` | Capture/create sheet templates, reusable JSON libraries, independent PDF layer pens |
| Recovery | `RECOVERYHISTORY` | Owned snapshot history, retention, restore as an unsaved document, reviewed audit repairs |
| BOQ | `TAKEOFFRULES` | Layer/type rules, specifications, local rate libraries, cancellable background quantity previews |
| AI | `AIDRAFT` | Reviewed drafting plans, copy arrays, impact summaries, JSON plan import/export and one Undo |

## Display and import performance

Cached remains the default display path. Choose Progressive in Display to paint visible candidates in cooperative chunks, retaining the complete drawing and normal picking. Optional subpixel simplification applies only to unselected viewport geometry; selected geometry and PDF output keep full detail. Diagnostics reports candidate and painted counts and the latest chunk duration. Existing CPU/GPU settings control display; geometry editing, snapping, import and quantities still use the CPU.

This is not an out-of-core drawing database. Parsing and the document still require RAM, and a single complex block or hatch can take longer than the nominal eight-millisecond chunk target. Snapshot capture for background quantities also runs before the worker starts and can take time on a very large drawing. No new drawing file-size, entity-count or nesting quota is imposed by these features. Corrupt/circular data, available memory and external parser constraints remain relevant.

Imports now record worker timing and entity/block counts, plus open failures and warnings. The diagnostics event list is bounded to recent events; refresh explicitly to scan the current drawing. Exported diagnostics may contain source paths and failure details: review before sharing.

## DWG interoperability

The direct reader additionally handles supported fit-point and control-point splines, with compatibility fallback for unsupported drawing structures. R2000 DWG export now compares recovered model extents as well as the existing structural checks before publishing the destination. `DWGREPORT` compares units, extents, entity kinds, blocks and sheets with a loaded copy. These are preservation checks, not certification of visual or semantic equivalence.

Modern DWG editing is still subject to LibreDWG coverage. Auto/Direct/Compatibility settings remain available; R2000 writing still uses the DXF bridge. Proxy objects, unsupported 3D content, application-specific data and exact modern-DWG round trips are not guaranteed. Keep the original drawing.

## Precision edits

`JOIN` joins compatible lines, arcs and open polylines into a polyline, preserving arc bulges. Select a connected nonbranching chain with matching styles, then provide a positive endpoint tolerance. Linked/protected objects are rejected to avoid silently breaking associations. `BREAKAT` splits a selected line or arc at an interior fraction while preserving exact arc geometry. Both are reversible. Existing Trim, Extend, Fillet, Chamfer, Offset and Stretch remain available on the Edit page.

Nested block geometry contributes snapping candidates using cached spatial indexes. Block clipping retains crossing strokes and clips their display and picking to the boundary; root and nested clips also apply to PDF painting. DXF/DWG clip interchange remains subject to existing exporter coverage.

## External references

Attach and reload import in a cancellable worker. Attaching converts compatible physical drawing units; conflicting reference text styles receive separate names instead of overwriting host styles. Source file size and modification time provide changed/missing status; this is metadata detection, not a cryptographic source-fidelity guarantee. Relink chooses another source; Reload reads it again.

References remain flattened cached block definitions rather than a lazily shared external database. Unload stores a private, hash-checked geometry cache and removes active reference geometry in one Undo operation. Undo history may retain that geometry in memory. Restore cache explicitly restores the last cached copy, which may be older than the source. Keep reference files available; the private cache is not a portable project archive.

## Templates and plotting

Capture a sheet's paper size, margins, physical viewport scale and title fields as a named template. Create a sheet from it in one Undo operation. Physical scale requires defined drawing units. Import/export templates and PDF pen settings as JSON for reuse. Existing sheet management handles sheet organization and batch PDF output.

Set per-layer PDF color, width and plot visibility on Sheets. Drafting colors are independent. A monochrome plot preset takes precedence over pen colors. These are local PDF pens, not full AutoCAD CTB/STB compatibility.

## Recovery and repair

Create a manual snapshot or configure autosave interval and history retention. Existing tab recovery remains; the active autosaved drawing is additionally archived by a background history worker. Busy archive jobs skip another history capture rather than growing a queue. Archives contain validated native data and a hash; retention removes only owned matching files. A snapshot is not a substitute for an independent backup.

Restore opens a separate unsaved document after hash validation. Preview audit repairs to inspect eligible zero-length lines and exact duplicate primitives before applying a single undoable repair. Linked/protected and locked objects are excluded; this is a conservative repair tool, not exhaustive drawing reconstruction.

## Rule-based quantities and rates

Add named rules with a layer wildcard, entity type, Length/Area/Volume/Count, factor, description, material and specification. Rule names sort lexically: the first matching rule wins. Existing explicit tags, building-managed objects, locked/hidden targets and unmeasurable candidates are skipped. Use names such as `01 Walls`, `02 Slabs` to express priority.

Preview starts an isolated CPU worker after capturing an immutable snapshot. Cancel stops it without editing the drawing. Review quantities and source IDs, then apply tags in one Undo operation. If the drawing changed during review, preview again. The BOQ report can locate source objects and export CSV with specifications. Arc length and polygon-based net hatch area are supported. Hatch islands use nesting parity; crossing/touching loops are rejected for measurement. Curved imported boundaries use the importer's polygon approximation, so verify quantities against source geometry and project requirements.

Rate libraries contain user-entered rates and currency only. Specification mismatches remain unpriced. Mixed currencies are rejected; no exchange-rate conversion or live price lookup is performed. Import/export rules and rates as JSON, apply the rate library, and review unpriced/unmeasured counts before using the subtotal. Factors and units need project-specific verification; this is not a certified cost estimate.

## Reviewed AI drafting

The local chat supports existing typed drafting operations and selected-object rectangular arrays, for example `array selected 2 by 3 spacing 100,200`. Copy arrays support eligible unlinked primitives and two to 1,000 placements per proposal. Review the resulting added/changed/removed counts and available quantity/cost impacts before applying. Cancel keeps the live drawing unchanged; acceptance is one Undo operation. A changed drawing invalidates a staged plan.

Export a typed plan as JSON for inspection or import it for the same review path. The optional provider endpoint remains an explicit user configuration; these changes do not activate a hosted AI service automatically. Impact costs use only existing project rates and disclose unpriced quantities; they are not complete estimates.

## Compatibility and installation

Native project schema is now 13. This release reads schemas 1–12, but new schema-13 files require 16.26 or newer. Use a separate backup if older PY.cad versions must remain part of the workflow. Existing Ubuntu pinned dependency/QtPdf repair and native Windows dependency retry/output improvements from 16.25 remain included.

The release includes a full source ZIP and matching Linux x64, Windows x64 and universal macOS installer packages. Building installers and validating embedded payloads do not establish native Windows/macOS installation success. Hardware GPU behavior also needs testing on the target graphics system. Existing license, source notices and logo assets remain included.
