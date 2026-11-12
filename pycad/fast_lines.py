"""Ordered CPU batches for opaque lines with preserved continuous/dash styles; no model changes."""
from PyQt6.QtCore import QPointF,Qt
from PyQt6.QtGui import QPen,QColor
from .geometry import LineEntity
from .appearance import colors
from .linetypes import apply_pen,world_pixel_scale

class Lines:
 def __init__(self,canvas,painter,selected):
  self.canvas=canvas;self.painter=painter;self.selected=selected;self.styles={};self.style=None;self.points=[];self.count=0
  self.frame=canvas.__dict__.get('_frame_transform');self.ink=colors(canvas)['ui_selection']
 def offer(self,e):
  if type(e) is not LineEntity or e.transparency or self.frame is None:return False
  doc=self.canvas.document;chosen=id(e) in self.selected;key=(e.layer,e.color,e.linetype,chosen)
  if key not in self.styles:
   self.styles[key]=(self.ink if chosen else doc.entity_color(e),max(2 if chosen else 1,doc.layers.layers.get(e.layer,{}).get('lineweight',.25)*3.78),doc.entity_linetype(e))
  style=self.styles[key]
  if style is None or style[2] in doc.extensions.get("office_linetypes",{}):return False
  if style!=self.style:self.flush();self.style=style
  cx,cy,px,py,z=self.frame
  self.points.extend((QPointF(cx+(e.p1.x-px)*z,cy-(e.p1.y-py)*z),QPointF(cx+(e.p2.x-px)*z,cy-(e.p2.y-py)*z)));self.count+=1
  if len(self.points)>=8192:self.flush()
  return True
 def flush(self):
  if not self.points:return
  p=self.painter;p.save()
  try:
   pen=QPen(QColor(self.style[0]));pen.setWidthF(self.style[1]);apply_pen(pen,self.style[2],world_pixel_scale(self.canvas),self.canvas.document.linetype_scale,dense_preview=not self.canvas.__dict__.get('_persistent_recording',False));p.setPen(pen);p.setOpacity(1);p.setBrush(Qt.BrushStyle.NoBrush);p.drawLines(self.points)
  finally:p.restore();self.points=[]
