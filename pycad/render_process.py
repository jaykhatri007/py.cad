"""Persistent renderer process and asynchronous snapshot transfer."""
import os,sys,json,pickle,struct,tempfile,threading,uuid,logging
from pathlib import Path
from types import SimpleNamespace
from PyQt6.QtCore import QRunnable,QProcess,QProcessEnvironment,Qt,pyqtSlot
from PyQt6.QtGui import QImage
from .async_display import Controller,Signals

class WriteSnapshot(QRunnable):
    def __init__(self,request,state,path):
        super().__init__();self.request=request;self.state=state;self.path=path;self.signals=Signals()
    def run(self):
        error=None
        try:
            from .scene_transfer import write_snapshot
            with open(self.path+'.partial','wb') as out:write_snapshot(out,self.state,self.request.cancelled)
            os.replace(self.path+'.partial',self.path)
        except Exception as ex:
            error=repr(ex)
            try:Path(self.path+'.partial').unlink(missing_ok=True)
            except OSError:pass
        self.state=None # Release large private geometry in the transfer thread.
        self.signals.finished.emit(self,self.path,error)

class ProcessController(Controller):
    isolated_process=True
    def __init__(self,canvas):
        super().__init__(canvas);self.directory=tempfile.TemporaryDirectory(prefix='pycad-render-');self.process=None;self.written=None;self.writer=None;self.buffer=b'';self.error=None;self.stderr='';self._closing=False;self.model_token=None;self.overlays={};self._state=None
    def reset(self,signature):
        if self.signature==signature:return
        old_path=self.written;super().reset(signature);self.active=None;self.error=None;self.written=None;self.model_token=uuid.uuid4().hex;self.overlays.clear()
        canvas=self.canvas()
        if canvas is not None:canvas._render_process_error=''
        if self.process is not None:
            old=self.process;self.process=None;old.kill();old.finished.connect(old.deleteLater)
            if old_path:old.finished.connect(lambda *args,path=old_path:ProcessController._remove(path))
        elif old_path:self._remove(old_path)
    @staticmethod
    def _remove(path):
        try:Path(path).unlink(missing_ok=True)
        except OSError:pass
    def close(self,*args):
        if getattr(self,'_closing',False):return
        self._closing=True
        if self.active:self.active.cancelled.set()
        process=self.process;self.process=None
        if process is not None:
            from PyQt6 import sip
            if not sip.isdeleted(process):process.kill();process.waitForFinished(1500)
        super().close(*args)
        try:self.directory.cleanup()
        except OSError:pass
    def selection_ids(self,canvas):
        key=(id(canvas.selected_entities),len(canvas.selected_entities),canvas.document.render_revision)
        if canvas.__dict__.get('_isolated_selection_key')!=key:canvas._isolated_selection_key=key;canvas._isolated_selection_ids=tuple(sorted(e.id for e in canvas.selected_entities))
        return canvas._isolated_selection_ids
    def request(self,state,key,painter,canvas,overlay=False):
        self._state=state
        if self.error or self.active or self.closed:return
        z,px,py,w,h=key[3:8]
        if w<=0 or h<=0:return
        margin=min(768,max(128,((int(max(w,h)*.2)+7)//8)*8))
        request=SimpleNamespace(mode='overlay' if overlay else 'base',selection=self.selection_ids(canvas),font=painter.font().toString(),id=uuid.uuid4().hex,pose=(z,px,py,w+2*margin,h+2*margin),signature=self.signature,cancelled=threading.Event(),stats={},colors=dict(__import__('pycad.appearance',fromlist=['colors']).colors(canvas)),hints=painter.renderHints().value,lod=bool(key[-2]),boq=bool(key[-1]))
        self.active=request;self.jobs+=1
        if self.written:self._send(request)
        else:
            transfer=dict(snapshot_doc=state['snapshot_doc'],items=state['items']);state['items']=[]
            self.writer=WriteSnapshot(request,transfer,str(Path(self.directory.name)/(self.model_token+'.pickle')));self.writer.signals.finished.connect(self.written_ready,Qt.ConnectionType.QueuedConnection);self.pool.start(self.writer)
    @pyqtSlot(object,object,object)
    def written_ready(self,writer,path,error):
        if self.writer is writer:self.writer=None
        request=writer.request
        if self.closed:return
        if request is not self.active or request.signature!=self.signature or error:
            if self.active is request:self.active=None
            if error and not request.cancelled.is_set():self._fail(error)
            self._wake();return
        self.written=path;self._send(request)
    def _send(self,request):
        if self.closed or request is not self.active:return
        if self.process is None:
            process=QProcess(self);self.process=process;self.buffer=b'';env=QProcessEnvironment.systemEnvironment();env.insert('QT_QPA_PLATFORM','offscreen');process.setProcessEnvironment(env)
            program=Path(sys.executable)
            if program.name.lower()=='pythonw.exe' and program.with_name('python.exe').exists():program=program.with_name('python.exe')
            process.setProgram(str(program));process.setArguments([str(Path(__file__).with_name('render_worker.py'))])
            self._connect_process(process);process.start();return
        if self.process.state()!=QProcess.ProcessState.Running:return
        request.image=str(Path(self.directory.name)/(request.id+'.pixels'))
        command=dict(id=request.id,model=self.model_token,snapshot=self.written,image=request.image,pose=request.pose,hints=request.hints,colors=request.colors,lod=request.lod,mode=request.mode,selection=request.selection,font=request.font,boq=request.boq,regenerate=getattr(request,'regenerate',False))
        self.process.write((json.dumps(command)+'\n').encode())
    def _connect_process(self,process):
        # QObject receiver slots are disconnected by Qt before destruction.
        # Lambdas capturing self lack that receiver lifetime and can run late.
        process.started.connect(self._on_started)
        process.readyReadStandardOutput.connect(self._on_stdout)
        process.readyReadStandardError.connect(self._on_stderr)
        process.errorOccurred.connect(self._on_error)
        process.finished.connect(self._on_finished)
    @pyqtSlot()
    def _on_started(self):
        process=self.sender()
        if not self.closed and not self._closing and self.process is process and self.active is not None:self._send(self.active)
    @pyqtSlot()
    def _on_stdout(self):
        if not self.closed and not self._closing:self._read(self.sender())
    @pyqtSlot()
    def _on_stderr(self):
        if not self.closed and not self._closing:self._stderr(self.sender())
    @pyqtSlot(QProcess.ProcessError)
    def _on_error(self,error):
        if not self.closed and not self._closing:self._process_error(self.sender())
    @pyqtSlot(int,QProcess.ExitStatus)
    def _on_finished(self,code,status):
        if not self.closed and not self._closing:self._exit(self.sender(),code)
    def _stderr(self,process):
        if self.process is process:self.stderr=(self.stderr+bytes(process.readAllStandardError()).decode(errors='replace'))[-8192:]
    def _process_error(self,process):
        if self.process is process and not self.closed and not self._closing:self._fail('Render process: '+process.errorString())
    def _exit(self,process,code):
        if self.process is process and not self._closing:self.process=None;self._fail('Render process exited ('+str(code)+'). '+self.stderr[-1000:])
    def _read(self,process):
        if self.process is not process:return
        self.buffer+=bytes(process.readAllStandardOutput())
        while b'\n' in self.buffer:
            line,self.buffer=self.buffer.split(b'\n',1)
            try:
                result=json.loads(line);request=self.active
                if request is None or result.get('id')!=request.id:continue
                if result.get('error'):self._fail(result['error']);continue
                if request.signature!=self.signature:self.active=None;self._wake();continue
                path=Path(request.image)
                with path.open('rb') as incoming:
                    w,h,stride=struct.unpack('<III',incoming.read(12))
                    if (w,h)!=(request.pose[3],request.pose[4]) or stride!=w*4:raise ValueError('Invalid render dimensions')
                    pixels=incoming.read(stride*h)
                if len(pixels)!=stride*h:raise ValueError('Incomplete render image')
                image=QImage(pixels,w,h,stride,QImage.Format.Format_ARGB32_Premultiplied).copy();path.unlink(missing_ok=True);request.stats=result['stats']
                if request.mode=='overlay':
                    self.active=None;self.overlays[(request.selection,request.pose)]=image
                    while sum(im.sizeInBytes() for im in self.overlays.values())>16*1024*1024 and len(self.overlays)>1:self.overlays.pop(next(iter(self.overlays)))
                    self._wake()
                else:self.accept(request,image,None)
            except Exception as ex:self._fail(repr(ex))
    def paint_selection(self,canvas,painter,key):
        ids=self.selection_ids(canvas)
        if not ids:return
        z,px,py,w,h=key[3:8];covered=False;fallback=None
        for (saved_ids,pose),image in reversed(list(self.overlays.items())):
            if saved_ids!=ids:continue
            oz,ox,oy,iw,ih=pose;factor=z/oz;dx=w/2-iw/2*factor+(ox-px)*z;dy=h/2-ih/2*factor+(py-oy)*z
            if fallback is None:fallback=(image,factor,dx,dy)
            reuse=canvas.__dict__.get('reuse_nearby_zooms',True)
            if (.8<=factor<=1.25 if reuse else abs(factor-1)<1e-10) and dx<=1e-5 and dy<=1e-5 and dx+iw*factor>=w-1e-5 and dy+ih*factor>=h-1e-5:fallback=(image,factor,dx,dy);covered=True;break
        if fallback:
            image,factor,dx,dy=fallback;painter.save()
            try:painter.translate(dx,dy);painter.scale(factor,factor);painter.drawImage(0,0,image)
            finally:painter.restore()
        if not covered and self._state is not None:self.request(self._state,key,painter,canvas,overlay=True)
        canvas._selection_complete=covered
    def _wake(self):
        canvas=self.canvas()
        if canvas is not None:
            try:canvas.viewport().update()
            except RuntimeError:pass
    def _fail(self,error):
        self.error=str(error);self.active=None;logging.getLogger('pycad.render_process').error(self.error)
        canvas=self.canvas()
        if canvas is not None:canvas._render_process_error=self.error
        self._wake()
