"""Typed single-object editing inside the existing compact Properties dock."""

import copy
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QLabel,
    QHeaderView,
)
from .geometry import Point
from .document import SetAttrCommand


def values_for(doc, entity):
    values = {}
    for attr in (
        "p1",
        "p2",
        "center",
        "point",
        "position",
        "insertion_point",
        "dim_point",
    ):
        point = getattr(entity, attr, None)
        if isinstance(point, Point):
            values[attr + ".x"] = point.x
            values[attr + ".y"] = point.y
    for attr in ("radius", "height", "rotation", "scale", "wrap_width"):
        if hasattr(entity, attr):
            values[attr] = getattr(entity, attr)
    record = doc.extensions.get("architecture", {}).get(entity.id)
    if record:
        fields = {
            "wall": ("length", "width", "height", "material"),
            "opening": ("identifier", "station", "width", "height", "sill"),
            "room": ("number", "name", "finish"),
        }[record["kind"]]
        values.update({"Architecture." + k: record[k] for k in fields})
    if entity.kind == "INSERT":
        block = doc.blocks.get(entity.block_name)
        if block:
            for spec in block.attributes:
                values["Attribute." + spec["tag"]] = entity.attributes.get(
                    spec["tag"], spec["default"]
                )
    link = doc.extensions.get("view_links", {}).get(entity.id)
    if link:
        fields = ("axis", "offset") if link["type"] == "section" else ("view",)
        values.update({"View." + k: link[k] for k in fields})
    element = doc.extensions.get('building_elements', {}).get(entity.id)
    if element:
        values.update({'Building.'+k:v for k,v in element.items() if k not in ('kind','block','profile','holes')})
    if doc.extensions.get('levels') and entity.id not in doc.extensions.get('views', {}):
        from .building import level_for
        values['Level.name'] = level_for(doc, entity.id)
    view = doc.extensions.get('building_views', {}).get(entity.id)
    if view:
        values.update({'BuildingView.'+k:view[k] for k in ('axis','offset','view','hidden','hatch')})
    return values


def label_for(key):
    if key.startswith('Building.'):
        return key.split('.',1)[1].replace('_',' ').title()
    if key == 'Level.name':
        return 'Level'
    if key.startswith('BuildingView.'):
        return {'axis':'Section axis','offset':'Plane position','view':'Projection','hidden':'Hidden edges','hatch':'Section hatch'}[key.split('.')[1]]
    if key.startswith("Architecture."):
        return key.split(".", 1)[1].replace("_", " ").title()
    if key.startswith("Attribute."):
        return "Attribute " + key.split(".", 1)[1]
    if key.startswith("View."):
        return {
            "axis": "Section axis",
            "offset": "Plane position",
            "view": "Projection",
        }[key.split(".")[1]]
    if "." in key:
        attr, coord = key.split(".")
        return (
            {
                "p1": "Start",
                "p2": "End",
                "center": "Center",
                "point": "Point",
                "position": "Position",
                "insertion_point": "Position",
                "dim_point": "Label",
            }[attr]
            + " "
            + coord.upper()
        )
    return key.replace("_", " ").title()


def apply_values(doc, entity, values):
    from .native_io import document_to_dict, entity_to_dict, entity_from_dict
    from .validation import validate_payload, finite

    if entity not in doc.editable_entities():
        raise ValueError("Select an editable object on an unlocked layer")
    previous = values_for(doc, entity)
    if set(values) - set(previous):
        raise ValueError("Unknown object property")
    changes = {}
    extensions = copy.deepcopy(doc.extensions)
    for key, value in values.items():
        if type(previous[key]) is bool:
            if isinstance(value, str):
                if value.lower() not in ('true','false','1','0','yes','no'):
                    raise ValueError('Boolean values must be true or false')
                value = value.lower() in ('true','1','yes')
            if type(value) is not bool:
                raise ValueError('Boolean values must be true or false')
        elif type(previous[key]) in (int, float):
            value = float(value)
            finite(value, key)
            if key == 'Building.steps':
                if not value.is_integer():
                    raise ValueError('Step count must be an integer')
                value = int(value)
        elif not isinstance(value, str):
            raise ValueError("Text properties must be strings")
        if value == previous[key]:
            continue
        if key.startswith('Building.'):
            extensions['building_elements'][entity.id][key.split('.',1)[1]] = value
        elif key.startswith('BuildingView.'):
            extensions['building_views'][entity.id][key.split('.',1)[1]] = value
        elif key == 'Level.name':
            if value not in __import__('pycad.building', fromlist=['levels']).levels(doc):
                raise ValueError('Choose an existing level')
            if entity.id in extensions.get('building_elements', {}):
                extensions['building_elements'][entity.id]['level'] = value
            else:
                extensions.setdefault('level_assignments', {})[entity.id] = {'level':value}
        elif key.startswith("Architecture."):
            extensions["architecture"][entity.id][key.split(".", 1)[1]] = value
        elif key.startswith("View."):
            extensions["view_links"][entity.id][key.split(".", 1)[1]] = value
        elif key.startswith("Attribute."):
            changes.setdefault("attributes", copy.deepcopy(entity.attributes))[
                key.split(".", 1)[1]
            ] = value
        elif "." in key:
            attr, coord = key.split(".")
            point = changes.setdefault(attr, copy.deepcopy(getattr(entity, attr)))
            setattr(point, coord, value)
        else:
            changes[key] = value
    if not changes and extensions == doc.extensions:
        return False
    clone = entity_from_dict(entity_to_dict(entity))
    for key, value in changes.items():
        setattr(clone, key, copy.deepcopy(value))
    candidate = document_to_dict(doc)
    candidate["entities"] = [
        entity_to_dict(clone) if e.id == entity.id else entity_to_dict(e)
        for e in doc.entities
    ]
    candidate["extensions"] = extensions
    validate_payload(candidate)
    # Constructors also guard positive radii, text heights and nonzero INSERT scale.
    entity_from_dict(entity_to_dict(clone))
    from .drawing_checks import opening_conflicts

    record = extensions.get("architecture", {}).get(entity.id)
    if record and record["kind"] in ("wall", "opening"):
        conflicts = opening_conflicts(doc, extensions["architecture"])
        if conflicts:
            raise ValueError("The edit would overlap hosted openings")
    doc.undo_stack.beginMacro("Object properties")
    try:
        for attr, value in changes.items():
            doc.undo_stack.push(
                SetAttrCommand(
                    doc, entity, attr, getattr(entity, attr), value, "Object property"
                )
            )
        if extensions != doc.extensions:
            doc.undo_stack.push(
                SetAttrCommand(
                    doc, doc, "extensions", doc.extensions, extensions, "Object data"
                )
            )
    finally:
        doc.undo_stack.endMacro()
    return True


