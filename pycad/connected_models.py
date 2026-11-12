"""Persistent source links with last-valid geometry and deterministic Undo caches."""

import copy
import hashlib
import json
import re
import uuid
from .geometry import BlockReferenceEntity
from .document import SetAttrCommand
from .wall_joining import frames, world_point


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def validate_links(value):
    from .validation import name, finite

    for key, r in value.get("wall_models", {}).items():
        name(key, "Wall model ID")
        if not isinstance(r, dict) or set(r) != {"wall", "fingerprint"}:
            raise ValueError("Invalid live wall model link")
        name(r["wall"], "Wall source")
        if not isinstance(r["fingerprint"], str) or not re.fullmatch(
            "[0-9a-f]{64}", r["fingerprint"]
        ):
            raise ValueError("Invalid wall source fingerprint")
    for key, r in value.get("view_links", {}).items():
        name(key, "Linked view ID")
        if not isinstance(r, dict) or set(r) != {
            "source",
            "type",
            "axis",
            "offset",
            "view",
            "fingerprint",
        }:
            raise ValueError("Invalid linked view definition")
        name(r["source"], "View source")
        if (
            r["type"] not in ("section", "elevation")
            or r["axis"] not in ("X", "Y", "Z")
            or r["view"] not in ("Top", "Front", "Right")
        ):
            raise ValueError("Invalid linked view plane")
        finite(r["offset"], "Section offset")
        if not isinstance(r["fingerprint"], str) or not re.fullmatch(
            "[0-9a-f]{64}", r["fingerprint"]
        ):
            raise ValueError("Invalid view source fingerprint")


def wall_signature(doc, key, f):
    openings = sorted(
        [
            tuple(r[field] for field in ("station", "width", "height", "sill"))
            for oid, r in doc.extensions.get("architecture", {}).items()
            if r["kind"] == "opening" and r["wall"] == key and doc.find_by_id(oid)
        ]
    )
    data = dict(
            polygon=f["polygon"],
            height=f["record"]["height"] * abs(f["entity"].scale),
            openings=openings,
            scale=f["entity"].scale,
            rotation=f["entity"].rotation,
            mirrored=f["entity"].mirrored,
            origin=f["a"],
        )
    from .building import elevation
    z = elevation(doc, key)
    if z:
        data['elevation'] = z
    return digest(data)


def wall_shape(doc, key, f):
    from .solids import kernel

    cq = kernel()
    wire = cq.Wire.makePolygon(
        [cq.Vector(x, y, 0) for x, y in f["polygon"]], close=True
    )
    scale = abs(f["entity"].scale)
    shape = cq.Solid.extrudeLinear(wire, [], (0, 0, f["record"]["height"] * scale))
    wall = f["entity"]
    for oid, r in doc.extensions.get("architecture", {}).items():
        if r["kind"] != "opening" or r["wall"] != key or not doc.find_by_id(oid):
            continue
        cut = (
            cq.Workplane("XY")
            .box(
                r["width"] * scale,
                f["h"] * 4,
                r["height"] * scale,
                centered=(True, True, False),
            )
            .val()
        )
        x, y = world_point(wall, r["station"], 0)
        cut = cut.rotate((0, 0, 0), (0, 0, 1), wall.rotation).translate(
            (x, y, r["sill"] * scale)
        )
        shape = shape.cut(cut)
    if not shape.isValid() or not shape.Solids() or shape.Volume() <= 1e-12:
        raise ValueError("The current wall parameters do not produce a closed solid")
    from .building import elevation
    return shape.translate((0, 0, elevation(doc, key)))


def _cache(doc, kind, key, signature, geometry=None):
    cache = getattr(doc, "_connected_cache", None)
    if cache is None:
        cache = doc._connected_cache = {}
    history = cache.setdefault((kind, key), {})
    if geometry is not None:
        history[signature] = copy.deepcopy(geometry)
        # Preserve the first snapshot and recent edits, keeping memory bounded.
        if len(history) > 24:
            del history[list(history)[1]]
    return copy.deepcopy(history.get(signature))


