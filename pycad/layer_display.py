"""Damage-limited composition over ordered, retained layer display batches."""
import math
from PyQt6.QtCore import QRect,Qt
from PyQt6.QtGui import QPainter,QRegion


def repair(canvas,painter,scene,frame,token,delta):
 """Repair existing pixels in place; unchanged pixels/layer commands survive."""
 if not delta or not delta.damage or frame['token'][:-1]!=token[:-1]:return False
 region=QRegion();view=canvas.viewport()
 for box in delta.damage:
  a=canvas.world_to_screen(box[0],box[1]);b=canvas.world_to_screen(box[2],box[3])
  left=max(0,math.floor(min(a.x(),b.x()))-8);top=max(0,math.floor(min(a.y(),b.y()))-8)
  right=min(view.width(),math.ceil(max(a.x(),b.x()))+9);bottom=min(view.height(),math.ceil(max(a.y(),b.y()))+9)
  if right>left and bottom>top:region|=QRegion(QRect(left,top,right-left,bottom-top))
 if not region.isEmpty():
  target=QPainter(frame['image']);target.setRenderHints(painter.renderHints());target.setFont(painter.font());target.setClipRegion(region)
  try:
   target.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source);target.fillRect(view.rect(),Qt.GlobalColor.transparent);target.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
   rect=region.boundingRect();a=canvas.screen_to_world(rect.left()-32,rect.top()-32);b=canvas.screen_to_world(rect.right()+32,rect.bottom()+32)
   from .persistent_scene import replay
   replay(canvas,target,scene,additions=False,world_box=(min(a.x(),b.x()),min(a.y(),b.y()),max(a.x(),b.x()),max(a.y(),b.y())))
  finally:target.end()
 frame['token']=token;delta.damage.clear();canvas._dirty_region_updates=canvas.__dict__.get('_dirty_region_updates',0)+1
 return True
