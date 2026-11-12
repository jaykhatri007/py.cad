"""Versioned, non-executable native project format and atomic file writes.

Unlike DXF interchange, this preserves PyCAD IDs and associative links. Runtime
caches, selection, undo history and file paths used by the OS are never executed.
"""

import copy
import json
import math
import os
import tempfile
from pathlib import Path

from .geometry import (
    Point,
    LineEntity,
    CircleEntity,
    ArcEntity,
    PointEntity,
    EllipseEntity,
    RayEntity,
    XLineEntity,
    PolylineEntity,
    RectangleEntity,
    TextEntity,
    DimensionEntity,
    HatchEntity,
    SplineEntity,
    BlockDefinition,
    BlockReferenceEntity,
)
from .layout import Layout, Viewport
from .validation import validate_payload, MAX_FILE_BYTES
from .curved_dimensions import CurvedDimensionEntity
from .ordinate_dimensions import OrdinateDimensionEntity
from .mleaders import MultileaderEntity

FORMAT = "PyCAD"
SCHEMA_VERSION = 18
ENTITY_TYPES = {
    c.kind: c
    for c in (
        LineEntity,
        CircleEntity,
        ArcEntity,
        PointEntity,
        EllipseEntity,
        RayEntity,
        XLineEntity,
        PolylineEntity,
        RectangleEntity,
        TextEntity,
        DimensionEntity,
        CurvedDimensionEntity,
        OrdinateDimensionEntity,
        MultileaderEntity,
        HatchEntity,
        SplineEntity,
        BlockReferenceEntity,
    )
}


def _encode(value):
    if isinstance(value, Point):
        return {"point": [value.x, value.y]}
    if isinstance(value, dict):
        return {k: _encode(v) for k,v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_encode(v) for v in value]
    return value


