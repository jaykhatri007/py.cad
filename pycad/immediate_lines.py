"""Camera-scaled native line ink, independent of whole-scene preparation."""
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPen,QColor
from .linetypes import apply_pen


def record(doc,batch):
 lines=[];boxes=[]
 for e in batch:
  if not doc.is_visible(e):continue
  lines.append((e.p1.x,e.p1.y,e.p2.x,e.p2.y,doc.entity_color(e),max(1,doc.layers.layers.get(e.layer,{}).get('lineweight',.25)*3.78),doc.entity_linetype(e),1-e.transparency/100))
  boxes.append(e.bbox())
 if not boxes:return None
 return None,dict(lines=lines,bounds=(min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes)))


def draw(canvas,painter,lines):
 painter.save()
 try:
  painter.setBrush(Qt.BrushStyle.NoBrush)
  for x1,y1,x2,y2,color,width,linetype,opacity in lines:
   pen=QPen(QColor(color));pen.setWidthF(width);pen.setCosmetic(True);apply_pen(pen,linetype,canvas.zoom,canvas.document.linetype_scale)
   painter.setPen(pen);painter.setOpacity(opacity)
   a,b=canvas.world_to_screen(x1,y1),canvas.world_to_screen(x2,y2)
   custom=canvas.document.extensions.get('office_linetypes',{}).get(linetype)
   if custom:
    from .office_ink import draw_path
    from PyQt6.QtGui import QPainterPath
    path=QPainterPath(a);path.lineTo(b);draw_path(painter,path,custom,abs(canvas.zoom)*canvas.document.linetype_scale)
   else:painter.drawLine(a,b)
 finally:painter.restore()


def committed(canvas,entity):
 # Only the most recent temporary ink is retained; model geometry is never
 # discarded. A complete current scene or a document switch clears the queue.
 state=canvas.__dict__.get('_pending_line_ink')
 if state is None or state[0] is not canvas.document:state=(canvas.document,[]);canvas._pending_line_ink=state
 state[1].append(entity)
 if len(state[1])>256:del state[1][:-256]
 canvas.viewport().update()


def paint_pending(canvas,painter):
 state=canvas.__dict__.get('_pending_line_ink')
 if state is None:return
 doc,entities=state
 if doc is not canvas.document:canvas.__dict__.pop('_pending_line_ink',None);return
 live=[e for e in entities if (bool(doc.entities) and doc.entities[-1] is e or doc.contains_entity(e)) and doc.is_visible(e)]
 # Preserve the last complete scene; show newly committed ink above it.
 value=record(doc,live)
 if value:
  lines=value[1]['lines']
  if getattr(canvas,'boq_overlay_enabled',False):lines=[(*line[:4],'#d66565',*line[5:]) for line in lines]
  draw(canvas,painter,lines)
 canvas._pending_line_ink_count=len(live)
