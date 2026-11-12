# PY.cad 16.27 professional workflows

Type **PROWORKFLOW** or use the Workflow menu. The ten pages add the following capabilities alongside the existing 16.26 tools.

| Command | Added capability |
| --- | --- |
| `REGIONALCACHE` | Disk-backed, spatially indexed regional drawing inspection |
| `GPUBUFFERS` | Experimental cached OpenGL line/curve/convex-hatch buffers and measured CPU/OpenGL benchmark |
| `ASSOCIATIONS` | Persistent dimension anchors and validated closed hatch-boundary links |
| `BLOCKVARIANTS` | Visibility/stretch states, reusable door/window symbols and existing attribute editing |
| `REVISIONS` | Native-ID revision comparison with colored prior/current views and reports |
| `VIEWPORTPLUS` | Viewport rotation, polygon clipping and annotation size multiplier |
| `ARCHREVIEW` | Small endpoint-gap checks, reviewed wall alignment and hosted-opening checks |
| `BOQCHANGES` | Source deductions, wastage calculations and quantity differences between revisions |
| `ROOMPLANNER` | Reviewed room modules with walls, hosted doors, labels and linked dimensions |
| `PROJECTPACKAGE` | Project dependency bundles, verified extraction and offline portable release staging/rollback |

## 1. Regional drawing cache

Open the original drawing normally once, then create a `.pycaddb` cache. Cache creation runs in an isolated cancellable process after an immutable snapshot is captured. Successful results publish atomically; cancellation leaves an existing cache unchanged.

Open the cache, pan with the middle mouse button, zoom with the wheel, and choose **Load visible region**. Only entities intersecting that region and their required block definitions are hydrated. Definitions are stored once in SQLite; an R-tree indexes bounds, including crossing objects. Infinite rays/lines remain candidates in every region. The initial inspection view zooms into a smaller region for larger caches.

This is a regional inspection mode, not a fully disk-backed editing database. Initial source parsing, snapshot capture and cache creation still require RAM. Opening a region containing most objects, or a very large block definition, can still consume substantial memory. Cached geometry is a snapshot: rebuild after changing the source. Inspection omits project feature links, layouts and embedded underlays; edit/save the original drawing for the complete project. No original geometry is discarded or overwritten.

## 2. GPU geometry cache

Select GPU display in Graphics settings, then enable cached GPU geometry on this page. Enabling chooses Direct drawing for the current session. It is disabled by default and is separate from the existing QPainter/OpenGL display option.

The new path uses OpenGL vertex buffers and shaders for continuous thin linework, tessellated curves, straight/curved polylines and eligible convex solid hatches. Selection, thicker/dashed/transparent geometry, text, blocks, patterned/gradient/complex hatches and other content retain the established renderer. To preserve drawing order, buffering handles an eligible leading run; the remaining content falls back in its original order. Contiguous primitive/color groups retain order. PDF output always uses the vector plotting path.

The buffer cache rebases coordinates near the geometry to limit floating-point precision loss, releases old buffers, invalidates on drawing changes, and retires resources with the OpenGL context. Driver/shader failure disables the path for that canvas and draws through QPainter. A single object can exceed the nominal cache target; available memory still matters.

Use **Benchmark with pixel readback** on the target machine. It compares warmed CPU image rendering with the actual OpenGL device, waits for GPU completion and reports sampled image differences. This is drawing-specific; different antialiasing and graphics drivers may differ. The release was exercised on Mesa llvmpipe (software OpenGL), not a physical graphics card. No universal speedup or GPU compute support is promised; editing, importing, snapping and quantities remain CPU work.

## 3. Associative dimensions and hatches

Select a linear/radial dimension and one or two source objects, then choose anchors such as `p1`, `p2`, `center`, `point`, circular `east`, arc `start`/`end`, or polyline `vertex:0`. The two anchor IDs persist in native projects. Existing angular/ordinate annotation workflows remain available through their existing tools.

For a hatch, select it and its circle/closed-polyline boundaries, outer first. The boundaries must be valid, noncrossing and nontouching; islands must stay inside the outer boundary. Source edits refresh the hatch. Missing or invalid sources retain the last valid geometry and appear in **Inspect broken associations**. Binding and detaching are undoable. Fully copied source/target sets retain remapped links through clipboard transfer; incomplete copies become static snapshots.

## 4. Block variants and symbols

Define a state from an original local block, optional hidden layers, X/Y stretch distances and thresholds. Vertices beyond a threshold move by that distance. Straight lines, straight polylines and text support stretching; curved or other content must be edited in the block editor. Derived definitions use fresh entity IDs and can be selected per instance. Refresh the state explicitly after editing its base.

These are native derived-block states, not Autodesk dynamic-block parameter compatibility. Exported geometry remains ordinary blocks. Door/window symbols include editable TYPE/WIDTH/HEIGHT attributes; height is metadata in these plan symbols. Existing ATTDEF, ATTEDIT and schedules remain connected.

