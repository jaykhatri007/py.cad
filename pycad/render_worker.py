"""Isolated renderer. Loads only its parent's private, locally-created snapshot."""
import sys,os,json,pickle,struct,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));os.environ['QT_QPA_PLATFORM']='offscreen'
from PyQt6.QtGui import QGuiApplication,QPainter,QImage,QFont
from pycad.async_display import Job,SnapshotCanvas
from pycad.retained_scene import record
from pycad.scene_transfer import read_snapshot

def serve():
    app=QGuiApplication([]);model=None;items=[];document=None;compiles=0
    for line in sys.stdin:
        request=None
        try:
            request=json.loads(line)
            if request['mode'] in ('scene','scene_selection'):
                if request['model']!=model:
                    data=read_snapshot(request['snapshot'])
                    document=data['document'];document.entities=[e for item in data['items'] for e in item[4]]
                    document._boq_data={};document._boq_error=''
                    if request.get('boq'):
                        from pycad.productivity import overlay as boq_overlay
                        document._boq_data=boq_overlay(document)
                    model=request['model'];compiles+=1
                from pycad.persistent_scene import export_scene
                scene_stats=export_scene(document,data,request)
                print(json.dumps(dict(id=request['id'],stats=dict(renderer_pid=os.getpid(),model_compiles=compiles,**scene_stats),error=None)),flush=True)
                continue
            if request['model']!=model:
                data=read_snapshot(request['snapshot'])
                document=data['document'];document.entities=[e for item in data['items'] for e in item[4]];items=[]
                document._boq_data={};document._boq_error=''
                if request.get('boq'):
                    try:
                        from pycad.productivity import overlay as boq_overlay
                        document._boq_data=boq_overlay(document)
                    except ValueError as ex:document._boq_error=str(ex)
                proxy=SnapshotCanvas(document,(1,0,0,640,480),request['colors'],False)
                proxy.boq_overlay_enabled=request.get('boq',False);proxy._boq_overlay_revision=(id(document),document.render_revision);proxy._boq_overlay=document._boq_data
                for original in data['items']:
                    batch=original[4]
                    item,exact=record(proxy,batch,QPainter.RenderHint(request['hints'])) if document.current_space=='Model' else (None,False)
                    items.append((*item,None,None) if item is not None and exact else (None,None,None,True,batch))
                model=request['model'];compiles+=1
            if request['mode']=='overlay':
                ids=set(request['selection']);selected=[e for e in document.entities if e.id in ids]
                image=QImage(request['pose'][3],request['pose'][4],QImage.Format.Format_ARGB32_Premultiplied);image.fill(0);p=QPainter(image);p.setRenderHints(QPainter.RenderHint(request['hints']))
                font=QFont();font.fromString(request['font']);p.setFont(font)
                doc=copy.copy(document);doc.entities=selected;doc.underlays=[];overlay=SnapshotCanvas(doc,request['pose'],request['colors'],False);overlay.selected_entities=selected
                try:
                    if document.current_space!='Model':overlay._draw_layout_viewports(p)
                    else:
                        for start in range(0,len(selected),64):overlay._draw_entities(p,entities=selected[start:start+64])
                        unique={e.id:e for e in selected}
                        if len(unique)==1:overlay.selected_entities=[next(iter(unique.values()))];overlay._draw_grips(p)
                finally:p.end()
                stats=dict(overlay=True)
            else:
                job=Job(items,document,tuple(request['pose']),QPainter.RenderHint(request['hints']),request['colors'],('private',),lod=request['lod']);job._external_process=True;job.base_font=request['font'];job.boq=request.get('boq',False);result=[]
                job.signals.finished.connect(lambda j,im,error:result.append((im,error)));job.run();image,error=result[0]
                if error:raise RuntimeError(error)
                stats={**job.stats,'boq_error':document._boq_error}
            image=image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
            with open(request['image'],'wb') as output:
                output.write(struct.pack('<III',image.width(),image.height(),image.bytesPerLine()));output.write(image.constBits().asstring(image.sizeInBytes()))
            print(json.dumps(dict(id=request['id'],stats={**stats,'renderer_pid':os.getpid(),'model_compiles':compiles},error=None)),flush=True)
        except Exception as ex:print(json.dumps(dict(id=request.get('id') if request else None,error=repr(ex))),flush=True)
    return 0
if __name__=='__main__':raise SystemExit(serve())
