//go:build !windows

package main

func prepareDestination(o *options, uninstall, worker bool) (bool, error) { return false, nil }
