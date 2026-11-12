# PyCAD 15.7 — move from Windows to Ubuntu

PyCAD now includes an Ubuntu setup path and a more reliable Linux launcher.
The same source build supports your existing Windows workflow. Drawing features,
the compact ribbon, cursor input, managers and embedded viewports are retained.

## Recommended starting point

The primary target is **Ubuntu 26.04 LTS (Resolute Raccoon), 64-bit x86_64**, with
its default Python 3.14. Canonical's Ubuntu 26.04 package listings provide
`python3-venv`, `python3.14-venv` and the required XCB runtime libraries. The
core launcher accepts 64-bit CPython 3.11–3.14 and prefers 3.14 on 26.04. Use
Python 3.12 for the validated optional CadQuery 2.7 solid-export stack. ARM and other Linux
distributions need separate validation. Wine, Windows Python and Docker are not
required for the desktop application.

## Before leaving Windows

1. Save and close PyCAD. Keep a backup of the folders containing your actual
   `.pycad`, `.pycadt`, DXF/DWG drawings, backups and reference files. Drawings
   may be outside the application folder; copying only PyCAD is not a backup.
2. Preserve linked DXF folders and their structure. `ETRANSMIT` can package a
   native drawing and its direct DXF references into a portable ZIP. Nested
   external dependency collection is still limited; retain your source folders.
3. Native files embed PDF/image underlays, so those references travel with the
   drawing. Keep original source PDFs/images as project records if needed.
4. If you have unsaved crash-recovery data, recover and save it first. The Windows
   recovery file normally lives at `%USERPROFILE%\.pycad\recovery.pycad`.
5. Do not transfer `.venv`, Windows executables or a copied Linux `.venv-linux`
   as the runtime. Python environments must be recreated on the target machine.

No drawing-format conversion is necessary. 15.7 still reads/writes native
schema 6, as 15.6 does. Units, layers, dimension styles, constraints, layouts,
underlays and saved extrusion data remain in the drawing. Windows registry-based
UI preferences, recent paths and command aliases do not automatically migrate;
configure them again on Ubuntu. Fonts and physical printer setups are OS-specific.

## Install and launch

Extract the **full ZIP** to a writable location, for example
`/home/YOUR-USER/Applications/PyCAD-v15`. In Ubuntu Files, open that folder,
right-click empty space and choose **Open in Terminal**. Run:

```bash
bash setup_ubuntu.sh
bash start.sh
```

Run those commands as your normal user. Setup requests sudo only for apt.
It installs Python virtual-environment support and Qt's runtime/display libraries,
creates **.venv-linux**, installs the core Python dependencies, and adds a
**PyCAD** entry to Applications. First setup needs Internet access. It does not
replace the operating system's Python or use `sudo pip`.

No `chmod` is needed when invoking a script with `bash`. Keep the extracted folder
in place: the Applications entry points to it. The entry opens a terminal alongside
the app so startup messages are available. It does not change default file associations.

On subsequent launches, a matching requirements fingerprint and successful import
checks allow startup without contacting the package index. Changed requirements
or missing/broken dependencies trigger setup. Invalid or moved Linux environments
are renamed to `.venv-linux-backup-TIMESTAMP`; no existing environment is erased.
The Windows `.venv` is kept separate and untouched.

To install optional CadQuery solid export using the selected Python:

```bash
bash start.sh --setup-only --with-3d
```

The embedded software 3D inspection/orbit workspace is available without CadQuery.
CadQuery supplies the existing STEP/STL solid-generation workflows. Failed optional
installation leaves the core environment in place; read the log and use Python 3.12.

## Open drawings and repair references

Open `.pycad` files through File → Open, or pass a path:

```bash
bash start.sh "/home/YOUR-USER/Documents/CAD/House plan.pycad"
```

Relative arguments resolve from the terminal's original directory, even though
the application runs from its own folder. Spaces and Unicode paths are supported.

Relative reference paths saved with Windows backslashes now resolve on Linux.
Absolute Windows paths such as `C:\Projects\site.dxf` cannot identify an Ubuntu
file. PyCAD reports them explicitly instead of guessing a substitute:

1. Run **XREF**, select the missing reference, and click **Relink selected…**.
2. Choose the copied DXF in its Ubuntu location.
3. Review the reload result and save the native drawing.

Relink loads and validates the source before applying changes. It preserves the
reference's unit-conversion scale, updates geometry/layers, and is one Undo step.
An invalid source leaves cached geometry and the old path intact. Saved drawings
store the selected path relative to the drawing where possible. Unsaved drawings
must use an absolute path until they have a location. Preserve relative folder
structure when moving drawings; Ubuntu filenames are case-sensitive.

## Display and graphics checks

Run the built-in check after installation:

```bash
bash start.sh --check
```

It opens/closes a real PyCAD window in a temporary profile, checks native save/
reopen, PDF support, embedded four-view navigation and orbit, and reports whether
an OpenGL context can be created. It does not edit your drawings or delete your
normal recovery file. Context creation alone does not validate a physical GPU.

