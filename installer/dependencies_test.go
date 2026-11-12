package main

import (
	"context"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func TestPrivateDependencySettings(t *testing.T) {
	t.Setenv("UV_HTTP_TIMEOUT", "1")
	t.Setenv("UV_LINK_MODE", "symlink")
	for _, osname := range []string{"windows", "linux", "darwin"} {
		env := dependencyEnv(t.TempDir(), platform{OS: osname})
		joined := strings.Join(env, "\n")
		for _, setting := range []string{"UV_HTTP_TIMEOUT=300", "UV_HTTP_RETRIES=5", "UV_CONCURRENT_DOWNLOADS=4", "PYTHONNOUSERSITE=1", "UV_NO_CONFIG=1"} {
			if !strings.Contains(joined, setting+"\n") && !strings.HasSuffix(joined, setting) {
				t.Fatalf("missing %s", setting)
			}
		}
		if strings.Contains(joined, "UV_LINK_MODE=symlink") {
			t.Fatal("inherited link override")
		}
		if osname == "windows" && (!strings.Contains(joined, "UV_LINK_MODE=copy") || !strings.Contains(joined, "UV_NATIVE_TLS=1")) {
			t.Fatal("Windows copy/TLS policy")
		}
	}
}

func TestTemporaryPackageFailureRetriesWithoutCommitting(t *testing.T) {
	state := newState(platform{}, "test", t.TempDir())
	calls := 0
	err := retryPackageInstall(context.Background(), state, func() error {
		calls++
		if calls == 1 {
			state.lastOutput = "Connection reset while downloading vtk.whl"
			return errors.New("failed")
		}
		return nil
	}, 0)
	if err != nil || calls != 2 || len(state.status().Notes) != 1 {
		t.Fatal(err, calls, state.status())
	}
}

func TestPermanentPackageFailureDoesNotLoop(t *testing.T) {
	for _, output := range []string{"No solution found: incompatible wheel", "access is denied", "no space left", "permission denied: timeout file"} {
		state := newState(platform{}, "test", t.TempDir())
		calls := 0
		err := retryPackageInstall(context.Background(), state, func() error { calls++; state.lastOutput = output; return errors.New("failed") }, 0)
		if err == nil || calls != 1 {
			t.Fatal(output, calls, err)
		}
	}
}

func TestCancelStopsPackageRetry(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	state := newState(platform{}, "test", t.TempDir())
	calls := 0
	err := retryPackageInstall(ctx, state, func() error { calls++; state.lastOutput = "download timed out"; cancel(); return errors.New("failed") }, time.Hour)
	if !errors.Is(err, context.Canceled) || calls != 1 {
		t.Fatal(calls, err)
	}
}

func TestDependencyOutputHelper(t *testing.T) {
	if os.Getenv("PYCAD_DEPENDENCY_HELPER") != "1" {
		return
	}
	fmt.Println("Downloading PyQt6-Qt6 test wheel")
	until := time.Now().Add(5 * time.Second)
	for time.Now().Before(until) {
		if _, err := os.Stat(os.Getenv("PYCAD_DEPENDENCY_RELEASE")); err == nil {
			fmt.Fprintln(os.Stderr, "test download timed out")
			os.Exit(7)
		}
		time.Sleep(5 * time.Millisecond)
	}
	os.Exit(9)
}

func TestPackageOutputVisibleWhileCommandRuns(t *testing.T) {
	dir := t.TempDir()
	release := filepath.Join(dir, "release")
	state := newState(platform{}, "test", dir)
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	env := append(os.Environ(), "PYCAD_DEPENDENCY_HELPER=1", "PYCAD_DEPENDENCY_RELEASE="+release)
	done := make(chan error, 1)
	go func() { done <- run(ctx, state, env, dir, os.Args[0], "-test.run=^TestDependencyOutputHelper$", "--") }()
	deadline := time.Now().Add(5 * time.Second)
	visible := false
	for time.Now().Before(deadline) {
		if strings.Contains(nativeView(state.status(), true, false).Details, "Downloading PyQt6-Qt6") {
			visible = true
			break
		}
		time.Sleep(5 * time.Millisecond)
	}
	if err := os.WriteFile(release, []byte("done"), 0600); err != nil {
		t.Fatal(err)
	}
	err := <-done
	if !visible || err == nil || !strings.Contains(err.Error(), "test download timed out") {
		t.Fatal("missing live/failure output", visible, err)
	}
}
