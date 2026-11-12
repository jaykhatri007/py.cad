//go:build windows

package main

import (
	"bytes"
	"context"
	"fmt"
	"image"
	"image/draw"
	"image/gif"
	"image/png"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"syscall"
	"time"
	"unsafe"
)

var (
	setupUser           = syscall.NewLazyDLL("user32.dll")
	setupGDI            = syscall.NewLazyDLL("gdi32.dll")
	setupKernel         = syscall.NewLazyDLL("kernel32.dll")
	setupCommon         = syscall.NewLazyDLL("comctl32.dll")
	createWindow        = setupUser.NewProc("CreateWindowExW")
	defaultWindow       = setupUser.NewProc("DefWindowProcW")
	destroyWindow       = setupUser.NewProc("DestroyWindow")
	setWindowText       = setupUser.NewProc("SetWindowTextW")
	sendWindowMessage   = setupUser.NewProc("SendMessageW")
	activeSetupWindow   *nativeSetupWindow
	setupWindowCallback = syscall.NewCallback(setupWindowProc)
)

const (
	wmClose   = 0x0010
	wmDestroy = 0x0002
	wmSize    = 0x0005
	wmCommand = 0x0111
	wmTimer   = 0x0113
	wsChild   = 0x40000000
	wsVisible = 0x10000000
	wsTabStop = 0x00010000
	idClose   = 2
	idRetry   = 101
	idLog     = 102
	idLegal   = 103
)

type setupPoint struct{ X, Y int32 }
type setupRect struct{ Left, Top, Right, Bottom int32 }
type setupMessage struct {
	Window         uintptr
	Message        uint32
	WParam, LParam uintptr
	Time           uint32
	Point          setupPoint
	Private        uint32
}
type setupWindowClass struct {
	Size, Style                        uint32
	Procedure                          uintptr
	ClassExtra, WindowExtra            int32
	Instance, Icon, Cursor, Background uintptr
	MenuName, ClassName                *uint16
	SmallIcon                          uintptr
}
type setupBitmapInfo struct {
	Size                   uint32
	Width, Height          int32
	Planes, BitCount       uint16
	Compression, SizeImage uint32
	XPels, YPels           int32
	Used, Important        uint32
}

type nativeSetupWindow struct {
	uninstall                                                                                                          bool
	steps, transferText, transferBar                                                                                   uintptr
	frames                                                                                                             []image.Image
	heroW, heroH                                                                                                       int32
	animationStart                                                                                                     time.Time
	frame                                                                                                              int
	marquee                                                                                                            bool
	lastTransfer, lastSteps                                                                                            string
	started                                                                                                            time.Time
	lastActivity                                                                                                       string
	hwnd, instance, font, headingFont, bitmap                                                                          uintptr
	logo, heading, subtitle, title, bar, activity, location, details, closeButton, retryButton, logButton, legalButton uintptr
	dpi                                                                                                                int32
	state                                                                                                              *progress
	attempt                                                                                                            setupAttempt
	ctx                                                                                                                context.Context
	cancel                                                                                                             context.CancelFunc
	job                                                                                                                func(context.Context) error
	closing                                                                                                            bool
	last                                                                                                               nativeSetupView
	auxiliary                                                                                                          map[uintptr]uintptr
}

