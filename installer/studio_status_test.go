package main

import (
	"bytes"
	"encoding/json"
	"image/gif"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestStudioDownloadProgressMeasuredAndUnknown(t *testing.T) {
	for _, total := range []int64{8, -1} {
		s := newState(platform{}, "16.44.0", "fixture")
		r := &countedDownload{reader: strings.NewReader("12345678"), state: s, total: total}
		b := make([]byte, 4)
		if n, e := r.Read(b); n != 4 || e != nil {
			t.Fatal(n, e)
		}
		v := s.status()
		if !v.Transfer.Active || v.Transfer.Bytes != 4 || v.Transfer.Total != max(0, total) {
			t.Fatalf("%+v", v.Transfer)
		}
		if v.Transfer.Name != "UV runtime bootstrap" {
			t.Fatal(v.Transfer)
		}
	}
}

func TestStudioPackageActivityAndReset(t *testing.T) {
	s := newState(platform{}, "16.44.0", "fixture")
	s.mu.Lock()
	s.capturePackages("Downloading PyQt6-Qt6 (74.5 MiB)\r\n Downloading numpy (16 MiB)\n\x1b[32m Downloaded PyQt6-Qt6\x1b[0m\n")
	s.mu.Unlock()
	v := s.status()
	if len(v.Packages) != 2 || !v.Packages[0].Done || v.Packages[0].Size != "74.5 MiB" || v.Packages[1].Done {
		t.Fatalf("%+v", v.Packages)
	}
	v.Packages[0].Name = "changed outside state"
	if s.status().Packages[0].Name != "PyQt6-Qt6" {
		t.Fatal("snapshot mutated installer state")
	}
	s.reset()
	if len(s.status().Packages) != 0 {
		t.Fatal("retry did not clear package activity")
	}
}

func TestStudioAssetsAndStatusUseLocalAuthorization(t *testing.T) {
	s := newState(platform{}, "16.44.0", "fixture")
	s.transfer("Verified download", 12, 24, true)
	handler := progressHandler(s, "test", "127.0.0.1:12345", func() {})
	for path, mime := range map[string]string{"/": "text/html; charset=utf-8", "/status": "application/json", "/studio-banner.png": "image/png", "/studio-animation.gif": "image/gif"} {
		for _, query := range []string{"", "?key=test"} {
			r := httptest.NewRequest(http.MethodGet, "http://127.0.0.1:12345"+path+query, nil)
			w := httptest.NewRecorder()
			handler.ServeHTTP(w, r)
			if query == "" {
				if w.Code != 404 {
					t.Fatalf("%s leaked", path)
				}
				continue
			}
			if w.Code != 200 || w.Header().Get("Content-Type") != mime {
				t.Fatal(path, w.Code, w.Header())
			}
			if path == "/status" {
				var v snapshot
				if e := json.Unmarshal(w.Body.Bytes(), &v); e != nil || v.Transfer.Bytes != 12 || v.Transfer.Total != 24 {
					t.Fatal(v.Transfer, e)
				}
			}
		}
	}
	g, e := gif.DecodeAll(bytes.NewReader(studioAnimation))
	if e != nil || len(g.Image) < 2 {
		t.Fatal("animated banner is not decodable", e)
	}
}
