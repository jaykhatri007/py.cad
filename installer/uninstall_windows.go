//go:build windows

package main

import (
	"context"
	"crypto/sha256"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"syscall"
	"unsafe"
)

func isUninstallLink(info os.FileInfo) bool {
	if info.Mode()&os.ModeSymlink != 0 {
		return true
	}
	data, ok := info.Sys().(*syscall.Win32FileAttributeData)
	return ok && data.FileAttributes&syscall.FILE_ATTRIBUTE_REPARSE_POINT != 0
}

func uninstallRegistryKey(root string) string {
	digest := sha256.Sum256([]byte(strings.ToLower(filepath.Clean(root))))
	return fmt.Sprintf(`Software\Microsoft\Windows\CurrentVersion\Uninstall\PY.cad-%x`, digest[:8])
}

func uninstallRegistrationScript(root, version string) string {
	exe := filepath.Join(root, uninstallExeName)
	command := windowsQuote(exe) + " --uninstall --root " + windowsQuote(root)
	return `$ErrorActionPreference='Stop';
$key=[Microsoft.Win32.Registry]::CurrentUser.CreateSubKey(` + psQuote(uninstallRegistryKey(root)) + `);
try {
 $key.SetValue('DisplayName','PY.cad');
 $key.SetValue('DisplayVersion',` + psQuote(version) + `);
 $key.SetValue('Publisher','Jay Kundanlal Khatri');
 $key.SetValue('InstallLocation',` + psQuote(root) + `);
 $key.SetValue('DisplayIcon',` + psQuote(filepath.Join(root, "icons", "pycad.ico")) + `);
 $key.SetValue('UninstallString',` + psQuote(command) + `);
 $key.SetValue('NoModify',1,[Microsoft.Win32.RegistryValueKind]::DWord);
 $key.SetValue('NoRepair',1,[Microsoft.Win32.RegistryValueKind]::DWord);
} finally { $key.Dispose() };
$folder=[Environment]::GetFolderPath('Programs');
$shell=New-Object -ComObject WScript.Shell;
$shortcut=$shell.CreateShortcut([IO.Path]::Combine($folder,'Uninstall PY.cad.lnk'));
$shortcut.TargetPath=` + psQuote(exe) + `;
$shortcut.Arguments=` + psQuote("--uninstall --root "+windowsQuote(root)) + `;
$shortcut.IconLocation=` + psQuote(filepath.Join(root, "icons", "pycad.ico")+",0") + `;
$shortcut.Description='Uninstall PY.cad (keeps drawings and settings)';
$shortcut.Save();`
}

func uninstallCleanupScript(root string) string {
	return `$ErrorActionPreference='Stop';
$root=` + psQuote(root) + `;
$prefix=$root.TrimEnd('\')+'\';
$keyName=` + psQuote(uninstallRegistryKey(root)) + `;
$key=[Microsoft.Win32.Registry]::CurrentUser.OpenSubKey($keyName);
if($null -ne $key) {
 try { $location=[string]$key.GetValue('InstallLocation') } finally { $key.Dispose() };
 if(-not [string]::Equals($location,$root,[StringComparison]::OrdinalIgnoreCase)){throw 'The installed-apps entry belongs to another location'};
};
$shell=New-Object -ComObject WScript.Shell;
foreach($folder in @([Environment]::GetFolderPath('Programs'),[Environment]::GetFolderPath('DesktopDirectory'))) {
 foreach($name in @('PY.cad.lnk','PyCAD.lnk','Uninstall PY.cad.lnk')) {
  $path=[IO.Path]::Combine($folder,$name);
  if(Test-Path -LiteralPath $path) {
   $shortcut=$shell.CreateShortcut($path);
   if($shortcut.TargetPath.StartsWith($prefix,[StringComparison]::OrdinalIgnoreCase)){Remove-Item -LiteralPath $path};
  }
 }
};
if($null -ne $key){[Microsoft.Win32.Registry]::CurrentUser.DeleteSubKeyTree($keyName,$false)};`
}

