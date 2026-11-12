"""
document.py
The drawing document: holds entities, the layer manager, and the undo stack.
"""
from .linetypes import NAMES as LINETYPE_NAMES

import copy
import math
from typing import Dict, List, Optional
from PyQt6.QtGui import QUndoStack, QUndoCommand

from .geometry import (Entity, Point, LineEntity, CircleEntity, PolylineEntity, DimensionEntity,
                       HatchEntity, BlockDefinition, BlockReferenceEntity, RayEntity, XLineEntity)
from .layers import LayerManager
from .layout import Layout
from .spatial_index import SpatialIndex


class Document:
    def __init__(self):
        self.entities: List[Entity] = []
        self.render_revision = 0
        self.isolated_ids = None
        self.spatial_index = SpatialIndex()
        self.layers = LayerManager()
        from .constraints import ConstraintUndoStack, DEFAULT_SETTINGS
        self.constraints = []
        self.constraint_settings = dict(DEFAULT_SETTINGS)
        self.constraint_report = {}
        self.cad_standard = None
        self.undo_stack = ConstraintUndoStack(self)
        self.filepath: Optional[str] = None
        self._saved_state = None
        self._force_dirty = False
        from .dimstyles import DEFAULT_STYLE
        self.dimstyles = {"Standard": copy.deepcopy(DEFAULT_STYLE)}
        self.current_dimstyle = "Standard"
        from .mleaders import DEFAULT_STYLE as MLEADER_STYLE
        self.mleaderstyles = {"Standard":copy.deepcopy(MLEADER_STYLE)}
        self.current_mleaderstyle = "Standard"
        from .textstyles import DEFAULT_STYLE as TEXT_STYLE
        self.textstyles = {'Standard': copy.deepcopy(TEXT_STYLE)}
        self.current_textstyle = 'Standard'
        self.extrusions = []
        self.extensions = {}
        self.underlays = []
        self.units = "mm"
        from .units import DEFAULT_SETTINGS as UNIT_DEFAULTS
        self.unit_settings = dict(UNIT_DEFAULTS)
        self.import_warnings = []
        self.source_filepath = None
        self.source_archive = None
        self.current_linetype = "BYLAYER"
        self.linetype_scale = 1.0
        self.blocks: Dict[str, BlockDefinition] = {}
        # Layouts (Paper Space sheets) - see layout.py. Keyed by name;
        # "Model" is implicit and not stored here.
        self.layouts: Dict[str, Layout] = {}
        self.current_space = "Model"
        # Any edit that goes through the undo stack (draw, move, delete,
        # fillet, mirror, array, ...) fires indexChanged - listening here
        # means associative Dimensions/Hatches refresh after every such
        # operation, uniformly, without every tool needing to know about it.
        self.undo_stack.indexChanged.connect(self.sync_associative)
        self.mark_saved()
        from .document_lifecycle import register
        register(self)

    @property
    def dirty(self):
        from .native_io import document_to_dict
        return self._force_dirty or document_to_dict(self) != self._saved_state

    @dirty.setter
    def dirty(self, value):
        # Existing commands mark dirty explicitly; content comparison also catches
        # direct layer/script edits, and becomes clean after undo back to a save.
        from .edit_journal import invalidate
        if self.__dict__.get("_edit_context") is None: invalidate(self)
        self.render_revision += 1
        if not value:
            self.mark_saved()

    def mark_saved(self):
        from .native_io import document_to_dict
        self._saved_state = document_to_dict(self)
        self._force_dirty = False
        self.undo_stack.setClean()

    def editable_entities(self):
        return [e for e in self.visible_entities() if not self.layers.is_locked(e.layer)]

    def entity_color(self, entity):
        if not entity.color or entity.color.upper() == "BYLAYER":
            return self.layers.layers.get(entity.layer, {}).get("color", "#FFFFFF")
        return entity.color

    def edit_dimstyle(self, operation, name, value=None):
        from .dimstyles import edit_style
        edit_style(self, operation, name, value)

    def entity_linetype(self, entity):
        if entity.linetype == "BYLAYER":
            return self.layers.layers.get(entity.layer, {}).get("linetype", "CONTINUOUS")
        return entity.linetype

    def add_entity(self, entity: Entity):
        self.entities.append(entity)
        self.spatial_index.invalidate()
        self.dirty = True

    def remove_entity(self, entity: Entity):
        if self.entities and self.entities[-1] is entity:
            self.entities.pop()
            self.spatial_index.invalidate()
            self.dirty = True
        elif entity in self.entities:
            self.entities.remove(entity)
            self.spatial_index.invalidate()
            self.dirty = True

    def is_visible(self, entity):
        from .building import visible
        return (self.layers.is_visible(entity.layer) and visible(self, entity.id) and
                (self.isolated_ids is None or entity.id in self.isolated_ids))

    def contains_entity(self, entity):
        from .edit_journal import current
        state = current(self)
        if state is not None: return state.ids.get(entity.id) is entity
        key = (id(self.entities),len(self.entities),self.render_revision)
        if getattr(self,'_membership_key',None) != key:
            self._membership_ids = {id(e) for e in self.entities}
            self._membership_key = key
        return id(entity) in self._membership_ids

    def is_editable(self, entity):
        return self.contains_entity(entity) and self.is_visible(entity) and not self.layers.is_locked(entity.layer)

    def visible_entities(self):
        from .building import visible
        return [e for e in self.entities if self.is_visible(e)]

    def rebuild_spatial_index(self):
        self.spatial_index.rebuild(self.entities)
        self._unbounded_entities = [e for e in self.entities if isinstance(e, (RayEntity, XLineEntity))]
        self._spatial_collection = (id(self.entities), len(self.entities))
        self._spatial_revision = self.render_revision

    def query_entities(self, bbox, visible_only=True, editable_only=False):
        """Return entities whose bounding boxes overlap ``bbox``.

        The index is rebuilt lazily after undoable geometry transforms. The
        final visibility/lock filters remain in the document model so this
        acceleration cache cannot change CAD semantics.
        """
        if (self.spatial_index._dirty or getattr(self,'_spatial_revision',None)!=self.render_revision or
                getattr(self, '_spatial_collection', None) != (id(self.entities), len(self.entities))):
            self.rebuild_spatial_index()
        entities = self.spatial_index.query(bbox)
        # Rays and construction lines are mathematically unbounded; their
        # finite defining-point boxes cannot be used as spatial bounds. Keep
        # them in the candidate stream so selection remains CAD-correct even
        # far away from the defining point.
        indexed_ids = {id(entity) for entity in entities}
        entities.extend(
            entity for entity in self._unbounded_entities
            if id(entity) not in indexed_ids
        )
        if visible_only:
            from .building import visible
            entities = [e for e in entities if self.is_visible(e)]
        if editable_only:
            entities = [e for e in entities if not self.layers.is_locked(e.layer)]
        return entities

    def find_by_id(self, entity_id: str) -> Optional[Entity]:
        from .edit_journal import current
        state = current(self)
        if state is not None: return state.ids.get(entity_id)
        key=(id(self.entities),len(self.entities),self.render_revision)
        if getattr(self,'_id_lookup_key',None)!=key:
            self._id_lookup={e.id:e for e in self.entities};self._id_lookup_key=key
        return self._id_lookup.get(entity_id)

    def add_block(self, block_def: BlockDefinition):
        self.blocks[block_def.name] = block_def
        self.dirty = True

    def add_layout(self, name: str, page_width: float = 297.0, page_height: float = 210.0) -> Layout:
        """Compatibility entry point for scripts and older callers.

        New layout creation is a normal undoable table edit in v12; retaining
        this method keeps the v11 scripting surface working while routing it
        through the validated command path.
        """
        return self.create_layout(name, page_width, page_height)

    def reload_xref(self, name: str, source=None):
        """Re-import an Xref's source file and refresh every place it's
        inserted. No-op if `name` isn't an Xref (or doesn't exist)."""
        block_def = self.blocks.get(name)
        if block_def is not None and block_def.is_xref:
            from .xref import read_reference, reference_path, portable_path
            from .table_commands import LayerStateCommand
            source_path = portable_path(self, source) if source is not None else block_def.source_filepath
            entities,layers,warnings = read_reference(reference_path(self,source_path))
            from .unit_conversion import scale_geometry
            for entity in entities:
                scale_geometry(entity, block_def.source_scale)
            merged = {**layers,**self.layers.layers}
            self.undo_stack.beginMacro("Reload reference")
            if source is not None:
                self.undo_stack.push(SetAttrCommand(self,block_def,"source_filepath",block_def.source_filepath,source_path,"Relink reference"))
            self.undo_stack.push(LayerStateCommand(self,merged,self.layers.current_layer,"Reference layers"))
            self.undo_stack.push(SetAttrCommand(self,block_def,"entities",block_def.entities,entities,"Reload reference"))
            self.undo_stack.endMacro()
            return warnings
        return []

    def edit_layer(self, operation, name, value=None):
        from .table_commands import LayerStateCommand
        from .validation import name as validate_name, color as validate_color
        name = validate_name(name.strip(), "Layer name")
        layers = copy.deepcopy(self.layers.layers)
        current = self.layers.current_layer
        rename = None
        if operation == "add":
            if any(key.casefold() == name.casefold() for key in layers):
                raise ValueError("A layer with that name already exists")
            validate_color(value or "#FFFFFF", False)
            from .layers import LAYER_DEFAULTS
            layers[name] = {**LAYER_DEFAULTS, "color":value or "#FFFFFF"}
        elif name not in layers:
            raise ValueError("Layer does not exist")
        elif operation == "delete":
            if name == "0" or any(e["layer"]==name for e in self.extensions.get("solids",{}).values()) or any(s["layer"]==name for b in self.blocks.values() for s in b.attributes) or any(e["layer"] == name for e in self.extrusions) or any(e.layer == name for e in self.entities) or any(e.layer == name for b in self.blocks.values() for e in b.entities):
                raise ValueError("Layer 0 and layers containing entities cannot be deleted")
            del layers[name]
            if current == name:current = "0"
        elif operation == "rename":
            new_name = validate_name(value.strip(), "Layer name")
            if name == "0" or any(key.casefold() == new_name.casefold() for key in layers if key != name):
                raise ValueError("Cannot rename layer 0 or duplicate a layer name")
            layers = {new_name if key == name else key:props for key,props in layers.items()}
            current = new_name if current == name else current
            rename = (name,new_name)
        elif operation == "current":
            if layers[name].get("frozen",False):raise ValueError("Thaw the layer before making it current")
            current = name
        elif operation in ("visible","locked","frozen","plot"):
            if type(value) is not bool:raise ValueError("Layer state must be boolean")
            if operation == "frozen" and value and name == current:raise ValueError("Cannot freeze the current layer")
            layers[name][operation] = value
        elif operation == "linetype":
            if value not in LINETYPE_NAMES and value not in self.extensions.get("office_linetypes",{}):raise ValueError("Unsupported layer linetype")
            layers[name][operation] = value
        elif operation == "lineweight":
            from .layers import LINEWEIGHTS
            if value not in LINEWEIGHTS:raise ValueError("Choose a standard lineweight")
            if type(value) not in (int,float) or not math.isfinite(value) or not 0<=value<=2.11:raise ValueError("Lineweight must be 0–2.11 mm")
            layers[name][operation] = value
        elif operation == "color":
            validate_color(value,False)
            layers[name]["color"] = value
        else:raise ValueError("Unknown layer operation")
        if layers != self.layers.layers or current != self.layers.current_layer:
            self.undo_stack.push(LayerStateCommand(self,layers,current,operation.title()+" layer",rename))

    def create_layout(self, name, width=297.0, height=210.0):
        from .table_commands import LayoutTableCommand
        from .validation import name as validate_name, finite
        name = validate_name(name.strip(), "Layout name")
        if name.casefold() == "model" or any(n.casefold()==name.casefold() for n in self.layouts):
            raise ValueError("A layout with that name already exists")
        finite(width,"Page width",True);finite(height,"Page height",True)
        layout = Layout(name,width,height)
        bounds = [e.bbox() for e in self.visible_entities()]
        from .underlays import bounds as underlay_bounds
        bounds.extend(underlay_bounds(self))
        bbox = (min(b[0] for b in bounds),min(b[1] for b in bounds),max(b[2] for b in bounds),max(b[3] for b in bounds)) if bounds else (0,0,100,100)
        layout.add_default_viewport(bbox)
        after = dict(self.layouts);after[name] = layout
        self.undo_stack.push(LayoutTableCommand(self,after,"New layout"))
        return layout

    def edit_layout(self, name, new_name=None):
        from .table_commands import LayoutTableCommand
        from .validation import name as validate_name
        if name not in self.layouts:raise ValueError("Select a layout first")
        after = dict(self.layouts)
        if new_name is None:
            del after[name];description = "Delete layout"
        else:
            new_name = validate_name(new_name.strip(),"Layout name")
            if new_name.casefold()=="model" or any(k.casefold()==new_name.casefold() for k in after if k!=name):
                raise ValueError("Duplicate or reserved layout name")
            after = {new_name if k==name else k:v for k,v in after.items()}
            description = "Rename layout"
        self.undo_stack.push(LayoutTableCommand(self,after,description))

    def sync_associative(self, *_args):
        """Refresh any DimensionEntity/HatchEntity that references a live
        source entity, and rebuild any BlockReferenceEntity from its
        current block definition. If a source was deleted, the dependent
        entity just keeps its last-known geometry (it "detaches" rather
        than erroring)."""
        self.render_revision += 1
        from .edit_journal import sync, invalidate
        if sync(self): return
        invalidate(self)
        self.spatial_index.invalidate()
        try:
            stack_index = self.undo_stack.index()
        except RuntimeError:
            return  # Qt may emit indexChanged while destroying the Undo stack.
        if getattr(self, '_checked_index', None) != stack_index:
            self.check_issues = []
        from .feature_data import sync_extensions
        sync_extensions(self)
        resolved = set()
        # Fingerprint each definition once, not once per placed INSERT. A
        # no-op sync/save must not reallocate every transformed block copy.
        import hashlib, json
        from .native_io import entity_to_dict
        revisions = {}
        rebuilt = set()
        style_key = json.dumps(self.textstyles, sort_keys=True)

        def refresh_reference(entity):
            stamp = (revisions.get(entity.block_name), entity_to_dict(entity))
            if (getattr(entity, '_display_stamp', None) != stamp or
                    getattr(entity, '_display_cache_token', None) != id(entity.resolved_entities)):
                entity.rebuild(self.blocks.get(entity.block_name))
                entity._display_stamp = stamp
                entity._display_cache_token = id(entity.resolved_entities)
                rebuilt.add(id(entity))
        for entity in self.entities + [e for b in self.blocks.values() for e in b.entities]:
            if entity.kind == 'TEXT':
                from .textstyles import style_for as text_style_for
                entity._text_style = copy.deepcopy(text_style_for(self, entity))
            if entity.kind == 'MLEADER':
                from .mleaders import style_for
                entity._mleader_style = copy.deepcopy(style_for(self,entity))
        from .block_budget import block_order
        for name in block_order(self.blocks):
            block=self.blocks[name]
            for child in block.entities:
                if isinstance(child,BlockReferenceEntity):refresh_reference(child)
            content=([entity_to_dict(e) for e in block.entities],block.attributes,
                     [(e.block_name,revisions.get(e.block_name)) for e in block.entities if isinstance(e,BlockReferenceEntity)],style_key)
            revisions[name]=hashlib.sha256(json.dumps(content,sort_keys=True).encode()).hexdigest()
        for e in self.entities:
            if e.kind == 'CURVED_DIMENSION' and e.source_line_ids:
                from .annotation_links import line_angle_geometry
                sources = [self.find_by_id(key) for key in e.source_line_ids]
                if all(source is not None for source in sources):
                    try:
                        center, p1, p2 = line_angle_geometry(*sources, e.line_directions)
                        if center.distance_to(e.dim_point) > 1e-12:
                            e.center, e.p1, e.p2 = center, p1, p2
                    except ValueError:
                        pass  # Retain the last valid snapshot; Properties explains the link status.
            elif e.kind == 'ORDINATE_DIMENSION' and e.source_entity_id:
                from .annotation_links import anchor_point
                try:
                    p = anchor_point(self.find_by_id(e.source_entity_id), e.source_anchor)
                    e.p2 = Point(p.x, p.y)
                except (ValueError, AttributeError):
                    pass
            elif e.kind == 'CURVED_DIMENSION' and e.source_arc_id:
                from .geometry import ArcEntity
                src = self.find_by_id(e.source_arc_id)
                if isinstance(src, ArcEntity):
                    e.center = Point(src.center.x, src.center.y)
                    e.p1, e.p2 = src.endpoints()
            elif isinstance(e, DimensionEntity) and e.source_line_id:
                src = self.find_by_id(e.source_line_id)
                if isinstance(src, LineEntity):
                    e.p1 = Point(src.p1.x, src.p1.y)
                    e.p2 = Point(src.p2.x, src.p2.y)
            elif isinstance(e, HatchEntity) and e.source_entity_id:
                src = self.find_by_id(e.source_entity_id)
                if isinstance(src, CircleEntity):
                    from . import geom_ops
                    e.boundary = geom_ops.circle_to_polygon(src.center, src.radius)
                elif isinstance(src, PolylineEntity):
                    e.boundary = [Point(p.x, p.y) for p in src.sample_points()]
                if e.source_hole_ids:
                    from .hatch_ui import loop_for
                    e.holes = [loop_for(source) if isinstance(source, (CircleEntity,PolylineEntity)) else loop
                               for ref,loop in zip(e.source_hole_ids,e.holes)
                               for source in [self.find_by_id(ref)]]
            elif isinstance(e,BlockReferenceEntity):
                refresh_reference(e)
        from .associations import sync as sync_links
        sync_links(self)
        pending=[e for e in self.entities if not isinstance(e,BlockReferenceEntity) or id(e) in rebuilt]
        while pending:
            entity=pending.pop()
            if isinstance(entity,BlockReferenceEntity):pending.extend(entity.resolved_entities)
            elif entity.kind=='TEXT':
                from .textstyles import style_for
                entity._text_style=copy.deepcopy(style_for(self,entity))


