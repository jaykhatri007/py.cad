"""PAT-compatible hatch families, bounded painting and exact shared definitions.

Definitions come from the installed MIT-licensed ezdxf library, not AutoCAD files.
"""
import math
from functools import lru_cache
from .geometry import Point

EXTRA_FIELDS = {'pattern_scale', 'origin', 'double', 'island_style',
                'pattern_definition', 'background_color', 'gradient_color',
                'source_hole_ids', 'boundary_mode', 'loop_flags'}
GRADIENTS = ('GRADIENT_LINEAR', 'GRADIENT_RADIAL', 'GRADIENT_CONICAL')


@lru_cache(maxsize=1)
def library():
    from ezdxf.tools.pattern import load
    return load()


def pattern_names():
    return ['LINES', 'SOLID', *GRADIENTS, *sorted(library())]


def validate_definition(definition):
    from .validation import finite
    if not isinstance(definition, (list, tuple)) or not 1 <= len(definition) <= 128:
        raise ValueError('A PAT pattern needs 1–128 line families')
    for row in definition:
        if not isinstance(row, (list, tuple)) or len(row) != 4:
            raise ValueError('Invalid PAT line family')
        angle, base, offset, dashes = row
        finite(angle, 'PAT angle')
        for pair in (base, offset):
            if not isinstance(pair, (list, tuple)) or len(pair) != 2:
                raise ValueError('Invalid PAT point/offset')
            for v in pair: finite(v, 'PAT coordinate')
        a = math.radians(angle)
        if abs(-math.sin(a)*offset[0]+math.cos(a)*offset[1]) < 1e-10:
            raise ValueError('PAT rows must have nonzero perpendicular spacing')
        if not isinstance(dashes, (list, tuple)) or len(dashes) > 128:
            raise ValueError('Too many PAT dash items')
        for v in dashes: finite(v, 'PAT dash')
        if dashes and sum(abs(v) for v in dashes) < 1e-10:
            raise ValueError('PAT dash cycle must have a nonzero length')


def validate_options(e):
    from .validation import finite, color, name
    if e.get('boundary_mode', 'strict') not in ('strict', 'evenodd'):
        raise ValueError('Invalid hatch boundary mode')
    flags = e.get('loop_flags',[])
    if (not isinstance(flags,list) or flags and len(flags)!=1+len(e.get('holes',[]))
            or any(type(v) is not int or not 0 <= v <= 255 for v in flags)):
        raise ValueError('Invalid hatch path flags')
    pattern = e.get('pattern', 'LINES')
    definition = e.get('pattern_definition', [])
    if not isinstance(definition,(list,tuple)):raise ValueError('Pattern definition must be a list')
    if definition: validate_definition(definition)
    if not isinstance(pattern, str) or (pattern not in pattern_names() and not definition):
        raise ValueError('Unknown hatch pattern; import its PAT definition first')
    name(pattern, 'Pattern name')
    finite(e.get('pattern_scale', 1), 'Pattern scale', True)
    finite(e.get('spacing', 5), 'Hatch spacing', True)
    finite(e.get('angle', 45), 'Hatch angle')
    origin = e.get('origin', Point(0, 0))
    if isinstance(origin, dict):
        from .validation import point
        point(origin);origin = Point(*origin['point'])
    if not isinstance(origin, Point): raise ValueError('Invalid hatch origin')
    finite(origin.x, 'Origin X'); finite(origin.y, 'Origin Y')
    if type(e.get('double', False)) is not bool: raise ValueError('Double hatch must be boolean')
    if e.get('island_style', 'normal') not in ('normal', 'outer', 'ignore'):
        raise ValueError('Invalid island style')
    if e.get('background_color') is not None: color(e['background_color'], False)
    color(e.get('gradient_color', '#0088ff'), False)
    refs = e.get('source_hole_ids', [])
    if not isinstance(refs, list) or len(refs) > 10000: raise ValueError('Invalid island links')
    if refs and len(refs)!=len(e.get('holes',[])):raise ValueError('Island links must match the stored island loops')
    for ref in refs:
        if ref is not None: name(ref, 'Island source ID')


def definitions(hatch):
    if hatch.pattern == 'LINES' and not hatch.pattern_definition:
        rows = [[0, [0, hatch.spacing/2], [0, hatch.spacing], []]]
    else:
        rows = hatch.pattern_definition or library().get(hatch.pattern, [])
    from ezdxf.tools.pattern import scale_pattern
    rows = scale_pattern(rows, hatch.pattern_scale, hatch.angle)
    if hatch.double:
        rows += scale_pattern(rows, 1, 90)
    return [[a, (b[0]+hatch.origin.x, b[1]+hatch.origin.y), o, d]
            for a, b, o, d in rows]


