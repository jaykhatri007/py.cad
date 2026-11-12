"""Opt-in OpenGL VBO geometry cache with QPainter fallback for unsupported content."""
import math,time,array,statistics
from collections import OrderedDict
from .geometry import LineEntity,PolylineEntity,CircleEntity,ArcEntity,HatchEntity


def vertices(e,tolerance=.1):
    if type(e) is LineEntity:return 1,[e.p1.as_tuple(),e.p2.as_tuple()]
    if isinstance(e,PolylineEntity):
        points=e.sample_points(tolerance)
        if not points:return None
        if e.closed and points[-1].distance_to(points[0])>1e-12:points=points+[points[0]]
        return 1,[p.as_tuple() for a,b in zip(points,points[1:]) for p in (a,b)]
    if isinstance(e,(CircleEntity,ArcEntity)):
        if e.radius<=0:return None
        start=e.start_angle if isinstance(e,ArcEntity) else 0;span=(e.end_angle-start)%360 if isinstance(e,ArcEntity) else 360;step=2*math.acos(max(-1,min(1,1-tolerance/e.radius)));count=max(4,math.ceil(math.radians(span)/max(step,1e-5)))
        if count>100000:return None
        points=[(e.center.x+e.radius*math.cos(math.radians(start+span*i/count)),e.center.y+e.radius*math.sin(math.radians(start+span*i/count))) for i in range(count+1)]
        return 1,[p for a,b in zip(points,points[1:]) for p in (a,b)]
    if isinstance(e,HatchEntity) and e.pattern=='SOLID' and not e.holes and not e.background_color:
        pts=[p.as_tuple() for p in e.boundary]
        if len(pts)>3 and pts[0]==pts[-1]:pts.pop()
        crosses=[(b[0]-a[0])*(c[1]-b[1])-(b[1]-a[1])*(c[0]-b[0]) for a,b,c in zip(pts,pts[1:]+pts[:1],pts[2:]+pts[:2])]
        if crosses and (all(v>=0 for v in crosses) or all(v<=0 for v in crosses)):
            from .takeoff_geometry import hatch_area
            try:
                if hatch_area(e)<=1e-12:return None
            except ValueError:return None
            return 4,[p for i in range(1,len(pts)-1) for p in (pts[0],pts[i],pts[i+1])]
    return None


class Buffers:
    def __init__(self,context):
        from PyQt6.QtOpenGL import QOpenGLShaderProgram,QOpenGLShader,QOpenGLFunctions_2_0
        self.context=context;self.program=QOpenGLShaderProgram();self.buffers=OrderedDict();self.bytes=0
        for kind,code in [(QOpenGLShader.ShaderTypeBit.Vertex,'attribute vec2 position; uniform vec2 shift; uniform vec2 factor; void main(){gl_Position=vec4((position+shift)*factor,0.0,1.0);}'),(QOpenGLShader.ShaderTypeBit.Fragment,'#ifdef GL_ES\nprecision mediump float;\n#endif\nuniform vec4 ink; void main(){gl_FragColor=ink;}')]:
            if not self.program.addShaderFromSourceCode(kind,code):raise RuntimeError(self.program.log())
        if not self.program.link():raise RuntimeError(self.program.log())
        self.functions=QOpenGLFunctions_2_0()
        if not self.functions.initializeOpenGLFunctions():raise RuntimeError('OpenGL 2 functions unavailable')
        context.aboutToBeDestroyed.connect(self.clear)
    def clear(self):
        for b,n,anchor,size in self.buffers.values():b.destroy()
        self.buffers.clear();self.bytes=0
    def get(self,key,points):
        from PyQt6.QtOpenGL import QOpenGLBuffer
        if key in self.buffers:value=self.buffers.pop(key);self.buffers[key]=value;return value
        anchor=points[0];raw=array.array('f',(v for p in points for v in (p[0]-anchor[0],p[1]-anchor[1]))).tobytes();b=QOpenGLBuffer(QOpenGLBuffer.Type.VertexBuffer)
        if not b.create() or not b.bind():raise RuntimeError('Vertex buffer allocation failed')
        b.setUsagePattern(QOpenGLBuffer.UsagePattern.StaticDraw);b.allocate(raw,len(raw));b.release();value=(b,len(points),anchor,len(raw));self.buffers[key]=value;self.bytes+=len(raw)
        while len(self.buffers)>1 and self.bytes>64*1024*1024:
            old=self.buffers.popitem(last=False)[1];old[0].destroy();self.bytes-=old[3]
        return value