## 5. Revision comparison

Choose a previous native project and compare it with the current drawing. Added/current objects appear green; removed/prior objects appear orange; modified objects appear in both views. Reports distinguish IDs, units, feature settings and block-definition changes. Changes to nested definitions propagate to affected parent instances.

Reliable matching uses native persistent IDs. Independent DWG/DXF imports may assign different IDs, producing additions/removals rather than geometric matching. Reports are read-only; the live drawing is not changed.

## 6. Sheet viewports

Select a paper viewport and set rotation, an annotation size multiplier, and optional clipping points `x,y; x,y; ...` in paper millimetres. Clips must enclose a valid area on the sheet. Existing layer visibility/color overrides are retained. The same rotation, clipping and text/dimension sizes apply to the canvas and PDF output.

The multiplier changes annotation appearance without changing measured geometry. It is not a complete annotative-object scale-list system or CTB/STB compatibility. These extra settings are native/PDF features; equivalent DXF/DWG interchange is not guaranteed.

## 7. Architecture checks

Set an endpoint-gap tolerance in drawing units. Checks find nearby wall endpoints on the same level and overlapping hosted openings. **Preview endpoint alignment** proposes midpoint-aligned wall endpoints, updated wall angles and lengths, validates hosted data, and uses the existing visual proposal review. Ambiguous endpoint clusters, locked/scaled/mirrored walls and collapsed walls are rejected. Acceptance creates one Undo step.

Existing mitered wall joins, doors/windows, enclosed rooms and linked schedules remain available. These checks are drafting aids, not building-code or construction-compliance certification.

## 8. BOQ revisions and adjustments

Select a measured source and enter a deduction in its reported BOQ unit, a waste percentage and a reason. The adjusted report shows gross, deduction, net, waste, final quantity, source ID, method, specification and available rate/cost. A per-source waste percentage replaces the global percentage for that source; it is not compounded twice. Excess deductions are rejected. Deleting the source leaves a dormant record so Undo can restore it.

Compare a prior drawing to show quantities before/after and deltas grouped by description, material, specification and unit, with source IDs for both revisions. Units and currencies must match; no exchange-rate conversion is performed. This report is separate from the original BOQ report. Unpriced and unmeasured content still needs review; drawing measurements and project rates are not certified estimates.

## 9. Multi-step drafting planner

Use millimetre drawing units. Enter room rows such as:

```
Office, 6000, 4000
Store, 3000, 3000
```

Answer the start position, separation, wall thickness/height, door and dimension questions. Preview shows walls, optional 900 × 2100 mm hosted doors, room labels and linked dimensions before applying in one Undo. Invalid or incomplete sizes are rejected. Accepting a stale proposal requires previewing again.

Offline chat also accepts `plan rooms Office 6000x4000; Store 3000x3000` using disclosed defaults. Use ROOMPLANNER for explicit choices. This creates separate room modules in a row; it does not solve site constraints, circulation or a complete building layout. The existing optional AI endpoint remains user-configured; no network AI service is activated automatically.

## 10. Project packages and portable releases

**Package drawing and dependencies** writes `.pycadpack`: a native drawing, available xref sources, explicitly selected font files and a SHA256 manifest. Native images/PDF underlays remain embedded. Missing references abort publication. Active cached block geometry is included; dependencies inside raw nested external source files may need separate packaging. Font-family names are listed, but only explicitly selected font files are copied; verify font redistribution permission.

Extraction verifies every listed file, rejects unsafe/duplicate/symbolic paths and only writes a new directory. Bundled reference paths resolve relative to the extracted native drawing. Selected TTF/OTF fonts can load for that session; SHX files are packaged but do not add an SHX rendering engine.

For portable updates, choose a full release ZIP, supply a SHA256 obtained independently from the publisher, and stage into a separate release folder. Existing versions are retained and the selection can roll back. Close PY.cad and launch `start.sh` or `start_windows.bat` in the selected version. This does not modify the running Program Files installation or migrate/downgrade native project schemas. A matching hash proves byte integrity against the supplied hash, not publisher authentication; installers remain unsigned. Older versions cannot open newer native schemas.

`scripts/release_acceptance.py` exercises real runtime imports, native save/reopen, PDF, desktop startup and all ten pages. `scripts/native_install_acceptance.py` can install to a new isolated Windows/Ubuntu directory, then exercise the installed managed runtime. `.github/workflows/native-acceptance.yml` provides an opt-in CI workflow. These scripts are included; native Windows/macOS acceptance has not been executed for this release in this environment.

## Compatibility

New native saves use schema **14**, requiring PY.cad **16.27 or newer**. Schemas 1–13 remain readable. Keep a separate backup for older builds. Prior startup/dependency repairs, approved logo, open-source licenses and source notices remain included. See the validation report for executed checks and platform limitations.
