"""User-workflow acceptance gates for managers, persistence and model views."""

import math
import pytest
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtWidgets import QToolButton
from PyQt6.QtTest import QTest
from pycad.document import Document
from pycad.geometry import (
    Point,
    LineEntity,
    RectangleEntity,
    CircleEntity,
    DimensionEntity,
)
from pycad import native_io, dxf_io
from pycad.dimstyles import DEFAULT_STYLE, dimension_label, dimension_geometry
from pycad.model3d import create_extrusion, Camera, dot, feature_mesh, profile_entity
from pycad.managers import (
    DimensionStyleManager,
    LayerPropertiesManager,
    AssignStyleCommand,
)
from pycad.view3d import ModelWorkspace


def test_style_edit_changes_existing_dimension_and_undo():
    d = Document()
    e = DimensionEntity(Point(0, 0), Point(123.45, 0), Point(60, 10))
    d.add_entity(e)
    before = dimension_label(e, d.dimstyles["Standard"])
    style = {
        **DEFAULT_STYLE,
        "precision": 1,
        "suffix": " mm",
        "scale": 4,
        "arrow_type": "Tick",
    }
    d.edit_dimstyle("modify", "Standard", style)
    assert dimension_label(e, d.dimstyles["Standard"]) == "123.5 mm"
    assert dimension_geometry(e, d.dimstyles["Standard"])[3] == 10
    d.undo_stack.undo()
    assert dimension_label(e, d.dimstyles["Standard"]) == before
    d.undo_stack.redo()
    assert dimension_geometry(e, d.dimstyles["Standard"])[3] == 10


def test_named_style_native_roundtrip_and_legacy_migration(tmp_path):
    d = Document()
    d.edit_dimstyle(
        "add", "Architectural", {**DEFAULT_STYLE, "precision": 0, "scale": 100}
    )
    e = DimensionEntity(
        Point(0, 0), Point(10, 0), Point(5, 5), style_name="Architectural"
    )
    d.add_entity(e)
    d.edit_dimstyle("current", "Architectural")
    path = tmp_path / "styled.pycad"
    native_io.save_project(d, path)
    loaded = native_io.load_project(path)
    assert loaded.current_dimstyle == "Architectural"
    assert loaded.entities[0].style_name == "Architectural"
    assert loaded.dimstyles["Architectural"]["scale"] == 100
    assert e.clone().style_name == "Architectural"
    old = native_io.document_to_dict(Document())
    old["schema_version"] = 2
    for key in ("dimstyles", "current_dimstyle", "extrusions"):
        old.pop(key)
    old["layers"]["0"] = {
        k: v
        for k, v in old["layers"]["0"].items()
        if k in ("color", "visible", "locked")
    }
    migrated = native_io.document_from_dict(old)
    assert migrated.dimstyles["Standard"] == DEFAULT_STYLE
    assert migrated.layers.layers["0"]["plot"] is True


@pytest.mark.parametrize(
    "field,value",
    [
        ("text_height", 0),
        ("precision", 9),
        ("scale", math.inf),
        ("color", "bad"),
        ("arrow_type", "bad"),
    ],
)
def test_invalid_styles_rejected(field, value):
    d = Document()
    with pytest.raises(ValueError):
        d.edit_dimstyle("modify", "Standard", {**DEFAULT_STYLE, field: value})
    assert d.dimstyles["Standard"] == DEFAULT_STYLE


def test_style_delete_and_assignment(main_window):
    d = main_window.document
    d.edit_dimstyle("add", "Detail")
    e = DimensionEntity(Point(0, 0), Point(10, 0), Point(5, 3))
    d.add_entity(e)
    d.undo_stack.push(AssignStyleCommand(d, [e], "Detail"))
    with pytest.raises(ValueError):
        d.edit_dimstyle("delete", "Detail")
    d.undo_stack.undo()
    assert e.style_name == "Standard"
    d.edit_dimstyle("delete", "Detail")
    assert "Detail" not in d.dimstyles


