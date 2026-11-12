package main

import (
	"context"
	"path/filepath"
	"strings"
	"time"
)

// Stable private setup settings. Keep certificate validation and wheel-only
// installation; avoid Windows hard links and short idle download timeouts.
func dependencyEnv(root string, p platform) []string {
	extra := map[string]string{
		"UV_PYTHON_INSTALL_DIR": filepath.Join(root, "python"),
		"UV_CACHE_DIR":          filepath.Join(root, "cache"),
		"UV_NO_PROGRESS":        "1", "UV_NO_CONFIG": "1", "UV_PYTHON_INSTALL_BIN": "0",
		"UV_PYTHON_DOWNLOADS": "automatic", "PYTHONNOUSERSITE": "1",
		"UV_HTTP_TIMEOUT": "300", "UV_HTTP_RETRIES": "5", "UV_CONCURRENT_DOWNLOADS": "4",
	}
	if p.OS == "windows" {
		extra["UV_NATIVE_TLS"] = "1"
		extra["UV_LINK_MODE"] = "copy"
	}
	return cleanEnv(extra)
}

func transientPackageError(output string) bool {
	lower := strings.ToLower(output)
	for _, permanent := range []string{"no solution found", "no matching distribution", "conflicting dependencies", "access is denied", "permission denied", "no space left"} {
		if strings.Contains(lower, permanent) {
			return false
		}
	}
	for _, temporary := range []string{"timed out", "timeout", "connection reset", "connection refused", "connection closed", "error sending request", "temporary failure", "os error 10054", "unexpected eof", "incomplete body", "502 bad gateway", "503 service unavailable"} {
		if strings.Contains(lower, temporary) {
			return true
		}
	}
	return false
}

func retryPackageInstall(ctx context.Context, s *progress, action func() error, delay time.Duration) error {
	for attempt := 0; attempt < 2; attempt++ {
		if err := ctx.Err(); err != nil {
			return err
		}
		err := action()
		if err == nil {
			return nil
		}
		if ctx.Err() != nil {
			return ctx.Err()
		}
		s.mu.Lock()
		output := s.lastOutput
		s.mu.Unlock()
		if attempt != 0 || !transientPackageError(output) {
			return err
		}
		s.note("A temporary package download failed. Retrying once using the verified download cache…")
		timer := time.NewTimer(delay)
		select {
		case <-ctx.Done():
			timer.Stop()
			return ctx.Err()
		case <-timer.C:
		}
	}
	return nil
}

func installPackages(ctx context.Context, s *progress, env []string, release, uv, python, requirements string) error {
	return retryPackageInstall(ctx, s, func() error {
		return runWithTransfer(ctx, s, "CAD dependency packages", env, release, uv, "pip", "install", "--python", python,
			"--only-binary", ":all:", "-r", requirements)
	}, 2*time.Second)
}
