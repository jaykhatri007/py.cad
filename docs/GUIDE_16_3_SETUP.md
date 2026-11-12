# PyCAD 16.3 — automatic setup

PyCAD now has a native setup engine that detects the running OS and CPU,
prepares its own Python environment, installs dependencies, adds an application
shortcut and opens PyCAD. The previous drawing, BOQ, building and chat features
remain in this release. No Python, pip, Go, Homebrew or terminal commands are
needed for the normal native setup path.

## Which file to open

| Computer | Setup file | Target |
|---|---|---|
| Ubuntu / other desktop Linux | `PyCAD-Setup-16.3.0-Linux-x64.run` | Intel/AMD x64, glibc 2.34+; Ubuntu 22.04/24.04/26.04 are intended targets. |
| Windows | `PyCAD-Setup-16.3.0-Windows-x64.exe` | Windows 10/11 on Intel/AMD x64. |
| Mac | `PyCAD-Setup-16.3.0-macOS-Universal.zip` | macOS 13+; contains one app supporting Intel and Apple Silicon. |

Open the Windows EXE directly. On Mac, extract the ZIP and open **PyCAD Setup.app**.
On Linux, open the `.run` file as a program. If your file manager requires it,
first enable **Allow executing file as program** in its Properties. Some Linux
file managers require **Run as a program** or a terminal action; that first-run
file permission cannot be silently granted by a downloaded file itself.

Once Setup opens, installation starts automatically. A small local progress page
opens in your default browser; it shows the detected system and each step. It
is an installer interface on your own computer, not an online account or website.
You can cancel, save its diagnostic log or retry after an error. Leave the
computer connected while components download. PyCAD launches when checks pass.
Afterward, open **PyCAD** from the Start menu, Applications menu or
`~/Applications/PyCAD.app`. Close the setup tab with **Finish**.

The full build ZIP also contains these files under `PyCAD-v15/installer/packages`.
The source code and previous launchers are included. For most users, the separate
native setup file is the easiest download; extracting the source ZIP is optional.

## What happens automatically

1. **Detect:** identify Windows/macOS/Linux, 64-bit CPU, desktop availability and
   relevant platform requirements. Unsupported systems receive an explanation.
2. **Prepare:** create a private installation folder for the signed-in user and
   unpack the embedded complete application source. Your existing extracted
   source build is not overwritten.
3. **Python:** obtain a checksum-verified, pinned uv runtime bootstrap and use it
   to install a managed **CPython 3.12** if missing. The system Python is untouched;
   no global PATH changes, system pip or Homebrew are used.
4. **Dependencies:** install the tested Qt, DXF and NumPy versions, then CadQuery
   and IfcOpenShell for live 3D and IFC. Prebuilt wheels are required, avoiding an
   unexpected compiler/toolchain build on the user's machine.
5. **Check:** verify imports and pinned core versions, a real kernel solid and
   IFC creation. Check desktop libraries and open/close a real PyCAD window in
   private temporary preferences before selecting the new installation.
6. **Finish:** add the user application shortcut, select the checked release and
   launch it. Later runs verify the existing environment and reuse it if healthy.
   A broken environment is repaired in a separate release directory.

A usable system Python is not required. Using a private 3.12 runtime also avoids
the optional CAD kernel depending on Ubuntu's newer system Python version.
All Python packages are confined to PyCAD's environment. The bootstrap archive
is verified against its embedded SHA-256 before execution. Python/package
transfers use the runtime manager's HTTPS downloads and package verification.

First setup requires internet access to GitHub releases, Python's managed
runtime download host, PyPI/package files and, when necessary, your OS package
repositories or Microsoft. CAD/Qt packages are substantial; allow several minutes
and a few gigabytes of space. Downloads and package files are cached for retry.
This is an **online installer**, not an offline bundle of every dependency.

## OS desktop dependencies and security prompts

On Linux, Setup checks actual Qt/XCB libraries. Missing runtime libraries are
mapped to apt, dnf, pacman or zypper packages. On a recognized desktop distribution,
`pkexec` requests normal administrator authorization and the OS package manager
installs them. No password is collected by PyCAD. Repository refresh/package
installation can require OS authorization. If the distribution or authorization
helper is unavailable, Setup lists what is missing and stops so it can be fixed
before retrying. Linux package-manager plans other than Ubuntu/Debian have unit
coverage, not real distribution installation tests.

On Windows, if dependency imports fail, Setup can download Microsoft's current
Visual C++ runtime, verify its Authenticode signature and run its installer.
Windows may request administrator approval or a restart. No antivirus or system
security setting is disabled. On Mac, Python and Qt come through the private
runtime and wheels, with no global package manager installation.

These setup files have **not** been signed with a Windows publisher certificate
or Apple Developer ID/notarization account. Your OS may require you to approve
opening them. For macOS, follow Apple's normal Privacy & Security controls for
an app you trust. A fully silent first launch on every OS is not promised:
file execution permission, Gatekeeper/SmartScreen and administrator authorization
are controlled by the operating system. A single native executable cannot serve
as the same clickable program format on all three OS families. This release
uses one shared engine and the appropriate native setup file for each OS.

