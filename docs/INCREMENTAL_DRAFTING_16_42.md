# PY.cad 16.42: incremental drafting and faster presentation

Ordinary independent drafting now keeps the existing persistent scene. Previously every model revision triggered a complete snapshot and scene preparation, including after individual line clicks. A worker cache alone could not eliminate that traversal.

The new bounded edit journal identifies small supported changes and records only the affected display batches. New geometry is appended in batches of up to 128 objects. Changes to existing geometry replace its original batches; deletion, undo and redo update membership and the spatial index. Geometry moved outside its original bounds remains visible. Selection overlays include changed objects. Pending check markers are cleared after edits.

The unchanged view is cached as a transparent image, with newly drafted geometry drawn over it. Navigation replays the persistent vectors at the current camera transform. Eligible continuous line batches use native Qt paths. Coordinate entry and command prompts no longer increment the model revision merely to refresh panels. During supported edits, panel refresh is deferred by 120 ms while geometry and undo state update immediately.

Recording releases temporary canvas closures immediately. A full garbage collection occurs at a completed full-scene load boundary, outside paint and drafting handlers; automatic garbage collection remains enabled.

## Scope and correctness

The fast path covers independent lines, circles, arcs, points and small polylines (up to 128 vertices), with conservative restrictions for expensive dash patterns. Associated source objects, constraints, generated building features, expensive mixed batches, macros, global styles, BOQ overlays and unsupported history changes retain full preparation. The 128-vertex threshold is a local update optimization, not a drawing import limit. REGEN explicitly regenerates the complete display.

The journal retains at most 2,048 events. If its continuity, model revision, membership or style signature becomes invalid, the display uses full preparation instead of risking stale geometry.

## Validation and measurement

See the included VALIDATION_16_42 reports for measured results, test counts and installer checks. The reproducible benchmark is scripts/benchmark_drafting.py. It uses a real MainWindow with 80,000 synthetic lines, offscreen software rendering, snapping and grid disabled. The baseline samples five line segments; this build samples fifty. Handler duration, commit-to-render-ready time and vector presentation duration are separate measurements. They do not measure physical mouse-to-monitor latency or establish a universal 1 ms guarantee. The user's heavy DWG/DXF and a physical GPU were not available for testing. Windows and macOS installers are cross-built and inspected, not executed on those operating systems.

## Research used

Qt documents retained scene geometry and view transforms in [QGraphicsScene](https://doc.qt.io/qt-6/qgraphicsscene.html). Autodesk documents display regeneration and its scope in [REGEN](https://help.autodesk.com/cloudhelp/2026/ENU/AutoCAD-Core/files/GUID-A4FB9763-625A-4C4F-B948-100BE5566694.htm). Python documents collection generations and explicit collection in [gc](https://docs.python.org/3.14/library/gc.html). These support the architectural approach; this release makes no claim about proprietary AutoCAD internals or comparative speed on real drawings.
