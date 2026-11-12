"""Drawing-linked quantity takeoff, explicit rates, costs and traceable exports."""

import csv
import json
import math
from pathlib import Path
from .units import UNIT_MM


def validate_boq(table):
    from .validation import finite

    if set(table) - {"settings", "rates", "tags"}:
        raise ValueError("Invalid BOQ table")
    settings = table.get("settings", dict(currency="INR", waste_percent=0))
    if (
        not isinstance(settings, dict)
        or set(settings) != {"currency", "waste_percent"}
        or not isinstance(settings["currency"], str)
        or not 1 <= len(settings["currency"]) <= 12
    ):
        raise ValueError("Invalid BOQ settings")
    finite(settings["waste_percent"], "Waste percentage")
    if not 0 <= settings["waste_percent"] <= 100:
        raise ValueError("Waste percentage must be 0–100")
    rates = table.get("rates", {})
    if not isinstance(rates, dict):
        raise ValueError("Invalid rate table")
    for key, rate in rates.items():
        if not isinstance(key, str) or len(key) > 255:
            raise ValueError("Invalid rate key")
        finite(rate, "Unit rate")
        if rate < 0:
            raise ValueError("Rates cannot be negative")
    tags = table.get("tags", {})
    if not isinstance(tags, dict):
        raise ValueError("Invalid measurement tags")
    for key, r in tags.items():
        if (
            not isinstance(r, dict)
            or set(r) != {"description", "material", "measurement", "factor"}
            or r["measurement"] not in ("Length", "Area", "Volume", "Count")
        ):
            raise ValueError("Invalid measurement tag")
        for field in ("description", "material"):
            if not isinstance(r[field], str) or not 1 <= len(r[field]) <= 200:
                raise ValueError("Invalid measurement description")
        finite(r["factor"], "Measurement factor", True)


def rate_key(description, material, unit):
    value = "|".join((description, material, unit))
    if len(value) > 255:
        import hashlib

        return "item-" + hashlib.sha256(value.encode()).hexdigest()
    return value


