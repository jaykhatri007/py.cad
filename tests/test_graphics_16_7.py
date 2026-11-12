"""Policy, isolated-process recovery and lossless renderer switching.

Fake surfaces test UI state only; they are never GPU rendering evidence.
Real OpenGL pixel checks live in pycad.graphics_probe and the release QA.
"""

import json
import sys
import time
from pathlib import Path

import pytest
from PyQt6.QtCore import QPointF, QTimer, pyqtSignal
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QWidget
from pycad import appsettings, graphics
from pycad.geometry import LineEntity, Point, RectangleEntity
from pycad.model3d import create_extrusion
from pycad.native_io import document_to_dict


def probe(renderer="llvmpipe (LLVM)"):
    return dict(format=1, render_test_passed=True, frames_tested=2,
                paint_engine="OpenGL2", vendor="Mesa", renderer=renderer, version="4.5")


@pytest.mark.parametrize("name,expected", [
    ("llvmpipe (LLVM 20)", "software"), ("ANGLE (SwiftShader)", "software"),
    ("GDI Generic", "software"), ("Microsoft Basic Render Driver", "software"),
    ("Mesa Intel UHD Graphics", "hardware_or_virtual"), ("NVIDIA RTX", "hardware_or_virtual"),
    ("Apple M4", "hardware_or_virtual"), ("virgl", "hardware_or_virtual"),
    ("Unidentified adapter", "unknown"), ("", "unknown"),
])
def test_driver_classification(name, expected):
    assert graphics.renderer_class(name) == expected


@pytest.mark.parametrize("change", [
    {"format": 2}, {"render_test_passed": False}, {"frames_tested": 1},
    {"paint_engine": "Raster"}, {"renderer": ""}, {"vendor": "x" * 513},
])
def test_incomplete_probe_never_enables_opengl(change):
    with pytest.raises(ValueError):
        graphics.validated_probe({**probe(), **change})


def spin(qapp, predicate, limit=4):
    deadline = time.monotonic() + limit
    while not predicate() and time.monotonic() < deadline:
        qapp.processEvents()
        QTest.qWait(10)
    assert predicate(), "Timed out waiting for the graphics operation"


def use_probe_script(controller, monkeypatch, body):
    monkeypatch.setattr(QApplication, "platformName", staticmethod(lambda: "xcb"))
    monkeypatch.setattr(controller, "_probe_command", lambda path: (
        sys.executable, ["-c", "import sys,time,json;from pathlib import Path;" + body, path]))


def test_display_fallback_preserves_canvas_and_saved_mode(main_window):
    c = main_window.canvas
    main_window.set_tool("LINE")
    tool = main_window.current_tool
    tool.points = [Point(4, 7)]
    c.pan_offset, c.zoom = QPointF(6, 9), 42
    c.snap_modes, c.snap_radius_px = {"Endpoint"}, 19
    main_window.graphics.set_mode("hardware")
    assert main_window.graphics.backend == "software"
    assert main_window.graphics.process is None
    assert main_window.canvas is c and main_window.current_tool is tool
    assert tool.points[0].x == 4 and c.zoom == 42
    assert c.snap_modes == {"Endpoint"} and c.snap_radius_px == 19
    assert appsettings.get_settings().value("graphics/mode") == "hardware"
    assert graphics.requested_mode() == "hardware"


def test_environment_recovery_override(main_window, monkeypatch):
    appsettings.get_settings().setValue("graphics/mode", "hardware")
    monkeypatch.setenv("PYCAD_GRAPHICS", "software")
    assert graphics.requested_mode() == "software"
    monkeypatch.setenv("PYCAD_GRAPHICS", "invalid")
    assert graphics.requested_mode() == "hardware"


def test_probe_is_responsive_and_cpu_driver_is_honestly_reported(main_window, qapp, monkeypatch):
    ctl = main_window.graphics
    payload = json.dumps(probe())
    use_probe_script(ctl, monkeypatch, "time.sleep(.35);Path(sys.argv[1]).write_text(" + repr(payload) + ")")
    ticks = []
    timer = QTimer()
    timer.timeout.connect(lambda: ticks.append(ctl.process is not None))
    timer.start(5)
    ctl.set_mode("auto", retry=True)
    assert ctl.process is not None
    directory = Path(ctl._probe_directory.name)
    spin(qapp, lambda: ctl.process is None)
    timer.stop()
    qapp.processEvents()
    assert any(ticks), "The UI timer must run while the graphics process is active"
    assert ctl.backend == "software"
    assert ctl.report()["probe"]["renderer_class"] == "software"
    assert ctl.report()["physical_gpu_verified"] is False
    assert not directory.exists()


