"""Persistent, bounded 2D sketch constraints and atomic undo integration.

The solver uses normalized coordinates and a damped least-squares projection.
It supports explicit LINE, POINT, CIRCLE and ARC entities, not a B-rep kernel.
Failed transactions restore geometry and constraints without entering history.
"""

import copy
import math
import uuid

import numpy as np
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QUndoStack, QUndoCommand

KINDS = {
    "coincident",
    "collinear",
    "concentric",
    "fixed",
    "parallel",
    "perpendicular",
    'tangent',
    "linear",
    "aligned",
    "angular",
    "radius",
    "diameter",
}
PARAMETERS = {"LINE": 4, "POINT": 2, "CIRCLE": 3, "ARC": 5}
DEFAULT_SETTINGS = {"show": True, "tolerance": 1e-6, "max_iterations": 80}
MAX_CONSTRAINTS = 80
MAX_VARIABLES = 256


class ConstraintError(ValueError):
    pass


def parameters(entity):
    if entity.kind == "LINE":
        return [entity.p1.x, entity.p1.y, entity.p2.x, entity.p2.y]
    if entity.kind == "POINT":
        return [entity.point.x, entity.point.y]
    if entity.kind in ("CIRCLE", "ARC"):
        values = [entity.center.x, entity.center.y, entity.radius]
        if entity.kind == "ARC":
            values += [entity.start_angle, entity.end_angle]
        return values
    return None


def set_parameters(entity, values):
    if entity.kind == "LINE":
        entity.p1.x, entity.p1.y, entity.p2.x, entity.p2.y = values
    elif entity.kind == "POINT":
        entity.point.x, entity.point.y = values
    else:
        entity.center.x, entity.center.y, entity.radius = values[:3]
        if entity.kind == "ARC":
            entity.start_angle, entity.end_angle = values[3:]


def geometry_state(doc):
    return {e.id: parameters(e) for e in doc.entities if e.kind in PARAMETERS}


def restore_geometry(doc, state):
    for e in doc.entities:
        if e.id in state and e.kind in PARAMETERS:
            set_parameters(e, state[e.id])
    doc.spatial_index.invalidate()


def validate_settings(settings):
    if not isinstance(settings, dict) or set(settings) != set(DEFAULT_SETTINGS):
        raise ConstraintError("Invalid constraint settings")
    if type(settings["show"]) is not bool:
        raise ConstraintError("Constraint visibility must be boolean")
    tol = settings["tolerance"]
    if (
        type(tol) not in (int, float)
        or not math.isfinite(tol)
        or not 1e-8 <= tol <= 0.001
    ):
        raise ConstraintError(
            "Constraint tolerance must be between 1e-8 and .001 drawing units"
        )
    if (
        type(settings["max_iterations"]) is not int
        or not 20 <= settings["max_iterations"] <= 160
    ):
        raise ConstraintError("Solver iteration limit must be 20–160")


