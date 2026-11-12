"""Independent drawing sessions, canvas state and tab-aware save/close handling."""

import os
import uuid
from PyQt6.QtCore import QPointF
from PyQt6.QtWidgets import QTabBar


class DrawingTabs(QTabBar):
    def __init__(self, mw):
        super().__init__(mw)
        self.mw = mw
        self.sessions = []
        self.active = -1
        self.switching = False
        self.setObjectName("drawing_tabs")
        self.setExpanding(False)
        self.setTabsClosable(True)
        self.setMovable(False)
        self.currentChanged.connect(self.activate)
        self.tabCloseRequested.connect(self.close_drawing)
        self.add_document(mw.document, initial=True)

    def state(self):
        canvas = self.mw.canvas
        return dict(
            zoom=canvas.zoom,
            pan=QPointF(canvas.pan_offset),
            space=self.mw.document.current_space,
            selection=list(canvas.selected_entities),
        )

    def add_document(self, doc, initial=False):
        if self.active >= 0:
            self.sessions[self.active]["view"] = self.state()
        self.blockSignals(True)
        self.sessions.append({"doc": doc, "view": None, "id": uuid.uuid4().hex})
        index = self.addTab("Drawing")
        self.blockSignals(False)
        if initial:
            self.active = index
            self.setCurrentIndex(index)
        else:
            self.setCurrentIndex(index)
        self.refresh()
        return index

    def replace_active(self, doc):
        if not self.switching and self.active >= 0:
            self.sessions[self.active]["doc"] = doc
            self.sessions[self.active]["view"] = None
            self.refresh()

    def activate(self, index):
        if index < 0 or index >= len(self.sessions) or index == self.active:
            return
        if getattr(self.mw, "action_recorder", None):
            self.mw.command_history.appendPlainText(
                "Stop recording before switching drawings."
            )
            self.blockSignals(True)
            self.setCurrentIndex(self.active)
            self.blockSignals(False)
            return
        if self.active >= 0:
            self.sessions[self.active]["view"] = self.state()
        session = self.sessions[index]
        self.switching = True
        try:
            self.mw._finish_pending_drag()
            self.mw._replace_document(session["doc"])
            self.active = index
            if session["view"]:
                view = session["view"]
                self.mw.document.current_space = (
                    view["space"]
                    if view["space"] == "Model"
                    or view["space"] in self.mw.document.layouts
                    else "Model"
                )
                self.mw.space_tabs.setCurrentIndex(
                    ["Model", *self.mw.document.layouts].index(
                        self.mw.document.current_space
                    )
                )
                self.mw.canvas.zoom = view["zoom"]
                self.mw.canvas.pan_offset = QPointF(view["pan"])
                self.mw.canvas.selected_entities = [
                    e
                    for e in view["selection"]
                    if e in self.mw.document.editable_entities()
                ]
        finally:
            self.switching = False
        self.refresh()
        self.mw.refresh_document_ui()

    def refresh(self):
        for i, s in enumerate(self.sessions):
            doc = s["doc"]
            name = (
                os.path.basename(doc.filepath) if doc.filepath else f"Untitled {i + 1}"
            )
            self.setTabText(i, name + (" *" if modified_for_ui(doc) else ""))
            self.setTabToolTip(i, doc.filepath or "Unsaved drawing")

    def close_drawing(self, index):
        if index < 0 or index >= len(self.sessions):
            return False
        previous = self.active
        self.setCurrentIndex(index)
        if self.active != index:
            return False
        if not self.mw._confirm_save_changes():
            self.setCurrentIndex(previous)
            return False
        self.sessions.pop(index)
        self.blockSignals(True)
        self.removeTab(index)
        self.blockSignals(False)
        self.active = -1
        if self.sessions:
            target = min(index, len(self.sessions) - 1)
            self.activate(target)
            self.blockSignals(True)
            self.setCurrentIndex(target)
            self.blockSignals(False)
        else:
            from .document import Document

            doc = Document()
            self.switching = True
            try:
                self.mw._replace_document(doc)
            finally:
                self.switching = False
            self.add_document(doc, initial=True)
        self.refresh()
        return True

    def confirm_all(self):
        original = self.active
        for index in range(len(self.sessions)):
            self.setCurrentIndex(index)
            if self.active != index or not self.mw._confirm_save_changes():
                self.setCurrentIndex(original)
                return False
        self.setCurrentIndex(original)
        return True


