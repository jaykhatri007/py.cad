"""Native building objects, storeys, derived plans and live model sources."""

import copy
import uuid
from .geometry import Point, PolylineEntity, LineEntity, BlockReferenceEntity
from .document import SetAttrCommand
from .architecture import _install
from .feature_data import edit_table


def levels(doc):
    from .units import UNIT_MM

    return doc.extensions.get("levels") or {
        "Ground": dict(
            elevation=0, height=3000 / UNIT_MM.get(doc.units, 1), visible=True
        )
    }


def current_level(doc):
    return (
        doc.extensions.get("building_settings", {})
        .get("current", {})
        .get("level", next(iter(levels(doc))))
    )


def level_for(doc, key):
    r = doc.extensions.get("building_elements", {}).get(key)
    if r:
        return r["level"]
    r = doc.extensions.get("architecture", {}).get(key, {})
    if r.get("kind") == "opening":
        return level_for(doc, r["wall"])
    return (
        doc.extensions.get("level_assignments", {}).get(key, {}).get("level", "Ground")
    )


def elevation(doc, key):
    return levels(doc).get(level_for(doc, key), dict(elevation=0))["elevation"]


def visible(doc, key):
    if not doc.extensions.get('levels'):return True
    if key in doc.extensions.get("views", {}):
        return True
    return levels(doc).get(level_for(doc, key), dict(visible=True))["visible"]


def source_for_solid(doc, key):
    r = doc.extensions.get("building_models", {}).get(key)
    if r:
        return r["source"]
    r = doc.extensions.get("wall_models", {}).get(key)
    return r["wall"] if r else key


def set_level(doc, name, elevation_value=0, height=3000, visible_value=True):
    from .validation import finite, name as check_name

    check_name(name, "Level name")
    finite(elevation_value, "Level elevation")
    finite(height, "Floor height", True)
    if type(visible_value) is not bool:
        raise ValueError("Level visibility must be boolean")
    after = copy.deepcopy(doc.extensions)
    after.setdefault("levels", copy.deepcopy(levels(doc)))[name] = dict(
        elevation=elevation_value, height=height, visible=visible_value
    )
    after.setdefault("building_settings", {})["current"] = {"level": name}
    commit_data(doc, after, "Level settings")


def assign_level(doc, ids, name):
    if name not in levels(doc):
        raise ValueError("Choose an existing level")
    after = copy.deepcopy(doc.extensions)
    after.setdefault("levels", copy.deepcopy(levels(doc)))
    for key in ids:
        entity = doc.find_by_id(key)
        if entity is None or entity not in doc.editable_entities():
            raise ValueError("Level target is missing, hidden or locked")
        record = after.get("building_elements", {}).get(key)
        if record:
            record["level"] = name
        else:
            after.setdefault("level_assignments", {})[key] = {"level": name}
    commit_data(doc, after, "Assign level")


def commit_data(doc, after, title):
    from .native_io import document_to_dict
    from .validation import validate_payload

    payload = document_to_dict(doc)
    payload["extensions"] = after
    validate_payload(payload)
    if after != doc.extensions:
        doc.undo_stack.push(
            SetAttrCommand(doc, doc, "extensions", doc.extensions, after, title)
        )


