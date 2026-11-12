//go:build linux || darwin

package main

import (
	"context"
	"errors"
	"os"
)

func isUninstallLink(info os.FileInfo) bool { return info.Mode()&os.ModeSymlink != 0 }
func registerUninstaller(ctx context.Context, root, version string, before map[string]bool, s *progress) error {
	return nil
}
func runUninstaller(root string, worker bool, parent int) error {
	return errors.New("The built-in uninstaller is for Windows")
}
