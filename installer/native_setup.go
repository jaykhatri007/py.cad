package main

import (
	"context"
	"errors"
	"strings"
	"sync"
)

var errNativeSetupIncomplete = errors.New("PY.cad setup was closed without completing installation")

// Windows uses its own top-level window. Explicit --no-browser retains the
// existing console/automation path, without a browser or a native UI.
func wantsNativeSetup(p platform, o options) bool {
	return p.OS == "windows" && !o.NoBrowser
}

type setupAttempt struct {
	mu      sync.Mutex
	running bool
}

func (a *setupAttempt) busy() bool {
	a.mu.Lock()
	defer a.mu.Unlock()
	return a.running
}

func (a *setupAttempt) start(ctx context.Context, s *progress, retry bool, job func(context.Context) error) bool {
	a.mu.Lock()
	defer a.mu.Unlock()
	if a.running || ctx.Err() != nil {
		return false
	}
	if retry {
		if s.status().Error == "" {
			return false
		}
		s.reset()
	}
	a.running = true
	go func() {
		err := job(ctx)
		if err != nil {
			s.fail(err)
		} else {
			s.finish()
		}
		a.mu.Lock()
		a.running = false
		a.mu.Unlock()
	}()
	return true
}

type nativeSetupView struct {
	Title, Details, CloseLabel string
	Stage                      int
	Retry, CanClose            bool
}

func nativeView(v snapshot, busy, closing bool) nativeSetupView {
	stage := v.Step
	if stage < 0 {
		stage = 0
	}
	if stage > 6 {
		stage = 6
	}
	view := nativeSetupView{Title: v.Title, Stage: stage, CloseLabel: "Close", CanClose: true}
	if busy {
		view.CloseLabel = "Cancel"
	}
	if v.Done {
		view.Title = "Installation complete — PY.cad is ready"
		view.Stage = 6
	}
	view.Retry = !busy && v.Error != ""
	details := strings.Join(v.Notes, "\r\n")
	if !v.Done && v.Output != "" {
		text := []rune(v.Output)
		if len(text) > 6000 {
			text = text[len(text)-6000:]
		}
		details += "\r\n\r\nCurrent package / command output:\r\n" + string(text)
	}
	if v.Error != "" {
		details += "\r\n\r\nSetup needs attention:\r\n" + v.Error
	}
	runes := []rune(details)
	if len(runes) > 48000 {
		details = string(runes[len(runes)-48000:])
	}
	view.Details = details
	if closing {
		view.Title = "Stopping setup…"
		view.CloseLabel = "Stopping…"
		view.Retry = false
		view.CanClose = false
	}
	return view
}
