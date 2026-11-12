# Windows uninstall — PY.cad 16.13

Install or update with the 16.13 Windows installer first. The source-folder
start_windows launcher is portable use and does not register an uninstaller.

## Remove the installed application

1. Save your drawings and close PY.cad and its setup windows.
2. Open Windows Settings → Apps → Installed apps (Windows 10: Apps & features).
3. Find PY.cad and choose Uninstall. Confirm the native prompt.
4. Watch the native progress window. Click Close when removal completes.

You can also use Start → Uninstall PY.cad, or double-click
`%LOCALAPPDATA%\PyCAD\Installation\Uninstall-PY.cad.exe` for a default install.
A custom installation uses its own folder. The native uninstaller has Retry and
Open log. If the app is still open, close it and click Retry. It never force-kills
a drawing session. No browser is used. It works offline without downloading or
installing dependencies, and uses a temporary self-copy so the installed EXE can
be removed. Temporary cleanup is attempted after the window closes; restrictive
Windows policies may leave that helper in the current user's Temp folder.

## What is retained

Drawings/project formats, user settings and AI settings, logs, and untracked or
modified files are kept. The uninstaller records only newly installed owned
files and removes a file only when its contents still match that inventory.
It never recursively deletes the installation tree. Drawing formats are excluded
from removal, including PY.cad, DXF/DWG, PDF, IFC and common 3D exports. This can
also retain shipped sample drawings. Files outside the installation are untouched.
Shared Microsoft runtimes and system dependencies remain installed.

The install folder may remain with retained files. Existing files from releases
before 16.13 are deliberately not claimed during an upgrade; old environments
and caches may remain after removal. Inspect any remaining folder before deleting
it manually. Save your work in your own project folders as usual.

Cancelling removal can leave the application partially removed. The recovery
uninstaller and inventory stay available until removal succeeds; run it again to
finish. A broken or tampered inventory, linked/junction path, or locked owned
file stops removal rather than widening the deletion scope.

Installed-app entries are per Windows account and installation root; no admin
rights are requested by uninstall. Shortcut cleanup checks that each shortcut
still targets this installation. The application layout from 16.12 is retained.

## Developer validation and acceptance

Portable ownership/removal tests run on Linux, with Windows binaries and test
fixtures cross-compiled. No actual Windows registry, shortcut COM, native frame
or end-to-end installation/uninstallation was executed in this environment.

On a Windows test account, install 16.13 and check both Settings and Start.
Cancel the initial prompt and verify the application still launches. With the
app open, request removal and verify the Close/Retry instruction. Close the app,
retry, verify the application entry and managed shortcuts disappear, and check
inside/outside drawing files and modified source files are retained. Confirm
Close exits the uninstall window and a fresh reinstall succeeds. Test a path
with spaces and apostrophes, an upgrade from 16.12, and a second custom root.

Developer registry/shortcut fixture (isolated temp registry key and redirected
shortcut folder): `PYCAD_UNINSTALL_TEST=1 go test -run TestWindowsUninstall -v`
using the equivalent Windows environment-variable syntax. Native setup window
fixture tests remain available with PYCAD_NATIVE_UI_TEST=1. These fixture tests
are separate from the real install/uninstall acceptance described above.
