# PyCAD product roadmap — v12 onward

PyCAD can become a professional Python CAD product, but AutoCAD parity is a multi-year product program rather than a single code drop. The right target is a measured capability inventory: preserve drawing data first, then make geometry exact, then add persistent 3D, constraints, performance and release engineering.

## Delivered in v12

- Native `.pycad` schema 2 with strict structural validation, finite-number limits, duplicate-key rejection, bounded embedded source archives and atomic saves with a validated `.bak` backup.
- Undoable layer table edits: add, rename, delete, visibility, lock, color and current layer.
- Undoable paper-space layout creation, rename and deletion with tab synchronization.
- Object snaps for endpoint, midpoint, center, intersection, perpendicular, quadrant, tangent and nearest geometry.
- `DIST` and `AREA` measurement commands in the command line, ribbon and menu.
- DXF/DWG imports retain a bounded copy of the original source in a native save, while oversized sources are reported safely.
- Full regression coverage for the new milestone; the existing build remains runnable with the software renderer and optional OpenGL path.

## Build sequence

### 1. Exact 2D engine

Add a single tolerance policy, robust predicates, ellipse/ray/xline/region entities, bulged polylines, true B-spline/NURBS storage, exact offset/trim/extend topology and a spatial index for pick/snapping. Replace raster-only hatch detection with curve-aware boundaries and islands.

**Gate:** adversarial geometry tests at tiny and very large coordinates, deterministic intersections and tangencies, stable undo/redo, and measured pick latency on 1k/10k/100k entity drawings.

### 2. Documentation and interchange

Implement MTEXT, leaders, tables, dimension/text styles, annotative scales, native editable DXF dimensions, paper-space annotations, CTB/STB-style plotting and a hand-reviewed DXF corpus containing OCS, bulges, attributes, proxies, nested blocks and external references.

**Gate:** every imported entity is preserved, converted with an explicit report, or blocks unsafe overwrite; golden PDF measurements and reload tests pass in independent CAD readers.

### 3. Persistent 3D workspace

Move from export-only extrusion to a persistent Open CASCADE/OCP model tree with orbit/pan/zoom, selection highlighting, feature parameters and rollback. Implement extrude/revolve, then Boolean, sweep, loft, shell, fillet/chamfer and mesh workflows. Persist B-rep and feature metadata with schema migrations.

**Gate:** volume, area, topology validity, STEP round trips, editable reopen and failed-kernel-operation recovery all pass.

### 4. Constraints and reusable content

Add a solver interface, geometric/dimensional constraints, degrees-of-freedom reporting, conflict diagnostics, attributed blocks, dynamic symbols and assemblies.

**Gate:** under-, fully- and over-constrained fixtures solve deterministically and a failed solve never silently changes geometry.

### 5. Performance and professional UI

Profile real drawings before changing rendering. Add cached tessellation, dirty-region updates, asynchronous long operations, multiple documents, configurable palettes, high-DPI/accessibility support, keyboard-only workflows and command option documentation.

**Gate:** open/save/render/undo/pick benchmarks are published for the target corpus; no GUI freezes or disappearing annotation on supported platforms.

### 6. Distribution and ecosystem

Build signed Windows/Linux/macOS installers, clean-machine install tests, update rollback and crash-recovery drills. Treat architecture, MEP, electrical, civil/GIS, plant, collaboration, standards and AutoLISP/ObjectARX compatibility as separately scoped modules.

**Gate:** a clean install can draw, edit, save, reopen, plot, recover and uninstall on each supported platform, with a defined format/limits/support policy.

## Product rule

A toolbar that resembles AutoCAD does not make a professional CAD system. Each release should publish its supported entities, file-fidelity limits, performance measurements, platform matrix and migration behavior. That is how PyCAD can grow into a trustworthy alternative without claiming features that have not been verified.
