# Update: 16.45.0

See [Office drafting](../CHANGELOG.md) for the five new 2D tools and usage steps.

# Update: 16.44.0

Immediate line display, including long dashed segments and independent additions beside constrained objects. See [release notes](../CHANGELOG.md) and [details](docs/IMMEDIATE_LINES_16_44.md).

# Update: 16.43.0

Layer-aware display updates and manual REFRESH. See [release notes](../CHANGELOG.md) and [rendering details](docs/LAYER_RENDERING_16_43.md).

# Update: 16.42.0

Incremental independent drafting retains the loaded scene and updates affected objects. See [release notes](../CHANGELOG.md) and [performance details](docs/INCREMENTAL_DRAFTING_16_42.md).

# PY.cad 16.41 — stability and large-drawing processing

Fixes reentrant snapshot and deleted-controller crashes. Reuses unchanged vector batches after edits and prepares picking indexes during loading. See [performance and stability](docs/PERFORMANCE_AND_STABILITY_16_41.md).

# PY.cad 16.40 — persistent vector scene

Pan and zoom reuse stored vector commands across the whole drawing. Type REGEN to explicitly rebuild the display. See [persistent display](docs/PERSISTENT_SCENE_16_40.md).

# PY.cad 16.39.1 — text rendering hotfix

Fixes blank heavy drawings caused by missing text style state in the isolated renderer. See UPDATE_16_39_1.txt.

# PY.cad 16.39 — isolated rendering and zoom reuse

See [renderer guide](docs/ISOLATED_RENDERING_16_39.md).

# PY.cad 16.38 — background refinement and cached navigation

See [background display guide](docs/BACKGROUND_DISPLAY_16_38.md).

# PY.cad 16.37 — persistent zoom display and editable cached xrefs

See [large drawing and xref guide](docs/LARGE_DRAWINGS_AND_XREFS_16_37.md).

# PY.cad 16.36 — large-drawing navigation and polyline grips

Wheel zoom now uses cached previews and progressive refinement for large scenes. Select a polyline, then drag or right-click its square vertex / round midpoint grips. Type `PEDIT` for the full polyline editor. See [the guide](docs/NAVIGATION_AND_GRIPS_16_36.md).

# PY.cad 16.35.2 — cursor dimensions

Live sizes now appear beside the cursor independently of F12 numeric input. View → Cursor Dimensions controls the readout. See [instructions](../CHANGELOG.md).

# PY.cad 16.35.1 — exact-coordinate MOVE

Select objects → `M` → Enter → `0,0` → Enter. See [MOVE instructions](../CHANGELOG.md) for reference points, relative offsets and explicit base-point entry.

# PY.cad 16.35 — drafting tools

Type `DRAFTINGTOOLS` for the six new editing, hatch, search, template and shortcut pages. Read [the feature guide](docs/DRAFTING_16_35.md). Native schema 17 reads schemas 1–16.

# PY.cad 16.34 — coordinated workflows

Type `COORDINATION`. See [the feature guide](docs/COORDINATION_16_34.md) for six workflow improvements. Open the guided sample as an unsaved copy through `TUTORIALS`. Native schema remains 16.

# PY.cad 16.33 — precision editing

Type `EDITING` for six editing/workspace improvements. Read [the feature guide](docs/EDITING_16_33.md). Native schema remains 16.

# PY.cad 16.32 — drawing production

Type `PRODUCTION` for seven new production workflows. See [the guide](docs/PRODUCTION_16_32.md). Native schema 16 reads older schemas 1–15.

# PY.cad 16.31 — efficiency workflows

Open Workflow → Efficiency (`EFFICIENCY`) for all eight additions. Ctrl+Shift+P opens the command palette; Tab/Shift+Tab cycles overlapping selection. Read [the guide](docs/EFFICIENCY_16_31.md). Native schema remains 15.

# PY.cad 16.30 — import repair and drawing responsiveness