def validate_tables(value, payload=None):
    from .validation import name, finite

    table = value.get("levels") or {
        "Ground": dict(elevation=0, height=3000, visible=True)
    }
    for key, r in table.items():
        name(key, "Level name")
        if (
            not isinstance(r, dict)
            or set(r) != {"elevation", "height", "visible"}
            or type(r["visible"]) is not bool
        ):
            raise ValueError("Invalid level settings")
        finite(r["elevation"], "Level elevation")
        finite(r["height"], "Floor height", True)
    settings = value.get("building_settings", {})
    if set(settings) - {"current"} or (
        "current" in settings
        and (
            not isinstance(settings["current"], dict)
            or set(settings["current"]) != {"level"}
            or settings["current"]["level"] not in table
        )
    ):
        raise ValueError("Invalid current level")
    for key, r in value.get("level_assignments", {}).items():
        name(key, "Level object")
        if not isinstance(r, dict) or set(r) != {"level"} or r["level"] not in table:
            raise ValueError("Invalid object level")
    for key, r in value.get("building_elements", {}).items():
        name(key, "Building object")
        common = {"kind", "block", "level", "name", "material"}
        fields = {
            "slab": {"profile", "holes", "thickness", "elevation"},
            "ceiling": {"profile", "holes", "thickness", "elevation"},
            "roof": {
                "profile",
                "thickness",
                "elevation",
                "slope",
                "overhang",
                "roof_type",
            },
            "stair": {
                "width",
                "tread",
                "height",
                "steps",
                "layout",
                "landing",
                "rail_height",
                "rails",
            },
        }
        if (
            not isinstance(r, dict)
            or r.get("kind") not in fields
            or set(r) != common | fields[r["kind"]]
        ):
            raise ValueError("Invalid building object definition")
        for field in ("block", "name", "material"):
            name(r[field], field)
        if r["level"] not in table:
            raise ValueError("Building object has no level")
        if r["kind"] == "stair":
            if (
                type(r["steps"]) is not int
                or not 2 <= r["steps"] <= 100
                or r["layout"] not in ("Straight", "L", "U")
                or type(r["rails"]) is not bool
            ):
                raise ValueError("Choose 2–100 steps and Straight/L/U layout")
            for k in ("width", "tread", "height", "landing", "rail_height"):
                finite(r[k], k, True)
        else:
            from .building_geometry import validate_profile

            validate_profile(r["profile"], r.get("holes", []))
            finite(r["thickness"], "Thickness", True)
            finite(r["elevation"], "Object elevation")
            if r["kind"] == "roof":
                if r["roof_type"] not in ("Flat", "Shed", "Gable", "Hip"):
                    raise ValueError("Invalid roof type")
                finite(r["slope"], "Roof slope")
                finite(r["overhang"], "Roof overhang")
                if not 0 <= r["slope"] <= 75 or r["overhang"] < 0:
                    raise ValueError("Roof slope must be 0–75°; overhang nonnegative")
                from .building_geometry import roof_rectangle

                roof_rectangle(r["profile"])
    for key, r in value.get("building_models", {}).items():
        name(key, "Building model")
        if not isinstance(r, dict) or set(r) != {"source", "fingerprint"}:
            raise ValueError("Invalid building model link")
        name(r["source"], "Building model source")
        if (
            not isinstance(r["fingerprint"], str)
            or len(r["fingerprint"]) != 64
            or any(c not in "0123456789abcdef" for c in r["fingerprint"])
        ):
            raise ValueError("Invalid building fingerprint")
    from .building_views import validate_views

    validate_views(value.get("building_views", {}))
    from .auto_rooms import validate_rooms

    validate_rooms(value.get("auto_rooms", {}), table)
    from .materials import validate_materials

    validate_materials(value)
    from .boq import validate_boq

    validate_boq(value.get("boq", {}))
    if payload:
        active = {r["data"]["id"]: r for r in payload.get("entities", [])}
        for area in ("building_elements", "building_views"):
            for key, record in value.get(area, {}).items():
                entity = active.get(key)
                if entity is not None and (
                    entity["kind"] != "INSERT"
                    or entity["data"].get("block_name") != record["block"]
                    or record["block"] not in payload.get("blocks", {})
                ):
                    raise ValueError(
                        "Building source/view block does not match its definition"
                    )


def create_element(doc, kind, boundary=None, **options):
    from .building_geometry import validate_profile
    from .units import UNIT_MM

    mm = 1 / UNIT_MM.get(doc.units, 1)
    level = options.pop("level", current_level(doc))
    record = dict(
        kind=kind,
        block="BUILDING_" + uuid.uuid4().hex[:10],
        level=level,
        name=options.pop("name", kind.title()),
        material=options.pop("material", "Concrete"),
    )
    if kind == "stair":
        position = options.pop("position", [0, 0])
        record.update(
            width=1000 * mm,
            tread=280 * mm,
            height=levels(doc)[level]["height"],
            steps=18,
            layout="Straight",
            landing=1000 * mm,
            rail_height=900 * mm,
            rails=True,
        )
    else:
        if (
            not isinstance(boundary, PolylineEntity)
            or not boundary.closed
            or any(boundary.bulges)
        ):
            raise ValueError("Select a closed straight-edge boundary")
        if boundary not in doc.editable_entities():
            raise ValueError("Boundary must be editable")
        position = [boundary.points[0].x, boundary.points[0].y]
        profile = [[p.x - position[0], p.y - position[1]] for p in boundary.points]
        validate_profile(profile, options.get("holes", []))
        record.update(profile=profile, thickness=150 * mm, elevation=0)
        if kind in ("slab", "ceiling"):
            record["holes"] = []
            if kind == "ceiling":
                record["elevation"] = levels(doc)[level]["height"]
        elif kind == "roof":
            record.update(
                slope=25,
                overhang=300 * mm,
                roof_type="Gable",
                elevation=levels(doc)[level]["height"],
            )
        else:
            raise ValueError("Choose slab, ceiling, roof or stair")
    record.update(options)
    prospective = copy.deepcopy(doc.extensions)
    prospective.setdefault("levels", copy.deepcopy(levels(doc)))
    prospective.setdefault("building_elements", {})["pending"] = record
    validate_tables(prospective)
    from .validation import finite

    if not isinstance(position, (list, tuple)) or len(position) != 2:
        raise ValueError("Position needs x,y")
    for x in position:
        finite(x, "Building position")
    doc.undo_stack.beginMacro("Create " + kind)
    try:
        if not doc.extensions.get("levels"):
            commit_data(
                doc,
                {**doc.extensions, "levels": copy.deepcopy(levels(doc))},
                "Initial level",
            )
        entity = _install(doc, record["block"], [], Point(*position))
        edit_table(doc, "building_elements", entity.id, record, "Building parameters")
    finally:
        doc.undo_stack.endMacro()
    return entity


