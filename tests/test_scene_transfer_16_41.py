import threading,pickle
import pytest
from pycad.scene_transfer import write_snapshot,read_snapshot
from pycad.document import Document
from pycad.geometry import Point,LineEntity
from pycad.async_display import SnapshotDocument,freeze_entities


def state():
 d=Document();d.entities=[LineEntity(Point(1,2),Point(3,4))];return dict(snapshot_doc=SnapshotDocument(d),items=[(None,None,None,True,freeze_entities(d.entities))])


def test_stream_roundtrip_and_stable_batch_fingerprints(tmp_path,qapp):
 s=state();path=tmp_path/'scene';event=threading.Event()
 with path.open('wb') as f:write_snapshot(f,s,event)
 first=read_snapshot(path);s['snapshot_doc'].render_revision+=1
 with path.open('wb') as f:write_snapshot(f,s,event)
 second=read_snapshot(path)
 assert first['fingerprints']==second['fingerprints'] and first['metadata_fingerprint']==second['metadata_fingerprint']
 assert second['items'][0][4][0].p1==Point(1,2)


def test_cancelled_or_corrupt_stream_is_rejected(tmp_path,qapp):
 s=state();event=threading.Event();event.set();path=tmp_path/'scene'
 with path.open('wb') as f,pytest.raises(InterruptedError):write_snapshot(f,s,event)
 event.clear()
 with path.open('wb') as f:write_snapshot(f,s,event)
 raw=path.read_bytes();path.write_bytes(raw[:-10])
 with pytest.raises(ValueError):read_snapshot(path)


def test_legacy_private_snapshot_still_reads(tmp_path,qapp):
 s=state();path=tmp_path/'scene';path.write_bytes(pickle.dumps(dict(document=s['snapshot_doc'],items=s['items'])))
 assert read_snapshot(path)['items'][0][4][0].p2==Point(3,4)
