package main

import (
	"archive/tar"
	"archive/zip"
	"bytes"
	"compress/gzip"
	"context"
	"crypto/sha256"
	_ "embed"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"os/exec"
	"path"
	"path/filepath"
	"strings"
	"sync"
	"time"
)

//go:embed assets/payload.zip
var payload []byte

//go:embed assets/manifest.json
var manifestBytes []byte

type asset struct {
	URL string `json:"url"`
	SHA string `json:"sha256"`
}
type manifest struct {
	Version, Python string
	PayloadSHA      string           `json:"payload_sha256"`
	UVVersion       string           `json:"uv_version"`
	Assets          map[string]asset `json:"assets"`
}
type receipt struct {
	Schema     int    `json:"schema"`
	Version    string `json:"version"`
	Release    string `json:"release"`
	PayloadSHA string `json:"payload_sha256"`
	Platform   string `json:"platform"`
	Profile    string `json:"profile"`
}

func digest(b []byte) string { h := sha256.Sum256(b); return hex.EncodeToString(h[:]) }
func readManifest() (manifest, error) {
	var m manifest
	err := json.Unmarshal(manifestBytes, &m)
	if err == nil && (m.Version == "" || m.Python != "3.12" || digest(payload) != m.PayloadSHA) {
		err = errors.New("The embedded application failed its integrity check. Download Setup again.")
	}
	return m, err
}
func safeName(s string) bool {
	return s != "" && s != "." && s != ".." && !strings.ContainsAny(s, "/\\\x00")
}
func writeJSON(file string, v any) error {
	b, err := json.MarshalIndent(v, "", "  ")
	if err != nil {
		return err
	}
	tmp := file + "." + nonce() + ".tmp"
	if err = os.WriteFile(tmp, append(b, '\n'), 0600); err != nil {
		return err
	}
	defer os.Remove(tmp)
	return os.Rename(tmp, file)
}
func loadReceipt(root string) (receipt, error) {
	var r receipt
	b, err := os.ReadFile(filepath.Join(root, "current.json"))
	if err != nil {
		return r, err
	}
	err = json.Unmarshal(b, &r)
	if err == nil && (r.Schema != 1 || !safeName(r.Release) || !strings.HasPrefix(r.Release, "pycad-")) {
		err = errors.New("Invalid installation receipt")
	}
	return r, err
}
func pyPath(release string, p platform) string {
	if p.OS == "windows" {
		return filepath.Join(release, "env", "Scripts", "python.exe")
	}
	return filepath.Join(release, "env", "bin", "python")
}
func appPath(release string) string { return filepath.Join(release, "app", "PyCAD-v15") }
func cleanEnv(extra map[string]string) []string {
	// Prevent an unrelated Python/Qt/uv configuration from changing this private setup.
	var env []string
	for _, v := range os.Environ() {
		k, _, _ := strings.Cut(v, "=")
		u := strings.ToUpper(k)
		if strings.HasPrefix(u, "PYTHON") || strings.HasPrefix(u, "UV_") || strings.HasPrefix(u, "PIP_") || u == "__PYVENV_LAUNCHER__" || u == "VIRTUAL_ENV" || u == "CONDA_PREFIX" || u == "QT_PLUGIN_PATH" || u == "QT_QPA_PLATFORM_PLUGIN_PATH" {
			continue
		}
		if _, ok := extra[k]; !ok {
			env = append(env, v)
		}
	}
	for k, v := range extra {
		env = append(env, k+"="+v)
	}
	if _, explicit := extra["PYTHONUTF8"]; !explicit {
		// Redirected Windows output otherwise uses the ANSI code page, which
		// can fail while printing a Unicode user/profile path into setup logs.
		env = append(env, "PYTHONUTF8=1")
	}
	return env
}

type commandTail struct {
	mu     sync.Mutex
	data   []byte
	notify func(string)
}

func (t *commandTail) Write(b []byte) (int, error) {
	t.mu.Lock()
	n := len(b)
	if len(b) >= 16000 {
		t.data = append(t.data[:0], b[len(b)-16000:]...)
	} else {
		t.data = append(t.data, b...)
		if len(t.data) > 16000 {
			t.data = t.data[len(t.data)-16000:]
		}
	}
	text := string(t.data)
	t.mu.Unlock()
	if t.notify != nil {
		t.notify(text)
	}
	return n, nil
}

