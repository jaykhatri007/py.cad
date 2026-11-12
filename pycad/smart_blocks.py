"""Editable ATTDEF/ATTRIB data and live block quantity schedules."""

import csv
from .geometry import Point, TextEntity, BlockReferenceEntity
from .document import SetAttrCommand


def validate_attributes(specs, layers=None, styles=None):
    from .validation import name, finite

    if not isinstance(specs, list) or len(specs) > 256:
        raise ValueError("Maximum 256 attributes per block")
    tags = set()
    for spec in specs:
        if not isinstance(spec, dict) or set(spec) != {
            "tag",
            "prompt",
            "default",
            "position",
            "height",
            "rotation",
            "visible",
            "layer",
            "style_name",
        }:
            raise ValueError("Invalid attribute definition")
        name(spec["tag"], "Attribute tag")
        if spec["tag"].casefold() in tags:
            raise ValueError("Duplicate attribute tag")
        tags.add(spec["tag"].casefold())
        for key in ("prompt", "default"):
            if not isinstance(spec[key], str) or len(spec[key]) > 10000:
                raise ValueError("Invalid attribute text")
        if not isinstance(spec["position"], list) or len(spec["position"]) != 2:
            raise ValueError("Invalid attribute position")
        for v in spec["position"]:
            finite(v, "Position")
        finite(spec["height"], "Attribute height", True)
        finite(spec["rotation"], "Attribute angle")
        if type(spec["visible"]) is not bool:
            raise ValueError("Attribute visibility must be boolean")
        if layers is not None and spec["layer"] not in layers:
            raise ValueError("Missing attribute layer")
        if styles is not None and spec["style_name"] not in styles:
            raise ValueError("Missing attribute style")


def attribute_entities(block, values):
    return [
        TextEntity(
            Point(*s["position"]),
            values.get(s["tag"], s["default"]),
            height=s["height"],
            rotation=s["rotation"],
            layer=s["layer"],
            style_name=s["style_name"],
        )
        for s in block.attributes
        if s["visible"]
    ]


def define_attribute(
    doc,
    block_name,
    tag,
    default="",
    position=(0, 0),
    height=2.5,
    prompt="",
    visible=True,
):
    block = doc.blocks.get(block_name)
    if block is None or block.is_xref:
        raise ValueError("Choose a local block")
    spec = dict(
        tag=tag.strip().upper(),
        prompt=prompt or tag,
        default=str(default),
        position=list(position),
        height=height,
        rotation=0.0,
        visible=visible,
        layer=doc.layers.current_layer,
        style_name=doc.current_textstyle,
    )
    after = [
        s for s in block.attributes if s["tag"].casefold() != spec["tag"].casefold()
    ] + [spec]
    validate_attributes(after, doc.layers.layers, doc.textstyles)
    doc.undo_stack.push(
        SetAttrCommand(
            doc, block, "attributes", block.attributes, after, "Define block attribute"
        )
    )


def set_attributes(doc, insert, values):
    if insert not in doc.editable_entities():
        raise ValueError("Choose an editable block instance")
    allowed = {s["tag"] for s in doc.blocks[insert.block_name].attributes}
    if set(values) - allowed:
        raise ValueError("Unknown block attribute tag")
    if any(not isinstance(v, str) or len(v) > 10000 for v in values.values()):
        raise ValueError("Invalid attribute value")
    doc.undo_stack.push(
        SetAttrCommand(
            doc,
            insert,
            "attributes",
            insert.attributes,
            values,
            "Edit block attributes",
        )
    )


def schedule_rows(doc, block_names=None, group=False):
    names = set(block_names or doc.blocks)
    rows = []
    for e in doc.entities:
        if not isinstance(e, BlockReferenceEntity) or e.block_name not in names:
            continue
        block = doc.blocks[e.block_name]
        row = {"Block": e.block_name, "Layer": e.layer, "Quantity": 1}
        row.update(
            {
                s["tag"]: e.attributes.get(s["tag"], s["default"])
                for s in block.attributes
            }
        )
        architectural = doc.extensions.get("architecture", {}).get(e.id)
        if architectural:
            row["Type"] = architectural["kind"]
            for field in (
                "identifier",
                "name",
                "number",
                "finish",
                "material",
                "width",
                "height",
            ):
                if field in architectural:
                    row[field.title()] = architectural[field]
            if architectural["kind"] == "room":
                from .architecture import room_metrics
                from .units import UNIT_MM

                _, area, _ = room_metrics(doc, architectural)
                row["Area"] = (
                    area
                    if doc.units == "unitless"
                    else area * (UNIT_MM[doc.units] / 1000) ** 2
                )
                row["Area units"] = (
                    "drawing units²" if doc.units == "unitless" else "m²"
                )
        rows.append(row)
    if group:
        grouped = {}
        for row in rows:
            key = tuple(sorted((k, v) for k, v in row.items() if k != "Quantity"))
            if key in grouped:
                grouped[key]["Quantity"] += 1
            else:
                grouped[key] = dict(row)
        rows = list(grouped.values())
    return rows


def export_schedule(doc, path, block_names=None, group=True):
    from .native_io import atomic_write

    rows = schedule_rows(doc, block_names, group)
    columns = ["Block", "Layer", "Quantity"] + sorted(
        {k for row in rows for k in row} - {"Block", "Layer", "Quantity"}
    )

    def write(filename):
        with open(filename, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)

    atomic_write(path, write)
    return rows


