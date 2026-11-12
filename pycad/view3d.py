"""Model inspection panes with shared raster/OpenGL drawing and orbitable cameras.

This is an orthographic inspection viewport, not a B-rep editing kernel. Saved
extrusion parameters regenerate real STEP/STL solids through optional CadQuery.
"""

import copy
from PyQt6.QtCore import Qt, QPointF, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QPainter, QPen, QPolygonF
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QComboBox,
    QPushButton,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QInputDialog,
    QFileDialog,
    QMessageBox,
)
from .model3d import (
    Camera,
    feature_mesh,
    ExtrusionCommand,
    profile_entity,
    dot,
    cross,
    unit,
)
from .geom_ops import entity_to_segments
from .geometry import BlockReferenceEntity
from .navigation import ViewportNavigation
from .command_input import ViewportCommandPrompt
from .canvas import safe_event


class ModelViewport(QWidget):
    activated = pyqtSignal(object)

    def __init__(self, workspace, preset):
        super().__init__()
        self.workspace = workspace
        self.camera = Camera(preset)
        self.setMinimumSize(220, 180)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.last = None
        self.fit_pending = True
        self.faces = []
        self.wires = []
        self.points = []
        self.solid_wires=[]
        self.graphics_surface = None
        self.interaction_mode = "orbit"
        self.drag_mode = None
        self.command_overlay = ViewportCommandPrompt(workspace.mw, self)
        self.navigation = ViewportNavigation(self)
        self.navigation.mode_requested.connect(self.set_navigation_mode)
        self.navigation.view_requested.connect(self.select_view)
        self.navigation.zoom_requested.connect(self.zoom_camera)
        self.navigation.fit_requested.connect(self.activate_and_fit)
        self.navigation.draft_requested.connect(workspace.draft_requested)
        self.navigation.layout_requested.connect(self.select_layout)
        self.navigation.orbit_requested.connect(self.rotate_camera)
        self.navigation.sync(self.camera, self.interaction_mode)
        self.set_graphics_backend(workspace.mw.graphics.backend)

    def set_graphics_backend(self, backend):
        if backend == "opengl" and self.graphics_surface is None:
            surface = self.workspace.mw.graphics.create_surface(self, self._paint_scene)
            self.graphics_surface = surface
            surface.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            surface.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            surface.setGeometry(self.rect())
            surface.lower()
            surface.show()
            for control in (self.navigation, self.navigation.cube, self.navigation.view_selector, self.command_overlay):
                control.raise_()
        elif backend == "software" and self.graphics_surface is not None:
            surface, self.graphics_surface = self.graphics_surface, None
            self.workspace.mw.graphics.release_surface(surface)
            surface.hide()
            surface.deleteLater()
        self.update()

    def update(self, *args):
        super().update(*args)
        surface = getattr(self, "graphics_surface", None)
        if surface is not None:
            surface.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.graphics_surface is not None:
            self.graphics_surface.setGeometry(self.rect())

    def set_navigation_mode(self, mode):
        self.interaction_mode = mode
        self.workspace.activate(self)
        self.setCursor(Qt.CursorShape.OpenHandCursor if mode == "pan" else Qt.CursorShape.SizeAllCursor)
        self.setFocus()

    def select_view(self, name):
        self.workspace.activate(self)
        self.workspace.change_view(name)

    def activate_and_fit(self):
        self.workspace.activate(self)
        self.fit()

    def select_layout(self, four):
        self.workspace.activate(self)
        self.workspace.layout_mode.setCurrentIndex(0 if four else 1)

    def rotate_camera(self, dx, dy):
        self.workspace.activate(self)
        self.camera.orbit(dx, dy)
        self.update()
        self.workspace.update_view_label()

    def zoom_camera(self, factor):
        self.workspace.activate(self)
        self.camera.scale = max(1e-10, min(1e10, self.camera.scale * factor))
        self.update()

    def set_scene(self, faces, wires, points):
        self.faces = faces
        self.wires = wires
        self.points = points
        if self.fit_pending:
            self.fit()
        self.update()

    def fit(self):
        self.camera.fit(self.points, self.width(), self.height())
        self.fit_pending = False
        self.update()

    def set_view(self, name):
        self.camera.set_view(name)
        self.fit()
        self.workspace.update_view_label()

    def screen(self, p):
        x, y, z = self.camera.project(p)
        return QPointF(
            self.width() / 2 + x * self.camera.scale + self.camera.pan[0],
            self.height() / 2 - y * self.camera.scale + self.camera.pan[1],
        ), z

    @safe_event
    def paintEvent(self, event):
        if self.graphics_surface is not None:
            return
        painter = QPainter(self)
        try:
            self._paint_scene(painter)
        finally:
            painter.end()

    def _paint_scene(self, painter):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        from .appearance import colors
        ui = colors(self)
        painter.fillRect(self.rect(), QColor(ui['model3d']))
        # A screen grid supplies depth-independent navigation context.
        painter.setPen(QPen(QColor(ui['ui_3d_grid']), 1))
        for x in range(0, self.width(), 32):
            painter.drawLine(x, 0, x, self.height())
        for y in range(0, self.height(), 32):
            painter.drawLine(0, y, self.width(), y)
        ordered = []
        for vertices, color, feature_id in self.faces:
            projected = [self.screen(p) for p in vertices]
            ordered.append(
                (
                    sum(p[1] for p in projected) / len(projected),
                    projected,
                    color,
                    feature_id,
                    vertices,
                )
            )
        ordered.sort(key=lambda item: item[0])
        selected = self.workspace.selected_id()
        for _, projected, color, feature_id, vertices in ordered:
            c = QColor(color)
            if self.workspace.visual.currentText() == "Shaded with edges":
                a, b, cpt = vertices[:3]
                normal = cross(
                    tuple(b[i] - a[i] for i in range(3)),
                    tuple(cpt[i] - a[i] for i in range(3)),
                )
                if dot(normal, self.camera.back) <= 0:
                    continue
                if dot(normal, normal) > 1e-16:
                    light = 0.45 + 0.55 * abs(dot(unit(normal), unit((0.4, -0.6, 1))))
                    c = QColor.fromRgbF(
                        c.redF() * light, c.greenF() * light, c.blueF() * light
                    )
                from .materials import brush
                painter.setBrush(brush(self.workspace.doc, feature_id, c))
            elif self.workspace.visual.currentText() == "X-Ray":
                c.setAlpha(55)
                painter.setBrush(c)
            else:
                painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(
                QPen(
                    QColor(ui['ui_selection']) if feature_id == selected else QColor(ui['ui_3d_edge']),
                    1.5 if feature_id == selected else 0.65,
                )
            )
            if feature_id in self.workspace.doc.extensions.get('solids',{}) and self.workspace.visual.currentText()!='Wireframe': painter.setPen(Qt.PenStyle.NoPen)
            from .materials import appearance
            material = appearance(self.workspace.doc, feature_id)
            if material and material['texture'] and self.workspace.visual.currentText() == 'Shaded with edges':
                painter.setOpacity(material['opacity'])
            painter.drawPolygon(QPolygonF([p[0] for p in projected]))
            painter.setOpacity(1)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if self.workspace.visual.currentText()!='Wireframe':
            for a,b,feature_id in self.solid_wires:
                painter.setPen(QPen(QColor(ui['ui_selection']) if feature_id==selected else QColor(ui['ui_3d_edge']),1.2 if feature_id==selected else .65));painter.drawLine(self.screen(a)[0],self.screen(b)[0])
        if self.workspace.outlines.isChecked() or not self.faces:
            for a, b, color in self.wires:
                painter.setPen(QPen(QColor(color), 0.8))
                painter.drawLine(self.screen(a)[0], self.screen(b)[0])
        painter.setPen(QColor(ui['ui_text']))
        font = painter.font()
        font.setBold(True)
        painter.setFont(font)
        # The view selector is painted above the model as a child overlay.
        font.setBold(False)
        painter.setFont(font)
        painter.setPen(QColor(ui['ui_3d_text']))
        navigation_hint = (
            "ORTHOGRAPHIC  ·  ORBIT MODE"
            if self.interaction_mode == "orbit"
            else "ORTHOGRAPHIC  ·  PAN MODE"
        )
        if self.height() >= 300:
            painter.drawText(16, self.height() - 14, navigation_hint)
        origin = QPointF(48, self.height() - 64)
        for label, axis, color in [
            ("X", (1, 0, 0), ui['ui_axis_x']),
            ("Y", (0, 1, 0), ui['ui_axis_y']),
            ("Z", (0, 0, 1), ui['ui_axis_z']),
        ]:
            end = origin + QPointF(
                dot(axis, self.camera.right) * 32, -dot(axis, self.camera.up) * 32
            )
            painter.setPen(QPen(QColor(color), 2))
            painter.drawLine(origin, end)
            painter.drawText(end + QPointF(3, -3), label)
        active = self.workspace.active is self
        painter.setPen(
            QPen(QColor(ui['accent']) if active else QColor(ui['ui_border']), 2 if active else 1)
        )
        painter.drawRect(self.rect().adjusted(1, 1, -2, -2))

    def mousePressEvent(self, event):
        self.workspace.activate(self)
        self.last = event.position()
        shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        if event.button() == Qt.MouseButton.RightButton:
            self.drag_mode = "pan"
        elif event.button() == Qt.MouseButton.MiddleButton and shift:
            self.drag_mode = "orbit"
        elif event.button() == Qt.MouseButton.MiddleButton:
            self.drag_mode = "pan"
        elif event.button() == Qt.MouseButton.LeftButton and shift:
            self.drag_mode = "pan"
        elif event.button() == Qt.MouseButton.LeftButton:
            self.drag_mode = self.interaction_mode
        else:
            self.drag_mode = "pan"
        self.setFocus()
        event.accept()

    def mouseMoveEvent(self, event):
        if self.last is None:
            return
        dx = event.position().x() - self.last.x()
        dy = event.position().y() - self.last.y()
        if self.drag_mode == "pan":
            self.camera.pan = (self.camera.pan[0] + dx, self.camera.pan[1] + dy)
        elif self.drag_mode == "orbit":
            self.camera.orbit(dx, dy)
        self.last = event.position()
        self.update()
        self.workspace.update_view_label()

    def mouseReleaseEvent(self, event):
        self.last = None
        self.drag_mode = None

    def focusOutEvent(self, event):
        self.last = None
        self.drag_mode = None
        super().focusOutEvent(event)

    def mouseDoubleClickEvent(self, event):
        self.fit()

    def wheelEvent(self, event):
        self.workspace.activate(self)
        self.camera.scale = max(
            1e-10, min(1e10, self.camera.scale * 1.15 ** (event.angleDelta().y() / 120))
        )
        self.update()
        event.accept()

    def keyPressEvent(self, event):
        if self.workspace.mw.route_viewport_key(self, event):
            return
        if event.key() == Qt.Key.Key_Home:
            self.fit()
        elif event.key() == Qt.Key.Key_Escape:
            self.last = None
            self.drag_mode = None
            self.workspace.draft_requested.emit()
        else:
            super().keyPressEvent(event)


