package main

import (
	"context"
	"crypto/subtle"
	_ "embed"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"os"
	"sync"
	"time"
)

//go:embed setup.html
var setupHTML []byte

type snapshot struct {
	Transfer transferStatus  `json:"transfer"`
	Packages []packageStatus `json:"packages"`
	Version  string          `json:"version"`
	Platform string          `json:"platform"`
	Root     string          `json:"root"`
	Step     int             `json:"step"`
	Title    string          `json:"title"`
	Done     bool            `json:"done"`
	Error    string          `json:"error"`
	Notes    []string        `json:"notes"`
	Output   string          `json:"output"`
}
type progress struct {
	mu          sync.Mutex
	value       snapshot
	log         io.Writer
	logfile     string
	lastOutput  string
	haveCommand bool
	retry       chan struct{}
}

func newState(p platform, version, root string) *progress {
	return &progress{value: snapshot{Version: version, Platform: p.Label + " · " + p.ArchLabel, Root: root, Step: 0, Title: "Preparing your workspace", Notes: []string{}}, log: io.Discard, retry: make(chan struct{}, 1)}
}
func (s *progress) setLog(f *os.File, path string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.log = f
	s.logfile = path
}
func (s *progress) status() snapshot {
	s.mu.Lock()
	defer s.mu.Unlock()
	v := s.value
	v.Output = s.lastOutput
	v.Packages = append([]packageStatus{}, v.Packages...)
	v.Notes = append([]string{}, v.Notes...)
	return v
}
func (s *progress) logPath() string {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.logfile
}
func (s *progress) note(message string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.value.Notes = append(s.value.Notes, message)
	if len(s.value.Notes) > 100 {
		s.value.Notes = s.value.Notes[len(s.value.Notes)-100:]
	}
	fmt.Fprintln(s.log, time.Now().Format(time.RFC3339), message)
}
func (s *progress) logCommand(program string, args []string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	fmt.Fprintf(s.log, "\n%s: %s %q\n", time.Now().Format(time.RFC3339), program, args)
}
func (s *progress) step(index int, title string) {
	s.mu.Lock()
	s.value.Step = index
	s.value.Title = title
	s.mu.Unlock()
	s.note(title)
}
func (s *progress) fail(err error) {
	s.note(err.Error())
	s.mu.Lock()
	defer s.mu.Unlock()
	s.value.Error = err.Error()
	s.value.Title = "Setup needs attention"
}
func (s *progress) finish() {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.value.Done = true
	s.value.Step = 6
	s.value.Title = "Your workspace is ready"
}
func (s *progress) reset() {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.value.Done = false
	s.value.Error = ""
	s.value.Step = 0
	s.value.Title = "Retrying setup"
	s.value.Transfer = transferStatus{}
	s.value.Packages = nil
	s.log = io.Discard
	s.logfile = ""
	s.lastOutput = ""
	s.haveCommand = false
}
func progressHandler(s *progress, key, host string, cancel context.CancelFunc) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Cache-Control", "no-store")
		w.Header().Set("X-Content-Type-Options", "nosniff")
		w.Header().Set("Referrer-Policy", "no-referrer")
		w.Header().Set("Content-Security-Policy", "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'")
		if r.Host != host || subtle.ConstantTimeCompare([]byte(r.URL.Query().Get("key")), []byte(key)) != 1 {
			http.Error(w, "Not found", 404)
			return
		}
		if r.Method == http.MethodPost {
			origin := r.Header.Get("Origin")
			if origin != "" && origin != "http://"+host {
				http.Error(w, "Forbidden", 403)
				return
			}
		}
		switch r.URL.Path {
		case "/studio-banner.png", "/studio-animation.gif":
			if r.Method != http.MethodGet {
				http.Error(w, "Method not allowed", 405)
				return
			}
			if r.URL.Path == "/studio-animation.gif" {
				w.Header().Set("Content-Type", "image/gif")
				_, _ = w.Write(studioAnimation)
			} else {
				w.Header().Set("Content-Type", "image/png")
				_, _ = w.Write(studioBanner)
			}
		case "/logo", "/legal":
			if r.Method != http.MethodGet {
				http.Error(w, "Method not allowed", 405)
				return
			}
			if r.URL.Path == "/logo" {
				w.Header().Set("Content-Type", "image/png")
				_, _ = w.Write(brandLogo)
			} else {
				w.Header().Set("Content-Type", "text/html; charset=utf-8")
				_, _ = w.Write(legalHTML)
			}
		case "/":
			if r.Method != http.MethodGet {
				http.Error(w, "Method not allowed", 405)
				return
			}
			w.Header().Set("Content-Type", "text/html; charset=utf-8")
			_, _ = w.Write(setupHTML)
		case "/status":
			if r.Method != http.MethodGet {
				http.Error(w, "Method not allowed", 405)
				return
			}
			w.Header().Set("Content-Type", "application/json")
			_ = json.NewEncoder(w).Encode(s.status())
		case "/log":
			if r.Method != http.MethodGet {
				http.Error(w, "Method not allowed", 405)
				return
			}
			s.mu.Lock()
			file := s.logfile
			s.mu.Unlock()
			if file == "" {
				http.Error(w, "The log is not ready yet", 404)
				return
			}
			w.Header().Set("Content-Type", "text/plain; charset=utf-8")
			w.Header().Set("Content-Disposition", "attachment; filename=PY.cad-Setup.log")
			http.ServeFile(w, r, file)
		case "/close":
			if r.Method != http.MethodPost {
				http.Error(w, "Method not allowed", 405)
				return
			}
			w.WriteHeader(204)
			go func() { time.Sleep(100 * time.Millisecond); cancel() }()
		case "/retry":
			if r.Method != http.MethodPost {
				http.Error(w, "Method not allowed", 405)
				return
			}
			if s.status().Error == "" {
				http.Error(w, "Setup is already running", 409)
				return
			}
			select {
			case s.retry <- struct{}{}:
				w.WriteHeader(204)
			default:
				http.Error(w, "Retry already requested", 409)
			}
		default:
			http.NotFound(w, r)
		}
	})
}
func serveProgress(s *progress, cancel context.CancelFunc) (*http.Server, string, error) {
	l, err := net.Listen("tcp4", "127.0.0.1:0")
	if err != nil {
		return nil, "", err
	}
	key := nonce()
	host := l.Addr().String()
	server := &http.Server{Handler: progressHandler(s, key, host, cancel), ReadHeaderTimeout: 5 * time.Second, ReadTimeout: 15 * time.Second, WriteTimeout: 30 * time.Second, IdleTimeout: 30 * time.Second, MaxHeaderBytes: 8192}
	go func() {
		if e := server.Serve(l); e != nil && !errors.Is(e, http.ErrServerClosed) {
			s.note("Progress page: " + e.Error())
		}
	}()
	return server, "http://" + host + "/?key=" + url.QueryEscape(key), nil
}
