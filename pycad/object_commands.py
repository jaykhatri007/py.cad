"""Selection context commands and undoable, one-level decomposition."""
import copy
import uuid
from PyQt6.QtGui import QUndoCommand
from PyQt6.QtWidgets import QMenu
from .geometry import (Point, LineEntity, PolylineEntity, SplineEntity,
                       BlockReferenceEntity, HatchEntity, DimensionEntity)
from .document import SetAttrCommand


def selected(mw):
    return [e for e in mw.canvas.selected_entities if mw.document.is_editable(e)]


def parts(entity, doc):
    if isinstance(entity, BlockReferenceEntity):
        block = doc.blocks.get(entity.block_name)
        if block is None or block.is_xref or entity.clip_boundary:
            return None
        result = [e.clone() for e in entity.resolved_entities]
        for e in result:
            if e.color == 'BYBLOCK' or (e.layer == '0' and e.color == 'BYLAYER'):
                e.color = entity.color
            if e.layer == '0': e.layer = entity.layer
            if e.linetype == 'BYBLOCK': e.linetype = entity.linetype
            e.transparency = min(90, 100*(1-(1-entity.transparency/100)*(1-e.transparency/100)))
        return result
    if isinstance(entity, PolylineEntity):
        from .precision import polyline_parts
        return polyline_parts(entity)
    if isinstance(entity, SplineEntity):
        points = entity._catmull_rom_samples()
        # Approximate the displayed spline, retain all sampled segments.
        return [LineEntity(Point(a.x,a.y),Point(b.x,b.y),**entity.style_kwargs())
                for a,b in zip(points,points[1:])]
    if isinstance(entity, HatchEntity):
        return [PolylineEntity([Point(p.x,p.y) for p in loop],closed=True,**entity.style_kwargs())
                for loop in [entity.boundary,*entity.holes]]
    if isinstance(entity, DimensionEntity):
        from .dimstyles import style_for, dimension_geometry, dimension_label
        from .geometry import TextEntity
        style = style_for(doc, entity)
        lines, fills, anchor, height = dimension_geometry(entity, style)
        result = [LineEntity(Point(a.x,a.y),Point(b.x,b.y),**entity.style_kwargs()) for a,b in lines]
        result += [HatchEntity([Point(p.x,p.y) for p in tri],pattern='SOLID',**entity.style_kwargs()) for tri in fills]
        result.append(TextEntity(Point(anchor.x,anchor.y),dimension_label(entity,style),height=height,**entity.style_kwargs()))
        return result
    return None  # LINE and other primitive objects already have no components.


class ExplodeCommand(QUndoCommand):
    def __init__(self, doc, replacements):
        super().__init__('Explode')
        self.doc = doc
        self.before = list(doc.entities)
        self.after = [part for e in self.before for part in replacements.get(e.id,[e])]
        self.replaced = set(replacements)
        self.constraints = copy.deepcopy(doc.constraints)
        self.extensions = copy.deepcopy(doc.extensions)
        self.after_extensions = copy.deepcopy(doc.extensions)
        # A dissolved reference no longer carries parametric/quantity metadata.
        for area in ('architecture','building_elements','level_assignments','material_assignments',
                     'auto_rooms','leader_links','view_links','views'):
            for key in self.replaced: self.after_extensions.get(area,{}).pop(key,None)
        for key in self.replaced: self.after_extensions.get('boq',{}).get('tags',{}).pop(key,None)
        for members in self.after_extensions.get('groups',{}).values():
            members[:] = [p.id if hasattr(p,'id') else p for key in members for p in replacements.get(key,[key])]

    def redo(self):
        self.doc.entities = list(self.after)
        self.doc.extensions = copy.deepcopy(self.after_extensions)
        self.doc.constraints = [c for c in self.constraints if not any(r['entity'] in self.replaced for r in c['refs'])]
        self.doc.dirty = True

    def undo(self):
        self.doc.entities = list(self.before)
        self.doc.extensions = copy.deepcopy(self.extensions)
        self.doc.constraints = copy.deepcopy(self.constraints)


def explode(mw):
    doc = mw.document
    items = selected(mw)
    if not items: raise ValueError('Select blocks, groups, polylines, splines, hatches or dimensions first')
    keys = {e.id for e in items}
    groups = doc.extensions.get('groups',{})
    grouped = {name for name,members in groups.items() if keys.intersection(members)}
    if grouped:
        after = copy.deepcopy(doc.extensions)
        for name in grouped: after['groups'].pop(name)
        doc.undo_stack.push(SetAttrCommand(doc,doc,'extensions',doc.extensions,after,'Ungroup'))
        mw.command_history.appendPlainText(f'Dissolved {len(grouped)} group(s); geometry preserved. Run EXPLODE again for components.')
        return
    managed = set().union(*(set(doc.extensions.get(area,{})) for area in ('architecture','building_elements','views','view_links')))
    if keys.intersection(managed):
        raise ValueError('Parametric building objects must be detached before exploding')
    replacements = {e.id:p for e in items if (p:=parts(e,doc)) is not None}
    if not replacements:
        raise ValueError('These objects cannot be exploded. Lines are already primitive; clipped blocks and Xrefs must be edited at source.')
    doc.undo_stack.push(ExplodeCommand(doc,replacements))
    mw.canvas.selected_entities = [p for values in replacements.values() for p in values]
    mw.command_history.appendPlainText(f'Exploded {len(replacements)} object(s). Splines become sampled line segments; Undo restores originals.')


