"""Small building managers and creation forms using existing menu/dock space."""

import copy
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QPushButton,
    QCheckBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QListWidget,
    QListWidgetItem,
    QFileDialog,
)
from . import building, auto_rooms, building_views
from .feature_helpers import safe_action
from .geometry import PolylineEntity
from .units import UNIT_MM


def button(bar, label, fn, parent):
    b = QPushButton(label)
    b.clicked.connect(safe_action(parent, fn))
    bar.addWidget(b)
    return b


def levels_dialog(mw):
    doc = mw.document
    d = QDialog(mw)
    d.setWindowTitle("Levels / Storeys")
    d.resize(590, 350)
    root = QVBoxLayout(d)
    root.addWidget(
        QLabel(
            "Elevations and heights use drawing units. Visibility affects drafting and model views."
        )
    )
    table = QTableWidget(0, 4)
    table.setHorizontalHeaderLabels(["Level", "Elevation", "Floor height", "Visible"])
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    root.addWidget(table)
    combo = QComboBox()
    root.addWidget(combo)

    def refresh():
        values = building.levels(doc)
        table.setRowCount(len(values))
        combo.clear()
        combo.addItems(values)
        combo.setCurrentText(building.current_level(doc))
        for i, (name, r) in enumerate(values.items()):
            item = QTableWidgetItem(name)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            table.setItem(i, 0, item)
            for j, k in [(1, "elevation"), (2, "height")]:
                table.setItem(i, j, QTableWidgetItem(str(r[k])))
            item = QTableWidgetItem()
            item.setCheckState(
                Qt.CheckState.Checked if r["visible"] else Qt.CheckState.Unchecked
            )
            table.setItem(i, 3, item)

    bar = QHBoxLayout()
    root.addLayout(bar)

    def save():
        after = copy.deepcopy(doc.extensions)
        after["levels"] = {
            table.item(i, 0).text(): dict(
                elevation=float(table.item(i, 1).text()),
                height=float(table.item(i, 2).text()),
                visible=table.item(i, 3).checkState() == Qt.CheckState.Checked,
            )
            for i in range(table.rowCount())
        }
        after.setdefault("building_settings", {})["current"] = {
            "level": combo.currentText()
        }
        building.commit_data(doc, after, "Level settings")
        mw.refresh_document_ui()

    def add():
        from PyQt6.QtWidgets import QInputDialog

        name, ok = QInputDialog.getText(d, "Add level", "Level name")
        if ok and name:
            values = building.levels(doc)
            if name in values:
                raise ValueError("Level already exists")
            last = max(values.values(), key=lambda r: r["elevation"])
            building.set_level(
                doc, name, last["elevation"] + last["height"], last["height"]
            )
            refresh()
            mw.refresh_document_ui()

    def assign():
        save()
        building.assign_level(
            doc, [e.id for e in mw.canvas.selected_entities], combo.currentText()
        )
        mw.refresh_document_ui()

    button(bar, "Add level", add, d)
    button(bar, "Apply / Current", save, d)
    button(bar, "Assign selection", assign, d)
    button(bar, "Close", d.accept, d)
    refresh()
    d.exec()


