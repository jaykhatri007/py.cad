# Hatch editing and CPU/GPU rendering — 16.23

## Double-click a hatch

In Select mode, double-click inside an editable hatch's filled region to open its hatch settings with its current pattern, scale, angle, colors and other options. Accept applies an undoable edit; Cancel leaves the drawing unchanged. This also works on a hatch inside the block editor. A hatch inside a block reference is edited by opening the block definition first, then double-clicking the hatch there.

Ctrl/Alt repeated clicks remain selection actions. Locked/hidden objects do not become editable. A click in an island/hole does not hit the surrounding hatch. If a line or another object lies under the cursor, picking retains the existing closest-stroke preference; click a clear filled part of the hatch, or select it and use HATCHEDIT.

## Processor controls

Click the **CPU / GPU** status button, use **View → Graphics · CPU / GPU → Settings and diagnostics**, or type **GRAPHICS**, **PROCESSOR** or **PROCESSING**.

- **Auto (GPU when available)** probes the OpenGL driver, uses an accepted driver, and falls back to software when necessary.
- **GPU / OpenGL** requests the OpenGL display backend, retaining detection, failure recovery and CPU fallback. A selected GPU preference is not proof that hardware is active: check Status and the report's active backend/driver.
- **CPU / Software** selects the software display backend.
- **CPU** and **GPU** commands change that rendering preference directly.

The selection applies to the main drafting viewport and supported 3D workspace panes. The block editor retains its separate software canvas. It is not a universal CPU/GPU calculation switch or a selector for an individual graphics adapter.

## 2D drawing path

The settings also offer:

- **Cached drawing** (default): CPU code builds reusable QImage model/selection images. The selected viewport renderer displays/composes those images. This retains the fast repeated-selection behavior introduced in 16.20.
- **Direct drawing**: vector painting commands, including hatch clipping/fill/stroke painting, are issued directly to the selected viewport painter. With an active supported OpenGL backend those paint operations use Qt's OpenGL path. With a software backend they use CPU rasterization. No restart is required.

Direct mode can redraw substantially more geometry per frame. It is not guaranteed to be faster than cached mode, especially on large drawings where CPU geometry preparation dominates. Both choices preserve drawing data and plot/export geometry; they change viewport painting only. Settings persist per user.

## What remains on CPU

The process table and saved diagnostic report explicitly list execution scope. DWG/DXF reading and conversion, geometric calculations, selection queries, hatch boundary detection and pattern-stroke generation, 3D projection/face ordering, and BOQ calculations remain CPU work. There is no implemented CUDA/OpenCL compute backend for those operations. Painting a hatch on a GPU does not move its boundary or pattern-generation algorithms to the GPU.

Qt documents QPainter/QOpenGLWidget as a supported way to accelerate 2D painting on supported hardware. QImage rendering uses Qt's software raster engine. These are capabilities of the rendering route, not a measured speed claim for this release:

- https://doc.qt.io/qt-6/qtopengl-2dpainting-example.html
- https://doc.qt.io/qt-6/qpainter.html

## Verification and limits

Tests cover hatch settings routing/undo/cancel, block-editor hatch editing, islands/locked layers/modifier safeguards, CPU/GPU preference and fallback reporting, persisted Cached/Direct selection, direct painter routing, cached image reuse and quick commands. Existing graphics switching/recovery and hatch rendering regressions are retained.

Linux offscreen tests verify software output and routing; they cannot prove physical GPU acceleration. Native Windows/macOS execution, physical GPU operation/performance and the user's drawing remain unverified. Driver strings may identify virtual graphics. See VALIDATION_16_23.txt for exact checks.