# ---------------------------------------------------------------------------
# Undo/redo commands
# ---------------------------------------------------------------------------

class AddEntityCommand(QUndoCommand):
    def __init__(self, document: Document, entity: Entity, description: str = "Add"):
        super().__init__(description)
        self.document = document
        self.entity = entity

    def redo(self):
        self.document.add_entity(self.entity)

    def undo(self):
        self.document.remove_entity(self.entity)


class DeleteEntitiesCommand(QUndoCommand):
    def __init__(self, document: Document, entities: List[Entity], description: str = "Delete"):
        super().__init__(description)
        self.document = document
        self.entities = [e for e in entities if e in document.entities and not document.layers.is_locked(e.layer)]
        self.positions = [(document.entities.index(e), e) for e in self.entities]

    def redo(self):
        for e in self.entities:
            self.document.remove_entity(e)

    def undo(self):
        for index, e in sorted(self.positions):
            self.document.entities.insert(index, e)


class TranslateEntitiesCommand(QUndoCommand):
    def __init__(self, document: Document, entities: List[Entity], dx: float, dy: float,
                 description: str = "Move"):
        super().__init__(description)
        self.document = document
        self.entities = list(entities)
        self.dx = dx
        self.dy = dy

    def redo(self):
        for e in self.entities:
            e.translate(self.dx, self.dy)

    def undo(self):
        for e in self.entities:
            e.translate(-self.dx, -self.dy)