def test_layer_properties_undo_native_and_dxf(tmp_path):
    d = Document()
    d.edit_layer("add", "Walls", "#93c0d8")
    for key, value in [
        ("frozen", True),
        ("locked", True),
        ("plot", False),
        ("linetype", "DASHED"),
        ("lineweight", 0.5),
    ]:
        d.edit_layer(key, "Walls", value)
    e = LineEntity(Point(0, 0), Point(10, 10), layer="Walls", linetype="BYLAYER")
    d.add_entity(e)
    assert e not in d.visible_entities()
    assert d.entity_linetype(e) == "DASHED"
    for suffix in ("pycad", "dxf"):
        path = tmp_path / ("layers." + suffix)
        if suffix == "pycad":
            native_io.save_project(d, path)
            loaded = native_io.load_project(path)
        else:
            dxf_io.export_dxf(d, path)
            loaded = dxf_io.import_dxf(path)
        props = loaded.layers.layers["Walls"]
        assert props["frozen"] and props["locked"] and not props["plot"]
        assert props["linetype"] == "DASHED" and props["lineweight"] == 0.5
        assert loaded.entities[0].linetype == "BYLAYER"
    d.undo_stack.undo()
    assert d.layers.layers["Walls"]["lineweight"] == 0.25


def test_current_layer_cannot_freeze():
    d = Document()
    with pytest.raises(ValueError):
        d.edit_layer("frozen", "0", True)


def test_saved_extrusion_undo_reopen_and_mesh(tmp_path):
    d = Document()
    rect = RectangleEntity(Point(0, 0), Point(20, 10))
    d.add_entity(rect)
    create_extrusion(d, rect, 15)
    vertices, faces = feature_mesh(d.extrusions[0])
    assert len(vertices) == 8 and len(faces) == 6 and max(p[2] for p in vertices) == 15
    rect.translate(100, 100)  # independent profile snapshot
    assert d.extrusions[0]["profile"]["points"][0] == [0, 0]
    d.undo_stack.undo()
    assert not d.extrusions
    d.undo_stack.redo()
    assert len(d.extrusions) == 1
    path = tmp_path / "model.pycad"
    native_io.save_project(d, path)
    loaded = native_io.load_project(path)
    assert loaded.extrusions == d.extrusions
    assert not loaded.dirty


def test_extrusion_layer_rename_and_delete_protection():
    d = Document()
    d.edit_layer("add", "Body")
    rect = RectangleEntity(Point(0, 0), Point(10, 10), layer="Body")
    create_extrusion(d, rect, 20)
    with pytest.raises(ValueError):
        d.edit_layer("delete", "Body")
    d.edit_layer("rename", "Body", "Structure")
    assert d.extrusions[0]["layer"] == "Structure"
    d.undo_stack.undo()
    assert d.extrusions[0]["layer"] == "Body"
    d.undo_stack.redo()
    assert d.extrusions[0]["layer"] == "Structure"


def test_3d_export_guard_preserves_destination(tmp_path):
    d = Document()
    create_extrusion(d, CircleEntity(Point(0, 0), 5), 10)
    path = tmp_path / "original.dxf"
    path.write_text("original content")
    with pytest.raises(ValueError, match="3D"):
        dxf_io.export_dxf(d, path)
    assert path.read_text() == "original content"


@pytest.mark.parametrize(
    "name,right,up",
    [
        ("Top", (1, 0, 0), (0, 1, 0)),
        ("Front", (1, 0, 0), (0, 0, 1)),
        ("Right", (0, 1, 0), (0, 0, 1)),
        ("Left", (0, -1, 0), (0, 0, 1)),
        ("Bottom", (-1, 0, 0), (0, 1, 0)),
        ("Back", (-1, 0, 0), (0, 0, 1)),
    ],
)
def test_standard_views_are_real_projections(name, right, up):
    c = Camera(name)
    assert c.project(right)[:2] == pytest.approx((1, 0))
    assert c.project(up)[:2] == pytest.approx((0, 1))


def test_free_orbit_remains_orthonormal_across_poles():
    c = Camera()
    before = c.project((8, 12, 20))
    for _ in range(200):
        c.orbit(4, 11)
    assert c.project((8, 12, 20)) != before
    for axis in (c.right, c.up, c.back):
        assert dot(axis, axis) == pytest.approx(1)
    assert dot(c.right, c.up) == pytest.approx(0, abs=1e-12)
    assert dot(c.right, c.back) == pytest.approx(0, abs=1e-12)


