"""Cancellable worker for cache verification and pure native/DXF/PDF export."""
import json,sys,tempfile
from pathlib import Path
from PyQt6.QtCore import QProcess,QProcessEnvironment,QTimer,Qt
from PyQt6.QtWidgets import QProgressDialog

def run(parent,task,parameters,document=None,timeout_ms=300000):
    with tempfile.TemporaryDirectory(prefix='pycad-desk-') as directory:
        root=Path(directory);request=root/'request.json';result=root/'result.json'
        value=dict(task=task,parameters=parameters)
        if document is not None:
            from .native_io import document_to_dict
            source=root/'drawing.pycad';source.write_text(json.dumps(document_to_dict(document),ensure_ascii=False,allow_nan=False),encoding='utf-8');value['drawing']=str(source)
        request.write_text(json.dumps(value),encoding='utf-8');dialog=QProgressDialog('Checking drawing cache…' if task.startswith('cache') else 'Exporting drawing…','Cancel',0,0,parent);dialog.setWindowModality(Qt.WindowModality.WindowModal);dialog.setMinimumDuration(0);dialog.setAutoClose(False);dialog.setAutoReset(False)
        process=QProcess(dialog);process.setWorkingDirectory(str(Path(__file__).resolve().parents[1]));env=QProcessEnvironment.systemEnvironment()
        for key in list(env.keys()):
            if key.upper().startswith(('PYTHON','QT_PLUGIN','QT_QPA_PLATFORM_PLUGIN')):env.remove(key)
        env.insert('QT_QPA_PLATFORM','offscreen');env.insert('PYCAD_DATA_DIR',directory);env.insert('PYTHONNOUSERSITE','1');env.insert('PYTHONUTF8','1');process.setProcessEnvironment(env);state=dict(cancel=False,timeout=False,error='')
        def stop(reason):state[reason]=True;process.kill();dialog.reject()
        def failed(kind):
            if kind==QProcess.ProcessError.FailedToStart:state['error']=process.errorString();dialog.reject()
        process.finished.connect(dialog.accept);process.errorOccurred.connect(failed);dialog.canceled.connect(lambda:stop('cancel'));timer=QTimer(dialog);timer.setSingleShot(True);timer.timeout.connect(lambda:stop('timeout'));timer.start(timeout_ms)
        QTimer.singleShot(0,lambda:process.start(sys.executable,['-m','pycad.desk_worker',str(request),str(result)]));dialog.exec();timer.stop()
        if dialog.wasCanceled():state['cancel']=True
        if process.state()!=QProcess.ProcessState.NotRunning:process.kill();process.waitForFinished(3000)
        stderr=bytes(process.readAllStandardError()).decode('utf-8','replace')[-2000:];dialog.deleteLater()
        if state['cancel']:return None
        if state['timeout']:raise ValueError('Operation timed out; current drawing unchanged')
        if state['error']:raise ValueError(state['error'])
        if not result.is_file():raise ValueError('Worker returned no result: '+stderr)
        output=json.loads(result.read_text(encoding='utf-8'))
        if process.exitCode()!=0 or not output.get('ok'):raise ValueError(output.get('error','Worker stopped'))
        return output['value']
