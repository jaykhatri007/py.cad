# PY.cad 16.41 — lifecycle safety and large-drawing processing

## Crash fixes

The 16.40 snapshot generator could be advanced again from a nested paint callback.
Preparation now runs in a separate cooperative QObject timer task, outside paint
callbacks, with a reentrancy guard and cancellation on reset/close. Painting only
presents prepared geometry or a preparation message. It does not advance snapshot
generators. This also avoids repeatedly repainting the previous scene merely to
advance the next snapshot, which was adding substantial delay after edits.

QProcess signals now connect to QObject receiver slots. Qt disconnects them when
the receiver is destroyed. The former lambdas captured a controller whose C++
object could already have been deleted. Delayed process-exit/read/error/start
signals and preparation timers therefore no longer call deleted controllers.

## Processing improvements

Private snapshot transfer uses versioned, hashed, bounded native-pickle frames.
Cancellation is checked between batches; very large geometry batches retain the
cooperative serializer. The old private snapshot format is still readable.
These are internal temporary files, not a new drawing format. Never load user
files as pickle snapshots.

The renderer process now survives ordinary model/style changes. It caches vector
command batches by geometry fingerprint and display metadata, so a single edit
can reuse unchanged command lists. The main window also reuses unchanged Qt
pictures. Both historical-command caches have 64 MiB budgets; these are cache
eviction budgets, not entity limits. Current drawing scenes can use more RAM.
Style changes invalidate affected cache keys conservatively. Explicit REGEN
clears historical command caches and rebuilds every batch. Obsolete worker
results are rejected and their private temporary output is removed.

The picking index is prepared in cooperative timer slices while the display is
loading, rather than first being built on the first click. Updated bounds are
published atomically only for the matching entity collection and revision.
Ordinary queries retain their synchronous correctness fallback if preparation
has not completed. Querying a changed revision cannot reuse stale bounds.

Normal pan/zoom/resize still reuse the retained vector scene. Selection overlays,
subpixel controls, native/editable objects, original coordinates and exports are
preserved. Multileader style data is now retained alongside text style data in
private snapshots. No new third-party dependencies or drawing schema changes.

## What the AutoCAD research supports

Autodesk publicly documents cached display lists and regeneration of modified
objects, hardware acceleration and video-memory caching, and layer/spatial
indexes with demand loading for clipped/frozen xrefs. These are complementary
techniques; an object count such as 80,000 does not describe drawing complexity.

The changes above apply those principles to PY.cad's measured bottlenecks.
They do not reproduce Autodesk's proprietary implementation, introduce native
DirectX on Ubuntu, or implement AutoCAD-compatible DWG demand loading. The
existing Qt software/OpenGL surfaces remain in use. A dedicated GPU mesh engine,
true per-entity edit tracking, partial DWG database loading and GPU text atlases
would be further architectural work, not features claimed by this release.

Primary sources consulted 6 November 2026:
- Cached display lists / modified-object regeneration:
  https://help.autodesk.com/cloudhelp/2026/ENU/AutoCAD-Core/files/GUID-A4FB9763-625A-4C4F-B948-100BE5566694.htm
- Hardware acceleration, GPU fonts and graphics-memory caching:
  https://help.autodesk.com/cloudhelp/2026/ENU/AutoCAD-Core/files/GUID-14929CF2-8E39-4F87-B8C2-18440B12922E.htm
- Xref demand loading:
  https://help.autodesk.com/cloudhelp/2026/ENU/AutoCAD-Core/files/GUID-5A45465D-287F-460A-91B5-2CB8593FC7F1.htm
- Layer / spatial indexes for xrefs:
  https://help.autodesk.com/cloudhelp/2026/ENU/AutoCAD-Core/files/GUID-E4076F41-2F33-4E42-90D3-A1BA5AE64388.htm

## Validation limits

See VALIDATION_16_41.txt and the paired 80,000-line benchmark JSONs for results.
The provided crash traces were reproduced in focused regression tests before
fixing them. Full CPU/software tests are synthetic and environment-specific;
the actual problem DWG/DXF and a physical GPU have not been supplied/verified.
Initial import, complete snapshot capture, complex associations, exact geometry
and dense vector replay still require time and RAM. This release reuses command
batches after an edit; it still snapshots the drawing to discover changed batches.
No speed comparison against AutoCAD has been performed.
