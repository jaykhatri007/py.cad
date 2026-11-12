package main

import (
	"context"
	_ "embed"
	"encoding/base64"
	"encoding/binary"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"sort"
	"strconv"
	"strings"
	"unicode/utf16"
)

type platform struct{ OS, Arch, Label, ArchLabel string }

func (p platform) Key() string { return p.OS + "-" + p.Arch }
func detect(goos, arch string) (platform, error) {
	p := platform{OS: goos, Arch: arch}
	switch goos {
	case "windows":
		p.Label = "Windows"
		if arch != "amd64" {
			return p, errors.New("This Windows release needs 64-bit Intel/AMD Windows. ARM64 Windows is not qualified")
		}
	case "darwin":
		p.Label = "macOS"
	case "linux":
		p.Label = "Linux"
	default:
		return p, errors.New("PY.cad Setup supports Windows, macOS and desktop Linux")
	}
	switch arch {
	case "amd64":
		p.ArchLabel = "Intel / AMD 64-bit"
	case "arm64":
		p.ArchLabel = "ARM64 / Apple Silicon"
	default:
		return p, errors.New("PY.cad Setup needs a 64-bit x86 or ARM processor")
	}
	return p, nil
}
func defaultRoot(goos string) (string, error) {
	home, err := os.UserHomeDir()
	if err != nil {
		return "", err
	}
	switch goos {
	case "windows":
		base := os.Getenv("ProgramW6432")
		if base == "" {
			base = os.Getenv("ProgramFiles")
		}
		if base == "" {
			base = `C:\Program Files`
		}
		return filepath.Join(base, "PY.cad"), nil
	case "darwin":
		return filepath.Join(home, "Library", "Application Support", "PyCAD", "Installation"), nil
	default:
		base := os.Getenv("XDG_DATA_HOME")
		if !filepath.IsAbs(base) {
			base = filepath.Join(home, ".local", "share")
		}
		return filepath.Join(base, "pycad", "installation"), nil
	}
}
func preflight(p platform, o options) error {
	if strings.ContainsAny(o.Root, "\r\n\t") {
		return errors.New("The installation path cannot contain line breaks or tabs")
	}
	if p.OS == "linux" {
		if p.Arch != "amd64" && !o.CoreOnly {
			return errors.New("This full Linux build requires Intel/AMD x64. Linux ARM64 3D kernel wheels are not available in the pinned release")
		}
		output, err := exec.Command("getconf", "GNU_LIBC_VERSION").Output()
		if err != nil {
			return errors.New("This Linux setup requires a glibc desktop distribution; musl/Alpine is not supported")
		}
		fields := strings.Fields(string(output))
		if len(fields) != 2 {
			return errors.New("Cannot detect the Linux glibc version")
		}
		numbers := strings.Split(fields[1], ".")
		if len(numbers) < 2 {
			return errors.New("Cannot detect the Linux glibc version")
		}
		major, _ := strconv.Atoi(numbers[0])
		minor, _ := strconv.Atoi(numbers[1])
		minimum := 34
		if p.Arch == "arm64" {
			minimum = 39
		}
		if major < 2 || (major == 2 && minor < minimum) {
			return fmt.Errorf("This Qt build needs glibc 2.%d or later. Update the Linux distribution before installing", minimum)
		}
	}
	if p.OS == "darwin" {
		b, e := exec.Command("/usr/bin/sw_vers", "-productVersion").Output()
		if e != nil {
			return e
		}
		major, e := strconv.Atoi(strings.Split(strings.TrimSpace(string(b)), ".")[0])
		if e != nil || major < 13 {
			return errors.New("This setup targets macOS 13 or later")
		}
	}
	if p.OS == "linux" && !o.NoLaunch && os.Getenv("DISPLAY") == "" && os.Getenv("WAYLAND_DISPLAY") == "" {
		return errors.New("Open Setup from your graphical desktop session. No X11/Wayland display was detected")
	}
	return nil
}
func openURL(url string) error {
	var cmd *exec.Cmd
	switch runtime.GOOS {
	case "windows":
		cmd = exec.Command("rundll32.exe", "url.dll,FileProtocolHandler", url)
	case "darwin":
		cmd = exec.Command("/usr/bin/open", url)
	default:
		cmd = exec.Command("xdg-open", url)
	}
	hideConsole(cmd)
	return cmd.Run()
}
func shellQuote(s string) string { return "'" + strings.ReplaceAll(s, "'", "'\"'\"'") + "'" }
func psQuote(s string) string    { return "'" + strings.ReplaceAll(s, "'", "''") + "'" }
func encodedPS(script string) string {
	r := utf16.Encode([]rune(script))
	b := make([]byte, len(r)*2)
	for i, v := range r {
		binary.LittleEndian.PutUint16(b[i*2:], v)
	}
	return base64.StdEncoding.EncodeToString(b)
}
func windowsQuote(s string) string {
	var b strings.Builder
	b.WriteByte('"')
	slashes := 0
	for _, r := range s {
		if r == '\\' {
			slashes++
			continue
		}
		if r == '"' {
			b.WriteString(strings.Repeat("\\", slashes*2+1))
		} else {
			b.WriteString(strings.Repeat("\\", slashes))
		}
		slashes = 0
		b.WriteRune(r)
	}
	b.WriteString(strings.Repeat("\\", slashes*2))
	b.WriteByte('"')
	return b.String()
}
func desktopQuote(s string) string {
	s = strings.ReplaceAll(s, "%", "%%")
	for _, c := range []string{"\\", "\"", "`", "$"} {
		s = strings.ReplaceAll(s, c, "\\"+c)
	}
	return "\"" + s + "\""
}
func copySelf(root string, p platform) (string, error) {
	self, err := os.Executable()
	if err != nil {
		return "", err
	}
	if p.OS == "windows" {
		return stageWindowsLauncher(root, self)
	}
	target := filepath.Join(root, "PyCAD")
	if p.OS == "windows" {
		target += ".exe"
	}
	if same, err := filepath.EvalSymlinks(self); err == nil && same == target {
		return target, nil
	}
	src, err := os.Open(self)
	if err != nil {
		return "", err
	}
	defer src.Close()
	temp := target + "." + nonce() + ".tmp"
	dst, err := os.OpenFile(temp, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0700)
	if err != nil {
		return "", err
	}
	defer os.Remove(temp)
	_, err = io.Copy(dst, src)
	e := dst.Close()
	if err != nil {
		return "", err
	}
	if e != nil {
		return "", e
	}
	if err = os.Rename(temp, target); err != nil {
		return "", err
	}
	return target, nil
}
func stageWindowsLauncher(root, source string) (string, error) {
	data, err := os.ReadFile(source)
	if err != nil {
		return "", err
	}
	dir := filepath.Join(root, "launchers")
	if err = os.MkdirAll(dir, 0700); err != nil {
		return "", err
	}
	// Windows cannot replace a running executable. Keep launchers immutable;
	// upgrades and repair select a new content-addressed executable instead.
	target := filepath.Join(dir, "pycad-"+digest(data)[:20]+".exe")
	if old, e := os.ReadFile(target); e == nil {
		if digest(old) != digest(data) {
			return "", errors.New("Cached launcher failed its integrity check")
		}
		return target, nil
	} else if !os.IsNotExist(e) {
		return "", e
	}
	temp := target + "." + nonce() + ".tmp"
	if err = os.WriteFile(temp, data, 0700); err != nil {
		return "", err
	}
	defer os.Remove(temp)
	if err = os.Rename(temp, target); err != nil {
		return "", err
	}
	return target, nil
}

