"""Opt-in real native setup acceptance. Installs only to a new supplied directory.

This does download dependencies and execute the managed runtime. It is intended
for isolated Windows/Ubuntu CI workers, not an in-place production update.
"""
import argparse,os,json,subprocess,sys,tempfile,zipfile
from pathlib import Path


def run(installer,destination):
    installer=Path(installer).resolve();root=Path(destination).resolve()
    if root.exists():raise ValueError('Choose a new installation directory')
    if sys.platform not in ('win32','linux','darwin'):raise ValueError('Acceptance supports Windows, Linux and macOS')
    extracted=None
    if sys.platform=='darwin' and installer.suffix.lower()=='.zip':
        extracted=tempfile.TemporaryDirectory(prefix='pycad-mac-acceptance-');target=Path(extracted.name)/'PyCAD-Setup'
        with zipfile.ZipFile(installer) as z:target.write_bytes(z.read('PY.cad Setup.app/Contents/MacOS/PyCAD-Setup'))
        target.chmod(0o755);installer=target
    args=[str(installer),'--root',str(root),'--destination-confirmed','--no-browser','--no-system-packages','--no-launch','--core-only']
    if sys.platform=='linux':args=['bash',*args]
    result=subprocess.run(args,timeout=1800)
    if result.returncode:raise ValueError('Native installer failed: '+str(result.returncode))
    candidates=[*root.rglob('python.exe'),*root.rglob('bin/python3'),*root.rglob('bin/python')]
    candidates=[p for p in candidates if p.is_file()]
    if not candidates:raise ValueError('Managed runtime was not installed')
    scripts=list(root.rglob('scripts/release_acceptance.py'))
    if len(scripts)!=1:raise ValueError('Installed source acceptance entry point missing or ambiguous')
    for executable in candidates:
        probe=subprocess.run([str(executable),'-c','from PyQt6 import QtPdf; import ezdxf,numpy,pypdf'],capture_output=True)
        if probe.returncode==0:break
    else:raise ValueError('Installed runtime cannot load the required core packages')
    report=root/'native-acceptance.json';env={**os.environ,'QT_QPA_PLATFORM':'offscreen','PYCAD_DATA_DIR':str(root/'acceptance-profile')}
    subprocess.run([str(executable),str(scripts[0]),'--report',str(report)],check=True,timeout=240,env=env)
    return json.loads(report.read_text())


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--installer',required=True);p.add_argument('--destination',required=True);a=p.parse_args();print(json.dumps(run(a.installer,a.destination),indent=2))
