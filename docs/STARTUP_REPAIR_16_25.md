# Startup and dependency repair · 16.25

## Ubuntu 26.04 / Python 3.14

The reported source-start failure installed PyQt6 6.12.0 / Qt 6.12.0 from broad version ranges, then failed importing QtPdf. Installing apt runtime libraries cannot supply a Python binding module absent from that wheel. Native setup already used a pinned core, but start.sh's Python launcher used a different requirements file. This inconsistency is repaired.

Source/manual requirements now delegate to requirements-install-core.txt, including the existing constraints. The launcher installs and checks PyQt6 6.11.0, PyQt6-Qt6 6.11.2, ezdxf 1.4.4 and NumPy 2.3.5. The required QtPdf, QtSvg, print and OpenGL binding imports must succeed. The setup stamp tracks both core requirements and their constraint file, with a new schema invalidating old stamps. A failed import check forces replacement of installed core wheels instead of accepting a broken or mismatched "already satisfied" environment.

Extract the complete 16.25 ZIP, open a terminal inside PY.cad, then run:

```bash
bash start.sh
```

For a prepare-and-diagnose repair without opening the drawing window:

```bash
bash Repair-Ubuntu.sh
```

No sudo pip is used. This works with Ubuntu's Python 3.14 for core drafting; optional CadQuery still recommends the managed Python 3.12 profile. A healthy stamped environment starts offline without reinstalling packages. Existing moved/broken environment folders retain the backup behavior. For actual missing Linux system libraries, setup_ubuntu.sh remains the system-dependency installer. A missing QtPdf binding is handled by the pinned Python-package repair.

## Windows dependency setup

The native frame installer and managed Python 3.12 are retained. Core requirements remain pinned; full setup still requests CadQuery and IfcOpenShell. The complete dependency list resolves to Windows x64 wheels. This metadata check does not execute their DLLs or reproduce a particular Windows machine's error.

The installation engine now:

- Uses a 300-second HTTP idle timeout and five HTTP retries, with four concurrent downloads.
- Uses copy-mode package installation on Windows, avoiding dependence on hard links between the download cache and destination.
- Retries a temporary package-network failure once at the command level, using the verified cache. The wait is cancellable; persistent version conflicts, permissions and disk-space failures are not retried blindly.
- Shows bounded live command/package output in the native setup window while downloads/installations run, and includes the failed command's error tail and full log location on failure.
- Retains the existing Retry / Open log / Close flow, Windows system certificate verification, binary-wheel-only package policy and destination selection.

A missing package wheel, persistent network/certificate/permission problem or failed runtime test still stops safely. Setup does not label an incomplete full installation successful, silently remove optional features, disable TLS verification or switch the active receipt before checks pass. A previous committed installation remains available on dependency failure. Microsoft runtime repair and its separate authorization flow are unchanged.

If a Windows dependency error persists, open **Open log** in setup and provide its final error/traceback. Without that log the exact cause on the user's machine is unverified; these changes address download/copy reliability and make the actual cause visible. Native Windows execution remains unverified in this Linux build environment.

Official uv configuration reference (the bundled uv version is unchanged):
https://docs.astral.sh/uv/reference/environment/
https://docs.astral.sh/uv/reference/cli/

All DWG, hatch, selection, graphics policy, UI and uninstaller changes from 16.24 are retained.
