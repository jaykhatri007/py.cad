"""Read-only measurements of the actual tool preview, rendered inside its viewport."""

import math
from dataclasses import dataclass
from PyQt6.QtCore import QEvent, QPoint, QRect, Qt
from PyQt6.QtWidgets import QFrame, QLabel, QGridLayout, QVBoxLayout
from .geometry import Point
from .units import format_length, format_angle, number


@dataclass
class Measurement:
    title: str
    values: list  # (label, full-precision value, length/angle/sweep/scalar)


def vector_values(start, end, label="Length", deltas=True):
    dx, dy = end.x - start.x, end.y - start.y
    values = [
        (label, math.hypot(dx, dy), "length"),
        ("Angle", math.degrees(math.atan2(dy, dx)) if dx or dy else 0.0, "angle"),
    ]
    if deltas:
        values += [("ΔX", dx, "length"), ("ΔY", dy, "length")]
    return values


def measurement_for(tool, current):
    if tool is None or current is None or not all(math.isfinite(v) for v in current):
        return None
    p = Point(*current)
    name = tool.name
    points = tool.points
    if name == "POLYGRIP":
        entity=tool.candidate or tool.source;i=tool.index;values=[]
        if tool.operation=='vertex':
            for label,j in (("Previous edge",i-1),("Next edge",i+1)):
                if entity.closed or 0<=j<len(entity.points):
                    from .precision import arc_data
                    segment=(i-1)%len(entity.points) if j<i else i
                    a,b=entity.points[segment],entity.points[(segment+1)%len(entity.points)]
                    data=arc_data(a,b,entity.bulges[segment])
                    values.append((label,abs(data[1]*data[3]) if data else a.distance_to(b),"length"))
        elif tool.operation=='arc':
            from .precision import arc_data
            data=arc_data(entity.points[i],entity.points[(i+1)%len(entity.points)],entity.bulges[i])
            if data:values=[("Radius",data[1],"length"),("Sweep",abs(math.degrees(data[3])),"sweep"),("Arc length",abs(data[1]*data[3]),"length")]
        values+=vector_values(tool.points[0],p,"Movement",False)
        return Measurement("Polyline grip · preview",values)
    if name == "SELECT":
        entity = tool.grip_entity
        if entity is not None:
            title = "Grip stretch · preview"
            if entity.kind == "LINE":
                return Measurement(title, vector_values(entity.p1, entity.p2))
            if entity.kind == "CIRCLE" and tool.grip_kind == "radius":
                return Measurement(
                    title,
                    [
                        ("Radius", entity.radius, "length"),
                        ("Diameter", entity.radius * 2, "length"),
                    ],
                )
            if entity.kind == "ARC" and tool.grip_kind in ("start", "end"):
                sweep = (entity.end_angle - entity.start_angle) % 360
                return Measurement(
                    title,
                    [
                        ("Radius", entity.radius, "length"),
                        ("Sweep", sweep, "sweep"),
                        ("Arc length", entity.radius * math.radians(sweep), "length"),
                        ("Angle", getattr(entity, tool.grip_kind + "_angle"), "angle"),
                    ],
                )
            if entity.kind in ("LWPOLYLINE", "RECTANGLE") and tool.grip_kind.startswith(
                "pt"
            ):
                i = int(tool.grip_kind[2:])
                values = []
                for label, j in (("Previous edge", i - 1), ("Next edge", i + 1)):
                    if entity.closed or 0 <= j < len(entity.points):
                        values.append(
                            (
                                label,
                                entity.points[i].distance_to(
                                    entity.points[j % len(entity.points)]
                                ),
                                "length",
                            )
                        )
                if tool.grip_old_xy:
                    values += vector_values(
                        Point(*tool.grip_old_xy), p, "Movement", False
                    )
                return Measurement(title, values)
            if tool.grip_old_xy:
                return Measurement(
                    "Grip move · preview",
                    vector_values(Point(*tool.grip_old_xy), p, "Movement"),
                )
            return None
        if tool.dragging_entity and tool.drag_origin:
            return Measurement(
                "Move · preview", vector_values(tool.drag_origin, p, "Movement")
            )
        return None
    if name in ("MOVE", "COPY", "ROTATE", "SCALE"):
        base = tool.base_point
        if base is None:
            return None
        values = vector_values(
            base, p, "Movement" if name in ("MOVE", "COPY") else "Reference"
        )
        if name == "ROTATE":
            values = [values[1]]
        elif name == "SCALE" and tool.ref_points:
            ref = base.distance_to(tool.ref_points[0])
            if ref > 1e-9:
                values = [("Factor", base.distance_to(p) / ref, "scalar"), values[0]]
        return Measurement(name.title() + " · preview", values)
    if name == "STRETCH":
        if len(points) != 3:
            return None
        values = vector_values(points[2], p, "Movement")
        identities = {id(v) for v in tool.vertices}
        lines = [
            e
            for e in tool.document.entities
            if e.kind == "LINE" and (id(e.p1) in identities or id(e.p2) in identities)
        ]
        if len(lines) == 1:
            dx, dy = p.x - points[2].x, p.y - points[2].y
            line = lines[0]
            ends = [
                Point(v.x + dx, v.y + dy) if id(v) in identities else v
                for v in (line.p1, line.p2)
            ]
            values.append(("New length", ends[0].distance_to(ends[1]), "length"))
        return Measurement("Stretch · preview", values)
    if name in ("DIMANGULAR", "DIMARC") and (len(points) == 3 or len(getattr(tool, 'line_ids', [])) == 2):
        try:
            entity = tool._entity(p)
        except ValueError:
            return None
        return Measurement(name + " · preview", [
            ("Angle" if name == "DIMANGULAR" else "Arc length", entity.measurement(), "sweep" if name == "DIMANGULAR" else "length"),
            ("Dimension radius", entity.center.distance_to(p), "length"),
        ])
    if name == "DIMORDINATE" and points and not tool.origin_pending:
        try:
            entity = tool._entity(p)
        except ValueError:
            return None
        return Measurement("Ordinate · preview", [
            (entity.dim_style[-1].upper() + " coordinate", entity.measurement(), "length"),
            ("Datum X", tool.origin.x, "length"), ("Datum Y", tool.origin.y, "length"),
        ])
    if not points:
        return None
    if name in ('MLEADER', 'MLEADERADD'):
        label = 'Arrow leg' if len(points) == 1 else 'Text offset'
        return Measurement(name + ' · preview', vector_values(points[-1], p, label))
    if name in ("LINE", "PLINE", "DIST", "RAY", "XLINE", "SPLINE", "UNDERLAYCALIBRATE"):
        label = (
            "Next chord"
            if name == "SPLINE"
            else "Distance"
            if name in ("DIST", "RAY", "XLINE")
            else "Length"
        )
        return Measurement(name + " · preview", vector_values(points[-1], p, label))
    if name == "RECTANGLE":
        dx, dy = abs(p.x - points[0].x), abs(p.y - points[0].y)
        return Measurement(
            "Rectangle · preview",
            [
                ("Width", dx, "length"),
                ("Height", dy, "length"),
                ("Diagonal", math.hypot(dx, dy), "length"),
                ("Perimeter", 2 * (dx + dy), "length"),
            ],
        )
    if name == "CIRCLE":
        radius = points[0].distance_to(p)
        return Measurement(
            "Circle · preview",
            [("Radius", radius, "length"), ("Diameter", 2 * radius, "length")],
        )
    if name == "ARC":
        center = points[0]
        if len(points) == 1:
            return Measurement(
                "Arc start · preview", vector_values(center, p, "Radius", False)
            )
        radius = center.distance_to(points[1])
        start = math.atan2(points[1].y - center.y, points[1].x - center.x)
        end = math.atan2(p.y - center.y, p.x - center.x)
        sweep = math.degrees(end - start) % 360
        return Measurement(
            "Arc end · preview",
            [
                ("Radius", radius, "length"),
                ("Sweep", sweep, "sweep"),
                ("Arc length", radius * math.radians(sweep), "length"),
                ("End angle", math.degrees(end), "angle"),
            ],
        )
    if name == "ELLIPSE":
        radius = points[0].distance_to(p)
        if len(points) == 1:
            return Measurement(
                "Ellipse axis · preview",
                vector_values(points[0], p, "Axis radius", False),
            )
        return Measurement(
            "Ellipse · preview",
            [
                ("First radius", points[0].distance_to(points[1]), "length"),
                ("Second radius", radius, "length"),
            ],
        )
    return None


