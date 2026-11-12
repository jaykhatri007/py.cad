"""Physical drawing conversion with a preflight and identity-preserving undo."""

import copy
from PyQt6.QtGui import QUndoCommand
from .geometry import Point, BlockReferenceEntity
from .units import UNIT_MM, validate_settings


def scale_geometry(entity, factor):
    # Definitions are scaled once. An INSERT's dimensionless scale must stay put.
    if entity.kind == 'MLEADER':
        # Style sizes convert once at the drawing table; insertion scales stay dimensionless.
        for p in [entity.position,*entity.endpoints()]:
            p.x *= factor; p.y *= factor
    elif isinstance(entity, BlockReferenceEntity):
        entity.insertion_point.x *= factor
        entity.insertion_point.y *= factor
        for p in entity.clip_boundary or []:
            p.x *= factor
            p.y *= factor
    else:
        entity.scale_from(Point(0, 0), factor)


def _scale_document(doc, target, settings):
    factor = UNIT_MM[doc.units] / UNIT_MM[target]
    doc.linetype_scale *= factor
    for e in doc.entities:
        scale_geometry(e, factor)
    for block in doc.blocks.values():
        for e in block.entities:
            scale_geometry(e, factor)
        if block.is_xref:
            block.source_scale *= factor
    for style in doc.dimstyles.values():
        for key in (
            "text_height",
            "arrow_size",
            "text_gap",
            "extension_offset",
            "extension_beyond",
        ):
            style[key] *= factor
    for style in doc.textstyles.values():
        style['height'] *= factor
    for style in doc.mleaderstyles.values():
        for key in ('text_height','arrow_size','landing_length','text_gap'):
            style[key] *= factor
    for c in doc.constraints:
        if c["kind"] in ("linear", "aligned", "radius", "diameter"):
            c["value"] *= factor
        if c["kind"] == "fixed":
            kind = doc.find_by_id(c["refs"][0]["entity"]).kind
            n = {"POINT": 2, "LINE": 4, "CIRCLE": 3, "ARC": 3}[kind]
            c["fixed"][:n] = [v * factor for v in c["fixed"][:n]]
    doc.constraint_settings["tolerance"] = max(
        1e-8, min(0.001, doc.constraint_settings["tolerance"] * factor)
    )
    for f in doc.extrusions:
        f["height"] *= factor
        p = f["profile"]
        if p["kind"] == "CIRCLE":
            p["center"] = [v * factor for v in p["center"]]
            p["radius"] *= factor
        else:
            p["points"] = [[v * factor for v in xy] for xy in p["points"]]
    for u in doc.underlays:
        if doc.extensions.get("office_reviews",{}).get(u["id"],{}).get("space","Model")!="Model":continue
        u["origin"] = [v * factor for v in u["origin"]]
        u["width"] *= factor
    # Paper stays in millimeters; compensate model-to-paper viewport transforms.
    for layout in doc.layouts.values():
        for v in layout.viewports:
            v.center.x *= factor
            v.center.y *= factor
            v.scale /= factor
    from .feature_interop import scale_extensions
    scale_extensions(doc,factor)
    doc.units, doc.unit_settings = target, dict(settings)
    doc.sync_associative()
    return factor


def _restore(current, value):
    """Keep point/list identities used by previous undo commands whenever possible."""
    if isinstance(current, Point) and isinstance(value, Point):
        current.x, current.y = value.x, value.y
        return current
    if (
        isinstance(current, list)
        and isinstance(value, list)
        and len(current) == len(value)
    ):
        current[:] = [_restore(a, b) for a, b in zip(current, value)]
        return current
    if isinstance(current, dict) and isinstance(value, dict):
        for key in set(current) - set(value):
            del current[key]
        for key, item in value.items():
            current[key] = _restore(current.get(key), item)
        return current
    return copy.deepcopy(value)


def _snapshot(doc):
    entities = doc.entities + [e for b in doc.blocks.values() for e in b.entities]
    return dict(
        entities={
            e.id: copy.deepcopy(
                {k: v for k, v in vars(e).items() if k != "resolved_entities"}
            )
            for e in entities
        },
        block_entities={name:copy.deepcopy(b.entities) for name,b in doc.blocks.items()},
        sources={name: b.source_scale for name, b in doc.blocks.items()},
        attributes={name:copy.deepcopy(b.attributes) for name,b in doc.blocks.items()},
        viewports=[
            (v.center.x, v.center.y, v.scale)
            for l in doc.layouts.values()
            for v in l.viewports
        ],
        tables={
            key: copy.deepcopy(getattr(doc, key))
            for key in (
                "units",
                "unit_settings",
                "linetype_scale",
                "dimstyles",
                'textstyles',
                'current_textstyle',
                "mleaderstyles",
                "current_mleaderstyle",
                "constraints",
                "constraint_settings",
                "extrusions",
                "underlays",
                "extensions",
            )
        },
    )


class ConvertUnitsCommand(QUndoCommand):
    def __init__(self, doc, converted):
        super().__init__(f"Convert {doc.units} to {converted.units}")
        self.doc = doc
        self.before, self.after = _snapshot(doc), _snapshot(converted)
        self.block_objects = {e.id:e for b in doc.blocks.values() for e in b.entities}

    def apply(self, state):
        doc = self.doc
        for name, entities in state['block_entities'].items():
            restored = []
            for prototype in entities:
                if prototype.id not in self.block_objects:
                    self.block_objects[prototype.id] = copy.deepcopy(prototype)
                restored.append(self.block_objects[prototype.id])
            doc.blocks[name].entities = restored
        for e in doc.entities + [e for b in doc.blocks.values() for e in b.entities]:
            for key, value in state["entities"][e.id].items():
                setattr(e, key, _restore(getattr(e, key, None), value))
        for key, value in state["tables"].items():
            setattr(doc, key, _restore(getattr(doc, key), value))
        for name, value in state["sources"].items():
            doc.blocks[name].source_scale = value
            doc.blocks[name].attributes = copy.deepcopy(state["attributes"][name])
        for v, values in zip(
            (v for l in doc.layouts.values() for v in l.viewports), state["viewports"]
        ):
            v.center.x, v.center.y, v.scale = values
        doc._view_actual_signatures = {key:link['fingerprint'] for key,link in doc.extensions.get('view_links', {}).items()}
        doc._building_view_actual = {key:link['fingerprint'] for key,link in doc.extensions.get('building_views', {}).items()}
        doc.sync_associative()

    def redo(self):
        self.apply(self.after)

    def undo(self):
        self.apply(self.before)


def convert_units(doc, target, settings=None):
    """Keep physical size unchanged. Reject the whole conversion if preflight fails."""
    from .native_io import document_to_dict, document_from_dict
    from .validation import validate_payload

    settings = dict(settings or doc.unit_settings)
    validate_settings(settings, target)
    if doc.units not in UNIT_MM or target not in UNIT_MM:
        raise ValueError(
            "Physical conversion requires a known source and target unit; unitless cannot be converted."
        )
    if target == doc.units:
        from .units import change_units

        change_units(doc, target, settings)
        return 1.0
    candidate = document_from_dict(document_to_dict(doc))
    factor = _scale_document(candidate, target, settings)
    validate_payload(document_to_dict(candidate))
    if candidate.constraints:
        from .constraints import solve

        solve(candidate, check_only=True)
    doc.undo_stack.push(ConvertUnitsCommand(doc, candidate))
    if doc.units != target:
        raise ValueError(
            "The constraint solver rejected the conversion; no drawing changes were applied."
        )
    return factor