def report(doc, ids=None, level=None, synchronize=True):
    from .building import level_for
    from .materials import material_name
    from .building_geometry import polygon_area, roof_area, stair_parts
    from .architecture import room_metrics
    from .wall_joining import frames
    from .geometry import LineEntity, PolylineEntity, CircleEntity, ArcEntity, HatchEntity
    from .precision import polyline_measure

    if synchronize:doc.sync_associative()
    if doc.units not in UNIT_MM:
        raise ValueError("Assign physical drawing units before generating BOQ")
    m = UNIT_MM[doc.units] / 1000
    table = doc.extensions.get("boq", {})
    settings = table.get("settings", dict(currency="INR", waste_percent=0))
    rates = table.get("rates", {})
    waste = 1 + settings["waste_percent"] / 100
    selected = set(ids) if ids is not None else None
    items = []
    warnings = []
    measured = set()

    def eligible(key):
        return (
            doc.find_by_id(key) is not None
            and (selected is None or key in selected)
            and (level is None or level_for(doc, key) == level)
        )

    def add(key, description, material, unit, quantity, method):
        measured.add(key)
        rk = rate_key(description, material, unit)
        rate = rates.get(rk)
        specification=doc.extensions.get('workflow',{}).get('takeoff_specs',{}).get(key,'')
        library=doc.extensions.get('workflow',{}).get('rate_library',{}).get(rk)
        if library and library['specification'] and library['specification']!=specification:
            rate=None;warnings.append(key+': specification differs from rate library; left unpriced')
        items.append(
            dict(
                source_id=key,
                level=level_for(doc, key),
                description=description,
                material=material,
                unit=unit,
                quantity=quantity,
                adjusted_quantity=quantity * waste,
                rate=rate,
                amount=None if rate is None else quantity * waste * rate,
                method=method,
                specification=doc.extensions.get("workflow",{}).get("takeoff_specs",{}).get(key,""),
                rate_key=rk,
            )
        )

    architecture = doc.extensions.get("architecture", {})
    wall_frames = frames(doc)
    for key, r in architecture.items():
        if not eligible(key):
            continue
        entity = doc.find_by_id(key)
        scale = abs(entity.scale)
        material = material_name(doc, key) or r.get("finish") or r.get("type", "")
        if r["kind"] == "wall":
            openings = [
                o
                for oid, o in architecture.items()
                if doc.find_by_id(oid) and o["kind"] == "opening" and o["wall"] == key
            ]
            cuts = sum(o["width"] * o["height"] for o in openings) * scale**2
            face = max(0, r["length"] * r["height"] * scale**2 - cuts) * m * m
            volume = (
                max(
                    0,
                    polygon_area(wall_frames[key]["polygon"]) * r["height"] * scale
                    - sum(o["width"] * o["height"] * r["width"] for o in openings)
                    * scale**3,
                )
                * m**3
            )
            # A valid cached kernel volume accounts for joined/cut topology exactly.
            solid = next(
                (
                    k
                    for k, l in doc.extensions.get("wall_models", {}).items()
                    if l["wall"] == key
                ),
                None,
            )
            method = "Joined footprint × height, less hosted openings"
            if (
                solid
                and doc.link_status.get(solid) == "Current"
                and solid in doc.extensions.get("solids", {})
            ):
                volume = doc.extensions["solids"][solid]["volume"] * m**3
                method = "Current linked solid net volume"
            add(key, "Wall masonry", material, "m3", volume, method)
            add(
                key,
                "Wall finish",
                material,
                "m2",
                face * 2,
                "Two centre-line faces less opening areas; reveals/end faces excluded",
            )
        elif r["kind"] == "opening":
            add(
                key,
                r["type"].title(),
                r["identifier"],
                "No.",
                1,
                "One live hosted opening",
            )
        elif r["kind"] == "room":
            _, area, _ = room_metrics(doc, r)
            add(
                key,
                "Room floor finish",
                r["finish"] or "Unspecified",
                "m2",
                area * m * m,
                "Current closed room boundary",
            )
            if (
                getattr(doc, "room_link_status", {})
                .get(key, "Current")
                .startswith("Stale")
            ):
                warnings.append("Room " + r["number"] + " uses its last valid boundary")
    for key, r in doc.extensions.get("building_elements", {}).items():
        if not eligible(key):
            continue
        scale = abs(doc.find_by_id(key).scale)
        material = material_name(doc, key) or r["material"]
        if r["kind"] in ("slab", "ceiling"):
            area = (
                (polygon_area(r["profile"]) - sum(polygon_area(h) for h in r["holes"]))
                * scale**2
                * m
                * m
            )
            add(
                key,
                r["kind"].title() + " material",
                material,
                "m3",
                area * r["thickness"] * scale * m,
                "Net profile area × vertical thickness",
            )
            add(
                key,
                r["kind"].title() + " finish",
                material,
                "m2",
                area,
                "Profile area less defined holes",
            )
        elif r["kind"] == "roof":
            add(
                key,
                "Roof covering",
                material,
                "m2",
                roof_area(r) * scale**2 * m * m,
                "Sloped roof surfaces including overhangs",
            )
        else:
            parts = stair_parts(r)
            volume = (
                sum(
                    polygon_area(poly) * top
                    for poly, top in parts["steps"] + parts["landings"]
                )
                * scale**3
                * m**3
            )
            add(
                key,
                "Solid-step stair material",
                material,
                "m3",
                volume,
                "Solid steps and landings; no waist-slab design inferred",
            )
            if r["rails"]:
                length = (
                    sum(
                        math.dist(a, b) + 2 * r["rail_height"]
                        for a, b in parts["rails"]
                    )
                    * scale
                    * m
                )
                add(
                    key,
                    "Stair railing",
                    "Steel",
                    "m",
                    length,
                    "Handrail segments plus end posts",
                )
    for key, r in table.get("tags", {}).items():
        if not eligible(key) or key in measured:
            continue
        entity = doc.find_by_id(key)
        measurement = r["measurement"]
        quantity = 1
        unit = {"Length": "m", "Area": "m2", "Volume": "m3", "Count": "No."}[
            measurement
        ]
        if measurement == "Length":
            if isinstance(entity, LineEntity):
                quantity = entity.p1.distance_to(entity.p2) * m
            elif isinstance(entity, PolylineEntity):
                quantity = polyline_measure(entity)[0] * m
            elif isinstance(entity, ArcEntity):
                quantity = math.radians((entity.end_angle-entity.start_angle)%360)*entity.radius*m
            elif isinstance(entity, CircleEntity):
                quantity = 2 * math.pi * entity.radius * m
            else:
                warnings.append(key + ": length tag requires line/polyline/circle")
                continue
        elif measurement in ("Area", "Volume"):
            if isinstance(entity, PolylineEntity) and entity.closed:
                quantity = polyline_measure(entity)[1] * m * m
            elif isinstance(entity, HatchEntity):
                from .takeoff_geometry import hatch_area
                try:quantity=hatch_area(entity)*m*m
                except ValueError as ex:
                    warnings.append(key+': '+str(ex));continue
            elif isinstance(entity, CircleEntity):
                quantity = math.pi * entity.radius**2 * m * m
            else:
                warnings.append(key + ": area/volume tag requires a closed boundary")
                continue
        add(
            key,
            r["description"],
            r["material"],
            unit,
            quantity * r["factor"],
            "Tagged " + measurement + "; volume factor is thickness in metres" + ("; hatch area uses polygonal boundary approximation" if isinstance(entity,HatchEntity) else ""),
        )
    generated = {
        r["source"] for r in architecture.values() if r["kind"] == "room"
    } | set(doc.extensions.get("views", {}))
    unmeasured = [
        e.id
        for e in doc.entities
        if eligible(e.id) and e.id not in measured and e.id not in generated
    ]
    groups = {}
    for row in items:
        key = (row["level"], row["description"], row["material"], row["unit"],row.get("specification",""))
        if key not in groups:
            groups[key] = {
                k: v for k, v in row.items() if k not in ("source_id", "method")
            }
            groups[key].update(
                source_ids=[],
                quantity=0,
                adjusted_quantity=0,
                amount=None if row["rate"] is None else 0,
            )
        group = groups[key]
        group["source_ids"].append(row["source_id"])
        group["quantity"] += row["quantity"]
        group["adjusted_quantity"] += row["adjusted_quantity"]
        if row["amount"] is not None:
            group["amount"] += row["amount"]
    if unmeasured:
        warnings.append(
            str(len(unmeasured))
            + " unmeasured objects: assign quantity tags where appropriate"
        )
    return dict(
        currency=settings["currency"],
        waste_percent=settings["waste_percent"],
        items=items,
        summary=list(groups.values()),
        priced_total=sum(r["amount"] or 0 for r in items),
        unpriced_items=sum(r["rate"] is None for r in items),
        unmeasured_ids=unmeasured,
        warnings=warnings,
    )