func run(ctx context.Context, s *progress, env []string, dir, program string, args ...string) error {
	s.logCommand(program, args)
	cmd := exec.CommandContext(ctx, program, args...)
	cmd.Env = env
	cmd.Dir = dir
	tail := &commandTail{notify: func(text string) {
		s.mu.Lock()
		s.lastOutput, s.haveCommand = text, true
		if last := strings.LastIndexAny(text, "\r\n"); last >= 0 {
			s.capturePackages(text[:last+1])
		}
		s.mu.Unlock()
	}}
	output := io.MultiWriter(s.log, tail)
	cmd.Stdout = output
	cmd.Stderr = output
	hideConsole(cmd)
	err := cmd.Run()
	s.mu.Lock()
	s.lastOutput, s.haveCommand = string(tail.data), true
	s.capturePackages(s.lastOutput)
	s.mu.Unlock()
	if err != nil {
		detail := []rune(strings.TrimSpace(string(tail.data)))
		if len(detail) > 2400 {
			detail = detail[len(detail)-2400:]
		}
		return fmt.Errorf("%s failed: %w. Installation log: %s\n%s", filepath.Base(program), err, s.logPath(), string(detail))
	}
	return nil
}
func check(ctx context.Context, release string, p platform, profile string, desktop bool, s *progress) error {
	code := `import sys,struct; assert sys.version_info[:2]==(3,12) and struct.calcsize('P')==8
from PyQt6 import QtWidgets,QtSvg,QtPrintSupport,QtPdf,QtOpenGL,QtOpenGLWidgets
import ezdxf,numpy,pypdf
import importlib.metadata as md
for name, version in [('PyQt6','6.11.0'),('PyQt6-Qt6','6.11.2'),('ezdxf','1.4.4'),('numpy','2.3.5'),('pypdf','6.10.0')]:
 assert md.version(name)==version, (name,md.version(name))
assert ezdxf.new().dxfversion and numpy.zeros(2).shape==(2,)
`
	if profile == "full" {
		code += `import cadquery as cq, ifcopenshell
shape=cq.Workplane('XY').box(10,10,10).val(); assert shape.isValid() and abs(shape.Volume()-1000)<1e-6
ifcopenshell.file(schema='IFC4')
`
	}
	if desktop {
		code += `from PyQt6.QtWidgets import QApplication
from pycad.main_window import MainWindow
app=QApplication([]); window=MainWindow(); window.close()
`
	}
	prefs, err := os.MkdirTemp("", "pycad-verify-")
	if err != nil {
		return err
	}
	defer os.RemoveAll(prefs)
	env := cleanEnv(map[string]string{"PYCAD_DATA_DIR": prefs, "PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1"})
	if !desktop {
		env = append(env, "QT_QPA_PLATFORM=offscreen")
	}
	return run(ctx, s, env, appPath(release), pyPath(release, p), "-c", code)
}
func checkWithRuntime(ctx context.Context, root, release string, p platform, profile string, desktop bool, s *progress) error {
	err := check(ctx, release, p, profile, desktop, s)
	if err != nil && p.OS == "windows" && needsWindowsRuntime(s) {
		if repairErr := repairWindowsRuntime(ctx, root, s); repairErr != nil {
			return repairErr
		}
		return check(ctx, release, p, profile, desktop, s)
	}
	return err
}

