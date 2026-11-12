"""Real image/PDF attachment, calibration, persistence, and rendered output."""

import copy
import hashlib
import base64
import struct
import pytest
from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QImage, QPainter, QColor, QPdfWriter
from PyQt6.QtWidgets import QDialog, QCheckBox, QDoubleSpinBox, QPushButton, QFileDialog
from pycad.document import Document
from pycad.geometry import Point, LineEntity
from pycad.underlays import (
    read_underlay,
    validate_underlays,
    UnderlaysCommand,
    calibrate,
    corners,
    draw_underlays,
    manage_dialog,
    attach_dialog,
)
from pycad.native_io import (
    document_to_dict,
    document_from_dict,
    save_project,
    load_project,
)
from pycad.unit_conversion import convert_units


def source_image(tmp_path):
    path = tmp_path / "reference.png"
    image = QImage(100, 60, QImage.Format.Format_RGB32)
    image.fill(QColor("#fafafa"))
    p = QPainter(image)
    p.fillRect(0, 0, 50, 30, QColor("#ff0000"))
    p.fillRect(50, 30, 50, 30, QColor("#0000ff"))
    p.end()
    assert image.save(str(path))
    return path


def test_image_embedded_undo_save_reopen_without_source(qapp, tmp_path):
    path = source_image(tmp_path)
    r = read_underlay(path)
    assert r["pixels"] == [100, 60]
    d = Document()
    d.undo_stack.push(UnderlaysCommand(d, [r]))
    assert d.dirty
    saved = tmp_path / "drawing.pycad"
    save_project(d, saved)
    path.unlink()
    result = load_project(saved)
    assert result.underlays == [r]
    d.undo_stack.undo()
    assert not d.underlays
    d.undo_stack.redo()
    assert d.underlays == [r]


def test_calibration_scales_about_first_point_preserves_rotation_and_other_geometry(
    qapp, tmp_path
):
    r = read_underlay(source_image(tmp_path))
    r["origin"] = [10, 20]
    r["rotation"] = 90
    d = Document()
    d.underlays = [r]
    line = LineEntity(Point(0, 0), Point(10, 10))
    d.entities = [line]
    old = copy.deepcopy(r)
    assert calibrate(d, r["id"], (10, 20), (10, 70), 100) == 2
    new = d.underlays[0]
    assert new["origin"] == [10, 20] and new["width"] == 200 and new["rotation"] == 90
    assert corners(new)[1] == pytest.approx((10, 220))
    assert line.p2.as_tuple() == (10, 10)
    d.undo_stack.undo()
    assert d.underlays == [old]
    d.underlays[0]["locked"] = True
    with pytest.raises(ValueError, match="Unlock"):
        calibrate(d, r["id"], (10, 20), (10, 70), 100)


def test_underlay_conversion_retains_physical_size(qapp, tmp_path):
    d = Document()
    r = read_underlay(source_image(tmp_path))
    r["origin"] = [1000, 2000]
    r["width"] = 1000
    d.underlays = [r]
    before = document_to_dict(d)
    convert_units(d, "m")
    assert d.underlays[0]["origin"] == [1, 2] and d.underlays[0]["width"] == 1
    d.undo_stack.undo()
    assert document_to_dict(d) == before


@pytest.mark.parametrize(
    "change",
    [
        lambda r: r.update(width=0),
        lambda r: r.update(pixels=[99999, 99999]),
        lambda r: r.update(sha256="bad"),
        lambda r: r.update(opacity=2),
        lambda r: r.update(locked="yes"),
        lambda r: r.update(png="not base64"),
    ],
)
def test_bad_underlay_records_rejected(qapp, tmp_path, change):
    r = read_underlay(source_image(tmp_path))
    change(r)
    with pytest.raises(ValueError):
        validate_underlays([r])


def test_hostile_png_header_rejected_before_decode(qapp, tmp_path):
    r = read_underlay(source_image(tmp_path))
    raw = bytearray(base64.b64decode(r["png"]))
    raw[16:24] = struct.pack(">II", 100000, 100000)
    r["png"] = base64.b64encode(raw).decode()
    r["sha256"] = hashlib.sha256(raw).hexdigest()
    with pytest.raises(ValueError, match="dimensions"):
        validate_underlays([r])


def test_underlay_draw_orientation_rotation_visibility_and_plot(qapp, tmp_path):
    from pycad.canvas import CadCanvas
    from PyQt6.QtCore import QPointF

    d = Document()
    r = read_underlay(source_image(tmp_path))
    r["opacity"] = 1
    d.underlays = [r]
    canvas = CadCanvas(d)
    canvas.world_to_screen = lambda x, y: QPointF(x, 100 - y)
    image = QImage(200, 200, QImage.Format.Format_RGB32)
    image.fill(QColor("#00ff00"))
    painter = QPainter(image)
    draw_underlays(canvas, painter)
    painter.end()
    assert image.pixelColor(10, 50).name() == "#ff0000"
    assert image.pixelColor(70, 80).name() == "#0000ff"
    r["plot"] = False
    canvas._plot_mm = 1
    image.fill(QColor("#00ff00"))
    painter = QPainter(image)
    draw_underlays(canvas, painter)
    painter.end()
    assert image.pixelColor(10, 50).name() == "#00ff00"
    del canvas._plot_mm
    r["visible"] = False
    image.fill(QColor("#00ff00"))
    painter = QPainter(image)
    draw_underlays(canvas, painter)
    painter.end()
    assert image.pixelColor(10, 50).name() == "#00ff00"
    canvas.deleteLater()


