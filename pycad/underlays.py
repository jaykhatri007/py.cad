"""Embedded raster underlays. PDF pages are rendered references, not CAD vectors."""

import base64
import copy
import hashlib
import math
import struct
import uuid
from functools import lru_cache
from pathlib import Path
from PyQt6.QtCore import QBuffer, QByteArray, QIODevice, QSize, Qt, QPointF
from PyQt6.QtGui import QImage, QImageReader, QTransform, QUndoCommand

MAX_IMAGE_BYTES = 8 * 1024 * 1024
MAX_SIDE = 4096
MAX_PIXELS = 16_777_216
FIELDS = {
    "id",
    "name",
    "kind",
    "page",
    "png",
    "sha256",
    "pixels",
    "origin",
    "width",
    "rotation",
    "opacity",
    "visible",
    "plot",
    "locked",
}


@lru_cache(maxsize=20)
def _validate_png(encoded, digest, width, height):
    if not isinstance(encoded, str) or len(encoded) > 4 * ((MAX_IMAGE_BYTES + 2) // 3):
        raise ValueError("An embedded underlay may contain at most 8 MiB of PNG data")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError) as error:
        raise ValueError("Invalid underlay image encoding") from error
    if (
        len(raw) > MAX_IMAGE_BYTES
        or len(raw) < 33
        or raw[:8] != b"\x89PNG\r\n\x1a\n"
        or raw[12:16] != b"IHDR"
    ):
        raise ValueError("Invalid underlay PNG")
    if (
        struct.unpack(">II", raw[16:24]) != (width, height)
        or hashlib.sha256(raw).hexdigest() != digest
    ):
        raise ValueError("Underlay image dimensions/checksum do not match")
    image = QImage.fromData(raw, "PNG")
    if image.isNull() or (image.width(), image.height()) != (width, height):
        raise ValueError("Unable to decode underlay image")


def validate_underlays(records):
    from .validation import finite, name

    if not isinstance(records, list) or len(records) > 20:
        raise ValueError("Maximum 20 embedded underlays per drawing")
    ids, total_pixels, total_bytes = set(), 0, 0
    for r in records:
        if not isinstance(r, dict) or set(r) != FIELDS:
            raise ValueError("Invalid underlay fields")
        name(r["id"], "Underlay ID")
        name(r["name"], "Underlay name")
        if r["id"] in ids:
            raise ValueError("Duplicate underlay ID")
        ids.add(r["id"])
        if (
            r["kind"] not in ("image", "pdf")
            or type(r["page"]) is not int
            or r["page"] < 1
        ):
            raise ValueError("Invalid underlay source/page")
        pixels = r["pixels"]
        if (
            not isinstance(pixels, list)
            or len(pixels) != 2
            or any(type(v) is not int or not 1 <= v <= MAX_SIDE for v in pixels)
        ):
            raise ValueError("Underlay raster must be 1–4096 pixels on each side")
        total_pixels += pixels[0] * pixels[1]
        if total_pixels > 32_000_000:
            raise ValueError("Combined underlay rasters exceed 32 million pixels")
        if not isinstance(r["png"], str) or not isinstance(r["sha256"], str):
            raise ValueError("Invalid embedded image data")
        total_bytes += len(r["png"])
        if total_bytes > 44_739_244:
            raise ValueError("Combined embedded underlays exceed 32 MiB")
        _validate_png(r["png"], r["sha256"], *pixels)
        if not isinstance(r["origin"], list) or len(r["origin"]) != 2:
            raise ValueError("Invalid underlay insertion point")
        for v in r["origin"]:
            finite(v, "Underlay coordinate")
        finite(r["width"], "Underlay width", True)
        finite(r["rotation"], "Underlay rotation")
        finite(r["opacity"], "Underlay opacity")
        if not 0 <= r["opacity"] <= 1:
            raise ValueError("Opacity must be 0–1")
        for key in ("visible", "plot", "locked"):
            if type(r[key]) is not bool:
                raise ValueError("Underlay flags must be boolean")


def _open_pdf(path):
    from PyQt6.QtPdf import QPdfDocument

    pdf = QPdfDocument(None)
    error = pdf.load(str(path))
    if error != QPdfDocument.Error.None_ or pdf.pageCount() < 1:
        pdf.close()
        raise ValueError("Unable to read PDF. Use a valid, unencrypted PDF file.")
    return pdf


