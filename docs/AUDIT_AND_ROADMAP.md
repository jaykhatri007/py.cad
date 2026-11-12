# Current release: PyCAD v15

See [v15 guide](GUIDE_V15.md) and [v15 roadmap](ROADMAP_V15.md) for the current
capability contract. The audit below is the preserved historical v10–v14
assessment; its export-only 3D and absent-style statements describe those older releases.

# PyCAD v10–v14 audit and development roadmap

Audit date: 26 September 2026.

## Assessment

The supplied `pycad_v10_full(2).zip` is a credible small Python 2D CAD prototype.
It contains roughly 6,400 lines across the main CAD modules, 115 existing tests,
a Qt interface, ezdxf I/O, basic tools and optional CadQuery extrusion. The
architecture is useful for continued development, but the existing feature
list overstated the strength of several workflows. For example, a layout export
test checked an ezdxf file for a viewport; it did not reload that viewport into
PyCAD. All 115 original tests passed even though practical data-loss and editing
bugs were present.

**v11 was a foundation release with verified fixes and a redesigned workspace.
It is not a professional AutoCAD-equivalent product yet.** Professional status
requires measured performance, file-fidelity corpora, substantially broader
geometry support, operating-system/GPU testing, packaging and release gates.
It cannot be established from toolbar appearance or a passing small test suite.

This audit used the latest identified archive. The other similarly named uploads
were not assumed to contain additional features and were not merged blindly.

## Verified faults and changes

### v12 milestone additions

v12 extends the foundation with a schema-2 native format boundary. Project
loads reject duplicate JSON keys, non-finite coordinates, oversized geometry,
invalid entity fields, block cycles and mismatched embedded-source checksums.
Saves use an atomic sibling file and retain a validated `.bak` copy of the
previous project. Layer and paper-space table edits now use undo commands and
the UI keeps its tabs synchronized after undo/redo. DXF/DWG imports retain a
bounded copy of the original source when it is at most 16 MiB. The viewport
adds intersection, perpendicular, quadrant, tangent and nearest snaps, and
the `DIST` and `AREA` commands report precision measurements. The v12 suite
contains 152 tests, all passing in the documented offscreen environment.

### v13 milestone additions

v13 expands the actual geometry model with native POINT, ELLIPSE, RAY and XLINE
entities. They render in the software and optional OpenGL paths, participate in
selection, transforms, grips, snapping, plotting and block cloning, and are
available through drawing tools and the command line. The schema validator
checks ellipse radii and construction-line directions. DXF import/export now
round-trips these four entity types with layer and linetype metadata. The
regression suite contains 157 passing tests.

### v14 milestone additions

v14 adds the numerical and interactive foundations needed before exact curve
topology work. `pycad.tolerance` defines a shared `EPSILON` policy and reusable
scalar/bounding-box predicates. `Document` owns a lazy uniform-grid spatial
index used by selection and snapping; add/remove, undo/redo transforms and
associative synchronization invalidate it safely. Unbounded rays and
construction lines remain selectable even though their defining-point boxes are
finite. Four focused v14 tests raise the regression suite to 161 passing tests.

