"""Compact, traceable BOQ report with editable rates and quantity tags."""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QLineEdit,
    QDoubleSpinBox,
    QComboBox,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QFileDialog,
    QHeaderView,
)
from . import boq, building
from .building_ui import button
from .feature_helpers import safe_action


def dialog(mw):
    d = QDialog(mw)
    d.setWindowTitle("Bill of quantities")
    d.resize(720, 410)
    root = QVBoxLayout(d)
    row = QHBoxLayout()
    level = QComboBox()
    level.addItems(["All levels"] + list(building.levels(mw.document)))
    currency = QLineEdit(
        mw.document.extensions.get("boq", {}).get("settings", {}).get("currency", "INR")
    )
    currency.setMaximumWidth(65)
    waste = QDoubleSpinBox()
    waste.setRange(0, 100)
    waste.setSuffix("%")
    waste.setValue(
        mw.document.extensions.get("boq", {})
        .get("settings", {})
        .get("waste_percent", 0)
    )
    row.addWidget(level)
    row.addWidget(QLabel("Currency"))
    row.addWidget(currency)
    row.addWidget(QLabel("Allowance"))
    row.addWidget(waste)
    root.addLayout(row)
    table = QTableWidget(0, 7)
    table.setHorizontalHeaderLabels(
        ["Item", "Material", "Unit", "Net quantity", "Rate", "Amount", "Sources"]
    )
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    table.setColumnWidth(0, 170)
    root.addWidget(table, 1)
    totals = QLabel()
    totals.setWordWrap(True)
    root.addWidget(totals)
    note = QLabel(
        "Rows retain source IDs. Blank rates are unpriced. Quantity tags cover plain imported geometry."
    )
    note.setWordWrap(True)
    root.addWidget(note)
    state = {}

    def scope():
        return None if level.currentIndex() == 0 else level.currentText()

    def refresh():
        report = boq.report(mw.document, level=scope())
        rows = {}
        for item in report["items"]:
            key = item["rate_key"]
            if key not in rows:
                rows[key] = {
                    **item,
                    "source_ids": [],
                    "quantity": 0,
                    "amount": None if item["rate"] is None else 0,
                }
            row = rows[key]
            row["source_ids"].append(item["source_id"])
            row["quantity"] += item["quantity"]
            if item["amount"] is not None:
                row["amount"] += item["amount"]
        state["rows"] = list(rows.values())
        table.setRowCount(len(rows))
        for i, r in enumerate(state["rows"]):
            values = [
                r["description"],
                r["material"],
                r["unit"],
                f"{r['quantity']:.4f}",
                "" if r["rate"] is None else str(r["rate"]),
                "Unpriced" if r["amount"] is None else f"{r['amount']:.2f}",
                str(len(set(r["source_ids"]))),
            ]
            for j, value in enumerate(values):
                item = QTableWidgetItem(value)
                if j != 4:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                table.setItem(i, j, item)
        totals.setText(
            f"Priced subtotal: {report['currency']} {report['priced_total']:,.2f} · {report['unpriced_items']} unpriced items · {len(report['unmeasured_ids'])} unmeasured objects\n"
            + "\n".join(report["warnings"][:3])
        )

    def apply():
        rates = dict(mw.document.extensions.get("boq", {}).get("rates", {}))
        for i, r in enumerate(state["rows"]):
            value = table.item(i, 4).text().strip()
            if value:
                rates[r["rate_key"]] = float(value)
            else:
                rates.pop(r["rate_key"], None)
        boq.set_rates(mw.document, rates, currency.text(), waste.value())
        mw.refresh_document_ui()
        refresh()

    def select():
        i = table.currentRow()
        if i < 0:
            return
        ids = set(state["rows"][i]["source_ids"])
        if mw.document.current_space != "Model":
            mw.space_tabs.setCurrentIndex(
                next(
                    n
                    for n in range(mw.space_tabs.count())
                    if mw.space_tabs.tabText(n) == "Model"
                )
            )
        mw.viewport_stack.setCurrentWidget(mw.canvas)
        mw.canvas.selected_entities = [
            e for e in mw.document.editable_entities() if e.id in ids
        ]
        mw.refresh_document_ui()
        d.accept()

    def export():
        path, _ = QFileDialog.getSaveFileName(
            d,
            "Export quantities",
            "bill-of-quantities.csv",
            "CSV (*.csv);;Detailed JSON (*.json)",
        )
        if path:
            boq.export(mw.document, path, level=scope())

    bar = QHBoxLayout()
    root.addLayout(bar)
    button(bar, "Recalculate", refresh, d)
    button(bar, "Apply rates", apply, d)
    button(bar, "Select sources", select, d)
    button(bar, "Export", export, d)
    button(bar, "Close", d.accept, d)
    level.currentIndexChanged.connect(safe_action(d, refresh))
    refresh()
    d.exec()


def tag_dialog(mw):
    ids = [e.id for e in mw.canvas.selected_entities]
    if not ids:
        raise ValueError("Select geometry to tag for quantity measurement")
    d = QDialog(mw)
    d.setWindowTitle("Quantity measurement tag")
    root = QVBoxLayout(d)
    form = QFormLayout()
    description = QLineEdit("Measured item")
    material = QLineEdit("Unspecified")
    measurement = QComboBox()
    measurement.addItems(["Length", "Area", "Volume", "Count"])
    factor = QLineEdit("1")
    form.addRow("Item description", description)
    form.addRow("Material / Finish", material)
    form.addRow("Measure", measurement)
    form.addRow("Factor", factor)
    root.addLayout(form)
    hint = QLabel(
        "Length: line/polyline/circle. Area: closed boundary. Volume: closed area × thickness in metres entered as Factor. Count: instances. Physical drawing units are required."
    )
    hint.setWordWrap(True)
    root.addWidget(hint)
    apply = QPushButton("Tag selection")

    def commit():
        boq.tag(
            mw.document,
            ids,
            description.text(),
            material.text(),
            measurement.currentText(),
            float(factor.text()),
        )
        mw.refresh_document_ui()
        d.accept()

    apply.clicked.connect(safe_action(d, commit))
    root.addWidget(apply)
    d.resize(440, 260)
    d.exec()
