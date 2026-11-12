"""Prepare picking bounds cooperatively while the initial display is built."""
import time,weakref
from PyQt6.QtCore import QObject,QTimer,pyqtSlot
from .spatial_index import SpatialIndex
from .geometry import RayEntity,XLineEntity


class IndexWarmer(QObject):
 def __init__(self,parent):
  super().__init__(parent);self.timer=QTimer(self);self.timer.setSingleShot(True);self.timer.timeout.connect(self.step);self.job=None;self.working=False
 def cancel(self):
  self.timer.stop();self.job=None
 def start(self,doc):
  key=(id(doc.entities),len(doc.entities),doc.render_revision)
  if len(doc.entities)<2000:return
  if not doc.spatial_index._dirty and getattr(doc,'_spatial_collection',None)==key[:2] and getattr(doc,'_spatial_revision',None)==key[2]:return
  if self.job is not None and self.job['key']==key:return
  self.cancel();index=SpatialIndex();self.job=dict(doc=weakref.ref(doc),key=key,index=index,iterator=index.rebuild_iter(doc.entities),unbounded=[],ms=0.)
  self.timer.start(0)
 @pyqtSlot()
 def step(self):
  if self.job is None or self.working:return
  job=self.job;doc=job['doc']()
  if doc is None or (id(doc.entities),len(doc.entities),doc.render_revision)!=job['key']:self.cancel();return
  if not doc.spatial_index._dirty and getattr(doc,'_spatial_collection',None)==job['key'][:2] and getattr(doc,'_spatial_revision',None)==job['key'][2]:self.cancel();return
  self.working=True;start=time.perf_counter()
  try:
   while time.perf_counter()-start<.006:
    try:next(job['iterator'])
    except StopIteration:
     doc.spatial_index=job['index'];doc._spatial_collection=job['key'][:2];doc._spatial_revision=job['key'][2]
     doc._unbounded_entities=[record[0] for record in doc.spatial_index._records.values() if isinstance(record[0],(RayEntity,XLineEntity))]
     doc._spatial_warm_ms=job['ms']+(time.perf_counter()-start)*1000;self.job=None;return
   job['ms']+=(time.perf_counter()-start)*1000;self.timer.start(0)
  except Exception as error:
   doc._spatial_warm_error=repr(error);self.cancel()
  finally:self.working=False