def formatted_values(measurement, doc):
    result = []
    for label, value, kind in measurement.values:
        if kind == "length":
            text = format_length(value, doc.units, doc.unit_settings)
        elif kind in ("angle", "sweep"):
            text = format_angle(value, doc.unit_settings, normalize=kind == "angle")
        else:
            text = number(value, 4, True) + "×"
        result.append((label, text))
    return result


def overlay_rect(pointer, size, bounds, avoid=None):
    """Clamp to the viewport and prefer a quadrant clear of the command prompt."""
    avoid_rects = [] if avoid is None else list(avoid) if isinstance(avoid,(list,tuple)) else [avoid]
    width, height = size.width(), size.height()
    x, y = pointer.x(), pointer.y()
    candidates = []
    positions = [(x+18,y+22),(x+18,y-height-14),(x-width-18,y+22),(x-width-18,y-height-14)]
    for q in avoid_rects:
        positions += [(x+18,q.bottom()+10),(x+18,q.top()-height-10),
                      (q.right()+10,y+22),(q.left()-width-10,y+22)]
    for xx, yy in positions:
        rect = QRect(
            max(4, min(xx, bounds.width() - width - 4)),
            max(4, min(yy, bounds.height() - height - 4)),
            width,
            height,
        )
        if not any(rect.intersects(q.adjusted(-5,-5,5,5)) for q in avoid_rects):
            return rect
        candidates.append(rect)
    # An extremely small viewport cannot show two panels; the command input wins.
    return None if avoid_rects else candidates[0]