def attribute_dialog(mw, definition=False):
    from PyQt6.QtWidgets import (
        QDialog,
        QFormLayout,
        QLineEdit,
        QDoubleSpinBox,
        QCheckBox,
        QDialogButtonBox,
        QInputDialog,
    )

    doc = mw.document
    if definition:
        names = [n for n, b in doc.blocks.items() if not b.is_xref]
        if not names:
            raise ValueError("Create a block first")
        name, ok = QInputDialog.getItem(
            mw, "Attribute definition", "Block", names, editable=False
        )
        if not ok:
            return
        d = QDialog(mw)
        d.setWindowTitle("Attribute definition")
        form = QFormLayout(d)
        fields = {}
        for key, label, value in [
            ("tag", "Tag", "ID"),
            ("default", "Default value", "D01"),
            ("prompt", "Prompt", "Identifier"),
            ("position", "Local position (x,y)", "0,0"),
        ]:
            fields[key] = QLineEdit(value)
            form.addRow(label, fields[key])
        height = QDoubleSpinBox()
        height.setRange(0.001, 1e6)
        height.setValue(2.5)
        form.addRow("Height", height)
        visible = QCheckBox("Visible")
        visible.setChecked(True)
        form.addRow(visible)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        form.addRow(buttons)
        buttons.accepted.connect(d.accept)
        buttons.rejected.connect(d.reject)
        if d.exec() == QDialog.DialogCode.Accepted:
            position = tuple(map(float, fields["position"].text().split(",")))
            if len(position) != 2:
                raise ValueError("Enter x,y")
            define_attribute(
                doc,
                name,
                fields["tag"].text(),
                fields["default"].text(),
                position,
                height.value(),
                fields["prompt"].text(),
                visible.isChecked(),
            )
    else:
        items = [
            e
            for e in mw.canvas.selected_entities
            if isinstance(e, BlockReferenceEntity)
        ]
        if len(items) != 1:
            raise ValueError("Select one block instance")
        e = items[0]
        specs = doc.blocks[e.block_name].attributes
        if not specs:
            raise ValueError("This block has no attributes; use ATTDEF")
        d = QDialog(mw)
        d.setWindowTitle("Block attributes")
        form = QFormLayout(d)
        fields = {}
        for s in specs:
            field = fields[s["tag"]] = QLineEdit(
                e.attributes.get(s["tag"], s["default"])
            )
            form.addRow(s["prompt"] + " (" + s["tag"] + ")", field)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        form.addRow(buttons)
        buttons.accepted.connect(d.accept)
        buttons.rejected.connect(d.reject)
        if d.exec() == QDialog.DialogCode.Accepted:
            set_attributes(doc, e, {k: v.text() for k, v in fields.items()})


def schedule_dialog(mw):
    from PyQt6.QtWidgets import (
        QDialog,
        QVBoxLayout,
        QHBoxLayout,
        QTableWidget,
        QTableWidgetItem,
        QCheckBox,
        QPushButton,
        QFileDialog,
        QInputDialog,
        QComboBox,
    )
    from .feature_data import edit_table

    d = QDialog(mw)
    d.setWindowTitle("Live block schedule")
    d.resize(720, 400)
    root = QVBoxLayout(d)
    selector = QComboBox()
    selector.addItem("All blocks")
    selector.addItems(mw.document.blocks)
    selector.addItems(
        ["Saved: " + name for name in mw.document.extensions.get("schedules", {})]
    )
    root.addWidget(selector)
    group = QCheckBox("Group matching attributes and count quantities")
    group.setChecked(True)
    root.addWidget(group)
    table = QTableWidget()
    root.addWidget(table)
    bar = QHBoxLayout()
    root.addLayout(bar)

    def selected_names():
        name = selector.currentText()
        if name.startswith("Saved: "):
            return mw.document.extensions["schedules"][name[7:]]["blocks"]
        return None if name == "All blocks" else [name]

    def refresh():
        rows = schedule_rows(mw.document, selected_names(), group=group.isChecked())
        cols = ["Block", "Layer", "Quantity"] + sorted(
            {k for r in rows for k in r} - {"Block", "Layer", "Quantity"}
        )
        table.setColumnCount(len(cols))
        table.setHorizontalHeaderLabels(cols)
        table.setRowCount(len(rows))
        for i, row in enumerate(rows):
            for j, key in enumerate(cols):
                table.setItem(i, j, QTableWidgetItem(str(row.get(key, ""))))
        table.resizeColumnsToContents()

    def export():
        path, _ = QFileDialog.getSaveFileName(
            d, "Export CSV", "block-schedule.csv", "CSV (*.csv)"
        )
        if path:
            export_schedule(
                mw.document, path, selected_names(), group=group.isChecked()
            )

    def save():
        name, ok = QInputDialog.getText(d, "Schedule", "Saved schedule name")
        if ok and name.strip():
            edit_table(
                mw.document,
                "schedules",
                name.strip(),
                {
                    "blocks": selected_names() or list(mw.document.blocks),
                    "group": group.isChecked(),
                },
                "Save schedule",
            )
            selector.addItem("Saved: " + name.strip())

    for label, fn in [
        ("Refresh", refresh),
        ("Save definition", save),
        ("Export CSV", export),
        ("Close", d.accept),
    ]:
        b = QPushButton(label)
        b.clicked.connect(
            __import__("pycad.feature_helpers", fromlist=["safe_action"]).safe_action(
                d, fn
            )
        )
        bar.addWidget(b)

    def select_changed():
        name = selector.currentText()
        if name.startswith("Saved: "):
            group.setChecked(mw.document.extensions["schedules"][name[7:]]["group"])
        refresh()

    selector.currentTextChanged.connect(select_changed)
    group.toggled.connect(refresh)
    refresh()
    d.exec()
