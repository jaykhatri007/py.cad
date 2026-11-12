//go:build windows

package main

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"syscall"
	"time"
	"unsafe"
)

type destinationWindow struct {
	hwnd, edit, instance uintptr
	result               string
}

var destinationUI *destinationWindow
var destinationCallback = syscall.NewCallback(destinationProc)
var browseCallback = syscall.NewCallback(func(hwnd uintptr, message uint32, w, l uintptr) uintptr {
	if message == 1 && destinationUI != nil {
		sendWindowMessage.Call(hwnd, 0x0467, 1, uintptr(unsafe.Pointer(winText(destinationText(destinationUI.edit)))))
	}
	return 0
})

func destinationText(hwnd uintptr) string {
	n, _, _ := setupUser.NewProc("GetWindowTextLengthW").Call(hwnd)
	if n > 32760 {
		return ""
	}
	b := make([]uint16, int(n)+1)
	setupUser.NewProc("GetWindowTextW").Call(hwnd, uintptr(unsafe.Pointer(&b[0])), uintptr(len(b)))
	return syscall.UTF16ToString(b)
}

func validateDestination(root string) error {
	if !filepath.IsAbs(root) || strings.ContainsAny(root, "\r\n\t\x00") || len(root) > 240 {
		return fmt.Errorf("Choose an absolute local installation folder (up to 240 characters)")
	}
	clean := filepath.Clean(root)
	if filepath.VolumeName(clean) == "" || strings.HasPrefix(clean, `\\`) || clean == filepath.VolumeName(clean)+`\` {
		return fmt.Errorf("Choose a PY.cad subfolder on a local drive, not a drive root or network share")
	}
	for _, base := range []string{os.Getenv("ProgramFiles"), os.Getenv("ProgramW6432"), os.Getenv("WINDIR")} {
		if base != "" && strings.EqualFold(clean, filepath.Clean(base)) {
			return fmt.Errorf("Choose a PY.cad subfolder rather than a system folder")
		}
	}
	return nil
}

func browseDestination(owner uintptr) {
	shell := syscall.NewLazyDLL("shell32.dll")
	type browseInfo struct {
		Owner, Root, Display, Title uintptr
		Flags                       uint32
		Callback, Param             uintptr
		Image                       int32
	}
	buffer := make([]uint16, 32768)
	title := winText("Choose a parent folder. Setup will add a PY.cad subfolder.")
	info := browseInfo{Owner: owner, Display: uintptr(unsafe.Pointer(&buffer[0])), Title: uintptr(unsafe.Pointer(title)), Flags: 0x51, Callback: browseCallback}
	pidl, _, _ := shell.NewProc("SHBrowseForFolderW").Call(uintptr(unsafe.Pointer(&info)))
	if pidl != 0 {
		defer syscall.NewLazyDLL("ole32.dll").NewProc("CoTaskMemFree").Call(pidl)
		ok, _, _ := shell.NewProc("SHGetPathFromIDListW").Call(pidl, uintptr(unsafe.Pointer(&buffer[0])))
		if ok != 0 {
			winSetText(destinationUI.edit, filepath.Join(syscall.UTF16ToString(buffer), "PY.cad"))
		}
	}
	runtime.KeepAlive(title)
}

func destinationProc(hwnd uintptr, message uint32, w, l uintptr) uintptr {
	u := destinationUI
	if u != nil {
		switch message {
		case wmCommand:
			switch int(w & 0xffff) {
			case 201:
				browseDestination(hwnd)
				return 0
			case 202:
				root := strings.TrimSpace(destinationText(u.edit))
				if e := validateDestination(root); e != nil {
					notify("Installation folder", e.Error())
					return 0
				}
				u.result = filepath.Clean(root)
				destroyWindow.Call(hwnd)
				return 0
			case idClose:
				destroyWindow.Call(hwnd)
				return 0
			}
		case wmClose:
			destroyWindow.Call(hwnd)
			return 0
		case wmDestroy:
			setupUser.NewProc("PostQuitMessage").Call(0)
			return 0
		}
	}
	v, _, _ := defaultWindow.Call(hwnd, uintptr(message), w, l)
	return v
}

func chooseDestination(root string) (string, error) {
	runtime.LockOSThread()
	defer runtime.UnlockOSThread()
	ole := syscall.NewLazyDLL("ole32.dll")
	hr, _, _ := ole.NewProc("CoInitializeEx").Call(0, 2)
	if int32(hr) < 0 {
		return "", fmt.Errorf("Initialize folder chooser: 0x%x", hr)
	}
	defer ole.NewProc("CoUninitialize").Call()
	u := &destinationWindow{}
	destinationUI = u
	defer func() { destinationUI = nil }()
	u.instance, _, _ = setupKernel.NewProc("GetModuleHandleW").Call(0)
	cursor, _, _ := setupUser.NewProc("LoadCursorW").Call(0, 32512)
	class := winText("PYCAD_DESTINATION")
	wc := setupWindowClass{Procedure: destinationCallback, Instance: u.instance, Cursor: cursor, Background: 6, ClassName: class}
	wc.Size = uint32(unsafe.Sizeof(wc))
	atom, _, e := setupUser.NewProc("RegisterClassExW").Call(uintptr(unsafe.Pointer(&wc)))
	if atom == 0 {
		return "", fmt.Errorf("Register destination window: %w", e)
	}
	defer setupUser.NewProc("UnregisterClassW").Call(uintptr(unsafe.Pointer(class)), u.instance)
	u.hwnd, _, e = createWindow.Call(0, uintptr(unsafe.Pointer(class)), uintptr(unsafe.Pointer(winText("PY.cad — Installation folder"))), 0x00CA0000, 0x80000000, 0x80000000, 720, 250, 0, 0, u.instance, 0)
	if u.hwnd == 0 {
		return "", fmt.Errorf("Create destination window: %w", e)
	}
	font, _, _ := setupGDI.NewProc("GetStockObject").Call(17)
	add := func(class, text string, style uint32, id, x, y, w, h int) uintptr {
		v, _, _ := createWindow.Call(0, uintptr(unsafe.Pointer(winText(class))), uintptr(unsafe.Pointer(winText(text))), uintptr(style|wsVisible|wsChild), uintptr(x), uintptr(y), uintptr(w), uintptr(h), u.hwnd, uintptr(id), u.instance, 0)
		sendWindowMessage.Call(v, 0x30, font, 1)
		return v
	}
	add("STATIC", "Choose where to install PY.cad", 0, 0, 22, 18, 650, 24)
	add("STATIC", "Program Files may require Windows administrator approval (UAC).", 0, 0, 22, 48, 650, 24)
	u.edit = add("EDIT", root, 0x0080|0x00800000|wsTabStop, 200, 22, 86, 550, 28)
	add("BUTTON", "Browse…", wsTabStop, 201, 582, 86, 100, 28)
	add("STATIC", "Type an exact destination, or Browse for a parent folder.", 0, 0, 22, 124, 650, 24)
	add("BUTTON", "Install", wsTabStop|1, 202, 466, 164, 104, 30)
	add("BUTTON", "Cancel", wsTabStop, idClose, 582, 164, 100, 30)
	setupUser.NewProc("ShowWindow").Call(u.hwnd, 5)
	setupUser.NewProc("SetFocus").Call(u.edit)
	var msg setupMessage
	for {
		v, _, e := setupUser.NewProc("GetMessageW").Call(uintptr(unsafe.Pointer(&msg)), 0, 0, 0)
		if int32(v) == -1 {
			return "", fmt.Errorf("Destination message loop: %w", e)
		}
		if v == 0 {
			break
		}
		handled, _, _ := setupUser.NewProc("IsDialogMessageW").Call(u.hwnd, uintptr(unsafe.Pointer(&msg)))
		if handled == 0 {
			setupUser.NewProc("TranslateMessage").Call(uintptr(unsafe.Pointer(&msg)))
			setupUser.NewProc("DispatchMessageW").Call(uintptr(unsafe.Pointer(&msg)))
		}
	}
	return u.result, nil
}

func elevated() bool {
	v, _, _ := syscall.NewLazyDLL("shell32.dll").NewProc("IsUserAnAdmin").Call()
	return v != 0
}

func destinationWritable(root string) bool {
	dir := root
	for {
		if info, e := os.Stat(dir); e == nil && info.IsDir() {
			break
		}
		parent := filepath.Dir(dir)
		if parent == dir {
			return false
		}
		dir = parent
	}
	f, e := os.CreateTemp(dir, ".pycad-access-")
	if e != nil {
		return false
	}
	name := f.Name()
	f.Close()
	os.Remove(name)
	return true
}

func runElevated(args []string) error {
	runtime.LockOSThread()
	defer runtime.UnlockOSThread()
	ole := syscall.NewLazyDLL("ole32.dll")
	hr, _, _ := ole.NewProc("CoInitializeEx").Call(0, 2)
	if int32(hr) < 0 {
		return fmt.Errorf("Initialize Windows elevation: 0x%x", hr)
	}
	defer ole.NewProc("CoUninitialize").Call()
	self, e := os.Executable()
	if e != nil {
		return e
	}
	parts := make([]string, len(args))
	for i, a := range args {
		parts[i] = windowsQuote(a)
	}
	verb, file, parameters := winText("runas"), winText(self), winText(strings.Join(parts, " "))
	type shellInfo struct {
		Size, Mask                        uint32
		Window                            uintptr
		Verb, File, Parameters, Directory *uint16
		Show                              int32
		Instance, IDList                  uintptr
		Class                             *uint16
		ClassKey                          uintptr
		HotKey                            uint32
		Icon, Process                     uintptr
	}
	info := shellInfo{Mask: 0x140, Verb: verb, File: file, Parameters: parameters, Show: 1}
	info.Size = uint32(unsafe.Sizeof(info))
	ok, _, err := syscall.NewLazyDLL("shell32.dll").NewProc("ShellExecuteExW").Call(uintptr(unsafe.Pointer(&info)))
	if ok == 0 {
		return fmt.Errorf("Windows administrator approval was cancelled or unavailable: %w", err)
	}
	if info.Process == 0 {
		return fmt.Errorf("Windows did not return an installer process")
	}
	defer setupKernel.NewProc("CloseHandle").Call(info.Process)
	wait, _, _ := setupKernel.NewProc("WaitForSingleObject").Call(info.Process, 0xffffffff)
	if wait != 0 {
		return fmt.Errorf("Could not wait for elevated setup")
	}
	var code uint32
	setupKernel.NewProc("GetExitCodeProcess").Call(info.Process, uintptr(unsafe.Pointer(&code)))
	if code != 0 {
		return fmt.Errorf("Elevated setup did not complete (exit %d)", code)
	}
	runtime.KeepAlive(verb)
	runtime.KeepAlive(file)
	runtime.KeepAlive(parameters)
	return nil
}

func prepareDestination(o *options, uninstall, worker bool) (bool, error) {
	if o.Diagnose {
		return false, nil
	}
	if filepath.Base(os.Args[0]) == uninstallExeName {
		uninstall = true
	}
	if !uninstall && !worker && !o.NoBrowser && !o.DestinationConfirmed && !o.Launch {
		root, e := chooseDestination(o.Root)
		if e != nil {
			return true, e
		}
		if root == "" {
			return true, nil
		}
		o.Root = root
		o.DestinationConfirmed = true
	}
	if e := validateDestination(o.Root); e != nil {
		return true, e
	}
	if elevated() || destinationWritable(o.Root) {
		return false, nil
	}
	args := []string{"--destination-confirmed", "--root", o.Root, "--no-launch"}
	if uninstall || worker {
		args = append(args, "--uninstall")
	}
	if o.NoBrowser {
		args = append(args, "--no-browser")
	}
	if o.NoSystem {
		args = append(args, "--no-system-packages")
	}
	if o.CoreOnly {
		args = append(args, "--core-only")
	}
	if e := runElevated(args); e != nil {
		return true, e
	}
	// Refresh per-user shell links for the account that started Setup, even
	// when UAC used credentials belonging to a different administrator.
	if !uninstall && !worker {
		receipt, e := loadReceipt(o.Root)
		if e != nil {
			return true, e
		}
		self, e := os.Executable()
		if e != nil {
			return true, e
		}
		launcher, e := stageWindowsLauncher(o.Root, self)
		if e != nil {
			return true, e
		}
		release := filepath.Join(o.Root, "releases", receipt.Release)
		ctx, cancel := context.WithTimeout(context.Background(), 90*time.Second)
		defer cancel()
		if e = runWindowsShortcuts(ctx, o.Root, release, launcher, filepath.Join(o.Root, "icons")); e != nil {
			return true, e
		}
		if e = uninstallPowerShell(ctx, uninstallRegistrationScript(o.Root, receipt.Version)); e != nil {
			return true, e
		}
		if !o.NoLaunch {
			p, e := detect("windows", "amd64")
			if e != nil {
				return true, e
			}
			return true, launchCurrent(o.Root, p, nil)
		}
	}
	return true, nil
}
