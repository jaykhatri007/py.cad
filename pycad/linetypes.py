"""Shared simple dash/gap/dot linetypes for screen, PDF, layers and DXF."""
import math
from functools import lru_cache

# Signed drawing-unit lengths: positive dash, negative gap, zero point.
_FAMILIES = {
    'DASHED': ('Dashed', (6,-4)),
    'HIDDEN': ('Hidden edges', (3,-1.5)),
    'CENTER': ('Center line', (12,-2,2,-2)),
    'PHANTOM': ('Phantom / alternate position', (12,-2,2,-2,2,-2)),
    'DASHDOT': ('Dash and dot', (6,-3,0,-3)),
    'DASHDOTDOT': ('Dash and two dots', (6,-2,0,-2,0,-2)),
    'DOTTED': ('Dotted', (0,-3)),
    'BORDER': ('Border: two long dashes and a short dash', (12,-2,12,-2,2,-2)),
    'DIVIDE': ('Divide: long dash and two dots', (12,-2,0,-2,0,-2)),
    'LONGDASH': ('Long dash', (18,-4)),
    'SHORTDASH': ('Short dash', (1.5,-1)),
    'DASH3DOT': ('Dash and three dots', (8,-2,0,-2,0,-2,0,-2)),
}
PATTERNS = {'CONTINUOUS': ()}
DESCRIPTIONS = {'CONTINUOUS': 'Continuous solid line'}
for _name, (_description, _pattern) in _FAMILIES.items():
    for _suffix,_factor,_label in (('',1,''),('2',.5,' — half size'),('X2',2,' — double size')):
        PATTERNS[_name+_suffix]=tuple(v*_factor for v in _pattern)
        DESCRIPTIONS[_name+_suffix]=_description+_label

# ISO dash sequences from the installed ezdxf library, with retained MIT notice.
from ezdxf.tools.pattern import load as _load_hatch_patterns
for _name,_rows in _load_hatch_patterns().items():
    if _name.startswith('ACAD_ISO'):
        PATTERNS[_name]=tuple(_rows[0][3])
        DESCRIPTIONS[_name]='ISO metric dash sequence '+_name.split('ISO')[1].split('W')[0]

NAMES = tuple(PATTERNS)
DXF_NAMES = {name:('DOT'+name[6:] if name.startswith('DOTTED') else name) for name in NAMES}
DXF_NAMES['BYLAYER']='BYLAYER'
DXF_NAMES['BYBLOCK']='BYBLOCK'
FROM_DXF = {name.upper():key for key,name in DXF_NAMES.items()}
FROM_DXF.update({name:name for name in NAMES})
FROM_DXF['BYBLOCK']='BYBLOCK'


def names(bylayer=False):
    return (['BYLAYER','BYBLOCK'] if bylayer else [])+list(NAMES)


def validate_scale(value):
    if type(value) not in (int,float) or not math.isfinite(value) or not 1e-6<=value<=1e6:
        raise ValueError('Linetype scale must be between 0.000001 and 1,000,000')
    return value


def apply_pen(pen,name,world_pixels=1,scale=1,dense_preview=True):
    """Qt dash lengths are pen-width units; keep world spacing independent of weight."""
    from PyQt6.QtCore import Qt
    pen.setStyle(Qt.PenStyle.SolidLine)
    pen.setCapStyle(Qt.PenCapStyle.SquareCap)
    pattern=PATTERNS.get(name,())
    if not pattern:return
    validate_scale(scale)
    factor=abs(world_pixels)*scale
    width=max(pen.widthF(),1e-6)
    # Dense on-screen strokes merge visually; avoid excessive raster work.
    if dense_preview and sum(abs(v) for v in pattern)*factor<2:return
    values=[]
    for index,v in enumerate(pattern):
        # A small nonzero stroke plus a round cap produces a visible dot in Qt.
        values.append(max(.01,abs(v)*factor/width) if v else .01)
    if len(values)%2:values.append(.01)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap if 0 in pattern else Qt.PenCapStyle.FlatCap)
    pen.setDashPattern(values)


def world_pixel_scale(canvas):
    cached=canvas.__dict__.get('_frame_pixel_scale')
    if cached is not None:return cached
    a=canvas.world_to_screen(0,0);b=canvas.world_to_screen(1,0)
    return math.hypot(b.x()-a.x(),b.y()-a.y())


def install_dxf(doc):
    """Write our actual definitions even if ezdxf setup installed a same-name type."""
    for name,pattern in PATTERNS.items():
        if name=='CONTINUOUS':continue
        target=DXF_NAMES[name]
        if target in doc.linetypes:doc.linetypes.remove(target)
        doc.linetypes.add(target,pattern=[sum(abs(v) for v in pattern),*pattern],description=DESCRIPTIONS[name])


@lru_cache(maxsize=64)
def preview_icon(name):
    from PyQt6.QtGui import QIcon,QPixmap,QPainter,QPen,QColor
    from PyQt6.QtCore import Qt
    pix=QPixmap(92,18);pix.fill(Qt.GlobalColor.transparent)
    p=QPainter(pix);pen=QPen(QColor('#66afc4'),1.2)
    apply_pen(pen,name,.9);p.setPen(pen);p.drawLine(2,9,90,9);p.end()
    return QIcon(pix)


def populate_combo(combo,bylayer=False):
    from PyQt6.QtCore import Qt,QSize
    combo.setIconSize(QSize(92,18));combo.setMaxVisibleItems(16)
    for name in names(bylayer):
        combo.addItem(preview_icon(name),name)
        combo.setItemData(combo.count()-1,DESCRIPTIONS.get(name,'Use layer linetype'),Qt.ItemDataRole.ToolTipRole)