def _decode(value):
    if isinstance(value, dict):
        if set(value) != {"point"} or not isinstance(value["point"],list):
            return {k: _decode(v) for k,v in value.items()}
        if len(value["point"]) != 2:
            raise ValueError("Invalid point in project")
        x, y = value["point"]
        if not all(isinstance(v, (float, int)) and math.isfinite(v) for v in (x, y)):
            raise ValueError("Coordinates must be finite numbers")
        return Point(x, y)
    if isinstance(value, list):
        return [_decode(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Non-finite value in project")
    return value


def entity_to_dict(entity):
    return {
        "kind": entity.kind,
        "data": {
            k: _encode(v)
            for k, v in vars(entity).items()
            if k not in ("selected", "resolved_entities", "_mleader_style", "_text_style", "_display_stamp", "_display_cache_token", "_pick_index", "_pick_index_key", "_pick_unbounded", "_snap_index", "_snap_index_key", "_display_index", "_display_index_key", "_display_unbounded")
        },
    }


def entity_from_dict(record):
    cls = ENTITY_TYPES.get(record.get("kind"))
    if cls is None:
        raise ValueError(f"Unsupported entity type: {record.get('kind')}")
    data = {k: _decode(v) for k, v in record["data"].items()}
    entity_id = data.pop("id")
    if not isinstance(entity_id, str) or not entity_id:
        raise ValueError("Invalid entity ID")
    # Constructors reject unexpected fields instead of assigning arbitrary attributes.
    common = {k: data.pop(k) for k in ("layer", "color", "linetype")}
    common.update(transparency=data.pop("transparency",0.0),hyperlink=data.pop("hyperlink",""))
    if cls is RectangleEntity:
        pts = data.pop("points")
        data.pop("closed")
        bulges = data.pop("bulges", None)
        width = data.pop("width",0.0)
        if len(pts) != 4 or data:
            raise ValueError("Invalid rectangle")
        entity = RectangleEntity(pts[0], pts[2], width=width, **common)
        entity.points = pts  # rotated/grip-edited rectangles need their actual vertices
        entity.bulges = bulges or [0.0]*len(pts)
    else:
        entity = cls(**data, **common)
    for attr in ("radius", "major_radius", "minor_radius", "height", "spacing"):
        value = getattr(entity, attr, None)
        if value is not None and (not math.isfinite(value) or value <= 0):
            raise ValueError(f"Invalid {attr}")
    if isinstance(entity, (PolylineEntity, SplineEntity)) and len(entity.points) < 2:
        raise ValueError("A curve requires at least two vertices")
    if isinstance(entity, HatchEntity) and len(entity.boundary) < 3:
        raise ValueError("A hatch requires at least three boundary vertices")
    entity.id = entity_id
    return entity


def document_to_dict(document):
    return {
        "format": FORMAT,
        "schema_version": SCHEMA_VERSION if any(document.extensions.get(k) for k in ("office_doors","office_reviews","office_linetypes")) else 17,
        "units": document.units,
        "unit_settings": copy.deepcopy(document.unit_settings),
        "dimstyles": copy.deepcopy(document.dimstyles),
        "current_dimstyle": document.current_dimstyle,
        "mleaderstyles": copy.deepcopy(document.mleaderstyles),
        "current_mleaderstyle": document.current_mleaderstyle,
        'textstyles': copy.deepcopy(document.textstyles),
        'current_textstyle': document.current_textstyle,
        "extrusions": copy.deepcopy(document.extrusions),
        "extensions": copy.deepcopy(document.extensions),
        "underlays": copy.deepcopy(document.underlays),
        "constraints": copy.deepcopy(document.constraints),
        "constraint_settings": copy.deepcopy(document.constraint_settings),
        "cad_standard": copy.deepcopy(document.cad_standard),
        "current_layer": document.layers.current_layer,
        "current_linetype": document.current_linetype,
        "linetype_scale": document.linetype_scale,
        "source_archive": copy.deepcopy(document.source_archive),
        "layers": copy.deepcopy(document.layers.layers),
        "entities": [entity_to_dict(e) for e in document.entities],
        "blocks": {
            name: {
                "entities": [entity_to_dict(e) for e in b.entities],
                "source_filepath": b.source_filepath,
                "source_scale": b.source_scale,
                "attributes": copy.deepcopy(b.attributes),
            }
            for name, b in document.blocks.items()
        },
        "layouts": {
            name: {
                "page_width": layout.page_width,
                "page_height": layout.page_height,
                "viewports": [
                    {
                        "x": v.x,
                        "y": v.y,
                        "width": v.width,
                        "height": v.height,
                        "center": [v.center.x, v.center.y],
                        "scale": v.scale,
                    }
                    for v in layout.viewports
                ],
            }
            for name, layout in document.layouts.items()
        },
        "import_warnings": list(document.import_warnings),
        "source_filepath": document.source_filepath,
    }


def document_from_dict(data):
    validate_payload(data)
    return _document_from_validated_dict(data)


def _document_from_validated_dict(data):
    """Construct an already validated in-process payload; never a public reader.

    The isolated import worker also supplies such a payload via its private,
    hash-checked result file. Public native readers still validate their input.
    """
    from .document import Document

    if data.get("format") != FORMAT or data.get("schema_version") not in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, SCHEMA_VERSION):
        raise ValueError("Unsupported PY.cad project format/version")
    doc = Document()
    doc.units = data.get("units", "mm")
    from .units import DEFAULT_SETTINGS as UNIT_DEFAULTS
    doc.unit_settings = copy.deepcopy(data.get("unit_settings", UNIT_DEFAULTS))
    if doc.units not in ("mm", "cm", "m", "in", "ft", "unitless"):
        raise ValueError("Unsupported drawing units")
    from .layers import LAYER_DEFAULTS
    doc.layers.layers = {name: {**LAYER_DEFAULTS, **props} for name, props in data["layers"].items()}
    doc.dimstyles = copy.deepcopy(data.get("dimstyles", doc.dimstyles))
    doc.current_dimstyle = data.get("current_dimstyle", "Standard")
    doc.mleaderstyles = copy.deepcopy(data.get("mleaderstyles",doc.mleaderstyles))
    doc.current_mleaderstyle = data.get("current_mleaderstyle","Standard")
    doc.textstyles = copy.deepcopy(data.get('textstyles', doc.textstyles))
    doc.current_textstyle = data.get('current_textstyle', 'Standard')
    doc.extrusions = copy.deepcopy(data.get("extrusions", []))
    doc.extensions = copy.deepcopy(data.get("extensions", {}))
    doc.underlays = copy.deepcopy(data.get("underlays", []))
    doc.constraints = copy.deepcopy(data.get("constraints", []))
    from .constraints import DEFAULT_SETTINGS
    doc.constraint_settings = copy.deepcopy(data.get("constraint_settings", DEFAULT_SETTINGS))
    doc.cad_standard = copy.deepcopy(data.get("cad_standard"))
    if "0" not in doc.layers.layers:
        raise ValueError("Layer 0 is required")
    for name, props in doc.layers.layers.items():
        if not isinstance(name, str) or not isinstance(props.get("color"), str):
            raise ValueError("Invalid layer record")
    doc.layers.current_layer = data.get("current_layer", "0")
    doc.current_linetype = data.get("current_linetype", "CONTINUOUS")
    doc.linetype_scale = data.get('linetype_scale',1.0)
    doc.source_archive = copy.deepcopy(data.get("source_archive"))
    doc.entities = [entity_from_dict(e) for e in data["entities"]]
    ids = [e.id for e in doc.entities]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate entity IDs")
    for name, b in data["blocks"].items():
        doc.blocks[name] = BlockDefinition(
            name, [entity_from_dict(e) for e in b["entities"]], b.get("source_filepath"), b.get("source_scale", 1.0), b.get("attributes", [])
        )

    # Check allocation work before creating any transformed copies. The single
    # memoized rebuild in sync_associative below resolves the graph once.
    from .block_budget import check_expansion
    check_expansion(doc.blocks, doc.entities)
    for name, record in data["layouts"].items():
        if name == "Model":
            raise ValueError("Model is reserved")
        layout = Layout(name, record["page_width"], record["page_height"])
        for v in record["viewports"]:
            if any(
                not math.isfinite(v[k]) or v[k] <= 0
                for k in ("width", "height", "scale")
            ):
                raise ValueError("Viewport dimensions and scale must be positive")
            layout.viewports.append(
                Viewport(
                    v["x"],
                    v["y"],
                    v["width"],
                    v["height"],
                    Point(*v["center"]),
                    v["scale"],
                )
            )
        doc.layouts[name] = layout
    doc.import_warnings = list(data.get("import_warnings", []))
    doc.source_filepath = data.get("source_filepath")
    for e in doc.entities:
        if e.layer not in doc.layers.layers:
            raise ValueError(f"Missing layer: {e.layer}")
        if isinstance(e, BlockReferenceEntity) and e.block_name not in doc.blocks:
            raise ValueError(f"Missing block: {e.block_name}")
    if data['schema_version'] <= 10:
        from .connected_models import migrate_legacy_views
        migrate_legacy_views(doc)
    doc.sync_associative()
    if doc.constraints:
        from .constraints import solve
        doc.constraint_report = solve(doc, check_only=True)
    doc.mark_saved()
    return doc


def atomic_write(path, writer):
    """Install the completed sibling temp file; failed writes leave the old file intact."""
    path = Path(path).absolute()
    fd, temporary = tempfile.mkstemp(
        prefix=f".{path.stem}-", suffix=path.suffix, dir=path.parent
    )
    os.close(fd)
    try:
        writer(temporary)
        # Windows _commit/FlushFileBuffers needs a writable descriptor.
        # A read-only handle can raise EBADF while opening DWG/DXF via the worker.
        with open(temporary, "r+b") as stream:
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def parse_payload(text):
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:raise ValueError(f"Duplicate JSON key: {key}")
            result[key]=value
        return result
    try:
        data=json.loads(text,object_pairs_hook=pairs,parse_constant=lambda v: (_ for _ in ()).throw(ValueError(f"Invalid numeric value: {v}")))
        return validate_payload(data)
    except (KeyError,TypeError,RecursionError) as ex:
        raise ValueError("Invalid project structure") from ex


def save_project(document, filepath, backup=True):
    from .block_budget import check_expansion
    check_expansion(document.blocks, document.entities)
    if document.constraints:
        from .constraints import solve
        solve(document,check_only=True)
    document.sync_associative()
    data = document_to_dict(document)
    validate_payload(data)
    payload=json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)
    path=Path(filepath)
    if backup and path.exists():
        old=path.read_bytes()
        try:
            parse_payload(old.decode("utf-8"))
        except (ValueError,UnicodeError):
            pass  # Do not replace a good backup with corrupt current data.
        else:
            atomic_write(str(path)+".bak",lambda p:Path(p).write_bytes(old))
    atomic_write(path,lambda p:Path(p).write_text(payload,encoding="utf-8"))


def load_project(filepath):
    data=parse_payload(Path(filepath).read_text(encoding="utf-8"))
    document=_document_from_validated_dict(data)
    document.filepath=str(filepath)
    return document