def validate_records(records, entity_kinds):
    if not isinstance(records, list) or len(records) > MAX_CONSTRAINTS:
        raise ConstraintError(
            f"A sketch supports at most {MAX_CONSTRAINTS} constraints"
        )
    ids, referenced = set(), set()
    for c in records:
        if (
            not isinstance(c, dict)
            or not isinstance(c.get("kind"), str)
            or c.get("kind") not in KINDS
        ):
            raise ConstraintError("Unknown constraint kind")
        kind = c["kind"]
        fields = {"id", "kind", "refs"}
        if kind in ("linear", "aligned", "angular", "radius", "diameter"):
            fields.add("value")
        if kind in ("parallel", "perpendicular", "collinear", "angular"):
            fields.add("orientation")
        if kind == "linear":
            fields |= {"axis", "sign"}
        if kind == "fixed":
            fields.add("fixed")
        if kind == 'tangent':
            fields.add('mode')
        if set(c) != fields:
            raise ConstraintError("Invalid constraint fields")
        if (
            not isinstance(c["id"], str)
            or not 1 <= len(c["id"]) <= 128
            or c["id"] in ids
        ):
            raise ConstraintError("Invalid or duplicate constraint ID")
        ids.add(c["id"])
        count = 1 if kind in ("fixed", "radius", "diameter") else 2
        if not isinstance(c["refs"], list) or len(c["refs"]) != count:
            raise ConstraintError("Invalid constraint references")
        for ref in c["refs"]:
            point_ref = kind in ("coincident", "linear", "aligned")
            if not isinstance(ref, dict) or set(ref) != (
                {"entity", "point"} if point_ref else {"entity"}
            ):
                raise ConstraintError("Invalid constraint reference")
            key = ref["entity"]
            if (
                not isinstance(key, str)
                or key not in entity_kinds
                or entity_kinds[key] not in PARAMETERS
            ):
                raise ConstraintError(
                    "Constraint references a missing or unsupported entity"
                )
            referenced.add(key)
            shape = entity_kinds[key]
            if (
                point_ref
                and ref["point"]
                not in {
                    "LINE": ("p1", "p2"),
                    "POINT": ("point",),
                    "CIRCLE": ("center",),
                    "ARC": ("center",),
                }[shape]
            ):
                raise ConstraintError("Invalid constraint point")
            if (
                kind in ("parallel", "perpendicular", "collinear", "angular")
                and shape != "LINE"
            ):
                raise ConstraintError("This relation requires LINE entities")
            if kind in ("concentric", "radius", "diameter") and shape not in (
                "CIRCLE",
                "ARC",
            ):
                raise ConstraintError("This relation requires circles or arcs")
        if count == 2 and c["refs"][0] == c["refs"][1]:
            raise ConstraintError("Pick two distinct objects or points")
        if kind == 'tangent':
            shapes = [entity_kinds[r['entity']] for r in c['refs']]
            if shapes not in (['LINE','CIRCLE'], ['CIRCLE','LINE'], ['CIRCLE','CIRCLE']):
                raise ConstraintError('Tangent supports LINE/CIRCLE and CIRCLE/CIRCLE pairs')
            if c['mode'] not in ('left', 'right', 'external', 'internal'):
                raise ConstraintError('Invalid tangency mode')
            if ('LINE' in shapes) != (c['mode'] in ('left', 'right')):
                raise ConstraintError('Tangency mode does not match objects')
        if "orientation" in c and (
            type(c["orientation"]) is not int or c["orientation"] not in (-1, 1)
        ):
            raise ConstraintError("Invalid relation orientation")
        if "value" in c:
            v = c["value"]
            if type(v) not in (int, float) or not math.isfinite(v) or not 0 < v <= 1e9:
                raise ConstraintError(
                    "Driving values must be positive finite numbers up to 1e9"
                )
            if kind == "angular" and v >= 180:
                raise ConstraintError(
                    "Angular constraints must be greater than 0 and less than 180 degrees"
                )
        if kind == "linear" and (
            c["axis"] not in ("x", "y")
            or type(c["sign"]) is not int
            or c["sign"] not in (-1, 1)
        ):
            raise ConstraintError("Invalid linear constraint direction")
        if kind == "fixed":
            vals = c["fixed"]
            if (
                not isinstance(vals, list)
                or len(vals) != PARAMETERS[entity_kinds[c["refs"][0]["entity"]]]
            ):
                raise ConstraintError("Invalid fixed geometry")
            if any(
                type(v) not in (int, float) or not math.isfinite(v) or abs(v) > 1e12
                for v in vals
            ):
                raise ConstraintError("Invalid fixed geometry values")
    if sum(PARAMETERS[entity_kinds[k]] for k in referenced) > MAX_VARIABLES:
        raise ConstraintError(
            f"Constrained sketches are limited to {MAX_VARIABLES} scalar parameters"
        )


