import math
import pytest
from PyQt6.QtCore import Qt,QPointF
from PyQt6.QtGui import QPen,QColor,QImage,QPainter
from pycad.linetypes import NAMES,PATTERNS,DXF_NAMES,apply_pen,validate_scale
from pycad.geometry import Point,LineEntity,CircleEntity,PolylineEntity,BlockDefinition,BlockReferenceEntity
from pycad.document import Document
from pycad.native_io import document_to_dict,document_from_dict


@pytest.mark.parametrize('name',NAMES)
def test_every_linetype_native_and_dxf_roundtrip(name,tmp_path):
    import ezdxf
    from pycad.dxf_io import export_dxf,import_dxf
    from pycad.layers_plus import save_state
    doc=Document();doc.linetype_scale=2.5;doc.edit_layer('linetype','0',name)
    doc.current_linetype=name
    for e in [LineEntity(Point(0,0),Point(100,0),linetype=name),CircleEntity(Point(50,50),10,linetype='BYLAYER')]:doc.add_entity(e)
    save_state(doc,'Pattern state')
    assert document_to_dict(document_from_dict(document_to_dict(doc)))==document_to_dict(doc)
    path=tmp_path/'types.dxf';export_dxf(doc,str(path));raw=ezdxf.readfile(path)
    assert raw.header['$LTSCALE']==2.5
    assert raw.layers.get('0').dxf.linetype==DXF_NAMES[name]
    if PATTERNS[name]:
        entry=raw.linetypes.get(DXF_NAMES[name]);values=[v.value for v in entry.pattern_tags.tags if v.code==49]
        assert values==pytest.approx(PATTERNS[name])
    imported=import_dxf(str(path))
    assert not imported.import_warnings
    assert imported.linetype_scale==2.5 and imported.layers.layers['0']['linetype']==name
    assert imported.entities[0].linetype==name and imported.entities[1].linetype=='BYLAYER'


def test_catalogue_has_51_valid_patterns():
    assert len(NAMES)==51 and len(set(NAMES))==51
    for name,pattern in PATTERNS.items():
        if not pattern:continue
        assert len(pattern)%2==0 and all(math.isfinite(v) for v in pattern)
        assert all(v>=0 if i%2==0 else v<0 for i,v in enumerate(pattern))
        assert any(v<0 for v in pattern)
        if name.endswith('X2'):
            assert pattern==pytest.approx([2*v for v in PATTERNS[name[:-2]]])


@pytest.mark.parametrize('scale',[0,-1,float('nan'),float('inf'),1e7,1e-8,'2',True])
def test_scale_rejected_before_native_load(scale):
    doc=Document();data=document_to_dict(doc);data['linetype_scale']=scale
    with pytest.raises(ValueError):document_from_dict(data)


def test_old_drawing_scale_defaults():
    data=document_to_dict(Document());data.pop('linetype_scale')
    assert document_from_dict(data).linetype_scale==1


def test_pen_spacing_does_not_change_with_lineweight():
    thin=QPen(QColor('white'),1);wide=QPen(QColor('white'),4)
    apply_pen(thin,'CENTER',3,2);apply_pen(wide,'CENTER',3,2)
    assert [v*thin.widthF() for v in thin.dashPattern()]==pytest.approx([v*wide.widthF() for v in wide.dashPattern()])
    assert thin.dashPattern()[0]==72
    dense=QPen();apply_pen(dense,'DOTTED',.01)
    assert dense.style()==Qt.PenStyle.SolidLine
    apply_pen(dense,'DOTTED',.01,dense_preview=False)
    assert dense.style()==Qt.PenStyle.CustomDashLine


def test_real_pixels_have_dashes_and_gaps(qapp):
    image=QImage(500,30,QImage.Format.Format_ARGB32);image.fill(QColor('black'))
    p=QPainter(image);pen=QPen(QColor('white'),1);apply_pen(pen,'DASHED',4);p.setPen(pen);p.drawLine(0,15,499,15);p.end()
    assert image.pixelColor(10,15)==QColor('white')
    assert image.pixelColor(30,15)==QColor('black')
    assert image.pixelColor(45,15)==QColor('white')