Repeated DWG/DXF attribute tags now receive unique import-copy aliases without losing definitions or instance values. Paint-frame caching, nested-block culling and cached pan/zoom previews improve navigation. Read [the release notes](../CHANGELOG.md) and VALIDATION_16_30.txt. Native schema remains 15.

# PY.cad 16.29 — drawing productivity

Open Workflow → Drawingtools (`DRAWINGTOOLS`) for all eight additions. Read [the guide](docs/PRODUCTIVITY_16_29.md). Native schema 15 reads earlier schemas 1–14; keep originals for older releases.

# PY.cad 16.28.0

**Multiple-area hatching:** run H, choose settings, click inside each area, then press Enter to apply all previews together. U removes the last picked area; Esc cancels the operation. All new hatches share the chosen settings and undo together. Native schema remains 14 (readable by 16.27 or newer).

Type **PROWORKFLOW** for ten new professional workflows: regional caches, GPU buffers, associative links, block variants, revisions, advanced viewports, architecture checks, BOQ changes, reviewed room planning, and project packages/portable releases. See the [16.27 guide](docs/PROFESSIONAL_16_27.md). New native saves use schema 14 and require 16.27; schemas 1–13 remain readable. Regional caches are for inspection; GPU buffers are experimental.

Type **WORKFLOW** or open the Workflow menu for nine connected workspaces: diagnostics, progressive display, DWG checks, precision edits, xrefs, sheet templates, recovery history, rule-based BOQ and reviewed AI drafting. See the [16.26 workflow guide](docs/WORKFLOW_16_26.md) for commands, examples and limitations. The 16.26 workflow tools remain available.

**Ubuntu startup repair:** source starts now use the same pinned Qt/Python packages as setup, repair mismatched Qt automatically, and verify QtPdf before launch. **Windows setup:** slower-download tolerance, temporary-network retry, file-copy package installation and live package output. See [Startup and dependency repair](docs/STARTUP_REPAIR_16_25.md).

DWG opening now offers **Auto / Direct / Compatibility** readers. Supported 2D drawings can open without an intermediate DXF file; Auto falls back for unsupported structures. Bundled LibreDWG can export **R2000 DWG** on Windows x64 and Ubuntu 24.04+ x64, with a structural read-back check before replacing the destination. Type **DWGSETTINGS** or use Help → DWG support. See [DWG improvements](docs/DWG_NATIVE_16_24.md). This is not lossless modern-DWG editing.

Double-click an editable hatch to edit its settings. **GRAPHICS / PROCESSOR** opens explicit CPU/GPU rendering choices and Cached/Direct 2D drawing, with a process table showing the CPU-only calculations. See [Hatch editing and graphics](docs/HATCH_GPU_16_23.md).

**Ctrl-click adds** to the selection; **Alt-click removes**. **H / HATCH opens its settings dialog first**, then asks you to pick the area and confirm its preview with Enter. See [Selection and hatch workflow](docs/SELECTION_HATCH_16_22.md).

The fixed drawing file-size, object-count, expanded-display, vertex-count and block-depth quotas are removed. Circular references and corrupt data remain errors; available hardware and parser/tool constraints still matter. See [Drawing quotas removed](docs/DRAWING_QUOTAS_16_21.md).

Large drawings retain compound hatches and faster selection. Right-click provides object commands; **X / EXPLODE**, **SELECTSIMILAR**, **ISO / UNISO** and **GROUP / UNGROUP** are available. Properties shows block names; double-click opens the block editor. See [Object editing and performance](docs/OBJECTS_PERFORMANCE_16_20.md).

Windows setup now creates a logo **Desktop shortcut** and Start-menu shortcut. The installed main window runs through a private runtime copy branded **PY.cad**, with a matching taskbar app ID. See [Windows identity](docs/WINDOWS_IDENTITY_16_19.md).

The default Dark theme now uses lighter neutral grey surfaces and grey gradients. Type **THEME** for grouped, searchable UI and font colors, per-color Reset and Reset all colors. See [Appearance colors](docs/THEME_16_18.md).

Windows setup now offers a destination window (default **C:\Program Files\PY.cad**), with UAC when required. DWG/DXF import fixes and large-drawing display improvements are included. See [Open and setup repairs](docs/OPEN_SETUP_16_17.md).

