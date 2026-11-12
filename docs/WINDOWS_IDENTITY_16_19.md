# Windows shortcuts and running-app identity — 16.19

Run the matching 16.19 Windows setup, choose the existing installation folder
for an upgrade, and allow setup to finish its checks. Setup creates **PY.cad**
shortcuts on the current Windows Desktop and in Start > Programs, using the
approved PY.cad logo. Windows Known Folders are used, including a redirected
Desktop such as OneDrive. Shortcuts target the stable installed launcher with
the correct installation path and application ID. They do not target main.py.

## Running name and logo

The Windows process receives the stable ID `JayKhatri.PYcad.Desktop` before Qt
creates any windows. Both shortcuts use that same ID. Qt display/application
names and the window icon are PY.cad, with the multiresolution ICO on Windows.

Installed GUI launches use a generated, app-private copy of the managed Python
GUI executable. Its file/product description and embedded icon are PY.cad.
The original interpreter executables, DLLs, standard library and notices are
retained. The private copy is generated at installation, not shipped as a new
third-party binary in this source archive. Its versioned filename begins
`PY.cad-16.19.0-` and ends `.exe`; this avoids overwriting an open executable on
future upgrades. Its product/FileDescription is PY.cad. Source and copy hashes
are recorded, and the launcher checks copy integrity before use.

The bootstrap selects the installed CAD environment, preserves drawing arguments
and restores the ordinary venv Python path for isolated import and graphics
workers. Consequently, background checks/workers can still appear as Python in
Task Manager Details. The main installed GUI process is the branded copy.
Running the source manually with `python main.py` also still uses a Python
process; its Qt/taskbar identity is set, but its executable is not replaced.

Setup performs an offscreen startup check through the branded copy before it
marks a new release current. That check exercises the environment, imports,
Qt application name/logo, real process filename, embedded icon bytes,
FileDescription and Windows app ID. Full-profile installs also check 3D/IFC.
An unsuccessful branding check is reported in setup rather than silently using
an unbranded main process. Windowed standard streams get a writable user log
when no console streams are available.

## Repair, UAC and removal

Rerun the matching installer to recreate missing Desktop/Start links and check
the runtime copy. If UAC used another administrator's credentials, the original
setup process also refreshes links and uninstall registration for the account
that started setup. Per-account registration remains the model; this is not an
all-users deployment. An administrator account used during UAC may also have
its own registration/links. Uninstall cleans matching links visible to its
current account; other-account links may need removal in that account.

Uninstall removes the known Desktop/Start links only when their targets point
inside this installation. Links targeting another installation and personal
files are retained. Existing pinned taskbar items may still reference an old
Python/source launcher. Unpin that old item, launch through the new Desktop
shortcut, and pin the running PY.cad item again if Windows retains old branding.
There is no automatic deletion of user-pinned items or global icon caches.

## Validation limits

Resource formatting, argument forwarding, Qt metadata and installer identity/
integrity logic have portable regression tests. Real Windows COM, modified-PE
execution, redirected folders, UAC, Task Manager and taskbar appearance were not
executed in this Linux environment. The installer-side checks run on the actual
Windows machine; an additional opt-in test is included. Do not equate successful
cross-compilation with successful native Windows acceptance. Packages and the
generated branded copy remain unsigned. No original system Python is modified.

References:
- [Microsoft AppUserModelIDs](https://learn.microsoft.com/en-us/windows/win32/shell/appids)
- [Microsoft Shell links](https://learn.microsoft.com/en-us/windows/win32/shell/links)
- [Python 3.12 on Windows](https://docs.python.org/3.12/using/windows.html)
