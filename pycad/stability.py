"""Repeatable software-rendering measurements; no hardware-independent speed claim."""
import logging,time,statistics,sys
from .native_io import document_to_dict,document_from_dict

def measure(doc,repeats=3):
 if type(repeats) is not int or not 1<=repeats<=20:raise ValueError('Use 1–20 stability repetitions')
 from PyQt6.QtWidgets import QApplication
 from PyQt6.QtCore import QEvent
 from .canvas import CadCanvas
 from .document_lifecycle import dispose_document
 from .geom_ops import pick_entity
 from .drawing_diagnostics import resident_memory
 source=document_to_dict(doc);errors=[];rows=[];memory=[]
 class Capture(logging.Handler):
  def emit(self,record):
   if record.levelno>=logging.ERROR:errors.append(record.getMessage())
 handler=Capture();logger=logging.getLogger('pycad');logger.addHandler(handler)
 try:
  for index in range(repeats):
   start=time.perf_counter();copy=document_from_dict(source);native_equal=document_to_dict(copy)==source;copy.sync_associative();load_ms=(time.perf_counter()-start)*1000
   canvas=CadCanvas(copy);canvas.resize(960,600);canvas.show();canvas.zoom_extents();QApplication.processEvents();copy.render_revision+=1;start=time.perf_counter();image=canvas.grab();render_ms=(time.perf_counter()-start)*1000
   hit=None;pick_ms=None;entities=copy.editable_entities()
   if entities:
    points=entities[0].endpoints()
    if points:
     p=points[0];tolerance=12/max(canvas.zoom,1e-12);start=time.perf_counter();candidates=copy.query_entities((p.x-tolerance,p.y-tolerance,p.x+tolerance,p.y+tolerance),editable_only=True);hit=pick_entity(candidates,p,tolerance);pick_ms=(time.perf_counter()-start)*1000
   rows.append(dict(iteration=index+1,native_decode_sync_ms=load_ms,visible_capture_ms=render_ms,selection_query_pick_ms=pick_ms,picked=hit is not None,native_roundtrip=native_equal,render_nonempty=not image.isNull()));memory.append(resident_memory());canvas.close();canvas.deleteLater();dispose_document(copy);QApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete);QApplication.processEvents()
 finally:logger.removeHandler(handler)
 return dict(rows=rows,objects=len(doc.entities),blocks=len(doc.blocks),original_unchanged=document_to_dict(doc)==source,render_errors=errors,resident_bytes_samples=memory,python=sys.version.split()[0],platform=sys.platform,note='Offscreen/software viewport capture and indexed selection measurements; no universal timing threshold or physical GPU verification. RSS samples include allocator/Qt caches and are not a leak diagnosis.')