def test_managers_save_and_filter_via_widgets(main_window, qapp):
    w = main_window
    style = DimensionStyleManager(w)
    style.show()
    qapp.processEvents()
    style.fields["precision"].setValue(3)
    style.fields["suffix"].setText(" mm")
    style.save_style()
    assert w.document.dimstyles["Standard"]["precision"] == 3
    style.accept()
    w.document.edit_layer("add", "Furniture", "#dcb271")
    layers = LayerPropertiesManager(w)
    layers.show()
    qapp.processEvents()
    layers.search.setText("furn")
    qapp.processEvents()
    assert layers.table.isRowHidden(0) and not layers.table.isRowHidden(1)
    layers.table.cellWidget(1, 8).setChecked(False)
    qapp.processEvents()
    assert not w.document.layers.layers["Furniture"]["plot"]
    layers.accept()


def test_multiview_orbit_height_and_hidden_layer(main_window, qapp):
    d = main_window.document
    d.edit_layer("add", "Solid", "#83bcd4")
    create_extrusion(d, RectangleEntity(Point(0, 0), Point(100, 80), layer="Solid"), 50)
    w = ModelWorkspace(main_window)
    w.show()
    qapp.processEvents()
    assert all(v.isVisible() for v in w.views)
    view = w.views[3]
    before = view.camera.project((10, 20, 30))
    QTest.mousePress(view, Qt.MouseButton.LeftButton, pos=QPoint(80, 80))
    QTest.mouseMove(view, QPoint(130, 100))
    QTest.mouseRelease(view, Qt.MouseButton.LeftButton, pos=QPoint(130, 100))
    assert view.camera.project((10, 20, 30)) != before
    w.view_combo.setCurrentText("Left")
    assert view.camera.name == "Left"
    w.layout_mode.setCurrentIndex(1)
    qapp.processEvents()
    assert sum(v.isVisible() for v in w.views) == 1
    w.edit_feature("height", 90)
    assert d.extrusions[0]["height"] == 90
    d.undo_stack.undo()
    assert d.extrusions[0]["height"] == 50
    d.edit_layer("visible", "Solid", False)
    assert not view.faces
    w.close()


def test_viewport_navigation_rail_controls_views_and_modes(main_window, qapp):
    d = main_window.document
    d.edit_layer("add", "Navigation solid", "#83bcd4")
    create_extrusion(
        d, RectangleEntity(Point(0, 0), Point(100, 80), layer="Navigation solid"), 50
    )
    w = ModelWorkspace(main_window)
    w.show()
    qapp.processEvents()
    view = w.views[3]
    assert view.navigation.isVisible()
    assert view.navigation.view_selector.isVisible()
    assert view.navigation.orbit_button.isChecked()
    assert view.interaction_mode == "orbit"
    view.navigation.view_selector.setCurrentText("Front")
    view.navigation.view_selector.textActivated.emit("Front")
    assert view.camera.name == "Front"
    QTest.mouseClick(view.navigation.pan_button, Qt.MouseButton.LeftButton)
    assert view.interaction_mode == "pan"
    before = view.camera.project((10, 20, 30))
    QTest.mousePress(view, Qt.MouseButton.LeftButton, pos=QPoint(300, 240))
    QTest.mouseMove(view, QPoint(350, 270), delay=5)
    QTest.mouseRelease(view, Qt.MouseButton.LeftButton, pos=QPoint(350, 270))
    assert view.camera.project((10, 20, 30)) == before
    QTest.mouseClick(view.navigation.orbit_button, Qt.MouseButton.LeftButton)
    QTest.mousePress(
        view,
        Qt.MouseButton.MiddleButton,
        Qt.KeyboardModifier.ShiftModifier,
        QPoint(300, 240),
    )
    QTest.mouseMove(view, QPoint(340, 250), delay=5)
    QTest.mouseRelease(view, Qt.MouseButton.MiddleButton, Qt.KeyboardModifier.ShiftModifier, QPoint(340, 250))
    assert view.camera.project((10, 20, 30)) != before
    w.view_combo.setCurrentText("Free orbit")
    assert view.camera.name == "Free orbit"
    assert view.interaction_mode == "orbit"
    assert view.navigation.view_selector.currentText() == "Free orbit"
    view.navigation.view_selector.setCurrentText("Bottom")
    view.navigation.view_selector.textActivated.emit("Bottom")
    assert view.camera.name == "Bottom"
    scale = view.camera.scale
    zoom_in = next(
        button for button in view.navigation.findChildren(QToolButton)
        if button.text() == "+"
    )
    QTest.mouseClick(zoom_in, Qt.MouseButton.LeftButton)
    assert view.camera.scale > scale
    w.close()


