"""Physical paper sheets, title blocks, exact scales and ordered PDF publishing."""

import copy
from .feature_data import edit_table
from .document import SetAttrCommand
from .units import UNIT_MM

DEFAULT_PRESET = {
    "page_width": 297.0,
    "page_height": 210.0,
    "margin": 10.0,
    "monochrome": True,
    "scale_denominator": None,
}


def validate_preset(value):
    from .validation import finite

    if not isinstance(value, dict) or set(value) != set(DEFAULT_PRESET):
        raise ValueError("Invalid plot preset")
    for k in ("page_width", "page_height", "margin"):
        finite(value[k], k, k != "margin")
    if value["margin"] < 0 or 2 * value["margin"] >= min(
        value["page_width"], value["page_height"]
    ):
        raise ValueError("Margins leave no printable area")
    if type(value["monochrome"]) is not bool:
        raise ValueError("Monochrome must be boolean")
    if value["scale_denominator"] is not None:
        finite(value["scale_denominator"], "Scale denominator", True)
    return value


def save_preset(doc, name, value):
    from .validation import name as valid_name

    valid_name(name, "Preset name")
    validate_preset(value)
    edit_table(doc, "plot_presets", name, value, "Save plot preset")


def title_block(
    doc,
    space,
    project="Project",
    title="Drawing",
    number="A001",
    revision="A",
    author="",
):
    if space not in doc.layouts:
        raise ValueError("Create or select a paper layout")
    value = {
        "project": project,
        "title": title,
        "number": number,
        "revision": revision,
        "author": author,
    }
    if any(not isinstance(v, str) or len(v) > 255 for v in value.values()):
        raise ValueError("Title block fields must be at most 255 characters")
    doc.undo_stack.beginMacro("Title block")
    try:
        edit_table(doc, "sheets", space, value, "Edit title block")
        # Keep the model viewport above the title strip when adding a title for the first time.
        layout = doc.layouts[space]
        title_top = (
            min(10, min(layout.page_width, layout.page_height) * 0.04)
            + min(35, layout.page_height * 0.2)
            + 3
        )
        for viewport in layout.viewports:
            if viewport.y < title_top:
                delta = title_top - viewport.y
                if viewport.height - delta > 10:
                    doc.undo_stack.push(
                        SetAttrCommand(
                            doc,
                            viewport,
                            "height",
                            viewport.height,
                            viewport.height - delta,
                            "Title clearance",
                        )
                    )
                    doc.undo_stack.push(
                        SetAttrCommand(
                            doc, viewport, "y", viewport.y, title_top, "Title clearance"
                        )
                    )
    finally:
        doc.undo_stack.endMacro()


def set_viewport_scale(doc, viewport, denominator):
    from .validation import finite

    finite(denominator, "Scale denominator", True)
    scale = UNIT_MM[doc.units] / denominator
    doc.undo_stack.push(
        SetAttrCommand(
            doc,
            viewport,
            "scale",
            viewport.scale,
            scale,
            "Viewport scale 1:" + str(denominator),
        )
    )


def title_geometry(doc, space):
    from .geometry import LineEntity, TextEntity, Point

    layout = doc.layouts.get(space)
    data = doc.extensions.get("sheets", {}).get(space)
    if layout is None or data is None:
        return []
    w, h = layout.page_width, layout.page_height
    margin = min(10, min(w, h) * 0.04)
    height = min(35, h * 0.2)
    x0 = margin
    x1 = w - margin
    y0 = margin
    y1 = margin + height
    lines = [
        LineEntity(Point(x0, y0), Point(x1, y0)),
        LineEntity(Point(x1, y0), Point(x1, y1)),
        LineEntity(Point(x1, y1), Point(x0, y1)),
        LineEntity(Point(x0, y1), Point(x0, y0)),
    ]
    split = x0 + (x1 - x0) * 0.7
    lines.append(LineEntity(Point(split, y0), Point(split, y1)))
    lines.append(LineEntity(Point(x0, y0 + height * 0.5), Point(x1, y0 + height * 0.5)))
    size = min(3.5, height * 0.12)
    labels = [
        (data["project"], x0 + 3, y0 + height * 0.73),
        (data["title"], x0 + 3, y0 + height * 0.23),
        (data["number"] + " · Rev " + data["revision"], split + 3, y0 + height * 0.73),
        (data["author"], split + 3, y0 + height * 0.23),
    ]
    return lines + [
        TextEntity(Point(x, y), text, size) for text, x, y in labels if text
    ]


def draw_title(renderer, painter, space):
    from PyQt6.QtGui import QPen, QColor

    painter.save()
    painter.setPen(QPen(QColor("#17202a"), getattr(renderer, "_plot_pen_width", 1)))
    for entity in title_geometry(renderer.document, space):
        renderer._draw_entity(painter, entity)
    painter.restore()


