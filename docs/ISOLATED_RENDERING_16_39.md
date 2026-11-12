# PY.cad 16.39 — isolated rendering and zoom reuse

Heavy 2D display geometry is built once per model/style revision in a persistent
separate Python/Qt process. Camera changes reuse that model instead of reloading
the drawing. Native curve, hatch and Qt raster calls cannot hold the main
interpreter's GIL. Selection highlights and grips are rendered there too.

The UI captures a private model snapshot in cooperative batches. Complexity
routing counts vertices, spline/text work, hatch loops and bitmap size, rather
than only top-level entity count. Complex drawings containing few entities
therefore use the isolated renderer. This is not an entity-count limit.

Cached raster views can cover nearby pans and zoom ratios of 0.8–1.25 without
queuing another raster job. New detail or uncached areas can need new pixels,
which are produced outside the UI process while its previous image remains
visible. In PERFORMANCE, disable 'Reuse display across nearby zoom levels' for
exact raster outlines at each scale. Reuse can slightly soften outlines or
scale screen lineweights within that range. Original model geometry, coordinates,
snapping and exports remain precise. Subpixel-preview controls are unchanged.

Underlays, normal heavy layout views and BOQ display use the isolated renderer.
Live layout viewport dragging keeps its existing preview. Errors are displayed
and logged, rather than silently falling back to a blocking heavy UI renderer.
Reopen the drawing after correcting a reported renderer error.

Snapshots/images live in a private temporary directory; no network service is
used. Only parent-created snapshots are loaded by the child. Model changes
reject obsolete results. Transfer work and the child are stopped on shutdown.
Initial imports, initial display preparation, cold picking, constraints,
association updates and saving can still take time. Separate processes also
require RAM. The specific problem DWG/DXF has not been supplied, and no claim
of being faster than AutoCAD is made. See VALIDATION_16_39.txt for measured tests.

No new dependencies or native schema changes. Prior tools, editable cached
xrefs, branding, legal notices and native installers remain included.
