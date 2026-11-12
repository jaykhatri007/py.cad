package main

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestGraphicalUninstallShortcutAndLegacyMigration(t *testing.T) {
	root := t.TempDir()
	folder := t.TempDir()
	entry := filepath.Join(folder, "pycad-uninstall.desktop")
	script := filepath.Join(root, "uninstall-studio.py")
	legacy := "[Desktop Entry]\nType=Application\nName=Uninstall PY.cad\nExec=" + desktopCommand(desktopQuote("/usr/bin/python3"), "-I", desktopQuote(script)) + "\nTerminal=true\nCategories=Graphics;Engineering;\n"
	if e := os.WriteFile(entry, []byte(legacy), 0600); e != nil {
		t.Fatal(e)
	}
	icon := filepath.Join(root, "icons", "pycad.png")
	action, e := installLinuxUninstall(root, folder, icon)
	if e != nil {
		t.Fatal(e)
	}
	b, e := os.ReadFile(entry)
	if e != nil {
		t.Fatal(e)
	}
	if !strings.Contains(string(b), "\nTerminal=false\n") || !strings.Contains(action, "Actions=Uninstall;\n\n[Desktop Action Uninstall]\nName=Uninstall\n") {
		t.Fatal(action, string(b))
	}
	execLine := strings.Split(strings.Split(action, "Exec=")[1], "\n")[0]
	if !strings.Contains(string(b), "Exec="+execLine+"\n") || !strings.Contains(execLine, " --root ") {
		t.Fatal(execLine)
	}
	if _, e = installLinuxUninstall(root, folder, icon); e != nil {
		t.Fatal(e)
	}
	if e = os.WriteFile(entry, []byte("user shortcut"), 0600); e != nil {
		t.Fatal(e)
	}
	if _, e = installLinuxUninstall(root, folder, icon); e == nil {
		t.Fatal("unexpected overwrite")
	}
	b, _ = os.ReadFile(entry)
	if string(b) != "user shortcut" {
		t.Fatal("unrelated shortcut changed")
	}
}
