"""Whitelisted architectural actions shared by chat, previews and macros."""

OPS = {
    "planned_room",
    "wall",
    "opening",
    "properties",
    "level",
    "assign_level",
    "building",
    "auto_rooms",
    "build3d",
    "material",
    "boq_rates",
}
FIELDS = {
    "planned_room": {"op","ref","start","width","depth","wall_width","height","name","number","finish","door","dimensions"},
    "wall": {"op", "ref", "start", "end", "width", "height", "material"},
    "opening": {
        "op",
        "ref",
        "wall",
        "station",
        "width",
        "height",
        "sill",
        "type",
        "identifier",
    },
    "properties": {"op", "ids", "values"},
    "level": {"op", "name", "elevation", "height"},
    "assign_level": {"op", "ids", "level"},
    "building": {"op", "ref", "kind", "boundary", "parameters"},
    "auto_rooms": {"op", "level"},
    "build3d": {"op"},
    "material": {"op", "ids", "name"},
    "boq_rates": {"op", "rates", "currency", "waste_percent"},
}


def validate(action):
    from .validation import finite, name

    op = action["op"]
    if set(action) != FIELDS[op]:
        raise ValueError("Invalid " + op + " action fields")
    for key in ("ref", "wall", "name", "level", "material", "identifier", "currency"):
        if key in action:
            name(action[key], key)
    if "ref" in action and not action["ref"].startswith("@"):
        raise ValueError("New object references must start with @")
    for key in ("start", "end"):
        if key in action:
            if not isinstance(action[key], list) or len(action[key]) != 2:
                raise ValueError("Action coordinates need [x,y]")
            for value in action[key]:
                finite(value, "Action coordinate")
    for key in ("width", "depth", "wall_width", "height", "station", "sill", "elevation", "waste_percent"):
        if key in action:
            finite(action[key], key, key in ("width", "depth", "wall_width", "height"))
    if "ids" in action:
        if not isinstance(action["ids"], list) or not 1 <= len(action["ids"]) <= 1000:
            raise ValueError("Choose 1–1000 target IDs")
        for key in action["ids"]:
            name(key, "Target ID")
    if op == "planned_room":
        for k in ("door","dimensions"):
            if type(action[k]) is not bool:raise ValueError("Room options must be boolean")
        for k in ("number","finish"):
            name(action[k],k)
    if op == "properties" and (
        not isinstance(action["values"], dict)
        or not action["values"]
        or len(action["values"]) > 100
    ):
        raise ValueError("Property edits need a values object")
    if op == "building":
        if (
            action["kind"] not in ("slab", "ceiling", "roof", "stair")
            or not isinstance(action["parameters"], dict)
            or len(action["parameters"]) > 30
        ):
            raise ValueError("Invalid building action")
        if action["kind"] != "stair":
            from .building_geometry import validate_profile

            validate_profile(action["boundary"])
        elif action["boundary"] != []:
            raise ValueError("Stairs use position parameters, not a boundary")
    if op == "opening" and action["type"] not in ("door", "window"):
        raise ValueError("Choose door or window")
    if op == "boq_rates":
        from .boq import validate_boq

        validate_boq(
            {
                "rates": action["rates"],
                "settings": {
                    "currency": action["currency"],
                    "waste_percent": action["waste_percent"],
                },
            }
        )


def execute(doc, a, id_map):
    from . import architecture, building, materials, boq, auto_rooms, object_properties
    from .geometry import Point, PolylineEntity
    from .document import AddEntityCommand

    op = a["op"]
    if "ref" in a and a["ref"] in id_map:
        raise ValueError("Duplicate new object reference: " + a["ref"])

    def resolve(key):
        return id_map.get(key, key)

    def targets():
        keys = [resolve(k) for k in a["ids"]]
        if any(doc.find_by_id(k) not in doc.editable_entities() for k in keys):
            raise ValueError("Action target is missing, hidden or locked")
        return keys

    if op == "planned_room":
        from .room_planner import execute as execute_room
        execute_room(doc,a,id_map)
    elif op == "wall":
        entity = architecture.create_wall(
            doc,
            Point(*a["start"]),
            Point(*a["end"]),
            a["width"],
            a["height"],
            a["material"],
        )
        id_map[a["ref"]] = entity.id
    elif op == "opening":
        wall = doc.find_by_id(resolve(a["wall"]))
        if wall is None:
            raise ValueError("Opening host is missing")
        entity = architecture.create_opening(
            doc,
            wall,
            a["station"],
            a["width"],
            a["height"],
            a["type"],
            a["identifier"],
            a["sill"],
        )
        id_map[a["ref"]] = entity.id
    elif op == "properties":
        for key in targets():
            object_properties.apply_values(doc, doc.find_by_id(key), a["values"])
    elif op == "level":
        building.set_level(doc, a["name"], a["elevation"], a["height"])
    elif op == "assign_level":
        building.assign_level(doc, targets(), a["level"])
    elif op == "building":
        boundary = None
        if a["kind"] != "stair":
            boundary = PolylineEntity(
                [Point(*p) for p in a["boundary"]], True, layer=doc.layers.current_layer
            )
            doc.undo_stack.push(
                AddEntityCommand(doc, boundary, "Assisted building boundary")
            )
        entity = building.create_element(doc, a["kind"], boundary, **a["parameters"])
        id_map[a["ref"]] = entity.id
    elif op == "auto_rooms":
        auto_rooms.detect_rooms(doc, a["level"])
    elif op == "build3d":
        architecture.build_wall_solids(doc)
        building.build_models(doc)
    elif op == "material":
        materials.assign(doc, targets(), a["name"])
    elif op == "boq_rates":
        boq.set_rates(doc, a["rates"], a["currency"], a["waste_percent"])


GUIDANCE = """Additional architectural actions (all fields shown are required):
{"op":"wall","ref":"@wall1","start":[0,0],"end":[6000,0],"width":200,"height":3000,"material":"Brick"}
{"op":"opening","ref":"@door1","wall":"@wall1 or existing wall ID","station":1500,"width":900,"height":2100,"sill":0,"type":"door","identifier":"D01"}
{"op":"properties","ids":["existing selected ID"],"values":{"Architecture.height":3600}}
{"op":"level","name":"First","elevation":3300,"height":3000}
{"op":"assign_level","ids":["existing selected ID"],"level":"First"}
{"op":"building","ref":"@slab1","kind":"slab","boundary":[[0,0],[6000,0],[6000,4000],[0,4000]],"parameters":{"thickness":150,"material":"Concrete"}}
Building kinds slab/ceiling/roof/stair. Roofs require a rectangular boundary, roof_type Flat/Shed/Gable/Hip, slope in degrees, overhang and elevation. Stairs require boundary [] and parameters position [x,y], layout Straight/L/U, width, tread, height, steps integer 2–100, landing, rail_height, rails boolean.
{"op":"auto_rooms","level":"Ground"}
{"op":"build3d"}
{"op":"material","ids":["existing selected ID"],"name":"Timber"}
{"op":"boq_rates","rates":{"Wall masonry|Brick|m3":7500},"currency":"INR","waste_percent":5}
Use exact existing IDs from context. @refs can reference a previously created architectural action in the same proposal. Never emit code or invent existing IDs. Property keys for selected objects are supplied in context. Geometry uses drawing units; convert explicit metre/mm instructions correctly. Rates are user-supplied, never invent prices.
"""