func winText(value string) *uint16 {
	value = strings.ReplaceAll(strings.ToValidUTF8(value, "�"), "\x00", "�")
	p, _ := syscall.UTF16PtrFromString(value)
	return p
}
func winSetText(hwnd uintptr, value string) {
	setWindowText.Call(hwnd, uintptr(unsafe.Pointer(winText(value))))
}
func (u *nativeSetupWindow) px(value int32) int32 { return (value*u.dpi + 48) / 96 }
func winInt(value int32) uintptr                  { return uintptr(uint32(value)) }
func winEnable(hwnd uintptr, enabled bool) {
	v := uintptr(0)
	if enabled {
		v = 1
	}
	setupUser.NewProc("EnableWindow").Call(hwnd, v)
}
func (u *nativeSetupWindow) control(class, text string, style uint32, id int) (uintptr, error) {
	ex := uintptr(0)
	if class == "EDIT" {
		ex = 0x200
	}
	h, _, err := createWindow.Call(ex, uintptr(unsafe.Pointer(winText(class))), uintptr(unsafe.Pointer(winText(text))),
		uintptr(style|wsChild|wsVisible), 0, 0, 0, 0, u.hwnd, uintptr(id), u.instance, 0)
	if h == 0 {
		return 0, fmt.Errorf("Create %s control: %w", class, err)
	}
	sendWindowMessage.Call(h, 0x0030, u.font, 1) // WM_SETFONT
	return h, nil
}
func (u *nativeSetupWindow) move(hwnd uintptr, x, y, w, h int32) {
	setupUser.NewProc("MoveWindow").Call(hwnd, winInt(u.px(x)), winInt(u.px(y)), winInt(u.px(w)), winInt(u.px(h)), 1)
}
func (u *nativeSetupWindow) layout() {
	if u.closeButton == 0 {
		return
	}
	var r setupRect
	setupUser.NewProc("GetClientRect").Call(u.hwnd, uintptr(unsafe.Pointer(&r)))
	w, h := r.Right*96/u.dpi, r.Bottom*96/u.dpi
	heroH := min((w-48)*241/752, h/3)
	heroH = max(52, min(heroH, h-335))
	if u.heroW != w-48 || u.heroH != heroH {
		u.frame = -1
	}
	u.heroW, u.heroH = w-48, heroH
	u.move(u.logo, 24, 14, u.heroW, heroH)
	top := heroH + 20
	u.move(u.heading, 24, top, w-48, 26)
	u.move(u.subtitle, 24, top+26, w-48, 20)
	u.move(u.title, 24, top+48, w-48, 25)
	u.move(u.bar, 24, top+74, w-48, 10)
	u.move(u.steps, 24, top+88, w-48, 43)
	u.move(u.transferText, 24, top+131, w-48, 20)
	u.move(u.transferBar, 24, top+152, w-48, 9)
	u.move(u.activity, 24, top+165, w-48, 20)
	u.move(u.location, 24, top+185, w-48, 22)
	u.move(u.details, 24, top+212, w-48, max(20, h-top-265))
	y := h - 46
	u.move(u.legalButton, 24, y, 100, 28)
	u.move(u.logButton, 132, y, 100, 28)
	u.move(u.retryButton, w-224, y, 92, 28)
	u.move(u.closeButton, w-124, y, 100, 28)
}

func (u *nativeSetupWindow) prepareBanner() {
	var animation uint32
	setupUser.NewProc("SystemParametersInfoW").Call(0x1042, 0, uintptr(unsafe.Pointer(&animation)), 0)
	if animation != 0 {
		if g, e := gif.DecodeAll(bytes.NewReader(studioAnimation)); e == nil {
			canvas := image.NewRGBA(image.Rect(0, 0, g.Config.Width, g.Config.Height))
			// The embedded opaque frames use no background disposal; retain
			// earlier pixels when an optimized frame only changes a subregion.
			for _, frame := range g.Image {
				draw.Draw(canvas, frame.Bounds(), frame, frame.Bounds().Min, draw.Over)
				next := image.NewRGBA(canvas.Bounds())
				copy(next.Pix, canvas.Pix)
				u.frames = append(u.frames, next)
			}
		}
	}
	if still, e := png.Decode(bytes.NewReader(studioBanner)); e == nil {
		u.frames = append(u.frames, still)
	}
	u.animationStart = time.Now()
	u.frame = -1
}

