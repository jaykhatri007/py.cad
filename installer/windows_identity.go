package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

type windowsAppIdentity struct {
	Format int    `json:"format"`
	Name   string `json:"name"`
	Host   string `json:"host"`
	SHA    string `json:"sha256"`
}

func windowsAppCommand(root, release string, args []string) (string, []string, error) {
	data, err := os.ReadFile(filepath.Join(release, "windows-app.json"))
	if err != nil {
		return "", nil, err
	}
	var identity windowsAppIdentity
	if err = json.Unmarshal(data, &identity); err != nil {
		return "", nil, err
	}
	relative, err := filepath.Rel(filepath.Join(root, "python"), identity.Host)
	if err != nil || relative == ".." || strings.HasPrefix(relative, ".."+string(filepath.Separator)) || filepath.IsAbs(relative) ||
		identity.Format != 1 || identity.Name != "PY.cad" || !strings.HasPrefix(filepath.Base(identity.Host), "PY.cad-") || !strings.HasSuffix(identity.Host, ".exe") {
		return "", nil, errors.New("Invalid PY.cad Windows runtime identity; run Setup to repair")
	}
	executable, err := os.ReadFile(identity.Host)
	if err != nil {
		return "", nil, err
	}
	if digest(executable) != identity.SHA {
		return "", nil, errors.New("PY.cad Windows runtime integrity check failed; run Setup to repair")
	}
	arguments := []string{filepath.Join(appPath(release), "scripts", "windows_app_start.py"), "--env", filepath.Join(release, "env"), "--main", filepath.Join(appPath(release), "main.py")}
	return identity.Host, append(arguments, args...), nil
}

func prepareWindowsIdentity(ctx context.Context, root, release, profile string, p platform, s *progress) error {
	if p.OS != "windows" {
		return nil
	}
	s.note("Preparing PY.cad process name, logo and Windows application identity")
	env := cleanEnv(map[string]string{"PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1"})
	if err := run(ctx, s, env, appPath(release), pyPath(release, p), filepath.Join(appPath(release), "scripts", "prepare_windows_identity.py"), "--root", root, "--release", release); err != nil {
		return err
	}
	host, args, err := windowsAppCommand(root, release, nil)
	if err != nil {
		return err
	}
	temporary, err := os.MkdirTemp("", "pycad-identity-check-")
	if err != nil {
		return err
	}
	defer os.RemoveAll(temporary)
	output := filepath.Join(temporary, "result.json")
	args = append(args, "--probe", output)
	if profile == "full" {
		args = append(args, "--full")
	}
	env = cleanEnv(map[string]string{"PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1", "QT_QPA_PLATFORM": "offscreen", "PYCAD_DATA_DIR": temporary})
	if err = run(ctx, s, env, appPath(release), host, args...); err != nil {
		if data, e := os.ReadFile(output); e == nil {
			var detail struct {
				Error string `json:"error"`
			}
			if json.Unmarshal(data, &detail) == nil && detail.Error != "" {
				return fmt.Errorf("PY.cad branded runtime check: %s", detail.Error)
			}
		}
		return fmt.Errorf("PY.cad branded runtime check failed: %w", err)
	}
	data, err := os.ReadFile(output)
	if err != nil {
		return err
	}
	var result struct {
		Name  string `json:"name"`
		Host  string `json:"host"`
		AppID string `json:"app_id"`
	}
	if err = json.Unmarshal(data, &result); err != nil {
		return err
	}
	if result.Name != "PY.cad" || !strings.EqualFold(filepath.Clean(result.Host), filepath.Clean(host)) || result.AppID != "JayKhatri.PYcad.Desktop" {
		return errors.New("The branded runtime returned an unexpected process identity")
	}
	return nil
}

func runWindowsShortcuts(ctx context.Context, root, release, launcher, icons string) error {
	command := exec.CommandContext(ctx, pyPath(release, platform{OS: "windows"}), filepath.Join(appPath(release), "scripts", "windows_shortcuts.py"), "--root", root, "--launcher", launcher, "--icons", icons)
	command.Dir = appPath(release)
	command.Env = cleanEnv(map[string]string{"PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1"})
	hideConsole(command)
	if output, err := command.CombinedOutput(); err != nil {
		return fmt.Errorf("Create PY.cad Desktop and Start-menu shortcuts: %w: %s", err, string(output))
	}
	return nil
}
