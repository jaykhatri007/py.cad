"""Actual DWG round trips, direct hatch/block mapping, routing and safety."""
import hashlib
from pathlib import Path
import ezdxf
import pytest
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication,QComboBox,QDialog
from pycad import dwg_native,dwg_support,dxf_io,appsettings
from pycad.document import Document
from pycad.geometry import Point,LineEntity,HatchEntity


@pytest.fixture
def actual_dwg(tmp_path):
    doc=ezdxf.new('R2000');doc.units=4
    doc.layers.new('Walls',dxfattribs={'color':3,'flags':4})
    m=doc.modelspace();m.add_line((1,2),(11,22),dxfattribs={'layer':'Walls'})
    m.add_circle((20,20),3);m.add_arc((30,30),4,20,130)
    m.add_lwpolyline([(0,0,.2),(10,0,0),(10,10,0)],format='xyb',close=True)
    h=m.add_hatch();h.paths.add_polyline_path([(0,0),(10,0),(10,10),(0,10)])
    h.paths.add_polyline_path([(2,2),(4,2),(4,4),(2,4)],flags=0)
    hp=m.add_hatch();hp.set_pattern_fill('ANSI31',scale=2,angle=25)
    hp.paths.add_polyline_path([(50,0),(60,0),(60,10),(50,10)])
    b=doc.blocks.new('Desk',base_point=(1,1));b.add_line((1,1),(5,1))
    m.add_blockref('Desk',(40,40),dxfattribs={'rotation':30,'xscale':2,'yscale':2,'zscale':2})
    doc.saveas(tmp_path/'source.dxf')
    dwg_native.run_tool(dwg_native.tool_path('dwgwrite'),['-v0','--as','r2000','-I','DXF','-o','source.dwg','--','source.dxf'],tmp_path)
    return tmp_path/'source.dwg'


def test_real_direct_without_dxf(actual_dwg,monkeypatch):
    before=actual_dwg.read_bytes()
    monkeypatch.setattr(dwg_support,'convert_sync',lambda *a:pytest.fail('DXF called'))
    d=dxf_io.import_dwg(str(actual_dwg),mode='direct')
    assert len(d.entities)==7 and d.units=='mm'
    assert d.layers.layers['Walls']['locked']
    h=next(e for e in d.entities if isinstance(e,HatchEntity))
    assert h.pattern=='SOLID' and len(h.holes)==1 and h.boundary_mode=='evenodd'
    patterned=next(e for e in d.entities if isinstance(e,HatchEntity) and e.pattern!='SOLID')
    assert patterned.pattern=='ANSI31' and patterned.pattern_scale==pytest.approx(2)
    assert patterned.angle==pytest.approx(25)
    assert len(d.blocks['Desk'].entities)==1
    assert any('without an intermediate DXF' in w for w in d.import_warnings)
    assert actual_dwg.read_bytes()==before
    assert d.source_archive['sha256']==hashlib.sha256(before).hexdigest()


def test_real_open_source_export_roundtrip(actual_dwg,tmp_path,monkeypatch):
    original=dxf_io.import_dwg(str(actual_dwg),mode='direct')
    monkeypatch.setattr(dxf_io,'_require_odafc',lambda:pytest.fail('ODA called'))
    target=tmp_path/'new ü.dwg';dxf_io.export_dwg(original,str(target))
    assert target.read_bytes().startswith(b'AC1015')
    d=dxf_io.import_dwg(str(target),mode='auto')
    assert len(d.entities)==len(original.entities)
    assert sum(isinstance(e,HatchEntity) for e in d.entities)==2
    patterned=next(e for e in d.entities if isinstance(e,HatchEntity) and e.pattern!='SOLID')
    assert patterned.pattern=='ANSI31' and patterned.pattern_scale==pytest.approx(2)
    assert patterned.angle==pytest.approx(25)
    assert d.blocks['Desk'].entities[0].bbox()==original.blocks['Desk'].entities[0].bbox()