The default launcher uses `xcb` when `DISPLAY` exists: X11 on a classic session,
or XWayland on a Wayland session. Explicit `QT_QPA_PLATFORM` is respected unless
you pass an overriding launcher option. Troubleshooting commands:

```bash
bash start.sh --xcb
bash start.sh --xcb --software-rendering
bash start.sh --wayland
bash start.sh --diagnose
```

`--software-rendering` requests Mesa/Qt software OpenGL. The ordinary drafting
canvas already uses QPainter, and the embedded model viewer uses CPU projection.
Native Wayland is an opt-in path here and was not validated. If no graphical
display exists, the launcher explains that it needs a desktop session. Use
`--setup-only` to install from a headless terminal. Qt offscreen is for testing,
not for an interactive user workspace.

## Setup options and local data

| Command/setting | Purpose |
| --- | --- |
| `bash setup_ubuntu.sh --with-3d` | Core setup plus optional CadQuery |
| `bash setup_ubuntu.sh --no-desktop` | Skip the Applications shortcut |
| `bash setup_ubuntu.sh --no-system-packages` | Use already-installed OS libraries; no apt step |
| `sudo bash setup_ubuntu.sh --system-only --yes` | Administrator/CI installs only OS packages; no user environment or shortcut |
| `bash start.sh --setup-only --install-desktop` | Prepare/update the environment and repair the Applications entry after moving the app folder |
| `bash start.sh --diagnose` | Read-only environment/import report, without installing packages |
| `PYCAD_PYTHON=/usr/bin/python3.12 bash start.sh --setup-only` | Choose the bootstrap interpreter for a new Linux environment |
| `PYCAD_DATA_DIR=/absolute/profile/path bash start.sh` | Explicit isolated settings, recovery and logs profile |

The interpreter override does not replace a healthy existing environment. To
deliberately change interpreter, close PyCAD and rename `.venv-linux` as a backup,
then run setup with the desired override. Environment names are case-sensitive.

Default application/recovery logs are in `~/.pycad/logs`; Linux startup logs are
`startup-linux-*.log`, and the main app log is `pycad.log`. Default Ubuntu QSettings
preferences normally live under `~/.config/PyCAD`. Do not delete the recovery
file while troubleshooting. The new optional `PYCAD_DATA_DIR` keeps all three
kinds of data in a chosen profile and stores preferences in `settings.ini`.

To remove the Applications shortcut, delete
`~/.local/share/applications/pycad-local.desktop` (or its equivalent below your
custom `XDG_DATA_HOME`). This does not remove drawings, the application or data.

## File formats, fonts and remaining limits

Native files, DXF, PDFs and image underlays use the existing cross-platform code.
PDF/image underlays remain rendered references rather than editable PDF geometry.
Windows-only fonts can be substituted on Ubuntu, affecting text and plot metrics;
use appropriately licensed fonts available on both systems and verify key sheets.

DWG needs a separately installed **Linux ODA File Converter**; a Windows `.exe`
does not transfer this dependency. The ezdxf add-on finds `ODAFileConverter` on
PATH or its configured `unix_exec_path`. Follow its official documentation for
an AppImage/custom path. The converter is not bundled or tested in this release.
Additional formats and advanced CAD features retain their earlier limitations.

This is a full Python source build, not an AppImage, .deb or prebuilt executable.
The Windows launcher remains included and unchanged. Native schema 6 is unchanged;
15.6 and 15.7 drawings can be used on either platform within the implemented scope.

## Verification

Ubuntu 24.04.3 x86_64; Python 3.12.14; PyQt6 6.11.0/Qt 6.11.2.
The existing QA environment passed **366 tests**, with the Windows test and
opt-in fresh-install test skipped there. The fresh Linux installation test ran
separately and passed: broken-environment backup, untouched Windows environment,
Unicode/space paths, absolute file-argument routing and offline restart.

Actual `xcb` startup in Xvfb passed native/PDF/four-view/orbit checks and created
an OpenGL context. The desktop entry passed `desktop-file-validate`; an actual Qt
screenshot was reviewed. The system dependency phase was executed successfully.
See `TEST_RESULTS.txt` for the final fresh-environment regression result as well.

Not verified: a native Ubuntu 26.04 desktop run (the package sources and Python
3.14 assumptions were checked, while testing occurred on Ubuntu 24.04), native
Wayland, ARM, physical GPU/drivers, printers,
ODA DWG conversion or a Windows rerun. Xvfb is a virtual X11 display, not a full
GNOME desktop session. The included GitHub Actions job is configured for future
Ubuntu launcher checks; it was not run on a remote repository in this session.

## References used for the migration

- [Qt 6.11 Linux runtime dependencies](https://doc.qt.io/qt-6.11/linux-requirements.html)
- [Python virtual environments and portability](https://docs.python.org/3/library/venv.html)
- [Freedesktop application launcher quoting](https://specifications.freedesktop.org/desktop-entry/latest/exec-variables.html)
- [ezdxf ODA converter support on Linux](https://ezdxf.readthedocs.io/en/stable/addons/odafc.html)