func registerUninstaller(ctx context.Context, root, version string, before map[string]bool, s *progress) error {
	s.note("Preparing the built-in Windows uninstaller and file ownership inventory")
	source, err := os.Executable()
	if err != nil {
		return err
	}
	data, err := os.ReadFile(source)
	if err != nil {
		return err
	}
	target := filepath.Join(root, uninstallExeName)
	if _, err = checkedUninstallPath(root, uninstallExeName); err != nil {
		return err
	}
	tmp := target + "." + nonce() + ".tmp"
	if err = os.WriteFile(tmp, data, 0700); err != nil {
		return err
	}
	defer os.Remove(tmp)
	if err = os.Rename(tmp, target); err != nil {
		return err
	}
	if err = saveUninstallInventory(ctx, root, before); err != nil {
		return err
	}
	return run(ctx, s, cleanEnv(nil), root, "powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encodedPS(uninstallRegistrationScript(root, version)))
}

func uninstallPowerShell(ctx context.Context, script string) error {
	cmd := exec.CommandContext(ctx, "powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encodedPS(script))
	hideConsole(cmd)
	output, err := cmd.CombinedOutput()
	if err != nil {
		return fmt.Errorf("Windows uninstall: %w\n%s", err, output)
	}
	return nil
}

func uninstallConfirmation(root string) bool {
	answer, _, _ := setupUser.NewProc("MessageBoxW").Call(0,
		uintptr(unsafe.Pointer(winText("Remove PY.cad from this Windows account?\n\nClose PY.cad first.\n\n"+root+"\n\nDrawings, settings, and untracked or modified files will be kept. Shared Microsoft runtimes are not removed.\n\nContinue?"))),
		uintptr(unsafe.Pointer(winText("Uninstall PY.cad"))), 0x124) // YESNO, question, default No
	return answer == 6
}

func runUninstaller(root string, worker bool, parent int) error {
	inventory, err := loadUninstallInventory(root)
	if err != nil {
		return err
	}
	if !worker {
		// A running Windows executable cannot remove itself. Run an identical
		// private copy outside the installation, and wait for this parent to exit.
		dir, err := os.MkdirTemp("", "PYcad-uninstall-")
		if err != nil {
			return err
		}
		source, err := os.Executable()
		if err != nil {
			_ = os.Remove(dir)
			return err
		}
		data, err := os.ReadFile(source)
		if err != nil {
			_ = os.Remove(dir)
			return err
		}
		helper := filepath.Join(dir, uninstallExeName)
		if err = os.WriteFile(helper, data, 0700); err != nil {
			_ = os.Remove(dir)
			return err
		}
		cmd := exec.Command(helper, "--uninstall-worker", "--root", root, "--uninstall-parent", fmt.Sprint(os.Getpid()))
		detach(cmd)
		if err = cmd.Start(); err != nil {
			_ = os.Remove(helper)
			_ = os.Remove(dir)
			return err
		}
		_ = cmd.Process.Release()
		return nil
	}
	source, err := os.Executable()
	if err != nil {
		return err
	}
	// Cleanup only a helper actually running in our private temporary folder.
	tempRoot, err := filepath.Rel(os.TempDir(), filepath.Dir(source))
	if err == nil && !strings.ContainsAny(tempRoot, `/\`) && strings.HasPrefix(tempRoot, "PYcad-uninstall-") {
		cleanup := `Wait-Process -Id ` + fmt.Sprint(os.Getpid()) + ` -ErrorAction SilentlyContinue; Remove-Item -LiteralPath ` + psQuote(source) + ` -ErrorAction SilentlyContinue; Remove-Item -LiteralPath ` + psQuote(filepath.Dir(source)) + ` -ErrorAction SilentlyContinue`
		cmd := exec.Command("powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encodedPS(cleanup))
		detach(cmd)
		if cmd.Start() == nil {
			_ = cmd.Process.Release()
		}
	}
	if parent > 0 {
		h, _, e := setupKernel.NewProc("OpenProcess").Call(0x00100000, 0, uintptr(parent))
		if h != 0 {
			value, _, _ := setupKernel.NewProc("WaitForSingleObject").Call(h, 15000)
			setupKernel.NewProc("CloseHandle").Call(h)
			if value != 0 {
				return fmt.Errorf("The uninstall launcher has not exited; close it and retry")
			}
		} else if e != syscall.Errno(87) {
			return fmt.Errorf("Could not wait for uninstall launcher: %w", e)
		}
	}
	if !uninstallConfirmation(root) {
		return nil
	}
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	m, err := readManifest()
	if err != nil {
		return err
	}
	p, err := detect("windows", "amd64")
	if err != nil {
		return err
	}
	state := newState(p, m.Version, root)
	logdir, err := checkedUninstallPath(root, "logs")
	if err != nil {
		return err
	}
	if err = os.MkdirAll(logdir, 0700); err != nil {
		return err
	}
	logfile := filepath.Join(logdir, "uninstall-"+nonce()+".log")
	log, err := os.OpenFile(logfile, os.O_CREATE|os.O_WRONLY|os.O_EXCL, 0600)
	if err != nil {
		return err
	}
	defer log.Close()
	state.setLog(log, logfile)
	job := func(ctx context.Context) error {
		return withSetupLock(root, func() error {
			// Reload on every retry, and reject changed paths before removal.
			inventory, err = loadUninstallInventory(root)
			if err != nil {
				return err
			}
			state.step(0, "Checking that PY.cad is closed")
			if err = uninstallPowerShell(ctx, `$ErrorActionPreference='Stop';$prefix=`+psQuote(root+string(os.PathSeparator))+`; $running=@(Get-Process | Where-Object {try {$_.Path -and $_.Path.StartsWith($prefix,[StringComparison]::OrdinalIgnoreCase)} catch {$false}}); if($running.Count -gt 0){throw 'Close PY.cad and any setup windows for this installation, then click Retry.'}`); err != nil {
				return err
			}
			state.step(1, "Removing owned application and private runtime files")
			result, err := removeOwnedFiles(ctx, root, inventory, state)
			if err != nil {
				return err
			}
			state.step(4, "Removing managed shortcuts and the Installed apps entry")
			if err = uninstallPowerShell(ctx, uninstallCleanupScript(root)); err != nil {
				return err
			}
			// Keep the recovery launcher and inventory until every other step
			// succeeds. Failures leave them available for a safe retry.
			path, err := checkedUninstallPath(root, uninstallExeName)
			if err != nil {
				return err
			}
			digest, err := uninstallHash(path)
			if err != nil && !os.IsNotExist(err) {
				return err
			}
			if digest == inventory.Files[uninstallExeName] {
				if err = os.Remove(path); err != nil {
					return err
				}
			}
			if err = os.Remove(filepath.Join(root, uninstallManifestName)); err != nil {
				return err
			}
			pruneUninstallDirs(root)
			state.note(fmt.Sprintf("Removed %d owned files. Drawings, settings, logs, and untracked/modified files were kept. The folder may remain: %s", result.Removed, root))
			state.step(5, "PY.cad has been uninstalled")
			return nil
		})
	}
	return runNativeWindowMode(ctx, cancel, state, job, nil, true)
}