def test_saved_feature_regenerates_real_solid_volume():
    pytest.importorskip("cadquery")
    from pycad.extrude3d import extrude_to_solid

    d = Document()
    f = create_extrusion(d, RectangleEntity(Point(0, 0), Point(20, 10)), -15)
    solid = extrude_to_solid(profile_entity(f), f["height"])
    assert solid.val().isValid()
    assert solid.val().Volume() == pytest.approx(3000)


def test_styled_pdf_and_dxf_label_text(tmp_path, qapp):
    import fitz, ezdxf
    from pycad.plotting import export_pdf

    d = Document()
    d.edit_dimstyle(
        "modify", "Standard", {**DEFAULT_STYLE, "precision": 1, "suffix": " mm"}
    )
    d.add_entity(DimensionEntity(Point(0, 0), Point(25.25, 0), Point(12, 8)))
    pdf = tmp_path / "styled.pdf"
    export_pdf(d, pdf)
    with fitz.open(pdf) as doc:
        assert "25.2 mm" in doc[0].get_text()
    dxf = tmp_path / "styled.dxf"
    dxf_io.export_dxf(d, dxf)
    drawing = ezdxf.readfile(dxf)
    assert drawing.modelspace().query("TEXT")[0].dxf.text == "25.2 mm"
    assert len(drawing.modelspace().query("SOLID")) == 2


def test_plot_disabled_layer_and_dimension_arrows_roundtrip(tmp_path, qapp):
    import fitz
    from pycad.geometry import TextEntity
    from pycad.plotting import export_pdf

    d = Document()
    d.edit_layer("add", "No plot")
    d.edit_layer("plot", "No plot", False)
    d.add_entity(TextEntity(Point(0, 0), "DO NOT PLOT", height=3, layer="No plot"))
    d.add_entity(DimensionEntity(Point(0, 0), Point(30, 0), Point(15, 8)))
    pdf = tmp_path / "layer.pdf"
    export_pdf(d, pdf)
    with fitz.open(pdf) as doc:
        assert "DO NOT PLOT" not in doc[0].get_text()
        assert "30.00" in doc[0].get_text()
    path = tmp_path / "dims.dxf"
    dxf_io.export_dxf(d, path)
    reloaded = dxf_io.import_dxf(path)
    assert not reloaded.import_warnings
    assert sum(e.kind == "HATCH" for e in reloaded.entities) == 2


@pytest.mark.parametrize("height", [0, float("inf"), float("nan")])
def test_invalid_extrusions_leave_document_unchanged(height):
    d = Document()
    with pytest.raises(ValueError):
        create_extrusion(d, CircleEntity(Point(0, 0), 5), height)
    assert not d.extrusions and not d.undo_stack.canUndo()


def test_invalid_native_style_and_3d_records_rejected():
    d = Document()
    create_extrusion(d, CircleEntity(Point(0, 0), 5), 10)
    payload = native_io.document_to_dict(d)
    payload["extrusions"][0]["height"] = float("nan")
    with pytest.raises(ValueError):
        native_io.document_from_dict(payload)
    payload = native_io.document_to_dict(d)
    payload["current_dimstyle"] = "Missing"
    with pytest.raises(ValueError):
        native_io.document_from_dict(payload)


def test_self_crossing_profile_is_rejected():
    from pycad.geometry import PolylineEntity

    d = Document()
    polygon = PolylineEntity(
        [Point(0, 0), Point(10, 10), Point(0, 10), Point(10, 0)], closed=True
    )
    with pytest.raises(ValueError):
        create_extrusion(d, polygon, 10)
    assert not d.extrusions