def select_similar(mw):
    seeds = selected(mw)
    if not seeds: raise ValueError('Select an object first')
    def key(e): return (e.kind,e.layer,e.block_name if e.kind=='INSERT' else None)
    keys = {key(e) for e in seeds}
    mw.canvas.selected_entities = [e for e in mw.document.editable_entities() if key(e) in keys]
    mw.refresh_selection_ui()


def isolate(mw, restore=False):
    items = selected(mw)
    if not restore and not items: raise ValueError('Select objects to isolate')
    mw.document.isolated_ids = None if restore else {e.id for e in items}
    mw.document.render_revision += 1
    mw.refresh_selection_ui()


def group(mw, dissolve=False):
    items = selected(mw)
    if len(items)<(1 if dissolve else 2): raise ValueError('Select group members' if dissolve else 'Select at least two objects')
    after = copy.deepcopy(mw.document.extensions)
    table = after.setdefault('groups',{})
    keys = {e.id for e in items}
    if dissolve:
        table = {k:v for k,v in table.items() if not keys.intersection(v)}
        after['groups'] = table
    else:
        table[uuid.uuid4().hex] = sorted(keys)
    mw.document.undo_stack.push(SetAttrCommand(mw.document,mw.document,'extensions',mw.document.extensions,after,'Ungroup' if dissolve else 'Group'))


def commands(mw):
    return {'EXPLODE':lambda:explode(mw),'SELECTSIMILAR':lambda:select_similar(mw),
            'ISOLATEOBJECTS':lambda:isolate(mw),'UNISOLATEOBJECTS':lambda:isolate(mw,True),
            'GROUP':lambda:group(mw),'UNGROUP':lambda:group(mw,True)}


def context_menu(mw, pos):
    menu = QMenu(mw.canvas)
    if pos is not None:
        point=mw.canvas.screen_to_world(pos.x(),pos.y());mw.current_world_pos=(point.x(),point.y())
    active = getattr(mw.current_tool,'name','SELECT') != 'SELECT'
    if active:
        menu.addAction('Enter / Finish',lambda:mw._on_key_pressed(__import__('PyQt6.QtCore',fromlist=['Qt']).Qt.Key.Key_Return))
        menu.addAction('Cancel',mw.cancel_command)
        menu.addSeparator()
    if not active:
        from .selection_cycle import choose
        menu.addAction('Choose overlapping object…',lambda:choose(mw))
        menu.addSeparator()
    has = bool(selected(mw))
    for label, command in [('Properties','PROPERTIES'),('Select Similar','SELECTSIMILAR'),
                           ('Isolate Objects','ISOLATEOBJECTS'),('End Object Isolation','UNISOLATEOBJECTS'),
                           ('Block Editor','BEDIT'),('Bind Xref to drawing','BIND'),('Explode','EXPLODE'),('Group','GROUP'),('Ungroup','UNGROUP')]:
        action = menu.addAction(label,lambda checked=False,c=command:mw.run_ribbon_command(c))
        if command in ('PROPERTIES','SELECTSIMILAR','ISOLATEOBJECTS','EXPLODE','GROUP','UNGROUP'): action.setEnabled(has)
        if command=='UNISOLATEOBJECTS': action.setEnabled(mw.document.isolated_ids is not None)
        if command=='BIND': action.setEnabled(any(e.kind=='INSERT' and e.block_name in mw.document.blocks and mw.document.blocks[e.block_name].is_xref for e in selected(mw)))
        if command=='BEDIT': action.setEnabled(any(e.kind=='INSERT' for e in selected(mw)))
    if len(selected(mw))==1 and isinstance(selected(mw)[0],PolylineEntity):
        menu.addAction('Polyline editor (PEDIT)…',lambda:mw.run_ribbon_command('PEDIT'))
    modify = menu.addMenu('Modify')
    for label,command in [('Move','MOVE'),('Copy','COPY'),('Rotate','ROTATE'),('Scale','SCALE'),('Mirror','MIRROR'),('Trim','TRIM'),('Extend','EXTEND'),('Offset','OFFSET'),('Erase','ERASE')]:
        modify.addAction(label,lambda checked=False,c=command:mw.run_ribbon_command(c))
    draw = menu.addMenu('Draw')
    for label,command in [('Line','LINE'),('Polyline','PLINE'),('Circle','CIRCLE'),('Rectangle','RECTANGLE'),('Spline','SPLINE'),('Hatch','HATCH'),('Text','TEXT')]:
        draw.addAction(label,lambda checked=False,c=command:mw.run_ribbon_command(c))
    menu.addSeparator()
    for label,command in [('Undo','UNDO'),('Redo','REDO'),('Zoom Extents','ZOOMEXTENTS')]:
        menu.addAction(label,lambda checked=False,c=command:mw.run_ribbon_command(c))
    return menu
