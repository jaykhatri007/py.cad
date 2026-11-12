"""DWG reader isolation, provenance, integrity and real conversion acceptance."""

import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

import pytest
from PyQt6 import sip
from pycad.document import Document
from PyQt6.QtCore import QProcess, QTimer, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QProgressDialog, QPushButton

from pycad import dwg_support, dxf_io, native_io


@pytest.fixture(autouse=True)
def compatibility_reader_tests(monkeypatch):
    # This suite exercises the legacy reader, which remains selectable.
    monkeypatch.setenv('PYCAD_DWG_MODE', 'compatibility')


def test_reader_integrity_and_explicit_override(tmp_path, monkeypatch):
    monkeypatch.delenv("PYCAD_DWG_CONVERTER", raising=False)
    monkeypatch.setattr(dwg_support, "VENDOR", tmp_path)
    arch = {"x86_64": "amd64", "AMD64": "amd64"}.get(dwg_support.platform.machine(), dwg_support.platform.machine())
    key = {"linux": "linux", "win32": "windows", "darwin": "darwin"}[sys.platform] + "-" + arch
    name = "dwg2dxf.exe" if sys.platform == "win32" else "dwg2dxf"
    binary = tmp_path / "bin" / key / name
    binary.parent.mkdir(parents=True)
    binary.write_bytes(b"trusted reader")
    (tmp_path / "manifest.json").write_text(json.dumps({"binaries": {key: {name: hashlib.sha256(binary.read_bytes()).hexdigest()}}}))
    assert dwg_support.reader_path() == binary
    binary.write_bytes(b"changed")
    with pytest.raises(dxf_io.DWGSupportError, match="integrity"):
        dwg_support.reader_path()
    monkeypatch.setenv("PYCAD_DWG_CONVERTER", str(binary))
    assert dwg_support.reader_path() == binary
    monkeypatch.setenv("PYCAD_DWG_CONVERTER", "relative-reader")
    with pytest.raises(dxf_io.DWGSupportError, match="absolute"):
        dwg_support.reader_path()


def test_source_is_staged_privately_and_bounded(tmp_path, monkeypatch):
    source = tmp_path / "--my drawing ü.DWG"
    data = b"AC1032" + b"test data"
    source.write_bytes(data)
    target = tmp_path / "private"
    target.mkdir()
    assert dwg_support.stage_source(source, target).name == "input.dwg"
    assert source.read_bytes() == (target / "input.dwg").read_bytes() == data
    assert dwg_support.conversion_arguments()[-1] == "input.dwg"
    monkeypatch.setattr(dwg_support, "MAX_FILE_BYTES", 8)
    target2=tmp_path/"second";target2.mkdir()
    assert dwg_support.stage_source(source,target2).read_bytes()==data


@pytest.mark.parametrize("exit_code,content,limit,match", [
    (1, b"partial", 100, "conversion failed"),
    (0, b"", 100, "no DXF"),
])
def test_reader_output_is_never_accepted_on_failure(tmp_path, monkeypatch, exit_code, content, limit, match):
    (tmp_path / "drawing.dxf").write_bytes(content)
    monkeypatch.setattr(dwg_support, "MAX_FILE_BYTES", limit)
    with pytest.raises(ValueError, match=match):
        dwg_support.checked_output(tmp_path, exit_code, "diagnostics")


def slow_conversion(monkeypatch):
    original = QProcess.start
    children = []
    def start(process, program, arguments):
        children.append(process)
        return original(process, sys.executable, ["-c", "import time; time.sleep(30)"])
    monkeypatch.setattr(QProcess, "start", start)
    monkeypatch.setattr(dwg_support, "reader_path", lambda: Path(sys.executable))
    return children


def test_cancel_kills_direct_converter_and_keeps_workspace(main_window, tmp_path, monkeypatch):
    children = slow_conversion(monkeypatch)
    path = tmp_path / "cancel.dwg"
    path.write_bytes(b"AC1032example")
    before = main_window.document
    def cancel():
        dialog = next(w for w in QApplication.topLevelWidgets() if isinstance(w, QProgressDialog) and w.isVisible())
        QTest.mouseClick(dialog.findChild(QPushButton), Qt.MouseButton.LeftButton)
    QTimer.singleShot(200, cancel)
    assert not main_window._open_path(str(path))
    assert main_window.document is before
    assert len(main_window.drawing_tabs.sessions) == 1
    assert children and all(sip.isdeleted(p) or p.state() == QProcess.ProcessState.NotRunning for p in children)