## Existing drawings, upgrades and failures

Setup uses a separate per-user installation. It does not import or delete your
old project folders. Open your existing `.pycad` drawings normally. Drawings save
with the same schema 12 used by 16.2; prior schemas 1–11 still load. Keep project
files in your own Documents/project folders rather than inside installation data.

A new release is installed into a new directory. The current-release pointer
changes only after required checks pass, so an unsuccessful package download or
upgrade leaves the previous selected installation intact. Cancelling can leave
an incomplete release and cached downloads; it does not remove existing drawings.
OS libraries installed by the package manager can remain after a cancelled setup.
Failed release folders and older releases are preserved for diagnosis rather
than automatically deleted. Installation logs do not contain AI keys.

Use **Save log** if setup stops. **Retry setup** repeats the checks and uses the
cache. If the setup window was closed, open the same setup file again. Once
installed, a healthy app launch does not need an internet connection. Online AI
mode still depends on the service you configure; offline drafting chat needs none.
Since 16.13, Windows setup registers PY.cad in Installed apps and adds an
Uninstall PY.cad Start-menu shortcut. See WINDOWS_UNINSTALL_16_13.md. Earlier
versions had no registered uninstaller. User drawings and settings are retained;
preexisting files from older builds are not automatically claimed for removal.


## Locations and advanced options

| OS | Managed application/runtime data | Shortcut |
|---|---|---|
| Windows | `%LOCALAPPDATA%\PyCAD\Installation` | Current user's Start menu → PyCAD |
| macOS | `~/Library/Application Support/PyCAD/Installation` | `~/Applications/PyCAD.app` |
| Linux | `$XDG_DATA_HOME/pycad/installation`, default `~/.local/share/pycad/installation` | Applications → PyCAD |

Logs are in the installation folder's `logs` directory. Endpoint/model settings
and project preferences remain with the application's existing per-user settings.
`current.json` selects a checked release, and each release has its own `env` and
`app/PyCAD-v15` source folder. These locations are implementation details for
troubleshooting, not folders a normal user needs to manage.

The native executable supports advanced diagnostic/testing options:

```text
--diagnose              Report OS, CPU, version and intended folder; no install.
--root PATH             Use another private installation folder.
--core-only             Explicit 2D/BOQ/chat profile without CadQuery/IFC.
--no-browser            Print progress endpoint and exit when setup finishes.
--no-launch             Install/check packages without launching the desktop app.
--no-system-packages    Report missing OS libraries without changing them.
--launch                Launch the selected installation, or open Setup to repair.
```

These flags are optional. Normal setup requires no commands. Linux ARM64 and
Windows ARM64 are **not qualified full-build targets** for this release. The Mac
Universal app's Apple Silicon support is distinct from Linux/Windows ARM support.
A 32-bit OS, musl/Alpine Linux or an unsupported legacy OS cannot be converted
into a supported system by downloading Python dependencies.

## What was tested

A fresh private Linux installation downloaded its own Python, installed the full
CAD/3D/IFC profile and created its application entry. Missing Qt library detection,
retry/caching, checked source extraction, download checksum failures, conflicting
setup locks, failed-upgrade preservation, progress-page access controls, native
package envelopes and core CAD regressions are covered by the release checks.
Windows x64, Intel Mac and Apple Silicon Mac dependency resolution was checked
against compatible binary wheels and their native setup files were cross-built.

Actual Windows/macOS execution, code signing/notarization, native Ubuntu 26.04,
real administrator dialogs on other distributions and GPU/printer operation were
not tested here. See `docs/VALIDATION_16_3.txt` for the exact final results.
See `docs/GUIDE_16_2.md` for the nine building additions, BOQ and drafting chat.

## Source and rebuilding

All installer source is under `installer/`: the Go engine, local progress page,
runtime URL/hash manifest, tests and Python native-package builder. Go uses only
its standard library. With Go 1.23+ and Python available to the developer:

```bash
python installer/build.py --output ../setup-build
cd installer
go test ./...
```

Go 1.27.2 was used for this release. The builder emits a Windows GUI EXE, a
Mac Universal app ZIP and a Linux self-extracting executable. Rebuilds require
application source, `installer/runtime-sources.json` and Go; users of the final
setup files need none of those tools. Developer ID signing/notarization and
Windows publisher signing are separate release steps requiring the owner's
certificates. The builder does not bypass them or invent publisher identity.

Primary implementation references:

- [uv: installing/managing Python](https://docs.astral.sh/uv/guides/install-python/)
- [Qt: Linux platform dependencies](https://doc.qt.io/qt-6/linux-requirements.html)
- [Microsoft: Visual C++ runtime](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist)
- [Apple: safely open apps](https://support.apple.com/en-us/102445)
