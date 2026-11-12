"""Saved layer states, property filters, viewport overrides and compact auto-hide."""

import copy
from .feature_data import edit_table
from .table_commands import LayerStateCommand


def save_state(doc, name):
    from .validation import name as valid_name

    valid_name(name, "Layer state name")
    edit_table(
        doc,
        "layer_states",
        name,
        {
            "layers": copy.deepcopy(doc.layers.layers),
            "current": doc.layers.current_layer,
        },
        "Save layer state",
    )


def restore_state(doc, name):
    state = doc.extensions.get("layer_states", {}).get(name)
    if state is None:
        raise ValueError("Layer state does not exist")
    layers = copy.deepcopy(doc.layers.layers)
    for key, props in state["layers"].items():
        if key in layers:
            layers[key] = copy.deepcopy(props)
    current = (
        state["current"] if state["current"] in layers else doc.layers.current_layer
    )
    if layers[current].get("frozen"):
        layers[current]["frozen"] = False
    doc.undo_stack.push(LayerStateCommand(doc, layers, current, "Restore layer state"))


def matches(props, query):
    return {
        "All": True,
        "Visible": props["visible"] and not props.get("frozen", False),
        "Hidden": not props["visible"] or props.get("frozen", False),
        "Locked": props["locked"],
        "Unlocked": not props["locked"],
        "Plot": props.get("plot", True),
        "No plot": not props.get("plot", True),
        "Dashed": props.get("linetype", "CONTINUOUS") != "CONTINUOUS",
    }.get(query, True)


def state_dialog(mw):
    from PyQt6.QtWidgets import (
        QDialog,
        QVBoxLayout,
        QHBoxLayout,
        QListWidget,
        QPushButton,
        QInputDialog,
    )

    d = QDialog(mw)
    d.setWindowTitle("Layer states")
    d.resize(400, 280)
    root = QVBoxLayout(d)
    items = QListWidget()
    root.addWidget(items)
    bar = QHBoxLayout()
    root.addLayout(bar)

    def refresh():
        items.clear()
        items.addItems(mw.document.extensions.get("layer_states", {}))

    def save():
        name, ok = QInputDialog.getText(d, "Layer state", "State name")
        if ok and name.strip():
            save_state(mw.document, name.strip())
            refresh()

    def restore():
        if items.currentItem():
            restore_state(mw.document, items.currentItem().text())
            mw.refresh_document_ui()

    def delete():
        if items.currentItem():
            edit_table(
                mw.document,
                "layer_states",
                items.currentItem().text(),
                None,
                "Delete layer state",
            )
            refresh()

    for label, fn in [
        ("Save current", save),
        ("Restore", restore),
        ("Delete", delete),
        ("Close", d.accept),
    ]:
        b = QPushButton(label)
        b.clicked.connect(
            __import__("pycad.feature_helpers", fromlist=["safe_action"]).safe_action(
                d, fn
            )
        )
        bar.addWidget(b)
    refresh()
    d.exec()


def overrides(doc, space, index):
    return doc.extensions.get("viewport_overrides", {}).get(
        space + "::" + str(index), {}
    )


def viewport_override_dialog(mw):
    from PyQt6.QtWidgets import (
        QDialog,
        QVBoxLayout,
        QTableWidget,
        QTableWidgetItem,
        QCheckBox,
        QPushButton,
        QColorDialog,
        QDialogButtonBox,
    )

    doc = mw.document
    space = doc.current_space
    layout = doc.layouts.get(space)
    if layout is None or mw.canvas.selected_viewport not in layout.viewports:
        raise ValueError("Select a paper-space viewport")
    index = layout.viewports.index(mw.canvas.selected_viewport)
    values = copy.deepcopy(overrides(doc, space, index))
    d = QDialog(mw)
    d.setWindowTitle("Viewport layer overrides")
    d.resize(420, 320)
    root = QVBoxLayout(d)
    table = QTableWidget(len(doc.layers.layers), 3)
    table.setHorizontalHeaderLabels(["Layer", "Visible", "Color"])
    root.addWidget(table)
    widgets = {}
    for i, (name, props) in enumerate(doc.layers.layers.items()):
        table.setItem(i, 0, QTableWidgetItem(name))
        check = QCheckBox()
        check.setChecked(values.get(name, {}).get("visible", True))
        table.setCellWidget(i, 1, check)
        color = QPushButton(values.get(name, {}).get("color", "Inherit"))
        table.setCellWidget(i, 2, color)
        widgets[name] = (check, color)

        def choose(checked=False, b=color):
            value = QColorDialog.getColor(parent=d)
            if value.isValid():
                b.setText(value.name())

        color.clicked.connect(choose)
    reset = QPushButton("Reset overrides")
    root.addWidget(reset)

    def clear():
        for check, color in widgets.values():
            check.setChecked(True)
            color.setText("Inherit")

    reset.clicked.connect(clear)
    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
    )
    root.addWidget(buttons)
    buttons.accepted.connect(d.accept)
    buttons.rejected.connect(d.reject)
    if d.exec() == QDialog.DialogCode.Accepted:
        after = {}
        for name, (check, color) in widgets.items():
            value = {}
            if not check.isChecked():
                value["visible"] = False
            if color.text() != "Inherit":
                value["color"] = color.text()
            if value:
                after[name] = value
        edit_table(
            doc,
            "viewport_overrides",
            space + "::" + str(index),
            after,
            "Viewport layer overrides",
        )


def install_auto_hide(mw):
    from PyQt6.QtCore import QTimer
    from PyQt6.QtGui import QCursor
    from PyQt6.QtWidgets import QPushButton, QApplication
    from . import appsettings

    show = QPushButton("Layers")
    show.clicked.connect(lambda: (mw.layer_panel.show(), mw.layer_panel.raise_()))
    mw.statusBar().addPermanentWidget(show)
    pin = QPushButton("Pin layers")
    pin.setCheckable(True)
    pin.setChecked(
        appsettings.get_settings().value("interface/layer_pin", True, type=bool)
    )
    pin.toggled.connect(
        lambda value: appsettings.get_settings().setValue("interface/layer_pin", value)
    )
    mw.statusBar().addPermanentWidget(pin)
    mw.layer_pin = pin
    timer = QTimer(mw)
    timer.setInterval(1200)

    def hide():
        panel = mw.layer_panel
        focus = QApplication.focusWidget()
        if (
            not pin.isChecked()
            and panel.isVisible()
            and not panel.isFloating()
            and not panel.rect().contains(panel.mapFromGlobal(QCursor.pos()))
            and not (focus is panel or (focus and panel.isAncestorOf(focus)))
        ):
            panel.hide()

    timer.timeout.connect(hide)
    timer.start()
    mw.layer_hide_timer = timer
