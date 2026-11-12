"""Integration gates for navigating the main workspace without a modal viewer."""

import pytest
from PyQt6.QtCore import Qt, QPoint, QPointF
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QDialog

from pycad.document import Document
from pycad.geometry import Point, RectangleEntity
from pycad.model3d import Camera, create_extrusion
from pycad.native_io import document_to_dict


def choose(navigation, name):
    navigation.view_selector.setCurrentText(name)
    navigation.view_selector.textActivated.emit(name)


def solid(window):
    create_extrusion(window.document, RectangleEntity(Point(0, 0), Point(80, 60)), 40)


def test_startup_controls_are_inside_drafting_canvas(main_window, qapp):
    main_window.resize(1440, 960)
    qapp.processEvents()
    nav = main_window.draft_navigation
    parent = main_window.canvas.viewport()
    for control in (nav, nav.cube, nav.view_selector):
        assert control.isVisible()
        assert control.parentWidget() is parent
        assert parent.rect().contains(control.geometry())
    assert nav.width() == 36
    assert main_window.model_workspace is None
    scale = main_window.canvas.zoom
    QTest.mouseClick(nav.zoom_in_button, Qt.MouseButton.LeftButton)
    assert main_window.canvas.zoom > scale


def test_orbit_button_embeds_model_and_rotates_without_editing(main_window, qapp):
    solid(main_window)
    before_document = document_to_dict(main_window.document)
    QTest.mouseClick(main_window.draft_navigation.orbit_button, Qt.MouseButton.LeftButton)
    qapp.processEvents()
    workspace = main_window.model_workspace
    assert main_window.viewport_stack.currentWidget() is workspace
    assert not isinstance(workspace, QDialog)
    assert workspace.window() is main_window
    assert not qapp.activeModalWidget()
    assert sum(v.isVisible() for v in workspace.views) == 1
    view = workspace.active
    before = view.camera.project((20, 30, 40))
    QTest.mousePress(view, Qt.MouseButton.LeftButton, pos=QPoint(130, 90))
    QTest.mouseMove(view, QPoint(165, 115))
    QTest.mouseRelease(view, Qt.MouseButton.LeftButton, pos=QPoint(165, 115))
    assert view.camera.project((20, 30, 40)) != before
    assert document_to_dict(main_window.document) == before_document
    assert view.navigation.isVisible()


@pytest.mark.parametrize("name", list(Camera.PRESETS))
def test_standard_views_use_the_same_embedded_workspace(main_window, qapp, name):
    choose(main_window.draft_navigation, name)
    qapp.processEvents()
    workspace = main_window.model_workspace
    assert main_window.viewport_stack.currentWidget() is workspace
    assert workspace.active.camera.name == name
    expected = Camera(name)
    assert workspace.active.camera.right == pytest.approx(expected.right)
    assert workspace.active.camera.up == pytest.approx(expected.up)
    main_window.show_drafting()
    choose(main_window.draft_navigation, name)
    assert main_window.model_workspace is workspace


def test_four_panes_keep_controls_inside_when_small(main_window, qapp):
    main_window.open_model_workspace(four=True)
    main_window.resize(900, 650)
    qapp.processEvents()
    for view in main_window.model_workspace.views:
        assert view.isVisible()
        for control in (view.navigation, view.navigation.cube, view.navigation.view_selector):
            assert control.isVisible()
            assert view.rect().contains(control.geometry())
        assert view.navigation.height() == 36  # compact horizontal fallback


def test_camera_survives_layout_and_drafting_switches(main_window, qapp):
    solid(main_window)
    main_window.open_model_workspace(four=True)
    qapp.processEvents()
    workspace = main_window.model_workspace
    view = workspace.views[0]
    view.rotate_camera(28, 13)
    view.zoom_camera(1.25)
    view.camera.pan = (35, 22)
    state = (view.camera.right, view.camera.up, view.camera.scale, view.camera.pan)
    choose(view.navigation, "Single view")
    qapp.processEvents()
    assert workspace.active is view and view.isVisible()
    assert sum(v.isVisible() for v in workspace.views) == 1
    main_window.show_drafting()
    main_window.start_orbit()
    qapp.processEvents()
    assert main_window.model_workspace is workspace
    assert state == (view.camera.right, view.camera.up, view.camera.scale, view.camera.pan)


def test_draw_command_returns_to_existing_drafting_canvas(main_window, qapp):
    canvas = main_window.canvas
    canvas.zoom = 2
    canvas.pan_offset = QPointF(12, 34)
    main_window.start_orbit()
    main_window.set_tool("LINE")
    assert main_window.viewport_stack.currentWidget() is canvas
    assert canvas.zoom == 2 and canvas.pan_offset == QPointF(12, 34)
    assert main_window.current_tool.name == "LINE"
    assert not main_window.model_dock.isVisible()


def test_new_document_disposes_old_model_and_connections(main_window, qapp):
    solid(main_window)
    main_window.start_orbit()
    qapp.processEvents()
    old = main_window.model_workspace
    old_doc = main_window.document
    old_faces = len(old.active.faces)
    main_window._replace_document(Document())
    assert main_window.model_workspace is None
    old_doc.undo_stack.undo()
    assert len(old.active.faces) == old_faces  # detached before deferred deletion
    main_window.start_orbit()
    qapp.processEvents()
    assert main_window.model_workspace.doc is main_window.document
    assert not main_window.model_workspace.active.faces
    assert main_window.model_workspace is not old