| Area | v10 defect or gap | v11/v12 treatment / evidence |
| --- | --- | --- |
| New/Open/Close | Replaced/closed modified documents without save protection | Save/Discard/Cancel flow; cancelled/failed-save tests |
| Native persistence | Only interchange data saved; editability and links lost | Versioned `.pycad` JSON with validated entity construction and associations |
| Recovery | DXF recovery lost native semantics; empty drawings skipped | Native atomic recovery, including deletion of all geometry |
| Write integrity | Writes directly targeted the destination | Sibling temporary file and atomic replacement; injected failure preserves original |
| Dirty state | Move/rotate/undo and layer edits could miss dirty state | Compare document content with the saved snapshot; track native save separately from export |
| Dragging | Live entity movement never became an undo command | One Move command per drag; cancellation restores geometry |
| Grips | Point commands retained stale Point objects after a transform | Resolve the current point on the owning entity when undoing/redoing |
| Delete undo | Restored deleted entities at the end, changing draw order | Restore original list positions |
| Command input | Global letter actions stole characters from the line editor | Command aliases, editor history and completion; real QTest typing test |
| Document switch | Old tool/document references, layout tabs and selections survived | One replacement path resets and reconnects document state |
| Layer properties | Colors/off/locked properties did not round-trip in DXF | Import/export those properties; ByLayer colors render; lock controls/filtering; v12 table edits are undoable |
| Selection | Bounding boxes caused clicks far from geometry to pick it | Distance-based entity picking; locked geometry excluded |
| Layout import | Layouts vanished when reloaded into PyCAD | Import rectangular 2D viewports and their scales |
| Layout graphics | Content escaped viewport boundaries; circles used the wrong scale | Painter clipping and effective viewport scale |
| Arc graphics | 350°→10° could draw the long clockwise span | Consistent CCW wraparound in rendering and tessellation |
| Clones | Copies dropped linetype | Clone linetype metadata retained |
| Mirror blocks | Mirroring vanished after reference rebuild | Store handedness and orientation; rebuild regression |
| DXF blocks | Leading-underscore names, nested references and base points were mishandled | Preserve names, resolve nested definitions, compensate block base points |
| DXF loss | Unsupported/malformed entities silently disappeared | Import report and protection against overwriting a partial import's source |
| Spline I/O | Array truth-testing and closed export flags were fragile | Explicit array length checks and valid closed flags; regression |
| Block operations | Block definition creation/editor commit bypassed main undo | Definition creation and editor changes participate in undo |
| Polyline offset | Each edge chose a different side and closing corner was not joined | Consistent miter offsets for supported paths; collapse/self-crossing checks; concave closed paths rejected explicitly |
| GPU path | Separate renderer omitted text, fills, previews and layouts | Shared QPainter drawing implementation on optional QOpenGLWidget viewport |
| PDF | Screen raster, background/grid included; no physical scale | Vector model/layout PDF, physical units and clipping; 100 mm measurement test |
| UI | One long toolbar, little discoverability | Original tabbed ribbon, quick access, properties, layer controls, command history and status toggles |
| Dependencies | Heavy 3D dependency required for 2D startup installation | Core and optional 3D requirements separated; tested versions recorded |
| Qt lifetime | New signal connections initially exposed deletion-order errors | Bound receiver callbacks and explicit window disconnects; full-suite process exits cleanly |

Full source files are supplied, not patches. The change manifest records their
hashes against the original archive.

## Research findings and engineering direction