def render_loops(hatch):
    loops = [hatch.boundary, *hatch.holes]
    if hatch.loop_flags:
        if hatch.island_style == 'normal': return loops
        mask = 1 if hatch.island_style == 'ignore' else 17
        return [loop for loop, flags in zip(loops,hatch.loop_flags) if flags & mask]
    return [hatch.boundary, *island_loops(hatch)]


def island_loops(hatch):
    if hatch.island_style == 'ignore': return []
    if hatch.island_style == 'normal': return hatch.holes
    from .geom_ops import point_in_polygon
    return [loop for i, loop in enumerate(hatch.holes)
            if not any(point_in_polygon(loop[0], other)
                       for j, other in enumerate(hatch.holes) if i != j)]


def segments(hatch, bounds, limit=60000):
    """Dash phase stays anchored in world coordinates when panning/zooming.

    Every loop has a hard work budget, including empty/gap-only PAT families.
    The caller clips segments against the same polygon path used for solid fill.
    """
    x0, y0, x1, y1 = bounds
    emitted = 0
    work = 0
    for angle, base, offset, dashes in definitions(hatch):
        a = math.radians(angle); dx, dy = math.cos(a), math.sin(a)
        nx, ny = -dy, dx
        row_step = offset[0]*nx+offset[1]*ny
        if abs(row_step) < 1e-15:raise ValueError('Hatch row spacing is too dense; increase scale')
        corners = [(x, y) for x in (x0,x1) for y in (y0,y1)]
        indices = [((x-base[0])*nx+(y-base[1])*ny)/row_step for x,y in corners]
        first, last = math.ceil(min(indices)), math.floor(max(indices))
        if last-first > limit: raise ValueError('Hatch is too dense; increase its scale')
        cycle = sum(abs(v) for v in dashes)
        for row in range(first, last+1):
            work += 1
            if work > limit*4: raise ValueError('Hatch work limit reached; increase scale')
            bx, by = base[0]+row*offset[0], base[1]+row*offset[1]
            ts = [(x-bx)*dx+(y-by)*dy for x,y in corners]
            low, high = min(ts), max(ts)
            if not dashes or cycle < 1e-15:
                spans = [(low, high)]
            else:
                spans = []
                start, stop = math.floor(low/cycle), math.floor(high/cycle)
                if (stop-start+1)*len(dashes) > limit*4:
                    raise ValueError('PAT dashes are too dense; increase scale')
                for repeat in range(start, stop+1):
                    t = repeat*cycle
                    for dash in dashes:
                        work += 1
                        if work > limit*4: raise ValueError('Hatch work limit reached; increase scale')
                        end = t+abs(dash)
                        if dash >= 0 and end >= low and t <= high:
                            spans.append((max(low,t),min(high,end)))
                        t = end
            for start, end in spans:
                emitted += 1
                if emitted > limit: raise ValueError('Hatch stroke limit reached; increase scale')
                yield Point(bx+start*dx, by+start*dy), Point(bx+end*dx, by+end*dy)


