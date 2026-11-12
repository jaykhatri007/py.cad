"""Persistent, plain-text multileaders and shared screen/PDF/DXF primitives."""

import copy
import math
from PyQt6.QtGui import QUndoCommand
from .geometry import Entity, Point, _rotate_pt, _reflect_pt, _scale_pt

DEFAULT_STYLE = dict(
    text_height=2.5,
    arrow_size=2.5,
    landing_length=4.0,
    text_gap=1.0,
    scale=1.0,
    arrow_type="Closed",
    color="BYLAYER",
)
MAX_BRANCHES = 64


def validate_style(style):
    from .validation import color

    if not isinstance(style, dict) or set(style) != set(DEFAULT_STYLE):
        raise ValueError("Invalid multileader style fields")
    for key in ("text_height", "arrow_size", "landing_length", "text_gap", "scale"):
        value = style[key]
        if (
            type(value) not in (int, float)
            or not math.isfinite(value)
            or not 0 <= value <= 1e6
        ):
            raise ValueError(key + " must be finite and between 0 and 1,000,000")
        if key in ("text_height", "scale") and value == 0:
            raise ValueError(key + " must be positive")
    if style["arrow_type"] not in ("Closed", "Open", "None"):
        raise ValueError("Unknown multileader arrow type")
    color(style["color"])
    return style


def validate_text(text):
    if not isinstance(text, str) or not text.strip() or len(text) > 16384:
        raise ValueError("Multileader text must contain 1–16,384 characters")
    if len(text.split("\n")) > 128 or any(len(line) > 256 for line in text.split("\n")):
        raise ValueError("Use at most 128 lines and 256 characters per line")
    if any(ord(char) < 32 and char != "\n" for char in text):
        raise ValueError("Only printable text and line breaks are supported")
    return text


def style_for(document, entity):
    return document.mleaderstyles.get(entity.style_name, DEFAULT_STYLE)


