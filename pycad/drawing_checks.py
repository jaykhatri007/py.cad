"""Read-only architectural checks, screen highlights and JSON report export."""

from .wall_joining import frames, projection
from .geometry import PolylineEntity, LineEntity


def opening_conflicts(doc, records=None):
    records = records if records is not None else doc.extensions.get("architecture", {})
    active = [
        (key, r)
        for key, r in records.items()
        if r["kind"] == "opening" and doc.find_by_id(key)
    ]
    conflicts = []
    for i, (key, r) in enumerate(active):
        for other_key, other in active[i + 1 :]:
            if (
                r["wall"] == other["wall"]
                and abs(r["station"] - other["station"])
                < (r["width"] + other["width"]) / 2 - 1e-9
            ):
                conflicts.append((key, other_key))
    return conflicts


def inspect(doc):
    from .native_io import document_to_dict
    from .validation import validate_payload

    doc.sync_associative()
    issues = []

    def add(code, message, ids=(), point=None, severity="Warning"):
        issues.append(
            dict(
                code=code,
                message=message,
                ids=list(ids),
                point=list(point) if point else None,
                severity=severity,
            )
        )

    try:
        validate_payload(document_to_dict(doc))
    except ValueError as ex:
        add("INVALID_DATA", str(ex), severity="Error")
    wall_frames = frames(doc)
    for key, f in wall_frames.items():
        tolerance = max(1e-8, f["h"] * 1e-6)
        for end in ("a", "b"):
            p = f[end]
            connected = any(
                projection(p, other["a"], other["b"])[1] <= tolerance
                for other_key, other in wall_frames.items()
                if other_key != key and f['level'] == other['level']
            )
            if not connected:
                add(
                    "OPEN_WALL_END",
                    "Wall has a free or disconnected centre-line end",
                    [key],
                    p,
                )
    records = doc.extensions.get("architecture", {})
    for key, r in records.items():
        if doc.find_by_id(key) is None:
            continue
        if r["kind"] == "opening":
            host = wall_frames.get(r["wall"])
            if host is None:
                add(
                    "MISSING_HOST",
                    "Opening has no live host wall",
                    [key],
                    severity="Error",
                )
            elif (
                r["station"] - r["width"] / 2 < 0
                or r["station"] + r["width"] / 2 > host["record"]["length"]
                or r["height"] + r["sill"] > host["record"]["height"]
            ):
                add(
                    "OPENING_BOUNDS",
                    "Opening exceeds the host length or height",
                    [key, r["wall"]],
                    severity="Error",
                )
        elif r["kind"] == "room":
            source = doc.find_by_id(r["source"])
            if source is None:
                add(
                    "MISSING_ROOM_BOUNDARY",
                    "Room is using its saved boundary snapshot",
                    [key],
                    severity="Error",
                )
            elif not isinstance(source, PolylineEntity) or not source.closed:
                add(
                    "OPEN_ROOM",
                    "Room boundary must be a closed polyline",
                    [key, r["source"]],
                    severity="Error",
                )
            else:
                from .model3d import validate_feature

                points = source.sample_points()
                if points and points[0].distance_to(points[-1]) < 1e-9:
                    points = points[:-1]
                try:
                    validate_feature(
                        dict(
                            id="check",
                            name="Room",
                            layer=source.layer,
                            height=1,
                            profile=dict(
                                kind="POLYGON", points=[[p.x, p.y] for p in points]
                            ),
                        ),
                        doc.layers.layers,
                    )
                except ValueError as ex:
                    add("INVALID_ROOM", str(ex), [key, r["source"]], severity="Error")
    for ids in opening_conflicts(doc):
        add(
            "OVERLAPPING_OPENINGS",
            "Hosted openings overlap in plan",
            ids,
            severity="Error",
        )
    for entity in doc.entities:
        if isinstance(entity, LineEntity) and entity.p1.distance_to(entity.p2) <= 1e-10:
            add("ZERO_LENGTH", "Line has zero length", [entity.id], severity="Error")
    for key, status in getattr(doc, "link_status", {}).items():
        if status.startswith("Stale") or status.startswith("Source wall missing"):
            link = doc.extensions.get("wall_models", {}).get(key)
            building_link = doc.extensions.get('building_models', {}).get(key)
            add(
                "STALE_LINK",
                status,
                [link["wall"]] if link else [building_link['source']] if building_link else [key],
                severity="Error",
            )
    for key, status in getattr(doc, 'room_link_status', {}).items():
        if status.startswith('Stale'):
            add('STALE_ROOM', status, [key], severity='Error')
    doc.check_issues = issues
    doc._checked_index = doc.undo_stack.index()
    return issues


