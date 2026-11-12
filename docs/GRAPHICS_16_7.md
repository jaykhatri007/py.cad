# Graphics in PY.cad 16.7

Open **View > Graphics > Settings and diagnostics**, click **CPU / OpenGL**
in the status bar, or type **GRAPHICSCONFIG** (also **GRAPHICS / GRAPHICSINFO**).
The Graphics tab in Options offers the same saved mode. Changes apply to the
current 2D canvas and all existing/new model panes without replacing documents,
cameras, live tools, selections, snap preferences or undo history.

| Mode | Behaviour |
| --- | --- |
| Auto (default) | Tests the current driver in an isolated process. Uses OpenGL for a recognized hardware/virtual renderer that passes two-frame pixel readback. Otherwise uses software. |
| Hardware | Tries a driver that passes the same check, including an unclassified OpenGL driver. A known CPU OpenGL renderer or a failed check falls back to software. |
| Software | Uses Qt's raster painting, without creating an OpenGL viewport or running the driver probe. |

The OpenGL path uses Qt's OpenGL2 QPainter engine for 2D drafting and each of
the four model panes. Existing hatches, text, clipping, underlays, paper spaces,
materials, visual styles, previews, grips and navigation share their existing
drawing logic. All panes request the same surface format with depth/stencil
buffers, up to four samples and swap interval one; the driver chooses what it
actually supports. No extra Python graphics library is required.

This accelerates painting and composition when the driver provides hardware
support. Geometry calculations, 3D camera projection, face ordering, DXF
parsing, quantities and AI requests continue on the CPU. This is the existing
orthographic model viewer with accelerated painting, not a new GPU geometry
kernel or a depth-buffer-based scene engine. Performance depends on drawing,
driver and hardware; no universal speedup is promised.

## Detection and fallback

The separate graphics check has a 12-second parent timeout. It creates a small
temporary check window and verifies two distinct painted frames by framebuffer
readback. Driver details include vendor, renderer and OpenGL version. Known
CPU renderers such as llvmpipe, SwiftShader and GDI Generic are reported as
software. Virtual GPU strings are distinguished from proof of a physical GPU.

Detection failure, a crashed/timed-out check, missing context, failure to present
an initial frame, or a lost viewport context returns the app to software.
An unfinished activation leaves a local recovery marker, so the next launch
starts with software. Choose **Retry detection** after resolving the driver or
display issue. A native driver crash inside the main application cannot be
caught by Python; the isolated check and activation marker reduce that risk.
Save drawings regularly as with other desktop applications.

Use the operating system's graphics drivers. PY.cad does not install kernel or
display drivers. The offscreen, minimal and VNC Qt display plugins use the
raster path because they do not support OpenGL widget composition.

## Reports and recovery launch

**Copy report** and **Save report** export the current mode, active backend,
driver check, presented frame count and the reason for fallback. They do not
upload anything. Drawing content, API keys and environment variables are not
included. A driver string and a successful rendering test do not independently
prove which physical GPU performed the work.

To force a recovery launch from a source environment:

```sh
python main.py --graphics software
```

The environment variable `PYCAD_GRAPHICS=software` also overrides the saved
startup mode. On Ubuntu, `bash start.sh --software-rendering` selects this mode.
On Windows Command Prompt, set `PYCAD_GRAPHICS=software` before running the
source launcher. Remove that variable to use the saved startup preference.
No drawing file format or existing settings identity has changed.

The exact checks performed for this release and their limits are in
`VALIDATION_16_7.txt`. GPU hardware, driver-specific behaviour and native
Windows/macOS operation require testing on the corresponding machines.

Implementation references (Qt 6.11 primary documentation):

- https://doc.qt.io/qt-6.11/qopenglwidget.html
- https://doc.qt.io/qt-6.11/qgraphicsview.html
- https://doc.qt.io/qt-6/qopenglcontext.html
