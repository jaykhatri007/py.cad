"""Portable vector shared views and read-only native/DXF drawing comparison."""

import copy
import hashlib
import html
import json
import re
from pathlib import Path
from PyQt6.QtCore import QBuffer, QByteArray, QIODevice, QRect, QSize, QPointF
from PyQt6.QtGui import QPainter, QFont
from PyQt6.QtSvg import QSvgGenerator
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QListWidget,
    QCheckBox,
    QFileDialog,
)
from .native_io import (
    document_to_dict,
    document_from_dict,
    entity_to_dict,
    load_project,
    atomic_write,
)


def shared_view_html(doc, title="PY.cad Shared View"):
    from .canvas import CadCanvas
    from .plotting import plot_bounds
    from .underlays import bounds

    boxes = [plot_bounds(doc, e, QFont()) for e in doc.visible_entities()] + bounds(doc)
    if not boxes:
        raise ValueError("There is no visible 2D geometry to share")
    x0, y0, x1, y1 = (
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    )
    width, height = 1400, 900
    zoom = min((width - 80) / max(x1 - x0, 1), (height - 80) / max(y1 - y0, 1))
    raw = QByteArray()
    buffer = QBuffer(raw)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    svg = QSvgGenerator()
    svg.setOutputDevice(buffer)
    svg.setSize(QSize(width, height))
    svg.setViewBox(QRect(0, 0, width, height))
    svg.setTitle(title)
    painter = QPainter(svg)
    renderer = CadCanvas(doc)
    renderer.world_to_screen = lambda x, y: QPointF(
        width / 2 + (x - (x0 + x1) / 2) * zoom, height / 2 - (y - (y0 + y1) / 2) * zoom
    )
    renderer.zoom = zoom
    try:
        renderer._draw_entities(painter)
    finally:
        painter.end()
        buffer.close()
        renderer.deleteLater()
    content = bytes(raw).decode("utf-8")
    content = content[content.index("<svg") :]
    safe = html.escape(title)
    page = """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title><style>html,body{margin:0;height:100%;font:14px system-ui;background:#1e1e20;color:#e9eef5}header{display:flex;gap:12px;align-items:center;padding:12px;background:#233044}h1{font-size:15px;margin:0 auto 0 0}button{background:#34475b;border:1px solid #5c7287;color:white;border-radius:4px;padding:6px 12px}main{height:calc(100% - 88px);overflow:hidden;touch-action:none;cursor:grab}svg{width:100%;height:100%;transform-origin:0 0}footer{padding:8px;color:#acbcd0;font-size:12px}@media print{header,footer{display:none}main{height:100vh}svg{transform:none!important}}</style>
<header><h1>__TITLE__</h1><button id="out">−</button><button id="in">+</button><button id="fit">Fit</button><button id="bg">Background</button><button id="print">Print</button></header>
<main>__SVG__</main><footer>Read-only 2D snapshot · drag to pan, wheel to zoom · __UNITS__ · no external resources</footer>
<script>const host=document.querySelector('main'),s=host.querySelector('svg');let z=1,x=0,y=0,drag=null;
function update(){s.style.transform=`translate(${x}px,${y}px) scale(${z})`}
function zoom(k,px=host.clientWidth/2,py=host.clientHeight/2){let n=Math.max(.05,Math.min(30,z*k));x=px-(px-x)*n/z;y=py-(py-y)*n/z;z=n;update()}
document.getElementById('in').onclick=()=>zoom(1.2);document.getElementById('out').onclick=()=>zoom(1/1.2);
document.getElementById('fit').onclick=()=>{z=1;x=y=0;update()};document.getElementById('bg').onclick=()=>{host.style.background=host.style.background==='white'?'#1e1e20':'white'};
document.getElementById('print').onclick=()=>window.print();host.addEventListener('wheel',e=>{e.preventDefault();const r=host.getBoundingClientRect();zoom(e.deltaY<0?1.15:1/1.15,e.clientX-r.left,e.clientY-r.top)},{passive:false});
host.onpointerdown=e=>{drag=[e.clientX-x,e.clientY-y];host.setPointerCapture(e.pointerId)};host.onpointermove=e=>{if(drag){x=e.clientX-drag[0];y=e.clientY-drag[1];update()}};host.onpointerup=()=>drag=null;host.onpointercancel=()=>drag=null;
</script></html>"""
    values = {"TITLE": safe, "SVG": content, "UNITS": html.escape(doc.units)}
    return re.sub(r"__(TITLE|SVG|UNITS)__", lambda m: values[m[1]], page)


def export_shared_view(doc, path, title=None):
    text = shared_view_html(doc, title or Path(path).stem)
    atomic_write(path, lambda output: Path(output).write_text(text, encoding="utf-8"))


def share_view(mw):
    path, _ = QFileDialog.getSaveFileName(
        mw, "Export portable shared view", "shared-view.html", "HTML view (*.html)"
    )
    if path:
        export_shared_view(mw.document, path)
        mw.command_history.appendPlainText("Saved shared view: " + str(path))


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()
    ).hexdigest()


