"""Regressions for Windows flushing, external hatch loops and large drawings."""
import json
import os
import time
import ezdxf
import pytest
from PyQt6.QtCore import QThread, QTimer
from PyQt6.QtGui import QImage, QPainter
from pycad.document import Document
from pycad.geometry import Point, LineEntity, BlockDefinition, BlockReferenceEntity, RayEntity
from pycad.native_io import atomic_write, save_project, load_project, document_to_dict
from pycad.dxf_io import import_dxf


def test_atomic_flush_uses_writable_handle(tmp_path, monkeypatch):
    original = os.fsync
    def windows_flush(fd):
        # Windows rejects flushing a read-only handle. A zero-byte write
        # checks the same access contract on Linux without changing content.
        os.write(fd, b'')
        original(fd)
    monkeypatch.setattr(os, 'fsync', windows_flush)
    path = tmp_path/'drawing.txt'
    atomic_write(path, lambda p: open(p, 'w').write('complete'))
    assert path.read_text() == 'complete'


@pytest.mark.parametrize('duplicate', [False, True])
def test_external_hatch_problem_does_not_abort_drawing(qapp, tmp_path, duplicate):
    d = ezdxf.new(); m = d.modelspace()
    m.add_line((30,30), (40,40))
    hatch = m.add_hatch()
    outer = [(0,0),(20,0),(20,20),(0,20)]
    first = [(2,2),(10,2),(10,10),(2,10)]
    second = first if duplicate else [(7,7),(15,7),(15,15),(7,15)]
    for loop in (outer, first, second): hatch.paths.add_polyline_path(loop, is_closed=True)
    source = tmp_path/'source.dxf'; d.saveas(source); before = source.read_bytes()
    result = import_dxf(str(source))
    assert any(e.kind=='LINE' for e in result.entities)
    if duplicate:
        assert len(next(e for e in result.entities if e.kind=='HATCH').holes)==1
    else:
        hatch = next(e for e in result.entities if e.kind=='HATCH')
        assert len(hatch.holes)==2 and hatch.boundary_mode=='evenodd'
        assert not any('outlines' in w for w in result.import_warnings)
    native = tmp_path/'copy.pycad'; save_project(result, native)
    loaded = load_project(native)
    assert len(loaded.entities)==len(result.entities)
    assert source.read_bytes()==before


def test_large_repeated_blocks_open_save_and_keep_all_instances(qapp, tmp_path):
    d = ezdxf.new(); b = d.blocks.new('repeat')
    for n in range(1000): b.add_line((n,0),(n,1))
    for n in range(110): d.modelspace().add_blockref('repeat',(n*2000,0))
    path=tmp_path/'repeated.dxf'; d.saveas(path)
    doc=import_dxf(str(path))
    assert len(doc.entities)==110
    assert sum(len(e.resolved_entities) for e in doc.entities)==110000
    target=tmp_path/'all.pycad'; save_project(doc,target)
    loaded=load_project(target)
    assert sum(len(e.resolved_entities) for e in loaded.entities)==110000


def test_noop_sync_reuses_copies_but_definition_edit_rebuilds(qapp):
    d=Document(); line=LineEntity(Point(0,0),Point(10,0))
    d.blocks['B']=BlockDefinition('B',[line])
    ref=BlockReferenceEntity('B',Point(20,0));d.entities=[ref]
    d.sync_associative(); old=ref.resolved_entities[0]
    d.sync_associative();assert ref.resolved_entities[0] is old
    assert '_display_stamp' not in json.dumps(document_to_dict(d))
    line.p2.x=30;d.sync_associative()
    assert ref.resolved_entities[0].p2.x==50


def test_display_preparation_keeps_gui_events_and_undo_on_gui(qapp, monkeypatch):
    from pycad import import_ui, native_io
    original=native_io._document_from_validated_dict
    observed=[]
    def slow(data):
        observed.append(QThread.currentThread() is qapp.thread())
        time.sleep(.12)
        return original(data)
    monkeypatch.setattr(native_io,'_document_from_validated_dict',slow)
    ticks=[]; timer=QTimer();timer.timeout.connect(lambda:ticks.append(1));timer.start(10)
    doc=import_ui.prepare_display(None,json.dumps(document_to_dict(Document())))
    timer.stop()
    assert observed==[False] and len(ticks)>=3
    assert doc.undo_stack.thread() is qapp.thread()


def test_viewport_culls_offscreen_geometry_but_keeps_ray(main_window, monkeypatch):
    w=main_window;c=w.canvas
    near=LineEntity(Point(0,0),Point(1,1));far=LineEntity(Point(1e6,0),Point(1e6,1))
    ray=RayEntity(Point(1e6,0),Point(0,0))
    w.document.entities=[near,far,ray];w.document.spatial_index.invalidate()
    seen=[];monkeypatch.setattr(c,'_draw_entity',lambda painter,e:seen.append(e))
    image=QImage(900,600,QImage.Format.Format_ARGB32);p=QPainter(image)
    c._draw_entities(p);p.end()
    assert near in seen and ray in seen and far not in seen


def test_display_limit_still_bounds_expansion(qapp):
    from pycad.block_budget import check_expansion
    from pycad.validation import MAX_DISPLAY_ENTITIES
    block=BlockDefinition('B',[LineEntity(Point(0,0),Point(1,1)) for _ in range(1000)])
    refs=[BlockReferenceEntity('B',Point(n,0)) for n in range(600)]
    with pytest.raises(ValueError):check_expansion({'B':block},refs,limit=500000)
    check_expansion({'B':block},refs)
    assert MAX_DISPLAY_ENTITIES==float('inf')
