"""Tests for pycad.layout - the Paper Space layout/viewport data model."""
import pytest
from pycad.geometry import Point
from pycad.layout import Layout, Viewport


def test_viewport_model_to_paper_centers_correctly():
    vp = Viewport(x=10, y=10, width=100, height=80, center=Point(0, 0), scale=1.0)
    paper_pt = vp.model_to_paper(Point(0, 0))
    assert paper_pt.x == pytest.approx(10 + 50)  # x + width/2
    assert paper_pt.y == pytest.approx(10 + 40)  # y + height/2


def test_viewport_model_to_paper_applies_scale():
    vp = Viewport(x=0, y=0, width=100, height=100, center=Point(0, 0), scale=0.5)
    paper_pt = vp.model_to_paper(Point(10, 0))
    # 10 model units * 0.5 scale = 5 paper units, offset from viewport center (50,50)
    assert paper_pt.x == pytest.approx(55)


def test_layout_add_default_viewport_fits_bbox():
    layout = Layout("Sheet1", page_width=297, page_height=210)
    vp = layout.add_default_viewport((-50, -50, 50, 50))
    assert vp.center.x == pytest.approx(0)
    assert vp.center.y == pytest.approx(0)
    assert len(layout.viewports) == 1
    # the viewport should fit within the page with margin
    assert vp.x > 0 and vp.y > 0
    assert vp.x + vp.width < layout.page_width
