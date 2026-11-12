# PY.cad 16.36 — large-drawing navigation and polyline grips

## Zoom and pan

Wheel zoom now reuses the last scene image during a gesture and refines detail after the gesture stops. The world point beneath the pointer remains anchored, including fractional wheel/trackpad deltas. Drag zoom uses the same navigation preview. Panning reuses the scene cache. Grips and active-tool ghost previews pause during navigation and reappear when it stops.

Cached and Direct drawing paths automatically use progressive refinement for large scenes, including many objects inside a single nested block. This is a rendering policy, not an object-count limit: it does not remove, explode or alter drawing entities. Explicit Progressive mode remains available. Opaque continuous lines use ordered CPU batches; dashed/transparent and unsupported geometry keep the normal painter path. Plot/PDF rendering retains its existing full-geometry path.

Refinement divides ordinary objects into small batches and nested blocks into bounded child batches while preserving nesting, clipping, visibility, style inheritance and source geometry. Base geometry and selection highlights refine separately. A new view, drawing edit or document switch invalidates stale work. The viewport indicates navigation or refinement. Temporary image scaling can blur strokes or reveal empty margins during a gesture; fresh geometry replaces the preview after it stops.

The target is short, cooperative painting work, not a hard real-time deadline. Candidate indexing and an individual very complex hatch, spline, underlay or other primitive can exceed the approximate 8 ms chunk target. The CPU software/offscreen measurements are specific to the generated test scenes and this host; they do not certify every DWG, native host or physical GPU. The existing graphics options still select the display renderer; the new adaptive path does not claim all CAD computation runs on a GPU.

## Polyline vertex and midpoint grips

Select one polyline or rectangle:

- Square grips are vertices. Drag one to stretch that vertex.
- Round grips are segment midpoints, including true arc midpoints. Drag one to stretch that segment's endpoints together.
- Right-click a grip to open its editing menu.

The menu includes Insert Vertex at Midpoint / Before / After, Delete Vertex, Stretch Vertex / Segment, Set Vertex Coordinates, Convert / Reshape Segment to Arc, Set Signed Arc Angle, Straighten Segment, Reverse Polyline, Open / Close, and the existing Advanced Multi-Vertex Editor.

For arc conversion, choose **Convert / reshape segment to arc**, then move the midpoint to set the bulge and click, or enter a point. The midpoint moves normal to the chord while endpoints remain fixed. An existing arc remains a true bulged polyline segment; it is not replaced by short lines. Numeric signed angles are available in the same menu. Straighten reverses the conversion.

Set Vertex Coordinates accepts absolute `x,y` and relative `@dx,dy`. Active grip tools also accept those formats. The cursor readout shows adjacent edge lengths, movement, or the arc radius/sweep while previewing.

Edits preview on an independent candidate. Click/release commits one Undo step; Escape cancels without changing the source. IDs, common styles and uniform widths are retained. Topology-edited rectangles become general polylines. Undo/Redo restores both geometry and the selected object reference.

Arc midpoint insertion splits the arc exactly. Deleting a vertex between compatible circular arcs merges them exactly. For incompatible adjoining arcs, straighten them first; the tool rejects an ambiguous curved merge instead of silently flattening it. General closed two-vertex arc polylines remain supported. Managed/grouped/constrained or associated source topology is guarded; established linked-vertex dragging remains available where supported. For the new advanced operations, use its specialized editor or explicitly detach/ungroup it before these edits.

Type **PEDIT** or **POLYEDITOR** for the existing unified polyline editor, including Join, Simplify, uniform Width and segment operations. The normal object context menu also offers PEDIT. Ctrl-add and Alt-remove selection behavior remains unchanged.

## Release and validation

Native project schema remains 17. Existing tools, source, logos and license documents are included. No application dependency changes.

The complete ZIP includes the rebuilt Linux `.run`, Windows `.exe`, and macOS universal installer packages under `installer/packages`. Linux software/offscreen tests and payload checks are recorded in the release validation files. Native Windows/macOS execution and physical GPU verification are not claimed.
