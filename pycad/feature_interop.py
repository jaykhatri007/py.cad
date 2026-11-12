"""Feature dependencies for clipboard transfer and physical unit conversion."""

import copy


def selection_extensions(doc, ids, blocks):
    result = {}
    groups = {k:[v for v in members if v in ids] for k,members in doc.extensions.get('groups',{}).items()}
    groups = {k:v for k,v in groups.items() if len(v)>=2}
    if groups: result['groups'] = groups
    architecture = {
        k: copy.deepcopy(r)
        for k, r in doc.extensions.get("architecture", {}).items()
        if k in ids
    }
    # A hosted opening copied by itself becomes a static block, keeping its geometry.
    architecture = {
        k: r
        for k, r in architecture.items()
        if r["kind"] != "opening" or r["wall"] in architecture
    }
    if architecture:
        result["architecture"] = architecture
    links = {
        k: copy.deepcopy(value)
        for k, value in doc.extensions.get("leader_links", {}).items()
        if k in ids
    }
    for key, value in links.items():
        links[key] = [r if r is None or r["source"] in ids else None for r in value]
    if links:
        result["leader_links"] = links
    for area in ("building_elements", "level_assignments", "material_assignments"):
        selected = {
            k: copy.deepcopy(r)
            for k, r in doc.extensions.get(area, {}).items()
            if k in ids
        }
        if selected:
            result[area] = selected
    required = {r["level"] for r in result.get("building_elements", {}).values()} | {
        r["level"] for r in result.get("level_assignments", {}).values()
    }
    if required:
        from .building import levels

        result["levels"] = {
            k: copy.deepcopy(r) for k, r in levels(doc).items() if k in required
        }
    materials = {
        r["material"] for r in result.get("building_elements", {}).values()
    } | {r["material"] for r in result.get("material_assignments", {}).values()}
    if materials:
        result["materials"] = {
            k: copy.deepcopy(r)
            for k, r in doc.extensions.get("materials", {}).items()
            if k in materials
        }
    rooms = {
        k: copy.deepcopy(r)
        for k, r in doc.extensions.get("auto_rooms", {}).items()
        if k in ids
        and r["boundary"] in ids
        and all(source in ids for source in r["walls"])
    }
    if rooms:
        result["auto_rooms"] = rooms
    tags = {
        k: copy.deepcopy(r)
        for k, r in doc.extensions.get("boq", {}).get("tags", {}).items()
        if k in ids
    }
    if tags:
        result["boq"] = {"tags": tags}
        specs={k:v for k,v in doc.extensions.get('workflow',{}).get('takeoff_specs',{}).items() if k in tags}
        if specs:result['workflow']={'takeoff_specs':specs}
    for area in ('xref_sources','xref_unloaded'):
        selected={k:copy.deepcopy(v) for k,v in doc.extensions.get('workflow',{}).get(area,{}).items() if k in blocks}
        if selected:result.setdefault('workflow',{})[area]=selected
    pro=doc.extensions.get('professional',{});selected={}
    links={k:copy.deepcopy(v) for k,v in pro.get('associations',{}).items() if k in ids and all(source in ids for source in v['sources'])}
    if links:selected['associations']=links
    adjustments={k:copy.deepcopy(v) for k,v in pro.get('quantity_adjustments',{}).items() if k in ids}
    if adjustments:selected['quantity_adjustments']=adjustments
    variants={k:copy.deepcopy(v) for k,v in pro.get('variants',{}).items() if k in blocks and v['base'] in blocks}
    if variants:selected['variants']=variants
    if selected:result['professional']=selected
    prod=doc.extensions.get('productivity',{});new={}
    tables={k:copy.deepcopy(v) for k,v in prod.get('tables',{}).items() if k in blocks}
    params={k:copy.deepcopy(v) for k,v in prod.get('parameters',{}).items() if k in blocks and v['base'] in blocks}
    if tables:new['tables']=tables
    if params:new['parameters']=params
    if new:result['productivity']=new
    for area in ("office_doors","office_linetypes"):
        records=doc.extensions.get(area,{})
        if records:
            result[area]={k:copy.deepcopy(v) for k,v in records.items() if area=="office_linetypes" or k in blocks}
    return result