def build_models(doc, wall_ids=None):
    from .solids import shape_record

    wall_frames = frames(doc)
    chosen = [key for key in wall_frames if wall_ids is None or key in wall_ids]
    if not chosen:
        raise ValueError("Drawing has no live architectural walls")
    after = copy.deepcopy(doc.extensions)
    models = after.setdefault("wall_models", {})
    solids = after.setdefault("solids", {})
    keys = []
    # Preflight every shape before changing the drawing or its Undo stack.
    for wall_key in chosen:
        f = wall_frames[wall_key]
        if doc.layers.is_locked(f["entity"].layer):
            raise ValueError("Unlock the wall layer before generating 3D")
        key = (
            next((k for k, link in models.items() if link["wall"] == wall_key), None)
            or uuid.uuid4().hex
        )
        title = solids.get(key, {}).get(
            "name", "Wall solid " + str(chosen.index(wall_key) + 1)
        )
        record = shape_record(
            wall_shape(doc, wall_key, f), title, f["entity"].layer, "extrude"
        )
        signature = wall_signature(doc, wall_key, f)
        solids[key] = record
        models[key] = dict(wall=wall_key, fingerprint=signature)
        keys.append(key)
    from .feature_data import validate_extensions

    validate_extensions(after)
    doc.undo_stack.push(
        SetAttrCommand(
            doc, doc, "extensions", doc.extensions, after, "Link architectural 3D walls"
        )
    )
    return keys


def view_signature(doc, link):
    source = doc.extensions.get("solids", {}).get(link["source"])
    if source:
        source_data = source["sha256"]
    else:
        source_data = next(
            (r for r in doc.extrusions if r["id"] == link["source"]), None
        )
    if source_data is None:
        raise ValueError("The source solid is missing")
    return digest(
        [source_data, link["type"], link["axis"], link["offset"], link["view"]]
    )


def make_view_paths(doc, link):
    from .solids import section_paths, elevation_paths

    if link["type"] == "section":
        return section_paths(doc, link["source"], link["axis"], link["offset"])
    return elevation_paths(doc, link["source"], link["view"])


def _sync_models(doc):
    from .solids import shape_record

    wall_frames = frames(doc)
    table = doc.extensions.get("solids", {})
    for key, link in doc.extensions.get("wall_models", {}).items():
        old = table.get(key)
        if old is not None:
            _cache(doc, "model", key, link["fingerprint"], old)
        f = wall_frames.get(link["wall"])
        if f is None:
            table.pop(key, None)
            doc.link_status[key] = "Source wall missing; model hidden"
            continue
        try:
            signature = wall_signature(doc, link["wall"], f)
            if signature == link["fingerprint"] and old is not None:
                old["layer"] = f["entity"].layer
                doc.link_status[key] = "Current"
                continue
            record = _cache(doc, "model", key, signature)
            if record is None:
                record = shape_record(
                    wall_shape(doc, link["wall"], f),
                    old["name"] if old else "Wall solid",
                    f["entity"].layer,
                    "extrude",
                )
            elif old:
                record["name"] = old["name"]
            record["layer"] = f["entity"].layer
            table[key] = record
            link["fingerprint"] = signature
            _cache(doc, "model", key, signature, record)
            doc.link_status[key] = "Current"
        except Exception as ex:
            doc.link_status[key] = "Stale wall model: " + str(ex)