def make_constraint(doc, kind, refs, value=None, axis="x"):
    c = {"id": uuid.uuid4().hex, "kind": kind, "refs": copy.deepcopy(refs)}
    entities = {e.id: e for e in doc.entities}
    if kind in ("linear", "aligned", "angular", "radius", "diameter"):
        c["value"] = value
    if kind == "fixed":
        c["fixed"] = parameters(entities[refs[0]["entity"]])
    if kind in ("parallel", "perpendicular", "collinear", "angular"):
        a, b = [entities[r["entity"]] for r in refs]
        ax, ay = a.p2.x - a.p1.x, a.p2.y - a.p1.y
        bx, by = b.p2.x - b.p1.x, b.p2.y - b.p1.y
        dot, cross = ax * bx + ay * by, ax * by - ay * bx
        c["orientation"] = (
            1 if (dot if kind in ("parallel", "collinear") else cross) >= 0 else -1
        )
    if kind == "linear":
        a, b = [anchor_point(entities[r["entity"]], r["point"]) for r in refs]
        c.update(axis=axis, sign=1 if getattr(b, axis) - getattr(a, axis) >= 0 else -1)
    if kind == 'tangent':
        a, b = [entities[r['entity']] for r in refs]
        if a.kind == 'LINE' or b.kind == 'LINE':
            line, circle = (a,b) if a.kind == 'LINE' else (b,a)
            if circle.kind != 'CIRCLE': raise ConstraintError('Pick a LINE and CIRCLE or two CIRCLEs')
            cross = (line.p2.x-line.p1.x)*(circle.center.y-line.p1.y)-(line.p2.y-line.p1.y)*(circle.center.x-line.p1.x)
            c['mode'] = 'left' if cross >= 0 else 'right'
        elif a.kind == b.kind == 'CIRCLE':
            distance = a.center.distance_to(b.center)
            c['mode'] = 'external' if abs(distance-a.radius-b.radius) <= abs(distance-abs(a.radius-b.radius)) else 'internal'
            if c['mode'] == 'internal' and abs(a.radius-b.radius) <= 1e-12:
                raise ConstraintError('Internal tangency requires circles of different radii')
        else: raise ConstraintError('Pick a LINE and CIRCLE or two CIRCLEs')
    validate_records([c], {e.id: e.kind for e in doc.entities})
    return c


def anchor_point(entity, key):
    return getattr(entity, key)


