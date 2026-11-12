# PY.cad 16.34 — coordinated workflows

Open **Workflow → Coordination**, type `COORDINATION`, or search Ctrl+Shift+P.
The release extends the existing Properties dock and adds five connected pages.

| Command | Workflow |
| --- | --- |
| SHAREDPROPERTIES | Show the unified Properties dock for the current selection |
| BLOCKLIBRARY | Current-drawing block browser, sampled thumbnails, categories and favorites |
| REFCOORD | Reference status, definition dependencies, relink/reload and cached restore |
| PROJECTSTANDARDS | Portable standards capture, differences, application and native-file batch |
| TUTORIALS | Six guided lessons, local completion checklist and a sample copy |
| RELEASECHECKS | Cancellable native roundtrip/render/selection measurements |

## Unified Properties

Select multiple objects. Shared layer, linetype, color, transparency and hyperlink
controls now display **mixed** rather than silently displaying the first object's
value. The bounds describe the combined selection. The shared-field table lists
only attributes common to all selected objects; coordinate fields use clear X/Y
labels and full-key tooltips.

Check only the fields to change and enter explicit values. The whole candidate
native drawing validates before one Undo step is committed. Mixed placeholders
are never applied as values. Object IDs remain unchanged; ordinary associative
source links continue to identify their objects. The selection refreshes to the
updated objects. Layer visibility/lock rules remain in effect.

The table supports common typed geometry/style fields, coordinate components,
text content and common block-attribute tags where available. Specialized
architecture/building/view metadata retains the existing single-object editor;
this does not expose arbitrary Python attributes or add a spreadsheet scripting
language. Existing single-object Properties behavior is retained.

## Block browser

BLOCKLIBRARY searches definitions in the **current drawing** by name/category.
Favorites and categories are local, name-based application preferences, so they
can be reused for identically named definitions in other drawings. They are not
embedded into an exported DWG or synchronized with a cloud catalog. This release
does not add automatic scanning/import of external block-library files.

Thumbnails are generated lazily from a bounded geometry sample: up to 128 leaf
objects and 2,000 visited definition nodes, with a nesting inspection cap. These
bounds affect thumbnails only, not the source drawing or its import. Icons omit
some styling and attributes; Preview renders the selected reachable definition
with independent nested definitions and text/dimension styles. The source
geometry is never shared/mutated by the preview.

Choose scale and rotation, then place the block with a cursor ghost. Esc cancels
placement; a successful insertion is one Undo step. The tool rejects a changed
drawing/block so stale ghosts are not silently committed. Managed architectural
or table definitions must be created through their source tools. Existing block
creation/editing and external-reference attach tools remain available.

## Reference coordination

The table combines source availability/change status with nested definition
parents. The dependency view lists parent → child definition edges present in
this drawing, including missing-definition warnings. Locate selects direct or
ancestor instances that use the reference. Reloading a definition updates all
of its instances through existing block synchronization.

Relink chooses a source DWG/DXF and uses the established reload operation. Unload
and cached restore use the existing private integrity-checked reference cache.
Missing external paths retain the last imported drawing geometry. Source files
are read, not rewritten. Reload all reports each result; completed per-reference
operations remain undoable if a later operation fails or is cancelled.

Status uses the existing source size/mtime records. It is not a cryptographic
content-change monitor. Nested control describes the definition graph already
loaded into this drawing; it does not recursively discover all dependencies on
the filesystem. Current reference reload imports a flattened source snapshot,
so full native DWG attach/overlay semantics are outside this workflow.

## Project standards

Capture a portable JSON profile containing layer color/linetype/lineweight/plot
flags, complete text and dimension style definitions, and plot presets. Export
it and load it in another drawing. Preview lists added/updated definitions;
Apply asks to commit those changes in one Undo step. Existing geometry, layer
visibility/frozen/locked states and unrelated definitions remain unchanged.
Profiles add/merge definitions; they do not remove existing ones or rename
objects. Current style selections remain as they were.

The profile's drawing units must match the destination. Convert units explicitly
before applying a profile with a different unit system. Profiles contain data,
not executable code. Import accepts up to 8 MiB and 1,000 records per section.
These profile bounds do not limit drawing imports.

Apply to native files creates **new** `name-standard.pycad` outputs. Existing
outputs and original inputs are never replaced. The worker validates profiles,
checks each source, reports per-file failures and can be cancelled. Completed
outputs remain after cancellation. Publication requires an exclusive hard link
on the output filesystem; unsupported filesystems report failure rather than
falling back to a partially visible copy. Private staging is cleaned by the UI.

The standards batch is native-only. Use existing BATCHDRAWINGS to convert DWG/DXF
inputs to native drawings first. Ordinary current-drawing standards application
works after those files have been opened normally.

## Guided lessons and sample

TUTORIALS provides drafting/snaps, multi-area hatching, sheets/PDF, BOQ evidence,
AI proposal review and coordinated-property/library/standards lessons. Each opens
the relevant existing command. Completion is a manual local checkbox, not an
automatic assessment of drawing correctness.

Open sample creates a separate **unsaved copy** of
`examples/coordination_studio.pycad`. Your current drawing stays in its tab, and
ordinary Save asks for a new filename. The sample contains two architectural
rooms with hosted openings and dimensions, nested furniture blocks, hatching
practice areas, two paper layouts, a title-block set and traceable unpriced
furniture counts. It is practice geometry, not construction documentation.

The AI lesson uses the existing offline parser and reviewed action path. An
external model remains optional and user-configured; no service key or external
AI request is required for the tutorial.

## Release checks and verification

RELEASECHECKS stages the current document into a cancellable worker and measures
native decode/synchronization, a software viewport capture and one indexed
selection probe per repetition. It records roundtrip fidelity, render errors,
source-mutation checks and memory samples. These are host-specific diagnostics;
they do not certify GPU acceleration, a memory leak or universal response times.
The current-document worker excludes original DWG/DXF import time.

For original-file import measurements, run from the source/runtime environment:

```bash
python scripts/release_stability.py /path/to/project.dwg --repeats 2 --report stability.json
```

The script uses a temporary app-data profile, hashes originals before/after,
and uses the normal GUI import/cache path. Repetitions of an unchanged DWG may
use the validated cache. Native/DXF inputs are also supported. Render and pick
measurements use a separate copy. Actual attached project drawings were checked
in this release; their geometry is not included in the package.

`.github/workflows/native-acceptance.yml` now includes Linux, Windows and macOS.
`scripts/native_install_acceptance.py` supports a generated macOS Universal ZIP
as well as Linux/Windows setup. The workflow is opt-in and has not been submitted
to a remote repository by this release task. Windows/macOS native results remain
unverified until these checks are run on those hosts. See VALIDATION_16_34.txt
and STABILITY_16_34.json for the checks and measurements actually obtained.

Shutdown stabilization also disposes runtime document Undo stacks while Qt is
still alive and releases temporary preview stacks on close. This cleanup does
not change saved drawing geometry. The release runners keep the application
alive through teardown and explicitly drain their temporary UI resources.

Native schema remains **16**, with schemas 1–15 still readable. No application
dependencies or licensing terms are changed; the original logo and notices stay
included. Workspace metadata/tutorial progress is local application state.
