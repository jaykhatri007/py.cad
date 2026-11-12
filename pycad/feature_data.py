"""Versioned feature tables. Geometry remains ordinary editable CAD entities."""
from .linetypes import NAMES as LINETYPE_NAMES


import copy
import math
from .document import SetAttrCommand

AREAS = {
    "office_doors", "office_reviews", "office_linetypes",
    "production",
    "professional",
    "productivity",
    "workflow",
    "groups",
    "architecture",
    "schedules",
    "layer_states",
    "sheets",
    "plot_presets",
    "viewport_overrides",
    "leader_links",
    "solids",
    "macros",
    "views",
    "wall_models",
    "view_links",
    "levels", "building_settings", "level_assignments", "building_elements",
    "building_models", "building_views", "auto_rooms", "materials",
    "material_assignments", "boq",
}


def validate_extensions(value, payload=None):
    if not isinstance(value, dict) or set(value) - AREAS:
        raise ValueError("Invalid feature tables")
    count = 0

    def walk(v, depth=0):
        nonlocal count
        count += 1
        if count > 1500000 or depth > 20:
            raise ValueError("Feature data exceeds nesting or size limit")
        if v is None or type(v) is bool:
            return
        if type(v) in (int, float):
            if not math.isfinite(v) or abs(v) > 1e12:
                raise ValueError("Invalid feature number")
        elif isinstance(v, str):
            if len(v) > 24 * 1024 * 1024:
                raise ValueError("Feature string is too large")
        elif isinstance(v, list):
            for item in v:
                walk(item, depth + 1)
        elif isinstance(v, dict):
            if any(not isinstance(k, str) or len(k) > 255 for k in v):
                raise ValueError("Invalid feature key")
            for item in v.values():
                walk(item, depth + 1)
        else:
            raise ValueError("Feature data must be JSON values")

    walk(value)
    from .production import validate as validate_production
    validate_production(value.get("production",{}),payload)
    from .productivity import validate as validate_productivity
    validate_productivity(value.get("productivity",{}))
    from .pro_data import validate as validate_professional
    validate_professional(value.get("professional",{}))
    from .workflow_data import validate as validate_workflow
    validate_workflow(value.get("workflow",{}))
    for area, table in value.items():
        if not isinstance(table, dict) or len(table) > 1000:
            raise ValueError(f"Invalid {area} table")
    from .office_data import validate_office
    validate_office(value,payload)
    groups = value.get('groups',{})
    for key, members in groups.items():
        if (not isinstance(members,list) or not 2 <= len(members) <= 10000
                or any(not isinstance(v,str) or not v or len(v)>256 for v in members)
                or len(set(members)) != len(members)):
            raise ValueError('Invalid object group')
    from .connected_models import validate_links
    validate_links(value)
    from .building import validate_tables
    validate_tables(value, payload)
    if payload is not None:
        validate_saved_tables(value, payload)
        from .architecture import validate_table

        validate_table(value.get("architecture", {}), payload)
        from .solids import validate_solids

        validate_solids(value.get("solids", {}), payload["layers"])
        from .automation import validate_macros

        validate_macros(value.get("macros", {}))
    return value


def edit_table(doc, area, key, value, description=None):
    if area not in AREAS:
        raise ValueError("Unknown feature area")
    after = copy.deepcopy(doc.extensions)
    table = after.setdefault(area, {})
    if value is None:
        table.pop(key, None)
        if area == "solids":
            after.get("wall_models", {}).pop(key, None)
            after.get("building_models", {}).pop(key, None)
    else:
        table[key] = copy.deepcopy(value)
    validate_extensions(after)
    doc.undo_stack.push(
        SetAttrCommand(
            doc, doc, "extensions", doc.extensions, after, description or f"Edit {area}"
        )
    )