def solve(doc, pins=None, check_only=False):
    """Project the current sketch onto its constraints. No mutation until success."""
    records = doc.constraints
    if not records:
        return {
            "constraints": 0,
            "variables": 0,
            "rank": 0,
            "free_dof": 0,
            "residual": 0.0,
        }
    kinds = {e.id: e.kind for e in doc.entities}
    validate_records(records, kinds)
    validate_settings(doc.constraint_settings)
    keys = sorted({r["entity"] for c in records for r in c["refs"]})
    entities = {e.id: e for e in doc.entities if e.id in keys}
    raw = {k: parameters(entities[k]) for k in keys}
    origins = [v[:2] for v in raw.values()]
    origin = np.mean(origins, axis=0)
    sizes = [
        math.hypot(v[2] - v[0], v[3] - v[1]) if kinds[k] == "LINE" else v[2]
        for k, v in raw.items()
        if kinds[k] in ("LINE", "CIRCLE", "ARC")
    ]
    scale = max(1.0, float(np.median(sizes)) if sizes else 1.0)
    slots, shift, unit, flat = {}, [], [], []
    for key in keys:
        slots[key] = slice(len(flat), len(flat) + len(raw[key]))
        for i, v in enumerate(raw[key]):
            coordinate = i < (4 if kinds[key] == "LINE" else 2)
            shift.append(float(origin[i % 2]) if coordinate else 0.0)
            unit.append(
                scale if i < (4 if kinds[key] == "LINE" else 3) else 180 / math.pi
            )
            flat.append(v)
    shift, unit = np.array(shift), np.array(unit)
    start = (np.array(flat) - shift) / unit
    pinned = {}
    for (key, index), value in (pins or {}).items():
        if key in slots:
            n = slots[key].start + index
            pinned[n] = (value - shift[n]) / unit[n]
    # Locked/frozen/hidden constrained geometry cannot be moved indirectly.
    for key, e in entities.items():
        if doc.layers.is_locked(e.layer) or not doc.layers.is_visible(e.layer):
            for n in range(slots[key].start, slots[key].stop):
                pinned[n] = start[n]

    def point(x, ref):
        vals = x[slots[ref["entity"]]]
        return vals[2:4] if ref.get("point") == "p2" else vals[:2]

    def residual(x, include_pins=True):
        result = []
        for c in records:
            kind, refs = c["kind"], c["refs"]
            a = x[slots[refs[0]["entity"]]]
            if kind in ("coincident", "linear", "aligned"):
                d = point(x, refs[1]) - point(x, refs[0])
                if kind == "coincident":
                    result.extend(d)
                elif kind == "linear":
                    result.append(
                        d[0 if c["axis"] == "x" else 1] - c["sign"] * c["value"] / scale
                    )
                else:
                    result.append(float(np.linalg.norm(d)) - c["value"] / scale)
            elif kind == "concentric":
                result.extend(x[slots[refs[1]["entity"]]][:2] - a[:2])
            elif kind in ("radius", "diameter"):
                result.append(
                    a[2] - c["value"] / scale / (2 if kind == "diameter" else 1)
                )
            elif kind == "fixed":
                sl = slots[refs[0]["entity"]]
                result.extend(a - (np.array(c["fixed"]) - shift[sl]) / unit[sl])
            elif kind == 'tangent':
                b = x[slots[refs[1]['entity']]]
                if kinds[refs[0]['entity']] == 'LINE' or kinds[refs[1]['entity']] == 'LINE':
                    line, circle = (a,b) if kinds[refs[0]['entity']] == 'LINE' else (b,a)
                    u = line[2:4]-line[:2]; delta = circle[:2]-line[:2]
                    signed = (u[0]*delta[1]-u[1]*delta[0])/max(float(np.linalg.norm(u)), 1e-12)
                    result.append(signed-circle[2]*(1 if c['mode']=='left' else -1))
                else:
                    distance = float(np.linalg.norm(a[:2]-b[:2]))
                    result.append(distance-(a[2]+b[2] if c['mode']=='external' else abs(a[2]-b[2])))
            else:
                b = x[slots[refs[1]["entity"]]]
                u, v = a[2:4] - a[:2], b[2:4] - b[:2]
                cross = u[0] * v[1] - u[1] * v[0]
                dot = float(u @ v)
                target = (
                    0
                    if kind in ("parallel", "collinear")
                    else c["orientation"]
                    * (
                        math.pi / 2
                        if kind == "perpendicular"
                        else math.radians(c["value"])
                    )
                )
                angle = math.atan2(cross, dot)
                if kind in ("parallel", "collinear") and c["orientation"] < 0:
                    target = math.pi
                result.append(
                    math.atan2(math.sin(angle - target), math.cos(angle - target))
                )
                if kind == "collinear":
                    delta = b[:2] - a[:2]
                    result.append(
                        (u[0] * delta[1] - u[1] * delta[0])
                        / max(float(np.linalg.norm(u)), 1e-12)
                    )
        if include_pins:
            result.extend(x[i] - v for i, v in pinned.items())
        return np.array(result, dtype=float)

    def valid(x):
        if not np.all(np.isfinite(x)) or np.any(np.abs(x * unit + shift) > 1e12):
            return False
        for key in keys:
            a = x[slots[key]]
            if kinds[key] == "LINE" and float(np.linalg.norm(a[2:4] - a[:2])) < 1e-8:
                return False
            if kinds[key] in ("CIRCLE", "ARC") and a[2] < 1e-8:
                return False
        for record in records:
            if record['kind'] == 'tangent' and record['mode'] == 'internal':
                a, b = [x[slots[r['entity']]] for r in record['refs']]
                if abs(a[2]-b[2]) < 1e-8 or float(np.linalg.norm(a[:2]-b[:2])) < 1e-8:
                    return False
        return True

    def jacobian(x, r, include_pins=True):
        jac = np.empty((len(r), len(x)))
        h = 1e-6
        for i in range(len(x)):
            y = x.copy()
            y[i] += h
            jac[:, i] = (residual(y, include_pins) - r) / h
        return jac

    if not valid(start):
        raise ConstraintError(
            "Constraints require nonzero lines and positive circle/arc radii"
        )
    tolerance = max(1e-10, min(1e-6, doc.constraint_settings["tolerance"] / scale))
    x = start.copy()
    r = residual(x)
    if not check_only:
        for _ in range(doc.constraint_settings["max_iterations"]):
            if np.max(np.abs(r)) <= tolerance:
                break
            jac = jacobian(x, r)
            step = np.linalg.lstsq(jac, -r, rcond=1e-11)[0]
            accepted = False
            for factor in (1, 0.5, 0.25, 0.125, 0.0625, 0.03125, 0.015625):
                candidate = x + factor * step
                if not valid(candidate):
                    continue
                next_r = residual(candidate)
                if float(next_r @ next_r) < float(r @ r):
                    x, r = candidate, next_r
                    accepted = True
                    break
            if not accepted:
                break
    error = float(np.max(np.abs(r)))
    if error > tolerance:
        raise ConstraintError(
            "Conflicting constraints or edit cannot be solved within tolerance. Drawing unchanged; edit/delete a driving constraint or choose another edit."
        )
    intrinsic = residual(x, False)
    rank = int(np.linalg.matrix_rank(jacobian(x, intrinsic, False), tol=1e-7))
    if not check_only and not np.array_equal(x, start):
        values = x * unit + shift
        # Hard edit/locked coordinates retain their exact world-space values.
        for n in pinned:
            values[n] = flat[n]
        if np.max(np.abs(residual((values - shift) / unit))) > tolerance:
            raise ConstraintError(
                "Requested precision cannot be maintained at this coordinate scale. Drawing unchanged."
            )
        for key in keys:
            set_parameters(entities[key], values[slots[key]].tolist())
        doc.spatial_index.invalidate()
    return {
        "constraints": len(records),
        "variables": len(x),
        "rank": rank,
        "free_dof": len(x) - rank,
        "residual": error * scale,
    }


