"""Display actual transfer data without estimating an unknown byte count."""
import hashlib
import json
from pathlib import Path
import os
import re
import tempfile
import time
from urllib.parse import urlsplit
from urllib.request import build_opener, HTTPRedirectHandler

LIMIT = 128 << 20
PACKAGE = re.compile(r'^\s*(Downloading|Downloaded)\s+([\w.+-]+)(?:\s+\(([^)]+)\))?',re.M)
CSI = re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')

class HTTPSOnly(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if urlsplit(newurl).scheme != 'https':
            raise ValueError('Runtime download redirect was not HTTPS')
        return super().redirect_request(req,fp,code,msg,headers,newurl)

def checked_transfer(url, digest, target, report, cancel, opener=None):
    if urlsplit(url).scheme != 'https' or not re.fullmatch('[0-9a-f]{64}',digest):
        raise ValueError('Invalid runtime download descriptor')
    temp = None
    try:
        with (opener or build_opener(HTTPSOnly())).open(url,timeout=20) as response:
            size = response.headers.get('Content-Length','')
            total = int(size) if size.isascii() and size.isdecimal() else 0
            if total > LIMIT: raise ValueError('Runtime download exceeds its size limit')
            count, tick, sha = 0, 0.0, hashlib.sha256()
            report(count,total)
            with tempfile.NamedTemporaryFile(dir=target.parent,delete=False) as f:
                temp = Path(f.name)
                while True:
                    if cancel.is_set(): raise InterruptedError('Download cancelled')
                    data = response.read(65536)
                    if not data: break
                    count += len(data)
                    if count > LIMIT: raise ValueError('Runtime download exceeds its size limit')
                    sha.update(data); f.write(data)
                    if time.monotonic()-tick >= .1:
                        report(count,total); tick=time.monotonic()
            if cancel.is_set(): raise InterruptedError('Download cancelled')
            if sha.hexdigest()!=digest or (total and count!=total):
                raise ValueError('Runtime download failed integrity verification')
            os.replace(temp,target)
            report(count,total or count)
    finally:
        if temp is not None: temp.unlink(missing_ok=True)

def prefetch(root, manifest, report, cancel):
    # Existing installations let the original engine run its offline repair probe.
    if (root/'current.json').exists(): return
    import fcntl
    meta=json.loads(manifest.read_text())
    asset=meta['assets']['linux-amd64']
    root.mkdir(parents=True,exist_ok=True)
    if root.resolve()!=root: raise ValueError('Setup location uses a symbolic link')
    fd=os.open(root/'setup.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'rb') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if (root/'current.json').exists(): return
        tools=root/'tools'
        tools.mkdir(exist_ok=True)
        if tools.is_symlink(): raise ValueError('Setup tools location uses a symbolic link')
        target=tools/('uv-'+meta['uv_version']+'-linux-amd64.gz')
        if target.is_file() and not target.is_symlink() and target.stat().st_size<=LIMIT:
            with target.open('rb') as f:
                sha=hashlib.sha256()
                for block in iter(lambda:f.read(65536),b''): sha.update(block)
                if sha.hexdigest()==asset['sha256']: return
        checked_transfer(asset['url'],asset['sha256'],target,report,cancel)

class Packages:
    def __init__(self):
        self.items={}
    def observe(self, output):
        for status,name,size in PACKAGE.findall(CSI.sub('',output).replace('\r','\n')):
            if self.items.get(name,('',False))[1] and status=='Downloading': continue
            self.items[name]=(size or self.items.get(name,('',False))[0],status=='Downloaded')
        return self.items
