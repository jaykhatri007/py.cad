"""Tests for pycad.dxf_io - export/import round trips."""
import pytest
from pycad.document import Document
from pycad.geometry import (Point, LineEntity, CircleEntity, ArcEntity, RectangleEntity,
                             TextEntity, HatchEntity)
from pycad import dxf_io, geom_ops


def test_roundtrip_basic_entities(tmp_path):
    doc = Document()
    doc.add_entity(LineEntity(Point(0, 0), Point(10, 0), linetype="DASHED"))
    doc.add_entity(CircleEntity(Point(5, 5), 3, linetype="DOTTED"))
    doc.add_entity(ArcEntity(Point(0, 0), 5, 0, 90))
    doc.add_entity(TextEntity(Point(1, 1), "hello"))

    path = str(tmp_path / "test.dxf")
    dxf_io.export_dxf(doc, path)
    doc2 = dxf_io.import_dxf(path)

    kinds = sorted(e.kind for e in doc2.entities)
    assert kinds == ["ARC", "CIRCLE", "LINE", "TEXT"]

    line2 = next(e for e in doc2.entities if e.kind == "LINE")
    assert line2.linetype == "DASHED"
    circle2 = next(e for e in doc2.entities if e.kind == "CIRCLE")
    assert circle2.linetype == "DOTTED"
    text2 = next(e for e in doc2.entities if e.kind == "TEXT")
    assert text2.text == "hello"


def test_roundtrip_hatch_solid_and_pattern(tmp_path):
    doc = Document()
    doc.add_entity(HatchEntity([Point(0, 0), Point(10, 0), Point(10, 10), Point(0, 10)],
                                pattern="SOLID"))
    doc.add_entity(HatchEntity([Point(20, 0), Point(30, 0), Point(30, 10), Point(20, 10)],
                                pattern="LINES", angle=45, spacing=2))
    path = str(tmp_path / "hatch.dxf")
    dxf_io.export_dxf(doc, path)
    doc2 = dxf_io.import_dxf(path)
    hatches = [e for e in doc2.entities if e.kind == "HATCH"]
    assert len(hatches) == 2
    patterns = sorted(h.pattern for h in hatches)
    assert patterns == ["LINES", "SOLID"]


def test_roundtrip_rectangle_becomes_closed_polyline(tmp_path):
    doc = Document()
    doc.add_entity(RectangleEntity(Point(0, 0), Point(10, 10)))
    path = str(tmp_path / "rect.dxf")
    dxf_io.export_dxf(doc, path)
    doc2 = dxf_io.import_dxf(path)
    assert len(doc2.entities) == 1
    poly = doc2.entities[0]
    assert poly.kind == "LWPOLYLINE"
    assert poly.closed is True
    assert len(poly.points) == 4


def test_export_preserves_volume_of_geometry(tmp_path):
    """Sanity check: a circle's radius should survive the round trip exactly."""
    doc = Document()
    doc.add_entity(CircleEntity(Point(3, 4), 7.5))
    path = str(tmp_path / "circle.dxf")
    dxf_io.export_dxf(doc, path)
    doc2 = dxf_io.import_dxf(path)
    c2 = doc2.entities[0]
    assert c2.radius == pytest.approx(7.5)
    assert c2.center.x == pytest.approx(3)
    assert c2.center.y == pytest.approx(4)


def test_roundtrip_spline(tmp_path):
    from pycad.geometry import SplineEntity
    doc = Document()
    doc.add_entity(SplineEntity([Point(0, 0), Point(5, 10), Point(10, 0), Point(15, 10)]))
    path = str(tmp_path / "spline.dxf")
    dxf_io.export_dxf(doc, path)
    doc2 = dxf_io.import_dxf(path)
    assert len(doc2.entities) == 1
    sp2 = doc2.entities[0]
    assert sp2.kind == "SPLINE"
    assert len(sp2.points) == 4
    for orig, new in zip(doc.entities[0].points, sp2.points):
        assert new.x == pytest.approx(orig.x)
        assert new.y == pytest.approx(orig.y)


def test_roundtrip_radius_and_diameter_dimension(tmp_path):
    from pycad.geometry import DimensionEntity
    doc = Document()
    doc.add_entity(DimensionEntity(Point(0, 0), Point(5, 0), Point(8, 3), dim_style="radius"))
    path = str(tmp_path / "raddim.dxf")
    dxf_io.export_dxf(doc, path)
    doc2 = dxf_io.import_dxf(path)
    texts = [e.text for e in doc2.entities if e.kind == "TEXT"]
    assert "R5.00" in texts


def test_roundtrip_block_and_reference(tmp_path):
    from pycad.geometry import BlockDefinition, BlockReferenceEntity
    doc = Document()
    doc.add_block(BlockDefinition("Bracket", [LineEntity(Point(0, 0), Point(5, 0)),
                                               LineEntity(Point(0, 0), Point(0, 5))]))
    ref = BlockReferenceEntity("Bracket", Point(10, 10), scale=2.0, rotation=0.0)
    ref.rebuild(doc.blocks["Bracket"])
    doc.add_entity(ref)

    path = str(tmp_path / "block.dxf")
    dxf_io.export_dxf(doc, path)
    doc2 = dxf_io.import_dxf(path)

    assert "Bracket" in doc2.blocks
    assert len(doc2.blocks["Bracket"].entities) == 2
    inserts = [e for e in doc2.entities if e.kind == "INSERT"]
    assert len(inserts) == 1
    ins = inserts[0]
    assert ins.scale == pytest.approx(2.0)
    assert len(ins.resolved_entities) == 2
    # scaled 2x and translated to (10,10): (0,0)-(5,0) -> (10,10)-(20,10)
    sub = ins.resolved_entities[0]
    assert sub.p1.x == pytest.approx(10) and sub.p2.x == pytest.approx(20)


def test_roundtrip_layout_and_viewport(tmp_path):
    doc = Document()
    doc.add_entity(CircleEntity(Point(0, 0), 50))
    doc.add_layout("Sheet1", page_width=297, page_height=210)
    path = str(tmp_path / "layout.dxf")
    dxf_io.export_dxf(doc, path)

    import ezdxf
    raw = ezdxf.readfile(path)
    assert "Sheet1" in raw.layouts.names()
    layout = raw.layouts.get("Sheet1")
    viewport_count = sum(1 for e in layout if e.dxftype() == "VIEWPORT")
    assert viewport_count >= 1
