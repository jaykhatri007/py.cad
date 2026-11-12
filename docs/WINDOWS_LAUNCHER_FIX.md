# Windows launcher hotfix — 2026-09-27

The previous launcher only attempted `py -3.12` and `py -3.11`. It failed when
neither exact runtime was registered with `py`, including machines with a
usable Python on PATH or at a standard install location. The reported
“No suitable Python runtime found” comes from this runtime-selection step;
without the user's machine log, its exact installed Python inventory is unknown.
It also trusted an existing `.venv` executable without checking whether its
base interpreter was still available.

The replacement launcher:

- Verifies an existing environment by executing its interpreter.
- Searches an optional `PYCAD_PYTHON` path, `py`, PATH, traditional install
  directories, and the default Python Install Manager directory.
- Accepts final 64-bit CPython 3.11–3.14 with venv and ensurepip, excludes
  free-threaded builds, and prefers 3.12 when a new environment is needed.
- Suppresses Python launchers' automatic installation during discovery and
  avoids invoking generic Windows Store PATH aliases.
- Offers a user-confirmed WinGet Python 3.12 installation if none is found.
- Preserves an unusable `.venv` by renaming it before creating its replacement.
- Installs dependencies when the requirements hash changes or imports fail.
- Keeps logs under the user's local app-data directory and pauses on failure.
- Uses quoted paths, disables delayed expansion, and uses pushd/popd for paths
  containing spaces and exclamation marks and for Windows UNC folders.

This is a source-launcher repair, not a bundled Windows executable. No CAD
geometry, UI, saved drawing schema or application feature was changed.
Python 3.12 remains the recommended environment for optional CadQuery.
The widened discovery range does not establish full application compatibility
on 3.13 or 3.14.

## Verification scope

Checks completed for this hotfix:

- 11 runtime-probe scenarios passed on Linux: real interpreter, accepted
  versions, rejected older/future versions, preview, 32-bit, free-threaded
  and non-CPython runtimes. Simulated cases test the predicate, not those OS
  installations.
- Requirements-marker checks passed for missing, matching and changed files.
- Inline Python syntax, batch label references and ASCII/CRLF checks passed.
- The Windows integration test was discovered and skipped on Linux.
- Package CRC, manifest hashes and standalone/packaged launcher equality passed.

Local checks execute the actual inline Python probe and requirements-hash
commands from the batch file, exercising acceptance/rejection and cache
invalidation. The deliverables use ASCII batch content with CRLF endings;
ZIP checks cover CRCs, content hashes, and the standalone launcher's equality
to the packaged copy. Original v15 application results remain in
`TEST_RESULTS.txt`; those results predate this launcher hotfix.

Windows is unavailable in this environment, so cmd.exe parsing, WinGet
installation and Windows Qt loading have **not** been executed locally.
`tests/test_windows_launcher.py` runs under real cmd.exe on Windows and uses a
temporary project. It checks initial setup, preservation of a broken
environment, Python on PATH without the py launcher, special-character paths,
argument forwarding, and an offline
restart with no dependency reinstall. A dedicated Windows CI matrix now runs
that test on Python 3.11–3.14 when the repository workflow is executed.
No CI run is claimed for this download.

## Automation controls

Set `PYCAD_NO_INSTALL=1` to suppress the Python install prompt,
`PYCAD_NO_PAUSE=1` to return immediately on errors, and `PYCAD_SETUP_ONLY=1`
to prepare dependencies without opening the application. Success returns 0;
setup or application failures return 1. `PYCAD_PYTHON` selects a full
interpreter path for new environments; a working `.venv` takes priority.

## Primary references

- Python Windows runtime discovery and Install Manager:
  https://docs.python.org/3/using/windows.html
- Legacy launcher behavior:
  https://docs.python.org/3.11/using/windows.html
- Microsoft WinGet install options:
  https://learn.microsoft.com/en-us/windows/package-manager/winget/install
