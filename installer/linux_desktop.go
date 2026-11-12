package main

import (
	_ "embed"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

//go:embed studio/uninstall.py
var desktopUninstaller []byte

const legacyDesktopUninstallerSHA = "9e3a71bf920cc1b7c95d1d629ead6ac538b3b4918fcd7e3035066cc93e5e1ec2"

func desktopCommand(args ...string) string {
	return strings.ReplaceAll(strings.Join(args, " "), "\\", "\\\\")
}

func installLinuxUninstall(root, folder, icon string) (string, error) {
	script := filepath.Join(root, "uninstall-studio.py")
	entry := filepath.Join(folder, "pycad-uninstall.desktop")
	base := []string{desktopQuote("/usr/bin/python3"), "-I", desktopQuote(script)}
	command := desktopCommand(append(base, "--root", desktopQuote(root))...)
	prefix := "[Desktop Entry]\nType=Application\nName=Uninstall PY.cad\nExec="
	suffix := "\nCategories=Graphics;Engineering;\n"
	value := prefix + command + "\nTerminal=false" + suffix + "Icon=" + strings.ReplaceAll(icon, "\\", "\\\\") + "\n"
	legacy := prefix + desktopCommand(base...) + "\nTerminal=true" + suffix
	owned := func(path string, allowed func([]byte) bool) error {
		info, err := os.Lstat(path)
		if os.IsNotExist(err) {
			return nil
		}
		if err != nil {
			return err
		}
		if !info.Mode().IsRegular() || info.Size() > 128<<10 {
			return fmt.Errorf("Existing file was left untouched: %s", path)
		}
		data, err := os.ReadFile(path)
		if err != nil {
			return err
		}
		if !allowed(data) {
			return fmt.Errorf("Existing file was left untouched: %s", path)
		}
		return nil
	}
	if err := owned(script, func(b []byte) bool {
		return digest(b) == legacyDesktopUninstallerSHA || string(b) == string(desktopUninstaller)
	}); err != nil {
		return "", err
	}
	if err := owned(entry, func(b []byte) bool { return string(b) == legacy || string(b) == value }); err != nil {
		return "", err
	}
	if err := writeDesktopFile(script, desktopUninstaller); err != nil {
		return "", err
	}
	if err := writeDesktopFile(entry, []byte(value)); err != nil {
		return "", err
	}
	return "\nActions=Uninstall;\n\n[Desktop Action Uninstall]\nName=Uninstall\nExec=" + command + "\n", nil
}

func writeDesktopFile(path string, data []byte) error {
	f, err := os.CreateTemp(filepath.Dir(path), ".pycad-desktop-*")
	if err != nil {
		return err
	}
	defer os.Remove(f.Name())
	_, err = f.Write(data)
	closeErr := f.Close()
	if err != nil {
		return err
	}
	if closeErr != nil {
		return closeErr
	}
	return os.Rename(f.Name(), path)
}
