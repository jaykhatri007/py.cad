"""DWG dispatch, unavailable-reader errors and the optional ODA export path."""
import pytest
from pycad.document import Document
from pycad.geometry import Point, LineEntity
from pycad import dxf_io, dwg_native


def unavailable_writer(monkeypatch):
    def missing(*args):
        raise dxf_io.DWGSupportError('LibreDWG writer unavailable')
    monkeypatch.setattr(dwg_native, 'tool_path', missing)


def test_export_dwg_without_odafc_raises_clear_error(tmp_path, monkeypatch):
    unavailable_writer(monkeypatch)
    doc = Document()
    doc.add_entity(LineEntity(Point(0, 0), Point(10, 0)))
    with pytest.raises(dxf_io.DWGSupportError, match="ODA File Converter"):
        dxf_io.export_dwg(doc, str(tmp_path / "test.dwg"))


def test_import_dwg_without_reader_raises_clear_error(tmp_path, monkeypatch):
    monkeypatch.setenv('PYCAD_DWG_MODE', 'compatibility')
    from pycad import dwg_support
    def missing():
        raise dxf_io.DWGSupportError("LibreDWG reader is not installed")
    monkeypatch.setattr(dwg_support, "reader_path", missing)
    fake_dwg = tmp_path / "test.dwg"
    fake_dwg.write_bytes(b"not a real dwg")
    with pytest.raises(dxf_io.DWGSupportError, match="LibreDWG"):
        dxf_io.import_dwg(str(fake_dwg))


def test_export_any_dispatches_to_dxf_for_dxf_extension(tmp_path):
    doc = Document()
    doc.add_entity(LineEntity(Point(0, 0), Point(10, 0)))
    path = str(tmp_path / "test.dxf")
    dxf_io.export_any(doc, path)  # should NOT raise DWGSupportError
    doc2 = dxf_io.import_any(path)
    assert len(doc2.entities) == 1


def test_export_any_dispatches_to_dwg_for_dwg_extension(tmp_path, monkeypatch):
    unavailable_writer(monkeypatch)
    doc = Document()
    path = str(tmp_path / "test.dwg")
    with pytest.raises(dxf_io.DWGSupportError):
        dxf_io.export_any(doc, path)


def test_import_any_dispatches_to_dwg_for_dwg_extension(tmp_path):
    fake_dwg = tmp_path / "test.DWG"  # also check case-insensitivity
    fake_dwg.write_bytes(b"not a real dwg")
    with pytest.raises(ValueError, match="DWG file header"):
        dxf_io.import_any(str(fake_dwg))


def test_main_window_shows_friendly_dialog_not_crash(qapp, main_window, monkeypatch):
    """The UI layer should catch DWGSupportError and show a warning dialog,
    not let the exception propagate or silently fail."""
    from PyQt6.QtWidgets import QMessageBox
    unavailable_writer(monkeypatch)
    monkeypatch.setenv('PYCAD_DWG_MODE','compatibility')
    shown = []
    monkeypatch.setattr(QMessageBox, "warning",
                         staticmethod(lambda *a, **k: (shown.append(a[2] if len(a) > 2 else k.get("text")), QMessageBox.StandardButton.Save)[1]))
    main_window._save_to_path("/tmp/_pycad_test_output.dwg")
    assert any("ODA File Converter" in message for message in shown)

    shown.clear()
    from pycad import dwg_support
    def missing():
        raise dxf_io.DWGSupportError("LibreDWG reader is not installed")
    monkeypatch.setattr(dwg_support, "reader_path", missing)
    main_window._open_path("/tmp/_pycad_test_nonexistent.dwg")
    assert shown and "LibreDWG" in shown[0]