1. **Target scope must be a capability inventory.** Autodesk describes AutoCAD
   as covering 2D and 3D CAD, and its specialist toolsets extend beyond the core
   drafting application. Its comparison and toolset pages are the scope
   references, not evidence that PyCAD already implements those features.
   [AutoCAD comparison](https://www.autodesk.com/in/products/autocad/compare),
   [included toolsets](https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/Which-Specialized-Toolsets-included-with-AutoCAD.html).

2. **Retain Qt for the desktop shell.** Qt documents a Graphics View framework
   for interactive scenes and a QOpenGLWidget viewport option. v11 uses that
   supported path to avoid maintaining an incomplete independent renderer.
   It still paints the entity list manually; simply using QGraphicsView does
   not automatically give these entities a scene spatial index.
   [Qt Graphics View](https://doc.qt.io/qt-6/graphicsview.html).

3. **DXF and DWG must be treated separately.** ezdxf is a DXF library. Its ODA
   addon invokes an installed external converter for DWG read/write. A converter
   cannot prevent PyCAD's smaller entity model from dropping unsupported data.
   That is why v11 adds a native format and reports partial imports.
   [ezdxf introduction](https://ezdxf.readthedocs.io/en/stable/introduction.html),
   [ODA addon](https://ezdxf.readthedocs.io/en/stable/addons/odafc.html).

4. **Use an established geometric kernel for solids.** Open CASCADE provides
   modeling, data exchange and visualization components; CadQuery exposes an
   OCP-based Python modeling API. Keep application coordination in Python and
   use the compiled kernel for topology and solid operations. This is an
   engineering recommendation, not an implementation claim for v11.
   [Open CASCADE](https://dev.opencascade.org/doc/overview/html/),
   [CadQuery introduction](https://cadquery.readthedocs.io/en/latest/intro.html).

5. **Version upgrades need qualification.** PyPI lists CadQuery 2.8.0, whereas
   this environment's extrusion tests used 2.7.0. The optional requirements use
   the tested version. Evaluate 2.8 and its OCP dependencies as an explicit
   upgrade rather than labeling an untested dependency combination as verified.
   [CadQuery release package](https://pypi.org/project/cadquery/).

These sources were consulted on the audit date. No Autodesk UI artwork,
icons or proprietary code was copied; v11's icons and workspace styling are
original application code with familiar CAD organization.

## Capability matrix

| Capability family | v11/v12/v13/v14 status | Remaining scope |
| --- | --- | --- |
| Desktop workspace | Implemented foundation | Multiple documents, CUI customization, palettes, accessibility and high-DPI matrix |
| Basic 2D drawing | Implemented subset; v13 adds ellipse, point, ray and xline; v14 adds indexed picking foundations | Region, solid, multiline, complete NURBS/bulged polylines |
| Precision drafting | Partial | v12 adds intersection/perpendicular/tangent/quadrant/nearest snaps and DIST/AREA; v13 adds ellipse/construction geometry; v14 centralizes tolerance policy and indexed queries; polar tracking, dynamic input, UCS and exact curve predicates remain |
| Editing | Partial | Stretch/join/break/lengthen/explode, robust concave offsets, exact crossing selection, full command options |
| Annotation | Partial | Native DXF DIMENSION, style tables, MTEXT, leaders, tables, fields, annotative scaling and angular/ordinate dimensions |
| Hatches | Approximate boundary detection | Exact curves, islands/holes, pattern library, gradients, durable multi-source associations |
| Layers/properties | Partial | Full ByBlock inheritance, per-object lineweight/transparency, layer states/filters, complete undo and viewport overrides |
| Blocks/xrefs | Partial | Attributes, dynamic blocks, dependency transactions, exact clipping, robust relative-path resolution and nested reference lifecycle |
| File interchange | Supported 2D subset | Arbitrary DXF fidelity, attached unsupported entities, 3D OCS/UCS, proxy objects, external DWG certification corpus |
| Layouts/plots | Working vector foundation | Paper-space drawing, multiple sheets, page setup editor, CTB/STB, plot styles, printers and publish queue |
| Solid modeling | Export-only extrusion | Persistent solid entities, live 3D selection/orbit, Boolean, revolve, sweep, loft, shell, fillet/chamfer and history |
| Surfaces/meshes/rendering | Not implemented | NURBS editing, materials, lighting, cameras, shaded/hidden-line views and rendering |
| Constraints | Not implemented | Geometric/dimensional solver, degrees of freedom, conflict reporting |
| Automation/extensions | Local Python console | Versioned plugin API, command registry, transaction-aware scripts and optional compatibility layers |
| Documentation collaboration | Not implemented | Drawing compare, revision tracking, sheet sets, standards checks, reference packaging |
| Specialized verticals | Not implemented | Architecture/MEP/electrical/mechanical/civil/GIS/plant workflows; separate projects/modules |
| Production delivery | Development source | Installed-app testing, code signing, update channel, installer, migration guarantees and support process |

Specific limitations remain visible: splines use a Catmull–Rom fit curve and may
change shape on DXF exchange; imported unsupported types may be omitted;
DXF dimension export is LINE/TEXT graphics; clipping is approximate in native
block references and not preserved in DXF; compound hatch detection is raster
based; text metrics are approximate; reference color inheritance is incomplete.
These are not fixed merely by the new native format or interface.

## Phased roadmap with acceptance gates

### 1. File fidelity and document transactions

Expand the native schema with migration tests, recoverable revision snapshots,
complete undo for layer/layout/xref operations, cyclic-reference rejection and
schema/resource limits. Add a source-entity preservation strategy for partial
DXF imports. Establish a hand-reviewed corpus containing MTEXT, attributes,
DIMENSION, bulges, OCS, layouts, proxies, nested blocks and external references.

**Gate:** every input entity is preserved, converted with an explicit report,
or blocks an unsafe overwrite; repeated save/reload and failed-write tests pass.

### 2. Exact 2D geometry and drafting

Introduce robust predicates and tolerance policy, bulged polylines, proper
B-spline/NURBS data, exact hatch boundaries, polygon offset topology and richer
snaps. Add command state machines with documented options and selection sets.

**Gate:** adversarial tests for tiny/large coordinates, tangencies, coincident
edges, self-intersections and degenerate input; interactive dimensions remain
consistent after every supported edit and undo.

### 3. Documentation and plot system

Implement dimension/text styles, genuine editable DXF dimensions, leaders,
MTEXT, tables, fields, paper-space entities, viewports with explicit center/scale,
plot lineweights/styles and batch PDF sheets.

**Gate:** golden PDF comparisons plus exact scale measurements, font embedding,
clipping and multiple paper sizes; reload into independent CAD readers.

### 4. Persistent 3D CAD workspace

Store kernel solids separately from 2D entities, use an Open CASCADE/OCP scene,
add orbit/pan/zoom, selection highlighting and a feature/solid tree. Implement
extrude/revolve first, then Boolean/sweep/loft/shell/fillet with failure recovery.
Persist B-rep and feature parameters alongside schema/version metadata.

**Gate:** volume, surface area and topology validity tests, STEP round trips,
undoable features and failed-kernel-operation rollback. A saved 3D model reopens
with editable state, rather than existing only as an exported STEP file.

### 5. Constraints and reusable content

Add a solver behind an interface, geometric/dimensional constraints, clear
conflict diagnostics, attributed/dynamic symbols and reusable assemblies.

**Gate:** under/fully/over-constrained examples with deterministic results;
changes never silently distort a drawing after a failed solve.

### 6. Performance, UI and platform engineering

Profile real drawings before redesigning rendering. Add a spatial index for
picking/snapping, dirty-region/cached geometry updates and asynchronous long
operations. Expand the workspace to multiple documents, configurable palettes,
keyboard-only workflows and high-DPI/accessibility support.

**Gate:** measured open/save/render/pick/undo latency for 1k, 10k and 100k-entity
corpora; no GUI freezes or disappearing annotation; tested Windows/Linux/macOS
and representative GPU/remote-desktop configurations. No such performance
benchmark claim is made for this release.

### 7. Distribution and professional qualification

Build installers on the target operating systems, exercise clean-machine
installation, automated UI smoke tests, signed releases, update rollback,
crash-recovery drills and dependency/license manifests.

**Gate:** clean install, draw/edit/save/reopen/plot/recover/uninstall checklists
pass on each supported platform. Define supported formats, limits and support
policy before calling a release production-ready.

### 8. Larger AutoCAD ecosystem scope

Treat specialist architecture, MEP, electrical, GIS/civil and plant capabilities
as separately scoped modules. Add collaboration/standards/sheet management and
plugin compatibility as explicit product requirements. AutoLISP/ObjectARX
compatibility would require separate implementations and testing; the Python
console does not provide them.

The highest-value next engineering milestone after v14 is bulged curves and
exact 2D topology, followed by interchange fidelity. Building more toolbar
buttons before these foundations would leave the most consequential
drawing-integrity problems unresolved. The shorter product roadmap is in
`docs/ROADMAP_V14.md`.

## Validation boundaries

See `TEST_RESULTS.txt`. Offscreen Qt tests cover real command typing and the
software interface. The actual interface and sample vector PDF were rendered
and inspected. STEP extrusion volume tests ran with CadQuery installed.

No real DWG conversion, GPU driver execution, Windows/macOS run, installer build,
large-drawing qualification or full AutoCAD file comparison was performed.
The source archive and GitHub workflow are deliverables; remote CI success and
a packaged executable are not claimed.