def draw(canvas,painter,entities):
    if not getattr(canvas,'gpu_geometry_enabled',False) or getattr(canvas,'_gpu_geometry_error',None) or painter.paintEngine().type().name!='OpenGL2' or hasattr(canvas,'_plot_mm'):return set()
    from PyQt6.QtGui import QOpenGLContext,QVector2D,QVector4D,QColor
    context=QOpenGLContext.currentContext()
    if context is None:return set()
    selected=set(map(id,canvas.selected_entities));groups=[];revision=canvas.document.render_revision;tolerance=max(.000001,.2/max(canvas.zoom,1e-9));bucket=round(math.log2(max(canvas.zoom,1e-9)),4)
    cpu=getattr(canvas,'_gpu_cpu_geometry',None)
    if cpu is None or getattr(canvas,'_gpu_cpu_revision',None)!=(id(canvas.document),revision,bucket):canvas._gpu_cpu_geometry=cpu=OrderedDict();canvas._gpu_cpu_revision=(id(canvas.document),revision,bucket)
    for e in entities:
        if id(e) in selected or e.transparency or canvas.document.entity_linetype(e)!='CONTINUOUS' or canvas.document.layers.layers.get(e.layer,{}).get('lineweight',.25)>.265:break
        if e.id not in cpu:cpu[e.id]=vertices(e,tolerance)
        value=cpu[e.id]
        if not value or not value[1]:break
        mode,points=value;style=(mode,canvas.document.entity_color(e))
        if not groups or groups[-1][0]!=style:groups.append((style,[[],[]]))
        group=groups[-1][1];group[0].append(e);group[1].extend(points)
    while len(cpu)>4096:cpu.popitem(last=False)
    if not groups:return set()
    start=time.perf_counter();handled=set();painter.beginNativePainting()
    try:
        cache=getattr(canvas,'_gpu_buffers',None)
        if cache is None or cache.context is not context:cache=canvas._gpu_buffers=Buffers(context)
        program=cache.program;f=cache.functions
        if not program.bind():raise RuntimeError('Shader binding failed')
        f.glDisable(0x0B71);f.glDisable(0x0B44);f.glLineWidth(1.)
        for (mode,color),(objects,points) in groups:
            key=(id(canvas.document),revision,tuple(e.id for e in objects),mode,bucket);buffer,count,anchor,nbytes=cache.get(key,points);buffer.bind();program.enableAttributeArray('position');program.setAttributeBuffer('position',0x1406,0,2)
            origin=canvas.world_to_screen(*anchor);w,h=max(1,canvas.viewport().width()),max(1,canvas.viewport().height());program.setUniformValue('shift',QVector2D((origin.x()-w/2)/canvas.zoom,(h/2-origin.y())/canvas.zoom));program.setUniformValue('factor',QVector2D(2*canvas.zoom/w,2*canvas.zoom/h));c=QColor(color);program.setUniformValue('ink',QVector4D(c.redF(),c.greenF(),c.blueF(),1));f.glDrawArrays(mode,0,count);program.disableAttributeArray('position');buffer.release();handled.update(map(id,objects))
        program.release();canvas.gpu_geometry_stats=dict(objects=len(handled),buffers=len(cache.buffers),gpu_bytes=cache.bytes,last_submit_ms=round((time.perf_counter()-start)*1000,3))
    except Exception as ex:canvas._gpu_geometry_error=str(ex);handled=set()
    finally:painter.endNativePainting()
    return handled


def benchmark(canvas,repeats=5):
    from PyQt6.QtGui import QImage,QPainter,QColor
    from PyQt6.QtOpenGL import QOpenGLFramebufferObject,QOpenGLPaintDevice
    from .graphics_surface import PaintSurface
    surface=canvas.viewport()
    if not isinstance(surface,PaintSurface) or not surface.isValid():return dict(verified=False,reason='Select GPU display on a desktop with a working OpenGL context first')
    old=getattr(canvas,'gpu_geometry_enabled',False);surface.makeCurrent();size=surface.size();times={};images={}
    try:
        fbo=QOpenGLFramebufferObject(size)
        for mode in ('cpu','gpu'):
            samples=[]
            for n in range(repeats+1):
                canvas.gpu_geometry_enabled=mode=='gpu';canvas._gpu_geometry_error=None
                if mode=='cpu':device=QImage(size,QImage.Format.Format_ARGB32_Premultiplied);device.fill(0)
                else:
                    if not fbo.bind():raise ValueError('GPU benchmark framebuffer unavailable')
                    device=QOpenGLPaintDevice(size)
                p=QPainter(device);p.fillRect(0,0,size.width(),size.height(),QColor('#464b52'));start=time.perf_counter();canvas._draw_entities(p);p.end()
                if mode=='gpu' and getattr(canvas,'_gpu_buffers',None):canvas._gpu_buffers.functions.glFinish()
                if n:samples.append((time.perf_counter()-start)*1000)
                images[mode]=fbo.toImage() if mode=='gpu' else device
                if mode=='gpu':fbo.release()
            times[mode]=statistics.median(samples)
        if canvas._gpu_geometry_error:raise ValueError(canvas._gpu_geometry_error)
        mismatch=count=0
        for y in range(0,size.height(),4):
            for x in range(0,size.width(),4):
                a,b=images['cpu'].pixelColor(x,y),images['gpu'].pixelColor(x,y);count+=1
                if max(abs(a.red()-b.red()),abs(a.green()-b.green()),abs(a.blue()-b.blue()))>40:mismatch+=1
        return dict(verified=bool(getattr(canvas,'gpu_geometry_stats',{}).get('objects')),cpu_ms=round(times['cpu'],3),gpu_ms=round(times['gpu'],3),speedup=round(times['cpu']/max(times['gpu'],.000001),2),sampled_pixel_difference=mismatch/max(count,1),geometry=getattr(canvas,'gpu_geometry_stats',{}),note='Warmed same-viewport geometry; includes GPU completion, excludes readback. Antialiasing may differ; verify visually.')
    finally:canvas.gpu_geometry_enabled=old;surface.doneCurrent();canvas.viewport().update()