func (u *nativeSetupWindow) updateBanner() {
	if len(u.frames) == 0 || u.heroW <= 0 || u.heroH <= 0 {
		return
	}
	index := min(len(u.frames)-1, int(time.Since(u.animationStart)/(65*time.Millisecond)))
	if index == u.frame {
		return
	}
	img := u.frames[index]
	w, h := u.px(u.heroW), u.px(u.heroH)
	info := setupBitmapInfo{Size: 40, Width: w, Height: -h, Planes: 1, BitCount: 32}
	var pixels unsafe.Pointer
	bitmap, _, _ := setupGDI.NewProc("CreateDIBSection").Call(0, uintptr(unsafe.Pointer(&info)), 0, uintptr(unsafe.Pointer(&pixels)), 0, 0)
	if bitmap == 0 || pixels == nil {
		return
	}
	data := unsafe.Slice((*byte)(pixels), int(w*h*4))
	bounds := img.Bounds()
	for y := int32(0); y < h; y++ {
		for x := int32(0); x < w; x++ {
			r, g, b, _ := img.At(bounds.Min.X+int(x)*bounds.Dx()/int(w), bounds.Min.Y+int(y)*bounds.Dy()/int(h)).RGBA()
			i := int((y*w + x) * 4)
			data[i], data[i+1], data[i+2], data[i+3] = byte(b>>8), byte(g>>8), byte(r>>8), 0
		}
	}
	old, _, _ := sendWindowMessage.Call(u.logo, 0x0172, 0, bitmap)
	if old != 0 && old != u.bitmap {
		setupGDI.NewProc("DeleteObject").Call(old)
	}
	if u.bitmap != 0 {
		setupGDI.NewProc("DeleteObject").Call(u.bitmap)
	}
	u.bitmap = bitmap
	u.frame = index
}

func (u *nativeSetupWindow) updateTransfer(status snapshot, busy bool) {
	if u.uninstall {
		return
	}
	steps := []string{"System check", "Workspace", "Python runtime", "CAD packages", "Startup checks", "Finish"}
	for i, name := range steps {
		mark := "○ "
		if status.Done || i < status.Step {
			mark = "✓ "
		} else if i == status.Step {
			mark = "● "
		}
		steps[i] = mark + name
	}
	checklist := strings.Join(steps[:3], "     ") + "\r\n" + strings.Join(steps[3:], "     ")
	if checklist != u.lastSteps {
		winSetText(u.steps, checklist)
		u.lastSteps = checklist
	}
	text := downloadLabel(status)
	if text != u.lastTransfer {
		winSetText(u.transferText, text)
		u.lastTransfer = text
	}
	d := status.Transfer
	marquee := busy && ((d.Active && d.Total <= 0) || (!d.Active && (status.Step == 2 || status.Step == 3)))
	if marquee != u.marquee {
		get := setupUser.NewProc("GetWindowLongW")
		set := setupUser.NewProc("SetWindowLongW")
		style, _, _ := get.Call(u.transferBar, winInt(-16))
		if marquee {
			style |= 8
		} else {
			style &^= 8
		}
		set.Call(u.transferBar, winInt(-16), style)
		var enable uintptr
		if marquee {
			enable = 1
		}
		sendWindowMessage.Call(u.transferBar, 0x040A, enable, 45)
		u.marquee = marquee
	}
	if !marquee {
		var value int64
		if d.Active && d.Total > 0 {
			value = min(1000, d.Bytes*1000/d.Total)
		}
		if status.Done {
			value = 1000
		}
		sendWindowMessage.Call(u.transferBar, 0x0402, uintptr(value), 0)
	}
}

