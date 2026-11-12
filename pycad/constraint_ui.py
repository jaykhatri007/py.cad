"""Point-driven constraint commands, a manager and viewport relation labels."""

import copy
import math
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QColor, QPen
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QPushButton,
    QInputDialog,
    QMessageBox,
    QDoubleSpinBox,
    QSpinBox,
    QCheckBox,
    QFormLayout,
)
from .tools import Tool
from .geometry import Point
from .geom_ops import pick_entity
from .constraints import (
    PARAMETERS,
    ConstraintChangeCommand,
    make_constraint,
    add_constraint,
    solve,
    anchor_point,
)

COMMAND_KINDS = {
    "GCCOINCIDENT": "coincident",
    "GCCOLLINEAR": "collinear",
    "GCCONCENTRIC": "concentric",
    "GCFIX": "fixed",
    "GCPARALLEL": "parallel",
    "GCPERPENDICULAR": "perpendicular",
    'GCTANGENT': 'tangent',
    "DCLINEAR": "linear",
    "DCALIGNED": "aligned",
    "DCANGULAR": "angular",
    "DCRADIUS": "radius",
    "DCDIAMETER": "diameter",
}
DRIVING = {"linear", "aligned", "angular", "radius", "diameter"}


class ConstraintTool(Tool):
    kind = "parallel"

    def __init__(self, mw):
        super().__init__(mw)
        self.refs = []
        self.axis = "x"
        self.await_value = False
        self.default = 1.0

    def status_prompt(self):
        if self.await_value:
            units = "degrees" if self.kind == "angular" else self.document.units
            axis = (
                f" {self.axis.upper()} component [X/Y]" if self.kind == "linear" else ""
            )
            return f"{self.name}:{axis} Enter driving value in {units} <{self.default:.6g}>"
        label = (
            "endpoint / center"
            if self.kind in ("coincident", "linear", "aligned")
            else "LINE"
            if self.kind in ("parallel", "perpendicular", "collinear", "angular")
            else "circle / arc"
            if self.kind in ("concentric", "radius", "diameter")
            else "LINE / CIRCLE or two CIRCLEs"
            if self.kind == 'tangent'
            else "LINE, POINT, CIRCLE or ARC"
        )
        return f"{self.name}: Pick {'first' if not self.refs else 'second'} {label} (persistent constraint)"

    def on_click(self, x, y, snap_kind, button):
        if button != Qt.MouseButton.LeftButton.value or self.await_value:
            return
        point_mode = self.kind in ("coincident", "linear", "aligned")
        candidates = [
            e for e in self.document.editable_entities() if e.kind in PARAMETERS
        ]
        if self.kind in ("parallel", "perpendicular", "collinear", "angular"):
            candidates = [e for e in candidates if e.kind == "LINE"]
        elif self.kind in ("concentric", "radius", "diameter"):
            candidates = [e for e in candidates if e.kind in ("CIRCLE", "ARC")]
        elif self.kind == 'tangent':
            candidates = [e for e in candidates if e.kind in ('LINE', 'CIRCLE')]
            if self.refs and self.document.find_by_id(self.refs[0]['entity']).kind == 'LINE':
                candidates = [e for e in candidates if e.kind == 'CIRCLE']
        tol = self.mw.canvas.snap_radius_px / self.mw.canvas.zoom
        pos = Point(x, y)
        if point_mode:
            possibilities = [
                (pos.distance_to(getattr(e, key)), e, key)
                for e in candidates
                for key in (
                    {
                        "LINE": ("p1", "p2"),
                        "POINT": ("point",),
                        "CIRCLE": ("center",),
                        "ARC": ("center",),
                    }[e.kind]
                )
            ]
            if not possibilities:
                return
            distance, e, key = min(possibilities, key=lambda row: row[0])
            if distance > tol:
                return
            ref = {"entity": e.id, "point": key}
        else:
            e = pick_entity(candidates, pos, tol)
            if e is None:
                return
            ref = {"entity": e.id}
        if ref in self.refs:
            raise ValueError("Choose a different object or endpoint")
        self.refs.append(ref)
        count = 1 if self.kind in ("fixed", "radius", "diameter") else 2
        if len(self.refs) < count:
            return
        if self.kind in DRIVING:
            self.await_value = True
            self.default = self.measure()
        else:
            self.commit()

    def measure(self):
        entities = [self.document.find_by_id(r["entity"]) for r in self.refs]
        if self.kind in ("radius", "diameter"):
            return entities[0].radius * (2 if self.kind == "diameter" else 1)
        if self.kind == "angular":
            a, b = entities
            u = (a.p2.x - a.p1.x, a.p2.y - a.p1.y)
            v = (b.p2.x - b.p1.x, b.p2.y - b.p1.y)
            return max(
                0.001,
                min(
                    179.999,
                    math.degrees(
                        math.atan2(
                            abs(u[0] * v[1] - u[1] * v[0]), u[0] * v[0] + u[1] * v[1]
                        )
                    ),
                ),
            )
        a, b = [anchor_point(e, r["point"]) for e, r in zip(entities, self.refs)]
        return max(
            1e-6,
            abs(getattr(b, self.axis) - getattr(a, self.axis))
            if self.kind == "linear"
            else a.distance_to(b),
        )

    def commit(self, value=None):
        constraint = make_constraint(
            self.document, self.kind, self.refs, value, self.axis
        )
        if add_constraint(self.document, constraint):
            self.mw.command_history.appendPlainText(
                f"Persistent {self.kind} constraint created. Use CONSTRAINTSETTINGS to edit driving values."
            )
            self.finish()
        else:
            self.refs = []
            self.await_value = False

    def on_text_input(self, text):
        if self.await_value:
            if self.kind == "linear" and text.upper() in ("X", "Y"):
                self.axis = text.lower()
                self.default = self.measure()
                return
            self.commit(float(text))
            return
        point = self.parse_point(text)
        if point:
            self.on_click(point.x, point.y, "", Qt.MouseButton.LeftButton.value)
        else:
            raise ValueError("Pick existing geometry or enter an endpoint coordinate")

    def on_key(self, key):
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self.await_value:
            self.commit(self.default)
        elif key == Qt.Key.Key_Escape:
            self.finish()


