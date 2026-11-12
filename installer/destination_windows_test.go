//go:build windows

package main

import (
	"testing"
)

func TestDestinationValidation(t *testing.T) {
	t.Setenv("ProgramFiles", `C:\Program Files`)
	t.Setenv("ProgramW6432", `C:\Program Files`)
	t.Setenv("WINDIR", `C:\Windows`)
	for _, root := range []string{`C:\Program Files\PY.cad`, `D:\CAD software\PY.cad`, `C:\Users\Jay\CAD`} {
		if e := validateDestination(root); e != nil {
			t.Errorf("valid destination %q: %v", root, e)
		}
	}
	for _, root := range []string{`C:\`, `C:\Program Files`, `C:\Windows`, `relative`, `\\server\share\CAD`, "C:\\bad\nfolder"} {
		if e := validateDestination(root); e == nil {
			t.Errorf("accepted invalid destination %q", root)
		}
	}
}
