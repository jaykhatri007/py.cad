package main

import (
	"context"
	"errors"
	"strings"
	"sync/atomic"
	"testing"
	"time"
)

func TestNativeSetupRouting(t *testing.T) {
	for _, tc := range []struct {
		os              string
		console, native bool
	}{
		{"windows", false, true}, {"windows", true, false}, {"linux", false, false}, {"darwin", false, false},
	} {
		if got := wantsNativeSetup(platform{OS: tc.os}, options{NoBrowser: tc.console}); got != tc.native {
			t.Fatal(tc, got)
		}
	}
}

func TestNativeSetupPresentation(t *testing.T) {
	for _, tc := range []struct {
		name            string
		snapshot        snapshot
		busy, closing   bool
		label           string
		retry, closable bool
		stage           int
	}{
		{"working", snapshot{Step: 3, Title: "Installing CAD dependencies"}, true, false, "Cancel", false, true, 3},
		{"success", snapshot{Done: true, Step: 6}, false, false, "Close", false, true, 6},
		{"error", snapshot{Error: "Network unavailable"}, false, false, "Close", true, true, 0},
		{"stopping", snapshot{Step: 4}, true, true, "Stopping…", false, false, 4},
		{"clamped", snapshot{Step: 999}, false, false, "Close", false, true, 6},
	} {
		t.Run(tc.name, func(t *testing.T) {
			v := nativeView(tc.snapshot, tc.busy, tc.closing)
			if v.CloseLabel != tc.label || v.Retry != tc.retry || v.CanClose != tc.closable || v.Stage != tc.stage {
				t.Fatal(v)
			}
		})
	}
	s := snapshot{Notes: []string{strings.Repeat("界", 100000)}, Error: "Test error"}
	v := nativeView(s, false, false)
	if len([]rune(v.Details)) > 48000 || !strings.Contains(v.Details, "Test error") {
		t.Fatal("Unbounded or missing diagnostics")
	}
}

func waitAttempt(t *testing.T, a *setupAttempt) {
	t.Helper()
	deadline := time.Now().Add(3 * time.Second)
	for a.busy() && time.Now().Before(deadline) {
		time.Sleep(time.Millisecond)
	}
	if a.busy() {
		t.Fatal("Attempt did not finish")
	}
}

func TestNativeAttemptSerialRetryAndCompletion(t *testing.T) {
	s := newState(platform{OS: "windows"}, "test", t.TempDir())
	a := &setupAttempt{}
	gate := make(chan struct{})
	var count atomic.Int32
	job := func(ctx context.Context) error { count.Add(1); <-gate; return errors.New("First download failed") }
	if !a.start(context.Background(), s, false, job) || a.start(context.Background(), s, false, job) {
		t.Fatal("Duplicate worker accepted")
	}
	close(gate)
	waitAttempt(t, a)
	if s.status().Error == "" || s.status().Done {
		t.Fatal(s.status())
	}
	if !a.start(context.Background(), s, true, func(ctx context.Context) error { count.Add(1); return nil }) {
		t.Fatal("Retry rejected")
	}
	waitAttempt(t, a)
	if count.Load() != 2 || !s.status().Done || s.status().Error != "" {
		t.Fatal(count.Load(), s.status())
	}
	if a.start(context.Background(), s, true, job) {
		t.Fatal("Retry accepted after success")
	}
}

func TestNativeAttemptCancellationWaitsForCleanup(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	s := newState(platform{OS: "windows"}, "test", t.TempDir())
	a := &setupAttempt{}
	started := make(chan struct{})
	cleanup := make(chan struct{})
	a.start(ctx, s, false, func(ctx context.Context) error {
		close(started)
		<-ctx.Done()
		time.Sleep(20 * time.Millisecond)
		close(cleanup)
		return ctx.Err()
	})
	<-started
	cancel()
	if !a.busy() {
		t.Fatal("Cancellation skipped worker cleanup")
	}
	waitAttempt(t, a)
	<-cleanup
	if s.status().Done || s.status().Error == "" {
		t.Fatal(s.status())
	}
	if a.start(ctx, s, true, func(context.Context) error { return nil }) {
		t.Fatal("Cancelled setup restarted")
	}
}
