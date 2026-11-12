"""
scripting.py
The object exposed as `api` inside the Python console (see console.py).
Every creation method goes through the normal undo stack, so anything a
script does is undoable/redoable exactly like a manual draw command - this
was the main design goal: scripting is a first-class way to drive the same
document model the GUI tools use, not a side channel that bypasses undo.
"""
from .geometry import (Point, LineEntity, CircleEntity, ArcEntity, PolylineEntity,
                        RectangleEntity, TextEntity)
from .document import AddEntityCommand


class ScriptAPI:
    def __init__(self, main_window):
        self._mw = main_window

    @property
    def document(self):
        return self._mw.document

    # -- creation helpers (each pushes a proper undo command) ------------
    def line(self, x1, y1, x2, y2, layer=None, color="#FFFFFF"):
        e = LineEntity(Point(x1, y1), Point(x2, y2), layer=layer or self.document.layers.current_layer,
                        color=color)
        self.document.undo_stack.push(AddEntityCommand(self.document, e, "Script: Line"))
        return e

    def circle(self, cx, cy, r, layer=None, color="#FFFFFF"):
        e = CircleEntity(Point(cx, cy), r, layer=layer or self.document.layers.current_layer, color=color)
        self.document.undo_stack.push(AddEntityCommand(self.document, e, "Script: Circle"))
        return e

    def arc(self, cx, cy, r, start_angle, end_angle, layer=None, color="#FFFFFF"):
        e = ArcEntity(Point(cx, cy), r, start_angle, end_angle,
                       layer=layer or self.document.layers.current_layer, color=color)
        self.document.undo_stack.push(AddEntityCommand(self.document, e, "Script: Arc"))
        return e

    def rectangle(self, x1, y1, x2, y2, layer=None, color="#FFFFFF"):
        e = RectangleEntity(Point(x1, y1), Point(x2, y2),
                             layer=layer or self.document.layers.current_layer, color=color)
        self.document.undo_stack.push(AddEntityCommand(self.document, e, "Script: Rectangle"))
        return e

    def polyline(self, points, closed=False, layer=None, color="#FFFFFF"):
        pts = [Point(x, y) for x, y in points]
        e = PolylineEntity(pts, closed=closed, layer=layer or self.document.layers.current_layer, color=color)
        self.document.undo_stack.push(AddEntityCommand(self.document, e, "Script: Polyline"))
        return e

    def text(self, x, y, s, height=2.5, layer=None, color="#FFFFFF"):
        e = TextEntity(Point(x, y), s, height=height, layer=layer or self.document.layers.current_layer,
                        color=color)
        self.document.undo_stack.push(AddEntityCommand(self.document, e, "Script: Text"))
        return e

    # -- document / layer / view helpers ----------------------------------
    def add_layer(self, name, color="#FFFFFF"):
        self.document.layers.add_layer(name, color)

    def set_layer(self, name):
        self.document.layers.set_current(name)

    def entities(self):
        """All entities currently in the drawing (read-only list)."""
        return list(self.document.entities)

    def clear(self):
        """Delete every entity in the drawing (undoable as one step)."""
        from .document import DeleteEntitiesCommand
        if self.document.entities:
            self.document.undo_stack.push(DeleteEntitiesCommand(self.document, list(self.document.entities),
                                                                  "Script: Clear"))

    def undo(self):
        self.document.undo_stack.undo()

    def redo(self):
        self.document.undo_stack.redo()

    def zoom_extents(self):
        self._mw.canvas.zoom_extents()

    def refresh(self):
        self._mw.canvas.viewport().update()