class MeasurementOverlay(QFrame):
    def __init__(self, window, viewport):
        super().__init__(viewport)
        self.mw, self.viewport = window, viewport
        self.pointer = QPoint(0, 0)
        self.inside = False
        self.measurement = None
        self.display_values = []
        self.setObjectName("live_measurements_overlay")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setStyleSheet("""
            QFrame#live_measurements_overlay { background:#132b34; border:1px solid #4eabae; border-radius:4px; }
            QLabel { border:0; background:transparent; font-size:11px; color:#a9c5ce; }
            QLabel[measurementValue="true"] { color:#e4fff6; font-size:13px; font-weight:600; }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 5, 8, 6)
        layout.setSpacing(4)
        self.title = QLabel()
        layout.addWidget(self.title)
        grid = QGridLayout()
        grid.setHorizontalSpacing(7)
        grid.setVerticalSpacing(3)
        self.cells = []
        for i in range(6):
            label, value = QLabel(), QLabel()
            for item in (label, value):
                item.setTextFormat(Qt.TextFormat.PlainText)
                item.setMinimumWidth(0)
            value.setProperty("measurementValue", True)
            value.setWordWrap(True)
            value.setAlignment(Qt.AlignmentFlag.AlignRight|Qt.AlignmentFlag.AlignVCenter)
            grid.addWidget(label, i, 0)
            grid.addWidget(value, i, 1)
            self.cells.append((label, value))
        grid.setColumnStretch(1,1)
        layout.addLayout(grid)
        self.hide()
        viewport.installEventFilter(self)
        window.command_line.textChanged.connect(self.refresh)

    def refresh(self, *_):
        canvas = self.mw.canvas
        self.measurement = measurement_for(
            self.mw.current_tool, self.mw.current_world_pos
        )
        if (
            not self.inside
            or not self.viewport.isVisible()
            or canvas.document.current_space != "Model"
            or not self.mw.cursor_dimensions_action.isChecked()
            or canvas._panning
            or getattr(canvas, "navigation_pan", False)
            or getattr(canvas, "navigation_zoom", False)
            or self.measurement is None
        ):
            self.hide()
            return
        self.title.setText(
            self.measurement.title
            + (" · constrained" if canvas.document.constraints else "")
        )
        self.display_values = formatted_values(self.measurement, canvas.document)
        # Keep primary values readable; offsets remain available in the tooltip.
        shown = [(label,text) for label,text in self.display_values if label not in ("ΔX","ΔY")]
        desired = max((self.fontMetrics().horizontalAdvance(label)+self.fontMetrics().horizontalAdvance(text)+55 for label,text in shown), default=160)
        width = max(100,min(320,desired,self.viewport.width()-12))
        self.setFixedWidth(width)
        self.setToolTip("\n".join(label+": "+text for label,text in self.display_values))
        for i, (label, value) in enumerate(self.cells):
            active = i < len(shown)
            label.setVisible(active)
            value.setVisible(active)
            if active:
                caption, text = shown[i]
                label.setText(caption)
                value.setToolTip(text)
                value.setText(text)
        self.adjustSize()
        avoid = []
        for other in (getattr(canvas,"command_overlay",None),getattr(canvas,"dynamic_input",None)):
            if other is not None and other.isVisible():avoid.append(other.geometry())
        rect = overlay_rect(self.pointer, self.size(), self.viewport.rect(), avoid)
        if (
            rect is None
            or rect.width() > self.viewport.width() - 8
            or rect.height() > self.viewport.height() - 8
        ):
            self.hide()
            return
        self.setGeometry(rect)
        self.show()
        self.raise_()

    def eventFilter(self, obj, event):
        if not hasattr(self, 'viewport'):
            return False
        if obj is self.viewport:
            if event.type() == QEvent.Type.MouseMove:
                self.pointer = event.position().toPoint()
                self.inside = True
            elif event.type() == QEvent.Type.Enter:
                self.inside = True
                self.pointer = event.position().toPoint()
                self.refresh()
            elif event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                self.inside = True
                self.pointer = event.position().toPoint()
            elif event.type() in (QEvent.Type.Leave, QEvent.Type.Hide):
                self.inside = False
                self.hide()
            elif event.type() == QEvent.Type.Resize:
                self.refresh()
            elif (
                event.type() == QEvent.Type.MouseButtonPress
                and event.button() == Qt.MouseButton.MiddleButton
            ):
                self.hide()
        return super().eventFilter(obj, event)
