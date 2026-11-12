"""Cancellable, isolated analysis after capturing an immutable native snapshot."""
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from PyQt6.QtCore import QProcess,QProcessEnvironment,QTimer,Qt
from PyQt6.QtWidgets import QProgressDialog
from .native_io import document_to_dict


def snapshot_bytes(doc):
    return json.dumps(document_to_dict(doc),ensure_ascii=False,allow_nan=False).encode('utf-8')


def fingerprint(doc):return hashlib.sha256(snapshot_bytes(doc)).hexdigest()


def run(parent,doc,task="takeoff",timeout_ms=300000,artifact=None,parameters=None):
    if getattr(sys,'frozen',False):raise ValueError('This package needs the source/managed Python runtime for workflow analysis')
    raw=snapshot_bytes(doc);digest=hashlib.sha256(raw).hexdigest()
    with tempfile.TemporaryDirectory(prefix='pycad-analysis-') as directory:
        source=Path(directory)/'input.pycad';result=Path(directory)/'result.json';source.write_bytes(raw)
        if parameters is not None:(Path(directory)/'parameters.json').write_text(json.dumps(parameters,allow_nan=False),encoding='utf-8')
        d=QProgressDialog('Calculating quantities…' if task=='takeoff' else 'Importing PDF vectors…' if task=='pdf_vectors' else 'Building regional drawing cache…','Cancel',0,0,parent);d.setMinimumDuration(0)
        d.setWindowModality(Qt.WindowModality.WindowModal);d.setAutoClose(False);d.setAutoReset(False)
        proc=QProcess(d);proc.setWorkingDirectory(str(Path(__file__).resolve().parents[1]))
        env=QProcessEnvironment.systemEnvironment()
        for key in list(env.keys()):
            if key.upper().startswith(('PYTHON','QT_PLUGIN','QT_QPA_PLATFORM_PLUGIN')):env.remove(key)
        env.insert('QT_QPA_PLATFORM','offscreen');env.insert('PYCAD_DATA_DIR',directory);env.insert('PYTHONUTF8','1');env.insert('PYTHONNOUSERSITE','1');proc.setProcessEnvironment(env)
        state={'cancel':False,'timeout':False,'error':''}
        def stop(reason):state[reason]=True;proc.kill();d.reject()
        def failed(kind):
            if kind==QProcess.ProcessError.FailedToStart:state['error']=proc.errorString();d.reject()
        d.canceled.connect(lambda:stop('cancel'));proc.errorOccurred.connect(failed);proc.finished.connect(d.accept)
        timer=QTimer(d);timer.setSingleShot(True);timer.timeout.connect(lambda:stop('timeout'));timer.start(timeout_ms)
        QTimer.singleShot(0,lambda:proc.start(sys.executable,['-m','pycad.workflow_worker',task,str(source),str(result)]))
        d.exec();timer.stop()
        if d.wasCanceled():state["cancel"]=True
        if proc.state()!=QProcess.ProcessState.NotRunning:proc.kill();proc.waitForFinished(3000)
        stderr=bytes(proc.readAllStandardError()).decode('utf-8','replace')[-3000:];d.deleteLater()
        if state['cancel']:return None
        if state['timeout']:raise ValueError('Quantity analysis timed out; drawing unchanged')
        if state['error']:raise ValueError('Could not start quantity analysis: '+state['error'])
        if not result.exists():raise ValueError('Quantity analysis returned no report: '+stderr)
        value=json.loads(result.read_text(encoding='utf-8'))
        if proc.exitStatus()!=QProcess.ExitStatus.NormalExit or proc.exitCode()!=0 or not value.get('ok'):raise ValueError(value.get('error','Quantity worker stopped unexpectedly'))
        output=value['value'];output['fingerprint']=digest
        if artifact is not None:
            from .native_io import atomic_write
            import shutil
            atomic_write(artifact,lambda path:shutil.copyfile(Path(directory)/'regional.pycaddb',path))
        return output


def takeoff(parent,doc,timeout_ms=300000):return run(parent,doc,timeout_ms=timeout_ms)