Commands now show clickable, highlighted shortcut choices. Try **L → Enter** or **Z → Enter**. See [Command options](docs/COMMAND_OPTIONS_16_16.md).

Drafting and Linetype controls now sit after all Home ribbon tool groups, in both grouped and compact modes.

DWG opening now includes a local LibreDWG reader on Windows x64 and Linux x64.
Use Ctrl+O or logo → Open. See [DWG support](docs/DWG_16_14.md).

Windows setup now registers PY.cad in Installed apps and adds an Uninstall PY.cad Start-menu shortcut. See [Windows uninstall](docs/WINDOWS_UNINSTALL_16_13.md).

The larger logo now leads the top menu row. Drafting and Linetype controls are on Home; the extra toolbar row is removed. Click the logo or use Alt+F for the File workspace.

![PY.cad wordmark](assets/pycad-logo.png)

An open-source desktop CAD application with 2D drafting, compact managers,
multiple model views, building objects, quantities and reviewed drafting chat.
Publisher and maintainer: **Jay Kundanlal Khatri, India**.

Version 16.10 opens Windows setup in a native frame with progress, Retry, logs,
license viewing and a Close button that exits setup after completion. No browser
or WebView is used for normal Windows setup. See [Windows setup](docs/WINDOWS_SETUP_16_10.md).
The retained 16.9 update adds 51 linetypes, preview swatches, a searchable manager and drawing
linetype scale. See [Linetype guide](docs/LINETYPES_16_9.md). The retained
16.8 hatch update adds a PAT-compatible hatch editor, 172 library patterns, scale, angle,
origin, custom PAT import, gradients, island controls and DXF pattern preservation.
See [Hatch guide](docs/HATCH_16_8.md). The retained 16.7 graphics support adds detected OpenGL rendering for drafting and all model panes,
with Auto / Hardware / Software modes, diagnostics and software fallback.
Open **View > Graphics > Settings and diagnostics**, click the small graphics
button in the status bar, or type **GRAPHICSCONFIG**. Settings also appear in
the Graphics tab of Options. See [the graphics guide](docs/GRAPHICS_16_7.md).
The Windows setup/repair and DXF responsiveness fixes from 16.6 are included.
The visible name and approved wordmark remain **PY.cad**. Publisher facts and
AI-development disclosure remain as recorded in legal/PUBLISHER.md; upstream
components retain their own authors and licenses.

DXF parsing, conversion and full validation run in an isolated reader process
with progress, Cancel and a five-minute timeout. Cancel/error leaves the current
drawing and source file unchanged. Cyclic, excessive or missing block graphs
are rejected before allocating transformed copies. Native loading also avoids
the previous repeated block traversal and duplicate validation.

Dense hatches use a screen density preview and viewport-bounded strokes; source
spacing/geometry and vector plotting remain unchanged. Intersection snapping
examines at most 64 nearby candidates in dense areas; zoom in when needed.
Import notices use a compact nonmodal report. Current limits include 100 MiB
DXF/native files and a 100,000-node expanded display/cache budget.

## Get started

Use the native setup matching your OS; it detects supported OS/CPU, checks its
requirements, downloads pinned bootstrap components, installs dependencies,
creates a managed per-user environment and launches the app. Internet is needed
for the first installation. The OS may request authorization for system libraries.

| Platform | Setup file |
| --- | --- |
| Desktop glibc Linux x64 | PY.cad-Setup-16.15.0-Linux-x64.run |
| Windows 10/11 x64 | PY.cad-Setup-16.15.0-Windows-x64.exe |
| macOS 13+, Intel/Apple Silicon | PY.cad-Setup-16.15.0-macOS-Universal.zip |

Windows: extract the full ZIP and double-click **Setup-Windows.cmd** to install
in its native frame, or open the matching .exe. The launcher exits immediately.
Use Setup-Windows-Console.cmd only for optional console diagnostics. Run as your normal
user; the missing Microsoft runtime requests its own OS authorization.

