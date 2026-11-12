"""Undoable table edits retain geometry/layout object identity across history."""
import copy
from PyQt6.QtGui import QUndoCommand


class LayerStateCommand(QUndoCommand):
    def __init__(self, document, layers, current, description, rename=None):
        super().__init__(description)
        self.doc = document
        self.before = copy.deepcopy(document.layers.layers)
        self.after = copy.deepcopy(layers)
        self.old_current = document.layers.current_layer
        self.new_current = current
        self.rename = rename
        self.targets = []
        if rename:
            self.targets = [e for e in document.entities if e.layer == rename[0]]
            self.targets += [e for b in document.blocks.values() for e in b.entities if e.layer == rename[0]]

    def _apply(self, layers, current, forward):
        self.doc.layers.layers.clear()
        self.doc.layers.layers.update(copy.deepcopy(layers))
        self.doc.layers.current_layer = current
        if self.rename:
            old, new = self.rename if forward else self.rename[::-1]
            for feature in self.doc.extrusions:
                if feature["layer"] == old: feature["layer"] = new
            for solid in self.doc.extensions.get('solids',{}).values():
                if solid['layer']==old: solid['layer']=new
            for block in self.doc.blocks.values():
                for spec in block.attributes:
                    if spec['layer']==old: spec['layer']=new
            for table in self.doc.extensions.get('viewport_overrides',{}).values():
                if old in table: table[new]=table.pop(old)
            for state in self.doc.extensions.get('layer_states',{}).values():
                if old in state['layers']: state['layers'][new]=state['layers'].pop(old)
                if state['current']==old: state['current']=new
            for entity in self.targets:
                entity.layer = self.rename[1 if forward else 0]

    def redo(self):self._apply(self.after,self.new_current,True)
    def undo(self):self._apply(self.before,self.old_current,False)


class LayoutTableCommand(QUndoCommand):
    def __init__(self, document, after, description):
        super().__init__(description)
        self.doc=document
        # Shallow mappings intentionally retain Layout and Viewport identity.
        self.before=dict(document.layouts)
        self.after=dict(after)
        self.before_space=document.current_space
        self.reviews_before=copy.deepcopy(document.extensions.get("office_reviews"))
        self.reviews_after=copy.deepcopy(self.reviews_before)
        if self.reviews_after:
            by_layout={id(layout):name for name,layout in self.after.items()}
            for review in self.reviews_after.values():
                space=review["space"]
                if space in self.before:
                    review["space"]=by_layout.get(id(self.before[space]),space)


    def _apply(self, values, restore_space=None):
        self.doc.layouts.clear();self.doc.layouts.update(values)
        for name,layout in values.items():layout.name=name
        if restore_space in values or restore_space=='Model':self.doc.current_space=restore_space
        elif self.doc.current_space not in values:self.doc.current_space='Model'

    def _reviews(self, reviews):
        if reviews is not None:self.doc.extensions["office_reviews"]=copy.deepcopy(reviews)

    def redo(self):
        self._apply(self.after)
        self._reviews(self.reviews_after)

    def undo(self):
        self._apply(self.before,self.before_space)
        self._reviews(self.reviews_before)


class StyleTableCommand(QUndoCommand):
    def __init__(self, document, styles, current):
        super().__init__('Dimension style')
        self.doc = document
        self.before = copy.deepcopy(document.dimstyles)
        self.after = copy.deepcopy(styles)
        self.old_current = document.current_dimstyle
        self.new_current = current

    def _apply(self, styles, current):
        self.doc.dimstyles = copy.deepcopy(styles)
        self.doc.current_dimstyle = current

    def redo(self): self._apply(self.after, self.new_current)
    def undo(self): self._apply(self.before, self.old_current)
