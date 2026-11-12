# PY.cad 16.43 — retained layer batches and manual refresh

## What caused the remaining rebuilds

16.42's incremental journal treated the presence of whole feature tables (including saved production and survey metadata) as a global geometry dependency. This disabled local drafting even for an unrelated line. Mixed batches containing hatches or text could also exclude neighboring primitive objects from local editing. Finally, if another revision arrived while a replacement scene was loading, the reset path replaced the previous complete scene with None; this could make the drawing disappear until preparation finished.

These are code paths reproduced in tests. The user's actual heavy drawing was not supplied, so other file-specific causes cannot be ruled out.

## Changes

- Retained display batches follow CAD layers and drawing order. Expensive geometry is separated from independent primitives. Large homogeneous batches remain bounded at 256 objects. Highly interleaved layers use bounded ordered packets to avoid creating a separate native file for every entity.
- New objects occupy separate display overlay batches, grouped in ordered layer runs of up to 128 objects. They keep the CAD layer selected by the user; no extra drawing layers are created.
- Editing existing supported geometry repairs the old and new ink regions of the cached view in place. The rest of the cached image remains intact. Overlapping geometry in those regions is composited again in its original order, avoiding eraser holes and stale pixels. A camera change still presents vectors at the new transform; it does not regenerate model geometry.
- Feature metadata alone no longer blocks local drafting. Actual referenced entity IDs are protected. Constraints, automatic room discovery, live schedule tables and unsupported dependent edits retain the full synchronization path.
- Two views of the same document share the valid edit journal instead of invalidating one another when the second view first loads.
- Repeated invalidations retain the last complete scene until its replacement is ready. During a necessary full rebuild, that previous view can be momentarily stale rather than blank.

## Manual commands

Type **REFRESH** then Enter to rebuild the complete drawing display. **REGEN**, **REGENALL**, **RE** and **REDRAW** continue to work. Ordinary supported drafting does not require a manual refresh. Global style changes, constraints, unsupported edits, BOQ overlays and dependent geometry may still require automatic preparation for correctness.

This is display caching, not delayed saving: drawing geometry changes immediately, remains editable, and participates in undo/redo.

## Research

Qt distinguishes repainting a viewport from regenerating model geometry. Its [QGraphicsView documentation](https://doc.qt.io/qt-6/qgraphicsview.html) describes update regions and caching, and warns that built-in view caching is limited to the background. PY.cad paints custom foreground geometry, so switching that flag alone would not cache its drawing. [QPainter clipping and composition](https://doc.qt.io/qt-6/qpainter.html) provide the mechanisms used here to clear and repair only damaged image regions. This release uses custom retained command batches and a cached image; it does not replace the editor with a new QGraphicsItem scene.

## Validation

See VALIDATION_16_43.txt and the included machine-readable reports. Regression coverage includes a saved/reopened mixed-layer drawing, real Qt mouse clicks through MainWindow, delayed panel refresh, local edits beside hatches, pixel comparison against a full presentation, multiple views, manual REFRESH and repeated rebuild requests. Benchmarks are synthetic offscreen software measurements, not physical input-to-screen latency. The user's file, a physical GPU and Windows/macOS execution were not available.