func (u *nativeSetupWindow) refresh() {
	busy := u.attempt.busy()
	if u.closing && !busy {
		destroyWindow.Call(u.hwnd)
		return
	}
	status := u.state.status()
	v := nativeView(status, busy, u.closing)
	u.updateBanner()
	u.updateTransfer(status, busy)
	if !u.uninstall && len(status.Packages) > 0 {
		lines := []string{"Reported downloads:"}
		for _, p := range status.Packages {
			mark := "↓ "
			if p.Done {
				mark = "✓ "
			}
			line := mark + p.Name
			if p.Size != "" {
				line += " (" + p.Size + ")"
			}
			lines = append(lines, line)
		}
		v.Details = strings.Join(lines, "\r\n") + "\r\n\r\n" + v.Details
	}
	if u.uninstall && status.Done {
		v.Title = "Uninstall complete — PY.cad was removed"
	}
	elapsed := int(time.Since(u.started).Seconds())
	stage := v.Stage + 1
	if stage > 6 {
		stage = 6
	}
	activity := fmt.Sprintf("Stage %d of 6 · working · %02d:%02d elapsed", stage, elapsed/60, elapsed%60)
	if !busy {
		activity = "Setup stopped. Review the details, open the log, or Retry."
	}
	if status.Done {
		activity = "Complete. Click Close to exit setup. PY.cad stays open."
		if u.uninstall {
			activity = "Complete. Click Close to exit the uninstaller. Drawings and settings were kept."
		}
	}
	if u.closing {
		activity = "Stopping the current operation before closing…"
	}
	if activity != u.lastActivity {
		winSetText(u.activity, activity)
		u.lastActivity = activity
	}
	if v.Title != u.last.Title {
		winSetText(u.title, v.Title)
	}
	if v.Details != u.last.Details {
		winSetText(u.details, v.Details)
		sendWindowMessage.Call(u.details, 0x00B1, ^uintptr(0), ^uintptr(0)) // EM_SETSEL at end
		sendWindowMessage.Call(u.details, 0x00B7, 0, 0)                     // EM_SCROLLCARET
	}
	if v.CloseLabel != u.last.CloseLabel {
		winSetText(u.closeButton, v.CloseLabel)
	}
	sendWindowMessage.Call(u.bar, 0x0402, uintptr(v.Stage), 0) // PBM_SETPOS (stages, not byte percent)
	winEnable(u.retryButton, v.Retry)
	winEnable(u.closeButton, v.CanClose)
	winEnable(u.logButton, u.state.logPath() != "")
	u.last = v
}

func (u *nativeSetupWindow) requestClose() {
	if u.closing {
		return
	}
	if !u.attempt.busy() {
		destroyWindow.Call(u.hwnd)
		return
	}
	message := "Stop this installation? Setup will stop its current operation before closing. Your drawings are kept. Any completed installation remains available."
	title := "Cancel PY.cad setup?"
	if u.uninstall {
		message = "Stop uninstalling? Some application files may already be removed. Drawings and settings are kept. Run the uninstaller again to finish removal."
		title = "Stop PY.cad uninstall?"
	}
	answer, _, _ := setupUser.NewProc("MessageBoxW").Call(u.hwnd,
		uintptr(unsafe.Pointer(winText(message))),
		uintptr(unsafe.Pointer(winText(title))), 0x124) // YESNO | QUESTION
	if answer != 6 {
		return
	}
	u.closing = true
	u.cancel()
	u.refresh()
}

func (u *nativeSetupWindow) openLog() {
	file := u.state.logPath()
	if file == "" {
		return
	}
	buffer := make([]uint16, 32768)
	n, _, _ := setupKernel.NewProc("GetSystemDirectoryW").Call(uintptr(unsafe.Pointer(&buffer[0])), uintptr(len(buffer)))
	if n == 0 || n >= uintptr(len(buffer)) {
		return
	}
	cmd := exec.Command(filepath.Join(syscall.UTF16ToString(buffer), "notepad.exe"), file)
	// Notepad is a GUI program: unlike background console helpers it must not
	// inherit SW_HIDE, otherwise its log window may remain invisible.
	cmd.SysProcAttr = &syscall.SysProcAttr{CreationFlags: 0x00000200}
	if err := cmd.Start(); err != nil {
		u.state.note("Could not open log: " + err.Error())
	} else {
		_ = cmd.Process.Release()
	}
}

