"""Point-driven native multileader creation and branch editing."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPen
from PyQt6.QtWidgets import QInputDialog
from .tools import Tool, PREVIEW_COLOR
from .geometry import Point
from .document import AddEntityCommand, SetAttrCommand
from .geom_ops import pick_entity, point_segment_distance
from .mleaders import MultileaderEntity, validate_entity, edit_branches, style_for

LEFT = Qt.MouseButton.LeftButton.value


class MultileaderTool(Tool):
    name = "MLEADER"

    def status_prompt(self):
        return (
            "MLEADER: "
            + ("Pick arrow tip", "Pick elbow", "Pick text position")[len(self.points)]
        )

    def on_text_input(self, text):
        point = self.parse_point(text, self.points[-1] if self.points else None)
        if point is None:
            raise ValueError("Enter x,y or @dx,dy")
        self.on_click(point.x, point.y, "", LEFT)

    def on_click(self, x, y, snap_kind, button):
        if button != LEFT:
            return
        point = Point(x, y)
        if len(self.points) == 1 and self.points[0].distance_to(point) <= 1e-12:
            raise ValueError("Leader tip and elbow must differ")
        if len(self.points) < 2:
            self.points.append(point)
            return
        text, accepted = QInputDialog.getMultiLineText(
            self.mw, "Multileader", "Plain-text annotation:"
        )
        if accepted:
            entity = MultileaderEntity(
                point,
                text,
                [self.points],
                style_name=self.document.current_mleaderstyle,
                layer=self.document.layers.current_layer,
                linetype=self.document.current_linetype,
            )
            validate_entity(self.document, entity)
            self.document.undo_stack.push(
                AddEntityCommand(self.document, entity, "Multileader")
            )
        self.finish()

    def draw_preview(self, painter, canvas):
        if not self.points or self.mw.current_world_pos is None:
            return
        current = Point(*self.mw.current_world_pos)
        painter.save()
        painter.setPen(QPen(PREVIEW_COLOR, 1, Qt.PenStyle.DashLine))
        if len(self.points) == 1:
            painter.drawLine(
                canvas.world_to_screen(self.points[0].x, self.points[0].y),
                canvas.world_to_screen(current.x, current.y),
            )
        else:
            preview = MultileaderEntity(
                current,
                "Text",
                [self.points],
                style_name=self.document.current_mleaderstyle,
            )
            canvas._draw_mleader(painter, preview)
        painter.restore()


class BranchTool(Tool):
    def __init__(self, mw):
        super().__init__(mw)
        selected = [
            e
            for e in mw.canvas.selected_entities
            if e.kind == "MLEADER" and e in self.document.editable_entities()
        ]
        self.target = selected[0] if len(selected) == 1 else None

    def select_target(self, x, y):
        candidates = [
            e for e in self.document.editable_entities() if e.kind == "MLEADER"
        ]
        self.target = pick_entity(
            candidates, Point(x, y), self.mw.canvas.snap_radius_px / self.mw.canvas.zoom
        )
        if self.target is not None:
            self.mw.canvas.selected_entities = [self.target]
        return self.target

    def require_editable(self):
        if self.target not in self.document.editable_entities():
            raise ValueError("Select a visible, unlocked native multileader")

    def on_text_input(self, text):
        point = self.parse_point(text, self.points[-1] if self.points else None)
        if point is None:
            raise ValueError("Enter x,y or @dx,dy")
        self.on_click(point.x, point.y, "", LEFT)


class AddLeaderTool(BranchTool):
    name = "MLEADERADD"

    def status_prompt(self):
        if self.target is None:
            return "MLEADERADD: Select a native multileader"
        return "MLEADERADD: " + (
            "Pick new arrow tip" if not self.points else "Pick new elbow"
        )

    def on_click(self, x, y, snap_kind, button):
        if button != LEFT:
            return
        if self.target is None:
            self.select_target(x, y)
            return
        self.require_editable()
        point = Point(x, y)
        if not self.points:
            self.points.append(point)
            return
        edit_branches(
            self.document,
            self.target,
            self.target.leaders + [[self.points[0], point]],
            "Add leader branch",
        )
        self.finish()

    def draw_preview(self, painter, canvas):
        if self.target is None or not self.points or self.mw.current_world_pos is None:
            return
        preview = self.target.clone()
        preview.leaders = [[self.points[0], Point(*self.mw.current_world_pos)]]
        painter.save()
        painter.setPen(QPen(PREVIEW_COLOR, 1, Qt.PenStyle.DashLine))
        canvas._draw_mleader(painter, preview)
        painter.restore()


class RemoveLeaderTool(BranchTool):
    name = "MLEADERREMOVE"

    def status_prompt(self):
        return "MLEADERREMOVE: " + (
            "Select a native multileader"
            if self.target is None
            else "Pick branch near its arrow or elbow"
        )

    def on_click(self, x, y, snap_kind, button):
        if button != LEFT:
            return
        if self.target is None:
            self.select_target(x, y)
            return
        self.require_editable()
        if len(self.target.leaders) == 1:
            raise ValueError(
                "Keep one leader branch; use ERASE to delete the annotation"
            )
        pos = Point(x, y)
        paths = self.target.branch_paths(style_for(self.document, self.target))
        candidates = [
            (min(point_segment_distance(pos, a, b) for a, b in zip(path, path[1:])), i)
            for i, path in enumerate(paths)
        ]
        distance, index = min(candidates)
        if distance > self.mw.canvas.snap_radius_px / self.mw.canvas.zoom:
            return
        branches = [
            branch for i, branch in enumerate(self.target.leaders) if i != index
        ]
        edit_branches(self.document, self.target, branches, "Remove leader branch")
        self.finish()


def edit_text(mw):
    entities = [
        e for e in mw.canvas.selected_entities if e in mw.document.editable_entities()
    ]
    if len(entities) != 1 or entities[0].kind != "MLEADER":
        raise ValueError("Select one visible, unlocked native multileader first")
    entity = entities[0]
    text, accepted = QInputDialog.getMultiLineText(
        mw, "Edit multileader", "Plain-text annotation:", entity.text
    )
    if accepted and text != entity.text:
        candidate = entity.clone()
        candidate.text = text
        validate_entity(mw.document, candidate)
        mw.document.undo_stack.push(
            SetAttrCommand(
                mw.document, entity, "text", entity.text, text, "Multileader text"
            )
        )


def apply_style(mw, name):
    entities = [
        e
        for e in mw.canvas.selected_entities
        if e.kind == "MLEADER" and e in mw.document.editable_entities()
    ]
    if not entities:
        raise ValueError("Select a visible, unlocked native multileader first")
    for entity in entities:
        candidate = entity.clone()
        candidate.style_name = name
        validate_entity(mw.document, candidate)
    changed = [e for e in entities if e.style_name != name]
    if changed:
        mw.document.undo_stack.beginMacro("Apply multileader style")
        for entity in changed:
            mw.document.undo_stack.push(
                SetAttrCommand(
                    mw.document, entity, "style_name", entity.style_name, name
                )
            )
        mw.document.undo_stack.endMacro()


MLEADER_TOOLS = {
    cls.name: cls for cls in (MultileaderTool, AddLeaderTool, RemoveLeaderTool)
}