def test_real_gui_direct(main_window,actual_dwg):
    from pycad.dwg_ui import load_dwg
    d=load_dwg(main_window,str(actual_dwg),mode='direct')
    assert len(d.entities)==7 and any('DWG direct reader:' in w for w in d.import_warnings)
    assert d.filepath==str(actual_dwg)


def test_whole_drawing_fallback(actual_dwg,monkeypatch):
    def unsupported(*a):raise dwg_native.DirectUnsupported('unsupported object')
    monkeypatch.setattr(dwg_native,'read_direct',unsupported)
    d=dxf_io.import_dwg(str(actual_dwg),mode='auto')
    assert len(d.entities)==7 and any('compatibility fallback' in w for w in d.import_warnings)
    with pytest.raises(dwg_native.DirectUnsupported):dxf_io.import_dwg(str(actual_dwg),mode='direct')


def test_corrupt_direct_never_retries(tmp_path,monkeypatch):
    def fail(*a):raise ValueError('reader failed')
    monkeypatch.setattr(dwg_native,'read_direct',fail)
    monkeypatch.setattr(dwg_support,'convert_sync',lambda *a:pytest.fail('corrupt input retried'))
    with pytest.raises(ValueError,match='reader failed'):dxf_io.import_dwg(str(tmp_path/'bad.dwg'),mode='auto')


def test_failed_export_preserves_destination(tmp_path,monkeypatch):
    d=Document();d.add_entity(LineEntity(Point(0,0),Point(3,4)))
    out=tmp_path/'preserve.dwg';out.write_bytes(b'original')
    def fail(*a,**k):raise ValueError('writer failed')
    monkeypatch.setattr(dwg_native,'run_tool',fail)
    with pytest.raises(ValueError,match='writer failed'):dwg_native.export_r2000(d,out)
    assert out.read_bytes()==b'original'


def test_policy_and_override(monkeypatch):
    monkeypatch.delenv('PYCAD_DWG_MODE',raising=False);monkeypatch.delenv('PYCAD_DWG_CONVERTER',raising=False)
    appsettings.get_settings().setValue('dwg/import_mode','auto')
    assert dwg_native.requested_mode()=='auto'
    monkeypatch.setenv('PYCAD_DWG_CONVERTER','/legacy');assert dwg_native.requested_mode()=='compatibility'
    monkeypatch.setenv('PYCAD_DWG_MODE','direct');assert dwg_native.requested_mode()=='direct'
    monkeypatch.setenv('PYCAD_DWG_MODE','bad');assert dwg_native.requested_mode()=='auto'


def test_settings_save_cancel(main_window):
    from pycad.dwg_settings import show_settings
    s=appsettings.get_settings();s.setValue('dwg/import_mode','auto')
    def choose(accept):
        d=next(w for w in QApplication.topLevelWidgets() if isinstance(w,QDialog) and w.windowTitle()=='DWG support and settings')
        d.findChild(QComboBox,'dwg_import_mode').setCurrentIndex(2)
        d.accept() if accept else d.reject()
    QTimer.singleShot(30,lambda:choose(False));assert not show_settings(main_window)
    assert s.value('dwg/import_mode')=='auto'
    QTimer.singleShot(30,lambda:choose(True));assert show_settings(main_window)
    assert s.value('dwg/import_mode')=='compatibility'


def test_unknown_objects_reject_entire_direct_import(tmp_path):
    from pycad.dwg_json import from_data
    with pytest.raises(dwg_native.DirectUnsupported,match='ACAD_PROXY_ENTITY'):
        from_data({'OBJECTS':[{'entity':'ACAD_PROXY_ENTITY','handle':[0,1,5]}]},str(tmp_path/'source.dwg'))


def test_tool_override(tmp_path,monkeypatch):
    monkeypatch.setenv('PYCAD_DWGREAD','relative')
    with pytest.raises(dxf_io.DWGSupportError,match='absolute'):dwg_native.tool_path('dwgread')
    p=tmp_path/'reader';p.write_bytes(b'reader')
    monkeypatch.setenv('PYCAD_DWGREAD',str(p));assert dwg_native.tool_path('dwgread')==p


