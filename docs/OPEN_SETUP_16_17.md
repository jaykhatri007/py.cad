# Windows destination and drawing-open repairs — 16.17

Windows setup first opens a native installation-folder window. Its default is
`%ProgramW6432%\PY.cad` / `%ProgramFiles%\PY.cad`, normally
`C:\Program Files\PY.cad`. Type another exact destination or use Browse to
select a parent folder; Browse adds a PY.cad subfolder. Click Install to proceed.
Protected folders require Windows UAC approval. Cancelling does not silently
switch to AppData. The command-line `--root` option remains available.

The elevated installer runs with application launch disabled. When setup closes
successfully, the original unelevated setup process launches the application.
Normal application logs and verification preferences no longer require write
access to Program Files. Uninstall requests elevation when the destination is
protected. Registration and Start-menu shortcuts remain per Windows account.
If UAC credentials belong to a different account, that account receives setup's
per-user registration; this release does not promise an all-users deployment.

The old AppData installation is not automatically deleted or migrated. Keep
personal drawings outside installation folders. After testing this release,
remove an old installation with its own uninstaller. Existing shortcuts may be
replaced when installing the new version under the same Windows account.

## Drawing-open fixes

- Temporary native drawings now flush through a writable handle, correcting a
  Windows read-only-descriptor path that can cause error 9 (EBADF).
- Duplicate hatch loops are deduplicated. Touching/crossing or excessively
  complex external hatch boundaries become closed outlines with an import
  warning, so they cannot abort the complete drawing. Their fill is unavailable;
  review affected regions before plotting or quantities. Original files remain
  unchanged. Supported ordinary hatch fills and islands are retained.
- Stored geometry is still limited to 100,000 entities. Repeated display copies
  have a separate 500,000-instance allocation ceiling (including cached copies
  in the in-memory check). This avoids the previous 100,000 combined-cache
  rejection without allowing unbounded block expansion. Cycles/nesting limits
  and the 100 MiB file limit remain. Exceptionally large files can still exceed
  supported limits; they are not silently truncated.
- Block definitions and placements retain transformed copies during unchanged
  sync/save operations; definition, placement and text-style changes invalidate
  them. The private stamp is never written to native documents.
- Display preparation runs on a background thread after isolated DXF parsing.
  Parsing/conversion remains cancellable; the final preparation phase is shown
  separately and finishes before closing. The Qt undo stack is transferred to
  the GUI thread before interaction.
- Drafting paints query visible viewport bounds rather than drawing all off-
  screen entities. Rays/construction lines remain eligible. Spatial queries
  examine nearby candidate IDs in drawing order, instead of rescanning the
  complete entity list. Plot and paper-viewport drawing paths retain their full
  candidate stream. Large selections use identity sets during UI refresh.

These repairs were developed from the reported messages and synthetic/upstream
fixtures. The user's failing DWG/DXF files were not supplied. Native Windows
UAC, destination-window and installation acceptance still need a real Windows
machine; cross-compilation is not execution. No claim of universal DWG fidelity
or hardware performance is made. See the validation report and retained DWG guide.

Implementation references:
- [Microsoft ShellExecuteEx](https://learn.microsoft.com/en-us/windows/win32/api/shellapi/nf-shellapi-shellexecuteexw)
- [Microsoft _commit](https://learn.microsoft.com/en-us/cpp/c-runtime-library/reference/commit)
