//go:build windows

package main

import (
	"context"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func TestWindowsUninstallCommandsQuoteSpecialPaths(t *testing.T) {
	root := `C:\Users\Jay's account\PY.cad & personal\Installation`
	script := uninstallRegistrationScript(root, "16.13.0")
	for _, part := range []string{"CurrentUser.CreateSubKey", "UninstallString", "NoModify", "NoRepair", "--uninstall --root", "Jay''s account", "Uninstall PY.cad.lnk"} {
		if !strings.Contains(script, part) {
			t.Fatal("missing registration", part)
		}
	}
	cleanup := uninstallCleanupScript(root)
	if !strings.Contains(cleanup, "OrdinalIgnoreCase") || strings.Contains(cleanup, "-Recurse") || !strings.Contains(cleanup, "InstallLocation") {
		t.Fatal("unsafe cleanup")
	}
	if uninstallRegistryKey(root) == uninstallRegistryKey(root+"-other") {
		t.Fatal("different roots share uninstall key")
	}
}

func TestNativeWindowUninstallCompletionAndClose(t *testing.T) {
	nativeGUIEnabled(t)
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	state := newState(platform{OS: "windows", Label: "Windows"}, "Uninstall fixture", t.TempDir())
	result := make(chan bool, 1)
	err := runNativeWindowMode(ctx, cancel, state, func(context.Context) error { return nil }, func(hwnd uintptr) {
		go func() {
			ok := nativeTestWait(func() bool { return state.status().Done && nativeButtonText(nativeControl(hwnd, idClose)) == "Close" })
			ok = ok && strings.HasPrefix(nativeButtonText(hwnd), "Uninstall PY.cad")
			result <- ok
			nativePost(hwnd, wmCommand, idClose)
		}()
	}, true)
	if err != nil {
		t.Fatal(err)
	}
	select {
	case ok := <-result:
		if !ok {
			t.Fatal("uninstall UI completion failed")
		}
	case <-time.After(time.Second):
		t.Fatal("uninstall UI fixture did not finish")
	}
}

// Opt in on a real Windows test machine. Registry entries use a unique temp
// installation key; shortcut operations are redirected to an isolated folder.
func TestWindowsUninstallRegistryAndShortcutLifecycle(t *testing.T) {
	if os.Getenv("PYCAD_UNINSTALL_TEST") != "1" {
		t.Skip("requires opt-in Windows registry integration")
	}
	root := t.TempDir()
	programs := t.TempDir()
	redirect := func(s string) string {
		return strings.ReplaceAll(s, "[Environment]::GetFolderPath('Programs')", psQuote(programs))
	}
	cleanup := redirect(uninstallCleanupScript(root))
	defer uninstallPowerShell(context.Background(), cleanup)
	script := redirect(uninstallRegistrationScript(root, "16.13.0"))
	if err := uninstallPowerShell(context.Background(), script); err != nil {
		t.Fatal(err)
	}
	for _, file := range []string{"Uninstall PY.cad.lnk"} {
		if _, err := os.Stat(filepath.Join(programs, file)); err != nil {
			t.Fatal(err)
		}
	}
	check := `$ErrorActionPreference='Stop';$key=[Microsoft.Win32.Registry]::CurrentUser.OpenSubKey(` + psQuote(uninstallRegistryKey(root)) + `);if($null -eq $key){throw 'missing registry entry'};try{if($key.GetValue('DisplayVersion') -ne '16.13.0'){throw 'wrong version'};if($key.GetValue('UninstallString') -notlike '*--uninstall --root*'){throw 'wrong uninstall command'}}finally{$key.Dispose()}`
	if err := uninstallPowerShell(context.Background(), check); err != nil {
		t.Fatal(err)
	}
	if err := uninstallPowerShell(context.Background(), cleanup); err != nil {
		t.Fatal(err)
	}
	if _, err := os.Stat(filepath.Join(programs, "Uninstall PY.cad.lnk")); !os.IsNotExist(err) {
		t.Fatal("shortcut retained", err)
	}
	check = `$key=[Microsoft.Win32.Registry]::CurrentUser.OpenSubKey(` + psQuote(uninstallRegistryKey(root)) + `);if($null -ne $key){$key.Dispose();throw 'uninstall entry retained'}`
	if err := uninstallPowerShell(context.Background(), check); err != nil {
		t.Fatal(err)
	}
}
