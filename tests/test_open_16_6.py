"""Real reader-process responsiveness, cancellation and bounded drawing work."""

import hashlib
import sys
from pathlib import Path

import ezdxf
import pytest
from PyQt6.QtCore import QProcess, QTimer, Qt
from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtWidgets import QApplication, QProgressDialog, QPushButton
from PyQt6.QtTest import QTest

from pycad import dxf_io, native_io, precision
from pycad.document import Document
from pycad.geometry import Point, LineEntity, BlockDefinition, BlockReferenceEntity, HatchEntity


def test_real_dxf_open_keeps_events_and_source_and_undo(main_window, tmp_path):
    source = tmp_path / 'large drawing ü.dxf'
    raw = ezdxf.new()
    for i in range(12000):
        raw.modelspace().add_line((i % 200, i // 200), (i % 200 + .5, i // 200))
    raw.saveas(source)
    before = hashlib.sha256(source.read_bytes()).digest()
    ticks = []
    timer = QTimer()
    timer.setInterval(10)
    timer.timeout.connect(lambda: ticks.append(1))
    timer.start()
    try:
        assert main_window._open_path(str(source))
    finally:
        timer.stop()
    doc = main_window.document
    assert len(ticks) > 5
    assert len(doc.entities) == 12000
    assert doc.filepath == str(source) and doc.source_filepath == str(source)
    assert doc.source_archive and not doc.dirty
    assert hashlib.sha256(source.read_bytes()).digest() == before
    assert doc.undo_stack.thread() is QApplication.instance().thread()
    from pycad.document import AddEntityCommand
    doc.undo_stack.push(AddEntityCommand(doc, LineEntity(Point(0, 0), Point(2, 2))))
    assert doc.dirty and len(doc.entities) == 12001
    doc.undo_stack.undo()
    assert len(doc.entities) == 12000 and not doc.dirty


def sleeping_reader(monkeypatch):
    original = QProcess.start
    children = []

    def start(process, program, arguments):
        children.append(process)
        return original(process, sys.executable, ['-c', 'import time; time.sleep(60)'])

    monkeypatch.setattr(QProcess, 'start', start)
    return children


def test_cancel_kills_reader_and_preserves_active_drawing(main_window, monkeypatch):
    children = sleeping_reader(monkeypatch)
    doc = main_window.document
    doc.add_entity(LineEntity(Point(0, 0), Point(1, 0)))

    def cancel():
        dialogs = [w for w in QApplication.topLevelWidgets() if isinstance(w, QProgressDialog)]
        assert dialogs
        QTest.mouseClick(dialogs[0].findChild(QPushButton), Qt.MouseButton.LeftButton)

    QTimer.singleShot(200, cancel)
    assert not main_window._open_path('cancelled.dxf')
    assert main_window.document is doc and len(main_window.drawing_tabs.sessions) == 1
    assert len(doc.entities) == 1 and doc.dirty
    assert children and all(p.state() == QProcess.ProcessState.NotRunning for p in children)


def test_reader_timeout_terminates_child(main_window, monkeypatch):
    from pycad.import_ui import load_dxf
    children = sleeping_reader(monkeypatch)
    with pytest.raises(ValueError, match='timed out'):
        load_dxf(main_window, 'slow.dxf', timeout_ms=100)
    assert children and children[0].state() == QProcess.ProcessState.NotRunning


def test_malformed_dxf_reports_error_without_document_replacement(main_window, tmp_path):
    from pycad.import_ui import load_dxf
    p = tmp_path / 'broken.dxf'
    p.write_text('not a DXF')
    before = main_window.document
    with pytest.raises(ValueError):
        load_dxf(main_window, str(p))
    assert main_window.document is before


@pytest.mark.parametrize('cyclic', [True])
def test_reference_graph_checked_before_any_display_cloning(tmp_path, monkeypatch, cyclic):
    raw = ezdxf.new()
    leaf = raw.blocks.new('B0')
    if cyclic:
        leaf.add_blockref('B1', (0, 0))
        raw.blocks.new('B1').add_blockref('B0', (0, 0))
        name = 'B1'
    else:
        # A tiny DXF with empty leaves used to allocate an exponential number
        # of INSERT containers while bypassing leaf-only expansion counts.
        for i in range(1, 28):
            b = raw.blocks.new('B'+str(i))
            b.add_blockref('B'+str(i-1), (0, 0))
            b.add_blockref('B'+str(i-1), (1, 0))
        name = 'B27'
    raw.modelspace().add_blockref(name, (0, 0))
    path = tmp_path / 'branching.dxf'
    raw.saveas(path)
    original = path.read_bytes()
    monkeypatch.setattr(BlockReferenceEntity, 'rebuild', lambda *args: pytest.fail('allocated before checking graph'))
    with pytest.raises(ValueError, match='[Cc]yclic|budget'):
        dxf_io.import_dxf(str(path))
    assert path.read_bytes() == original


def test_native_shared_definitions_rebuilt_once(qapp, monkeypatch):
    doc = Document()
    doc.blocks['B0'] = BlockDefinition('B0', [LineEntity(Point(0, 0), Point(1, 0))])
    for i in range(1, 7):
        doc.blocks['B'+str(i)] = BlockDefinition('B'+str(i), [
            BlockReferenceEntity('B'+str(i-1), Point(0, 0)),
            BlockReferenceEntity('B'+str(i-1), Point(0, 0))])
    doc.entities = [BlockReferenceEntity('B6', Point(0, 0))]
    payload = native_io.document_to_dict(doc)
    calls = []
    rebuild = BlockReferenceEntity.rebuild
    def count(self, block):
        calls.append(self.block_name)
        return rebuild(self, block)
    monkeypatch.setattr(BlockReferenceEntity, 'rebuild', count)
    loaded = native_io.document_from_dict(payload)
    assert len(calls) == 13
    assert loaded.entities[0].bbox() == (0, 0, 1, 0)


def test_dense_hatch_screen_does_not_scan_world_rows(main_window, monkeypatch):
    from pycad import geom_ops
    hatch = HatchEntity([Point(0,0),Point(1e8,0),Point(1e8,1e8),Point(0,1e8)], spacing=1e-6)
    old = native_io.entity_to_dict(hatch)
    canvas = main_window.canvas
    canvas.zoom = .01
    monkeypatch.setattr(geom_ops, 'compute_hatch_lines', lambda *args: pytest.fail('unbounded screen scan'))
    image = QImage(900, 600, QImage.Format.Format_ARGB32)
    image.fill(0)
    painter = QPainter(image)
    try:
        precision.draw_hatch(canvas, painter, hatch)
    finally:
        painter.end()
    assert native_io.entity_to_dict(hatch) == old


def test_screen_hatch_rows_are_viewport_bounded_and_keep_grid_phase(main_window):
    c = main_window.canvas
    c.zoom = 1
    h = HatchEntity([Point(-1e9,-1e9),Point(1e9,-1e9),Point(1e9,1e9),Point(-1e9,1e9)], angle=0, spacing=10)
    rows = list(precision.display_hatch_lines(c, h))
    assert 0 < len(rows) < 2048
    assert all((a.y-(-1e9+5))/10 == pytest.approx(round((a.y-(-1e9+5))/10)) for a,b in rows)


def test_disabled_intersections_do_no_pair_work(main_window, monkeypatch):
    from pycad.canvas import Snap
    canvas = main_window.canvas
    canvas.snap_modes = {Snap.ENDPOINT}
    main_window.document.entities = [LineEntity(Point(0, 0), Point(10, 0))]
    main_window.document.spatial_index.invalidate()
    monkeypatch.setattr(canvas, '_intersection_points', lambda *a: pytest.fail('disabled intersection search'))
    canvas.find_snap_point(canvas.world_to_screen(0, 0))


def test_dense_intersections_have_bounded_candidate_work(main_window, monkeypatch):
    from pycad.canvas import Snap
    canvas = main_window.canvas
    canvas.snap_modes = {Snap.INTERSECTION}
    main_window.document.entities = [LineEntity(Point(-10, i/1000), Point(10, i/1000)) for i in range(500)]
    main_window.document.spatial_index.invalidate()
    work = []
    monkeypatch.setattr(canvas, '_intersection_points', lambda entities: work.append(len(entities)) or [])
    canvas.find_snap_point(canvas.world_to_screen(0, 0))
    assert work and work[0] <= 64