def sync_extensions(doc):
    for entity in doc.entities:
        if entity.kind == "MLEADER":
            links = doc.extensions.get("leader_links", {}).get(entity.id, [])
            from .annotation_links import anchor_point

            for i, link in enumerate(links):
                if link is None or i >= len(entity.leaders):
                    continue
                try:
                    p = anchor_point(doc.find_by_id(link["source"]), link["anchor"])
                    entity.leaders[i][0] = p
                except (ValueError, AttributeError, KeyError):
                    pass
    from .architecture import sync_architecture

    from .building import sync_plans
    sync_plans(doc)
    sync_architecture(doc)
    from .connected_models import sync
    sync(doc)
    from .productivity import sync as sync_productivity
    sync_productivity(doc)


def validate_saved_tables(value, payload):
    from .validation import name, finite, color
    from .sheets import validate_preset

    for key, preset in value.get("plot_presets", {}).items():
        name(key, "Plot preset")
        validate_preset(preset)
    for key, r in value.get("sheets", {}).items():
        name(key, "Sheet name")
        if (
            not isinstance(r, dict)
            or set(r) != {"project", "title", "number", "revision", "author"}
            or any(not isinstance(v, str) or len(v) > 255 for v in r.values())
        ):
            raise ValueError("Invalid title block data")
    for key, r in value.get("schedules", {}).items():
        name(key, "Schedule name")
        if (
            not isinstance(r, dict)
            or set(r) != {"blocks", "group"}
            or not isinstance(r["blocks"], list)
            or len(r["blocks"]) > 1000
            or type(r["group"]) is not bool
        ):
            raise ValueError("Invalid schedule definition")
        for block in r["blocks"]:
            name(block, "Schedule block")
    for key, r in value.get("layer_states", {}).items():
        name(key, "Layer state")
        if (
            not isinstance(r, dict)
            or set(r) != {"layers", "current"}
            or not isinstance(r["layers"], dict)
            or r["current"] not in r["layers"]
            or len(r["layers"]) > 10000
        ):
            raise ValueError("Invalid saved layer state")
        for layer, props in r["layers"].items():
            name(layer, "Saved layer")
            if (
                not isinstance(props, dict)
                or set(props)
                - {
                    "color",
                    "visible",
                    "locked",
                    "frozen",
                    "linetype",
                    "lineweight",
                    "plot",
                }
                or not {"color", "visible", "locked"} <= set(props)
            ):
                raise ValueError("Invalid saved layer properties")
            color(props["color"], False)
            for k in ("visible", "locked", "frozen", "plot"):
                if k in props and type(props[k]) is not bool:
                    raise ValueError("Saved layer flags must be boolean")
            finite(props.get("lineweight", 0.25), "Saved layer weight")
            if not 0 <= props.get("lineweight", 0.25) <= 2.11 or props.get(
                "linetype", "CONTINUOUS"
            ) not in LINETYPE_NAMES:
                raise ValueError("Invalid saved layer plotting property")
    for key, table in value.get("viewport_overrides", {}).items():
        name(key, "Viewport key")
        if not isinstance(table, dict) or len(table) > 10000:
            raise ValueError("Invalid viewport overrides")
        for layer, r in table.items():
            name(layer, "Viewport layer")
            if not isinstance(r, dict) or set(r) - {"visible", "color"}:
                raise ValueError("Invalid viewport layer property")
            if "visible" in r and type(r["visible"]) is not bool:
                raise ValueError("Viewport visibility must be boolean")
            if "color" in r:
                color(r["color"], False)
    for key, links in value.get("leader_links", {}).items():
        name(key, "Leader ID")
        if not isinstance(links, list) or len(links) > 1000:
            raise ValueError("Invalid leader links")
        for r in links:
            if r is None:
                continue
            if (
                not isinstance(r, dict)
                or set(r) != {"source", "anchor"}
                or r["anchor"] not in ("p1", "p2", "point", "center")
            ):
                raise ValueError("Invalid leader source anchor")
            name(r["source"], "Leader source")
    for key, r in value.get("views", {}).items():
        name(key, "Generated view ID")
        if not isinstance(r, dict) or set(r) != {"source", "view", "block"}:
            raise ValueError("Invalid generated view data")
        for k in r:
            name(r[k], "Generated " + k)