class ConstraintChangeCommand(QUndoCommand):
    needs_solve = True

    def __init__(self, doc, records, description="Constraints"):
        super().__init__(description)
        self.doc = doc
        self.before = copy.deepcopy(doc.constraints)
        self.after = copy.deepcopy(records)

    def redo(self):
        self.doc.constraints = copy.deepcopy(self.after)

    def undo(self):
        self.doc.constraints = copy.deepcopy(self.before)


class SolvedCommand(QUndoCommand):
    def __init__(
        self, doc, commands, before, after, old_constraints, new_constraints, text
    ):
        super().__init__(text)
        self.doc = doc
        self.commands = commands
        self.before = before
        self.after = after
        self.old_constraints = old_constraints
        self.new_constraints = new_constraints
        self.first = True

    def redo(self):
        if self.first:
            self.first = False
            return
        for command in self.commands:
            command.redo()
        restore_geometry(self.doc, self.after)
        self.doc.constraints = copy.deepcopy(self.new_constraints)

    def undo(self):
        for command in reversed(self.commands):
            command.undo()
        restore_geometry(self.doc, self.before)
        self.doc.constraints = copy.deepcopy(self.old_constraints)


class ConstraintUndoStack(QUndoStack):
    rejected = pyqtSignal(str)

    def __init__(self, doc):
        super().__init__()
        self.doc = doc
        self.batch = None
        self.depth = 0

    def push(self, command):
        if self.batch is not None:
            command.redo()
            self.batch["commands"].append(command)
            return
        from .edit_journal import independent_add
        if (not self.doc.constraints or independent_add(self.doc, command)) and not getattr(command, "needs_solve", False):
            from .edit_journal import begin, end
            token = begin(self.doc, command)
            try: super().push(command)
            finally: end(self.doc, token)
            return
        before = geometry_state(self.doc)
        old = copy.deepcopy(self.doc.constraints)
        command.redo()
        self._commit([command], before, old, command.text())

    def undo(self):
        from .edit_journal import begin, end
        command = self.command(self.index()-1) if self.canUndo() else None
        if command is None: return super().undo()
        token = begin(self.doc, command, undo=True)
        try: return super().undo()
        finally: end(self.doc, token)

    def redo(self):
        from .edit_journal import begin, end
        command = self.command(self.index()) if self.canRedo() else None
        if command is None: return super().redo()
        token = begin(self.doc, command)
        try: return super().redo()
        finally: end(self.doc, token)

    def beginMacro(self, text):
        if self.batch is not None:
            self.depth += 1
            return
        if self.doc.constraints:
            self.batch = {
                "commands": [],
                "before": geometry_state(self.doc),
                "old": copy.deepcopy(self.doc.constraints),
                "text": text,
            }
            self.depth = 1
        else:
            super().beginMacro(text)

    def endMacro(self):
        if self.batch is None:
            super().endMacro()
            return
        self.depth -= 1
        if self.depth:
            return
        batch = self.batch
        self.batch = None
        if batch["commands"]:
            self._commit(
                batch["commands"], batch["before"], batch["old"], batch["text"]
            )

    def _commit(self, commands, before, old, text):
        doc = self.doc
        try:
            present = {e.id for e in doc.entities}
            doc.constraints = [
                c
                for c in doc.constraints
                if all(r["entity"] in present for r in c["refs"])
            ]
            after_raw = geometry_state(doc)
            pins = {
                (key, i): v
                for key, vals in after_raw.items()
                if key in before
                for i, v in enumerate(vals)
                if i < len(before[key])
                and not math.isclose(v, before[key][i], rel_tol=0, abs_tol=1e-10)
            }
            pins.update(explicit_edit_pins(commands, after_raw))
            report = solve(doc, pins)
        except (ValueError, np.linalg.LinAlgError) as ex:
            for command in reversed(commands):
                command.undo()
            restore_geometry(doc, before)
            doc.constraints = old
            doc.sync_associative()
            self.rejected.emit(str(ex))
            return
        after = geometry_state(doc)
        new = copy.deepcopy(doc.constraints)
        doc.constraint_report = report
        super().push(SolvedCommand(doc, commands, before, after, old, new, text))