def test_underlay_only_model_and_layout_plot_have_raster(qapp, tmp_path):
    from pycad.plotting import export_pdf
    import fitz

    d = Document()
    r = read_underlay(source_image(tmp_path))
    d.underlays = [r]
    model = tmp_path / "model.pdf"
    export_pdf(d, model)
    with fitz.open(model) as pdf:
        assert pdf[0].get_images()
    layout = d.create_layout("Reference sheet")
    assert layout.viewports
    paper = tmp_path / "paper.pdf"
    export_pdf(d, paper, layout.name)
    with fitz.open(paper) as pdf:
        assert pdf[0].get_images()
    r["plot"] = False
    with pytest.raises(ValueError, match="visible"):
        export_pdf(d, tmp_path / "empty.pdf")


def test_pdf_page_selection_physical_size_and_invalid_source(qapp, tmp_path):
    path = tmp_path / "pages.pdf"
    writer = QPdfWriter(str(path))
    writer.setResolution(72)
    painter = QPainter(writer)
    painter.fillRect(0, 0, 200, 200, QColor("#ff0000"))
    writer.newPage()
    painter.fillRect(0, 0, 200, 200, QColor("#0000ff"))
    painter.end()
    page1 = read_underlay(path, "mm", 1)
    page2 = read_underlay(path, "mm", 2)
    assert page1["kind"] == "pdf" and page2["page"] == 2
    assert page1["png"] != page2["png"] and page1["width"] == pytest.approx(
        210, abs=0.2
    )
    assert max(page1["pixels"]) <= 4096
    with pytest.raises(ValueError, match="page"):
        read_underlay(path, "mm", 3)
    bad = tmp_path / "bad.pdf"
    bad.write_text("not a PDF")
    with pytest.raises(ValueError):
        read_underlay(bad)


def test_underlay_manager_apply_lock_and_cancel(main_window, tmp_path):
    w = main_window
    w.document.underlays = [read_underlay(source_image(tmp_path))]

    def edit():
        dialog = w.findChild(QDialog, "underlay_manager")
        dialog.findChild(QDoubleSpinBox, "underlay_width").setValue(250)
        dialog.findChild(QCheckBox, "underlay_locked").setChecked(True)
        next(b for b in dialog.findChildren(QPushButton) if b.text() == "Apply").click()
        assert w.document.underlays[0]["width"] == 250
        assert w.document.underlays[0]["locked"]
        assert not dialog.findChild(QDoubleSpinBox, "underlay_width").isEnabled()
        dialog.accept()

    QTimer.singleShot(0, edit)
    manage_dialog(w)
    before = document_to_dict(w.document)

    def cancel():
        dialog = w.findChild(QDialog, "underlay_manager")
        dialog.findChild(QDoubleSpinBox, "underlay_opacity").setValue(10)
        dialog.reject()

    QTimer.singleShot(0, cancel)
    manage_dialog(w)
    assert document_to_dict(w.document) == before
    w.undo()
    assert (
        w.document.underlays[0]["width"] == 100
        and not w.document.underlays[0]["locked"]
    )


def test_calibrate_tool_uses_points_and_known_length(main_window, tmp_path):
    w = main_window
    r = read_underlay(source_image(tmp_path))
    w.document.underlays = [r]
    w.set_tool("UNDERLAYCALIBRATE")
    w._on_world_clicked(0, 0, "", 1)
    w._on_world_clicked(50, 0, "", 1)
    w.command_line.setText("1000")
    w._on_command_entered()
    assert w.document.underlays[0]["width"] == 2000 and w.current_tool.name == "SELECT"
    w.undo()
    assert w.document.underlays[0]["width"] == 100


def test_attach_ui_actual_image_and_explicit_export_warning(
    main_window, tmp_path, monkeypatch
):
    from pycad import underlays
    from pycad.dxf_io import export_warnings

    w = main_window
    path = source_image(tmp_path)
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", lambda *a, **kw: (str(path), "Images")
    )
    monkeypatch.setattr(underlays, "manage_dialog", lambda *a: None)
    attach_dialog(w, "image")
    assert len(w.document.underlays) == 1 and w.document.dirty
    assert any("underlays are omitted" in text for text in export_warnings(w.document))
    assert (
        document_from_dict(document_to_dict(w.document)).underlays
        == w.document.underlays
    )
