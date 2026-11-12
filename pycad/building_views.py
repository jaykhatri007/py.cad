"""Linked multi-object sections, hatching and kernel hidden-line projections."""

import uuid
from .geometry import Point, HatchEntity
from .connected_models import digest, _cache


def validate_views(table):
    from .validation import name, finite

    for key, r in table.items():
        name(key, "Building view")
        if not isinstance(r, dict) or set(r) != {
            "sources",
            "type",
            "axis",
            "offset",
            "view",
            "hidden",
            "hatch",
            "block",
            "fingerprint",
        }:
            raise ValueError("Invalid building drawing view")
        if (
            not isinstance(r["sources"], list)
            or not 1 <= len(r["sources"]) <= 500
            or len(set(r["sources"])) != len(r["sources"])
        ):
            raise ValueError("Choose 1–500 distinct view sources")
        for source in r["sources"]:
            name(source, "View source")
        if (
            r["type"] not in ("section", "elevation")
            or r["axis"] not in ("X", "Y", "Z")
            or r["view"] not in ("Top", "Front", "Right")
            or type(r["hidden"]) is not bool
            or type(r["hatch"]) is not bool
        ):
            raise ValueError("Invalid drawing-view options")
        name(r["block"], "View block")
        finite(r["offset"], "Section plane")
        if (
            not isinstance(r["fingerprint"], str)
            or len(r["fingerprint"]) != 64
            or any(c not in "0123456789abcdef" for c in r["fingerprint"])
        ):
            raise ValueError("Invalid view fingerprint")


def signature(doc, r):
    values = []
    for key in r["sources"]:
        source = doc.extensions.get("solids", {}).get(key)
        if source is None:
            raise ValueError("A building view source is missing")
        if doc.link_status.get(key, "Current") != "Current":
            raise ValueError(doc.link_status[key])
        values.append([key, source["sha256"]])
    return digest(
        [
            values,
            {k: r[k] for k in ("type", "axis", "offset", "view", "hidden", "hatch")},
        ]
    )


def projection_paths(shape, view, hidden=False):
    from .solids import kernel, _edge_paths
    from OCP.HLRBRep import HLRBRep_Algo, HLRBRep_HLRToShape
    from OCP.HLRAlgo import HLRAlgo_Projector
    from OCP.gp import gp_Ax2, gp_Pnt, gp_Dir

    normals = {"Top": (0, 0, 1), "Front": (0, -1, 0), "Right": (1, 0, 0)}
    xaxis = (0, 1, 0) if view == "Right" else (1, 0, 0)
    algo = HLRBRep_Algo()
    algo.Add(shape.wrapped)
    algo.Projector(
        HLRAlgo_Projector(
            gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(*normals[view]), gp_Dir(*xaxis))
        )
    )
    algo.Update()
    algo.Hide()
    extract = HLRBRep_HLRToShape(algo)
    cq = kernel()
    paths = []
    for fn, style in [
        (extract.VCompound, "CONTINUOUS"),
        (extract.OutLineVCompound, "CONTINUOUS"),
    ] + (
        [(extract.HCompound, "DASHED"), (extract.OutLineHCompound, "DASHED")]
        if hidden
        else []
    ):
        wrapped = fn()
        if wrapped.IsNull():
            continue
        for path in _edge_paths(cq.Shape.cast(wrapped), "Z"):
            path.linetype = style
            paths.append(path)
    return paths


