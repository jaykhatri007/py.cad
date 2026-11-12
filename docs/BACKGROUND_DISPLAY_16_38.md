# PY.cad 16.38 — background viewport refinement and reusable view caches

The drawing renderer now refines large visible model-space views on a background
worker. The worker receives private geometry/style snapshots and immutable Qt
display lists; it never accesses widgets or the live drawing model. The main
thread keeps the previous drawing visible and continues accepting input.

Completed views are retained in a least-recently-used image cache. Returning to
a cached zoom reuses it. Scenes render an extra border
around the viewport, allowing nearby pans without another geometry render.
Zoom and pan previews remain immediate; genuinely new views refine asynchronously.
The normal cache budget is 48 MiB per canvas; one image larger than that budget
must still be retained to display an unusually large viewport. Cache contents
are disposable and do not cap or remove drawing objects.

Dashed and dotted opaque lines now use ordered Qt line batches with the same
world spacing, linetype scale, caps, color and lineweight as individual strokes.
Patterned hatches, dimensions, rich text and other view-dependent geometry use
private native-object snapshots in the worker, preserving the full renderer.
These objects are not flattened, converted to lines in the drawing, or removed.

Cold viewport display traverses time-sliced drawing batches rather than building
the complete picking index inside the first paint. Picking builds its index when
needed. Unsaved tab/title indicators avoid repeatedly serializing an edited
Undo stack; canonical save/close checks retain the exact content comparison.

Model/layer/theme changes invalidate old cached views. Superseded worker jobs
are cancelled; stale results cannot replace a changed drawing. Selection remains
a separate overlay. Workers stop before Qt shutdown. If background rendering
fails, the existing synchronous renderer remains available as a fallback.
PDF/image underlays and plot/layout rendering keep their existing paths.

The initial display-list/snapshot construction still takes time and occurs in
short main-thread batches. Single unusually complex primitives, cold picking,
file import, save/recovery and associative/constraint updates can still be costly.
CPU background rendering is not a claim of GPU compute acceleration. Benchmark
results for generated drawings are in VALIDATION_16_38.txt. No claim of being
faster than AutoCAD is made without a controlled same-file/hardware comparison.
If a particular file remains slow, provide that DWG/DXF (or a reduced copy) and
the operation that triggers it so it can be profiled directly.

No new application dependencies or file schema changes. BIND/BINDMISSING,
editable cached xrefs, precision geometry, prior tools, logo and legal notices
remain included. See the prior xref guide for binding instructions.

Interleaved styles are coalesced into bounded display batches instead of creating
a Qt picture for every tiny run. Frozen hatch snapshots reuse their dense-fill
paths. With the existing subpixel-preview option enabled, wholly subpixel native
batches (under 1.5 pixels across) use ordered point previews; zooming in restores
full shapes. Disable “Simplify subpixel display features” in PERFORMANCE for exact outline display at
all scales. Source geometry, selection and exports are unaffected. Workers
explicitly yield the Python GIL between batches to keep UI event delivery moving.
