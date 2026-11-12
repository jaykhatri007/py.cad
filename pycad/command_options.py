"""Context-sensitive keyword choices shared by typed and clicked command input."""

from dataclasses import dataclass
from html import escape


@dataclass(frozen=True)
class Option:
    key: str
    label: str
    enabled: bool = True
    aliases: tuple = ()


def options(mw):
    tool = mw.current_tool
    if tool is None:
        return []
    if tool.name == "SELECT":
        return [Option("ESC", "Cancel")] if getattr(mw.canvas, "navigation_zoom", False) or getattr(mw.canvas, "navigation_pan", False) else []
    name, points = tool.name, tool.points
    result = []
    if hasattr(tool, "keyword_options"):
        result = tool.keyword_options()
    elif name == "LINE":
        result = [Option("U", "Undo", bool(points)), Option("C", "Close", len(points) >= 3), Option("ENTER", "Finish")]
    elif name in ("PLINE", "SPLINE"):
        result = [Option("U", "Undo", bool(points)), Option("C", "Close", len(points) >= 3), Option("ENTER", "Finish", len(points) >= 2)]
    elif name == "HATCH":
        result = [Option("S", "Settings", aliases=("OPTIONS",)), Option("A", "Areas"), Option("C", "Combine"), Option("SEPARATE", "Separate"), Option("U", "Remove last area", bool(getattr(tool,"areas",[])), aliases=("UNDO","REMOVE")), Option("ENTER", "Apply areas", tool.boundary_points is not None)]
    elif name == "MIRROR" and tool.done_picking_axis:
        result = [Option("Y", "Yes", aliases=("YES",)), Option("N", "No", aliases=("NO",)), Option("ENTER", "Keep source")]
    elif name in ("TRIM", "EXTEND") and tool.picking_boundaries:
        result = [Option("ENTER", "Continue")]
    elif name == "DIMANGULAR":
        result = [Option("P", "Points"), Option("L", "Lines"), Option("A", "Arc")]
    elif name == "DIMORDINATE":
        result = [Option("X", "X axis"), Option("Y", "Y axis"), Option("O", "Origin")]
    elif getattr(tool, "await_value", False):
        if getattr(tool, "kind", "") == "linear":
            result = [Option("X", "X axis"), Option("Y", "Y axis")]
        result.append(Option("ENTER", "Accept default"))
    elif name == "MENUBAR":
        result = [Option("0", "Hide menus"), Option("1", "Show menus")]
    elif name == "AREA":
        result = [Option("ENTER", "Calculate", len(points) >= 3)]
    elif name == "COPY":
        result = [Option("ENTER", "Finish")]
    elif name in ("DIMCONTINUE", "DIMBASELINE"):
        result = [Option("ENTER", "Finish")]
    return [*result, Option("ESC", "Cancel")]


def resolve(mw, text):
    if mw.command_accepts_spaces():
        return None  # Text and block names remain literal.
    value = text.strip().upper()
    if not value:
        return None
    for option in options(mw):
        if value in (option.key, option.label.upper(), *option.aliases):
            return option
    return None


def markup(choices, dark=True, palette=None):
    accent = "#70d8ff" if dark else "#005ca8"
    muted = "#89939e" if dark else "#666666"
    if palette:
        accent, muted = palette['ui_command_option'], palette['ui_command_disabled']
    labels = []
    for option in choices:
        key, label = escape(option.key), escape(option.label)
        if option.label.upper().startswith(option.key) and option.key not in ("ENTER", "ESC"):
            label = f'<b><u>{label[:len(key)]}</u></b>{label[len(key):]}'
        else:
            label = f'<b><u>{key.title()}</u></b>: {label}'
        if option.enabled:
            label = f'<a href="{key}" style="color:{accent};text-decoration:none">{label}</a>'
        else:
            label = f'<span style="color:{muted}">{label}</span>'
        labels.append(label)
    return " &nbsp; | &nbsp; ".join(labels)
