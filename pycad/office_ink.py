"""World-sized repeated labels and strokes for custom office linetypes."""
import math
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QFont, QPainterPath, QPen
from .linetypes import world_pixel_scale

def draw_path(painter,path,recipe,pixels):
    length=path.length()
    dash,gap,height=(recipe[k]*pixels for k in ('dash','gap','height'))
    step=dash+gap
    if length<=0 or step<=0:return
    painter.save()
    try:
        pen=QPen(painter.pen())
        pen.setStyle(Qt.PenStyle.SolidLine)
        painter.setPen(pen)
        if length/step>1024 or step<1:
            painter.drawPath(path)
            return
        path.setCachingEnabled(True)
        strokes=QPainterPath()
        marks=[]
        for i in range(math.ceil(length/step)):
            start=i*step
            end=min(length,start+dash)
            if end>start:strokes.addPath(path.trimmed(start/length,end/length))
            middle=end+gap/2
            if height>=1 and middle+gap/2<=length+1e-7:
                marks.append(path.percentAtLength(middle))
        painter.drawPath(strokes)
        if not marks:return
        # Outline text once, then place that reusable geometry tangent to the path.
        font=QFont(painter.font())
        font.setPixelSize(100)
        glyph=QPainterPath();glyph.addText(QPointF(0,0),font,recipe['text'])
        box=glyph.boundingRect()
        if box.isEmpty():return
        scale=min(height/box.height(),gap*.88/box.width())
        painter.setBrush(pen.color())
        painter.setPen(Qt.PenStyle.NoPen)
        for percent in marks:
            painter.save()
            painter.translate(path.pointAtPercent(percent))
            angle=-path.angleAtPercent(percent)
            angle=(angle+90)%180-90
            painter.rotate(angle)
            painter.scale(scale,scale)
            painter.translate(-box.center())
            painter.drawPath(glyph)
            painter.restore()
    finally:painter.restore()

def draw_custom(canvas,painter,e):
    if e.kind not in ('LINE','CIRCLE','ARC','LWPOLYLINE','POLYLINE','RECTANGLE'):return False
    doc=canvas.document
    style=doc.extensions.get('office_linetypes',{}).get(doc.entity_linetype(e))
    if style is None:return False
    scale=world_pixel_scale(canvas);point=canvas.world_to_screen
    path=QPainterPath()
    if e.kind=='LINE':
        path.moveTo(point(e.p1.x,e.p1.y));path.lineTo(point(e.p2.x,e.p2.y))
    elif e.kind in ('ARC','CIRCLE'):
        c=point(e.center.x,e.center.y);r=e.radius*scale
        rect=QRectF(c.x()-r,c.y()-r,2*r,2*r)
        if e.kind=='CIRCLE':path.addEllipse(rect)
        else:
            a=e.start_angle+getattr(canvas,'_viewport_rotation',0)
            path.arcMoveTo(rect,a);path.arcTo(rect,a,(e.end_angle-e.start_angle)%360)
    else:
        points=e.sample_points()
        if not points:return False
        path.moveTo(point(points[0].x,points[0].y))
        for p in points[1:]:path.lineTo(point(p.x,p.y))
        if e.closed:path.closeSubpath()
    draw_path(painter,path,style,scale*doc.linetype_scale)
    return True
