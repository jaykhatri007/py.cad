# PY.cad Studio Setup — Windows, Linux, and macOS

All release installers use the same teal PY.cad wordmark, animated wireframe banner, six-stage checklist, and download information from a shared setup engine. System animation preferences are respected by the presentation on each platform.

| Platform | Setup | Uninstall |
| --- | --- | --- |
| Windows x64 | Run the Setup EXE. It opens a native window and retains destination selection. | Use **Settings → Apps → Installed apps → PY.cad**, or the installed uninstaller. |
| Ubuntu/Linux x64 | Run the Studio .run file with bash. The default window uses system Python 3 and GTK 3. | Right-click **PY.cad** in Applications and choose **Uninstall**. If your desktop does not show application actions, open **Uninstall PY.cad** from Applications. Both open a GTK confirmation without a terminal. |
| macOS Intel / Apple silicon | Extract the ZIP and open **PY.cad Setup.app**. It opens the Studio page on the local setup server. | Run **Uninstall-PY.cad.command** next to the app; keep its bundled `uninstall.py` beside it. |

The progress bars show two different things. The installation bar reports stages. The download bar measures received bytes for the runtime bootstrap when its server provides a total. Managed Python, CAD packages, system libraries, and Windows runtime repair use activity indicators when their package tools do not expose byte totals. Reported package names, sizes and completion are listed. These indicators never invent a percentage.

On Ubuntu/Linux, use `--studio-preview` for a no-install preview or `--classic` for the same Studio design in the local browser page. The CAD payload remains version 16.45.0 and includes the updated Linux launcher. Existing installation and destination handling are preserved.

### Start PY.cad without a terminal

On Linux, open **PY.cad** from Applications or run `bash start.sh` from the extracted project. Once the app starts, you can close the terminal. During initial environment setup, keep the terminal open until the launcher reports that PY.cad started. To create or refresh the portable shortcut, run `bash start.sh --setup-only --install-desktop`. Use `bash start.sh --foreground` only when you want the terminal attached for debugging.

Reinstall with the updated Linux installer to refresh an existing Applications icon and replace the old terminal-based uninstall entry. Close PY.cad before confirming uninstall. On Linux/macOS the uninstaller moves a verified default per-user installation and matching shortcuts into a recovery folder. It leaves settings and other files outside the installation untouched. Check the recovery folder before deleting it to reclaim space. The macOS companion uses the managed installation's private Python runtime.

## Release parity

Build all platforms together from the complete source with:

```sh
python3 installer/build.py --reuse-payload --output ../setup-build
```

The build emits Windows x64, Linux x64, and both macOS architectures, and checks that every target includes the shared Studio artwork. Keep installer changes in the shared setup engine and verify all three presentation paths before packaging. For installer-only updates, preserve the existing verified CAD payload so installed environments can use their existing repair path. Windows and macOS release builds were cross-compiled; interactive native desktop tests on those platforms remain outstanding.