class SetAttrCommand(QUndoCommand):
    """Generic undoable attribute swap - used by Trim/Extend/Fillet/Chamfer to
    reassign an entity's endpoint/attribute (e.g. line.p1 = new_point).
    Combine several of these with QUndoStack.beginMacro()/endMacro() so a
    single Fillet (which shortens two lines AND adds an arc) undoes as one step."""

    def __init__(self, document: Document, entity: Entity, attr_name: str,
                 old_value, new_value, description: str = "Edit"):
        super().__init__(description)
        self.document = document
        self.entity = entity
        self.attr_name = attr_name
        self.old_value = copy.deepcopy(old_value)
        self.new_value = copy.deepcopy(new_value)

    def redo(self):
        setattr(self.entity, self.attr_name, copy.deepcopy(self.new_value))
        self.document.dirty = True

    def undo(self):
        setattr(self.entity, self.attr_name, copy.deepcopy(self.old_value))


class RotateEntitiesCommand(QUndoCommand):
    def __init__(self, document: Document, entities: List[Entity], center: Point, angle_deg: float,
                 description: str = "Rotate"):
        super().__init__(description)
        self.document = document
        self.entities = list(entities)
        self.center = center
        self.angle_deg = angle_deg

    def redo(self):
        for e in self.entities:
            e.rotate_around(self.center, self.angle_deg)

    def undo(self):
        for e in self.entities:
            e.rotate_around(self.center, -self.angle_deg)


