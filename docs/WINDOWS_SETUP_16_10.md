# Windows setup — PY.cad 16.10

Double-click **PY.cad-Setup-16.10.0-Windows-x64.exe**. In the full source ZIP,
**Setup-Windows.cmd** opens the same EXE and immediately exits its launcher.
Normal Windows setup opens a native Win32 frame: it does not start a browser,
WebView or local web progress server and does not require Python beforehand.

The frame shows the approved logo, version/OS, destination, six coarse stages,
elapsed time and recent setup notes. The bar shows stages, not a measured
percentage of downloaded bytes. Work runs in the background so the UI can
continue responding during dependency downloads and checks.

- **Open log** opens the current setup log in Windows Notepad. Full dependency
  command output is in that log; recent stage notes/errors appear in the frame.
- **Licenses** opens a second native text window with the retained project and
  upstream documentation. Closing it leaves setup running.
- A failure stays visible. **Retry** starts one new attempt after the previous
  attempt has stopped and released its installation lock. The new attempt has
  a new log. Existing download caches remain available.
- During work, **Cancel** or the title-bar X asks whether to stop. Confirmation
  cancels the worker and waits for it to finish its cleanup before closing.
  Drawings are retained. A valid installation already committed remains usable.
- On success, the action changes to **Close**. Clicking it (or X) destroys the
  frame, ends its message loop and exits the setup process. It does not close
  the independently launched PY.cad application. The completed frame stays open
  until you close it; it does not wait for a web page or a 15-minute web timeout.

The installer retains its existing OS/dependency checks, private Python setup,
Microsoft runtime repair, source/notice retention and application launch.
Internet is needed for the first dependency downloads. Windows may still show
its own UAC authorization or Microsoft runtime installation dialog. Cancelling
PY.cad setup does not promise to interrupt a separate elevated Microsoft installer.
Packages remain unsigned; SmartScreen or other OS security prompts may appear.

## Optional console diagnostics

**Setup-Windows-Console.cmd** retains the earlier visible console logging path.
It explicitly passes **--no-browser**, which skips the native frame, prints
progress and exits with the installation status. This is an opt-in diagnostic
route, not the normal installation launcher. The normal .cmd needs only the
matching EXE; fully extract the downloaded ZIP before opening it.

Linux/macOS keep their existing installation interfaces in this release.
The drawing application's hatch, linetype, graphics and drafting features are
unchanged apart from the displayed version.

## Validation scope

Portable Go tests exercise routing, progress presentation, one-at-a-time workers,
retry, completion and cancellation cleanup. Windows-specific GUI acceptance
cases compile with the executable and cover completion/Close, license-viewer
closure, retry and confirmed cancellation, using simulated installation jobs.
They require an actual Windows GUI session to execute. Set PYCAD_NATIVE_UI_TEST=1
and run `go test -run TestNativeWindow -v` from installer/ with a supported Go
compiler on Windows. These are UI fixture jobs, not real dependency installation.

This Linux build environment cannot execute the Windows GUI tests: its Wine
attempt was blocked before starting the EXE because Unix sockets are unavailable.
Cross-build and model tests do not establish native Windows 10/11 UI or actual
installation acceptance. See VALIDATION_16_10.txt for the exact completed checks.
