"""Reference migration, isolated profiles and desktop-entry interoperability."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

import pytest
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QDialog, QFileDialog, QPushButton, QTableWidget
from pycad.document import Document
from pycad.geometry import Point, CircleEntity, BlockDefinition, BlockReferenceEntity
from pycad.native_io import save_project, load_project, document_to_dict
from pycad import dxf_io, ribbon_actions
from pycad.xref import reference_path, portable_path
from scripts import linux_launcher as launcher


def reference_drawing(tmp_path):
    folder = tmp_path / 'references'
    folder.mkdir()
    source = Document()
    source.entities = [CircleEntity(Point(0, 0), 500)]
    path = folder / 'Plan A.dxf'
    dxf_io.export_dxf(source, str(path))
    drawing = Document()
    drawing.filepath = str(tmp_path / 'drawing.pycad')
    drawing.blocks['Ref'] = BlockDefinition('Ref', [CircleEntity(Point(0, 0), 1)],
                                          r'C:\Old Windows\Plan A.dxf', source_scale=.001)
    drawing.entities = [BlockReferenceEntity('Ref', Point(3, 4))]
    drawing.sync_associative()
    return drawing, path


def test_relative_windows_separators_resolve_and_transmit(qapp, tmp_path):
    drawing, path = reference_drawing(tmp_path)
    drawing.blocks['Ref'].source_filepath = r'references\Plan A.dxf'
    assert reference_path(drawing, drawing.blocks['Ref'].source_filepath) == path
    drawing.reload_xref('Ref')
    assert drawing.blocks['Ref'].entities[0].radius == pytest.approx(.5)
    archive = tmp_path / 'portable.zip'
    ribbon_actions.transmittal(drawing, archive)
    with zipfile.ZipFile(archive) as z:
        z.extractall(tmp_path / 'destination')
    restored = load_project(tmp_path / 'destination/drawing.pycad')
    restored.reload_xref('Ref')
    assert restored.blocks['Ref'].entities[0].radius == pytest.approx(.5)


@pytest.mark.skipif(os.name == 'nt', reason='Windows drive paths are native on Windows')
def test_windows_absolute_path_requires_explicit_relink(qapp, tmp_path):
    drawing, _ = reference_drawing(tmp_path)
    with pytest.raises(ValueError, match='Relink selected'):
        drawing.reload_xref('Ref')
    # Never silently choose a similarly named file from another directory.
    assert drawing.blocks['Ref'].entities[0].radius == 1


def test_relink_preserves_scale_has_single_undo_and_persists(qapp, tmp_path):
    drawing, path = reference_drawing(tmp_path)
    before = document_to_dict(drawing)
    drawing.reload_xref('Ref', source=path)
    assert drawing.blocks['Ref'].source_filepath == 'references/Plan A.dxf'
    assert drawing.blocks['Ref'].source_scale == .001
    assert drawing.blocks['Ref'].entities[0].radius == pytest.approx(.5)
    assert drawing.undo_stack.count() == 1
    after = document_to_dict(drawing)
    drawing.undo_stack.undo()
    assert document_to_dict(drawing) == before
    drawing.undo_stack.redo()
    assert document_to_dict(drawing) == after
    save_project(drawing, drawing.filepath)
    loaded = load_project(drawing.filepath)
    loaded.reload_xref('Ref')
    assert loaded.blocks['Ref'].entities[0].radius == pytest.approx(.5)


def test_invalid_relink_keeps_path_cached_geometry_and_history(qapp, tmp_path):
    drawing, _ = reference_drawing(tmp_path)
    bad = tmp_path / 'invalid.dxf'
    bad.write_text('not a drawing')
    before = document_to_dict(drawing)
    with pytest.raises(Exception):
        drawing.reload_xref('Ref', source=bad)
    assert document_to_dict(drawing) == before
    assert drawing.undo_stack.count() == 0


def test_reference_manager_relink_button(main_window, tmp_path, monkeypatch):
    drawing, path = reference_drawing(tmp_path)
    main_window.document.blocks = drawing.blocks
    main_window.document.entities = drawing.entities
    main_window.document.filepath = drawing.filepath
    monkeypatch.setattr(QFileDialog, 'getOpenFileName', lambda *a, **k: (str(path), ''))
    def choose():
        dialog = main_window.findChild(QDialog, 'xref_manager')
        table = dialog.findChild(QTableWidget)
        table.setCurrentCell(0, 0)
        dialog.findChild(QPushButton, 'xref_relink').click()
        assert table.item(0, 1).text() == 'references/Plan A.dxf'
        dialog.accept()
    QTimer.singleShot(0, choose)
    ribbon_actions.xrefs(main_window)
    assert main_window.document.blocks['Ref'].entities[0].radius == pytest.approx(.5)


def test_unsaved_reference_uses_absolute_path(qapp, tmp_path):
    drawing = Document()
    assert portable_path(drawing, tmp_path / 'test.dxf') == (tmp_path / 'test.dxf').as_posix()


def test_profile_override_is_shared_by_settings_recovery_and_logs(tmp_path):
    env = dict(os.environ, PYCAD_DATA_DIR=str(tmp_path))
    result = subprocess.run([sys.executable, '-c',
        'import json; from pycad import applog,appsettings; '
        's=appsettings.get_settings();s.setValue("test/value",12);s.sync();'
        'print(json.dumps([applog.APP_DIR,appsettings.RECOVERY_PATH,s.fileName()]))'],
        env=env, capture_output=True, text=True, check=True)
    root, recovery, settings = json.loads(result.stdout)
    assert Path(root) == tmp_path
    assert Path(recovery).parent == tmp_path
    assert Path(settings) == tmp_path / 'settings.ini'


def test_desktop_entry_handles_special_path_and_respects_unrelated_file(tmp_path, monkeypatch):
    root = tmp_path / 'CAD (Jay) 100% $ quote" back\\tick`'
    root.mkdir()
    monkeypatch.setenv('XDG_DATA_HOME', str(tmp_path / 'applications data'))
    path = launcher.install_desktop(root)
    assert 'Terminal=true' in path.read_text()
    assert '100%%' in path.read_text()
    if shutil.which('desktop-file-validate'):
        subprocess.run(['desktop-file-validate', str(path)], check=True, capture_output=True)
    path.write_text('[Desktop Entry]\nName=Another app\n')
    with pytest.raises(RuntimeError, match='unrelated'):
        launcher.install_desktop(root)


def test_backend_selection_preserves_explicit_choice(monkeypatch):
    from argparse import Namespace
    args = Namespace(xcb=False, wayland=False, software_rendering=False)
    monkeypatch.setenv('DISPLAY', ':123')
    monkeypatch.delenv('QT_QPA_PLATFORM', raising=False)
    assert launcher.display_environment(args)['QT_QPA_PLATFORM'] == 'xcb'
    monkeypatch.setenv('QT_QPA_PLATFORM', 'offscreen')
    assert launcher.display_environment(args)['QT_QPA_PLATFORM'] == 'offscreen'
    args.wayland = True
    args.software_rendering = True
    env = launcher.display_environment(args)
    assert env['QT_QPA_PLATFORM'] == 'wayland' and env['LIBGL_ALWAYS_SOFTWARE'] == '1'


@pytest.mark.skipif(sys.platform != 'linux', reason='Linux shell launcher')
def test_no_display_has_actionable_error_without_setup(tmp_path):
    root = Path(__file__).resolve().parents[1]
    env = dict(os.environ, PYCAD_PYTHON=sys.executable, PYCAD_DATA_DIR=str(tmp_path))
    for key in ('DISPLAY', 'WAYLAND_DISPLAY', 'QT_QPA_PLATFORM'):
        env.pop(key, None)
    result = subprocess.run(['bash', str(root / 'start.sh')], env=env,
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 1
    assert 'No graphical display' in result.stderr and '--setup-only' in result.stderr
    assert not list(tmp_path.iterdir())
