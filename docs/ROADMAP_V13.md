# PyCAD product roadmap — v13 onward

PyCAD is now a working geometry foundation with a staged path toward an AutoCAD-class application. Complete parity remains a large product program; each milestone expands the real data model, file fidelity, editing behavior, and release qualification.

## Delivered in v13

- Native `POINT`, `ELLIPSE`, `RAY`, and `XLINE` entities with transforms, grips, selection and rendering.
- `POINT`, `ELLIPSE`, `RAY`, and `XLINE` drawing tools in the ribbon, menus and command line aliases.
- Native `.pycad` schema validation for the new entity types, including positive ellipse radii and non-zero construction-line directions.
- DXF export and import for POINT, ELLIPSE, RAY and XLINE, preserving layer and linetype metadata.
- Ellipse sampling and construction-line geometry used by snapping, picking, plotting and block cloning.
- 157 regression tests passing in the documented offscreen environment.

## Next build sequence

### 1. Exact 2D geometry

Add a shared tolerance policy, robust predicates, bulged polylines, true B-spline/NURBS storage, ellipse-aware intersections, exact offset/trim/extend topology, regions, boundaries with islands, and a spatial index for picking and snapping.

**Gate:** adversarial tests at tiny and very large coordinates, deterministic tangencies and intersections, stable undo/redo, and published pick latency for 1k, 10k and 100k entity drawings.

### 2. Documentation and interchange

Implement MTEXT, leaders, tables, dimension/text styles, annotative scales, editable DXF dimensions, paper-space annotations, CTB/STB-style plotting and a reviewed corpus containing OCS, bulges, attributes, proxies, nested blocks and external references.

**Gate:** every imported entity is preserved, converted with an explicit report, or blocks unsafe overwrite; golden PDF measurements and independent CAD-reader reload tests pass.

### 3. Persistent 3D workspace

Move from export-only extrusion to a persistent Open CASCADE/OCP model tree with orbit/pan/zoom, selection highlighting, feature parameters and rollback. Implement extrude/revolve, then Boolean, sweep, loft, shell, fillet/chamfer and mesh workflows. Persist B-rep and feature metadata with migrations.

**Gate:** volume, area, topology validity, STEP round trips, editable reopen and failed-kernel-operation recovery all pass.

### 4. Constraints and reusable content

Add a solver interface, geometric/dimensional constraints, degrees-of-freedom reporting, conflict diagnostics, attributed blocks, dynamic symbols and assemblies.

**Gate:** under-, fully- and over-constrained fixtures solve deterministically and failed solves never silently change geometry.

### 5. Performance and professional UI

Profile real drawings before changing rendering. Add cached tessellation, dirty-region updates, asynchronous long operations, multiple documents, configurable palettes, high-DPI/accessibility support, keyboard workflows and documented command options.

**Gate:** open/save/render/undo/pick benchmarks are published for the target corpus; no GUI freezes or disappearing annotation on supported platforms.

### 6. Distribution and ecosystem

Build signed Windows/Linux/macOS installers, clean-machine install tests, update rollback and crash-recovery drills. Treat architecture, MEP, electrical, civil/GIS, plant, collaboration, standards and AutoLISP/ObjectARX compatibility as separately scoped modules.

**Gate:** clean install, draw, edit, save, reopen, plot, recover and uninstall checks pass on every supported platform with a defined limits/support policy.
