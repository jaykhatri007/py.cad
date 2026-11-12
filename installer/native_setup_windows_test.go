//go:build windows

package main

import (
	"context"
	"errors"
	"os"
	"sync/atomic"
	"syscall"
	"testing"
	"time"
	"unsafe"
)

func nativeGUIEnabled(t *testing.T) {
	t.Helper()
	if os.Getenv("PYCAD_NATIVE_UI_TEST") != "1" {
		t.Skip("Opt-in real Windows window acceptance")
	}
}
func nativeTestWait(condition func() bool) bool {
	deadline := time.Now().Add(12 * time.Second)
	for time.Now().Before(deadline) {
		if condition() {
			return true
		}
		time.Sleep(30 * time.Millisecond)
	}
	return false
}
func nativePost(hwnd uintptr, message uint32, wparam uintptr) {
	setupUser.NewProc("PostMessageW").Call(hwnd, uintptr(message), wparam, 0)
}
func nativeControl(hwnd uintptr, id int) uintptr {
	v, _, _ := setupUser.NewProc("GetDlgItem").Call(hwnd, uintptr(id))
	return v
}
func nativeButtonText(hwnd uintptr) string {
	buf := make([]uint16, 256)
	setupUser.NewProc("GetWindowTextW").Call(hwnd, uintptr(unsafe.Pointer(&buf[0])), uintptr(len(buf)))
	return syscall.UTF16ToString(buf)
}
func nativeStillOpen(hwnd uintptr) bool {
	v, _, _ := setupUser.NewProc("IsWindow").Call(hwnd)
	return v != 0
}

func TestNativeWindowCompleteCloseAndLegalViewer(t *testing.T) {
	nativeGUIEnabled(t)
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	s := newState(platform{OS: "windows", Label: "Windows", ArchLabel: "x64"}, "UI acceptance", t.TempDir())
	gate := make(chan struct{})
	result := make(chan bool, 1)
	err := runNativeWindow(ctx, cancel, s, func(ctx context.Context) error { <-gate; s.step(5, "Ready"); return nil }, func(hwnd uintptr) {
		go func() {
			nativePost(hwnd, wmCommand, idLegal)
			var legal uintptr
			ok := nativeTestWait(func() bool {
				legal, _, _ = setupUser.NewProc("FindWindowW").Call(0, uintptr(unsafe.Pointer(winText("PY.cad — Licenses and Legal"))))
				return legal != 0
			})
			if ok {
				nativePost(legal, wmClose, 0)
				ok = nativeTestWait(func() bool { return !nativeStillOpen(legal) }) && nativeStillOpen(hwnd)
			}
			close(gate)
			ok = nativeTestWait(func() bool { return s.status().Done && nativeButtonText(nativeControl(hwnd, idClose)) == "Close" }) && ok
			result <- ok
			nativePost(hwnd, wmCommand, idClose)
		}()
	})
	if err != nil || !<-result {
		t.Fatal("Completion/Close/legal UI failed", err)
	}
}

func TestNativeWindowRetryUsesOneWorker(t *testing.T) {
	nativeGUIEnabled(t)
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	s := newState(platform{OS: "windows"}, "UI retry acceptance", t.TempDir())
	var count atomic.Int32
	result := make(chan bool, 1)
	err := runNativeWindow(ctx, cancel, s, func(ctx context.Context) error {
		if count.Add(1) == 1 {
			return errors.New("Simulated dependency download failure")
		}
		return nil
	}, func(hwnd uintptr) {
		go func() {
			ok := nativeTestWait(func() bool {
				enabled, _, _ := setupUser.NewProc("IsWindowEnabled").Call(nativeControl(hwnd, idRetry))
				return s.status().Error != "" && enabled != 0
			})
			if ok {
				nativePost(hwnd, wmCommand, idRetry)
			}
			ok = nativeTestWait(func() bool { return s.status().Done && nativeButtonText(nativeControl(hwnd, idClose)) == "Close" }) && ok
			result <- ok
			nativePost(hwnd, wmCommand, idClose)
		}()
	})
	if err != nil || !<-result || count.Load() != 2 {
		t.Fatal("Retry UI failed", err, count.Load())
	}
}

func TestNativeWindowCancelWaitsAndCloses(t *testing.T) {
	nativeGUIEnabled(t)
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	s := newState(platform{OS: "windows"}, "UI cancellation acceptance", t.TempDir())
	var cleaned atomic.Bool
	result := make(chan bool, 1)
	err := runNativeWindow(ctx, cancel, s, func(ctx context.Context) error {
		<-ctx.Done()
		time.Sleep(100 * time.Millisecond)
		cleaned.Store(true)
		return ctx.Err()
	}, func(hwnd uintptr) {
		go func() {
			nativePost(hwnd, wmClose, 0)
			var prompt uintptr
			ok := nativeTestWait(func() bool {
				prompt, _, _ = setupUser.NewProc("FindWindowW").Call(0, uintptr(unsafe.Pointer(winText("Cancel PY.cad setup?"))))
				return prompt != 0
			})
			if ok {
				nativePost(prompt, wmCommand, 6)
			} else {
				cancel()
				nativePost(hwnd, wmCommand, idClose)
			}
			result <- ok
		}()
	})
	if !errors.Is(err, errNativeSetupIncomplete) || !<-result || !cleaned.Load() {
		t.Fatal("Cancel UI failed", err, cleaned.Load())
	}
}