CONSTRAINT_TOOLS = {
    command: type(command + "Tool", (ConstraintTool,), {"name": command, "kind": kind})
    for command, kind in COMMAND_KINDS.items()
}


def toggle_visibility(mw):
    from .document import SetAttrCommand

    settings = dict(mw.document.constraint_settings)
    settings["show"] = not settings["show"]
    mw.document.undo_stack.push(
        SetAttrCommand(
            mw.document,
            mw.document,
            "constraint_settings",
            mw.document.constraint_settings,
            settings,
            "Constraint visibility",
        )
    )


def delete_constraints(mw):
    ids = {e.id for e in mw.canvas.selected_entities}
    if ids:
        records = [
            c
            for c in mw.document.constraints
            if not any(r["entity"] in ids for r in c["refs"])
        ]
    else:
        if not mw.document.constraints:
            return
        if (
            QMessageBox.question(
                mw,
                "Delete constraints",
                "Delete all constraints in this drawing? Geometry will keep its current shape.",
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        records = []
    mw.document.undo_stack.push(
        ConstraintChangeCommand(mw.document, records, "Delete constraints")
    )


def constraint_manager(mw):
    doc = mw.document
    dialog = QDialog(mw)
    dialog.setWindowTitle("Persistent 2D constraints")
    dialog.resize(770, 510)
    layout = QVBoxLayout(dialog)
    note = QLabel(
        "LINE endpoints, POINT entities and CIRCLE/ARC centers and radii. Conflicting edits are rejected. Constraints apply when an edit is committed; a drag preview may be temporarily unconstrained."
    )
    note.setWordWrap(True)
    layout.addWidget(note)
    report = QLabel()
    layout.addWidget(report)
    table = QTableWidget(0, 4)
    table.setHorizontalHeaderLabels(["Relation", "Driving value", "Objects", "ID"])
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    layout.addWidget(table)

    def refresh():
        table.setRowCount(len(doc.constraints))
        for row, c in enumerate(doc.constraints):
            for col, value in enumerate(
                (
                    c["kind"],
                    str(c.get("value", "—")),
                    ", ".join(
                        r["entity"][:8] + ("." + r["point"] if "point" in r else "")
                        for r in c["refs"]
                    ),
                    c["id"],
                )
            ):
                table.setItem(row, col, QTableWidgetItem(value))
        try:
            info = solve(doc, check_only=True)
            report.setText(
                f"{info['constraints']} relations · {info['free_dof']} remaining scalar degrees of freedom · residual {info['residual']:.3g}"
            )
        except ValueError as ex:
            report.setText(str(ex))

    row = QHBoxLayout()
    edit = QPushButton("Edit driving value…")
    remove = QPushButton("Delete selected relation")
    row.addWidget(edit)
    row.addWidget(remove)
    layout.addLayout(row)

    def edit_value():
        index = table.currentRow()
        if index < 0:
            return
        c = doc.constraints[index]
        if "value" not in c:
            report.setText(
                "This is a geometric relation. Select a dimensional relation to edit its value."
            )
            return
        value, ok = QInputDialog.getDouble(
            dialog,
            "Driving value",
            "Degrees:" if c["kind"] == "angular" else "Drawing units:",
            c["value"],
            0.000001,
            179.999999 if c["kind"] == "angular" else 1e9,
            6,
        )
        if ok:
            records = copy.deepcopy(doc.constraints)
            records[index]["value"] = value
            doc.undo_stack.push(
                ConstraintChangeCommand(doc, records, "Edit driving constraint")
            )
            refresh()

    def remove_relation():
        index = table.currentRow()
        if index >= 0:
            records = copy.deepcopy(doc.constraints)
            records.pop(index)
            doc.undo_stack.push(
                ConstraintChangeCommand(doc, records, "Delete constraint")
            )
            refresh()

    edit.clicked.connect(edit_value)
    remove.clicked.connect(remove_relation)
    form = QFormLayout()
    visible = QCheckBox()
    visible.setChecked(doc.constraint_settings["show"])
    tolerance = QDoubleSpinBox()
    tolerance.setDecimals(8)
    tolerance.setRange(1e-8, 0.001)
    tolerance.setValue(doc.constraint_settings["tolerance"])
    iterations = QSpinBox()
    iterations.setRange(20, 160)
    iterations.setValue(doc.constraint_settings["max_iterations"])
    form.addRow("Show relation labels", visible)
    form.addRow("Tolerance (drawing units)", tolerance)
    form.addRow("Maximum iterations", iterations)
    layout.addLayout(form)
    apply = QPushButton("Apply settings")
    layout.addWidget(apply)

    def apply_settings():
        from .document import SetAttrCommand

        settings = {
            "show": visible.isChecked(),
            "tolerance": tolerance.value(),
            "max_iterations": iterations.value(),
        }
        doc.undo_stack.push(
            SetAttrCommand(
                doc,
                doc,
                "constraint_settings",
                doc.constraint_settings,
                settings,
                "Constraint settings",
            )
        )
        refresh()

    apply.clicked.connect(apply_settings)
    close = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    close.rejected.connect(dialog.reject)
    layout.addWidget(close)
    refresh()
    dialog.exec()


def draw_constraints(painter, canvas):
    doc = canvas.document
    if not doc.constraint_settings["show"] or not doc.constraints:
        return
    painter.save()
    try:
        font = painter.font()
        font.setPixelSize(10)
        painter.setFont(font)
        occupied = {}
        for c in doc.constraints:
            refs = []
            for ref in c["refs"]:
                e = doc.find_by_id(ref["entity"])
                if e is None or not doc.layers.is_visible(e.layer):
                    continue
                if "point" in ref:
                    p = anchor_point(e, ref["point"])
                elif e.kind == "LINE":
                    p = Point((e.p1.x + e.p2.x) / 2, (e.p1.y + e.p2.y) / 2)
                else:
                    p = e.point if e.kind == "POINT" else e.center
                refs.append(canvas.world_to_screen(p.x, p.y))
            if not refs:
                continue
            x, y = (
                sum(p.x() for p in refs) / len(refs),
                sum(p.y() for p in refs) / len(refs),
            )
            tag = c["kind"] + (
                f" {c.get('axis', '')}={c['value']:.4g}" if "value" in c else ""
            )
            key = (round(x / 60), round(y / 20))
            offset = occupied.get(key, 0)
            occupied[key] = offset + 1
            rect = QRectF(
                x + 10,
                y + 8 + offset * 18,
                painter.fontMetrics().horizontalAdvance(tag) + 12,
                16,
            )
            painter.setPen(QPen(QColor("#69d3bb"), 1))
            painter.setBrush(QColor("#203d3d"))
            painter.drawRoundedRect(rect, 3, 3)
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, tag)
    finally:
        painter.restore()


def commands(mw):
    return {
        "CONSTRAINTBAR": lambda: toggle_visibility(mw),
        "DELCONSTRAINT": lambda: delete_constraints(mw),
        "CONSTRAINTSETTINGS": lambda: constraint_manager(mw),
    }