def test_manager_search_apply_and_undo(main_window,qapp):
    from pycad.linetype_ui import LinetypeDialog,apply_choice
    w=main_window;line=LineEntity(Point(0,0),Point(50,0));w.document.add_entity(line);w.canvas.selected_entities=[line]
    dialog=LinetypeDialog(w);dialog.show();dialog.search.setText('phantom');qapp.processEvents()
    assert dialog.list.count()==3 and not dialog.grab().isNull()
    apply_choice(w,'PHANTOM',2,'selection');assert line.linetype=='PHANTOM' and w.document.linetype_scale==2
    w.document.undo_stack.undo();assert line.linetype=='CONTINUOUS' and w.document.linetype_scale==1
    apply_choice(w,'CENTER',1.5,'layer');assert w.document.layers.layers['0']['linetype']=='CENTER'
    w.document.undo_stack.undo();assert w.document.layers.layers['0']['linetype']=='CONTINUOUS'
    apply_choice(w,'HIDDEN',1,'current');assert w.document.current_linetype=='HIDDEN'
    w.document.undo_stack.undo();assert w.document.current_linetype=='BYLAYER'
    dialog.close()


def test_locked_selection_is_unchanged(main_window):
    from pycad.linetype_ui import apply_choice
    w=main_window;line=LineEntity(Point(0,0),Point(50,0));w.document.add_entity(line);w.canvas.selected_entities=[line]
    w.document.layers.layers['0']['locked']=True
    with pytest.raises(ValueError,match='unlocked'):apply_choice(w,'CENTER',2,'selection')
    assert line.linetype=='CONTINUOUS' and w.document.linetype_scale==1


def test_all_combos_offer_new_types(main_window):
    w=main_window
    assert w.linetype_combo.findText('PHANTOMX2')>=0
    assert w.properties_panel.line.findText('ACAD_ISO15W100')>=0
    assert not w.linetype_combo.itemIcon(w.linetype_combo.findText('CENTER')).isNull()


def test_physical_unit_conversion_preserves_pattern_size(qapp):
    from pycad.unit_conversion import convert_units
    doc=Document();doc.linetype_scale=2;doc.add_entity(LineEntity(Point(0,0),Point(100,0),linetype='CENTER'))
    convert_units(doc,'cm');assert doc.linetype_scale==pytest.approx(.2)
    doc.undo_stack.undo();assert doc.linetype_scale==2
    doc.undo_stack.redo();assert doc.linetype_scale==pytest.approx(.2)


def test_import_warns_for_used_nonmatching_or_complex_types(tmp_path):
    import ezdxf
    from pycad.dxf_io import import_dxf
    raw=ezdxf.new(setup=True);raw.modelspace().add_line((0,0),(50,0),dxfattribs={'linetype':'CENTER','ltscale':2})
    path=tmp_path/'foreign.dxf';raw.saveas(path);doc=import_dxf(str(path))
    assert any('different source definition' in w for w in doc.import_warnings)
    assert any('Individual DXF' in w for w in doc.import_warnings)


def test_block_child_linetype_is_applied_to_painter(qapp):
    from pycad.canvas import CadCanvas
    doc=Document();children=[LineEntity(Point(0,0),Point(50,0),linetype='HIDDEN'),
        LineEntity(Point(0,10),Point(50,10),linetype='BYBLOCK')]
    doc.blocks['T']=BlockDefinition('T',children)
    ref=BlockReferenceEntity('T',Point(0,0),linetype='CENTER');ref.rebuild(doc.blocks['T']);doc.add_entity(ref)
    canvas=CadCanvas(doc);canvas.zoom=4;record={};original=canvas._draw_entity
    def capture(painter,entity):
        if isinstance(entity,LineEntity):record[entity.linetype]=painter.pen().dashPattern()
        return original(painter,entity)
    canvas._draw_entity=capture
    image=QImage(400,200,QImage.Format.Format_ARGB32);image.fill(QColor('black'));painter=QPainter(image)
    canvas._draw_entities(painter);painter.end()
    assert record['HIDDEN']!=record['BYBLOCK']
    assert record['BYBLOCK'][0]/record['HIDDEN'][0]==pytest.approx(4)
    canvas.close()