def draw_highlights(canvas, painter):
    from PyQt6.QtCore import Qt, QRectF
    from PyQt6.QtGui import QColor, QPen

    painter.save()
    painter.setBrush(Qt.BrushStyle.NoBrush)
    for issue in getattr(canvas.document, "check_issues", []):
        painter.setPen(
            QPen(
                QColor("#f07878" if issue["severity"] == "Error" else "#ffc45e"),
                2,
                Qt.PenStyle.DashLine,
            )
        )
        if issue["point"]:
            p = canvas.world_to_screen(*issue["point"])
            painter.drawEllipse(p, 7, 7)
        else:
            for key in issue["ids"]:
                e = canvas.document.find_by_id(key)
                if e:
                    x0, y0, x1, y1 = e.bbox()
                    a, b = (
                        canvas.world_to_screen(x0, y0),
                        canvas.world_to_screen(x1, y1),
                    )
                    painter.drawRect(QRectF(a, b).normalized().adjusted(-4, -4, 4, 4))
    painter.restore()


def dialog(mw):
    import json
    from PyQt6.QtWidgets import (
        QDialog,
        QVBoxLayout,
        QHBoxLayout,
        QLabel,
        QTableWidget,
        QTableWidgetItem,
        QPushButton,
        QFileDialog,
        QHeaderView,
    )
    from .native_io import atomic_write
    from .feature_helpers import safe_action

    d = QDialog(mw)
    d.setWindowTitle("Drawing checks")
    d.resize(650, 360)
    root = QVBoxLayout(d)
    summary = QLabel(
        "Free wall ends can be intentional. Edits clear highlights; rerun to check again."
    )
    summary.setWordWrap(True)
    root.addWidget(summary)
    table = QTableWidget(0, 3)
    table.setHorizontalHeaderLabels(["Level", "Check", "Details"])
    table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    root.addWidget(table)

    def refresh():
        d.issues = inspect(mw.document)
        table.setRowCount(len(d.issues))
        for i, r in enumerate(d.issues):
            for j, value in enumerate((r["severity"], r["code"], r["message"])):
                table.setItem(i, j, QTableWidgetItem(value))
        mw.canvas.viewport().update()

    def locate():
        i = table.currentRow()
        if i < 0:
            return
        issue = d.issues[i]
        mw.canvas.selected_entities = [
            e
            for key in issue["ids"]
            if (e := mw.document.find_by_id(key)) in mw.document.editable_entities()
        ]
        mw.document.current_space = "Model"
        mw.viewport_stack.setCurrentWidget(mw.canvas)
        mw.canvas.zoom_extents()
        mw.refresh_document_ui()
        d.accept()

    def export():
        path, _ = QFileDialog.getSaveFileName(
            d, "Save check report", "drawing-checks.json", "JSON (*.json)"
        )
        if path:
            from pathlib import Path

            report = json.dumps(
                dict(
                    format="PyCAD drawing checks",
                    units=mw.document.units,
                    issues=d.issues,
                ),
                indent=2,
                ensure_ascii=False,
            )
            atomic_write(path, lambda filename: Path(filename).write_text(report))

    def clear():
        mw.document.check_issues = []
        mw.canvas.viewport().update()

    bar = QHBoxLayout()
    root.addLayout(bar)
    for label, callback in [
        ("Recheck", refresh),
        ("Select issue", locate),
        ("Export JSON", export),
        ("Clear marks", clear),
        ("Close", d.accept),
    ]:
        b = QPushButton(label)
        b.clicked.connect(safe_action(d, callback))
        bar.addWidget(b)
    refresh()
    d.exec()