class ScaleEntitiesCommand(QUndoCommand):
    def __init__(self, document: Document, entities: List[Entity], center: Point, factor: float,
                 description: str = "Scale"):
        super().__init__(description)
        self.document = document
        self.entities = list(entities)
        self.center = center
        if not math.isfinite(factor) or factor <= 0:
            raise ValueError("Scale factor must be finite and positive")
        self.factor = factor

    def redo(self):
        for e in self.entities:
            e.scale_from(self.center, self.factor)

    def undo(self):
        for e in self.entities:
            e.scale_from(self.center, 1.0 / self.factor)


class SetPointCommand(QUndoCommand):
    """Grip-editing primitive: reassigns an existing Point object's (x, y)
    in place - used when dragging a line endpoint, a polyline/spline
    vertex, or a circle/arc center, all of which are real stored Point
    attributes on the entity (so mutating the object's coordinates directly
    edits the entity, no extra bookkeeping needed)."""

    def __init__(self, document: Document, point: Point, old_xy, new_xy, description: str = "Edit point"):
        super().__init__(description)
        self.document = document
        self.point = point
        self.owner = None
        self.grip_kind = None
        for entity in document.entities:
            for kind, candidate in entity.grip_points():
                if candidate is point:
                    self.owner, self.grip_kind = entity, kind
        self.old_xy = old_xy
        self.new_xy = new_xy

    def _target(self):
        if self.owner is not None:
            for kind, candidate in self.owner.grip_points():
                if kind == self.grip_kind:
                    return candidate
        return self.point

    def redo(self):
        target = self._target()
        target.x, target.y = self.new_xy
        self.document.dirty = True

    def undo(self):
        target = self._target()
        target.x, target.y = self.old_xy


