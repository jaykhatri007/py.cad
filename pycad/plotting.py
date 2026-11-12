"""Vector PDF plots in physical millimetres, independent of zoom and grid."""

import math
from PyQt6.QtGui import QPdfWriter, QPainter, QPageSize, QPageLayout, QFont, QFontMetricsF
from PyQt6.QtCore import QSizeF, QMarginsF, QPointF, QRectF
from .canvas import CadCanvas
from .native_io import atomic_write

UNIT_MM = {"mm": 1.0, "cm": 10.0, "m": 1000.0, "in": 25.4, "ft": 304.8, "unitless": 1.0}


def plot_bounds(document, entity, font):
    """Include dimension labels and arrows when fitting a model-space plot."""
    from .geometry import DimensionEntity
    if entity.kind == 'MLEADER':
        from .mleaders import style_for
        rendered = entity.clone()
        rendered._mleader_style = style_for(document, entity)
        return rendered.bbox()
    if not isinstance(entity, DimensionEntity):
        return entity.bbox()
    from .dimstyles import dimension_geometry, dimension_label, style_for
    style = style_for(document, entity)
    lines, fills, anchor, height = dimension_geometry(entity, style)
    points = [p for pair in lines for p in pair] + [p for triangle in fills for p in triangle]
    measurement_font = QFont(font)
    measurement_font.setPixelSize(1000)
    width = QFontMetricsF(measurement_font).horizontalAdvance(dimension_label(entity, style)) * height / 1000
    left = anchor.x - width / 2 if entity.dim_style not in ('radius','diameter') else anchor.x
    from .geometry import Point
    points += [Point(left-height*.1, anchor.y-height*.3), Point(left+width+height*.1, anchor.y+height*1.2)]
    return min(p.x for p in points), min(p.y for p in points), max(p.x for p in points), max(p.y for p in points)


def export_pdf(document, filepath, space="Model", scale_denominator=None):
    return publish_pdf(document,filepath,[space],scale_denominator=scale_denominator)


def publish_pdf(document,filepath,spaces,scale_denominator=None,preset=None):
    from .sheets import DEFAULT_PRESET,validate_preset,draw_title
    from .layers_plus import overrides
    settings={**DEFAULT_PRESET,**(preset or {})}
    if scale_denominator is not None: settings['scale_denominator']=scale_denominator
    validate_preset(settings)
    if not isinstance(spaces,(list,tuple)) or not spaces or len(spaces)>1000: raise ValueError('Choose 1–1,000 drawing sheets')
    for space in spaces:
        if space!='Model' and space not in document.layouts: raise ValueError('Layout does not exist')
    document.sync_associative()
    from .connected_models import require_current_plot_views
    require_current_plot_views(document, spaces)
    def write(path):
        writer=QPdfWriter(path);writer.setResolution(600);writer.setTitle('PY.cad drawing sheets')
        painter=QPainter();renderer=CadCanvas(document);px=writer.resolution()/25.4
        renderer._plot_pen_width=.25*px;renderer._plot_mm=px;renderer._plot_arrow_size=2*px;renderer._plot_text_height=2.5*px;renderer._monochrome=settings['monochrome']
        def draw(transform,scale,rect,layer_overrides=None,clip=None,clip_transform=None,annotation_scale=1,rotation=0):
            painter.save()
            try:
                painter.setClipRect(rect)
                if clip:
                    from .viewport_plus import clip_path
                    from PyQt6.QtCore import Qt
                    painter.setClipPath(clip_path(clip,clip_transform),Qt.ClipOperation.IntersectClip)
                renderer._annotation_scale=annotation_scale;renderer._viewport_rotation=rotation
                renderer.world_to_screen=transform;renderer.zoom=scale;renderer._viewport_override=layer_overrides or {};renderer._draw_entities(painter,paper=True)
            finally: painter.restore()
        try:
            for page_index,space in enumerate(spaces):
                layout=document.layouts.get(space) if space!='Model' else None
                width,height=(layout.page_width,layout.page_height) if layout else (settings['page_width'],settings['page_height'])
                page=QPageSize(QSizeF(width,height),QPageSize.Unit.Millimeter,'PY.cad sheet');writer.setPageLayout(QPageLayout(page,QPageLayout.Orientation.Portrait,QMarginsF(0,0,0,0)))
                if page_index==0:
                    if not painter.begin(writer): raise OSError('Unable to open PDF output')
                elif not writer.newPage(): raise OSError('Unable to add PDF page')
                if layout:
                    for index,v in enumerate(layout.viewports):
                        from .viewport_plus import config,paper_point
                        cfg=config(document,space,index)
                        def transform(x,y,v=v,cfg=cfg):
                            p=paper_point(v,x,y,cfg["rotation"]);return QPointF(p.x*px,(height-p.y)*px)
                        draw(transform,v.scale*px,QRectF(v.x*px,(height-v.y-v.height)*px,v.width*px,v.height*px),overrides(document,space,index),cfg["clip"],lambda x,y:QPointF(x*px,(height-y)*px),cfg["annotation_scale"],cfg["rotation"])
                    renderer.world_to_screen=lambda x,y:QPointF(x*px,(height-y)*px);renderer.zoom=px;renderer._viewport_override={};renderer._annotation_scale=1;renderer._viewport_rotation=0;draw_title(renderer,painter,space)
                else:
                    entities=[e for e in document.visible_entities() if document.layers.layers.get(e.layer,{}).get('plot',True)]
                    from .underlays import bounds
                    boxes=[plot_bounds(document,e,painter.font()) for e in entities]+bounds(document,plot=True)
                    if not boxes: raise ValueError('There is no visible geometry to plot')
                    x0=min(b[0] for b in boxes);y0=min(b[1] for b in boxes);x1=max(b[2] for b in boxes);y1=max(b[3] for b in boxes);w,h=max(x1-x0,1e-9),max(y1-y0,1e-9);margin=settings['margin']
                    denominator=settings['scale_denominator'];scale=UNIT_MM[document.units]/denominator if denominator else min((width-2*margin)/w,(height-2*margin)/h)
                    if w*scale>width-2*margin+1e-7 or h*scale>height-2*margin+1e-7: raise ValueError('Drawing exceeds the printable page at this scale. Choose a smaller scale or a Layout.')
                    cx,cy=(x0+x1)/2,(y0+y1)/2
                    draw(lambda x,y:QPointF((width/2+(x-cx)*scale)*px,(height/2-(y-cy)*scale)*px),scale*px,QRectF(margin*px,margin*px,(width-2*margin)*px,(height-2*margin)*px))
        finally:
            if painter.isActive(): painter.end()
            renderer.deleteLater()
    atomic_write(filepath,write)