func (u *nativeSetupWindow) showLegal() {
	hwnd, _, _ := createWindow.Call(0, uintptr(unsafe.Pointer(winText("PYCAD_NATIVE_SETUP"))),
		uintptr(unsafe.Pointer(winText("PY.cad — Licenses and Legal"))), 0x00CF0000|wsVisible,
		0x80000000, 0x80000000, winInt(u.px(720)), winInt(u.px(560)), u.hwnd, 0, u.instance, 0)
	if hwnd == 0 {
		return
	}
	edit, _, _ := createWindow.Call(0x200, uintptr(unsafe.Pointer(winText("EDIT"))), 0,
		wsChild|wsVisible|0x00200000|0x00100000|0x0004|0x0040|0x0080|0x0800,
		0, 0, 0, 0, hwnd, 0, u.instance, 0)
	if edit == 0 {
		destroyWindow.Call(hwnd)
		return
	}
	u.auxiliary[hwnd] = edit
	sendWindowMessage.Call(edit, 0x0030, u.font, 1)
	sendWindowMessage.Call(edit, 0x00C5, 1024*1024, 0) // EM_SETLIMITTEXT
	winSetText(edit, strings.ReplaceAll(strings.ReplaceAll(string(nativeLegalText), "\r\n", "\n"), "\n", "\r\n"))
	var r setupRect
	setupUser.NewProc("GetClientRect").Call(hwnd, uintptr(unsafe.Pointer(&r)))
	setupUser.NewProc("MoveWindow").Call(edit, 0, 0, winInt(r.Right), winInt(r.Bottom), 1)
}

func setupWindowProc(hwnd uintptr, message uint32, wParam, lParam uintptr) uintptr {
	u := activeSetupWindow
	if u != nil {
		if edit, ok := u.auxiliary[hwnd]; ok {
			switch message {
			case wmSize:
				setupUser.NewProc("MoveWindow").Call(edit, 0, 0, lParam&0xffff, (lParam>>16)&0xffff, 1)
				return 0
			case wmClose:
				destroyWindow.Call(hwnd)
				return 0
			case wmDestroy:
				delete(u.auxiliary, hwnd)
				return 0
			}
		}
		if hwnd == u.hwnd {
			switch message {
			case wmSize:
				u.layout()
				return 0
			case wmTimer:
				u.refresh()
				return 0
			case wmCommand:
				if (wParam>>16)&0xffff != 0 {
					break
				}
				switch int(wParam & 0xffff) {
				case idClose:
					u.requestClose()
				case idRetry:
					if !u.closing && !u.attempt.busy() && u.state.status().Error != "" {
						u.started = time.Now()
						u.attempt.start(u.ctx, u.state, true, u.job)
						u.refresh()
					}
				case idLog:
					u.openLog()
				case idLegal:
					u.showLegal()
				}
				return 0
			case wmClose:
				u.requestClose()
				return 0
			case wmDestroy:
				setupUser.NewProc("KillTimer").Call(hwnd, 1)
				for child := range u.auxiliary {
					destroyWindow.Call(child)
				}
				setupUser.NewProc("PostQuitMessage").Call(0)
				return 0
			}
		}
	}
	value, _, _ := defaultWindow.Call(hwnd, uintptr(message), wParam, lParam)
	return value
}

func runNativeSetup(ctx context.Context, cancel context.CancelFunc, o options, p platform, m manifest, s *progress) error {
	return runNativeWindow(ctx, cancel, s, func(ctx context.Context) error {
		return withSetupLock(o.Root, func() error { return install(ctx, o, p, m, s) })
	}, nil)
}

// ready is used by Windows-only acceptance tests to drive the actual window;
// normal setup always supplies nil and always uses the real installation job.
func runNativeWindow(ctx context.Context, cancel context.CancelFunc, s *progress, job func(context.Context) error, ready func(uintptr)) error {
	return runNativeWindowMode(ctx, cancel, s, job, ready, false)
}

