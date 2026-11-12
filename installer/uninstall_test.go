package main

import (
	"context"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func uninstallFixture(t *testing.T, root, rel, data string) string {
	t.Helper()
	path := filepath.Join(root, filepath.FromSlash(rel))
	if err := os.MkdirAll(filepath.Dir(path), 0700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte(data), 0600); err != nil {
		t.Fatal(err)
	}
	return path
}

func TestUninstallPreservesDrawingsModifiedUnknownAndOutsideFiles(t *testing.T) {
	root := t.TempDir()
	outside := uninstallFixture(t, t.TempDir(), "outside.pycad", "outside")
	before, err := uninstallBaseline(root)
	if err != nil {
		t.Fatal(err)
	}
	owned := uninstallFixture(t, root, "releases/new/app/main.py", "owned")
	modified := uninstallFixture(t, root, "releases/new/app/custom.py", "original")
	drawing := uninstallFixture(t, root, "releases/new/app/my-drawing.pycad", "user drawing")
	for _, ext := range []string{"dxf", "dwg", "pdf", "ifc", "step", "pycad.bak"} {
		uninstallFixture(t, root, "releases/new/app/drawing."+ext, "drawing")
	}
	uninstallFixture(t, root, "current.json", "receipt")
	uninstallFixture(t, root, uninstallExeName, "launcher")
	if err = saveUninstallInventory(context.Background(), root, before); err != nil {
		t.Fatal(err)
	}
	unknown := uninstallFixture(t, root, "releases/new/app/notes.txt", "notes made after setup")
	if err = os.WriteFile(modified, []byte("user changes"), 0600); err != nil {
		t.Fatal(err)
	}
	inventory, err := loadUninstallInventory(root)
	if err != nil {
		t.Fatal(err)
	}
	result, err := removeOwnedFiles(context.Background(), root, inventory, nil)
	if err != nil || result.Removed != 2 || result.Kept != 1 {
		t.Fatalf("%+v %v", result, err)
	}
	if _, err = os.Stat(owned); !os.IsNotExist(err) {
		t.Fatal("owned app not removed")
	}
	pruneUninstallDirs(root)
	for _, file := range []string{modified, drawing, unknown, outside, filepath.Join(root, uninstallExeName), filepath.Join(root, uninstallManifestName)} {
		if _, err = os.Stat(file); err != nil {
			t.Fatal("preserved file missing", file, err)
		}
	}
}

func TestUninstallUpgradeDoesNotClaimPreexistingFiles(t *testing.T) {
	root := t.TempDir()
	legacy := uninstallFixture(t, root, "releases/old/app/my-notes.txt", "preexisting")
	before, err := uninstallBaseline(root)
	if err != nil {
		t.Fatal(err)
	}
	first := uninstallFixture(t, root, "releases/first/app/main.py", "first")
	uninstallFixture(t, root, "current.json", "first receipt")
	if err = saveUninstallInventory(context.Background(), root, before); err != nil {
		t.Fatal(err)
	}
	before, err = uninstallBaseline(root)
	if err != nil {
		t.Fatal(err)
	}
	second := uninstallFixture(t, root, "releases/second/app/main.py", "second")
	uninstallFixture(t, root, "current.json", "new receipt")
	if err = saveUninstallInventory(context.Background(), root, before); err != nil {
		t.Fatal(err)
	}
	inventory, err := loadUninstallInventory(root)
	if err != nil {
		t.Fatal(err)
	}
	if _, err = removeOwnedFiles(context.Background(), root, inventory, nil); err != nil {
		t.Fatal(err)
	}
	if _, err = os.Stat(legacy); err != nil {
		t.Fatal("claimed legacy file", err)
	}
	for _, p := range []string{first, second, filepath.Join(root, "current.json")} {
		if _, err = os.Stat(p); !os.IsNotExist(err) {
			t.Fatal("owned upgrade file remained", p)
		}
	}
}

func TestUninstallRejectsInvalidInventoryBeforeAnyRemoval(t *testing.T) {
	for _, rel := range []string{"../outside", "/absolute", "releases/../outside", `releases\escape`, "releases/a:stream", "arbitrary.txt", "releases/my.pycad"} {
		t.Run(rel, func(t *testing.T) {
			root := t.TempDir()
			owned := uninstallFixture(t, root, "releases/app/main.py", "keep on rejection")
			hash, _ := uninstallHash(owned)
			value := uninstallInventory{1, "PY.cad managed installation", root, map[string]string{"releases/app/main.py": hash, rel: strings.Repeat("a", 64)}}
			if err := writeJSON(filepath.Join(root, uninstallManifestName), value); err != nil {
				t.Fatal(err)
			}
			if _, err := loadUninstallInventory(root); err == nil {
				t.Fatal("accepted invalid inventory", rel)
			}
			if _, err := os.Stat(owned); err != nil {
				t.Fatal(err)
			}
		})
	}
}

func TestUninstallRefusesWrongRootAndReplacedDirectory(t *testing.T) {
	root := t.TempDir()
	before, _ := uninstallBaseline(root)
	uninstallFixture(t, root, "releases/app/main.py", "owned")
	if err := saveUninstallInventory(context.Background(), root, before); err != nil {
		t.Fatal(err)
	}
	inventory, err := loadUninstallInventory(root)
	if err != nil {
		t.Fatal(err)
	}
	inventory.Root = t.TempDir()
	if err = writeJSON(filepath.Join(root, uninstallManifestName), inventory); err != nil {
		t.Fatal(err)
	}
	if _, err = loadUninstallInventory(root); err == nil {
		t.Fatal("accepted wrong root")
	}
	inventory.Root = root
	if err = writeJSON(filepath.Join(root, uninstallManifestName), inventory); err != nil {
		t.Fatal(err)
	}
	if err = os.Rename(filepath.Join(root, "releases"), filepath.Join(root, "moved")); err != nil {
		t.Fatal(err)
	}
	if err = os.Symlink(filepath.Join(root, "moved"), filepath.Join(root, "releases")); err != nil {
		t.Skip("symlinks unavailable", err)
	}
	if _, err = loadUninstallInventory(root); err == nil {
		t.Fatal("followed replaced directory")
	}
	if _, err = os.Stat(filepath.Join(root, "moved", "app", "main.py")); err != nil {
		t.Fatal(err)
	}
}

func TestCancelledUninstallRetainsRecoveryAndOwnedFiles(t *testing.T) {
	root := t.TempDir()
	before, _ := uninstallBaseline(root)
	file := uninstallFixture(t, root, "releases/app/main.py", "owned")
	if err := saveUninstallInventory(context.Background(), root, before); err != nil {
		t.Fatal(err)
	}
	inventory, err := loadUninstallInventory(root)
	if err != nil {
		t.Fatal(err)
	}
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if _, err = removeOwnedFiles(ctx, root, inventory, nil); err != context.Canceled {
		t.Fatal(err)
	}
	if _, err = os.Stat(file); err != nil {
		t.Fatal(err)
	}
	if _, err = loadUninstallInventory(root); err != nil {
		t.Fatal("retry unavailable", err)
	}
}
