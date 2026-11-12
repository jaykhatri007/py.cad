package main

import (
	"context"
	"encoding/base64"
	"encoding/binary"
	"errors"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
	"unicode/utf16"
)

func TestWindowsLauncherUpgradeDoesNotReplaceOpenExecutable(t *testing.T) {
	root := filepath.Join(t.TempDir(), "CAD project (Jay)! ü")
	source := filepath.Join(t.TempDir(), "setup.exe")
	if err := os.WriteFile(source, []byte("first launcher"), 0700); err != nil {
		t.Fatal(err)
	}
	first, err := stageWindowsLauncher(root, source)
	if err != nil {
		t.Fatal(err)
	}
	open, err := os.Open(first)
	if err != nil {
		t.Fatal(err)
	}
	defer open.Close()
	if err = os.WriteFile(source, []byte("updated launcher"), 0700); err != nil {
		t.Fatal(err)
	}
	second, err := stageWindowsLauncher(root, source)
	if err != nil || first == second {
		t.Fatal(first, second, err)
	}
	old, _ := os.ReadFile(first)
	if string(old) != "first launcher" {
		t.Fatal("open previous executable was replaced")
	}
	again, err := stageWindowsLauncher(root, source)
	if err != nil || again != second {
		t.Fatal("offline reuse failed", err)
	}
	if err = os.WriteFile(second, []byte("corrupt"), 0700); err != nil {
		t.Fatal(err)
	}
	if _, err = stageWindowsLauncher(root, source); err == nil {
		t.Fatal("corrupt launcher accepted")
	}
}

func TestWindowsRuntimeRepairRetriesCurrentCommandAndRequestsUAC(t *testing.T) {
	if runtime.GOOS == "windows" {
		t.Skip("POSIX fake subprocess fixture; native Windows acceptance is separate")
	}
	root := t.TempDir()
	release := filepath.Join(root, "release")
	app := appPath(release)
	python := pyPath(release, platform{OS: "windows"})
	if err := os.MkdirAll(app, 0700); err != nil {
		t.Fatal(err)
	}
	if err := os.MkdirAll(filepath.Dir(python), 0700); err != nil {
		t.Fatal(err)
	}
	marker := filepath.Join(root, "runtime-ready")
	script := "#!/bin/sh\nif [ -f " + shellQuote(marker) + " ]; then exit 0; fi\necho 'ImportError: DLL load failed while importing QtCore' >&2\nexit 1\n"
	if err := os.WriteFile(python, []byte(script), 0700); err != nil {
		t.Fatal(err)
	}
	bin := filepath.Join(root, "bin")
	if err := os.MkdirAll(bin, 0700); err != nil {
		t.Fatal(err)
	}
	captured := filepath.Join(root, "powershell-args")
	ps := "#!/bin/sh\nfor arg; do printf '%s' \"$arg\" > " + shellQuote(captured) + "; done\ntouch " + shellQuote(marker) + "\n"
	if err := os.WriteFile(filepath.Join(bin, "powershell.exe"), []byte(ps), 0700); err != nil {
		t.Fatal(err)
	}
	t.Setenv("PATH", bin+string(os.PathListSeparator)+os.Getenv("PATH"))
	s := newState(platform{OS: "windows"}, "16.6.0", root)
	logfile := filepath.Join(root, "setup.log")
	log, err := os.Create(logfile)
	if err != nil {
		t.Fatal(err)
	}
	defer log.Close()
	s.setLog(log, logfile)
	if err = checkWithRuntime(context.Background(), root, release, platform{OS: "windows"}, "core", false, s); err != nil {
		t.Fatal(err)
	}
	encoded, err := os.ReadFile(captured)
	if err != nil {
		t.Fatal(err)
	}
	data, err := base64.StdEncoding.DecodeString(string(encoded))
	if err != nil {
		t.Fatal(err)
	}
	units := make([]uint16, len(data)/2)
	for i := range units {
		units[i] = binary.LittleEndian.Uint16(data[i*2:])
	}
	decoded := string(utf16.Decode(units))
	for _, token := range []string{"Get-AuthenticodeSignature", "Microsoft Corporation", "-Verb RunAs", "Tls12"} {
		if !strings.Contains(decoded, token) {
			t.Fatal("runtime verification/authorization missing", token)
		}
	}
	// A past DLL failure in the same log must not classify a later application
	// version or package assertion as another system-runtime problem.
	if err = os.WriteFile(python, []byte("#!/bin/sh\necho 'AssertionError: wrong package version' >&2\nexit 1\n"), 0700); err != nil {
		t.Fatal(err)
	}
	if err = check(context.Background(), release, platform{OS: "windows"}, "core", false, s); err == nil {
		t.Fatal("bad app check accepted")
	}
	if needsWindowsRuntime(s) {
		t.Fatal("stale DLL error triggered another runtime repair")
	}
}

func TestCommandTailIsBounded(t *testing.T) {
	tail := &commandTail{}
	_, _ = tail.Write([]byte(strings.Repeat("x", 20000)))
	_, _ = tail.Write([]byte("last error"))
	if len(tail.data) > 16000 || !strings.HasSuffix(string(tail.data), "last error") {
		t.Fatal("unbounded/missing diagnostic tail")
	}
}

func TestSetupLockReleasedAfterFailureAndReacquiredOnRetry(t *testing.T) {
	root := t.TempDir()
	failure := errors.New("dependency download failed")
	if err := withSetupLock(root, func() error {
		if err := withSetupLock(root, func() error { return nil }); err == nil {
			t.Fatal("concurrent setup entered")
		}
		return failure
	}); !errors.Is(err, failure) {
		t.Fatal(err)
	}
	if err := withSetupLock(root, func() error { return nil }); err != nil {
		t.Fatal("failed setup kept the root locked", err)
	}
	if err := withSetupLock(root, func() error { return nil }); err != nil {
		t.Fatal("completed retry kept the root locked", err)
	}
}
