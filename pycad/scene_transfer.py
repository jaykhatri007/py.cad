"""Versioned private, cancellable scene transfer in bounded pickle frames.

Only parent-created temporary snapshots are read. Never use this for user files.
"""
import hashlib,io,pickle,struct
MAGIC=b'PYCADSCENE\x01'


def large_item(item):
 pending=list(item[4] or ());count=0
 while pending and count<=4096:
  e=pending.pop();count+=1+len(getattr(e,'points',()))+len(getattr(e,'boundary',()))+sum(len(h) for h in getattr(e,'holes',()))
  pending.extend(getattr(e,'resolved_entities',()))
 return count>4096


def encode(value,event,cooperative=False):
 if event.is_set():raise InterruptedError('Snapshot superseded')
 if not cooperative:return pickle.dumps(value,protocol=4)
 class CancellablePickler(pickle._Pickler):
  def save(self,obj,save_persistent_id=True):
   if event.is_set():raise InterruptedError('Snapshot superseded')
   return super().save(obj,save_persistent_id)
 output=io.BytesIO();CancellablePickler(output,protocol=4).dump(value);return output.getvalue()


def write_snapshot(output,state,event):
 doc=state['snapshot_doc'];items=state['items']
 metadata={k:v for k,v in doc.__dict__.items() if k not in ('entities','render_revision')}
 fingerprint=hashlib.sha256(encode(metadata,event)).hexdigest()
 output.write(MAGIC);output.write(encode(dict(document=doc,metadata_fingerprint=fingerprint,count=len(items)),event))
 for item in items:
  raw=encode(item,event,large_item(item));output.write(struct.pack('<Q',len(raw)));output.write(hashlib.sha256(raw).digest());output.write(raw)
 if event.is_set():raise InterruptedError('Snapshot superseded')


def read_snapshot(path):
 with open(path,'rb') as incoming:
  if incoming.read(len(MAGIC))!=MAGIC:
   incoming.seek(0);return pickle.load(incoming)
  header=pickle.load(incoming);items=[];fingerprints=[]
  for unused in range(header['count']):
   size=incoming.read(8)
   if len(size)!=8:raise ValueError('Incomplete snapshot frame header')
   length=struct.unpack('<Q',size)[0];digest=incoming.read(32);raw=incoming.read(length)
   if len(digest)!=32 or len(raw)!=length or hashlib.sha256(raw).digest()!=digest:raise ValueError('Incomplete or corrupt snapshot frame')
   items.append(pickle.loads(raw));fingerprints.append(digest.hex())
  return dict(document=header['document'],items=items,fingerprints=fingerprints,metadata_fingerprint=header['metadata_fingerprint'])