def create_dialog(mw, kind):
    doc = mw.document
    mm = 1 / UNIT_MM.get(doc.units, 1)
    selected = mw.canvas.selected_entities
    boundary = None
    if kind != "stair":
        if (
            len(selected) != 1
            or not isinstance(selected[0], PolylineEntity)
            or not selected[0].closed
            or any(selected[0].bulges)
        ):
            raise ValueError("Select one closed straight-edge boundary first")
        boundary = selected[0]
    d = QDialog(mw)
    d.setWindowTitle("Create " + kind.title())
    root = QVBoxLayout(d)
    form = QFormLayout()
    root.addLayout(form)
    editors = {}

    def text(key, label, value):
        editor = QLineEdit(str(value))
        form.addRow(label, editor)
        editors[key] = editor

    def combo(key, label, choices, value):
        editor = QComboBox()
        editor.addItems(choices)
        editor.setCurrentText(value)
        form.addRow(label, editor)
        editors[key] = editor

    text("name", "Name", kind.title())
    text("material", "Material", "Concrete")
    combo("level", "Level", list(building.levels(doc)), building.current_level(doc))
    if kind == "stair":
        combo("layout", "Layout", ["Straight", "L", "U"], "Straight")
        for key, label, value in [
            ("width", "Width", 1000 * mm),
            ("tread", "Tread", 280 * mm),
            (
                "height",
                "Total rise",
                building.levels(doc)[building.current_level(doc)]["height"],
            ),
            ("steps", "Step count", 18),
            ("landing", "Landing length / gap", 1000 * mm),
            ("rail_height", "Railing height", 900 * mm),
            ("x", "Position X", 0),
            ("y", "Position Y", 0),
        ]:
            text(key, label, value)
        rails = QCheckBox("Include flight handrails and posts")
        rails.setChecked(True)
        root.addWidget(rails)
    else:
        text("thickness", "Vertical thickness", 150 * mm)
        text(
            "elevation",
            "Elevation above level",
            0
            if kind == "slab"
            else building.levels(doc)[building.current_level(doc)]["height"],
        )
        if kind == "roof":
            combo("roof_type", "Roof type", ["Flat", "Shed", "Gable", "Hip"], "Gable")
            text("slope", "Slope (degrees)", 25)
            text("overhang", "Overhang", 300 * mm)
    model = QCheckBox("Build live 3D models (requires optional CadQuery)")
    model.setChecked(False)
    root.addWidget(model)
    create = QPushButton("Create")
    root.addWidget(create)

    def commit():
        from .automation import apply_proposal

        params = {}
        for key, editor in editors.items():
            value = (
                editor.currentText() if isinstance(editor, QComboBox) else editor.text()
            )
            params[key] = (
                value
                if key in ("name", "material", "level", "layout", "roof_type")
                else int(value)
                if key == "steps"
                else float(value)
            )
        if kind == "stair":
            params["position"] = [params.pop("x"), params.pop("y")]
            params["rails"] = rails.isChecked()
        actions = [
            dict(
                op="building",
                ref="@building",
                kind=kind,
                boundary=[]
                if boundary is None
                else [[p.x, p.y] for p in boundary.points],
                parameters=params,
            )
        ]
        if model.isChecked():
            actions.append({"op": "build3d"})
        before = {e.id for e in doc.entities}
        apply_proposal(doc, actions)
        mw.canvas.selected_entities = [
            e
            for e in doc.entities
            if e.id not in before
            and e.id in doc.extensions.get("building_elements", {})
        ]
        mw.properties_panel.show()
        mw.properties_panel.raise_()
        mw.refresh_document_ui()
        d.accept()

    create.clicked.connect(safe_action(d, commit))
    d.exec()


def hole_from_selection(mw):
    elements = [
        e
        for e in mw.canvas.selected_entities
        if mw.document.extensions.get("building_elements", {}).get(e.id, {}).get("kind")
        in ("slab", "ceiling")
    ]
    boundaries = [
        e
        for e in mw.canvas.selected_entities
        if isinstance(e, PolylineEntity) and e.closed and not any(e.bulges)
    ]
    if len(elements) != 1 or len(boundaries) != 1:
        raise ValueError("Select one slab/ceiling and one closed hole boundary")
    from .wall_joining import local_point

    element = elements[0]
    r = copy.deepcopy(mw.document.extensions["building_elements"][element.id])
    r["holes"].append(
        [
            list(local_point(element, p.as_tuple()).as_tuple())
            for p in boundaries[0].points
        ]
    )
    after = copy.deepcopy(mw.document.extensions)
    after["building_elements"][element.id] = r
    building.commit_data(mw.document, after, "Add building opening")
    mw.refresh_document_ui()


def build_all(mw):
    from .automation import apply_proposal

    apply_proposal(mw.document, [{"op": "build3d"}])
    mw.refresh_document_ui()
    mw.open_model_workspace()


def rooms(mw):
    auto_rooms.detect_rooms(mw.document)
    mw.refresh_document_ui()


