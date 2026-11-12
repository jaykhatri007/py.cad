"""Temporary viewport tracking and distance/angle locks; never stored in drawings."""
import math
from .geometry import Point

def state(canvas):
 if getattr(canvas,'_aids_document',None) is not canvas.document:
  canvas._aids_document=canvas.document;canvas._draft_aids=dict(points=[],distance=None,angle=None);canvas._draft_feedback=None
 return canvas._draft_aids

def configure(canvas,distance=None,angle=None):
 from .validation import finite
 if distance is not None:finite(distance,'Locked distance',True)
 if angle is not None:finite(angle,'Locked angle')
 s=state(canvas);s.update(distance=distance,angle=angle);canvas.viewport().update()

def add_point(canvas,point):
 from .validation import finite
 finite(point.x,'Tracking x');finite(point.y,'Tracking y');s=state(canvas)
 if len(s['points'])>=20:raise ValueError('Clear temporary tracking points before adding more than 20')
 s['points'].append(Point(point.x,point.y));canvas.viewport().update()

def clear(canvas):
 s=state(canvas);s.update(points=[],distance=None,angle=None);canvas._draft_feedback=None;canvas.viewport().update()

def adjust(canvas,x,y,kind=''):
 s=state(canvas);canvas._draft_feedback=None
 if canvas.document.current_space!='Model' or getattr(canvas._active_tool,'name','') not in ('LINE','PLINE','WALL'):return x,y,kind
 tool=canvas._active_tool;points=getattr(tool,'points',[]);anchor=points[-1] if points else None;label=[]
 if not kind or kind=='Grid':
  tolerance=canvas.snap_radius_px/max(canvas.zoom,1e-12)
  xs=[p.x for p in s['points'] if abs(p.x-x)<=tolerance];ys=[p.y for p in s['points'] if abs(p.y-y)<=tolerance]
  if xs:x=min(xs,key=lambda v:abs(v-x));label.append('Track X')
  if ys:y=min(ys,key=lambda v:abs(v-y));label.append('Track Y')
 if anchor is not None and (s['distance'] is not None or s['angle'] is not None):
  angle=math.radians(s['angle']) if s['angle'] is not None else math.atan2(y-anchor.y,x-anchor.x)
  distance=s['distance'] if s['distance'] is not None else math.hypot(x-anchor.x,y-anchor.y)
  x,y=anchor.x+distance*math.cos(angle),anchor.y+distance*math.sin(angle);label.append('Locked '+('distance ' if s['distance'] is not None else '')+('angle' if s['angle'] is not None else ''))
 text=' · '.join(label) or kind
 if text:canvas._draft_feedback=(Point(x,y),text)
 return x,y,text

def draw(canvas,painter):
 from PyQt6.QtGui import QPen,QColor
 from PyQt6.QtCore import Qt,QRectF
 from .appearance import colors
 ui=colors(canvas);s=state(canvas);painter.save()
 try:
  painter.setPen(QPen(QColor(ui['ui_snap']),1,Qt.PenStyle.DashLine))
  for p in s['points']:
   q=canvas.world_to_screen(p.x,p.y);painter.drawLine(int(q.x()-5),int(q.y()),int(q.x()+5),int(q.y()));painter.drawLine(int(q.x()),int(q.y()-5),int(q.x()),int(q.y()+5))
  feedback=getattr(canvas,'_draft_feedback',None) if getattr(canvas._active_tool,'name','') in ('LINE','PLINE','WALL') else None
  if feedback:
   q,text=feedback;at=canvas.world_to_screen(q.x,q.y)
   for p in s['points']:
    if abs(p.x-q.x)<1e-8 or abs(p.y-q.y)<1e-8:painter.drawLine(canvas.world_to_screen(p.x,p.y),at)
   metrics=painter.fontMetrics();width=min(max(40,metrics.horizontalAdvance(text)+12),max(40,canvas.viewport().width()-96));x=max(8,min(at.x()+12,canvas.viewport().width()-width-80));y=max(4,min(at.y()-30,canvas.viewport().height()-28))
   painter.fillRect(QRectF(x,y,width,24),QColor(ui['ui_overlay']));painter.setPen(QColor(ui['ui_overlay_text']));painter.drawText(QRectF(x+6,y,width-12,24),Qt.AlignmentFlag.AlignVCenter,metrics.elidedText(text,Qt.TextElideMode.ElideRight,int(width-12)))
 finally:painter.restore()
