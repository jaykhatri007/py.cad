"""Cooperative model preparation outside QWidget paint callbacks."""
import time
from PyQt6.QtCore import QObject,QTimer,pyqtSignal,pyqtSlot


class CaptureTask(QObject):
 ready=pyqtSignal(object)
 def __init__(self,parent):
  super().__init__(parent);self.timer=QTimer(self);self.timer.setSingleShot(True);self.timer.timeout.connect(self.step);self.state=None;self.working=False
 def cancel(self):
  self.timer.stop();self.state=None
 def start(self,state):
  self.cancel();self.state=state;self.timer.start(0)
 @pyqtSlot()
 def step(self):
  state=self.state
  if state is None or self.working:return
  self.working=True;start=time.perf_counter()
  try:
   while time.perf_counter()-start<.006:
    try:value=next(state['iterator'])
    except StopIteration:
     if self.state is state:state['ready']=True;self.state=None;self.ready.emit(state)
     return
    if self.state is not state:return
    if value is not None:
     kind,payload=value
     if kind=='document':state['snapshot_doc']=payload
     else:state['items'].append(payload)
   if self.state is state:self.timer.start(0)
  except Exception as error:
   if self.state is state:state['error']=repr(error);state['ready']=True;self.state=None;self.ready.emit(state)
  finally:
   self.working=False
   from PyQt6 import sip
   if self.state is not None and not sip.isdeleted(self) and not self.timer.isActive():self.timer.start(0)
