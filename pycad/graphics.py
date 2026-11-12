"""Persistent graphics policy, isolated detection, live switching and recovery."""

import json
import logging
import os
import platform
import sys
import tempfile
import weakref
from pathlib import Path

from PyQt6.QtCore import QObject, QProcess, QProcessEnvironment, QTimer, Qt, pyqtSignal
from PyQt6.QtWidgets import QApplication, QWidget
from . import appsettings
from .graphics_surface import PaintSurface, replace_canvas_viewport

logger = logging.getLogger(__name__)
MODES = {"auto": "Auto (GPU when available)", "hardware": "GPU / OpenGL", "software": "CPU / Software"}
DRAWING_PATHS = {'cached':'Cached drawing (CPU image + selected display renderer)', 'direct':'Direct drawing (selected renderer paints geometry)', 'progressive':'Progressive viewport (time-sliced + subpixel preview)'}
SOFTWARE_RENDERERS = ("llvmpipe", "softpipe", "swrast", "swiftshader", "gdi generic",
                      "software rasterizer", "software renderer", "microsoft basic render", "warp")


def renderer_class(renderer):
    text = renderer.lower()
    if not text.strip():
        return "unknown"
    if any(marker in text for marker in SOFTWARE_RENDERERS):
        return "software"
    if any(marker in text for marker in ("intel", "nvidia", "geforce", "quadro", "amd", "radeon",
                                         "apple", "adreno", "mali", "powervr", "virgl", "svga3d", "v3d", "videocore")):
        return "hardware_or_virtual"
    return "unknown"


def requested_mode():
    override = os.environ.get("PYCAD_GRAPHICS", "").lower()
    saved = str(appsettings.get_settings().value("graphics/mode", "auto")).lower()
    return override if override in MODES else saved if saved in MODES else "auto"


def validated_probe(payload):
    if not isinstance(payload, dict) or payload.get("format") != 1:
        raise ValueError("Invalid graphics probe response")
    if payload.get("render_test_passed") is not True or payload.get("paint_engine") != "OpenGL2" or payload.get("frames_tested") != 2:
        raise ValueError(str(payload.get("reason", "The OpenGL rendering test failed"))[:512])
    result = {"format": 1, "render_test_passed": True, "paint_engine": "OpenGL2", "frames_tested": 2}
    for key in ("vendor", "renderer", "version"):
        if not isinstance(payload.get(key), str) or not payload[key].strip() or len(payload[key]) > 512:
            raise ValueError("Invalid graphics driver details")
        result[key] = payload[key]
    result["renderer_class"] = renderer_class(result["renderer"])
    return result


