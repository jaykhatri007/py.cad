package main

import (
	_ "embed"
	"os"
	"path/filepath"
)

//go:embed assets/pycad-icon.png
var pngIcon []byte

//go:embed assets/pycad.ico
var winIcon []byte

//go:embed assets/pycad.icns
var macIcon []byte

//go:embed assets/pycad-logo.png
var brandLogo []byte

//go:embed legal.html
var legalHTML []byte

//go:embed assets/legal.txt
var nativeLegalText []byte

func installBrandIcons(root string) (string, error) {
	dir := filepath.Join(root, "icons")
	if err := os.MkdirAll(dir, 0700); err != nil {
		return "", err
	}
	for name, data := range map[string][]byte{"pycad.png": pngIcon, "pycad.ico": winIcon, "pycad.icns": macIcon} {
		if err := os.WriteFile(filepath.Join(dir, name), data, 0600); err != nil {
			return "", err
		}
	}
	return dir, nil
}