def make_paths(doc, r):
    from .solids import kernel, get_shape, _edge_paths

    cq = kernel()
    shape = cq.Compound.makeCompound([get_shape(doc, key) for key in r["sources"]])
    if r["type"] == "elevation":
        return projection_paths(shape, r["view"], r["hidden"])
    axis = r["axis"]
    bounds = shape.BoundingBox()
    size = max(bounds.xlen, bounds.ylen, bounds.zlen, abs(r["offset"]), 1) * 4
    normals = {"X": (1, 0, 0), "Y": (0, 1, 0), "Z": (0, 0, 1)}
    origin = {
        "X": (r["offset"], 0, 0),
        "Y": (0, r["offset"], 0),
        "Z": (0, 0, r["offset"]),
    }[axis]
    plane = cq.Face.makePlane(size, size, cq.Vector(*origin), cq.Vector(*normals[axis]))
    cut = shape.intersect(plane)
    paths = _edge_paths(cut, axis)
    if r["hatch"]:
        axes = {"X": (1, 2), "Y": (0, 2), "Z": (0, 1)}[axis]

        def points(wire):
            sampled = wire.sample(64)[0]
            result = [Point(tuple(p)[axes[0]], tuple(p)[axes[1]]) for p in sampled]
            if result and result[0].distance_to(result[-1]) < 1e-7:
                result.pop()
            return result

        for face in cut.Faces():
            boundary = points(face.outerWire())
            holes = [points(wire) for wire in face.innerWires()]
            if len(boundary) >= 3:
                paths.insert(
                    0, HatchEntity(boundary, holes=holes, spacing=max(size / 250, 1e-5))
                )
    return paths


def create_view(
    doc,
    sources,
    kind="elevation",
    axis="Z",
    offset=1200,
    view="Front",
    hidden=False,
    hatch=True,
    position=(0, 0),
):
    from .architecture import _install
    from .feature_data import edit_table
    from .validation import finite

    doc.sync_associative()
    record = dict(
        sources=list(sources),
        type=kind,
        axis=axis,
        offset=offset,
        view=view,
        hidden=hidden,
        hatch=hatch,
        block="BUILDING_VIEW_" + uuid.uuid4().hex[:10],
        fingerprint="0" * 64,
    )
    validate_views({"pending": record})
    if len(position) != 2:
        raise ValueError("View position needs x,y")
    for value in position:
        finite(value, "View position")
    record["fingerprint"] = signature(doc, record)
    paths = make_paths(doc, record)
    if not paths:
        raise ValueError("No geometry at this plane/view")
    doc.undo_stack.beginMacro("Building " + kind)
    try:
        insert = _install(doc, record["block"], paths, Point(*position))
        for i, path in enumerate(paths):
            path.id = uuid.uuid5(
                uuid.NAMESPACE_URL, insert.id + "/building-view/" + str(i)
            ).hex
            path.layer = insert.layer
        edit_table(doc, "building_views", insert.id, record, "Link building drawing")
        edit_table(
            doc,
            "views",
            insert.id,
            dict(source=sources[0], view="Building " + kind, block=record["block"]),
            "Building view data",
        )
    finally:
        doc.undo_stack.endMacro()
    return insert


def sync(doc):
    actual = getattr(doc, "_building_view_actual", None)
    if actual is None:
        actual = doc._building_view_actual = {}
    for key, r in doc.extensions.get("building_views", {}).items():
        insert = doc.find_by_id(key)
        block = doc.blocks.get(r["block"])
        if insert is None or block is None:
            continue
        current = actual.setdefault(key, r["fingerprint"])
        _cache(doc, "building-view", key, current, block.entities)
        try:
            target = signature(doc, r)
            if target != current:
                paths = _cache(doc, "building-view", key, target)
                if paths is None:
                    paths = make_paths(doc, r)
                    for i, path in enumerate(paths):
                        path.id = uuid.uuid5(
                            uuid.NAMESPACE_URL, key + "/building-view/" + str(i)
                        ).hex
                        path.layer = insert.layer
                block.entities = paths
                actual[key] = target
                _cache(doc, "building-view", key, target, paths)
            r["fingerprint"] = target
            doc.link_status[key] = (
                "Current" if block.entities else "Current; section has no intersection"
            )
        except Exception as ex:
            doc.link_status[key] = "Stale building view: " + str(ex)