def add_constraint(doc, constraint):
    records = doc.constraints + [constraint]
    validate_records(records, {e.id: e.kind for e in doc.entities})
    doc.undo_stack.push(
        ConstraintChangeCommand(
            doc, records, "Add " + constraint["kind"] + " constraint"
        )
    )
    return any(c["id"] == constraint["id"] for c in doc.constraints)


def explicit_edit_pins(commands, state):
    """Pin complete user-specified points, including unchanged X/Y components."""
    result = {}
    for command in commands:
        entity = getattr(command, "owner", None) or getattr(command, "entity", None)
        key = getattr(command, "grip_kind", None) or getattr(command, "attr_name", None)
        if entity is not None and getattr(entity, "id", None) in state:
            indices = {
                "p1": (0, 1),
                "p2": (2, 3),
                "center": (0, 1),
                "point": (0, 1),
                "radius": (2,),
                "start_angle": (3,),
                "end_angle": (4,),
            }.get(key, ())
            for i in indices:
                if i < len(state[entity.id]):
                    result[(entity.id, i)] = state[entity.id][i]
        if type(command).__name__ in (
            "TranslateEntitiesCommand",
            "RotateEntitiesCommand",
            "ScaleEntitiesCommand",
        ):
            for entity in command.entities:
                if entity.id in state:
                    for i, v in enumerate(state[entity.id]):
                        result[(entity.id, i)] = v
    return result