def fingerprint(doc, e):
    record = copy.deepcopy(entity_to_dict(e))
    data = record["data"]
    data.pop("id")
    for k in ("source_line_id", "source_arc_id", "source_entity_id", "source_line_ids"):
        data.pop(k, None)
    result = {"entity": record, "layer": doc.layers.layers.get(e.layer)}
    if e.kind == "INSERT":
        # Definitions, including nested references, are separately reported in metadata.
        block = doc.blocks.get(e.block_name)
        result["block"] = (
            [entity_to_dict(child) for child in block.entities] if block else None
        )
    if hasattr(e, "style_name"):
        table = (
            doc.textstyles
            if e.kind == "TEXT"
            else doc.mleaderstyles
            if e.kind == "MLEADER"
            else doc.dimstyles
        )
        result["style"] = table.get(e.style_name)
    return digest(result)


def compare_drawings(current, reference):
    if current.units != reference.units:
        raise ValueError(
            "Drawing comparison requires matching units; convert a copy before comparison"
        )
    a = {e.id: e for e in current.entities}
    b = {e.id: e for e in reference.entities}
    common = set(a) & set(b)
    changed = [
        key
        for key in sorted(common)
        if fingerprint(current, a[key]) != fingerprint(reference, b[key])
    ]
    changed_set = set(changed)
    same = [key for key in sorted(common) if key not in changed_set]
    added = set(a) - common
    removed = set(b) - common
    # Independently imported drawings have different IDs. Pair identical visible entity states.
    signatures = {}
    for key in sorted(removed):
        signatures.setdefault(fingerprint(reference, b[key]), []).append(key)
    for key in sorted(added.copy()):
        matches = signatures.get(fingerprint(current, a[key]))
        if matches:
            old = matches.pop()
            added.remove(key)
            removed.remove(old)
            same.append(key)
    pa, pb = document_to_dict(current), document_to_dict(reference)
    metadata = {
        k: pa[k] != pb[k]
        for k in (
            "layers",
            "blocks",
            "dimstyles",
            "mleaderstyles",
            "textstyles",
            "layouts",
            "underlays",
            "constraints",
            "extrusions",
            "unit_settings",
        )
    }
    return dict(
        format="PyCAD drawing comparison",
        units=current.units,
        added=sorted(added),
        removed=sorted(removed),
        changed=changed,
        unchanged=same,
        metadata_changes=[k for k, v in metadata.items() if v],
    )


class ComparisonDialog(QDialog):
    def __init__(self, mw, reference):
        super().__init__(mw)
        self.mw = mw
        self.reference = reference
        self.current = document_from_dict(document_to_dict(mw.document))
        self.report = compare_drawings(self.current, reference)
        self.setWindowTitle("Drawing comparison")
        self.resize(590, 400)
        root = QVBoxLayout(self)
        r = self.report
        root.addWidget(
            QLabel(
                f"Current vs reference · {r['units']}\nAdded {len(r['added'])} · Removed {len(r['removed'])} · Changed {len(r['changed'])} · Unchanged {len(r['unchanged'])}"
            )
        )
        list_ = QListWidget()
        root.addWidget(list_)
        for kind in ("added", "removed", "changed"):
            source = reference if kind == "removed" else self.current
            for key in r[kind]:
                e = source.find_by_id(key)
                list_.addItem(f"{kind.title()} · {e.kind} · {e.layer} · {key[:12]}")
        list_.addItems(["Table/settings changed: " + k for k in r["metadata_changes"]])
        self.overlay = QCheckBox(
            "Show 2D overlay: green added, red removed, amber changed"
        )
        self.overlay.toggled.connect(self.show_overlay)
        root.addWidget(self.overlay)
        note = QLabel(
            "Native IDs identify modified objects. Identical foreign-ID geometry is paired; other imports appear as added/removed. Tables, layouts, constraints, references and solids are reported separately."
        )
        note.setWordWrap(True)
        root.addWidget(note)
        row = QHBoxLayout()
        root.addLayout(row)
        for label, fn in (("Save report…", self.save_report), ("Close", self.accept)):
            b = QPushButton(label)
            b.clicked.connect(fn)
            row.addWidget(b)
        self.overlay.setChecked(True)

    def show_overlay(self, enabled):
        entries = []
        if enabled:
            for key, color, doc in (
                [(k, "#70d994", self.current) for k in self.report["added"]]
                + [(k, "#f37985", self.reference) for k in self.report["removed"]]
                + [(k, "#f5c66c", self.current) for k in self.report["changed"]]
            ):
                entries.append((doc.find_by_id(key).clone(), color, doc))
        self.mw.canvas.comparison_overlay = entries
        self.mw.canvas.viewport().update()

    def save_report(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save comparison report", "drawing-comparison.json", "JSON (*.json)"
        )
        if path:
            atomic_write(
                path,
                lambda output: Path(output).write_text(
                    json.dumps(self.report, indent=2), encoding="utf-8"
                ),
            )

    def done(self, result):
        self.show_overlay(False)
        super().done(result)


def compare_dialog(mw):
    path, _ = QFileDialog.getOpenFileName(
        mw, "Choose reference drawing", "", "Drawing (*.pycad *.dxf)"
    )
    if not path:
        return
    from .dxf_io import import_dxf

    reference = (
        import_dxf(path) if Path(path).suffix.lower() == ".dxf" else load_project(path)
    )
    dialog = ComparisonDialog(mw, reference)
    try:
        dialog.exec()
    finally:
        dialog.show_overlay(False)
        dialog.setParent(None)
        dialog.deleteLater()


def commands(mw):
    from .cloud import cloud_manager

    return {
        "SHAREDVIEWS": lambda: share_view(mw),
        "COMPARE": lambda: compare_dialog(mw),
        "DWGCOMPARE": lambda: compare_dialog(mw),
        "CLOUD": lambda: cloud_manager(mw),
    }