@pytest.mark.parametrize("body,reason", [
    ("Path(sys.argv[1]).write_text('not json')", "Expecting value"),
    ("sys.exit(5)", "did not return"),
    ("Path(sys.argv[1]).write_text('x'*70000)", "bounded report"),
])
def test_bad_worker_report_falls_back_without_touching_drawing(main_window, qapp, monkeypatch, body, reason):
    ctl = main_window.graphics
    entity = LineEntity(Point(1, 2), Point(3, 4))
    main_window.document.add_entity(entity)
    before = document_to_dict(main_window.document)
    use_probe_script(ctl, monkeypatch, body)
    ctl.set_mode("hardware", retry=True)
    spin(qapp, lambda: ctl.process is None)
    assert ctl.backend == "software" and reason in ctl.reason
    assert document_to_dict(main_window.document) == before


def test_timeout_and_switch_to_software_kill_isolated_probe(main_window, qapp, monkeypatch):
    ctl = main_window.graphics
    use_probe_script(ctl, monkeypatch, "time.sleep(30)")
    ctl.timer.setInterval(100)
    ctl.set_mode("auto", retry=True)
    first = Path(ctl._probe_directory.name)
    spin(qapp, lambda: ctl.process is None)
    spin(qapp, lambda: not first.exists())
    assert "timed out" in ctl.reason
    ctl.set_mode("hardware", retry=True)
    second = Path(ctl._probe_directory.name)
    ctl.set_mode("software")
    spin(qapp, lambda: not second.exists())
    assert ctl.process is None and ctl.backend == "software"


def test_unfinished_activation_starts_in_recovery(main_window, monkeypatch):
    ctl = main_window.graphics
    ctl.recovery = True
    appsettings.get_settings().setValue("graphics/recovery_needed", True)
    monkeypatch.setattr(ctl, "_start_probe", lambda: pytest.fail("Recovery must not start OpenGL"))
    ctl.set_mode("auto", save=False)
    assert ctl.backend == "software" and "recovery" in ctl.reason
    assert appsettings.get_settings().value("graphics/recovery_needed", type=bool)
    ctl.set_mode("software")
    assert not appsettings.get_settings().value("graphics/recovery_needed", type=bool)


class FakeSurface(QWidget):
    started = pyqtSignal(object)
    ready = pyqtSignal(object, dict)
    failed = pyqtSignal(str)

    def __init__(self, parent=None, draw=None):
        super().__init__(parent)
        self.draw = draw
        self.retired = False
        self.frame_count = 0

    def retire(self):
        self.retired = True


def test_renderer_switch_keeps_live_tools_overlays_cameras_and_document(main_window, qapp, monkeypatch):
    monkeypatch.setattr(graphics, "PaintSurface", FakeSurface)
    from pycad import graphics_surface
    monkeypatch.setattr(graphics_surface, "PaintSurface", FakeSurface)
    mw = main_window
    create_extrusion(mw.document, RectangleEntity(Point(0, 0), Point(50, 40)), 20)
    mw.open_model_workspace(four=True)
    qapp.processEvents()  # Finish the workspace's deferred initial Fit all.
    workspace = mw.model_workspace
    view = workspace.active
    view.rotate_camera(18, 21)
    view.camera.pan = (11, 8)
    camera = (view.camera.right, view.camera.up, view.camera.pan)
    mw.show_drafting()
    mw.set_tool("LINE")
    tool = mw.current_tool
    tool.points = [Point(8, 9)]
    c = mw.canvas
    c.snap_modes = {"Endpoint"}
    c.snap_radius_px, c.grid_spacing = 24, 13
    c.zoom, c.pan_offset = 7.5, QPointF(4, -2)
    overlays = [c.command_overlay, c.measurement_overlay, c.dynamic_input, mw.draft_navigation]
    before = document_to_dict(mw.document)
    for _ in range(2):
        mw.graphics._apply_backend("opengl")
        qapp.processEvents()
        assert all(o.parentWidget() is c.viewport() and o.viewport is c.viewport() for o in overlays)
        assert all(v.graphics_surface is not None for v in workspace.views)
        mw.graphics._surface_failed("Simulated context loss")
        qapp.processEvents()
        assert all(v.graphics_surface is None for v in workspace.views)
    assert mw.canvas is c and mw.current_tool is tool
    assert tool.points[0].x == 8 and c.zoom == 7.5
    assert c.pan_offset == QPointF(4, -2)
    assert c.snap_modes == {"Endpoint"} and c.snap_radius_px == 24 and c.grid_spacing == 13
    assert (view.camera.right, view.camera.up, view.camera.pan) == camera
    assert document_to_dict(mw.document) == before
    assert all(o.parentWidget() is c.viewport() and o.viewport is c.viewport() for o in overlays)


def test_compact_dialog_applies_and_exports_actual_status(main_window, monkeypatch, tmp_path):
    from pycad.graphics_ui import GraphicsDialog, QFileDialog
    d = GraphicsDialog(main_window)
    d.mode.setCurrentIndex(2)
    d.apply()
    assert main_window.graphics.mode == "software"
    path = tmp_path / "graphics.json"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(path), ""))
    d.save_report()
    report = json.loads(path.read_text())
    assert report["active_backend"] == "software"
    assert report["physical_gpu_verified"] is False
    assert "CPU" in report["scope"]
    assert "Graphics" in d.windowTitle()
    d.close()
    d.deleteLater()