func install(ctx context.Context, o options, p platform, m manifest, s *progress) error {
	var uninstallBefore map[string]bool
	if p.OS == "windows" {
		var e error
		uninstallBefore, e = uninstallBaseline(o.Root)
		if e != nil {
			return e
		}
	}
	logdir := filepath.Join(o.Root, "logs")
	if err := os.MkdirAll(logdir, 0700); err != nil {
		return err
	}
	logfile := filepath.Join(logdir, "setup-"+time.Now().Format("20060102-150405")+"-"+nonce()[:6]+".log")
	f, err := os.OpenFile(logfile, os.O_CREATE|os.O_WRONLY|os.O_EXCL, 0600)
	if err != nil {
		return err
	}
	defer f.Close()
	s.setLog(f, logfile)
	s.step(0, "Detected "+p.Label+" · "+p.ArchLabel)
	if err = preflight(p, o); err != nil {
		return err
	}
	profile := "full"
	if o.CoreOnly {
		profile = "core"
	}
	if r, e := loadReceipt(o.Root); e == nil && r.PayloadSHA == m.PayloadSHA && r.Platform == p.Key() && r.Profile == profile {
		release := filepath.Join(o.Root, "releases", r.Release)
		probeCtx, cancel := context.WithTimeout(ctx, 90*time.Second)
		err = check(probeCtx, release, p, profile, false, s)
		cancel()
		if err != nil && p.OS == "windows" && needsWindowsRuntime(s) {
			// Do not spend the short offline probe timeout downloading a runtime
			// or waiting for the user's separate Microsoft authorization dialog.
			if err = repairWindowsRuntime(ctx, o.Root, s); err != nil {
				return err
			}
			err = check(ctx, release, p, profile, false, s)
		}
		if err == nil {
			if p.OS == "linux" {
				if err = ensureLinux(ctx, o, p, release, s); err != nil {
					return err
				}
			}
			s.note("Existing private environment passed checks; no dependency download needed.")
			s.step(4, "Checking application startup")
			if !o.NoLaunch {
				if err = checkWithRuntime(ctx, o.Root, release, p, profile, true, s); err != nil {
					return desktopError(err)
				}
			}
			if err = recordRuntimeLegal(ctx, release, p, s); err != nil {
				return err
			}
			if err = prepareWindowsIdentity(ctx, o.Root, release, profile, p, s); err != nil {
				return err
			}
			if err = installShortcuts(o.Root, p, s, release); err != nil {
				return err
			}
			if p.OS == "windows" {
				if err = registerUninstaller(ctx, o.Root, m.Version, uninstallBefore, s); err != nil {
					return err
				}
			}
			s.step(5, "PY.cad is ready")
			if !o.NoLaunch {
				return launchCurrent(o.Root, p, nil)
			}
			return nil
		}
		s.note("The existing environment needs repair. Preparing a separate replacement.")
	}
	s.step(1, "Preparing a private workspace")
	name := "pycad-" + m.Version + "-" + nonce()[:12]
	release := filepath.Join(o.Root, "releases", name)
	if err = os.MkdirAll(filepath.Join(release, "app"), 0700); err != nil {
		return err
	}
	if err = extractPayload(payload, filepath.Join(release, "app")); err != nil {
		return err
	}
	if err = writeJSON(filepath.Join(release, "owner.json"), map[string]string{"application": "PyCAD", "version": m.Version}); err != nil {
		return err
	}
	s.step(2, "Setting up Python 3.12")
	uv, err := prepareUV(ctx, o.Root, p, m, s)
	if err != nil {
		return err
	}
	env := dependencyEnv(o.Root, p)
	if err = runWithTransfer(ctx, s, "Managed Python runtime", env, release, uv, "venv", "--python", m.Python, "--managed-python", filepath.Join(release, "env")); err != nil {
		return fmt.Errorf("Python setup could not finish. Check internet access to GitHub and retry. %w", err)
	}
	s.step(3, "Installing CAD dependencies")
	req := filepath.Join(appPath(release), "requirements-install-core.txt")
	if err = installPackages(ctx, s, env, release, uv, pyPath(release, p), req); err != nil {
		return fmt.Errorf("Core CAD package setup could not finish. Review the package error below and use Retry after resolving it. The previous installation is unchanged. %w", err)
	}
	if profile == "full" {
		s.note("Adding live 3D and IFC support. The first download can take several minutes.")
		req = filepath.Join(appPath(release), "requirements-install-full.txt")
		if err = installPackages(ctx, s, env, release, uv, pyPath(release, p), req); err != nil {
			return fmt.Errorf("3D/IFC dependencies could not be installed for this OS/CPU. The previous installation is unchanged. Retry after checking the log; --core-only is available for a 2D/BOQ/chat installation. %w", err)
		}
	}
	s.step(4, "Checking desktop libraries and application startup")
	if p.OS == "linux" {
		if err = ensureLinux(ctx, o, p, release, s); err != nil {
			return err
		}
	}
	err = checkWithRuntime(ctx, o.Root, release, p, profile, false, s)
	if err != nil {
		return err
	}
	if !o.NoLaunch {
		if err = checkWithRuntime(ctx, o.Root, release, p, profile, true, s); err != nil {
			return desktopError(err)
		}
	}
	// Commit only after all required packages, geometry and startup checks pass.
	if err = recordRuntimeLegal(ctx, release, p, s); err != nil {
		return err
	}
	if err = prepareWindowsIdentity(ctx, o.Root, release, profile, p, s); err != nil {
		return err
	}
	r := receipt{1, m.Version, name, m.PayloadSHA, p.Key(), profile}
	if err = installShortcuts(o.Root, p, s, release); err != nil {
		return err
	}
	if err = writeJSON(filepath.Join(o.Root, "current.json"), r); err != nil {
		return err
	}
	if p.OS == "windows" {
		if err = registerUninstaller(ctx, o.Root, m.Version, uninstallBefore, s); err != nil {
			return err
		}
	}
	s.step(5, "PY.cad is ready")
	if !o.NoLaunch {
		return launchCurrent(o.Root, p, nil)
	}
	return nil
}
func recordRuntimeLegal(ctx context.Context, release string, p platform, s *progress) error {
	s.note("Retaining installed dependency licenses and inventory")
	return run(ctx, s, cleanEnv(nil), release, pyPath(release, p), filepath.Join(appPath(release), "scripts", "export_legal_inventory.py"), "--output", filepath.Join(release, "runtime-legal"))
}
func desktopError(err error) error {
	return fmt.Errorf("The packages are installed, but the desktop startup check failed. Use a normal graphical desktop session; check the log for Qt/display/driver requirements. The previous installation remains selected. %w", err)
}
func extractPayload(data []byte, dest string) error {
	z, err := zip.NewReader(bytes.NewReader(data), int64(len(data)))
	if err != nil {
		return err
	}
	seen := map[string]bool{}
	var total uint64
	for _, f := range z.File {
		n := f.Name
		if !strings.HasPrefix(n, "PyCAD-v15/") || strings.Contains(n, "\\") || path.Clean(n) != strings.TrimSuffix(n, "/") || strings.ContainsAny(n, "\x00:") {
			return fmt.Errorf("Unsafe application archive path %q", n)
		}
		if f.Mode()&os.ModeSymlink != 0 || (!f.Mode().IsRegular() && !f.FileInfo().IsDir()) {
			return errors.New("Unsupported application archive entry")
		}
		if seen[n] {
			return errors.New("Duplicate application archive entry")
		}
		seen[n] = true
		total += f.UncompressedSize64
		if total > 256<<20 {
			return errors.New("Application payload exceeds its size limit")
		}
		target := filepath.Join(dest, filepath.FromSlash(n))
		if f.FileInfo().IsDir() {
			if err = os.MkdirAll(target, 0700); err != nil {
				return err
			}
			continue
		}
		if err = os.MkdirAll(filepath.Dir(target), 0700); err != nil {
			return err
		}
		src, e := f.Open()
		if e != nil {
			return e
		}
		mode := os.FileMode(0600)
		if f.Mode()&0111 != 0 {
			mode = 0700
		}
		dst, e := os.OpenFile(target, os.O_CREATE|os.O_WRONLY|os.O_EXCL, mode)
		if e != nil {
			src.Close()
			return e
		}
		_, e = io.Copy(dst, io.LimitReader(src, 256<<20))
		src.Close()
		e2 := dst.Close()
		if e != nil {
			return e
		}
		if e2 != nil {
			return e2
		}
	}
	if _, err = os.Stat(filepath.Join(dest, "PyCAD-v15", "main.py")); err != nil {
		return errors.New("Application payload is incomplete")
	}
	return nil
}
func download(ctx context.Context, client *http.Client, a asset, target string, monitor ...*progress) error {
	u, err := url.Parse(a.URL)
	if err != nil || u.Scheme != "https" || len(a.SHA) != 64 {
		return errors.New("Invalid trusted download descriptor")
	}
	if b, e := os.ReadFile(target); e == nil && digest(b) == a.SHA {
		return nil
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, a.URL, nil)
	if err != nil {
		return err
	}
	req.Header.Set("User-Agent", "PY.cad-Setup")
	var state *progress
	if len(monitor) > 0 {
		state = monitor[0]
	}
	const label = "UV runtime bootstrap"
	if state != nil {
		state.transfer(label, 0, 0, true)
		defer state.transfer(label, 0, 0, false)
	}
	response, err := client.Do(req)
	if err != nil {
		return err
	}
	defer response.Body.Close()
	if response.StatusCode != 200 {
		return fmt.Errorf("Download returned HTTP %d", response.StatusCode)
	}
	reader := io.Reader(response.Body)
	if state != nil {
		reader = &countedDownload{reader: reader, state: state, total: response.ContentLength}
	}
	b, err := io.ReadAll(io.LimitReader(reader, (128<<20)+1))
	if err != nil {
		return err
	}
	if len(b) > 128<<20 {
		return errors.New("Download exceeds its size limit")
	}
	if digest(b) != a.SHA {
		return errors.New("Download checksum mismatch; nothing was executed")
	}
	tmp := target + "." + nonce() + ".tmp"
	if err = os.WriteFile(tmp, b, 0600); err != nil {
		return err
	}
	defer os.Remove(tmp)
	return os.Rename(tmp, target)
}
func prepareUV(ctx context.Context, root string, p platform, m manifest, s *progress) (string, error) {
	a, ok := m.Assets[p.Key()]
	if !ok {
		return "", errors.New("No runtime bootstrap is available for this OS/CPU")
	}
	dir := filepath.Join(root, "tools")
	if err := os.MkdirAll(dir, 0700); err != nil {
		return "", err
	}
	archive := filepath.Join(dir, "uv-"+m.UVVersion+"-"+p.Key()+path.Ext(a.URL))
	s.note("Checking the verified runtime bootstrap")
	client := &http.Client{Timeout: 10 * time.Minute, CheckRedirect: func(req *http.Request, via []*http.Request) error {
		if req.URL.Scheme != "https" || len(via) > 8 {
			return errors.New("Unsafe download redirect")
		}
		return nil
	}}
	if err := download(ctx, client, a, archive, s); err != nil {
		return "", fmt.Errorf("Could not download the verified runtime bootstrap: %w", err)
	}
	raw, err := os.ReadFile(archive)
	if err != nil {
		return "", err
	}
	binary, err := uvBinary(raw, p.OS == "windows")
	if err != nil {
		return "", err
	}
	exe := filepath.Join(dir, "uv-"+m.UVVersion+"-"+p.Key())
	if p.OS == "windows" {
		exe += ".exe"
	}
	if old, e := os.ReadFile(exe); e != nil || digest(old) != digest(binary) {
		if err = os.WriteFile(exe, binary, 0700); err != nil {
			return "", err
		}
	}
	return exe, nil
}
func uvBinary(raw []byte, windows bool) ([]byte, error) {
	var found []byte
	read := func(r io.Reader) error {
		b, e := io.ReadAll(io.LimitReader(r, (100<<20)+1))
		if e != nil {
			return e
		}
		if len(b) > 100<<20 {
			return errors.New("Runtime binary exceeds size limit")
		}
		if found != nil {
			return errors.New("Duplicate runtime binary")
		}
		found = b
		return nil
	}
	if windows {
		z, e := zip.NewReader(bytes.NewReader(raw), int64(len(raw)))
		if e != nil {
			return nil, e
		}
		for _, f := range z.File {
			if path.Base(f.Name) == "uv.exe" && f.Mode()&os.ModeSymlink == 0 {
				r, e := f.Open()
				if e != nil {
					return nil, e
				}
				e = read(r)
				r.Close()
				if e != nil {
					return nil, e
				}
			}
		}
	} else {
		g, e := gzip.NewReader(bytes.NewReader(raw))
		if e != nil {
			return nil, e
		}
		defer g.Close()
		t := tar.NewReader(g)
		for {
			h, e := t.Next()
			if e == io.EOF {
				break
			}
			if e != nil {
				return nil, e
			}
			if path.Base(h.Name) == "uv" && h.Typeflag == tar.TypeReg {
				if e = read(t); e != nil {
					return nil, e
				}
			}
		}
	}
	if len(found) == 0 {
		return nil, errors.New("Runtime binary is missing")
	}
	return found, nil
}

func needsWindowsRuntime(s *progress) bool {
	s.mu.Lock()
	file := s.logfile
	text, current := strings.ToLower(s.lastOutput), s.haveCommand
	s.mu.Unlock()
	if current {
		return strings.Contains(text, "dll load failed") || strings.Contains(text, "vcruntime") || strings.Contains(text, "0xc0000135")
	}
	data, err := os.ReadFile(file)
	if err != nil {
		return false
	}
	if len(data) > 16000 {
		data = data[len(data)-16000:]
	}
	text = strings.ToLower(string(data))
	return strings.Contains(text, "dll load failed") || strings.Contains(text, "vcruntime") || strings.Contains(text, "0xc0000135")
}