def read_underlay(path, units="mm", page=1):
    from .units import UNIT_MM

    path = Path(path)
    if path.stat().st_size > 50 * 1024 * 1024:
        raise ValueError("Source file exceeds the 50 MiB import limit")
    kind = "pdf" if path.suffix.lower() == ".pdf" else "image"
    if kind == "pdf":
        pdf = _open_pdf(path)
        try:
            if not 1 <= page <= pdf.pageCount():
                raise ValueError("PDF page is out of range")
            pts = pdf.pagePointSize(page - 1)
            if pts.width() <= 0 or pts.height() <= 0:
                raise ValueError("Invalid PDF page size")
            factor = min(150 / 72, MAX_SIDE / max(pts.width(), pts.height()))
            size = QSize(
                max(1, round(pts.width() * factor)),
                max(1, round(pts.height() * factor)),
            )
            image = pdf.render(page - 1, size)
            width = pts.width() * 25.4 / 72 / UNIT_MM.get(units, 1)
        finally:
            pdf.close()
    else:
        reader = QImageReader(str(path))
        reader.setAutoTransform(True)
        size = reader.size()
        if not size.isValid() or size.width() * size.height() > 100_000_000:
            raise ValueError(
                "Unsupported image or source image exceeds 100 million pixels"
            )
        if max(size.width(), size.height()) > MAX_SIDE:
            size.scale(MAX_SIDE, MAX_SIDE, Qt.AspectRatioMode.KeepAspectRatio)
            reader.setScaledSize(size)
        image = reader.read()
        width = 100.0
    if image.isNull():
        raise ValueError("Unable to decode the selected image/page")
    if max(image.width(), image.height()) > MAX_SIDE:
        image = image.scaled(
            MAX_SIDE,
            MAX_SIDE,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(buffer, "PNG"):
        raise ValueError("Unable to embed reference image")
    raw = bytes(data)
    result = dict(
        id=uuid.uuid4().hex,
        name=path.name,
        kind=kind,
        page=page,
        png=base64.b64encode(raw).decode("ascii"),
        sha256=hashlib.sha256(raw).hexdigest(),
        pixels=[image.width(), image.height()],
        origin=[0.0, 0.0],
        width=width,
        rotation=0.0,
        opacity=0.65,
        visible=True,
        plot=True,
        locked=False,
    )
    validate_underlays([result])
    return result


@lru_cache(maxsize=8)
def _image(encoded):
    return QImage.fromData(base64.b64decode(encoded), "PNG")


def corners(record):
    x, y = record["origin"]
    w = record["width"]
    h = w * record["pixels"][1] / record["pixels"][0]
    a = math.radians(record["rotation"])
    c, s = math.cos(a), math.sin(a)
    return [
        (x + c * xx - s * yy, y + s * xx + c * yy)
        for xx, yy in ((0, 0), (w, 0), (w, h), (0, h))
    ]


def bounds(doc, plot=False):
    result = []
    for r in doc.underlays:
        if doc.extensions.get("office_reviews",{}).get(r["id"],{}).get("space","Model")!="Model":continue
        if not r["visible"] or plot and not r["plot"]:
            continue
        p = corners(r)
        result.append(
            (
                min(x for x, y in p),
                min(y for x, y in p),
                max(x for x, y in p),
                max(y for x, y in p),
            )
        )
    return result


def draw_underlays(canvas, painter, review_space=None):
    reviews=canvas.document.extensions.get("office_reviews",{})
    for r in canvas.document.underlays:
        review=reviews.get(r["id"])
        if review_space is None and review and review["space"]!="Model":continue
        if review_space is not None and (not review or review["space"]!=review_space):continue
        if not r["visible"] or hasattr(canvas, "_plot_mm") and not r["plot"]:
            continue
        pts = corners(r)
        # QImage origin is top-left; drawing origin is bottom-left.
        a, b, c = [canvas.world_to_screen(*p) for p in (pts[3], pts[2], pts[0])]
        w, h = r["pixels"]
        transform = QTransform(
            (b.x() - a.x()) / w,
            (b.y() - a.y()) / w,
            (c.x() - a.x()) / h,
            (c.y() - a.y()) / h,
            a.x(),
            a.y(),
        )
        painter.save()
        painter.setOpacity(r["opacity"])
        painter.setRenderHint(painter.RenderHint.SmoothPixmapTransform)
        painter.setWorldTransform(transform, True)
        painter.drawImage(QPointF(0, 0), _image(r["png"]))
        painter.restore()
        if review and not hasattr(canvas,"_plot_mm") and (review_space or canvas.document.current_space) == review["space"]:
            from PyQt6.QtCore import QRectF
            from PyQt6.QtGui import QColor, QPen, QFont
            painter.save()
            for i,n in enumerate(review["notes"],1):
                center=transform.map(QPointF(n["x"]*w,(1-n["y"])*h))
                radius=max(3.0,abs(canvas.zoom)*r["width"]*.012)
                painter.setPen(QPen(QColor("#182632")))
                painter.setBrush(QColor("#53c6a5" if n["resolved"] else "#ffb34d"))
                painter.drawEllipse(center,radius,radius)
                font=QFont(painter.font());font.setPixelSize(max(4,min(200,round(radius*1.05))));painter.setFont(font)
                painter.drawText(QRectF(center.x()-radius,center.y()-radius,2*radius,2*radius),Qt.AlignmentFlag.AlignCenter,str(i))
            painter.restore()


class UnderlaysCommand(QUndoCommand):
    def __init__(self, doc, after, text="Edit underlays"):
        super().__init__(text)
        validate_underlays(after)
        self.doc = doc
        self.before, self.after = copy.deepcopy(doc.underlays), copy.deepcopy(after)

    def redo(self):
        self.doc.underlays = copy.deepcopy(self.after)

    def undo(self):
        self.doc.underlays = copy.deepcopy(self.before)


def calibrate(doc, uid, first, second, known):
    distance = math.hypot(second[0] - first[0], second[1] - first[1])
    if not math.isfinite(known) or known <= 0 or distance <= 1e-12:
        raise ValueError(
            "Pick two different reference points and enter a positive known distance"
        )
    after = copy.deepcopy(doc.underlays)
    r = next((r for r in after if r["id"] == uid), None)
    if r is None:
        raise ValueError("Underlay no longer exists")
    if r["locked"]:
        raise ValueError("Unlock this underlay before calibrating")
    factor = known / distance
    r["origin"] = [a + (v - a) * factor for a, v in zip(first, r["origin"])]
    r["width"] *= factor
    doc.undo_stack.push(UnderlaysCommand(doc, after, "Calibrate underlay"))
    return factor


def attach_dialog(window, kind):
    from PyQt6.QtWidgets import QFileDialog, QInputDialog, QMessageBox

    window.cancel_command()
    if window.document.current_space != "Model":
        raise ValueError("Switch to Model space before attaching an underlay")
    filters = (
        "PDF (*.pdf)"
        if kind == "pdf"
        else "Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.webp)"
    )
    path, _ = QFileDialog.getOpenFileName(
        window, "Attach " + kind + " underlay", "", filters
    )
    if not path:
        return
    try:
        page = 1
        if kind == "pdf":
            if Path(path).stat().st_size > 50 * 1024 * 1024:
                raise ValueError("PDF exceeds 50 MiB")
            pdf = _open_pdf(path)
            count = pdf.pageCount()
            pdf.close()
            if count > 1:
                page, ok = QInputDialog.getInt(
                    window, "PDF page", "Choose page to attach:", 1, 1, count
                )
                if not ok:
                    return
        record = read_underlay(path, window.document.units, page)
        window.document.undo_stack.push(
            UnderlaysCommand(
                window.document,
                [*window.document.underlays, record],
                "Attach " + kind + " underlay",
            )
        )
        window.show_drafting()
        window.canvas.zoom_extents()
        window.command_history.appendPlainText(
            "Attached embedded raster reference: "
            + record["name"]
            + ". UNDERLAYS manages placement, opacity, locking and calibration."
        )
        manage_dialog(window, record["id"])
    except (ValueError, OSError, ImportError) as ex:
        QMessageBox.warning(window, "Attach underlay", str(ex))


def manage_dialog(window, selected=None):
    from PyQt6.QtWidgets import (
        QDialog,
        QVBoxLayout,
        QHBoxLayout,
        QListWidget,
        QFormLayout,
        QDoubleSpinBox,
        QCheckBox,
        QLabel,
        QPushButton,
        QMessageBox,
    )

    window.cancel_command()
    doc = window.document
    dialog = QDialog(window)
    dialog.setObjectName("underlay_manager")
    dialog.setWindowTitle("Reference Underlays")
    dialog.resize(540, 580)
    layout = QVBoxLayout(dialog)
    note = QLabel(
        "Embedded raster references. PDF pages are rendered at up to 150 dpi; they do not become editable CAD geometry. Calibration changes the selected reference only."
    )
    note.setWordWrap(True)
    layout.addWidget(note)
    listing = QListWidget()
    listing.setObjectName("underlay_list")
    layout.addWidget(listing)
    form = QFormLayout()
    fields = {}
    for key, label, lo, hi in (
        ("x", "Insertion X", -1e12, 1e12),
        ("y", "Insertion Y", -1e12, 1e12),
        ("width", "Width (" + doc.units + ")", 1e-9, 1e12),
        ("rotation", "Rotation (degrees)", -360000, 360000),
        ("opacity", "Opacity (%)", 0, 100),
    ):
        field = QDoubleSpinBox()
        field.setDecimals(9 if key != "opacity" else 1)
        field.setRange(lo, hi)
        field.setObjectName("underlay_" + key)
        form.addRow(label, field)
        fields[key] = field
    for key, label in (
        ("visible", "Visible"),
        ("plot", "Include in PDF plots"),
        ("locked", "Lock placement and calibration"),
    ):
        field = QCheckBox(label)
        field.setObjectName("underlay_" + key)
        form.addRow(field)
        fields[key] = field
    layout.addLayout(form)
    row = QHBoxLayout()
    layout.addLayout(row)
    apply = QPushButton("Apply")
    calibration = QPushButton("Calibrate…")
    remove = QPushButton("Remove")
    close = QPushButton("Close")
    for b in (apply, calibration, remove, close):
        row.addWidget(b)
    close.clicked.connect(dialog.accept)
    current = {"id": None}

    def lock_state():
        locked = fields["locked"].isChecked()
        for key in ("x", "y", "width", "rotation"):
            fields[key].setEnabled(not locked)
        calibration.setEnabled(current["id"] is not None and not locked)

    def load():
        idx = listing.currentRow()
        r = doc.underlays[idx] if 0 <= idx < len(doc.underlays) else None
        current["id"] = r["id"] if r else None
        for field in fields.values():
            field.setEnabled(r is not None)
        for b in (apply, calibration, remove):
            b.setEnabled(r is not None)
        if r:
            for key in ("width", "rotation"):
                fields[key].setValue(r[key])
            fields["x"].setValue(r["origin"][0])
            fields["y"].setValue(r["origin"][1])
            fields["opacity"].setValue(r["opacity"] * 100)
            for key in ("visible", "plot", "locked"):
                fields[key].setChecked(r[key])
            lock_state()

    def refresh(uid=None):
        listing.blockSignals(True)
        listing.clear()
        for r in doc.underlays:
            listing.addItem(
                r["name"] + (f" · page {r['page']}" if r["kind"] == "pdf" else "")
            )
        idx = next((i for i, r in enumerate(doc.underlays) if r["id"] == uid), 0)
        listing.setCurrentRow(idx if doc.underlays else -1)
        listing.blockSignals(False)
        load()

    def save():
        if current["id"] is None:
            return False
        after = copy.deepcopy(doc.underlays)
        r = next(r for r in after if r["id"] == current["id"])
        if not r["locked"] or not fields["locked"].isChecked():
            r["origin"] = [fields["x"].value(), fields["y"].value()]
            r["width"], r["rotation"] = (
                fields["width"].value(),
                fields["rotation"].value(),
            )
        r["opacity"] = fields["opacity"].value() / 100
        for key in ("visible", "plot", "locked"):
            r[key] = fields[key].isChecked()
        try:
            if after != doc.underlays:
                doc.undo_stack.push(UnderlaysCommand(doc, after))
            window.refresh_document_ui()
            return True
        except ValueError as ex:
            QMessageBox.warning(dialog, "Underlay", str(ex))
            return False

    def delete():
        r = next((r for r in doc.underlays if r["id"] == current["id"]), None)
        if not r:
            return
        if r["locked"]:
            QMessageBox.information(
                dialog, "Underlay", "Unlock and Apply before removing this reference."
            )
            return
        doc.undo_stack.push(
            UnderlaysCommand(
                doc, [u for u in doc.underlays if u["id"] != r["id"]], "Remove underlay"
            )
        )
        refresh()

    def start_calibration():
        if not save():
            return
        uid = current["id"]
        dialog.accept()
        window.show_drafting()
        window.set_tool("UNDERLAYCALIBRATE")
        window.current_tool.underlay_id = uid
        window.update_status()

    fields["locked"].toggled.connect(lock_state)
    listing.currentRowChanged.connect(load)
    apply.clicked.connect(save)
    remove.clicked.connect(delete)
    calibration.clicked.connect(start_calibration)
    refresh(selected)
    dialog.exec()
    dialog.setParent(None)
    dialog.deleteLater()
    window.focus_active_viewport()


def commands(window):
    return {
        "IMAGEATTACH": lambda: attach_dialog(window, "image"),
        "PDFATTACH": lambda: attach_dialog(window, "pdf"),
        "UNDERLAYS": lambda: manage_dialog(window),
    }
