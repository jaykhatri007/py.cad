"""Named dimension styles and shared world-space annotation geometry."""

import copy
import math
from .geometry import Point

DEFAULT_STYLE = dict(
    text_height=2.5,
    arrow_size=2.5,
    text_gap=0.8,
    extension_offset=0.6,
    extension_beyond=1.2,
    scale=1.0,
    precision=2,
    prefix="",
    suffix="",
    arrow_type="Closed",
    color="BYLAYER",
    suppress_zeros=False,
)


def validate_style(style):
    from .validation import color

    if not isinstance(style, dict) or set(style) != set(DEFAULT_STYLE):
        raise ValueError("Invalid dimension style fields")
    for key in (
        "text_height",
        "arrow_size",
        "text_gap",
        "extension_offset",
        "extension_beyond",
        "scale",
    ):
        value = style[key]
        if (
            type(value) not in (int, float)
            or not math.isfinite(value)
            or value < 0
            or value > 1e6
        ):
            raise ValueError(
                f"{key} must be a finite non-negative value no larger than 1,000,000"
            )
        if key in ("text_height", "arrow_size", "scale") and value == 0:
            raise ValueError(f"{key} must be positive")
    if type(style["precision"]) is not int or not 0 <= style["precision"] <= 8:
        raise ValueError("Precision must be 0–8")
    for key in ("prefix", "suffix"):
        if (
            not isinstance(style[key], str)
            or len(style[key]) > 64
            or any(ord(c) < 32 for c in style[key])
        ):
            raise ValueError(
                "Prefix and suffix must be at most 64 printable characters"
            )
    if style["arrow_type"] not in ("Closed", "Open", "Tick"):
        raise ValueError("Unknown arrow type")
    if type(style["suppress_zeros"]) is not bool:
        raise ValueError("Zero suppression must be boolean")
    color(style["color"])
    return style


def style_for(document, entity):
    return document.dimstyles.get(entity.style_name, DEFAULT_STYLE)


def dimension_label(entity, style):
    number = f"{entity.measurement():.{style['precision']}f}"
    if style["suppress_zeros"] and "." in number:
        number = number.rstrip("0").rstrip(".")
    if number.startswith("-") and float(number) == 0:
        number = number[1:]
    symbol = (
        "R"
        if entity.dim_style == "radius"
        else "\u2300"
        if entity.dim_style == "diameter"
        else ""
    )
    label = style["prefix"] + symbol + number + style["suffix"]
    if entity.dim_style == 'angular':
        label = style['prefix'] + number + '°' + style['suffix']
    elif entity.dim_style == 'arc_length':
        label = style['prefix'] + '⌒' + number + style['suffix']
    return (
        entity.text_override.replace("<>", label)
        if entity.text_override is not None
        else label
    )


def dimension_geometry(entity, style):
    """Return lines, arrow triangles, text anchor and text height in model units.

    Canvas, PDF and DXF consume the same primitives so style edits propagate.
    Text is horizontal. Short spans place labels and arrow bases outside automatically.
    """
    if entity.kind == 'CURVED_DIMENSION':
        from .curved_dimensions import curved_geometry
        return curved_geometry(entity, style)
    if entity.kind == 'ORDINATE_DIMENSION':
        from .ordinate_dimensions import ordinate_geometry
        return ordinate_geometry(entity, style)
    factor = style["scale"]
    size = style["arrow_size"] * factor
    gap = style["text_gap"] * factor
    lines, fills = [], []
    a, b = entity.dimension_line_points()

    def arrow(tip, toward):
        dx, dy = toward.x - tip.x, toward.y - tip.y
        length = math.hypot(dx, dy)
        if length < 1e-12:
            return
        ux, uy = dx / length, dy / length
        p = Point(
            tip.x + ux * size - uy * size * 0.35, tip.y + uy * size + ux * size * 0.35
        )
        q = Point(
            tip.x + ux * size + uy * size * 0.35, tip.y + uy * size - ux * size * 0.35
        )
        if style["arrow_type"] == "Closed":
            fills.append([tip, p, q])
        elif style["arrow_type"] == "Open":
            lines.extend([(tip, p), (tip, q)])
        else:
            dx, dy = (ux - uy) * size * 0.4, (uy + ux) * size * 0.4
            lines.append((Point(tip.x - dx, tip.y - dy), Point(tip.x + dx, tip.y + dy)))

    estimated_width=len(dimension_label(entity,style))*style['text_height']*factor*.7
    fit_outside=entity.dim_style not in ('radius','diameter') and a.distance_to(b)<estimated_width+2*size+2*gap
    lines.append((a,b))
    if fit_outside:
        dx,dy=b.x-a.x,b.y-a.y
        arrow(a,Point(a.x-dx,a.y-dy))
    else: arrow(a,b)
    if entity.dim_style in ("radius", "diameter"):
        anchor = Point(b.x + gap, b.y + gap)
    else:
        arrow(b,Point(b.x+(b.x-a.x),b.y+(b.y-a.y)) if fit_outside else a)
        for source, target in ((entity.p1, a), (entity.p2, b)):
            dx, dy = target.x - source.x, target.y - source.y
            length = math.hypot(dx, dy)
            if length > 1e-12:
                ux, uy = dx / length, dy / length
                offset = min(style["extension_offset"] * factor, length)
                beyond = style["extension_beyond"] * factor
                lines.append(
                    (
                        Point(source.x + ux * offset, source.y + uy * offset),
                        Point(target.x + ux * beyond, target.y + uy * beyond),
                    )
                )
        if fit_outside:
            anchor=Point(b.x+gap+estimated_width/2,b.y+gap)
            lines.append((b,Point(b.x+gap+estimated_width,b.y)))
        else: anchor = Point((a.x + b.x) / 2, (a.y + b.y) / 2 + gap)
    return lines, fills, anchor, style["text_height"] * factor


def edit_style(document, operation, name, value=None):
    from .table_commands import StyleTableCommand
    from .validation import name as valid_name

    valid_name(name, "Style name")
    styles = copy.deepcopy(document.dimstyles)
    current = document.current_dimstyle
    if operation == "add":
        if any(key.casefold() == name.casefold() for key in styles):
            raise ValueError("A style with that name already exists")
        styles[name] = copy.deepcopy(value if value is not None else styles[current])
        validate_style(styles[name])
    elif name not in styles:
        raise ValueError("Dimension style does not exist")
    elif operation == "modify":
        styles[name] = copy.deepcopy(validate_style(value))
    elif operation == "current":
        current = name
    elif operation == "delete":
        entities = document.entities + [
            e for b in document.blocks.values() for e in b.entities
        ]
        if (
            name == "Standard"
            or name == current
            or any(getattr(e, "style_name", None) == name for e in entities)
        ):
            raise ValueError(
                "Standard, current, and referenced styles cannot be deleted"
            )
        del styles[name]
    else:
        raise ValueError("Unknown style operation")
    if styles != document.dimstyles or current != document.current_dimstyle:
        document.undo_stack.push(StyleTableCommand(document, styles, current))