def sheets_dialog(mw):
    from PyQt6.QtCore import Qt
    from PyQt6.QtWidgets import (
        QDialog,
        QVBoxLayout,
        QHBoxLayout,
        QListWidget,
        QListWidgetItem,
        QPushButton,
        QInputDialog,
        QFileDialog,
        QMessageBox,
        QComboBox,
        QLabel,
    )

    doc = mw.document
    d = QDialog(mw)
    d.setWindowTitle("Drawing sheets / Publish")
    d.resize(660, 410)
    root = QVBoxLayout(d)
    root.addWidget(
        QLabel(
            "Check sheets, arrange their order, then publish one combined vector PDF."
        )
    )
    items = QListWidget()
    root.addWidget(items)
    bar = QHBoxLayout()
    root.addLayout(bar)
    presets = QComboBox()
    root.addWidget(presets)

    def refresh():
        items.clear()
        for name in doc.layouts:
            item = QListWidgetItem(name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            items.addItem(item)
        presets.clear()
        presets.addItem("Default")
        presets.addItems(doc.extensions.get("plot_presets", {}))

    def perform(op):
        try:
            current = items.currentItem()
            space = current.text() if current else doc.current_space
            if op == "new":
                name, ok = QInputDialog.getText(d, "New sheet", "Sheet name")
                if ok and name.strip():
                    doc.create_layout(name.strip())
                    refresh()
            elif op == "title":
                if space not in doc.layouts:
                    raise ValueError("Select a sheet")
                old = doc.extensions.get("sheets", {}).get(
                    space,
                    dict(
                        project="Project",
                        title=space,
                        number="A001",
                        revision="A",
                        author="",
                    ),
                )
                text, ok = QInputDialog.getMultiLineText(
                    d,
                    "Title block",
                    "One key=value per line",
                    "\n".join(k + "=" + v for k, v in old.items()),
                )
                if ok:
                    data = dict(old)
                    for line in text.splitlines():
                        key, value = line.split("=", 1)
                        if key not in data:
                            raise ValueError("Unknown title field")
                        data[key] = value
                    title_block(doc, space, **data)
            elif op == "scale":
                layout = doc.layouts.get(space)
                if layout is None or not layout.viewports:
                    raise ValueError("Sheet has no viewport")
                index, ok = QInputDialog.getInt(
                    d, "Viewport", "Viewport number", 1, 1, len(layout.viewports)
                )
                if not ok:
                    return
                denominator, ok = QInputDialog.getDouble(
                    d, "Scale", "Scale denominator (1:N)", 100, 0.000001, 1e12, 6
                )
                if ok:
                    set_viewport_scale(doc, layout.viewports[index - 1], denominator)
            elif op == "preset":
                name, ok = QInputDialog.getText(d, "Plot preset", "Preset name")
                if not ok or not name.strip():
                    return
                old = copy.deepcopy(
                    doc.extensions.get("plot_presets", {}).get(
                        presets.currentText(), DEFAULT_PRESET
                    )
                )
                text, ok = QInputDialog.getMultiLineText(
                    d,
                    "Plot preset",
                    "Dimensions and margins in mm. Scale: fit or denominator.",
                    "\n".join(
                        f"{k}={v if v is not None else 'fit'}" for k, v in old.items()
                    ),
                )
                if ok:
                    for line in text.splitlines():
                        k, v = line.split("=", 1)
                        if k not in old:
                            raise ValueError("Unknown preset property")
                        if k == "monochrome":
                            if v.lower() not in ("true", "false"):
                                raise ValueError("Monochrome must be true or false")
                            old[k] = v.lower() == "true"
                        else:
                            old[k] = (
                                None
                                if k == "scale_denominator" and v.lower() == "fit"
                                else float(v)
                            )
                    save_preset(doc, name.strip(), old)
                    refresh()
                    presets.setCurrentText(name.strip())
            elif op in ("up", "down"):
                row = items.currentRow()
                target = row + (-1 if op == "up" else 1)
                if row >= 0 and 0 <= target < items.count():
                    item = items.takeItem(row)
                    items.insertItem(target, item)
                    items.setCurrentRow(target)
            else:
                spaces = [
                    items.item(i).text()
                    for i in range(items.count())
                    if items.item(i).checkState() == Qt.CheckState.Checked
                ]
                if not spaces:
                    raise ValueError("Check at least one sheet")
                path, _ = QFileDialog.getSaveFileName(
                    d, "Publish sheet set", "drawing-sheets.pdf", "PDF (*.pdf)"
                )
                if path:
                    from .plotting import publish_pdf

                    preset = doc.extensions.get("plot_presets", {}).get(
                        presets.currentText(), DEFAULT_PRESET
                    )
                    publish_pdf(doc, path, spaces, preset=preset)
                    mw.command_history.appendPlainText(
                        f"Published {len(spaces)} sheets: " + path
                    )
            mw.refresh_document_ui()
        except (ValueError, OSError) as ex:
            QMessageBox.warning(d, "Sheets", str(ex))

    for label, op in [
        ("New", "new"),
        ("Title block", "title"),
        ("Scale", "scale"),
        ("↑", "up"),
        ("↓", "down"),
        ("Preset", "preset"),
        ("Publish PDF", "publish"),
    ]:
        b = QPushButton(label)
        b.clicked.connect(lambda _, o=op: perform(o))
        bar.addWidget(b)
    refresh()
    d.exec()
