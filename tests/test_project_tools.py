import copy
import pytest
from PyQt6.QtWidgets import QInputDialog, QDialog
from pycad.document import Document
from pycad.geometry import (
    Point,
    LineEntity,
    CircleEntity,
    RectangleEntity,
    TextEntity,
    BlockDefinition,
)
from pycad.native_io import (
    document_to_dict,
    document_from_dict,
    save_project,
    load_project,
)
from pycad.project_tools import (
    TranslateLayerCommand,
    capture_standard,
    check_standard,
    validate_standard,
    valid_link,
)
from pycad.dxf_io import export_dxf, import_dxf


@pytest.mark.parametrize(
    "factory",
    [
        lambda: LineEntity(Point(0, 0), Point(10, 10)),
        lambda: CircleEntity(Point(0, 0), 4),
        lambda: RectangleEntity(Point(0, 0), Point(5, 5)),
        lambda: TextEntity(Point(0, 0), "Label"),
    ],
)
def test_new_object_properties_survive_clone_and_native(qapp, factory):
    d = Document()
    e = factory()
    e.transparency = 65.5
    e.hyperlink = "https://example.com/detail"
    d.entities = [e]
    clone = e.clone()
    assert (
        clone.transparency == 65.5
        and clone.hyperlink == e.hyperlink
        and clone.id != e.id
    )
    restored = document_from_dict(document_to_dict(d)).entities[0]
    assert restored.transparency == 65.5 and restored.hyperlink == e.hyperlink


def test_transparency_and_hyperlink_dxf_roundtrip(qapp, tmp_path):
    d = Document()
    e = CircleEntity(Point(3, 4), 5)
    e.transparency = 50
    e.hyperlink = "https://example.com/circle"
    d.entities = [e]
    path = tmp_path / "properties.dxf"
    export_dxf(d, str(path))
    restored = import_dxf(str(path)).entities[0]
    assert restored.transparency == pytest.approx(50, abs=0.5)
    assert restored.hyperlink == e.hyperlink


def test_transparency_command_undo_and_pdf_render(main_window, monkeypatch, tmp_path):
    w = main_window
    e = LineEntity(Point(0, 0), Point(10, 10))
    w.document.entities = [e]
    w.canvas.selected_entities = [e]
    monkeypatch.setattr(QInputDialog, "getDouble", lambda *a, **k: (40, True))
    w.run_ribbon_command("TRANSPARENCY")
    assert e.transparency == 40
    w.document.undo_stack.undo()
    assert e.transparency == 0
    w.document.undo_stack.redo()
    assert e.transparency == 40
    from pycad.plotting import export_pdf

    path = tmp_path / "alpha.pdf"
    export_pdf(w.document, str(path))
    assert path.read_bytes().startswith(b"%PDF")


def test_layer_translation_does_not_corrupt_existing_target_features(qapp):
    d = Document()
    d.layers.add_layer("Source")
    d.layers.add_layer("Target")
    source = LineEntity(Point(0, 0), Point(10, 0), layer="Source")
    target = CircleEntity(Point(2, 2), 3, layer="Target")
    block = BlockDefinition("Block", [source.clone()])
    d.blocks["Block"] = block
    d.entities = [source, target]
    # Track the exact subset of extrusion records affected by a layer merge.
    source_feature = {"layer": "Source"}
    target_feature = {"layer": "Target"}
    d.extrusions = [source_feature, target_feature]
    command = TranslateLayerCommand(d, "Source", "Target")
    command.redo()
    assert (
        source.layer == block.entities[0].layer == "Target"
        and "Source" not in d.layers.layers
    )
    command.undo()
    assert source.layer == block.entities[0].layer == "Source"
    assert (
        target.layer == "Target"
        and target_feature["layer"] == "Target"
        and source_feature["layer"] == "Source"
    )


def test_layer_zero_translation_retains_required_layer(qapp):
    d = Document()
    d.layers.add_layer("New")
    e = LineEntity(Point(0, 0), Point(1, 1))
    d.entities = [e]
    d.undo_stack.push(TranslateLayerCommand(d, "0", "New"))
    assert "0" in d.layers.layers and e.layer == "New"
    restored = document_from_dict(document_to_dict(d))
    assert restored.entities[0].layer == "New"
    d.undo_stack.undo()
    assert e.layer == "0"


def test_standards_report_persistence_and_invalid_profiles(qapp, tmp_path):
    d = Document()
    d.layers.add_layer("Walls")
    d.cad_standard = capture_standard(d)
    assert check_standard(d) == []
    d.layers.layers["Walls"]["color"] = "#FF0000"
    d.units = "cm"
    d.layers.add_layer("Extra")
    issues = check_standard(d)
    assert {i[0] for i in issues} == {"color", "Drawing units", "Extra layer"}
    path = tmp_path / "standards.pycad"
    save_project(d, path)
    assert check_standard(load_project(path)) == issues
    bad = copy.deepcopy(d.cad_standard)
    bad["format"] = "DWS"
    with pytest.raises(ValueError, match="DWS"):
        validate_standard(bad)


@pytest.mark.parametrize(
    "link",
    [
        "javascript:alert(1)",
        "file:///tmp/project",
        "https://",
        "https://example.com/\nfile",
    ],
)
def test_unsafe_or_malformed_links_rejected(qapp, link):
    assert not valid_link(link)
    d = Document()
    e = CircleEntity(Point(0, 0), 1)
    e.hyperlink = link
    d.entities = [e]
    with pytest.raises(ValueError):
        document_from_dict(document_to_dict(d))


def test_standards_dialog_commands_are_live(main_window, monkeypatch):
    w = main_window
    w.document.cad_standard = capture_standard(w.document)
    monkeypatch.setattr(QDialog, "exec", lambda self: 0)
    for name in ("STANDARDS", "CONFIGURESTANDARDS", "CHECKSTANDARDS"):
        w.run_ribbon_command(name)
    assert "Command failed" not in w.command_history.toPlainText()
def test_malformed_ipv6_hyperlink_is_rejected():
    from pycad.project_tools import valid_link
    assert not valid_link("https://[not-an-ipv6-address")