def paint(canvas, painter, hatch):
    from PyQt6.QtCore import Qt, QPointF
    from PyQt6.QtGui import QPainterPath, QColor, QBrush, QLinearGradient, QRadialGradient, QConicalGradient
    path = QPainterPath(); path.setFillRule(Qt.FillRule.OddEvenFill)
    for loop in render_loops(hatch):
        if not loop: continue
        path.moveTo(canvas.world_to_screen(loop[0].x, loop[0].y))
        for p in loop[1:]: path.lineTo(canvas.world_to_screen(p.x,p.y))
        path.closeSubpath()
    painter.save()
    try:
        painter.setClipPath(path, Qt.ClipOperation.IntersectClip)
        foreground = painter.pen().color()
        if hatch.background_color: painter.fillPath(path, QColor(hatch.background_color))
        if hatch.pattern == 'SOLID': painter.fillPath(path, foreground); return
        if hatch.pattern in GRADIENTS:
            x0,y0,x1,y1 = hatch.bbox(); cx,cy=(x0+x1)/2,(y0+y1)/2
            a=math.radians(hatch.angle); r=math.hypot(x1-x0,y1-y0)/2
            center=canvas.world_to_screen(cx,cy)
            start=canvas.world_to_screen(cx-r*math.cos(a),cy-r*math.sin(a))
            end=canvas.world_to_screen(cx+r*math.cos(a),cy+r*math.sin(a))
            if hatch.pattern == 'GRADIENT_LINEAR': g=QLinearGradient(start,end)
            elif hatch.pattern == 'GRADIENT_RADIAL': g=QRadialGradient(center, max(1,math.hypot(end.x()-center.x(),end.y()-center.y())))
            else: g=QConicalGradient(center,hatch.angle)
            g.setColorAt(0,foreground); g.setColorAt(1,QColor(hatch.gradient_color))
            painter.fillPath(path,QBrush(g)); return
        bounds=hatch.bbox()
        # Intersect the viewport's inverse affine bounds with the hatch bounds.
        if not hasattr(canvas,'_plot_mm'):
            o=canvas.world_to_screen(0,0); px=canvas.world_to_screen(1,0); py=canvas.world_to_screen(0,1)
            ax,ay=px.x()-o.x(),px.y()-o.y(); bx,by=py.x()-o.x(),py.y()-o.y(); det=ax*by-ay*bx
            if abs(det)<1e-24:return
            def inverse(x,y):
                x-=o.x();y-=o.y();return ((x*by-y*bx)/det,(ax*y-ay*x)/det)
            v=canvas.viewport(); pts=[inverse(x,y) for x,y in ((0,0),(v.width(),0),(0,v.height()),(v.width(),v.height()))]
            xs,ys=zip(*pts)
            bounds=(max(bounds[0],min(xs)),max(bounds[1],min(ys)),min(bounds[2],max(xs)),min(bounds[3],max(ys)))
            if bounds[0]>bounds[2] or bounds[1]>bounds[3]:return
            # Use the actual active transform, including paper-space viewports.
            pixel_scale=min(math.hypot(ax,ay),math.hypot(bx,by))
            if any(abs(-math.sin(math.radians(a))*off[0]+math.cos(math.radians(a))*off[1])*pixel_scale < 2
                   for a,_,off,_ in definitions(hatch)):
                painter.fillPath(path,QBrush(foreground,Qt.BrushStyle.Dense4Pattern));return
        # Preflight before painting: no partially painted/truncated patterns.
        try: strokes=list(segments(hatch,bounds,200000 if hasattr(canvas,'_plot_mm') else 12000))
        except ValueError:
            if hasattr(canvas,'_plot_mm'): raise
            painter.fillPath(path,QBrush(foreground,Qt.BrushStyle.Dense4Pattern));return
        for p,q in strokes:
            p,q=canvas.world_to_screen(p.x,p.y),canvas.world_to_screen(q.x,q.y)
            if p==q:painter.drawPoint(p)
            else:painter.drawLine(p,q)
    finally:painter.restore()


def read_pat(path):
    from pathlib import Path
    from ezdxf.tools.pattern import parse
    p=Path(path)
    if p.stat().st_size>2*1024*1024:raise ValueError('PAT file exceeds 2 MiB')
    result=parse(p.read_text(encoding='utf-8-sig'))
    if not result or len(result)>512:raise ValueError('PAT file must contain 1–512 patterns')
    for name,definition in result.items():
        validate_options({'pattern':name,'pattern_definition':definition})
    return result


def bridge_gaps(entities,tolerance):
    """Temporary short endpoint joins for pick-point detection; source is untouched."""
    from .geometry import LineEntity
    if not math.isfinite(tolerance) or tolerance<0:raise ValueError('Gap tolerance must be finite and nonnegative')
    entities=list(entities)
    if tolerance==0:return entities
    ends=[]
    for entity in entities:
        if entity.kind in ('LINE','ARC','LWPOLYLINE') and not getattr(entity,'closed',False):
            points=entity.endpoints()
            if len(points)>=2:ends.extend([points[0],points[-1]])
    if len(ends)>2048:raise ValueError('Gap closing supports up to 2,048 endpoints; narrow the boundary set')
    loose=[i for i,p in enumerate(ends) if not any(i!=j and p.distance_to(q)<1e-8 for j,q in enumerate(ends))]
    used=set()
    for i in loose:
        if i in used:continue
        candidates=[j for j in loose if j!=i and j not in used and ends[i].distance_to(ends[j])<=tolerance]
        if candidates:
            j=min(candidates,key=lambda j:ends[i].distance_to(ends[j]));used.update((i,j))
            entities.append(LineEntity(Point(ends[i].x,ends[i].y),Point(ends[j].x,ends[j].y)))
    return entities