func installShortcuts(root string, p platform, s *progress, releases ...string) error {
	icons, err := installBrandIcons(root)
	if err != nil {
		return err
	}
	exe, err := copySelf(root, p)
	if err != nil {
		return err
	}
	home, err := os.UserHomeDir()
	if err != nil {
		return err
	}
	switch p.OS {
	case "windows":
		release := ""
		if len(releases) > 0 {
			release = releases[0]
		} else {
			receipt, e := loadReceipt(root)
			if e != nil {
				return e
			}
			release = filepath.Join(root, "releases", receipt.Release)
		}
		return runWindowsShortcuts(context.Background(), root, release, exe, icons)
	case "darwin":
		bundle := filepath.Join(home, "Applications", "PY.cad.app")
		if err = migrateManagedBundle(filepath.Join(home, "Applications", "PyCAD.app"), bundle); err != nil {
			return err
		}
		marker := filepath.Join(bundle, "Contents", "PyCAD-Managed.txt")
		if info, e := os.Lstat(bundle); e == nil {
			if !info.IsDir() || info.Mode()&os.ModeSymlink != 0 {
				return errors.New("The PY.cad.app launcher location is not a real managed directory")
			}
			if b, e := os.ReadFile(marker); e != nil || string(b) != "PyCAD managed installation\n" {
				return errors.New("An unmanaged ~/Applications/PY.cad.app already exists. Rename it before installing this managed build")
			}
		}
		macos := filepath.Join(bundle, "Contents", "MacOS")
		if err = os.MkdirAll(macos, 0700); err != nil {
			return err
		}
		resources := filepath.Join(bundle, "Contents", "Resources")
		if err = os.MkdirAll(resources, 0700); err != nil {
			return err
		}
		if err = os.WriteFile(filepath.Join(resources, "pycad.icns"), macIcon, 0600); err != nil {
			return err
		}
		plist := `<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd"><plist version="1.0"><dict><key>CFBundleName</key><string>PY.cad</string><key>CFBundleDisplayName</key><string>PY.cad</string><key>CFBundleIdentifier</key><string>org.pycad.desktop</string><key>CFBundleExecutable</key><string>PyCAD</string><key>CFBundlePackageType</key><string>APPL</string><key>LSMinimumSystemVersion</key><string>13.0</string><key>NSHighResolutionCapable</key><true/></dict></plist>`
		plist = strings.Replace(plist, "<key>CFBundleName</key>", "<key>CFBundleIconFile</key><string>pycad.icns</string><key>CFBundleName</key>", 1)
		if err = os.WriteFile(filepath.Join(bundle, "Contents", "Info.plist"), []byte(plist), 0600); err != nil {
			return err
		}
		script := "#!/bin/sh\nexec " + shellQuote(exe) + " --root " + shellQuote(root) + " --launch \"$@\"\n"
		if err = os.WriteFile(filepath.Join(macos, "PyCAD"), []byte(script), 0700); err != nil {
			return err
		}
		return os.WriteFile(marker, []byte("PyCAD managed installation\n"), 0600)
	default:
		data := os.Getenv("XDG_DATA_HOME")
		if !filepath.IsAbs(data) {
			data = filepath.Join(home, ".local", "share")
		}
		folder := filepath.Join(data, "applications")
		if err = os.MkdirAll(folder, 0700); err != nil {
			return err
		}
		// Desktop Entry string escaping is applied after Exec argument quoting.
		command := desktopQuote(exe) + " --root " + desktopQuote(root) + " --launch"
		command = strings.ReplaceAll(command, "\\", "\\\\")
		entry := "[Desktop Entry]\nType=Application\nName=PY.cad\nComment=Architecture and CAD drafting\nExec=" + command + "\nTerminal=false\nCategories=Graphics;Engineering;\nStartupNotify=true\n"
		entry += "Icon=" + strings.ReplaceAll(filepath.Join(icons, "pycad.png"), "\\", "\\\\") + "\nStartupWMClass=PY.cad\n"
		uninstallAction, uninstallErr := installLinuxUninstall(root, folder, filepath.Join(icons, "pycad.png"))
		if uninstallErr != nil {
			s.note("Could not add the graphical uninstall shortcut: " + uninstallErr.Error())
		} else {
			entry += uninstallAction
		}
		if err = os.WriteFile(filepath.Join(folder, "pycad-managed.desktop"), []byte(entry), 0700); err != nil {
			return err
		}
		s.note("Added PY.cad to the Applications menu")
	}
	return nil
}
func launchCurrent(root string, p platform, args []string) error {
	r, err := loadReceipt(root)
	if err != nil {
		return err
	}
	if r.Platform != p.Key() {
		return errors.New("The installed environment belongs to another OS/CPU")
	}
	release := filepath.Join(root, "releases", r.Release)
	// Fast import check catches a removed/broken runtime before showing an empty app.
	ctx, cancel := context.WithTimeout(context.Background(), 90*1e9)
	defer cancel()
	logdir := filepath.Join(root, "logs")
	if p.OS == "windows" {
		cache, e := os.UserCacheDir()
		if e != nil {
			return e
		}
		logdir = filepath.Join(cache, "PY.cad", "logs")
	}
	if err = os.MkdirAll(logdir, 0700); err != nil {
		return err
	}
	log, err := os.OpenFile(filepath.Join(logdir, "application.log"), os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0600)
	if err != nil {
		return err
	}
	defer log.Close()
	s := newState(p, r.Version, root)
	s.setLog(log, filepath.Join(logdir, "application.log"))
	if err = check(ctx, release, p, r.Profile, true, s); err != nil {
		return err
	}
	program := pyPath(release, p)
	arguments := append([]string{filepath.Join(appPath(release), "main.py")}, args...)
	if p.OS == "windows" {
		extra := append([]string{"--"}, args...)
		program, arguments, err = windowsAppCommand(root, release, extra)
		if err != nil {
			return err
		}
	}
	command := exec.Command(program, arguments...)
	command.Dir = appPath(release)
	command.Env = cleanEnv(map[string]string{"PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1"})
	command.Stdout = log
	command.Stderr = log
	detach(command)
	if err = command.Start(); err != nil {
		return err
	}
	return command.Process.Release()
}