class AddViewportCommand(QUndoCommand):
    """Undoable Layout.add_viewport_at() - Layout/Viewport objects aren't
    Entity subclasses (they're Paper Space plumbing, not drawing content),
    so they need their own small commands rather than reusing
    AddEntityCommand/DeleteEntitiesCommand."""

    def __init__(self, document: Document, layout, x: float, y: float, width: float, height: float,
                 model_bbox, description: str = "Add Viewport"):
        super().__init__(description)
        self.document = document
        self.layout = layout
        self.x, self.y, self.width, self.height = x, y, width, height
        self.model_bbox = model_bbox
        self.viewport = None

    def redo(self):
        if self.viewport is None:
            self.viewport = self.layout.add_viewport_at(self.x, self.y, self.width, self.height, self.model_bbox)
        elif self.viewport not in self.layout.viewports:
            self.layout.viewports.append(self.viewport)
        self.document.dirty = True

    def undo(self):
        if self.viewport in self.layout.viewports:
            self.layout.viewports.remove(self.viewport)


class RemoveViewportCommand(QUndoCommand):
    def __init__(self, document: Document, layout, viewport, description: str = "Remove Viewport"):
        super().__init__(description)
        self.document = document
        self.layout = layout
        self.viewport = viewport

    def redo(self):
        if self.viewport in self.layout.viewports:
            self.layout.viewports.remove(self.viewport)
        self.document.dirty = True

    def undo(self):
        if self.viewport not in self.layout.viewports:
            self.layout.viewports.append(self.viewport)


class SetViewportRectCommand(QUndoCommand):
    """Undoable move/resize of an existing Viewport's paper-space rectangle
    (used by SelectTool's viewport-grip dragging). Does NOT change the
    viewport's model-space center/scale - moving/resizing on the paper
    just relocates the window, it doesn't change what part of the model it
    shows (matching how dragging a viewport border works in AutoCAD)."""

    def __init__(self, document: Document, viewport, old_rect, new_rect, description: str = "Resize Viewport"):
        super().__init__(description)
        self.document = document
        self.viewport = viewport
        self.old_rect = old_rect  # (x, y, width, height)
        self.new_rect = new_rect

    def redo(self):
        self.viewport.x, self.viewport.y, self.viewport.width, self.viewport.height = self.new_rect
        self.document.dirty = True

    def undo(self):
        self.viewport.x, self.viewport.y, self.viewport.width, self.viewport.height = self.old_rect


class AddBlockCommand(QUndoCommand):
    def __init__(self, document, definition):
        super().__init__("Define block")
        self.document, self.definition = document, definition

    def redo(self):
        self.document.blocks[self.definition.name] = self.definition

    def undo(self):
        self.document.blocks.pop(self.definition.name, None)