class GraphicsController(QObject):
    changed = pyqtSignal()

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.mode = requested_mode()
        path=str(appsettings.get_settings().value('graphics/drawing_path','cached'))
        self.drawing_path=path if path in DRAWING_PATHS else 'cached'
        self.window.canvas.drawing_path=self.drawing_path
        self.window.canvas.reuse_nearby_zooms=appsettings.get_settings().value('graphics/reuse_nearby_zooms',True,type=bool)
        self.window.canvas.progressive_lod=appsettings.get_settings().value('graphics/progressive_lod',True,type=bool)
        self.backend = "software"
        self.reason = "Graphics detection has not run"
        self.probe = {}
        self.live_driver = {}
        self.process = None
        self._stdout = bytearray()
        self._stderr = bytearray()
        self._pending = set()
        self._surfaces = weakref.WeakSet()
        self._closed = False
        self._failed = False
        self._probe_directory = None
        self.recovery = appsettings.get_settings().value("graphics/recovery_needed", False, type=bool)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(12000)
        self.timer.timeout.connect(lambda: self._probe_failed("Graphics detection timed out"))

    def start(self):
        self.set_mode(self.mode, save=False)

    def set_mode(self, mode, save=True, retry=False):
        if mode not in MODES:
            raise ValueError("Graphics mode must be auto, hardware or software")
        self.mode = mode
        if save:
            appsettings.get_settings().setValue("graphics/mode", mode)
        self._cancel_probe()
        if retry or save:
            self.recovery = False
            self._failed = False
            self._clear_guard()
        if mode == "software":
            self._use_software("Software rendering selected")
        elif self.recovery:
            self._use_software("Software recovery: the previous OpenGL activation did not finish. Use Retry detection to try again.")
        elif QApplication.platformName() in ("offscreen", "minimal", "vnc"):
            self._use_software("This Qt display plugin does not support OpenGL widgets")
        elif self._failed and not retry:
            self._use_software(self.reason)
        elif self.probe and not retry:
            self._choose_backend()
        else:
            self._use_software("Checking the graphics driver…")
            self._start_probe()
        self.changed.emit()

    def retry(self):
        self.set_mode(self.mode, retry=True)

    def _start_probe(self):
        self.probe = {}
        proc = self.process = QProcess(self)
        directory = self._probe_directory = tempfile.TemporaryDirectory(prefix="pycad-graphics-")
        report_path = str(Path(directory.name) / "report.json")
        self._stdout.clear()
        self._stderr.clear()
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONUTF8", "1")
        proc.setProcessEnvironment(env)
        proc.setWorkingDirectory(str(Path(__file__).resolve().parents[1]))
        program, args = self._probe_command(report_path)
        # A private file also works with windowed/frozen Python (stdout=None).
        proc.readyReadStandardOutput.connect(lambda: self._read_probe(proc))
        proc.readyReadStandardError.connect(lambda: self._read_probe(proc))
        proc.finished.connect(lambda code, status: self._finish_probe(proc, code, status))
        proc.finished.connect(lambda *_: directory.cleanup())
        proc.errorOccurred.connect(lambda error: self._process_error(proc, error))
        self.timer.start()
        proc.start(program, args)

    @staticmethod
    def _probe_command(report_path):
        args = ["--graphics-probe"] if getattr(sys, "frozen", False) else ["-m", "pycad.graphics_probe"]
        return sys.executable, args + [report_path]

    def _read_probe(self, proc):
        if proc is not self.process:
            return
        self._stdout.extend(bytes(proc.readAllStandardOutput()))
        self._stderr.extend(bytes(proc.readAllStandardError()))
        if len(self._stdout) > 65536 or len(self._stderr) > 65536:
            self._probe_failed("The graphics driver produced excessive diagnostic output")

    def _process_error(self, proc, error):
        if proc is self.process and error == QProcess.ProcessError.FailedToStart:
            self._probe_failed("The isolated graphics check could not start")

    def _finish_probe(self, proc, code, status):
        if proc is not self.process:
            return
        self._read_probe(proc)
        if proc is not self.process:
            return
        self.timer.stop()
        self.process = None
        proc.deleteLater()
        try:
            if status != QProcess.ExitStatus.NormalExit:
                raise ValueError("The graphics driver crashed during detection")
            path = Path(self._probe_directory.name) / "report.json"
            if not path.is_file() or path.stat().st_size > 65536:
                raise ValueError("The graphics check did not return a bounded report")
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.probe = validated_probe(payload)
            if code != 0:
                raise ValueError("The isolated graphics check failed")
            self._choose_backend()
        except (ValueError, UnicodeError, TypeError, OSError) as ex:
            self._failed = True
            self._use_software(str(ex))

    def _choose_backend(self):
        kind = self.probe["renderer_class"]
        if kind == "software":
            self._use_software("The OpenGL driver reports CPU rendering (" + self.probe["renderer"] + ")")
        elif kind == "unknown" and self.mode == "auto":
            self._use_software("The driver passed rendering checks but its hardware type is unknown. Hardware mode can try this driver.")
        else:
            self._apply_backend("opengl")
            self.reason = "OpenGL rendering active; driver reports " + self.probe["renderer"]
            self.changed.emit()

    def _cancel_probe(self):
        self.timer.stop()
        proc, self.process = self.process, None
        if proc is not None:
            proc.finished.connect(proc.deleteLater)
            if proc.state() != QProcess.ProcessState.NotRunning:
                proc.kill()
            else:
                proc.deleteLater()
                if self._probe_directory is not None:
                    self._probe_directory.cleanup()

    def _probe_failed(self, reason):
        self._cancel_probe()
        self._failed = True
        self._use_software(reason)

    def _use_software(self, reason):
        self._apply_backend("software")
        self.reason = reason
        self.changed.emit()

    def _apply_backend(self, backend):
        self.backend = backend
        canvas = self.window.canvas
        is_gl = isinstance(canvas.viewport(), PaintSurface)
        if is_gl != (backend == "opengl"):
            surface = self.create_surface(canvas) if backend == "opengl" else QWidget(canvas)
            replace_canvas_viewport(canvas, surface)
        workspace = self.window.model_workspace
        if workspace is not None:
            for view in workspace.views:
                view.set_graphics_backend(backend)
        if backend == "software":
            self._pending.clear()
            self._clear_guard()
        canvas.viewport().update()

    def create_surface(self, parent, draw=None):
        self._set_guard()
        surface = PaintSurface(parent, draw)
        self._surfaces.add(surface)
        surface.started.connect(self._surface_started)
        surface.ready.connect(self._surface_ready)
        # Defer replacement until the driver/paint callback has unwound.
        surface.failed.connect(self._surface_error, Qt.ConnectionType.QueuedConnection)
        return surface

    def release_surface(self, surface):
        surface.retire()
        self._pending.discard(id(surface))
        self._surfaces.discard(surface)
        if not self._pending:
            self._clear_guard()

    def _surface_started(self, surface):
        if self.backend == "opengl" and not self._closed:
            self._pending.add(id(surface))
            self._set_guard()

    def _surface_ready(self, surface, details):
        if self.backend != "opengl" or surface.retired or self._closed:
            return
        self.live_driver = dict(details)
        self._pending.discard(id(surface))
        if renderer_class(details.get("renderer", "")) == "software":
            QTimer.singleShot(0, lambda: self._surface_failed("The active viewport changed to a software OpenGL driver"))
        elif not self._pending:
            self._clear_guard()
        self.changed.emit()

    def _surface_failed(self, reason):
        if self.backend != "opengl" or self._closed:
            return
        logger.warning("Graphics fallback: %s", reason)
        self._failed = True
        self._use_software(reason + ". Software rendering is active.")

    def _surface_error(self, reason):
        surface = self.sender()
        if surface is not None and not surface.retired:
            self._surface_failed(reason)

    @staticmethod
    def _set_guard():
        prefs = appsettings.get_settings()
        prefs.setValue("graphics/recovery_needed", True)
        prefs.sync()

    def _clear_guard(self):
        # Preserve a previous crash marker until an explicit retry/selection.
        if self.recovery:
            return
        prefs = appsettings.get_settings()
        prefs.setValue("graphics/recovery_needed", False)
        prefs.sync()

    def set_drawing_path(self,path):
        if path not in DRAWING_PATHS:raise ValueError('Drawing path must be cached or direct')
        self.drawing_path=path
        appsettings.get_settings().setValue('graphics/drawing_path',path)
        self.window.canvas.drawing_path=path
        self.window.canvas._drawing_image_key=None
        self.window.canvas._selection_image_key=None
        self.window.canvas.viewport().update()
        self.changed.emit()

    def process_execution(self):
        display='GPU / OpenGL driver' if self.backend=='opengl' else 'CPU / Software'
        drawing=display if self.drawing_path=='direct' else 'CPU image cache; '+display+' display'
        return {'2D geometry and hatch painting':drawing,'3D viewport painting':display,
                'Hatch boundaries and pattern generation':'CPU',
                'DWG/DXF reading and conversion':'CPU',
                'Geometry, selection and 3D projection':'CPU','BOQ and quantities':'CPU'}

    def report(self):
        from PyQt6.QtCore import QT_VERSION_STR, PYQT_VERSION_STR, qVersion
        from ._version import __version__
        return {
            "format": 1, "application": "PY.cad", "application_version": __version__,
            "os": platform.system(), "architecture": platform.machine(),
            "qt": qVersion(), "qt_bindings_built_against": QT_VERSION_STR, "pyqt": PYQT_VERSION_STR,
            "display_plugin": QApplication.platformName(), "requested_mode": self.mode,
            "active_backend": self.backend, "drawing_path": self.drawing_path,
            "process_execution": self.process_execution(), "detecting": self.process is not None,
            "reason": self.reason, "probe": dict(self.probe),
            "active_driver": dict(self.live_driver) if self.backend == "opengl" else {},
            "canvas_paint_engine": getattr(self.window.canvas, "paint_engine_name", "unpainted"),
            "presented_frames": sum(s.frame_count for s in self._surfaces if not s.retired),
            "physical_gpu_verified": False,
            "scope": "GPU/OpenGL is a display renderer, not a general calculation engine. Direct 2D drawing sends vector paint commands to the selected viewport; cached 2D drawing builds CPU images then displays them. Hatch boundary/pattern generation, geometry, selection, 3D projection, face ordering, DWG/DXF parsing and BOQ remain on CPU. Driver strings may describe a virtual GPU.",
        }

    def shutdown(self):
        self._closed = True
        self._cancel_probe()
        for surface in self._surfaces:
            surface.retire()
        self._clear_guard()
