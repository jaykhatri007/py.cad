"""Saved material appearances and embedded texture previews."""

import base64
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QImage, QPixmap, QBrush
from .feature_data import edit_table

DEFAULTS = {
    "Concrete": dict(color="#abb0b4", opacity=1.0, pattern="Solid", texture=""),
    "Brick": dict(color="#b8775d", opacity=1.0, pattern="Brick", texture=""),
    "Timber": dict(color="#bb9468", opacity=1.0, pattern="Wood", texture=""),
    "Tile": dict(color="#bfc8ca", opacity=1.0, pattern="Tile", texture=""),
    "Glass": dict(color="#84bbce", opacity=0.35, pattern="Solid", texture=""),
    "Steel": dict(color="#8b99a4", opacity=1.0, pattern="Solid", texture=""),
}


def validate_materials(value):
    from .validation import color, finite, name

    for key, r in value.get("materials", {}).items():
        name(key, "Material name")
        if (
            not isinstance(r, dict)
            or set(r) != {"color", "opacity", "pattern", "texture"}
            or r["pattern"] not in ("Solid", "Brick", "Wood", "Tile")
        ):
            raise ValueError("Invalid material appearance")
        color(r["color"], False)
        finite(r["opacity"], "Material opacity")
        if not 0 <= r["opacity"] <= 1:
            raise ValueError("Opacity must be 0–1")
        if not isinstance(r["texture"], str) or len(r["texture"]) > 1400000:
            raise ValueError("Embedded texture exceeds 1 MiB")
        if r["texture"]:
            try:
                raw = base64.b64decode(r["texture"], validate=True)
            except Exception as ex:
                raise ValueError("Invalid texture encoding") from ex
            image = QImage.fromData(raw)
            if image.isNull() or image.width() > 2048 or image.height() > 2048:
                raise ValueError("Texture must be an image up to 2048 × 2048")
    available = set(DEFAULTS) | set(value.get("materials", {}))
    for key, r in value.get("material_assignments", {}).items():
        name(key, "Material target")
        if (
            not isinstance(r, dict)
            or set(r) != {"material"}
            or r["material"] not in available
        ):
            raise ValueError("Invalid assigned material")


def material_name(doc, key):
    from .building import source_for_solid

    key = source_for_solid(doc, key)
    assigned = doc.extensions.get("material_assignments", {}).get(key)
    if assigned:
        return assigned["material"]
    record = doc.extensions.get("building_elements", {}).get(key) or doc.extensions.get(
        "architecture", {}
    ).get(key, {})
    return record.get("material", "")


def appearance(doc, key):
    name = material_name(doc, key)
    return doc.extensions.get("materials", {}).get(name, DEFAULTS.get(name))


def assign(doc, ids, name):
    from .building import source_for_solid, commit_data
    import copy

    if name not in DEFAULTS and name not in doc.extensions.get("materials", {}):
        raise ValueError("Choose a defined material")
    after = copy.deepcopy(doc.extensions)
    for key in ids:
        key = source_for_solid(doc, key)
        entity = doc.find_by_id(key)
        if entity is None or entity not in doc.editable_entities():
            raise ValueError("Material target is missing, hidden or locked")
        after.setdefault("material_assignments", {})[key] = {"material": name}
        record = after.get("building_elements", {}).get(key) or after.get(
            "architecture", {}
        ).get(key)
        if record and "material" in record:
            record["material"] = name
    commit_data(doc, after, "Assign material")


def save_material(doc, name, color="#abb0b4", opacity=1.0, pattern="Solid", texture=""):
    record = dict(color=color, opacity=opacity, pattern=pattern, texture=texture)
    validate_materials({"materials": {name: record}})
    edit_table(doc, "materials", name, record, "Material appearance")


def brush(doc, key, color):
    material = appearance(doc, key)
    if material is None:
        return QBrush(color)
    c = QColor(color)
    c.setAlphaF(material["opacity"])
    if material["texture"]:
        caches = getattr(doc, "_texture_brushes", None)
        if caches is None:
            caches = doc._texture_brushes = {}
        data = material["texture"]
        if data not in caches:
            image = QImage.fromData(base64.b64decode(data)).scaled(
                128, 128, Qt.AspectRatioMode.KeepAspectRatio
            )
            if len(caches) >= 32:
                caches.pop(next(iter(caches)))
            caches[data] = QBrush(QPixmap.fromImage(image))
        return caches[data]
    patterns = {
        "Solid": Qt.BrushStyle.SolidPattern,
        "Brick": Qt.BrushStyle.CrossPattern,
        "Wood": Qt.BrushStyle.BDiagPattern,
        "Tile": Qt.BrushStyle.DiagCrossPattern,
    }
    return QBrush(c, patterns[material["pattern"]])