// Each soname maps to runtime (not development) packages. Actual Qt ldd results
// are checked as well, so a distribution-specific missing library is visible.
var qtLibraries = map[string][4]string{
	"libGL.so.1":              {"libgl1", "libglvnd-glx", "libglvnd", "libGL1"},
	"libEGL.so.1":             {"libegl1", "libglvnd-egl", "libglvnd", "libEGL1"},
	"libfontconfig.so.1":      {"libfontconfig1", "fontconfig", "fontconfig", "libfontconfig1"},
	"libxkbcommon-x11.so.0":   {"libxkbcommon-x11-0", "libxkbcommon-x11", "libxkbcommon-x11", "libxkbcommon-x11-0"},
	"libxcb-cursor.so.0":      {"libxcb-cursor0", "xcb-util-cursor", "xcb-util-cursor", "libxcb-cursor0"},
	"libxcb-icccm.so.4":       {"libxcb-icccm4", "xcb-util-wm", "xcb-util-wm", "libxcb-icccm4"},
	"libxcb-image.so.0":       {"libxcb-image0", "xcb-util-image", "xcb-util-image", "libxcb-image0"},
	"libxcb-keysyms.so.1":     {"libxcb-keysyms1", "xcb-util-keysyms", "xcb-util-keysyms", "libxcb-keysyms1"},
	"libxcb-render-util.so.0": {"libxcb-render-util0", "xcb-util-renderutil", "xcb-util-renderutil", "libxcb-render-util0"},
	"libxcb-xinerama.so.0":    {"libxcb-xinerama0", "libxcb", "libxcb", "libxcb-xinerama0"},
	"libxcb-xkb.so.1":         {"libxcb-xkb1", "libxcb", "libxcb", "libxcb-xkb1"},
	"libX11-xcb.so.1":         {"libx11-xcb1", "libX11-xcb", "libx11", "libX11-xcb1"},
	"libSM.so.6":              {"libsm6", "libSM", "libsm", "libSM6"},
	"libICE.so.6":             {"libice6", "libICE", "libice", "libICE6"},
}

