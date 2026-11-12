//go:build linux || darwin

package main

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"syscall"
)

func acquireLock(root string) (*os.File, error) {
	f, e := os.OpenFile(filepath.Join(root, "setup.lock"), os.O_CREATE|os.O_RDWR, 0600)
	if e != nil {
		return nil, e
	}
	if e = syscall.Flock(int(f.Fd()), syscall.LOCK_EX|syscall.LOCK_NB); e != nil {
		f.Close()
		return nil, fmt.Errorf("Another PY.cad Setup is active. Wait for it to finish")
	}
	return f, nil
}
func hideConsole(c *exec.Cmd) {}
func detach(c *exec.Cmd)      { c.SysProcAttr = &syscall.SysProcAttr{Setsid: true} }
func notify(title, message string) {
	if os.Getenv("PYCAD_SETUP_TEST") == "1" {
		return
	}
	if _, e := exec.LookPath("osascript"); e == nil {
		_ = exec.Command("osascript", "-e", "display alert "+strconv.Quote(title)+" message "+strconv.Quote(message)).Start()
	} else if _, e = exec.LookPath("zenity"); e == nil {
		_ = exec.Command("zenity", "--error", "--title="+title, "--text="+message).Start()
	}
}
