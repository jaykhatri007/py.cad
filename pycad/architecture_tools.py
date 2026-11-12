from PyQt6.QtCore import Qt
from .tools import LineTool, Tool
from .geometry import Point


class WallTool(LineTool):
    name = "WALL"

    def __init__(self, mw, width, height):
        super().__init__(mw)
        self.width = width
        self.height = height

    def status_prompt(self):
        return "WALL: Click points or enter x,y; Enter finishes"

    def _commit_segment(self, a, b):
        from .architecture import create_wall

        create_wall(self.document, a, b, self.width, self.height)


class OpeningTool(Tool):
    def __init__(self, mw, kind, width, identifier):
        super().__init__(mw)
        self.name = kind.upper()
        self.kind = kind
        self.width = width
        self.identifier = identifier

    def status_prompt(self):
        return self.name + ": Click a host wall; Esc finishes"

    def on_click(self, x, y, snap_kind, button):
        if button != Qt.MouseButton.LeftButton.value:
            return
        from .geom_ops import pick_entity
        from .architecture import create_opening
        import math

        table = self.document.extensions.get("architecture", {})
        walls = [
            e
            for e in self.document.editable_entities()
            if table.get(e.id, {}).get("kind") == "wall"
        ]
        wall = pick_entity(
            walls,
            Point(x, y),
            self.mw.canvas.snap_radius_px / max(self.mw.canvas.zoom, 1e-12),
        )
        if wall is None:
            return
        angle = math.radians(wall.rotation)
        station = (
            (x - wall.insertion_point.x) * math.cos(angle)
            + (y - wall.insertion_point.y) * math.sin(angle)
        ) / wall.scale
        try:
            create_opening(
                self.document,
                wall,
                station,
                self.width,
                2100 if self.kind == "door" else 1200,
                self.kind,
                self.identifier,
                0 if self.kind == "door" else 900,
            )
        except ValueError as ex:
            self.mw.command_history.appendPlainText(str(ex))
