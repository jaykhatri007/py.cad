package main

import (
	"bytes"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
)

func TestBrandLegalHTTPKeepsAuthorization(t *testing.T) {
	s := newState(platform{}, "16.5.0", "private")
	h := progressHandler(s, "secret", "127.0.0.1:7777", func() {})
	for _, route := range []string{"/logo", "/legal"} {
		for _, authorized := range []bool{false, true} {
			path := route
			if authorized {
				path += "?key=secret"
			}
			r := httptest.NewRequest("GET", "http://127.0.0.1:7777"+path, nil)
			w := httptest.NewRecorder()
			h.ServeHTTP(w, r)
			if !authorized {
				if w.Code != 404 {
					t.Fatal("brand/legal content leaked without key", route, w.Code)
				}
				continue
			}
			if w.Code != 200 {
				t.Fatal(route, w.Code)
			}
			if route == "/logo" && !bytes.Equal(w.Body.Bytes(), brandLogo) {
				t.Fatal("logo does not match approved asset")
			}
			if route == "/legal" && !bytes.Contains(w.Body.Bytes(), []byte("GNU GENERAL PUBLIC LICENSE")) {
				t.Fatal("full GPL missing from legal viewer")
			}
		}
	}
}

func TestNativeIconFilesInstalledWithoutDrawingChanges(t *testing.T) {
	root := t.TempDir()
	drawing := filepath.Join(root, "keep.pycad")
	if err := os.WriteFile(drawing, []byte("drawing"), 0600); err != nil {
		t.Fatal(err)
	}
	dir, err := installBrandIcons(root)
	if err != nil {
		t.Fatal(err)
	}
	for name, expected := range map[string][]byte{"pycad.png": pngIcon, "pycad.ico": winIcon, "pycad.icns": macIcon} {
		data, err := os.ReadFile(filepath.Join(dir, name))
		if err != nil || !bytes.Equal(data, expected) {
			t.Fatal(name, err)
		}
	}
	if data, _ := os.ReadFile(drawing); string(data) != "drawing" {
		t.Fatal("drawing changed")
	}
}
