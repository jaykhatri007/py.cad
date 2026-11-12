# PyCAD product roadmap — v14 onward

PyCAD is being built as a staged, open-source CAD product. The application is
already usable for a supported 2D subset, but AutoCAD parity is a multi-year
program involving geometry, interchange, annotation, a solid kernel,
performance, packaging and specialist modules. Each release below is tied to
working code, acceptance tests and explicit limits.

## Delivered in v14

- Shared `pycad.tolerance` policy with a documented `EPSILON` and reusable
  scalar/bounding-box predicates for future exact topology work.
- Uniform-grid spatial index used by canvas snapping and selection to avoid
  scanning every finite entity for every pointer event.
- Lazy rebuild and invalidation after add/remove, undo/redo transforms and
  associative geometry synchronization; the drawing model remains authoritative.
- CAD-correct treatment of unbounded `RAY` and `XLINE` entities during indexed
  queries, so far-away construction geometry remains selectable.
- Four focused v14 tests covering tolerance boundaries, finite-entity queries,
  undoable movement, layer filtering and unbounded construction lines.
- 161 regression tests passing in the documented offscreen environment.

## Next build sequence

### 1. Exact 2D geometry

Add bulge segments to polylines, true B-spline/NURBS storage, ellipse-aware
intersections, robust line/arc predicates, exact offset/trim/extend topology,
regions, boundaries with islands, and tessellation caches. Keep the tolerance
policy shared by every predicate and make spatial-index entries versioned when
geometry changes.

**Gate:** adversarial tiny/large-coordinate fixtures, deterministic tangencies
and intersections, stable undo/redo, exact crossing selection, and published
pick latency for 1k, 10k and 100k entity drawings.

### 2. Documentation and interchange

Implement MTEXT, leaders, tables, dimension/text styles, annotative scales,
editable DXF dimensions and paper-space annotations. Build a reviewed corpus
covering OCS, bulges, attributes, proxies, nested blocks and external
references; preserve unsupported content or produce an explicit report.

**Gate:** each imported entity is preserved, converted with a report, or blocks
unsafe overwrite; golden PDF measurements and independent CAD-reader reloads
pass.

### 3. Persistent 3D workspace

Move from export-only extrusion to a persistent Open CASCADE/OCP model tree
with orbit/pan/zoom, selection highlighting, feature parameters and rollback.
Add extrude/revolve, Boolean, sweep, loft, shell, fillet/chamfer and mesh
workflows with schema migrations.

**Gate:** volume/area/topology checks, STEP round trips, editable reopen and
recoverable failed-kernel operations pass.

### 4. Constraints and reusable content

Add a solver interface, geometric/dimensional constraints, degrees-of-freedom
reporting, conflict diagnostics, attributed blocks, dynamic symbols and
assemblies.

**Gate:** under-, fully- and over-constrained fixtures solve deterministically;
failed solves never silently change geometry.

### 5. Performance and professional UI

Profile real drawings before changing rendering. Add cached tessellation,
dirty-region updates, asynchronous long operations, multiple documents,
configurable palettes, high-DPI/accessibility support, keyboard workflows and
documented command options.

**Gate:** open/save/render/undo/pick benchmarks are published for the target
corpus; supported platforms show no GUI freezes or disappearing annotations.

### 6. Distribution and ecosystem

Build signed Windows/Linux/macOS installers, clean-machine install tests,
update rollback and crash-recovery drills. Treat architecture, MEP, electrical,
civil/GIS, plant, collaboration, standards and AutoLISP/ObjectARX compatibility
as separately scoped modules.

**Gate:** clean install, draw, edit, save, reopen, plot, recover and uninstall
checks pass on every supported platform with a defined limits/support policy.

## Release boundary

v14 is a real engineering milestone, not a claim of full AutoCAD parity. It
improves interactive performance and numerical consistency while retaining the
existing supported entity subset. The next high-value work is bulged curves,
exact curve topology and interchange fidelity; adding more ribbon buttons before
those foundations would not make the product professional.