def test_converter_timeout_keeps_workspace(main_window, tmp_path, monkeypatch):
    from pycad.dwg_ui import load_dwg
    children = slow_conversion(monkeypatch)
    path = tmp_path / "slow.dwg"
    path.write_bytes(b"AC1032example")
    before = main_window.document
    with pytest.raises(ValueError, match="timed out"):
        load_dwg(main_window, str(path), timeout_ms=100)
    assert main_window.document is before
    assert children and all(sip.isdeleted(p) or p.state() == QProcess.ProcessState.NotRunning for p in children)


def test_output_growth_does_not_apply_old_size_cap(main_window,tmp_path,monkeypatch):
    from pycad import dwg_ui
    from pycad import import_ui
    monkeypatch.setattr(dwg_support,'reader_path',lambda:Path(sys.executable))
    monkeypatch.setattr(dwg_support,'conversion_arguments',lambda:['-c',"from pathlib import Path; Path('drawing.dxf').write_bytes(b'x'*4096)"])
    monkeypatch.setattr(dwg_ui,'MAX_FILE_BYTES',2048)
    accepted=[];accepted_doc=Document()
    monkeypatch.setattr(import_ui,'load_dxf',lambda *a,**kw:accepted.append(a[1]) or accepted_doc)
    path=tmp_path/'large.dwg';path.write_bytes(b'AC1032example')
    assert dwg_ui.load_dwg(main_window,str(path),timeout_ms=2000) is accepted_doc
    assert accepted


def test_invalid_converted_dxf_keeps_workspace(main_window, tmp_path, monkeypatch):
    from pycad.dwg_ui import load_dwg
    monkeypatch.setattr(dwg_support, "reader_path", lambda: Path(sys.executable))
    monkeypatch.setattr(dwg_support, "conversion_arguments", lambda: ["-c", "from pathlib import Path; Path('drawing.dxf').write_text('not a DXF')"])
    path = tmp_path / "broken.dwg"
    path.write_bytes(b"AC1032example")
    before = main_window.document
    with pytest.raises(ValueError):
        load_dwg(main_window, str(path))
    assert main_window.document is before


def real_fixture(name):
    directory = os.environ.get("PYCAD_DWG_FIXTURES")
    if not directory:
        pytest.skip("Set PYCAD_DWG_FIXTURES to the upstream 0.14 test/test-data directory")
    path = Path(directory) / name
    assert path.is_file()
    return path


@pytest.mark.parametrize("version", ["2000", "2004", "2007", "2010", "2013", "2018"])
def test_real_dwg_versions_open_without_oda(tmp_path, version):
    original = real_fixture(version + "/Line.dwg")
    source = tmp_path / ("Drawing ü " + version + ".DWG")
    shutil.copyfile(original, source)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    document = dxf_io.import_any(source)
    assert any(e.kind == "LINE" for e in document.entities)
    assert document.source_filepath == str(source)
    assert document.source_archive["filename"] == source.name
    assert document.source_archive["sha256"] == digest
    assert hashlib.sha256(base64.b64decode(document.source_archive["data_base64"])).hexdigest() == digest
    assert dwg_support.NOTE in document.import_warnings
    assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
    native = tmp_path / "editable.pycad"
    native_io.save_project(document, native)
    reopened = native_io.load_project(native)
    assert len(reopened.entities) == len(document.entities)
    assert reopened.source_archive["filename"] == source.name
    with pytest.raises(ValueError, match="protect the source"):
        dxf_io.export_any(document, str(source))


def test_real_gui_dwg_import_preserves_events_and_original(main_window, tmp_path):
    source = tmp_path / "Drawing ü.dwg"
    shutil.copyfile(real_fixture("2018/Line.dwg"), source)
    raw = source.read_bytes()
    ticks = []
    timer = QTimer()
    timer.setInterval(5)
    timer.timeout.connect(lambda: ticks.append(1))
    timer.start()
    try:
        assert main_window._open_path(str(source))
    finally:
        timer.stop()
    assert ticks and any(e.kind == "LINE" for e in main_window.document.entities)
    assert main_window.document.filepath == str(source)
    assert main_window.document.source_archive["filename"] == source.name
    assert source.read_bytes() == raw


@pytest.mark.parametrize("name,kind", [
    ("Arc.dwg", "ARC"), ("circle.dwg", "CIRCLE"), ("Text.dwg", "TEXT"),
    ("Polyline.dwg", "LWPOLYLINE"), ("Ellipse.dwg", "ELLIPSE"), ("Spline.dwg", "SPLINE"),
])
def test_real_dwg_geometry_types(name, kind):
    document = dxf_io.import_dwg(real_fixture("2018/" + name))
    entities = [e for e in document.entities if e.kind == kind]
    assert entities
    if kind == "ARC":
        # Independent AutoCAD object-property dump in upstream Arc.txt.
        assert entities[0].radius == pytest.approx(8.2931, rel=1e-4)