def view_dialog(mw):
    doc = mw.document
    doc.sync_associative()
    sources = doc.extensions.get("solids", {})
    if not sources:
        raise ValueError("Build live wall/building models first")
    d = QDialog(mw)
    d.setWindowTitle("Building sections / Elevations")
    d.resize(590, 410)
    root = QVBoxLayout(d)
    root.addWidget(
        QLabel("Checked models share one linked view. Source edits regenerate it.")
    )
    listing = QListWidget()
    root.addWidget(listing, 1)
    for key, r in sources.items():
        source = building.source_for_solid(doc, key)
        item = QListWidgetItem(r["name"] + " · " + building.level_for(doc, source))
        item.setData(Qt.ItemDataRole.UserRole, key)
        item.setCheckState(
            Qt.CheckState.Checked
            if building.visible(doc, source)
            else Qt.CheckState.Unchecked
        )
        listing.addItem(item)
    form = QFormLayout()
    root.addLayout(form)
    kind = QComboBox()
    kind.addItems(["Elevation", "Section"])
    axis = QComboBox()
    axis.addItems(["Z", "Y", "X"])
    view = QComboBox()
    view.addItems(["Front", "Top", "Right"])
    offset = QLineEdit(str(1200 / UNIT_MM.get(doc.units, 1)))
    x = QLineEdit(str(10000 / UNIT_MM.get(doc.units, 1)))
    y = QLineEdit("0")
    form.addRow("Drawing type", kind)
    form.addRow("Projection", view)
    form.addRow("Section axis / position", axis)
    form.addRow("Plane position", offset)
    pair = QHBoxLayout()
    pair.addWidget(x)
    pair.addWidget(y)
    form.addRow("Placement X / Y", pair)
    hidden = QCheckBox("Show hidden edges as dashed lines")
    hatch = QCheckBox("Hatch section cuts")
    hatch.setChecked(True)
    root.addWidget(hidden)
    root.addWidget(hatch)
    bar = QHBoxLayout()
    root.addLayout(bar)

    def create():
        keys = [
            listing.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(listing.count())
            if listing.item(i).checkState() == Qt.CheckState.Checked
        ]
        insert = building_views.create_view(
            doc,
            keys,
            kind=kind.currentText().lower(),
            axis=axis.currentText(),
            offset=float(offset.text()),
            view=view.currentText(),
            hidden=hidden.isChecked(),
            hatch=hatch.isChecked(),
            position=(float(x.text()), float(y.text())),
        )
        mw.canvas.selected_entities = [insert]
        mw.refresh_document_ui()
        mw.canvas.zoom_extents()
        d.accept()

    button(bar, "Create view", create, d)
    button(bar, "Close", d.reject, d)
    d.exec()


def ifc(mw):
    path, _ = QFileDialog.getSaveFileName(
        mw, "Export building IFC", "building.ifc", "IFC4 (*.ifc)"
    )
    if path:
        from .ifc_export import export

        result = export(mw.document, path)
        mw.command_history.appendPlainText(
            f"IFC4 exported: {result['objects']} building objects, {result['levels']} levels"
        )


def manager(mw):
    d = QDialog(mw)
    d.setWindowTitle("Building tools")
    d.resize(440, 310)
    root = QVBoxLayout(d)
    hint = QLabel(
        "Create from a selected boundary; edit parameters in the shared Properties dock."
    )
    hint.setWordWrap(True)
    root.addWidget(hint)
    for label, fn in [
        ("Levels / Storeys", lambda: levels_dialog(mw)),
        ("Slab", lambda: create_dialog(mw, "slab")),
        ("Ceiling", lambda: create_dialog(mw, "ceiling")),
        ("Roof", lambda: create_dialog(mw, "roof")),
        ("Stair / Railing", lambda: create_dialog(mw, "stair")),
        ("Detect rooms", lambda: rooms(mw)),
        ("Build live models", lambda: build_all(mw)),
        ("Sections / Elevations", lambda: view_dialog(mw)),
    ]:
        b = QPushButton(label)
        b.clicked.connect(safe_action(d, fn))
        root.addWidget(b)
    close = QPushButton("Close")
    close.clicked.connect(d.accept)
    root.addWidget(close)
    d.exec()
