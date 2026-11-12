package main

import (
	"context"
	_ "embed"
	"fmt"
	"regexp"
	"strings"
)

//go:embed studio/art/banner.png
var studioBanner []byte

//go:embed studio/art/construction.gif
var studioAnimation []byte

type transferStatus struct {
	Name   string `json:"name"`
	Bytes  int64  `json:"bytes"`
	Total  int64  `json:"total"`
	Active bool   `json:"active"`
}
type packageStatus struct {
	Name string `json:"name"`
	Size string `json:"size"`
	Done bool   `json:"done"`
}

var packageLine = regexp.MustCompile(`(?m)^\s*(Downloading|Downloaded)\s+([a-zA-Z0-9_.+\-]+)(?:[ \t]+\(([^)\r\n]+)\))?`)
var terminalEscape = regexp.MustCompile("\x1b\\[[0-?]*[ -/]*[@-~]")

func (s *progress) transfer(name string, count, total int64, active bool) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.value.Transfer = transferStatus{name, count, total, active}
}

// Called under s.mu. Remember reported packages across command output windows.
func (s *progress) capturePackages(text string) {
	text = strings.ReplaceAll(terminalEscape.ReplaceAllString(text, ""), "\r", "\n")
	for _, m := range packageLine.FindAllStringSubmatch(text, -1) {
		index := -1
		for i, item := range s.value.Packages {
			if item.Name == m[2] {
				index = i
				break
			}
		}
		if index < 0 {
			if len(s.value.Packages) >= 512 {
				continue
			}
			s.value.Packages = append(s.value.Packages, packageStatus{Name: m[2]})
			index = len(s.value.Packages) - 1
		}
		item := &s.value.Packages[index]
		if m[3] != "" {
			item.Size = m[3]
		}
		if m[1] == "Downloaded" {
			item.Done = true
		}
	}
}
func downloadLabel(v snapshot) string {
	d := v.Transfer
	if d.Active {
		if d.Total > 0 {
			return fmt.Sprintf("%s · %.2f / %.2f MiB", d.Name, float64(d.Bytes)/1048576, float64(d.Total)/1048576)
		}
		if d.Bytes > 0 {
			return fmt.Sprintf("%s · %.2f MiB received", d.Name, float64(d.Bytes)/1048576)
		}
		return d.Name + " · working"
	}
	if v.Done {
		return "Downloads complete"
	}
	if v.Error != "" {
		return "Download activity stopped"
	}
	if v.Step == 2 || v.Step == 3 {
		return "Download activity · waiting for package details"
	}
	return "Downloads"
}

type countedDownload struct {
	reader       interface{ Read([]byte) (int, error) }
	state        *progress
	count, total int64
}

func (r *countedDownload) Read(b []byte) (int, error) {
	n, err := r.reader.Read(b)
	r.count += int64(n)
	r.state.transfer("UV runtime bootstrap", r.count, max(0, r.total), true)
	return n, err
}

func runWithTransfer(ctx context.Context, s *progress, label string, env []string, dir, program string, args ...string) error {
	s.transfer(label, 0, 0, true)
	defer s.transfer(label, 0, 0, false)
	return run(ctx, s, env, dir, program, args...)
}