def set_rates(doc, rates, currency="INR", waste_percent=0):
    from .building import commit_data
    import copy

    after = copy.deepcopy(doc.extensions)
    table = after.setdefault("boq", {})
    table["rates"] = dict(rates)
    table["settings"] = dict(currency=currency, waste_percent=waste_percent)
    validate_boq(table)
    commit_data(doc, after, "BOQ rates and allowances")


def tag(doc, ids, description, material="Unspecified", measurement="Area", factor=1):
    from .building import commit_data
    import copy

    after = copy.deepcopy(doc.extensions)
    tags = after.setdefault("boq", {}).setdefault("tags", {})
    for key in ids:
        if doc.find_by_id(key) not in doc.editable_entities():
            raise ValueError("Tag target is missing, hidden or locked")
        tags[key] = dict(
            description=description,
            material=material,
            measurement=measurement,
            factor=factor,
        )
    validate_boq(after["boq"])
    commit_data(doc, after, "Quantity measurement tags")


def export(doc, path, ids=None, level=None):
    from .native_io import atomic_write

    value = report(doc, ids, level)

    def write(filename):
        if str(path).lower().endswith(".json"):
            Path(filename).write_text(
                json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)
            )
        else:
            fields = [
                "source_id",
                "specification",
                "level",
                "description",
                "material",
                "unit",
                "quantity",
                "adjusted_quantity",
                "rate",
                "amount",
                "method",
            ]
            with open(filename, "w", newline="", encoding="utf-8-sig") as stream:
                writer = csv.DictWriter(
                    stream, fieldnames=fields, extrasaction="ignore"
                )
                writer.writeheader()
                writer.writerows(value["items"])

    atomic_write(path, write)
    return value
