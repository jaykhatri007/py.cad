# PY.cad 16.37 — persistent large-drawing display and editable cached xrefs

## Zoom and pan

Large drawings retain their last complete image during camera refinement. Wheel
and pan input reuse that image immediately; the drawing is no longer cleared at
the start of each idle refresh. Refinement yields to Qt in short batches, without
the previous fixed 16 ms pause after every batch.

A reusable, camera-independent Qt display list caches supported model geometry.
After its initial compilation, zooming/panning replays that geometry in small
batches without rebuilding each entity in Python. The completed image is swapped
in together, then reused for ordinary repaints. Revision/layer/theme changes
invalidate the cache. Selection is a separate overlay. Blocks retain nested
clipping and opacity. Curved polylines use compact arc paths in this display cache;
their original vertices/bulges/widths and saved geometry are unchanged.

Text with wrapping/rich formatting, patterned/gradient hatches, custom/dashed
linetypes, underlays and other view-dependent objects retain the existing full
renderer for their own chunks, with the last complete image visible during
refinement. These objects do not disable caching for the remaining supported
geometry in a mixed drawing. Images are
previews; source precision and export paths are unchanged. Display caches can be
rebuilt and do not remove, cap or explode drawing entities. New areas exposed by
zooming out appear as the new view finishes. Initial compilation and exceptionally
complex individual entities can still take time. Object count alone does not
guarantee performance: curve density, hatches, reference nesting, RAM and graphics
hardware matter. See VALIDATION_16_37.txt for measured 200,000-object workloads.

## Make an external reference editable

- Select an xref and run **BIND**, or right-click **Bind Xref to drawing**.
- In **XREFMANAGER**, select a reference and choose **Bind to drawing**.
- Run **BINDMISSING** to bind all definitions with missing/unresolved sources
  whose cached geometry is available. Available nested references stay linked.
- Double-click/BEDIT a missing-source xref: its cached definition is made local,
  then the block editor opens. An available live xref stays linked unless you
  explicitly bind it.

Binding preserves the local definition, all its instances, insertion points,
rotation/scale, clipping, attributes, layers, curves and hatches. It changes all
instances of the chosen definition. Edit its contents through **BEDIT**; after
binding, **EXPLODE** also works for ordinary unclipped references. Clipped blocks
stay blocks so their clipping is preserved. Save the drawing to retain the change.

Binding is one Undo/Redo operation. An unloaded reference can restore its verified
private cache before binding. If geometry/cache is absent or corrupt, binding
fails without changing the drawing; Relink/Reload the source first. Missing files
cannot be reconstructed without cached geometry. Cached content is the last
imported version, potentially older than its source. External source files are
never modified by binding. Explicitly binding a parent does not silently unlink
available nested/shared definitions.

No new dependencies or native file schema fields were added. Existing installers,
licenses, logo, hatch and polyline tools remain included.