class ModelWorkspace(QWidget):
    """Persistent model panes embedded in the main window's central stack."""

    draft_requested = pyqtSignal()

    def __init__(self, mw, preset="Isometric", four=True):
        super().__init__(mw)
        self.mw = mw
        self.doc = mw.document
        self.setObjectName("embedded_model_workspace")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        bar = QHBoxLayout()
        root.addLayout(bar)
        bar.setContentsMargins(8, 3, 8, 3)
        heading = QLabel("MODEL VIEWS")
        bar.addWidget(heading)
        bar.addStretch()
        self.layout_mode = QComboBox()
        self.layout_mode.addItems(["Four views", "Single view"])
        bar.addWidget(self.layout_mode)
        self.view_combo = QComboBox()
        self.view_combo.addItems([*Camera.PRESETS, "Free orbit"])
        self.view_combo.setParent(self)
        self.view_combo.hide()  # View angles are controlled inside each pane.
        self.visual = QComboBox()
        self.visual.addItems(["Shaded with edges", "Wireframe", "X-Ray"])
        bar.addWidget(self.visual)
        fit = QPushButton("Fit all")
        fit.clicked.connect(self.fit_all)
        bar.addWidget(fit)
        close = QPushButton("Return to drafting")
        close.clicked.connect(self.draft_requested)
        bar.addWidget(close)
        container = QWidget()
        self.grid = QGridLayout(container)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(2)
        self.views = [
            ModelViewport(self, name) for name in ("Top", "Front", "Right", preset)
        ]
        self.active = self.views[3]
        for i, view in enumerate(self.views):
            self.grid.addWidget(view, i // 2, i % 2)
        root.addWidget(container, 1)
        side = self.feature_panel = QWidget(self)
        side.hide()
        side.setMinimumWidth(220)
        panel = QVBoxLayout(side)
        panel.addWidget(QLabel("SAVED MODEL OBJECTS"))
        self.features = QListWidget()
        panel.addWidget(self.features, 1)
        self.info = QLabel()
        self.info.setTextFormat(Qt.TextFormat.PlainText)
        self.info.setWordWrap(True)
        panel.addWidget(self.info)
        for label, callback in [
            ("Edit source object…", self.edit_source),
            ("Rename…", self.rename_feature),
            ("Change height…", self.change_height),
            ("Delete object", self.delete_feature),
            ("Export STEP / STL…", self.export_feature),
        ]:
            button = QPushButton(label)
            button.clicked.connect(callback)
            panel.addWidget(button)
        row = QHBoxLayout()
        panel.addLayout(row)
        for label, callback in [
            ("Undo", self.doc.undo_stack.undo),
            ("Redo", self.doc.undo_stack.redo),
        ]:
            button = QPushButton(label)
            button.clicked.connect(callback)
            row.addWidget(button)
        self.outlines = QPushButton("2D outline overlay")
        self.outlines.setCheckable(True)
        self.outlines.setChecked(False)
        panel.addWidget(self.outlines)
        panel.addWidget(QLabel("Select a saved extrusion or solid above to edit it."))
        self.features.currentRowChanged.connect(self.selection_changed)
        self.view_combo.currentTextChanged.connect(self.change_view)
        self.layout_mode.currentIndexChanged.connect(self.change_layout)
        self.visual.currentTextChanged.connect(self.repaint_views)
        self.outlines.toggled.connect(self.repaint_views)
        self.doc.undo_stack.indexChanged.connect(self.refresh)
        self.layout_mode.setCurrentIndex(0 if four else 1)
        self.refresh()
        self.activate(self.active)
        QTimer.singleShot(0, self.fit_all)

    def closeEvent(self, event):
        self.disconnect_document()
        super().closeEvent(event)

    def disconnect_document(self, *args):
        for view in self.views:
            view.set_graphics_backend("software")
        try:
            self.doc.undo_stack.indexChanged.disconnect(self.refresh)
        except TypeError:
            pass

    def edit_source(self):
        from .building import source_for_solid
        entity = self.doc.find_by_id(source_for_solid(self.doc, self.selected_id()))
        if entity is None:
            QMessageBox.information(self, 'Source object', 'This solid has no live building source.')
            return
        self.mw.viewport_stack.setCurrentWidget(self.mw.canvas)
        self.mw.canvas.selected_entities = [entity]
        self.mw.properties_panel.show()
        self.mw.properties_panel.raise_()
        self.mw.refresh_document_ui()

    def selected_id(self):
        item = self.features.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def selected(self):
        key=self.selected_id()
        if key in self.doc.extensions.get('solids',{}): return {**self.doc.extensions['solids'][key],'id':key,'solid':True}
        return next(
            (f for f in self.doc.extrusions if f["id"] == self.selected_id()), None
        )

    def activate(self, view):
        self.active = view
        self.update_view_label()
        self.repaint_views()

    def update_view_label(self):
        self.view_combo.blockSignals(True)
        self.view_combo.setCurrentText(self.active.camera.name)
        self.view_combo.blockSignals(False)
        for view in self.views:
            view.navigation.sync(view.camera, view.interaction_mode)

    def change_view(self, name):
        if name in Camera.PRESETS:
            self.active.set_view(name)
        elif name == "Free orbit":
            self.active.camera.name = "Free orbit"
            self.active.navigation.set_mode("orbit")
            self.active.update()

    def change_layout(self, index):
        # Keep the active camera when maximizing one pane, even if it is Top.
        for view in self.views:
            self.grid.removeWidget(view)
            view.hide()
        if index == 0:
            for i, view in enumerate(self.views):
                self.grid.addWidget(view, i // 2, i % 2)
                view.show()
        else:
            self.grid.addWidget(self.active, 0, 0, 2, 2)
            self.active.show()
        self.update_view_label()
        self.active.setFocus()

    def fit_all(self):
        for view in self.views:
            view.fit()

    def repaint_views(self, *args):
        for view in self.views:
            view.update()

    def selection_changed(self, *args):
        f = self.selected()
        if f and f.get('solid'):
            self.info.setText(f"{f['name']}\nLayer: {f['layer']}\nOperation: {f['operation']}\nVolume: {f['volume']:g} {self.doc.units}³\n{getattr(self.doc, 'link_status', {}).get(f['id'], 'Snapshot')}")
        else:
            self.info.setText(f"{f['name']}\nLayer: {f['layer']}\nHeight: {f['height']:g} {self.doc.units}" if f else "Select a saved extrusion or solid. Use EXTRUDE, REVOLVE, SWEEP or Solid tools.")
        self.repaint_views()

    def refresh(self, *args):
        selected = self.selected_id()
        self.features.blockSignals(True)
        self.features.clear()
        faces = []
        wires = []
        points = []
        solid_wires=[]
        for feature in self.doc.extrusions:
            item = QListWidgetItem(feature["name"])
            item.setData(Qt.ItemDataRole.UserRole, feature["id"])
            self.features.addItem(item)
            if feature["id"] == selected:
                self.features.setCurrentItem(item)
            if not self.doc.layers.is_visible(feature["layer"]):
                continue
            vertices, indices = feature_mesh(feature)
            points.extend(vertices)
            color = self.doc.layers.layers[feature["layer"]]["color"]
            faces.extend(
                ([vertices[i] for i in face], color, feature["id"]) for face in indices
            )
        for key,solid in self.doc.extensions.get('solids',{}).items():
            item=QListWidgetItem(solid['name']);item.setData(Qt.ItemDataRole.UserRole,key);self.features.addItem(item)
            if key==selected: self.features.setCurrentItem(item)
            from .building import visible, source_for_solid
            if not self.doc.layers.is_visible(solid['layer']) or not visible(self.doc, source_for_solid(self.doc, key)): continue
            vertices=solid['vertices'];points.extend(vertices)
            from .solids import mesh_boundary_wires
            solid_wires.extend((a,b,key) for a,b in mesh_boundary_wires(solid))
            color=self.doc.layers.layers[solid['layer']]['color']
            from .materials import appearance
            material = appearance(self.doc, key)
            if material:
                color = material['color']
            faces.extend(([vertices[i] for i in face],color,key) for face in solid['faces'])
        if self.features.currentRow() < 0 and self.features.count():
            self.features.setCurrentRow(0)
        self.features.blockSignals(False)

        def outlines(entity):
            if not self.doc.layers.is_visible(entity.layer):
                return
            if isinstance(entity, BlockReferenceEntity):
                for child in entity.resolved_entities:
                    outlines(child)
            else:
                for a, b in entity_to_segments(entity):
                    aa = (a.x, a.y, 0)
                    bb = (b.x, b.y, 0)
                    wires.append((aa, bb, self.doc.entity_color(entity)))
                    points.extend([aa, bb])

        for entity in self.doc.visible_entities():
            outlines(entity)
        for view in self.views:
            view.solid_wires=solid_wires
            view.set_scene(faces,wires,points)
        self.selection_changed()

    def edit_feature(self, field, value):
        feature = self.selected()
        if not feature:
            return
        if self.doc.layers.is_locked(feature["layer"]):
            raise ValueError("Unlock the extrusion layer to edit it")
        if feature.get('solid'):
            from .feature_data import edit_table
            if field=='delete': edit_table(self.doc,'solids',feature['id'],None,'Delete solid')
            elif field=='name':
                from .validation import name
                name(value,'Solid name');after=copy.deepcopy(self.doc.extensions['solids'][feature['id']]);after['name']=value;edit_table(self.doc,'solids',feature['id'],after,'Rename solid')
            else: raise ValueError('Edit the source profile or architectural parameters, then regenerate this solid')
            return
        after = copy.deepcopy(self.doc.extrusions)
        if field == "delete":
            after = [f for f in after if f["id"] != feature["id"]]
        else:
            target = next(f for f in after if f["id"] == feature["id"])
            target[field] = value
            from .model3d import validate_feature

            validate_feature(target, self.doc.layers.layers)
        self.doc.undo_stack.push(ExtrusionCommand(self.doc, after, "Edit extrusion"))

    def safe_edit(self, field, value=None):
        try:
            self.edit_feature(field, value)
        except ValueError as ex:
            QMessageBox.warning(self, "Extrusion", str(ex))

    def rename_feature(self):
        f = self.selected()
        if f:
            name, ok = QInputDialog.getText(
                self, "Rename extrusion", "Name:", text=f["name"]
            )
            if ok:
                self.safe_edit("name", name.strip())

    def change_height(self):
        f = self.selected()
        if f and f.get('solid'):
            QMessageBox.information(self,'Saved solid','Edit the source geometry or architectural parameters, then regenerate with Solid tools.');return
        if f:
            height, ok = QInputDialog.getDouble(
                self,
                "Extrusion height",
                "Height in drawing units:",
                f["height"],
                -1e9,
                1e9,
                4,
            )
            if ok:
                self.safe_edit("height", height)

    def delete_feature(self):
        self.safe_edit("delete")

    def export_feature(self):
        f = self.selected()
        if not f:
            return
        path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export saved extrusion",
            "solid.step",
            "STEP (*.step *.stp);;STL (*.stl)",
        )
        if not path:
            return
        from pathlib import Path

        if not Path(path).suffix:
            path += ".stl" if selected_filter.startswith("STL") else ".step"
        try:
            from .extrude3d import extrude_and_export

            if f.get('solid'):
                from .solids import export_solid
                export_solid(self.doc,f['id'],path)
            else: extrude_and_export(profile_entity(f),f['height'],path)
        except ImportError:
            QMessageBox.warning(
                self,
                "3D export",
                "Install requirements-3d.txt to enable STEP/STL export.",
            )
            return
        except Exception as ex:
            QMessageBox.warning(self, "3D export", str(ex))
            return
        self.info.setText("Exported " + Path(path).name)
