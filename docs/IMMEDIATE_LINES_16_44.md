# PY.cad 16.44 — immediate committed lines

## Reproduced remaining causes

The 16.43 edit journal rejected long dashed lines based on a dash-expansion work estimate. Even a LINE command could therefore request persistent-scene preparation. Existing constraints also sent every new line through the global constraint transaction path, including new lines with no connection to constrained objects. These are reproduced code paths; the user's specific drawing was not supplied.

## Focused change

Local line batches now retain numeric endpoints and resolved pen styles, drawing through native Qt line primitives at the current camera scale. They no longer expand all dash intervals into world-space picture commands to commit a line. Dash spacing, layer colors, lineweight and transparency are retained; zoom/pan behavior for the loaded base scene remains on the existing retained path. Mixed line/non-line additions use separate local batches.

A new independent line can bypass a global solver snapshot when the existing journal proves that its ID is not a constraint or feature source. The constraints and the geometry of constrained objects are preserved. Commands that modify constrained geometry retain the solver path. Automatic room discovery and live schedule dependencies retain their existing synchronization behavior.

The LINE tool also queues committed ink over the last complete scene while a necessary replacement is pending. This is immediate display of committed geometry, not a substitute for committing or saving it. Undo/deletion and document switching remove stale temporary ink; a completed current scene clears the queue. At most 256 recent lines are kept in this temporary queue, with all geometry remaining in the model. BOQ preparation retains its existing path; temporary unmeasured ink is shown in red until the complete overlay replaces it.

The preparation label is not hidden: initial loads, manual REFRESH and genuine global/dependent rebuilds can still show it. Independent supported line placement should not request that preparation.

## Validation

See VALIDATION_16_44.txt and the included JSON benchmark reports. New coverage includes long BYLAYER continuous/dashed/center/dotted lines with undo/redo; unrelated existing constraints without a global solver snapshot; visible committed ink while a worker is deliberately stalled; pixel equality with direct canvas line rendering at four camera scales; selection without new scene jobs; and actual Qt mouse placement of long dashed segments with deferred panel refresh.

The comparison benchmark uses a real MainWindow with 80,000 synthetic base lines and a newly drafted DASHED line alternating between x=500 and x=5500. It uses offscreen software rendering with grid/snapping disabled. Baseline uses five segments; 16.44 uses fifty. Timing is handler-to-render-ready, not physical input-to-monitor latency. The user's file and physical GPU were not available, and Windows/macOS packages were cross-built and inspected rather than executed.

REFRESH, REGEN and other existing manual regeneration commands remain available. Other drawing tools, navigation and model/export data are retained.