def plan_paths(record, layer):
    from .building_geometry import roof_surfaces, stair_parts

    if record["kind"] == "stair":
        parts = stair_parts(record)
        return [
            PolylineEntity([Point(x, y) for x, y in poly], True, layer=layer)
            for poly, _ in parts["steps"] + parts["landings"]
        ]
    points = record["profile"]
    paths = [PolylineEntity([Point(*p) for p in points], True, layer=layer)]
    paths.extend(
        PolylineEntity([Point(*p) for p in hole], True, layer=layer)
        for hole in record.get("holes", [])
    )
    if record["kind"] == "roof":
        seen = set()
        for face in roof_surfaces(record):
            for a, b in zip(face, face[1:] + face[:1]):
                pair = tuple(sorted((tuple(a[:2]), tuple(b[:2]))))
                if pair in seen or pair[0] == pair[1]:
                    continue
                seen.add(pair)
                paths.append(LineEntity(Point(*a[:2]), Point(*b[:2]), layer=layer))
    return paths


def sync_plans(doc):
    for key, r in doc.extensions.get("building_elements", {}).items():
        entity = doc.find_by_id(key)
        if not isinstance(entity, BlockReferenceEntity) or r["block"] not in doc.blocks:
            continue
        paths = plan_paths(r, entity.layer)
        for i, path in enumerate(paths):
            path.id = uuid.uuid5(uuid.NAMESPACE_URL, key + "/building/" + str(i)).hex
        doc.blocks[r["block"]].entities = paths
    from .auto_rooms import sync_rooms

    sync_rooms(doc)


def model_signature(doc, key):
    from .connected_models import digest

    entity = doc.find_by_id(key)
    r = doc.extensions.get("building_elements", {}).get(key)
    if not isinstance(entity, BlockReferenceEntity) or r is None:
        raise ValueError("Source building object is missing")
    return digest(
        dict(
            record={
                k: v
                for k, v in r.items()
                if k not in ("name", "material", "block", "level")
            },
            level=elevation(doc, key),
            position=list(entity.insertion_point.as_tuple()),
            rotation=entity.rotation,
            scale=entity.scale,
            mirrored=entity.mirrored,
        )
    )


def build_models(doc, ids=None):
    from .building_geometry import make_shape
    from .solids import shape_record

    targets = (
        list(ids)
        if ids is not None
        else [
            k for k in doc.extensions.get("building_elements", {}) if doc.find_by_id(k)
        ]
    )
    before = doc.extensions
    after = copy.deepcopy(before)
    table = after.setdefault("solids", {})
    links = after.setdefault("building_models", {})
    keys = []
    for source in targets:
        r = doc.extensions.get("building_elements", {}).get(source)
        entity = doc.find_by_id(source)
        if r is None or entity is None:
            raise ValueError("Select existing building objects")
        key = next(
            (k for k, link in links.items() if link["source"] == source),
            uuid.uuid4().hex,
        )
        fingerprint = model_signature(doc, source)
        if links.get(key, {}).get("fingerprint") != fingerprint or key not in table:
            table[key] = shape_record(
                make_shape(doc, source), r["name"], entity.layer, "extrude"
            )
        links[key] = dict(source=source, fingerprint=fingerprint)
        keys.append(key)
    if after != before:
        commit_data(doc, after, "Build live building models")
    return keys


def sync_models(doc):
    from .connected_models import _cache
    from .building_geometry import make_shape
    from .solids import shape_record

    links = doc.extensions.get("building_models", {})
    if not links:
        return
    table = doc.extensions.setdefault("solids", {})
    for key, link in links.items():
        old = table.get(key)
        if old:
            _cache(doc, "building", key, link["fingerprint"], old)
        if not doc.find_by_id(link["source"]):
            table.pop(key, None)
            doc.link_status[key] = "Source building object missing; model hidden"
            continue
        try:
            signature = model_signature(doc, link["source"])
            if signature != link["fingerprint"] or old is None:
                record = _cache(doc, "building", key, signature)
                if record is None:
                    r = doc.extensions["building_elements"][link["source"]]
                    record = shape_record(
                        make_shape(doc, link["source"]),
                        old["name"] if old else r["name"],
                        doc.find_by_id(link["source"]).layer,
                        "extrude",
                    )
                table[key] = record
                link["fingerprint"] = signature
                _cache(doc, "building", key, signature, record)
            table[key]["layer"] = doc.find_by_id(link["source"]).layer
            doc.link_status[key] = "Current"
        except Exception as ex:
            doc.link_status[key] = "Stale building model: " + str(ex)