func runNativeWindowMode(ctx context.Context, cancel context.CancelFunc, s *progress, job func(context.Context) error, ready func(uintptr), uninstall bool) error {
	runtime.LockOSThread()
	defer runtime.UnlockOSThread()
	u := &nativeSetupWindow{uninstall: uninstall, ctx: ctx, cancel: cancel, state: s, job: job, dpi: 96, auxiliary: map[uintptr]uintptr{}, started: time.Now()}
	activeSetupWindow = u
	defer func() { activeSetupWindow = nil }()
	if proc := setupUser.NewProc("SetProcessDPIAware"); proc.Find() == nil {
		proc.Call()
	}
	if proc := setupUser.NewProc("GetDpiForSystem"); proc.Find() == nil {
		if v, _, _ := proc.Call(); v >= 96 && v <= 480 {
			u.dpi = int32(v)
		}
	}
	u.instance, _, _ = setupKernel.NewProc("GetModuleHandleW").Call(0)
	cursor, _, _ := setupUser.NewProc("LoadCursorW").Call(0, 32512)
	icon, _, _ := setupUser.NewProc("LoadIconW").Call(u.instance, 1)
	if icon == 0 {
		icon, _, _ = setupUser.NewProc("LoadIconW").Call(0, 32512)
	}
	wc := setupWindowClass{Procedure: setupWindowCallback, Instance: u.instance, Icon: icon, SmallIcon: icon, Cursor: cursor, Background: 6, ClassName: winText("PYCAD_NATIVE_SETUP")}
	wc.Size = uint32(unsafe.Sizeof(wc))
	atom, _, err := setupUser.NewProc("RegisterClassExW").Call(uintptr(unsafe.Pointer(&wc)))
	if atom == 0 {
		return fmt.Errorf("Register setup window: %w", err)
	}
	defer func() {
		setupUser.NewProc("UnregisterClassW").Call(uintptr(unsafe.Pointer(wc.ClassName)), u.instance)
		runtime.KeepAlive(wc.ClassName)
	}()
	common := struct{ Size, Classes uint32 }{8, 0x20}
	if ok, _, e := setupCommon.NewProc("InitCommonControlsEx").Call(uintptr(unsafe.Pointer(&common))); ok == 0 {
		return fmt.Errorf("Initialize progress control: %w", e)
	}
	for _, item := range []struct {
		target       *uintptr
		size, weight int32
	}{{&u.font, 15, 400}, {&u.headingFont, 24, 600}} {
		*item.target, _, _ = setupGDI.NewProc("CreateFontW").Call(winInt(-u.px(item.size)), 0, 0, 0, uintptr(item.weight), 0, 0, 0, 1, 0, 0, 5, 0, uintptr(unsafe.Pointer(winText("Segoe UI"))))
		if *item.target == 0 {
			return fmt.Errorf("Create setup font")
		}
		defer setupGDI.NewProc("DeleteObject").Call(*item.target)
	}
	screenW, _, _ := setupUser.NewProc("GetSystemMetrics").Call(0)
	screenH, _, _ := setupUser.NewProc("GetSystemMetrics").Call(1)
	w, h := u.px(760), u.px(696)
	if w > int32(screenW)-40 {
		w = int32(screenW) - 40
	}
	if h > int32(screenH)-40 {
		h = int32(screenH) - 40
	}
	windowTitle := "PY.cad Setup — " + s.status().Version
	if uninstall {
		windowTitle = "Uninstall PY.cad — " + s.status().Version
	}
	u.hwnd, _, err = createWindow.Call(0x00010000, uintptr(unsafe.Pointer(wc.ClassName)), uintptr(unsafe.Pointer(winText(windowTitle))),
		0x00CA0000, winInt((int32(screenW)-w)/2), winInt((int32(screenH)-h)/2), winInt(w), winInt(h), 0, 0, u.instance, 0)
	if u.hwnd == 0 {
		return fmt.Errorf("Create setup window: %w", err)
	}
	// Startup failures destroy the hidden frame; no browser fallback is used.
	shown := false
	defer func() {
		if !shown {
			destroyWindow.Call(u.hwnd)
		}
	}()
	items := []struct {
		target      *uintptr
		class, text string
		style       uint32
		id          int
	}{
		{&u.logo, "STATIC", "", 0x000E, 0},
		{&u.heading, "STATIC", "PY.cad Studio Setup", 0, 0},
		{&u.subtitle, "STATIC", s.status().Version + " · " + s.status().Platform, 0, 0},
		{&u.title, "STATIC", "Preparing setup…", 0, 0},
		{&u.bar, "msctls_progress32", "", 0, 0},
		{&u.steps, "STATIC", "", 0, 0},
		{&u.transferText, "STATIC", "", 0, 0},
		{&u.transferBar, "msctls_progress32", "", 0, 0},
		{&u.activity, "STATIC", "Preparing…", 0, 0},
		{&u.location, "EDIT", s.status().Root, 0x0800 | 0x0080, 0},
		{&u.details, "EDIT", "", 0x0004 | 0x0040 | 0x0800 | 0x00200000, 0},
		{&u.legalButton, "BUTTON", "Licenses", wsTabStop, idLegal},
		{&u.logButton, "BUTTON", "Open log", wsTabStop, idLog},
		{&u.retryButton, "BUTTON", "Retry", wsTabStop, idRetry},
		{&u.closeButton, "BUTTON", "Cancel", wsTabStop | 1, idClose},
	}
	for _, item := range items {
		*item.target, err = u.control(item.class, item.text, item.style, item.id)
		if err != nil {
			return err
		}
	}
	if uninstall {
		winSetText(u.heading, "Uninstall PY.cad")
		winSetText(u.title, "Preparing uninstall…")
	}
	sendWindowMessage.Call(u.heading, 0x0030, u.headingFont, 1)
	sendWindowMessage.Call(u.details, 0x00C5, 1024*1024, 0)
	sendWindowMessage.Call(u.bar, 0x0406, 0, 6) // PBM_SETRANGE32: six stages
	if uninstall {
		winSetText(u.steps, "Removal progress")
		winSetText(u.transferText, "Drawings and settings are kept.")
		setupUser.NewProc("ShowWindow").Call(u.transferBar, 0)
	}
	sendWindowMessage.Call(u.transferBar, 0x0406, 0, 1000)
	u.prepareBanner()
	defer func() {
		if u.bitmap != 0 {
			setupGDI.NewProc("DeleteObject").Call(u.bitmap)
		}
	}()
	u.layout()
	u.attempt.start(ctx, s, false, job)
	u.refresh()
	setupUser.NewProc("ShowWindow").Call(u.hwnd, 5)
	setupUser.NewProc("UpdateWindow").Call(u.hwnd)
	if timer, _, e := setupUser.NewProc("SetTimer").Call(u.hwnd, 1, 65, 0); timer == 0 {
		u.closing = true
		cancel()
		for u.attempt.busy() {
			time.Sleep(20 * time.Millisecond)
		}
		destroyWindow.Call(u.hwnd)
		return fmt.Errorf("Start progress timer: %w", e)
	}
	shown = true
	if ready != nil {
		ready(u.hwnd)
	}
	var message setupMessage
	for {
		value, _, e := setupUser.NewProc("GetMessageW").Call(uintptr(unsafe.Pointer(&message)), 0, 0, 0)
		if int32(value) == -1 {
			cancel()
			return fmt.Errorf("Setup message loop: %w", e)
		}
		if value == 0 {
			break
		}
		if handled, _, _ := setupUser.NewProc("IsDialogMessageW").Call(u.hwnd, uintptr(unsafe.Pointer(&message))); handled != 0 {
			continue
		}
		setupUser.NewProc("TranslateMessage").Call(uintptr(unsafe.Pointer(&message)))
		setupUser.NewProc("DispatchMessageW").Call(uintptr(unsafe.Pointer(&message)))
	}
	if !s.status().Done {
		return errNativeSetupIncomplete
	}
	return nil
}
