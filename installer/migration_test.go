package main

import (
	"os"
	"path/filepath"
	"testing"
)

func TestManagedBundleRenamePreservesFilesAndUnrelatedApps(t *testing.T) {
	for _, tc := range []struct {
		name               string
		owned, existingNew bool
	}{
		{"owned legacy bundle", true, false},
		{"unrelated legacy bundle", false, false},
		{"new-name app already exists", true, true},
	} {
		t.Run(tc.name, func(t *testing.T) {
			root := t.TempDir()
			oldPath, newPath := filepath.Join(root, "PyCAD.app"), filepath.Join(root, "PY.cad.app")
			if err := os.MkdirAll(filepath.Join(oldPath, "Contents"), 0700); err != nil {
				t.Fatal(err)
			}
			if err := os.WriteFile(filepath.Join(oldPath, "keep.txt"), []byte("preserve"), 0600); err != nil {
				t.Fatal(err)
			}
			if tc.owned {
				if err := os.WriteFile(filepath.Join(oldPath, "Contents", "PyCAD-Managed.txt"), []byte("PyCAD managed installation\n"), 0600); err != nil {
					t.Fatal(err)
				}
			}
			if tc.existingNew {
				if err := os.Mkdir(newPath, 0700); err != nil {
					t.Fatal(err)
				}
				if err := os.WriteFile(filepath.Join(newPath, "unrelated.txt"), []byte("untouched"), 0600); err != nil {
					t.Fatal(err)
				}
			}
			if err := migrateManagedBundle(oldPath, newPath); err != nil {
				t.Fatal(err)
			}
			kept := oldPath
			if tc.owned && !tc.existingNew {
				kept = newPath
			}
			if data, err := os.ReadFile(filepath.Join(kept, "keep.txt")); err != nil || string(data) != "preserve" {
				t.Fatal("legacy content lost", err)
			}
			if tc.existingNew {
				if data, err := os.ReadFile(filepath.Join(newPath, "unrelated.txt")); err != nil || string(data) != "untouched" {
					t.Fatal("unrelated new app changed", err)
				}
			}
			if !tc.owned {
				if _, err := os.Lstat(newPath); !os.IsNotExist(err) {
					t.Fatal("unrelated old app was moved")
				}
			}
		})
	}
}