class ObjectEditor(QWidget):
    def __init__(self, mw):
        super().__init__()
        self.mw = mw
        self.entity = None
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 2, 0, 2)
        root.setSpacing(4)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["Property", "Value"])
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(25)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.table.setFixedHeight(180)
        root.addWidget(self.table)
        self.status = QLabel()
        self.status.setWordWrap(True)
        root.addWidget(self.status)
        bar = QHBoxLayout()
        self.apply_button = QPushButton("Apply")
        self.reload_button = QPushButton("Reset")
        self.detach_button = QPushButton("Detach link")
        for button in (self.apply_button, self.reload_button, self.detach_button):
            bar.addWidget(button)
        root.addLayout(bar)
        from .feature_helpers import safe_action

        self.apply_button.clicked.connect(safe_action(self, self.commit))
        self.reload_button.clicked.connect(lambda: self.refresh(self.entity))
        self.detach_button.clicked.connect(safe_action(self, self.detach))

    def refresh(self, entity):
        self.entity = entity
        self.setVisible(entity is not None)
        if entity is None:
            return
        doc = self.mw.document
        values = values_for(doc, entity)
        self.table.setRowCount(len(values))
        for i, (key, value) in enumerate(values.items()):
            item = QTableWidgetItem(label_for(key))
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            item.setData(Qt.ItemDataRole.UserRole, key)
            self.table.setItem(i, 0, item)
            self.table.setItem(i, 1, QTableWidgetItem(str(value)))
        self.setEnabled(doc.is_editable(entity))
        links = doc.extensions.get("wall_models", {})
        model = next(
            (key for key, link in links.items() if link["wall"] == entity.id), None
        )
        model = model or next((key for key, link in doc.extensions.get('building_models', {}).items() if link['source']==entity.id), None)
        linked = model or (
            entity.id if entity.id in doc.extensions.get("view_links", {}) or entity.id in doc.extensions.get('building_views', {}) or entity.id in doc.extensions.get('auto_rooms', {}) else None
        )
        self.detach_button.setVisible(linked is not None)
        self.status.setText(
            ("Live link: " + getattr(doc, "room_link_status", {}).get(linked, getattr(doc, "link_status", {}).get(linked, "Current")))
            if linked
            else "Values use drawing units. Apply commits one Undo step."
        )

    def commit(self):
        if self.entity is None:
            return
        values = {
            self.table.item(i, 0).data(Qt.ItemDataRole.UserRole): self.table.item(
                i, 1
            ).text()
            for i in range(self.table.rowCount())
        }
        apply_values(self.mw.document, self.entity, values)
        self.mw.refresh_document_ui()

    def detach(self):
        from .feature_data import edit_table

        doc = self.mw.document
        if self.entity.id in doc.extensions.get('auto_rooms', {}):
            edit_table(doc, 'auto_rooms', self.entity.id, None, 'Detach room from walls')
        elif self.entity.id in doc.extensions.get('building_views', {}):
            edit_table(doc, 'building_views', self.entity.id, None, 'Detach building view')
        elif self.entity.id in doc.extensions.get("view_links", {}):
            edit_table(doc, "view_links", self.entity.id, None, "Detach generated view")
        else:
            keys = [
                key
                for key, r in doc.extensions.get("wall_models", {}).items()
                if r["wall"] == self.entity.id
            ]
            doc.undo_stack.beginMacro("Detach wall model")
            for key in keys:
                edit_table(doc, "wall_models", key, None, "Detach wall model")
            for key, r in list(doc.extensions.get('building_models', {}).items()):
                if r['source'] == self.entity.id:
                    edit_table(doc, 'building_models', key, None, 'Detach building model')
            doc.undo_stack.endMacro()
        self.mw.refresh_document_ui()