def remap_extensions(value, ids, block_names):
    result = copy.deepcopy(value)
    import uuid
    if "office_doors" in result:
        result["office_doors"]={block_names.get(k,k):v for k,v in result["office_doors"].items()}
    if 'productivity' in result:
        prod=result['productivity']
        if 'tables' in prod:prod['tables']={block_names.get(k,k):v for k,v in prod['tables'].items()}
        if 'parameters' in prod:prod['parameters']={block_names.get(k,k):{**v,'base':block_names.get(v['base'],v['base'])} for k,v in prod['parameters'].items()}
    if 'professional' in result:
        pro=result['professional']
        for area in ('associations','quantity_adjustments'):
            if area in pro:pro[area]={ids.get(k,k):v for k,v in pro[area].items()}
        for r in pro.get('associations',{}).values():r['sources']=[ids.get(k,k) for k in r['sources']]
        if 'variants' in pro:
            pro['variants']={block_names.get(k,k):{**v,'base':block_names.get(v['base'],v['base'])} for k,v in pro['variants'].items()}
    if "workflow" in result:
        for area in ("xref_sources","xref_unloaded"):
            if area in result["workflow"]:result["workflow"][area]={block_names.get(k,k):v for k,v in result["workflow"][area].items()}
        result["workflow"]["takeoff_specs"]={ids.get(k,k):v for k,v in result["workflow"].get("takeoff_specs",{}).items()}
    if 'groups' in result:
        result['groups'] = {uuid.uuid4().hex:[ids.get(v,v) for v in members] for members in result['groups'].values()}
    for area in (
        "architecture",
        "leader_links",
        "building_elements",
        "level_assignments",
        "material_assignments",
        "auto_rooms",
    ):
        if area in result:
            result[area] = {ids.get(k, k): r for k, r in result[area].items()}
    for r in result.get("architecture", {}).values():
        r["block"] = block_names.get(r["block"], r["block"])
        for key in ("wall", "source"):
            if key in r:
                r[key] = ids.get(r[key], r[key])
    for links in result.get("leader_links", {}).values():
        for r in links:
            if r:
                r["source"] = ids.get(r["source"], r["source"])
    for r in result.get("building_elements", {}).values():
        r["block"] = block_names.get(r["block"], r["block"])
    for r in result.get("auto_rooms", {}).values():
        r["boundary"] = ids.get(r["boundary"], r["boundary"])
        r["walls"] = [ids.get(k, k) for k in r["walls"]]
    if "boq" in result:
        result["boq"]["tags"] = {
            ids.get(k, k): r for k, r in result["boq"]["tags"].items()
        }
    return result


def merge_extensions(current, imported, default_levels=None):
    result = copy.deepcopy(current)
    imported = copy.deepcopy(imported)
    if imported.get("levels") and not result.get("levels") and default_levels:
        result["levels"] = copy.deepcopy(default_levels)
    # Preserve the receiving drawing's existing storeys and appearances.
    for area in ("levels", "materials"):
        remap = {}
        for name, value in list(imported.get(area, {}).items()):
            existing = result.get(area, {})
            target = name
            count = 2
            while target in existing and existing[target] != value:
                target = name + "_" + str(count)
                count += 1
            if target != name:
                imported[area][target] = imported[area].pop(name)
                remap[name] = target
        if area == "levels":
            for section in ("level_assignments", "building_elements", "auto_rooms"):
                for record in imported.get(section, {}).values():
                    record["level"] = remap.get(record["level"], record["level"])
        else:
            for section in (
                "material_assignments",
                "building_elements",
                "architecture",
            ):
                for record in imported.get(section, {}).values():
                    if "material" in record:
                        record["material"] = remap.get(
                            record["material"], record["material"]
                        )
            for record in imported.get("boq", {}).get("tags", {}).values():
                record["material"] = remap.get(record["material"], record["material"])
    for area, values in imported.items():
        if area in ("professional","workflow","productivity"):
            for section,records in values.items():result.setdefault(area,{}).setdefault(section,{}).update(copy.deepcopy(records))
        elif area == "boq":
            result.setdefault("boq", {}).setdefault("tags", {}).update(
                copy.deepcopy(values.get("tags", {}))
            )
        else:
            result.setdefault(area, {}).update(copy.deepcopy(values))
    return result


