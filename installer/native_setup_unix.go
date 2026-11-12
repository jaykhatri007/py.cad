//go:build linux || darwin

package main

import (
	"context"
	"errors"
)

func runNativeSetup(ctx context.Context, cancel context.CancelFunc, o options, p platform, m manifest, s *progress) error {
	return errors.New("Native Windows setup is unavailable on this platform")
}
