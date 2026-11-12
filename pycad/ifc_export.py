"""IFC4 export of typed building objects with levels, materials and quantities."""

import numpy as np
from .units import UNIT_MM


def export(doc, path):
    try:
        import ifcopenshell
        import ifcopenshell.api as api
    except ImportError as ex:
        raise ValueError(
            "Install requirements-bim.txt in the PY.cad interpreter to export IFC"
        ) from ex
    from . import building, architecture, materials, boq, solids
    from .connected_models import wall_shape
    from .wall_joining import frames
    from .native_io import atomic_write

    doc.sync_associative()
    if doc.units not in UNIT_MM:
        raise ValueError("IFC needs physical drawing units")
    metre = UNIT_MM[doc.units] / 1000
    model = ifcopenshell.file(schema="IFC4")

    def run(action, **kwargs):
        return api.run(action, model, **kwargs)

    project = run("root.create_entity", ifc_class="IfcProject", name="PY.cad Building")
    units = [
        run("unit.add_si_unit", unit_type=t)
        for t in ("LENGTHUNIT", "AREAUNIT", "VOLUMEUNIT")
    ]
    run("unit.assign_unit", units=units)
    context = run("context.add_context", context_type="Model")
    body = run(
        "context.add_context",
        context_type="Model",
        context_identifier="Body",
        target_view="MODEL_VIEW",
        parent=context,
    )
    site = run("root.create_entity", ifc_class="IfcSite", name="Site")
    bld = run("root.create_entity", ifc_class="IfcBuilding", name="Building")
    run("aggregate.assign_object", products=[site], relating_object=project)
    run("aggregate.assign_object", products=[bld], relating_object=site)
    storeys = {}
    for name, r in building.levels(doc).items():
        storey = run("root.create_entity", ifc_class="IfcBuildingStorey", name=name)
        storey.Elevation = r["elevation"] * metre
        run("aggregate.assign_object", products=[storey], relating_object=bld)
        matrix = np.eye(4)
        matrix[2, 3] = r["elevation"] * metre
        run("geometry.edit_object_placement", product=storey, matrix=matrix, is_si=True)
        storeys[name] = storey
    quantity = boq.report(doc)
    by_source = {}
    for row in quantity["items"]:
        by_source.setdefault(row["source_id"], []).append(row)
    exported = {}
    material_entities = {}
    wall_frames = frames(doc)

    def solid_record(key):
        model_key = next(
            (
                k
                for k, r in doc.extensions.get("wall_models", {}).items()
                if r["wall"] == key
            ),
            None,
        )
        model_key = model_key or next(
            (
                k
                for k, r in doc.extensions.get("building_models", {}).items()
                if r["source"] == key
            ),
            None,
        )
        if model_key:
            if doc.link_status.get(model_key) != "Current":
                raise ValueError("Refresh stale building geometry before IFC export")
            record = doc.extensions.get("solids", {}).get(model_key)
            if record:
                return record
        if key in wall_frames:
            shape = wall_shape(doc, key, wall_frames[key])
        else:
            from .building_geometry import make_shape

            shape = make_shape(doc, key)
        return solids.shape_record(
            shape, "IFC source", doc.find_by_id(key).layer, "extrude"
        )

    def add(key, ifc_class, name, record, predefined=None):
        product = run(
            "root.create_entity",
            ifc_class=ifc_class,
            name=name,
            **({"predefined_type": predefined} if predefined else {}),
        )
        level = building.level_for(doc, key)
        container = storeys.get(level, next(iter(storeys.values())))
        if ifc_class == "IfcSpace":
            run(
                "aggregate.assign_object", products=[product], relating_object=container
            )
        else:
            run(
                "spatial.assign_container",
                products=[product],
                relating_structure=container,
            )
        vertices = [[float(v) * metre for v in p] for p in record["vertices"]]
        representation = run(
            "geometry.add_mesh_representation",
            context=body,
            vertices=[vertices],
            faces=[record["faces"]],
            unit_scale=1.0,
        )
        run(
            "geometry.assign_representation",
            product=product,
            representation=representation,
        )
        # Vertices are world coordinates; API derives a relative placement from
        # the selected storey while retaining the identity world transform.
        run(
            "geometry.edit_object_placement",
            product=product,
            matrix=np.eye(4),
            is_si=True,
        )
        props = {"SourceId": key, "Level": level, "DrawingUnits": doc.units}
        for i, row in enumerate(by_source.get(key, []), 1):
            props[f"Item{i}Description"] = row["description"]
            props[f"Item{i}Unit"] = row["unit"]
            props[f"Item{i}Quantity"] = row["quantity"]
            if row["rate"] is not None:
                props[f"Item{i}Rate"] = row["rate"]
                props[f"Item{i}Amount"] = row["amount"]
        pset = run("pset.add_pset", product=product, name="PyCAD_SourceAndQuantities")
        run("pset.edit_pset", pset=pset, properties=props)
        material_name = materials.material_name(doc, key)
        if material_name:
            if material_name not in material_entities:
                material_entities[material_name] = run(
                    "material.add_material", name=material_name
                )
            run(
                "material.assign_material",
                products=[product],
                type="IfcMaterial",
                material=material_entities[material_name],
            )
        exported[key] = product
        return product

    for key, r in doc.extensions.get("architecture", {}).items():
        if doc.find_by_id(key) and r["kind"] == "wall":
            add(key, "IfcWall", "Wall " + key[:8], solid_record(key), "STANDARD")
    for key, r in doc.extensions.get("building_elements", {}).items():
        if not doc.find_by_id(key):
            continue
        kinds = {
            "slab": ("IfcSlab", "FLOOR"),
            "ceiling": ("IfcCovering", "CEILING"),
            "roof": (
                "IfcRoof",
                r.get("roof_type", "").upper() + "_ROOF"
                if r.get("roof_type") in ("SHED", "GABLE", "HIP")
                else "USERDEFINED",
            ),
            "stair": (
                "IfcStair",
                {
                    "Straight": "STRAIGHT_RUN_STAIR",
                    "L": "QUARTER_TURN_STAIR",
                    "U": "HALF_TURN_STAIR",
                }[r["layout"]]
                if r["kind"] == "stair"
                else None,
            ),
        }
        ifc_class, predefined = kinds[r["kind"]]
        if r["kind"] == "roof":
            predefined = {
                "Flat": "FLAT_ROOF",
                "Shed": "SHED_ROOF",
                "Gable": "GABLE_ROOF",
                "Hip": "HIP_ROOF",
            }[r["roof_type"]]
        add(key, ifc_class, r["name"], solid_record(key), predefined)
    for key, r in doc.extensions.get("architecture", {}).items():
        entity = doc.find_by_id(key)
        if entity is None:
            continue
        if r["kind"] == "opening" and r["wall"] in exported:
            host = doc.find_by_id(r["wall"])
            h = doc.extensions["architecture"][r["wall"]]
            scale = abs(host.scale)
            cq = solids.kernel()
            from .wall_joining import world_point

            x, y = world_point(host, r["station"], 0)
            shape = (
                cq.Workplane("XY")
                .box(
                    r["width"] * scale,
                    h["width"] * scale,
                    r["height"] * scale,
                    centered=(True, True, False),
                )
                .val()
                .rotate((0, 0, 0), (0, 0, 1), host.rotation)
                .translate(
                    (x, y, building.elevation(doc, r["wall"]) + r["sill"] * scale)
                )
            )
            record = solids.shape_record(
                shape, r["identifier"], entity.layer, "extrude"
            )
            product = add(
                key,
                "IfcDoor" if r["type"] == "door" else "IfcWindow",
                r["identifier"],
                record,
            )
            product.OverallWidth = r["width"] * scale * metre
            product.OverallHeight = r["height"] * scale * metre
            opening = run(
                "root.create_entity",
                ifc_class="IfcOpeningElement",
                name="Opening " + r["identifier"],
            )
            opening.Representation = product.Representation
            opening.ObjectPlacement = product.ObjectPlacement
            model.create_entity(
                "IfcRelVoidsElement",
                GlobalId=ifcopenshell.guid.new(),
                RelatingBuildingElement=exported[r["wall"]],
                RelatedOpeningElement=opening,
            )
            model.create_entity(
                "IfcRelFillsElement",
                GlobalId=ifcopenshell.guid.new(),
                RelatingOpeningElement=opening,
                RelatedBuildingElement=product,
            )
        elif r["kind"] == "room":
            pts, _, _ = architecture.room_metrics(doc, r)
            cq = solids.kernel()
            wire = cq.Wire.makePolygon(
                [cq.Vector(p.x, p.y, building.elevation(doc, key)) for p in pts],
                close=True,
            )
            shape = cq.Solid.extrudeLinear(
                wire,
                [],
                (
                    0,
                    0,
                    building.levels(doc).get(
                        building.level_for(doc, key), {"height": 3000}
                    )["height"],
                ),
            )
            product = add(
                key,
                "IfcSpace",
                r["number"] + " " + r["name"],
                solids.shape_record(shape, r["name"], entity.layer, "extrude"),
            )
            product.LongName = r["name"]
    if not exported:
        raise ValueError("No typed building objects to export")
    atomic_write(path, lambda filename: model.write(str(filename)))
    return {"objects": len(exported), "levels": len(storeys), "schema": "IFC4"}