def scale_extensions(doc, factor):
    for r in doc.extensions.get('office_doors',{}).values():r['width']*=factor
    for r in doc.extensions.get('office_linetypes',{}).values():
        for key in ('dash','gap','height'):r[key]*=factor
    for r in doc.extensions.get('productivity',{}).get('parameters',{}).values():
        for k in ('base_width','base_height','width','height','threshold_x','threshold_y'):r[k]*=factor
    for r in doc.extensions.get('productivity',{}).get('tables',{}).values():r['position']=[v*factor for v in r['position']];r['cell_width']*=factor;r['row_height']*=factor
    for r in doc.extensions.get('productivity',{}).get('survey',{}).values():r['scale']/=factor
    for r in doc.extensions.get('productivity',{}).get('standards',{}).values():r['text_height']*=factor

    for state in doc.extensions.get("professional",{}).get("variants",{}).values():
        for k in ("stretch_x","stretch_y","threshold_x","threshold_y"):state[k]*=factor
    for level in doc.extensions.get("levels", {}).values():
        level["elevation"] *= factor
        level["height"] *= factor
    for r in doc.extensions.get("building_elements", {}).values():
        for key in (
            "width",
            "tread",
            "height",
            "landing",
            "rail_height",
            "thickness",
            "elevation",
            "overhang",
        ):
            if key in r:
                r[key] *= factor
        if "profile" in r:
            r["profile"] = [[v * factor for v in p] for p in r["profile"]]
        if "holes" in r:
            r["holes"] = [
                [[v * factor for v in p] for p in hole] for hole in r["holes"]
            ]
    for r in doc.extensions.get("auto_rooms", {}).values():
        r["seed"] = [v * factor for v in r["seed"]]
    for r in doc.extensions.get("building_views", {}).values():
        r["offset"] *= factor
    for block in doc.blocks.values():
        for spec in block.attributes:
            spec["position"] = [v * factor for v in spec["position"]]
            spec["height"] *= factor
    for r in doc.extensions.get("architecture", {}).values():
        for key in ("length", "width", "height", "sill", "station"):
            if key in r:
                r[key] *= factor
        if "boundary" in r:
            r["boundary"] = [[v * factor for v in p] for p in r["boundary"]]
    from .native_io import entity_from_dict, entity_to_dict
    from .unit_conversion import scale_geometry

    for macro in doc.extensions.get("macros", {}).values():
        for action in macro["actions"]:
            for key in ("start", "end", "center"):
                if key in action:
                    action[key] = [v * factor for v in action[key]]
            for key in ("radius", "width", "depth", "wall_width", "dx", "dy"):
                if key in action:
                    action[key] *= factor
            if "entity" in action:
                entity = entity_from_dict(action["entity"])
                scale_geometry(entity, factor)
                action["entity"] = entity_to_dict(entity)
    for link in doc.extensions.get("view_links", {}).values():
        link["offset"] *= factor
    if doc.extensions.get("solids"):
        from .solids import kernel, shape_record
        import base64, io

        for key, r in list(doc.extensions["solids"].items()):
            doc.extensions["solids"][key] = shape_record(
                kernel()
                .Shape.importBrep(io.BytesIO(base64.b64decode(r["brep"])))
                .scale(factor),
                r["name"],
                r["layer"],
                r["operation"],
            )
