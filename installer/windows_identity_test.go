package main

import (
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestWindowsRuntimeCommandChecksIdentityAndArguments(t *testing.T) {
	root := t.TempDir()
	release := filepath.Join(root, "releases", "pycad-fixture")
	host := filepath.Join(root, "python", "private-runtime", "PY.cad-fixture.exe")
	os.MkdirAll(filepath.Dir(host), 0700)
	os.MkdirAll(release, 0700)
	bytes := []byte("branded runtime fixture")
	os.WriteFile(host, bytes, 0600)
	record := windowsAppIdentity{1, "PY.cad", host, digest(bytes)}
	encoded, _ := json.Marshal(record)
	os.WriteFile(filepath.Join(release, "windows-app.json"), encoded, 0600)
	program, args, err := windowsAppCommand(root, release, []string{"--", "Drawing ü & personal.dwg"})
	if err != nil || program != host || args[len(args)-1] != "Drawing ü & personal.dwg" || !strings.HasSuffix(args[0], "windows_app_start.py") {
		t.Fatal(program, args, err)
	}
	os.WriteFile(host, []byte("tampered"), 0600)
	if _, _, err = windowsAppCommand(root, release, nil); err == nil {
		t.Fatal("tampered host accepted")
	}
	record.Host = filepath.Join(t.TempDir(), "PY.cad-outside.exe")
	encoded, _ = json.Marshal(record)
	os.WriteFile(filepath.Join(release, "windows-app.json"), encoded, 0600)
	if _, _, err = windowsAppCommand(root, release, nil); err == nil {
		t.Fatal("outside runtime accepted")
	}
}

func TestOtherPlatformsDoNotPrepareWindowsRuntime(t *testing.T) {
	if err := prepareWindowsIdentity(context.Background(), "unused", "unused", "core", platform{OS: "linux"}, nil); err != nil {
		t.Fatal(err)
	}
}

func TestForeignVenvLauncherDoesNotLeakIntoBrandedRuntime(t *testing.T) {
	t.Setenv("__PYVENV_LAUNCHER__", "foreign-python.exe")
	for _, item := range cleanEnv(nil) {
		if strings.HasPrefix(strings.ToUpper(item), "__PYVENV_LAUNCHER__=") {
			t.Fatal("foreign runtime leaked", item)
		}
	}
}
