package main

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"time"
)

type options struct {
	Root                                                      string
	NoBrowser, NoLaunch, NoSystem, CoreOnly, Diagnose, Launch bool
	DestinationConfirmed                                      bool
}

func main() {
	var o options
	var extractSource string
	var uninstall, uninstallWorker bool
	var uninstallParent int
	flag.BoolVar(&uninstall, "uninstall", false, "Uninstall this user installation (Windows)")
	flag.BoolVar(&uninstallWorker, "uninstall-worker", false, "Internal temporary uninstall worker")
	flag.IntVar(&uninstallParent, "uninstall-parent", 0, "Internal uninstall parent process")
	flag.StringVar(&extractSource, "extract-source", "", "Extract the embedded application and installer source into a new directory, without installing")
	flag.StringVar(&o.Root, "root", "", "Private installation location (advanced)")
	flag.BoolVar(&o.NoBrowser, "no-browser", false, "Print progress without opening a browser")
	flag.BoolVar(&o.NoLaunch, "no-launch", false, "Install and check without launching PY.cad")
	flag.BoolVar(&o.NoSystem, "no-system-packages", false, "Report missing system libraries without installing them")
	flag.BoolVar(&o.CoreOnly, "core-only", false, "Install the 2D/BOQ/chat profile without optional 3D/IFC")
	flag.BoolVar(&o.Diagnose, "diagnose", false, "Print OS/CPU and installer manifest without installing")
	flag.BoolVar(&o.Launch, "launch", false, "Launch the installed application, or repair it if needed")
	flag.BoolVar(&o.DestinationConfirmed, "destination-confirmed", false, "Internal: destination selected")
	flag.Parse()
	if extractSource != "" {
		// Refuse an existing path, so source extraction never overwrites user data.
		if err := os.Mkdir(extractSource, 0700); err != nil {
			fmt.Fprintln(os.Stderr, "Source extraction:", err)
			os.Exit(1)
		}
		if err := extractPayload(payload, extractSource); err != nil {
			fmt.Fprintln(os.Stderr, "Source extraction:", err)
			os.Exit(1)
		}
		fmt.Println("PY.cad application and installer source extracted to", extractSource)
		return
	}
	m, err := readManifest()
	if err != nil {
		fatal(err)
		return
	}
	p, err := detect(runtime.GOOS, runtime.GOARCH)
	if err != nil {
		fatal(err)
		return
	}
	if o.Root == "" {
		o.Root, err = defaultRoot(p.OS)
		if err != nil {
			fatal(err)
			return
		}
	}
	o.Root, err = filepath.Abs(o.Root)
	if err != nil {
		fatal(err)
		return
	}
	if !o.Launch {
		handled, e := prepareDestination(&o, uninstall, uninstallWorker)
		if e != nil {
			fatal(e)
			os.Exit(1)
		}
		if handled {
			return
		}
	}
	if uninstall || uninstallWorker || filepath.Base(os.Args[0]) == "Uninstall-PY.cad.exe" {
		if err = runUninstaller(o.Root, uninstallWorker, uninstallParent); err != nil {
			if errors.Is(err, errNativeSetupIncomplete) {
				os.Exit(1)
			}
			fmt.Fprintln(os.Stderr, err)
			notify("Uninstall PY.cad", err.Error())
			os.Exit(1)
		}
		return
	}
	if o.Diagnose {
		_ = json.NewEncoder(os.Stdout).Encode(map[string]any{"platform": p, "version": m.Version, "python": m.Python, "profile": "3D + IFC by default", "root": o.Root, "payload_sha256": m.PayloadSHA})
		return
	}
	if o.Launch {
		if err = launchCurrent(o.Root, p, flag.Args()); err == nil {
			return
		}
		o.DestinationConfirmed = true
		handled, e := prepareDestination(&o, false, false)
		if e != nil {
			fatal(e)
			os.Exit(1)
		}
		if handled {
			return
		}
	}
	if err = os.MkdirAll(o.Root, 0700); err != nil {
		fatal(err)
		return
	}
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	state := newState(p, m.Version, o.Root)
	if wantsNativeSetup(p, o) {
		if err = runNativeSetup(ctx, cancel, o, p, m, state); err != nil {
			if errors.Is(err, errNativeSetupIncomplete) {
				fmt.Fprintln(os.Stderr, err)
				os.Exit(1)
			}
			fatal(err)
		}
		return
	}
	srv, url, err := serveProgress(state, cancel)
	if err != nil {
		fatal(err)
		return
	}
	defer srv.Close()
	fmt.Println("PY.cad Setup:", url)
	if !o.NoBrowser {
		go func() {
			if openErr := openURL(url); openErr != nil {
				message := "Could not open the browser. Setup continues. Open this address: " + url
				state.note(message)
				notify("PY.cad Setup", message)
			}
		}()
	}
	err = withSetupLock(o.Root, func() error { return install(ctx, o, p, m, state) })
	if err != nil {
		state.fail(err)
	} else {
		state.finish()
	}
	if o.NoBrowser {
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(1)
		}
		return
	}
	// The page stops polling after completion. Allow time to read errors and save a log.
	for {
		select {
		case <-ctx.Done():
			return
		case <-time.After(15 * time.Minute):
			return
		case <-state.retry:
			state.reset()
			if err = withSetupLock(o.Root, func() error { return install(ctx, o, p, m, state) }); err != nil {
				state.fail(err)
			} else {
				state.finish()
			}
		}
	}
}

func withSetupLock(root string, action func() error) error {
	lock, err := acquireLock(root)
	if err != nil {
		return err
	}
	defer lock.Close()
	// A failed install must release the lock even while its error page stays
	// open. Every retry/reopened installer obtains a fresh exclusive lock.
	return action()
}
func fatal(err error) {
	fmt.Fprintln(os.Stderr, "PY.cad Setup:", err)
	notify("PY.cad Setup", err.Error())
	os.Exit(1)
}
func nonce() string {
	b := make([]byte, 16)
	if _, err := rand.Read(b); err != nil {
		panic(err)
	}
	return hex.EncodeToString(b)
}
