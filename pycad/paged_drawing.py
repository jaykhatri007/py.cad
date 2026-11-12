"""Disk-backed regional inspection, distinct from the editable source drawing."""
import copy,json,sqlite3,math
from pathlib import Path
from collections import OrderedDict
from .native_io import document_to_dict,document_from_dict,entity_to_dict,entity_from_dict,atomic_write


class Cancelled(ValueError):pass


def create(doc,path,cancel=lambda:False):
    doc.sync_associative()
    def write(filename):
        db=sqlite3.connect(filename)
        try:
            db.executescript('CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT); CREATE TABLE entities(n INTEGER PRIMARY KEY,id TEXT UNIQUE,data TEXT,unbounded INTEGER); CREATE VIRTUAL TABLE bounds USING rtree(n,x0,x1,y0,y1); CREATE TABLE blocks(name TEXT PRIMARY KEY,data TEXT);')
            entities,blocks=doc.entities,doc.blocks
            try:doc.entities=[];doc.blocks={};header=document_to_dict(doc)
            finally:doc.entities=entities;doc.blocks=blocks
            header.update(extensions={},constraints=[],extrusions=[],source_archive=None,underlays=[],layouts={},current_space='Model')
            # current_space is not a native field; the reader defaults to Model.
            header.pop('current_space',None)
            db.execute('INSERT INTO metadata VALUES(?,?)',('format','PY.cad regional cache 1'));db.execute('INSERT INTO metadata VALUES(?,?)',('header',json.dumps(header)))
            for name,b in blocks.items():
                if cancel():raise Cancelled('Cache creation cancelled')
                value=dict(entities=[entity_to_dict(e) for e in b.entities],source_filepath=b.source_filepath,source_scale=b.source_scale,attributes=b.attributes);db.execute('INSERT INTO blocks VALUES(?,?)',(name,json.dumps(value)))
            for n,e in enumerate(entities):
                if cancel():raise Cancelled('Cache creation cancelled')
                x0,y0,x1,y1=e.bbox();db.execute('INSERT INTO entities VALUES(?,?,?,?)',(n,e.id,json.dumps(entity_to_dict(e),allow_nan=False),int(e.kind in ('RAY','XLINE'))));db.execute('INSERT INTO bounds VALUES(?,?,?,?,?)',(n,x0,x1,y0,y1))
            db.commit()
            if db.execute('PRAGMA integrity_check').fetchone()!=('ok',):raise ValueError('Cache integrity check failed')
        finally:db.close()
    atomic_write(path,write)


class Store:
    def __init__(self,path,cache_entities=2048):
        self.path=Path(path);self.db=sqlite3.connect(self.path.resolve().as_uri()+'?mode=ro',uri=True);self.db.execute('PRAGMA trusted_schema=OFF');self.db.execute('PRAGMA query_only=ON')
        try:
            if self.db.execute("SELECT value FROM metadata WHERE key='format'").fetchone()!=('PY.cad regional cache 1',):raise ValueError('Not a PY.cad regional cache')
            self.header=json.loads(self.db.execute("SELECT value FROM metadata WHERE key='header'").fetchone()[0]);self.count=self.db.execute('SELECT count(*) FROM entities').fetchone()[0];self.extents=self.db.execute('SELECT min(x0),min(y0),max(x1),max(y1) FROM bounds').fetchone();self.cache=OrderedDict();self.capacity=max(1,int(cache_entities));self.loaded=0
        except Exception:self.db.close();raise
    def close(self):self.cache.clear();self.db.close()
    def rows(self,box):
        if len(box)!=4 or any(not math.isfinite(v) for v in box) or box[0]>box[2] or box[1]>box[3]:raise ValueError('Use ordered finite region bounds')
        x0,y0,x1,y1=box
        return self.db.execute('SELECT e.n,e.data FROM entities e WHERE e.n IN (SELECT n FROM bounds WHERE x1>=? AND x0<=? AND y1>=? AND y0<=?) OR e.unbounded=1 ORDER BY e.n',(x0,x1,y0,y1))
    def query(self,box):
        out=[]
        for n,raw in self.rows(box):
            if n in self.cache:e=self.cache.pop(n)
            else:e=entity_from_dict(json.loads(raw));self.loaded+=1
            self.cache[n]=e
            while len(self.cache)>self.capacity:self.cache.popitem(last=False)
            out.append(e)
        return out
    def document(self,box):
        value=copy.deepcopy(self.header);value['entities']=[json.loads(raw) for n,raw in self.rows(box)];pending=[r['data']['block_name'] for r in value['entities'] if r['kind']=='INSERT'];blocks={}
        while pending:
            name=pending.pop()
            if name in blocks:continue
            found=self.db.execute('SELECT data FROM blocks WHERE name=?',(name,)).fetchone()
            if not found:raise ValueError('Cache block is missing: '+name)
            record=json.loads(found[0]);blocks[name]=record;pending.extend(r['data']['block_name'] for r in record['entities'] if r['kind']=='INSERT')
        value['blocks']=blocks;return document_from_dict(value)


def viewer(parent,path):
    from PyQt6.QtCore import QTimer,QPointF,Qt
    from PyQt6.QtWidgets import QDialog,QVBoxLayout,QPushButton,QLabel
    from .canvas import CadCanvas
    from .document import Document
    from .feature_helpers import safe_action
    store=Store(path);d=QDialog(parent);d.setWindowTitle('Regional inspection — original drawing unchanged');d.resize(1000,700);root=QVBoxLayout(d);note=QLabel('Pan/zoom, then Load visible region. Inspection omits project links and underlays; normal editing uses the original drawing.');note.setWordWrap(True);root.addWidget(note);canvas=CadCanvas(Document());root.addWidget(canvas,1);canvas.snap_enabled=False
    box=store.extents
    if box[0] is not None:
        canvas.pan_offset=QPointF((box[0]+box[2])/2,(box[1]+box[3])/2);canvas.zoom=min(900/max(box[2]-box[0],1),500/max(box[3]-box[1],1))*max(1,math.sqrt(store.count/5000))
    def load():
        a=canvas.screen_to_world(0,0);b=canvas.screen_to_world(canvas.viewport().width(),canvas.viewport().height());region=(min(a.x(),b.x()),min(a.y(),b.y()),max(a.x(),b.x()),max(a.y(),b.y()));canvas.document=store.document(region);canvas.selected_entities=[];canvas.viewport().update();note.setText(f'{len(canvas.document.entities):,} regional objects of {store.count:,}. Middle-button pan / wheel zoom; load the next region explicitly. Source unchanged.')
    button=QPushButton('Load visible region');button.clicked.connect(safe_action(d,load));root.addWidget(button);canvas.keyPressEvent=lambda event:event.ignore();original_press=canvas.mousePressEvent
    def press(event):
        if event.button()==Qt.MouseButton.MiddleButton:original_press(event)
        else:event.accept()
    canvas.mousePressEvent=press
    try:d.show();QTimer.singleShot(0,safe_action(d,load));d.exec()
    finally:store.close();d.deleteLater()
