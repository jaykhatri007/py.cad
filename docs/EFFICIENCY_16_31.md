# PY.cad 16.31 — efficiency workflows

Use **Workflow → Efficiency** or type `EFFICIENCY`. The compact hub has eight pages. Existing drafting, professional and productivity tools remain available; native schema stays 15.

| Command / shortcut | Use |
| --- | --- |
| IMPORTCACHE | Enable/disable faster DWG reopening, inspect usage, clear disposable imports |
| RECOVERYCENTER | Automatic recovery setting, checkpoint tabs, inspect/open saved history |
| SELECTCYCLE; Tab / Shift+Tab | Cycle editable objects under the cursor while Select is active |
| COMMANDPALETTE; Ctrl+Shift+P | Search tools, commands, aliases, shortcuts and descriptions |
| CLEANUPPREVIEW | Review duplicates, zero-length lines and unused definitions before removal |
| BATCHDRAWINGS | Convert/plot multiple DWG/DXF/native inputs with cancellation and per-file results |
| REFDIAGNOSTICS | Check/relink drawing references and CSV links; inspect/substitute font families |
| PERFDASHBOARD | Object/memory/import/cache/frame diagnostics with relevant settings |

## Faster reopening

The normal GUI DWG open path stores a private native snapshot of a successful import. Every reuse checks the source SHA256, canonical path, selected import policy, build version and reader identity. It also checks the cached bytes and runs the native validator in a cancellable process. Changed/corrupt/missing entries fall back to the normal reader. Changing import mode or disabling the cache bypasses old imports. Cached data never replaces an edited workspace or writes to the source DWG.

Snapshots retain imported geometry, metadata, source archive and notices. Display construction is still required, so cached reopening is not instant. Only the GUI DWG open path is cached; regular API imports and DXF/native opening retain their existing behavior. External references remain imported snapshots until explicitly reloaded through their reference tools. Retention is up to ten native imports / 512 MiB. Clear cache removes only owned cache files, not original drawings or user saves.

## Automatic recovery

Validated recovery snapshots reopen as unsaved editable copies after an interrupted session. Turn **Automatically restore validated interrupted sessions** off to retain the recovery question instead. Recovery does not overwrite original drawings. Recovered work must be saved normally.

Unsaved undoable edits schedule a checkpoint after 30 seconds without a new edit. The regular timer defaults to one minute and retains an existing configured interval. Active selection/grip drags are not checkpointed mid-preview. Checkpoint now is also available. Work since the last completed checkpoint can still be lost; this is snapshot recovery, not a transaction log or power-loss guarantee.

Original recovery snapshots remain until a successful native save of all outstanding work or confirmed normal shutdown. Saving with other unsaved tabs updates their recovery snapshots. History entries are integrity checked and open as separate unsaved copies. Consecutive identical history snapshots are deduplicated. Invalid recovery data produces a clear failure / existing fallback question rather than automatic use of unvalidated content.

## Overlap selection

Move the cursor over geometry while Select is active and the command line is empty. Tab selects the first hit, then advances through the remaining hits; Shift+Tab reverses. The status bar identifies the current position in the list. Right-click **Choose overlapping object…** opens a named choice list. It includes object kind, layer, block name and ID so identical-looking objects can be distinguished. Hidden/locked/isolated-away objects are excluded. Geometry, Undo history and saved data are unchanged.

Tab retains normal command completion when text has been typed. Ctrl/Alt/Meta shortcuts retain their existing routing.

## Command palette

Ctrl+Shift+P opens the palette. Type words from a label, canonical command, alias, shortcut, tab/panel or help description. It uses implemented ribbon routes and actual QActions. Planned ribbon entries are excluded; disabled actions stay disabled. Enter or double-click runs the selected action through existing command routing. Escape dismisses the palette without running anything.

## Reviewed cleanup

Build the list, tick entries, optionally highlight checked objects, then Apply. Nothing is automatically removed when building the preview. The operation checks that the drawing still matches the proposal, validates the whole candidate drawing, then applies with one Undo/Redo step.

Object cleanup covers zero-length lines and exact LINE/ARC/CIRCLE/LWPOLYLINE duplicates; reversed straight lines are recognized. Different colors, linetypes, transparency, hyperlinks and native fields remain distinct. Managed/grouped/associated geometry is protected. This is not tolerance-based geometry merging.

Unused blocks, layers, text styles and dimension styles are listed conservatively. Current/default definitions, external references, live metadata links and definitions reachable from placed blocks are protected. A block referenced by another retained definition cannot be removed by itself: select the eligible unused dependency group together or keep it. Styles referenced by unused blocks may become eligible only after those blocks are removed and the preview is refreshed.

## Batch conversion and plotting

Choose DWG, DXF or native inputs and an output directory. Choose Native, DXF or PDF. PDF can plot Model only or Model plus all native paper layouts. DWG output is not offered in this batch workflow. Existing input/output files are never overwritten; duplicate output names are skipped and reported.

DWG/DXF reads use the existing cancellable GUI import pipeline; pure native/DXF/PDF exports run in a separate process. Each file receives Completed, Skipped, Failed or Cancelled/Not run status. Errors do not stop unrelated files. Cancel stops the active read/export before publication; already completed outputs remain. Display preparation uses the existing non-cancellable QObject construction phase, then cancellation can continue. Owned staging directories and partial files are removed. A uniquely named JSON report is saved in the output directory, including import/export notices. Original drawings and the active workspace remain unchanged.

PDF/DXF exports keep the existing format limits: unsupported DWG content can be omitted/approximated; native editing relationships may become ordinary interchange geometry. Review the per-file notices. Batch work does not remove those format limitations.

## Reference and font diagnostics

Scan external drawing paths, stored font families and linked CSV tables. Relink a drawing through the existing reload/unit-conversion workflow. Missing font families can be replaced with an installed family using Undo. Relinking CSV updates its path while retaining current cells; reload it explicitly in Drawing tools to review new values.

Native raster/PDF underlays are embedded PNG data. Their original image files are not needed to open a native project; manage/replace them through UNDERLAYS. Original SHX/font filenames are not always retained, so font diagnostics cover stored Qt families, not a complete reconstruction of the source CAD font environment.

## Performance dashboard

Refresh the dashboard for counts, large definitions, process memory, recent import/cache events and grouped frame timings. Full/direct redraw, cached frames, progressive frames and navigation previews are measured separately. A preview's fast frame time is not presented as full-drawing rendering speed. Median and p95 describe recorded session samples, not a hardware guarantee.

Recommendations use the current drawing and timings. Buttons open existing cached/progressive, graphics and regional-cache settings; they do not silently alter drawing geometry or assert a physical GPU speedup. Full JSON diagnostics remain exportable.

## Validation and platform scope

See VALIDATION_16_31.txt for actual checks. Native Windows/macOS installation and physical GPU performance require testing on those systems. Saved project schema remains 15, readable by 16.29/16.30. Original user DWGs used for acceptance checks are not included in the distribution.
