# Large drawings and object editing — 16.20

**Historical 16.20 notes:** the fixed drawing quotas described below are removed in 16.21. See [16.21 behavior](DRAWING_QUOTAS_16_21.md).

## Opening and hatches

The stored-entity limit is 500,000 across model geometry and definitions (previously 100,000). The transformed display allocation limit is 2,000,000 instances (previously 500,000). Nesting/cycle checks, the 100 MiB file limit and 1,000,000 stored-vertex limit remain. Limits prevent uncontrolled allocation; this is not an unlimited-size CAD engine. Separate messages distinguish entity count from nesting.

Imported complex, disconnected and touching hatch paths remain **HATCH objects** with their pattern, scale, angle, islands and source path flags. Compound even-odd fill replaces the earlier conversion to polylines. Native save/load and DXF export retain these loops and flags. Curved edges are flattened at the importer's 0.01 drawing-unit tolerance; import is not a lossless DWG implementation. Malformed/unsupported entities may still be omitted with warnings. Dense pattern previews can use a screen density approximation; the hatch model remains unchanged. Export/plot may reject patterns too dense to render safely. Original files remain unchanged by opening.

## Selection performance

Click/release selection updates Properties and overlays without full-drawing dirty comparisons or layer/tab refreshes. Ordinary picking uses an adaptive spatial grid and a cached list of unbounded rays/construction lines, instead of scanning every entity on every query. Large blocks also build disposable child indexes after the first pick; later picks reuse them. Idle Select uses raw cursor coordinates and skips drafting snaps; object/grip drags still use snapping with the moving selection excluded. The unchanged model and selected geometry are cached as separate viewport images; grips, snap markers, checks and previews draw separately. Edits, undo/redo, style changes, view changes and document switches invalidate the image. The cache is disposable, is never saved, and does not change plot/export geometry. Initial import, first paint, zooming to all objects, very large block picks and complex edits can still take time.

## Commands and right-click

Right-click in Model space selects the object under the cursor when necessary and opens a compact menu. Available actions include Properties, Select Similar, Isolate Objects, End Object Isolation, Block Editor, Explode, Group/Ungroup, Draw/Modify tools, Undo/Redo and Zoom Extents. During a running tool the menu also provides Enter/Finish and Cancel. Locked/hidden geometry stays protected. Paper-space viewport editing retains its existing controls.

- **EXPLODE** or **X**: select objects first. Performs one level of decomposition. Blocks preserve placed translation/rotation/uniform scale and visible attribute text. Polylines preserve circular bulges as arcs; splines become the same sampled line segments used by the display, not exact analytical splines. Hatches become closed boundary polylines only when explicitly exploded. Dimensions become graphical lines/fills/text and lose association. Undo restores originals and relationships.
- A **LINE** is already primitive and cannot be decomposed further. Circles, arcs, text and other unsupported primitives are retained. Empty ordinary blocks can be removed by Explode. Xrefs and clipped blocks are protected; edit their source or remove clipping first. Parametric building objects must be detached before decomposition. Mixed selections retain unsupported objects.
- **GROUP** joins the selected objects logically; their geometry remains ordinary editable entities. Selecting a member selects its visible, unlocked group members. **UNGROUP**, or EXPLODE on a group selection, dissolves the group while keeping all geometry. A second EXPLODE decomposes member objects. Native files and DXF groups preserve supported members. Clipboard copying remaps group member IDs.
- **SELECTSIMILAR** matches object type and layer; block references also match block name. Hidden and locked objects are excluded.
- **ISOLATEOBJECTS** / **ISO**, **UNISOLATEOBJECTS** / **UNISO** temporarily filter the current drawing view. Isolation is per document, does not change layers or drawing data, is not saved and does not mark the file modified. End isolation before expecting all objects in view-based operations such as plotting; exporting the model retains all entities.

## Block editing

Select one block to see **Block: name** in Properties. Double-click its geometry, choose Block Editor in the right-click menu, or use **BEDIT**. BEDIT opens the selected block directly; without a selected block it offers the definition list. Xrefs remain source-managed.

The editor works on independent copies, provides drawing/modify tools, command input and Undo/Redo. Save updates every insertion through an undoable definition change. Cancel discards edits. Definition saves reject missing/cyclic references and expansions above the display budget. This is a static 2D definition editor; it does not implement proprietary dynamic-block actions/parameters or full AutoCAD parity.

## Updating and acceptance

Close PY.cad, install this version to the existing destination and launch the new shortcut. Keep source DWGs and use a new native/DXF filename while checking imported drawings. New compound-hatch fields require PY.cad 16.20 or newer for native editing.

Tests use generated 100,005-entity DXF input, a 110,000-line selection case, compound/complex hatch round trips, object decomposition/undo, DXF groups, context actions and block double-click routing. These establish controlled regressions, not performance guarantees for arbitrary DWGs. The user's failing DWG was not supplied. Actual Windows/macOS installation and GPU behavior are not exercised by Linux offscreen tests or cross-compilation.
