# PY.cad 16.40 — persistent vector display

The normal visible workspace now prepares a camera-independent vector scene.
It no longer asks for a new viewport-sized raster image when the camera moves.
This replaces the 16.39 raster/overscan strategy, including its zoom-range and
coverage fallbacks. It applies to both small and heavy visible drawings.

A private worker prepares Qt QPicture command lists and bounds once. The main
window retains them and a spatial hierarchy, culls offscreen batches and presents
stored commands with translation and scale. Far pans show previously unseen
geometry already in the scene. Zoom, pan and resize do not capture the model,
resample CAD geometry, rebuild the scene, or request worker pixels. Screen
repainting remains necessary to show a changed camera; it is not regeneration.
QPainter uses the selected software/OpenGL display surface. This release does
not introduce a dedicated persistent GPU mesh renderer or claim GPU verification.

Selection highlights have their own retained command lists, prepared on selection
changes. Grip coordinates are transformed in Qt without recomputing the editable
points during navigation. Polylines retain analytic bulge arcs. Dash intervals
are expanded into world-space paths once, so their world spacing survives zoom.
Rich text, dimensions, hatches, resolved block/xref contents, embedded raster
underlays and ordinary paper layouts use the same retained scene. Source files
and exports retain their existing exact model paths. Truly infinite construction
lines use inexpensive camera-clipped endpoints instead of finite cached segments.
Live layout viewport editing and tool/comparison overlays retain their previews.

Edits and display-style changes regenerate the scene automatically so the view
stays current. Type REGEN (or RE), REGENALL or REDRAW to explicitly rebuild the
active drawing display. PERFORMANCE also has a Regenerate drawing display button.
The previous same-drawing scene stays visible while a replacement is prepared.
A failed preparation reports its error; REGEN retries without restarting PY.cad.

The default PERFORMANCE controls describe this engine. Simplify subpixel display
features chooses an already prepared point overview for very small circles; turn
it off for full outlines. Toggling it does not regenerate the scene. The old
nearby-raster-zoom checkbox is no longer presented for this renderer. Existing
legacy renderer settings remain available only when PYCAD_LEGACY_DISPLAY=1 is
explicitly set for diagnostics. Plot/printing paths remain separate.

## Limits and verification

Initial import and scene preparation still take time and RAM. Dense hatches
retain the existing density safeguards. Existing tiny/large text pixel clamps
are evaluated at the preparation reference scale. Replaying very dense vector
content can still take measurable time on a software renderer, even with no
scene rebuild. GPU speed and the user's specific problem DWG/DXF have not been
verified. No comparison with AutoCAD has been performed. See VALIDATION_16_40.txt
and the benchmark JSON for measured timings and exact coverage.

The source contains old renderer regression tests exercised with the explicit
legacy environment setting, and new default-renderer tests that independently
assert arbitrary camera changes and real wheel/pan events cause no build jobs.

## Research

Qt documents QPicture as reusable, resolution-independent painter commands:
https://doc.qt.io/qt-6/qpicture.html

Qt documents view transforms separately from scene contents:
https://doc.qt.io/qt-6/qgraphicsview.html

Qt documents length-based path trimming used to prepare dash intervals:
https://doc.qt.io/qt-6/qpainterpath.html#trimmed