func ensureLinux(ctx context.Context, o options, p platform, release string, s *progress) error {
	var libs []string
	for lib := range qtLibraries {
		libs = append(libs, lib)
	}
	data, _ := jsonMarshal(libs)
	script := "import ctypes,json; missing=[]\nfor name in " + string(data) + ":\n try: ctypes.CDLL(name)\n except OSError: missing.append(name)\nprint(json.dumps(missing))"
	probe := exec.CommandContext(ctx, pyPath(release, p), "-c", script)
	probe.Env = cleanEnv(nil)
	b, err := probe.Output()
	if err != nil {
		return err
	}
	var missing []string
	if err = jsonUnmarshal(b, &missing); err != nil {
		return err
	}
	if len(missing) > 0 {
		raw, _ := os.ReadFile("/etc/os-release")
		manager, packages, e := linuxPackages(string(raw), missing)
		if e != nil {
			return e
		}
		s.note("Desktop libraries needed: " + strings.Join(packages, ", "))
		if o.NoSystem {
			return fmt.Errorf("Missing desktop packages: %s. System package installation was disabled", strings.Join(packages, ", "))
		}
		if _, e = exec.LookPath("pkexec"); e != nil {
			return fmt.Errorf("This desktop has no graphical administrator helper (pkexec). Install these %s packages, then run Setup again: %s", manager, strings.Join(packages, " "))
		}
		s.note("Approve your operating system's administrator dialog to add desktop libraries")
		binary, e := exec.LookPath(manager)
		if e != nil {
			return e
		}
		if manager == "apt-get" {
			if e = runWithTransfer(ctx, s, "System package indexes", os.Environ(), "", "pkexec", binary, "update"); e != nil {
				return e
			}
		}
		args := []string{binary}
		switch manager {
		case "apt-get":
			args = append(args, "install", "-y")
		case "dnf":
			args = append(args, "install", "-y")
		case "pacman":
			args = append(args, "-S", "--needed", "--noconfirm")
		case "zypper":
			args = append(args, "--non-interactive", "install")
		}
		args = append(args, packages...)
		if e = runWithTransfer(ctx, s, "Desktop libraries: "+strings.Join(packages, ", "), os.Environ(), "", "pkexec", args...); e != nil {
			return fmt.Errorf("Desktop package installation was cancelled or failed. Approve the OS authorization request and retry. %w", e)
		}
	}
	code := `from PyQt6.QtCore import QLibraryInfo
from pathlib import Path
print(Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.PluginsPath))/'platforms'/'libqxcb.so')`
	cmd := exec.CommandContext(ctx, pyPath(release, p), "-c", code)
	cmd.Env = cleanEnv(nil)
	b, err = cmd.Output()
	if err != nil {
		return err
	}
	ld := exec.CommandContext(ctx, "ldd", strings.TrimSpace(string(b)))
	output, err := ld.CombinedOutput()
	if err != nil {
		return fmt.Errorf("Could not inspect Qt desktop libraries: %s", output)
	}
	if strings.Contains(string(output), "not found") {
		s.note(string(output))
		return errors.New("Qt still reports missing desktop libraries; their names are in the log. Install the distribution equivalents and retry")
	}
	return nil
}