@pytest.mark.parametrize('version',['2000','2004','2007','2010','2013','2018'])
@pytest.mark.parametrize('name',['Line.dwg','Arc.dwg','circle.dwg','Polyline.dwg','Text.dwg','Ellipse.dwg'])
def test_direct_matches_compatibility_on_upstream_drawings(version,name):
    import os
    from pathlib import Path
    root=os.environ.get('PYCAD_DWG_FIXTURES')
    if not root: pytest.skip('Set PYCAD_DWG_FIXTURES for independent upstream DWG tests')
    source=Path(root)/version/name
    assert source.exists()
    try:
        direct=dxf_io.import_dwg(str(source),mode='direct')
    except dwg_native.DirectUnsupported:
        # Older TEXT samples contain application EED; that requires Auto fallback.
        assert name=='Text.dwg' and version!='2018'
        direct=dxf_io.import_dwg(str(source),mode='auto')
        assert any('compatibility fallback' in w for w in direct.import_warnings)
    compat=dxf_io.import_dwg(str(source),mode='compatibility')
    assert [e.kind for e in direct.entities]==[e.kind for e in compat.entities]
    for a,b in zip(direct.entities,compat.entities):
        assert a.bbox()==pytest.approx(b.bbox(),rel=1e-8,abs=1e-7)
        assert a.color==b.color
        if a.kind=='TEXT': assert a.text==b.text


def test_wrong_writer_output_preserves_destination(tmp_path,monkeypatch):
    d=Document();out=tmp_path/'old.dwg';out.write_bytes(b'original')
    def empty(executable,args,directory,**kwargs):
        (Path(directory)/'output.dwg').write_bytes(b'not DWG')
    monkeypatch.setattr(dwg_native,'run_tool',empty)
    with pytest.raises(ValueError,match='valid R2000'):dwg_native.export_r2000(d,out)
    assert out.read_bytes()==b'original'


@pytest.mark.parametrize('mode',['direct','auto'])
def test_direct_cancel_kills_reader(main_window,tmp_path,monkeypatch,mode):
    import sys
    from PyQt6.QtCore import QProcess
    from PyQt6.QtWidgets import QProgressDialog
    from pycad.dwg_ui import load_dwg
    start=QProcess.start;children=[]
    def slow(process,program,args):
        children.append(process)
        return start(process,sys.executable,['-c','import time;time.sleep(30)'])
    monkeypatch.setattr(QProcess,'start',slow)
    source=tmp_path/'cancel.dwg';source.write_bytes(b'AC1032test')
    def cancel():
        d=next(w for w in QApplication.topLevelWidgets() if isinstance(w,QProgressDialog) and w.isVisible())
        d.canceled.emit()
    QTimer.singleShot(100,cancel)
    assert load_dwg(main_window,str(source),mode=mode) is None
    assert all(p.state()==QProcess.ProcessState.NotRunning for p in children)


def test_gui_auto_direct_spline(main_window):
    import os
    from pycad.dwg_ui import load_dwg
    root=os.environ.get('PYCAD_DWG_FIXTURES')
    if not root:pytest.skip('Set PYCAD_DWG_FIXTURES')
    d=load_dwg(main_window,str(Path(root)/'2018/Spline.dwg'),mode='auto')
    assert any(e.kind=='SPLINE' for e in d.entities)
    assert any('DWG direct reader:' in w for w in d.import_warnings)


def test_modern_color_methods():
    from pycad.dwg_json import color_attributes
    assert color_attributes({'index':256,'rgb':'c3000007'},layer=True)=={'color':7}
    assert color_attributes({'index':256,'rgb':'000000','flag':1})=={'color':256}
    assert color_attributes({'index':256,'rgb':'123456','flag':128})=={'color':256,'true_color':0x123456}


def test_gradient_export_rejected_without_overwriting(tmp_path):
    d=Document();d.add_entity(HatchEntity([Point(0,0),Point(10,0),Point(10,10)],pattern='GRADIENT_LINEAR'))
    out=tmp_path/'gradient.dwg';out.write_bytes(b'original')
    with pytest.raises(ValueError,match='gradient hatches'):dwg_native.export_r2000(d,out)
    assert out.read_bytes()==b'original'
