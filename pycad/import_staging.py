"""Cancellable source-file staging, keeping large DWG copies off the GUI thread."""
import threading
from PyQt6.QtCore import QThread,pyqtSignal,QTimer,Qt
from PyQt6.QtWidgets import QProgressDialog
from . import dwg_support


class StageJob(QThread):
    progress=pyqtSignal(int)
    def __init__(self,source,directory,parent):
        super().__init__(parent);self.source=source;self.directory=directory;self.cancelled=threading.Event();self.error=None
    def run(self):
        try:dwg_support.stage_source(self.source,self.directory,cancel=self.cancelled.is_set,progress=lambda n,total:self.progress.emit(int(n*100/max(1,total))))
        except Exception as ex:self.error=ex


def stage(parent,source,directory,timeout_ms=300000):
    dialog=QProgressDialog('Preparing DWG source…','Cancel',0,100,parent);dialog.setWindowTitle('Open DWG · staging')
    dialog.setWindowModality(Qt.WindowModality.WindowModal);dialog.setMinimumDuration(0);dialog.setAutoClose(False);dialog.setAutoReset(False)
    job=StageJob(source,directory,dialog);job.progress.connect(dialog.setValue);job.finished.connect(dialog.accept)
    dialog.canceled.connect(job.cancelled.set)
    timed_out=[]
    timer=QTimer(dialog);timer.setSingleShot(True)
    def timeout():timed_out.append(True);job.cancelled.set()
    timer.timeout.connect(timeout);timer.start(max(1,timeout_ms));QTimer.singleShot(0,job.start)
    dialog.exec();job.wait();timer.stop();cancelled=job.cancelled.is_set();error=job.error;dialog.deleteLater()
    if timed_out:raise ValueError('DWG staging timed out; original drawing unchanged')
    if cancelled:return False
    if error:raise error
    return True