def test_drafting_pan_moves_view_without_drawing(main_window, qapp):
    canvas = main_window.canvas
    before = canvas.pan_offset
    QTest.mouseClick(main_window.draft_navigation.pan_button, Qt.MouseButton.LeftButton)
    QTest.mousePress(canvas.viewport(), Qt.MouseButton.LeftButton, pos=QPoint(120, 90))
    QTest.mouseMove(canvas.viewport(), QPoint(155, 115))
    QTest.mouseRelease(canvas.viewport(), Qt.MouseButton.LeftButton, pos=QPoint(155, 115))
    assert canvas.pan_offset != before
    assert not main_window.document.entities
    QTest.keyClick(canvas, Qt.Key.Key_Escape)
    assert not canvas.navigation_pan


def test_orientation_cube_click_and_drag(main_window, qapp):
    main_window.open_model_workspace("Isometric", False)
    qapp.processEvents()
    view = main_window.model_workspace.active
    cube = view.navigation.cube
    polygon = next(poly for poly, name in cube.faces if name == "Top")
    center = QPointF(sum(p.x() for p in polygon) / len(polygon), sum(p.y() for p in polygon) / len(polygon))
    QTest.mouseClick(cube, Qt.MouseButton.LeftButton, pos=center.toPoint())
    assert view.camera.name == "Top"
    QTest.mousePress(cube, Qt.MouseButton.LeftButton, pos=QPoint(40, 40))
    QTest.mouseMove(cube, QPoint(60, 50))
    QTest.mouseRelease(cube, Qt.MouseButton.LeftButton, pos=QPoint(60, 50))
    assert view.camera.name == "Free orbit"
    main_window.show_drafting()
    cube = main_window.draft_navigation.cube
    QTest.mousePress(cube, Qt.MouseButton.LeftButton, pos=QPoint(40, 40))
    QTest.mouseMove(cube, QPoint(65, 55))
    QTest.mouseRelease(cube, Qt.MouseButton.LeftButton, pos=QPoint(65, 55))
    assert main_window.viewport_stack.currentWidget() is main_window.model_workspace
    assert main_window.model_workspace.active.camera.name == "Free orbit"


def test_plain_2d_geometry_remains_visible_in_model_view(main_window, qapp):
    main_window.document.add_entity(RectangleEntity(Point(0, 0), Point(80, 60)))
    main_window.open_model_workspace("Isometric", False)
    qapp.processEvents()
    view = main_window.model_workspace.active
    assert view.wires and not view.faces
    # Wires must be painted even when the optional overlay is off and no solids exist.
    image = view.grab().toImage()
    a, b, _ = view.wires[0]
    midpoint = view.screen(tuple((x + y) / 2 for x, y in zip(a, b)))[0].toPoint()
    assert image.pixelColor(midpoint).name() not in ("#111a25", "#192533")


def test_fit_centers_asymmetric_projected_bounds():
    camera = Camera("Isometric")
    points = [(0, 0, 0), (200, 0, 0), (0, 60, 50)]
    camera.fit(points, 600, 400)
    projected = [camera.project(p) for p in points]
    for axis in (0, 1):
        assert min(p[axis] for p in projected) == pytest.approx(-max(p[axis] for p in projected))


def test_model_keyboard_commands_and_menu_use_embedded_views(main_window, qapp):
    main_window.start_orbit()
    qapp.processEvents()
    workspace = main_window.model_workspace
    QTest.keyClick(workspace.active, Qt.Key.Key_F)
    assert main_window.command_line.hasFocus()
    QTest.keyClicks(main_window.command_line, "RONT")
    QTest.keyClick(main_window.command_line, Qt.Key.Key_Return)
    assert workspace.active.camera.name == "Front"
    main_window.command_line.setText("VPORTS")
    QTest.keyClick(main_window.command_line, Qt.Key.Key_Return)
    qapp.processEvents()
    assert sum(v.isVisible() for v in workspace.views) == 4
    main_window.command_line.setText("PLAN")
    QTest.keyClick(main_window.command_line, Qt.Key.Key_Return)
    assert main_window.viewport_stack.currentWidget() is main_window.canvas
    view_menu = next(a.menu() for a in main_window.menuBar().actions() if a.text() == "&View")
    next(a for a in view_menu.actions() if a.text() == "Free Orbit").trigger()
    assert main_window.model_workspace is workspace
    assert main_window.viewport_stack.currentWidget() is workspace
    assert not qapp.activeModalWidget()


def test_paper_layout_returns_to_drafting_and_orbit_returns_to_model(main_window, qapp):
    main_window.document.create_layout("Sheet 1")
    main_window.start_orbit()
    main_window.space_tabs.setCurrentIndex(1)
    assert main_window.document.current_space == "Sheet 1"
    assert main_window.viewport_stack.currentWidget() is main_window.canvas
    main_window.start_orbit()
    assert main_window.document.current_space == "Model"
    assert main_window.viewport_stack.currentWidget() is main_window.model_workspace
