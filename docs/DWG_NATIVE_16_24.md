# DWG improvements · 16.24

Use Ctrl+O / logo → Open as before. Type **DWGSETTINGS**, or open Help → DWG support, to choose:

- **Auto** (default): LibreDWG reads DWG objects into JSON, then PY.cad maps supported objects into its in-memory drawing model. No intermediate DXF file is created on this route. If the adapter cannot map a structure, the entire direct attempt is discarded and the established DXF compatibility reader opens the original source. Import notices identify the fallback and reason.
- **Direct**: same direct adapter, but unsupported structures produce an error instead of retrying. Useful for verifying which reader handles a drawing.
- **Compatibility**: the previous DWG → DXF → PY.cad route. Retained for broader existing coverage and troubleshooting.

This is an initial direct 2D adapter, not an in-process DWG database. It invokes an isolated LibreDWG CLI and uses a temporary JSON object stream, plus in-memory ezdxf entities to reuse the existing importer. It does not create an intermediate DXF file on a successful direct open. JSON can be larger than DXF and Auto can spend extra time on a fallback. Direct is not guaranteed faster or smaller. No performance improvement is claimed without testing the actual drawing.

## Current direct scope

Lines, points, circles, arcs, full ellipses, rays, construction lines, lightweight polylines with bulges, supported text, basic block definitions/inserts, solid faces and supported hatches. Hatch polyline boundaries, line/arc edge boundaries, holes, island flags, pattern definitions, angle and scale remain hatches. Compound hatches use the existing even-odd representation. Existing XY flattening and supported internal geometry rules still apply.

Blocks retain names, insertion transforms and base points. Layers retain supported color, lock/frozen/off and plot flags. Paper-space geometry/viewports, splines, attributed blocks, complex application metadata, referenced custom linetypes, gradients, unsupported hatch edges and other unsupported structures require compatibility import. Older text samples with EED metadata use Auto fallback. This list is deliberately conservative; a successful direct import is still a supported drawing view, not complete DWG preservation. Polyline widths are approximated as centerlines with an explicit import notice, matching the internal model's existing limitation.

Both GUI reader stages remain isolated/cancellable; cancelling does not install a partial drawing. Reader crashes, nonzero exit codes and timeouts fail the open rather than silently accepting partial output. Existing source embedding (up to 16 MiB) and source-overwrite protection remain. Larger sources remain path-linked, so retain the original DWG.

## Saving DWG

On Windows x64 and Ubuntu 24.04+ x64, **Save As → DWG** now uses bundled GNU LibreDWG's writer for **R2000 / AC1015** output. There is no proprietary-converter requirement on these platforms for that supported output target. Saving still passes PY.cad's supported export representation through DXF; direct JSON reading does not make export lossless.

Before replacing a destination, the exporter requires zero writer errors, verifies the AC1015 signature, reopens the result through the independent compatibility reader, then compares block/model/paper-space entity-type counts and hatch-loop counts. A failed check leaves the destination unchanged. This structural check does not prove geometric, text, styling or application-metadata equivalence in every external CAD program. Export is synchronous and has tool timeouts; large exports/read-back checks may take time.

Modern/proxy/dynamic/application objects not represented in PY.cad cannot be restored by this writer. Gradient-hatch export to R2000 is explicitly rejected; use .pycad or DXF. Other features unsupported by R2000 are not promised. Export may fail rather than produce an incomplete drawing. Save a **.pycad master**, keep the original DWG, and inspect exported copies in your target CAD application. The Save As dialog explains this before export. The source DWG is never edited in place through interchange Save As.

Other platforms can install compatible LibreDWG `dwgread`, `dwgwrite` and `dwg2dxf` on PATH. Overrides: `PYCAD_DWGREAD`, `PYCAD_DWGWRITE`, `PYCAD_DWG_CONVERTER`, each an absolute executable path. `PYCAD_DWG_MODE=auto|direct|compatibility` selects policy; an explicit legacy converter override retains Compatibility unless the mode is also explicitly set. The existing separately installed ODA exporter remains a fallback when no LibreDWG writer is available; its own terms apply. No macOS LibreDWG binary is bundled.

## Source and validation boundaries

GNU LibreDWG 0.14 tools, corresponding unmodified source tarball, GPL-3.0-or-later license, AUTHORS and rebuild instructions are under `vendor/libredwg`. Platform hashes are in its manifest. PY.cad's project license and approved logo are retained. No Autodesk or other proprietary SDK is bundled.

Official references:
- https://www.gnu.org/software/libredwg/
- https://www.gnu.org/software/libredwg/manual/html_node/Programs.html

Linux CLI execution, direct and compatibility GUI import offscreen, actual R2000 round trips, cancellation, source preservation and write failure checks are tested. Native Windows/macOS execution, physical GPU operation and this user's own large drawing remain unverified. Cross-compiled installers are not evidence of native execution.