// indirections keep encoding imports and platform planning testable without OS mutations.
var jsonMarshal = json.Marshal
var jsonUnmarshal = json.Unmarshal

func linuxPackages(release string, missing []string) (string, []string, error) {
	values := map[string]string{}
	for _, line := range strings.Split(release, "\n") {
		k, v, ok := strings.Cut(line, "=")
		if ok {
			values[k] = strings.Trim(v, "\"'")
		}
	}
	ids := strings.Fields(values["ID"] + " " + values["ID_LIKE"])
	manager := ""
	index := 0
	for _, id := range ids {
		switch id {
		case "ubuntu", "debian", "linuxmint", "pop":
			manager = "apt-get"
			index = 0
		case "fedora", "rhel", "centos":
			manager = "dnf"
			index = 1
		case "arch", "manjaro":
			manager = "pacman"
			index = 2
		case "opensuse", "opensuse-leap", "opensuse-tumbleweed", "suse":
			manager = "zypper"
			index = 3
		}
		if manager != "" {
			break
		}
	}
	if manager == "" {
		return "", nil, fmt.Errorf("Automatic desktop package setup does not recognize this Linux distribution. Install Qt/XCB runtime libraries and retry. Missing: %s", strings.Join(missing, ", "))
	}
	seen := map[string]bool{}
	var packages []string
	for _, name := range missing {
		p, ok := qtLibraries[name]
		if !ok {
			return "", nil, fmt.Errorf("Unknown desktop dependency %s", name)
		}
		if !seen[p[index]] {
			seen[p[index]] = true
			packages = append(packages, p[index])
		}
	}
	sort.Strings(packages)
	return manager, packages, nil
}

//go:embed repair-runtime.ps1
var windowsRuntimePS []byte

func repairWindowsRuntime(ctx context.Context, root string, s *progress) error {
	s.note("Checking the Microsoft Visual C++ runtime after a dependency import failure")
	file := filepath.Join(root, "tools", "vc_redist.x64.exe")
	// Microsoft services this stable URL. Verify Authenticode before executing it.
	script := "$pycadRuntimeFile=" + psQuote(file) + ";\n" + string(windowsRuntimePS)
	return runWithTransfer(ctx, s, "Microsoft Visual C++ runtime", cleanEnv(nil), root, "powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encodedPS(script))
}

// Preserve an owned legacy launcher bundle by moving it; never overwrite either
// an existing new-name bundle or an unrelated old-name application.
func migrateManagedBundle(oldPath, newPath string) error {
	if _, err := os.Lstat(newPath); err == nil {
		return nil
	} else if !os.IsNotExist(err) {
		return err
	}
	info, err := os.Lstat(oldPath)
	if os.IsNotExist(err) {
		return nil
	}
	if err != nil {
		return err
	}
	if !info.IsDir() || info.Mode()&os.ModeSymlink != 0 {
		return nil
	}
	marker := filepath.Join(oldPath, "Contents", "PyCAD-Managed.txt")
	data, err := os.ReadFile(marker)
	if err != nil || string(data) != "PyCAD managed installation\n" {
		return nil
	}
	return os.Rename(oldPath, newPath)
}
