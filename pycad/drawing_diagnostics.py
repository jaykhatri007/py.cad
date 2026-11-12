"""Session import telemetry and inexpensive, exportable drawing diagnostics."""
import collections
import json
import os
import time
from pathlib import Path

EVENTS=collections.deque(maxlen=100)


def record(stage,source='',**fields):
    event=dict(stage=stage,source=str(source),time=time.time(),**fields);EVENTS.append(event)
    return event


def resident_memory():
    try:
        if os.name=='posix' and Path('/proc/self/statm').exists():
            return int(Path('/proc/self/statm').read_text().split()[1])*os.sysconf('SC_PAGE_SIZE')
        if os.name=='nt':
            import ctypes
            from ctypes import wintypes
            class Counters(ctypes.Structure):
                _fields_=[('cb',wintypes.DWORD),('PageFaultCount',wintypes.DWORD)]+[(n,ctypes.c_size_t) for n in ('PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage','QuotaPeakNonPagedPoolUsage','QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage')]
            info=Counters();info.cb=ctypes.sizeof(info)
            kernel=ctypes.WinDLL('kernel32');kernel.GetCurrentProcess.restype=wintypes.HANDLE
            if ctypes.WinDLL('psapi').GetProcessMemoryInfo(kernel.GetCurrentProcess(),ctypes.byref(info),info.cb):return info.WorkingSetSize
    except (OSError,ValueError,AttributeError):pass
    return None


def report(doc,canvas=None):
    counts=collections.Counter(e.kind for e in doc.entities)
    return dict(format='PY.cad diagnostics 1',source=doc.source_filepath or doc.filepath,
                entities=len(doc.entities),kinds=dict(counts),blocks=len(doc.blocks),
                definition_entities=sum(len(b.entities) for b in doc.blocks.values()),
                largest_blocks=sorted(((n,len(b.entities)) for n,b in doc.blocks.items()),key=lambda x:x[1],reverse=True)[:20],
                process_resident_bytes=resident_memory(),units=doc.units,
                warnings=list(getattr(doc,'import_warnings',[])),events=list(EVENTS),
                display=dict(path=getattr(canvas,'drawing_path','cached'),last_draw_ms=getattr(canvas,'last_draw_ms',None),progressive=getattr(canvas,'progressive_stats',{}),persistent_scene=getattr(canvas,'persistent_scene_stats',{}),scene_worker=getattr(canvas,'_persistent_worker_stats',{})),
                memory_note='Process resident memory includes libraries and caches; it is not drawing-file size.')


def write_report(doc,path,canvas=None):
    from .native_io import atomic_write
    value=report(doc,canvas)
    atomic_write(path,lambda p:Path(p).write_text(json.dumps(value,indent=2,ensure_ascii=False),encoding='utf-8'))
    return value


def timed_paint(method):
    import functools
    @functools.wraps(method)
    def invoke(canvas,*args,**kwargs):
        started=time.perf_counter()
        try:return method(canvas,*args,**kwargs)
        finally:
            canvas.last_draw_ms=(time.perf_counter()-started)*1000
            samples=canvas.__dict__.setdefault('_paint_samples',collections.deque(maxlen=120))
            samples.append(dict(kind=canvas.__dict__.get('_last_draw_kind','redraw'),ms=canvas.last_draw_ms,time=time.time()))
    return invoke