def save_recovery(mw):
    import json
    from pathlib import Path
    from . import appsettings
    from .native_io import save_project, atomic_write

    base = Path(appsettings.RECOVERY_PATH)
    base.parent.mkdir(parents=True, exist_ok=True)
    sessions = mw.drawing_tabs.sessions
    if not any(s["doc"].dirty for s in sessions):
        return
    manifest = {
        "format": "PyCAD tab recovery",
        "active": mw.drawing_tabs.active,
        "drawings": [],
    }
    for index, session in enumerate(sessions):
        path = base.with_name(base.stem + "-" + session["id"] + ".pycad")
        save_project(session["doc"], path, backup=False)
        manifest["drawings"].append(
            {
                "snapshot": path.name,
                "source": session["doc"].filepath,
                "dirty": session["doc"].dirty,
            }
        )
    save_project(mw.document, base, backup=False)
    atomic_write(
        str(base) + ".tabs.json",
        lambda f: Path(f).write_text(
            json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
        ),
    )


def load_recovery_tabs(mw):
    import json, re
    from pathlib import Path
    from . import appsettings
    from .native_io import load_project

    base = Path(appsettings.RECOVERY_PATH)
    manifest_path = Path(str(base) + ".tabs.json")
    if not manifest_path.exists():
        return False
    if manifest_path.stat().st_size > 1024 * 1024:
        raise ValueError("Recovery manifest is too large")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (
        not isinstance(manifest, dict)
        or set(manifest) != {"format", "active", "drawings"}
        or manifest["format"] != "PyCAD tab recovery"
        or not isinstance(manifest["drawings"], list)
        or not 1 <= len(manifest["drawings"]) <= 1000
        or type(manifest["active"]) is not int
        or not 0 <= manifest["active"] < len(manifest["drawings"])
    ):
        raise ValueError("Invalid tab recovery manifest")
    docs = []
    for item in manifest["drawings"]:
        if (
            not isinstance(item, dict)
            or set(item) != {"snapshot", "source", "dirty"}
            or not isinstance(item["snapshot"], str)
            or not re.fullmatch(
                re.escape(base.stem) + r"-[a-f0-9]{32}\.pycad", item["snapshot"]
            )
            or type(item["dirty"]) is not bool
        ):
            raise ValueError("Invalid recovery drawing")
        doc = load_project(base.parent / item["snapshot"])
        doc.filepath = None if item["dirty"] else item["source"]
        doc._force_dirty = item["dirty"]
        docs.append(doc)
    # Validate every snapshot before replacing the starter drawing.
    mw._replace_document(docs[0])
    mw.drawing_tabs.sessions[0]["doc"] = docs[0]
    for doc in docs[1:]:
        mw.drawing_tabs.add_document(doc)
    mw.drawing_tabs.setCurrentIndex(manifest["active"])
    mw.refresh_document_ui()
    return True


def clear_recovery_tabs():
    from pathlib import Path
    from . import appsettings

    base = Path(appsettings.RECOVERY_PATH)
    for path in base.parent.glob(base.stem + "-*.pycad"):
        import re

        if re.fullmatch(re.escape(base.stem) + r"-[a-f0-9]{32}\.pycad", path.name):
            path.unlink(missing_ok=True)
    Path(str(base) + ".tabs.json").unlink(missing_ok=True)


def modified_for_ui(doc):
    """Cheap unsaved marker during normal edits; canonical save/close stays exact."""
    return not doc.undo_stack.isClean() or doc.dirty
