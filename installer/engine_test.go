package main

import (
	"archive/zip"
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
)

func TestPlatformDetection(t *testing.T) {
	for _, key := range []string{"linux-amd64", "linux-arm64", "windows-amd64", "darwin-amd64", "darwin-arm64"} {
		t.Run(key, func(t *testing.T) {
			a := strings.Split(key, "-")
			p, e := detect(a[0], a[1])
			if e != nil || p.Key() != key {
				t.Fatal(p, e)
			}
		})
	}
	for _, key := range []string{"windows-arm64", "linux-386", "freebsd-amd64"} {
		t.Run(key, func(t *testing.T) {
			a := strings.Split(key, "-")
			if _, e := detect(a[0], a[1]); e == nil {
				t.Fatal("unsupported target accepted")
			}
		})
	}
}
func TestEmbeddedIntegrity(t *testing.T) {
	m, e := readManifest()
	if e != nil || m.Version != "16.45.0" || len(m.Assets) != 5 {
		t.Fatal(m, e)
	}
	old := payload
	payload = append([]byte{}, old...)
	payload[3] ^= 1
	defer func() { payload = old }()
	if _, e = readManifest(); e == nil {
		t.Fatal("tampered application accepted")
	}
}
func archive(entries []string, link bool) []byte {
	var b bytes.Buffer
	w := zip.NewWriter(&b)
	for _, n := range entries {
		h := &zip.FileHeader{Name: n, Method: zip.Deflate}
		h.SetMode(0600)
		if link {
			h.SetMode(os.ModeSymlink | 0700)
		}
		f, _ := w.CreateHeader(h)
		_, _ = io.WriteString(f, "print('ok')")
	}
	_ = w.Close()
	return b.Bytes()
}
func TestPayloadExtraction(t *testing.T) {
	if e := extractPayload(archive([]string{"PyCAD-v15/main.py", "PyCAD-v15/folder/space ü.txt"}, false), t.TempDir()); e != nil {
		t.Fatal(e)
	}
	tests := map[string][]byte{"traversal": archive([]string{"PyCAD-v15/../../escape"}, false), "absolute": archive([]string{"/tmp/escape"}, false), "backslash": archive([]string{"PyCAD-v15/..\\escape"}, false), "drive": archive([]string{"PyCAD-v15/C:/escape"}, false), "duplicate": archive([]string{"PyCAD-v15/main.py", "PyCAD-v15/main.py"}, false), "symlink": archive([]string{"PyCAD-v15/main.py"}, true), "missing-main": archive([]string{"PyCAD-v15/readme.txt"}, false)}
	for name, b := range tests {
		t.Run(name, func(t *testing.T) {
			if e := extractPayload(b, t.TempDir()); e == nil {
				t.Fatal("unsafe payload accepted")
			}
		})
	}
}
func TestDownloadIntegrityAndCache(t *testing.T) {
	calls := 0
	server := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { calls++; _, _ = io.WriteString(w, "verified-runtime") }))
	defer server.Close()
	a := asset{server.URL, digest([]byte("verified-runtime"))}
	dest := filepath.Join(t.TempDir(), "runtime")
	if e := download(context.Background(), server.Client(), a, dest); e != nil {
		t.Fatal(e)
	}
	if e := download(context.Background(), server.Client(), a, dest); e != nil || calls != 1 {
		t.Fatal(e, calls)
	}
	a.SHA = strings.Repeat("0", 64)
	if e := download(context.Background(), server.Client(), a, dest); e == nil {
		t.Fatal("tampered download accepted")
	}
	b, _ := os.ReadFile(dest)
	if string(b) != "verified-runtime" {
		t.Fatal("failed download replaced old content")
	}
	a.URL = "http://example.com/runtime"
	if e := download(context.Background(), server.Client(), a, dest); e == nil {
		t.Fatal("unencrypted download accepted")
	}
}
func TestLinuxPackagePlans(t *testing.T) {
	tests := map[string]string{"ID=ubuntu": "apt-get", "ID=debian": "apt-get", "ID=fedora": "dnf", "ID=manjaro\nID_LIKE=arch": "pacman", "ID=opensuse-tumbleweed": "zypper", "ID=pop\nID_LIKE=\"ubuntu debian\"": "apt-get"}
	for data, want := range tests {
		t.Run(want+data, func(t *testing.T) {
			got, packages, e := linuxPackages(data, []string{"libxcb-cursor.so.0", "libGL.so.1", "libxcb-cursor.so.0"})
			if e != nil || got != want || len(packages) != 2 {
				t.Fatal(got, packages, e)
			}
		})
	}
	if _, _, e := linuxPackages("ID=unknown", []string{"libxcb-cursor.so.0"}); e == nil {
		t.Fatal("unknown distribution accepted")
	}
}
func TestCleanEnvironment(t *testing.T) {
	for _, k := range []string{"PYTHONHOME", "UV_INDEX_URL", "PIP_INDEX_URL", "QT_PLUGIN_PATH", "VIRTUAL_ENV"} {
		t.Setenv(k, "wrong")
	}
	for _, v := range cleanEnv(map[string]string{"UV_CACHE_DIR": "private", "PYTHONNOUSERSITE": "1"}) {
		if strings.HasSuffix(v, "=wrong") {
			t.Fatal(v)
		}
	}
	if !strings.Contains(strings.Join(cleanEnv(nil), "\n"), "PYTHONUTF8=1") {
		t.Fatal("Unicode Windows setup output was not made UTF-8")
	}
}
func TestReceiptValidationAndReplacement(t *testing.T) {
	root := t.TempDir()
	r := receipt{1, "old", "pycad-old", "abc", "linux-amd64", "full"}
	file := filepath.Join(root, "current.json")
	if e := writeJSON(file, r); e != nil {
		t.Fatal(e)
	}
	r.Version = "new"
	if e := writeJSON(file, r); e != nil {
		t.Fatal(e)
	}
	got, e := loadReceipt(root)
	if e != nil || got.Version != "new" {
		t.Fatal(got, e)
	}
	for _, bad := range []string{"../escape", "C:\\outside", ".", "otherapp"} {
		r.Release = bad
		_ = writeJSON(file, r)
		if _, e = loadReceipt(root); e == nil {
			t.Fatal("invalid receipt", bad)
		}
	}
}
func TestExclusiveSetupLock(t *testing.T) {
	root := t.TempDir()
	first, e := acquireLock(root)
	if e != nil {
		t.Fatal(e)
	}
	if f, e := acquireLock(root); e == nil {
		f.Close()
		t.Fatal("concurrent setup accepted")
	}
	first.Close()
	last, e := acquireLock(root)
	if e != nil {
		t.Fatal(e)
	}
	last.Close()
}
func TestFailedUpgradePreservesCurrentAndDrawing(t *testing.T) {
	if runtime.GOOS != "linux" {
		t.Skip("native Linux workflow")
	}
	root := t.TempDir()
	r := receipt{1, "old", "pycad-old", "old-payload", "linux-amd64", "full"}
	_ = writeJSON(filepath.Join(root, "current.json"), r)
	before, _ := os.ReadFile(filepath.Join(root, "current.json"))
	project := filepath.Join(root, "my-project.pycad")
	_ = os.WriteFile(project, []byte("drawing remains"), 0600)
	m, _ := readManifest()
	m.Assets = map[string]asset{}
	p, _ := detect("linux", "amd64")
	s := newState(p, m.Version, root)
	e := install(context.Background(), options{Root: root, NoLaunch: true, NoSystem: true}, p, m, s)
	if e == nil {
		t.Fatal("missing download should fail")
	}
	after, _ := os.ReadFile(filepath.Join(root, "current.json"))
	drawing, _ := os.ReadFile(project)
	if !bytes.Equal(before, after) || string(drawing) != "drawing remains" {
		t.Fatal("failed upgrade changed current installation or drawing")
	}
}
func TestProgressHTTPAuthorizationAndRetry(t *testing.T) {
	p, _ := detect("linux", "amd64")
	s := newState(p, "16.3.0", "private")
	h := progressHandler(s, "secret", "127.0.0.1:7777", func() {})
	request := func(method, path, key, origin string) int {
		r := httptest.NewRequest(method, "http://127.0.0.1:7777"+path+"?key="+key, nil)
		r.Header.Set("Origin", origin)
		w := httptest.NewRecorder()
		h.ServeHTTP(w, r)
		return w.Code
	}
	if request("GET", "/status", "wrong", "") != 404 || request("GET", "/status", "secret", "") != 200 {
		t.Fatal("authorization failed")
	}
	if request("POST", "/retry", "secret", "http://evil.example") != 403 || request("GET", "/close", "secret", "") != 405 {
		t.Fatal("foreign origin or GET mutation accepted")
	}
	if request("POST", "/retry", "secret", "") != 409 {
		t.Fatal("running setup retry accepted")
	}
	s.fail(errors.New("test failure"))
	if request("POST", "/retry", "secret", "http://127.0.0.1:7777") != 204 || request("POST", "/retry", "secret", "") != 409 {
		t.Fatal("retry queue failed")
	}
	<-s.retry
	s.reset()
	if s.status().Error != "" {
		t.Fatal("reset failed")
	}
	r := httptest.NewRequest("GET", "http://evil.invalid/status?key=secret", nil)
	w := httptest.NewRecorder()
	h.ServeHTTP(w, r)
	if w.Code != 404 {
		t.Fatal("untrusted Host accepted")
	}
}
func TestStatusTextAndQuoting(t *testing.T) {
	p, _ := detect("linux", "amd64")
	s := newState(p, "16.3.0", "private")
	s.note("<script>alert('x')</script>")
	b, _ := json.Marshal(s.status())
	if strings.Contains(string(b), "<script>") {
		t.Fatal("unsafe JSON")
	}
	if !bytes.Contains(setupHTML, []byte(".textContent=")) {
		t.Fatal("unsafe renderer")
	}
	if shellQuote("a'b") != "'a'\"'\"'b'" || psQuote("a'b") != "'a''b'" || encodedPS("'λ'") == "" {
		t.Fatal("quoting failed")
	}
}

func TestWindowsRuntimeRepairOnlyForDLLFailure(t *testing.T) {
	p, _ := detect("windows", "amd64")
	s := newState(p, "16.3.0", t.TempDir())
	file := filepath.Join(t.TempDir(), "log.txt")
	s.logfile = file
	_ = os.WriteFile(file, []byte("AssertionError: incorrect NumPy version"), 0600)
	if needsWindowsRuntime(s) {
		t.Fatal("unrelated import error requested a system runtime")
	}
	_ = os.WriteFile(file, []byte("ImportError: DLL load failed while importing OCP"), 0600)
	if !needsWindowsRuntime(s) {
		t.Fatal("DLL failure was not recognized")
	}
}