Linux: make the .run file executable in file properties, then open it, or run
`bash PY.cad-Setup-16.15.0-Linux-x64.run`. macOS: extract
the ZIP and open **PY.cad Setup.app**. Installers are unsigned. Native Windows
and macOS operation still needs acceptance testing; see VALIDATION_16_10.txt for
exact evidence and limits. Do not describe cross-built targets as fully qualified.

For source-folder use, extract **PY.cad-v16.15-Full.zip**. Inside **PY.cad**, run
`bash setup_ubuntu.sh` then `bash start.sh` on Ubuntu, or `start_windows.bat` on
Windows. `main.py`, requirements files and editable installer source are included.
The full ZIP also includes the native setup files in `installer/packages/`.

## Existing drawings and settings

The Python module remains `pycad`; native drawings/templates remain `.pycad` and
`.pycadt`. Native format/schema, clipboard/recovery records, settings organization,
user-data locations, installation roots and desktop entry IDs remain compatible.
The native source payload keeps its legacy `PyCAD-v15` root. These internal names
are intentional and do not indicate an incomplete display rename. The About
panel and title bar show **PY.cad 16.15.0**. Keep backups when upgrading.

A managed legacy macOS launcher bundle can move to PY.cad.app without deleting
its contents. Unrelated old/new applications are preserved. On Windows, an old
PyCAD shortcut is removed only when its target and arguments match this managed
installation; otherwise it is left alone. Existing settings and drawings are not
renamed. General Linux ARM64 and Windows ARM64 are not qualified by this release.

![Actual PY.cad 16.7 workspace using software rendering](docs/PYcad-16.7-Workspace.png)

## Included features

- Drafting commands, constraints, dimensions, styles, blocks and multileaders.
- Compact ribbon, typed commands, layer manager, File panels, themes and colors.
- Model/paper spaces, layouts, PDF underlays, printing and DXF/native exchange.
- Embedded orbit/model views and optional CadQuery solid operations.
- Tested-driver OpenGL painting, persistent graphics modes and diagnostic export.
- Typed building objects/levels/materials, BOQ and optional IFC4 export.
- Offline drafting chat and optional compatible AI services with Preview/Apply.
- Drawing checks, comparison, portable shared views and explicit WebDAV exchange.

Review output and known boundaries. BOQ uses entered classifications/rates; it
is not a certified estimate or substitute for professional review. Read the
historical feature guides for specific operation limits. Optional ODA conversion
and external AI/model services retain their own terms and costs.

## Source, licenses and release status

Project material is offered under **GPL-3.0-only** for licensable rights that exist
and are held. See LICENSE, COPYRIGHT, THIRD_PARTY_NOTICES.md and LICENSES. The
Help menu has an offline legal viewer with publisher, privacy, distribution and
readiness information. Your ordinary drawing output is not automatically GPL.

The public display-name choice is recorded, but a trademark clearance, statutory
AI copyright claim and donation classification have not been completed. No public
repository/release or donation account was created, application submitted or fee
paid by this update. These are readiness facts, not extra restrictions on GPL rights.
See legal/RELEASE_READINESS.md and legal/TRADEMARKS.md.

The exact source is supplied in this ZIP and embedded in each setup. Advanced
users can run a setup's native executable with `--extract-source NEW_DIRECTORY`.
For a public online binary release, publish the matching exact source beside it
under the applicable license route. Public source/contact URLs must be real;
none have been invented. SECURITY.md describes the current reporting position.

## Rebuild and validation

Use Python 3.12 and the appropriate requirements profiles. Native installer builds
use Go 1.27.3 with no third-party Go module dependencies:

```sh
python installer/build.py --output setup-build
```

The build regenerates embedded source/legal assets and creates the OS-specific
packages. The existing PNG symbol icon has not changed. `assets/BRANDING.md`
records the wordmark edit. `VALIDATION_16_7.txt` reports actual checks. Earlier
screenshots and docs, including docs/HISTORY-PyCAD-through-16.4.md, retain their
historical product names and versions for reference.
