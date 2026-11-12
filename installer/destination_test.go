package main

import (
	"os"
	"path/filepath"
	"testing"
)

func TestWindowsDefaultIsProgramFiles(t *testing.T) {
	t.Setenv("ProgramW6432", filepath.Join(t.TempDir(), "Program Files"))
	t.Setenv("LOCALAPPDATA", filepath.Join(t.TempDir(), "hidden"))
	root, err := defaultRoot("windows")
	if err != nil || root != filepath.Join(os.Getenv("ProgramW6432"), "PY.cad") {
		t.Fatalf("default folder: %s %v", root, err)
	}
}