def _sync_views(doc):
    actual = getattr(doc, "_view_actual_signatures", None)
    if actual is None:
        actual = doc._view_actual_signatures = {}
    for key, link in doc.extensions.get("view_links", {}).items():
        insert = doc.find_by_id(key)
        record = doc.extensions.get("views", {}).get(key)
        block = doc.blocks.get(record["block"]) if record else None
        if not isinstance(insert, BlockReferenceEntity) or block is None:
            continue
        current = actual.setdefault(key, link["fingerprint"])
        _cache(doc, "view", key, current, block.entities)
        try:
            if (
                link["source"] in doc.link_status
                and doc.link_status[link["source"]] != "Current"
            ):
                raise ValueError(doc.link_status[link["source"]])
            signature = view_signature(doc, link)
            if signature != current:
                paths = _cache(doc, "view", key, signature)
                if paths is None:
                    paths = make_view_paths(doc, link)
                    for i, path in enumerate(paths):
                        path.id = uuid.uuid5(
                            uuid.NAMESPACE_URL, key + "/view/" + str(i)
                        ).hex
                        path.layer = insert.layer
                block.entities = paths
                actual[key] = signature
                _cache(doc, "view", key, signature, paths)
            link["fingerprint"] = signature
            doc.link_status[key] = (
                "Current" if block.entities else "Current; section has no intersection"
            )
        except Exception as ex:
            doc.link_status[key] = "Stale view: " + str(ex)


def sync(doc):
    if getattr(doc, "_syncing_connected", False):
        return
    doc._syncing_connected = True
    doc.link_status = {}
    try:
        _sync_models(doc)
        from .building import sync_models
        sync_models(doc)
        _sync_views(doc)
        from .building_views import sync as sync_building_views
        sync_building_views(doc)
    finally:
        doc._syncing_connected = False


def refresh(mw):
    mw.document.sync_associative()
    mw.refresh_document_ui()
    failures = [v for v in mw.document.link_status.values() if v.startswith("Stale")]
    mw.command_history.appendPlainText(
        "Linked models/views refreshed" if not failures else "\n".join(failures)
    )


def migrate_legacy_views(doc):
    """Old views already carry source IDs; activate only recognised definitions."""
    sources = set(doc.extensions.get("solids", {})) | {r["id"] for r in doc.extrusions}
    for key, record in doc.extensions.get("views", {}).items():
        if not doc.find_by_id(key) or record["source"] not in sources:
            continue
        section = re.fullmatch(r"Section ([XYZ])=([-+0-9.eE]+)", record["view"])
        if section is None and record["view"] not in ("Top", "Front", "Right"):
            continue
        link = dict(
            source=record["source"],
            type="section" if section else "elevation",
            axis=section.group(1)
            if section
            else {"Top": "Z", "Front": "Y", "Right": "X"}[record["view"]],
            offset=float(section.group(2)) if section else 0,
            view="Front" if section else record["view"],
            fingerprint="0" * 64,
        )
        if math_is_finite(link["offset"]):
            doc.extensions.setdefault("view_links", {}).setdefault(key, link)


def math_is_finite(value):
    import math

    return math.isfinite(value) and abs(value) <= 1e12


def require_current_plot_views(doc, spaces):
    """Never publish a last-valid stale view when it lies inside a plotted sheet."""
    from .layers_plus import overrides

    for key in set(doc.extensions.get("view_links", {})) | set(doc.extensions.get("building_views", {})):
        if not getattr(doc, "link_status", {}).get(key, "").startswith("Stale"):
            continue
        entity = doc.find_by_id(key)
        if (
            entity is None
            or not doc.layers.is_visible(entity.layer)
            or not doc.layers.layers[entity.layer].get("plot", True)
        ):
            continue
        x0, y0, x1, y1 = entity.bbox()
        for space in spaces:
            visible = space == "Model"
            if space != "Model":
                for i, viewport in enumerate(doc.layouts[space].viewports):
                    if (
                        not overrides(doc, space, i)
                        .get(entity.layer, {})
                        .get("visible", True)
                    ):
                        continue
                    dx, dy = (
                        viewport.width / viewport.scale / 2,
                        viewport.height / viewport.scale / 2,
                    )
                    if (
                        x1 >= viewport.center.x - dx
                        and x0 <= viewport.center.x + dx
                        and y1 >= viewport.center.y - dy
                        and y0 <= viewport.center.y + dy
                    ):
                        visible = True
            if visible:
                raise ValueError(
                    "Cannot publish stale linked view: refresh its source or explicitly detach the view. "
                    + doc.link_status[key]
                )