class MultileaderEntity(Entity):
    kind = "MLEADER"

    def __init__(
        self,
        position,
        text,
        leaders,
        style_name="Standard",
        scale=1.0,
        rotation=0.0,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.position = Point(position.x, position.y)
        self.text = text
        self.leaders = [[Point(p.x, p.y) for p in branch] for branch in leaders]
        self.style_name, self.scale, self.rotation = style_name, scale, rotation
        self._mleader_style = copy.deepcopy(DEFAULT_STYLE)

    def local_point(self, x, y):
        return _rotate_pt(
            Point(self.position.x + x, self.position.y + y),
            self.position,
            self.rotation,
        )

    def branch_paths(self, style=None):
        style = style or self._mleader_style
        factor = style["scale"] * self.scale
        height = style["text_height"] * factor
        # Conservative text envelope; shared by hit tests and all output paths.
        width = max(len(line) for line in self.text.split("\n")) * height
        gap, length = style["text_gap"] * factor, style["landing_length"] * factor
        paths = []
        for tip, elbow in self.leaders:
            local = _rotate_pt(elbow, self.position, -self.rotation)
            edge, side = (-gap, -1) if local.x <= self.position.x else (width + gap, 1)
            paths.append(
                [
                    tip,
                    elbow,
                    self.local_point(edge + side * length, 0),
                    self.local_point(edge, 0),
                ]
            )
        return paths

    def geometry(self, style=None):
        style = style or self._mleader_style
        factor = style["scale"] * self.scale
        height = style["text_height"] * factor
        lines, fills = [], []
        for path in self.branch_paths(style):
            lines.extend(zip(path, path[1:]))
            tip, toward = path[:2]
            distance = tip.distance_to(toward)
            if distance <= 1e-12 or style["arrow_type"] == "None":
                continue
            size = min(style["arrow_size"] * factor, distance / 3)
            if size <= 0:
                continue
            ux, uy = (toward.x - tip.x) / distance, (toward.y - tip.y) / distance
            p = Point(tip.x + size * (ux - 0.35 * uy), tip.y + size * (uy + 0.35 * ux))
            q = Point(tip.x + size * (ux + 0.35 * uy), tip.y + size * (uy - 0.35 * ux))
            if style["arrow_type"] == "Closed":
                fills.append([tip, p, q])
            else:
                lines.extend(((tip, p), (tip, q)))
        labels = [
            (line, self.local_point(0, -index * height * 1.4), height, self.rotation)
            for index, line in enumerate(self.text.split("\n"))
        ]
        return lines, fills, labels

    def label_polygons(self, style=None):
        _, _, labels = self.geometry(style)
        polygons = []
        for text, pos, height, rotation in labels:
            left, right, bottom, top = (
                -height * 0.1,
                (len(text) + 0.1) * height,
                -height * 0.3,
                height * 1.2,
            )
            polygons.append(
                [
                    _rotate_pt(Point(pos.x + x, pos.y + y), pos, rotation)
                    for x, y in (
                        (left, bottom),
                        (right, bottom),
                        (right, top),
                        (left, top),
                    )
                ]
            )
        return polygons

    def bbox(self):
        lines, fills, _ = self.geometry()
        points = [p for pair in lines for p in pair] + [
            p for triangle in fills for p in triangle
        ]
        points += [p for poly in self.label_polygons() for p in poly]
        return (
            min(p.x for p in points),
            min(p.y for p in points),
            max(p.x for p in points),
            max(p.y for p in points),
        )

    def endpoints(self):
        return [p for branch in self.leaders for p in branch]

    def grip_points(self):
        result = [("position", self.position)]
        for index, (tip, elbow) in enumerate(self.leaders):
            result += [(f"tip{index}", tip), (f"elbow{index}", elbow)]
        return result

    def translate(self, dx, dy):
        for point in [self.position, *self.endpoints()]:
            point.x += dx
            point.y += dy

    def rotate_around(self, center, angle_deg):
        self.position = _rotate_pt(self.position, center, angle_deg)
        self.leaders = [
            [_rotate_pt(p, center, angle_deg) for p in pair] for pair in self.leaders
        ]
        self.rotation = (self.rotation + angle_deg) % 360

    def reflect_across(self, a, b):
        self.position = _reflect_pt(self.position, a, b)
        self.leaders = [[_reflect_pt(p, a, b) for p in pair] for pair in self.leaders]
        self.rotation = (
            2 * math.degrees(math.atan2(b.y - a.y, b.x - a.x)) - self.rotation
        ) % 360

    def scale_from(self, center, factor):
        self.position = _scale_pt(self.position, center, factor)
        self.leaders = [
            [_scale_pt(p, center, factor) for p in pair] for pair in self.leaders
        ]
        self.scale *= abs(factor)
        if factor < 0:
            self.rotation = (self.rotation + 180) % 360

    def clone(self):
        result = MultileaderEntity(
            copy.deepcopy(self.position),
            self.text,
            copy.deepcopy(self.leaders),
            self.style_name,
            self.scale,
            self.rotation,
            **self.style_kwargs(),
        )
        result._mleader_style = copy.deepcopy(self._mleader_style)
        return result

    def to_dict(self):
        return dict(
            kind=self.kind,
            text=self.text,
            position=self.position.as_tuple(),
            leaders=[[p.as_tuple() for p in branch] for branch in self.leaders],
            style_name=self.style_name,
            scale=self.scale,
            rotation=self.rotation,
            layer=self.layer,
            color=self.color,
        )


def validate_record(record, styles, encoded=True):
    from .validation import finite, point, name

    validate_text(record["text"])
    name(record["style_name"], "Multileader style name")
    if record["style_name"] not in styles:
        raise ValueError("Multileader references a missing style")
    finite(record["scale"], "Multileader scale", True)
    if record["scale"] > 1e6:
        raise ValueError("Multileader scale must not exceed 1,000,000")
    finite(record["rotation"], "Multileader rotation")
    branches = record["leaders"]
    if not isinstance(branches, list) or not 1 <= len(branches) <= MAX_BRANCHES:
        raise ValueError("A multileader requires 1–64 branches")

    def decode(p):
        if encoded:
            point(p)
            return Point(*p["point"])
        finite(p.x, "Leader X")
        finite(p.y, "Leader Y")
        return p

    position = decode(record["position"])
    leaders = []
    for branch in branches:
        if not isinstance(branch, list) or len(branch) != 2:
            raise ValueError("Each leader needs a tip and elbow")
        pair = [decode(p) for p in branch]
        if pair[0].distance_to(pair[1]) <= 1e-12:
            raise ValueError("Leader tip and elbow must differ")
        leaders.append(pair)
    entity = MultileaderEntity(
        position,
        record["text"],
        leaders,
        record["style_name"],
        record["scale"],
        record["rotation"],
    )
    entity._mleader_style = styles[entity.style_name]
    for coordinate in entity.bbox():
        finite(coordinate, "Multileader extent")


def validate_entity(document, entity):
    record = {k: v for k, v in vars(entity).items() if not k.startswith("_")}
    validate_record(record, document.mleaderstyles, encoded=False)


def edit_branches(document, entity, branches, description):
    from .document import SetAttrCommand

    if entity not in document.editable_entities():
        raise ValueError("Select a visible, unlocked multileader")
    candidate = entity.clone()
    candidate.leaders = copy.deepcopy(branches)
    validate_entity(document, candidate)
    document.undo_stack.push(
        SetAttrCommand(
            document, entity, "leaders", entity.leaders, branches, description
        )
    )


class StyleTableCommand(QUndoCommand):
    def __init__(self, document, styles, current):
        super().__init__("Multileader style")
        self.doc = document
        self.before, self.after = (
            copy.deepcopy(document.mleaderstyles),
            copy.deepcopy(styles),
        )
        self.old_current, self.new_current = document.current_mleaderstyle, current

    def apply(self, styles, current):
        self.doc.mleaderstyles = copy.deepcopy(styles)
        self.doc.current_mleaderstyle = current

    def redo(self):
        self.apply(self.after, self.new_current)

    def undo(self):
        self.apply(self.before, self.old_current)


def edit_style(document, operation, name, value=None):
    from .validation import name as valid_name

    valid_name(name, "Multileader style name")
    styles = copy.deepcopy(document.mleaderstyles)
    current = document.current_mleaderstyle
    entities = document.entities + [
        e for b in document.blocks.values() for e in b.entities
    ]
    if operation == "add":
        if len(styles) >= 1000:
            raise ValueError("Use at most 1,000 multileader styles")
        if any(key.casefold() == name.casefold() for key in styles):
            raise ValueError("A style with that name already exists")
        styles[name] = copy.deepcopy(validate_style(value or styles[current]))
    elif name not in styles:
        raise ValueError("Multileader style does not exist")
    elif operation == "modify":
        styles[name] = copy.deepcopy(validate_style(value))
    elif operation == "current":
        current = name
    elif operation == "delete":
        if (
            name == "Standard"
            or name == current
            or any(e.kind == "MLEADER" and e.style_name == name for e in entities)
        ):
            raise ValueError(
                "Standard, current and referenced styles cannot be deleted"
            )
        del styles[name]
    else:
        raise ValueError("Unknown multileader style operation")
    for entity in entities:
        if entity.kind == "MLEADER":
            validate_record(vars(entity), styles, encoded=False)
    if styles != document.mleaderstyles or current != document.current_mleaderstyle:
        document.undo_stack.push(StyleTableCommand(document, styles, current))
