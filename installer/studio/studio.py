"""Native GTK 3 setup window for the existing Linux installation engine."""
import ctypes as C
import json
import os
from pathlib import Path
import queue
import re
import subprocess
import sys
import threading
import time
import urllib.request

HERE = Path(__file__).resolve().parent
ART = HERE / 'art'
sys.path.insert(0,str(HERE))
from transfer import Packages
from uninstall import install_root, remove, validate
STATUS_URL = re.compile(r'http://127\.0\.0\.1:[1-9][0-9]{0,4}/\?key=[0-9a-f]{32}')
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def request(url, route, post=False):
    if not STATUS_URL.fullmatch(url) or route not in ('status', 'close'):
        raise ValueError('Invalid setup progress endpoint')
    root, query = url.split('/?', 1)
    with OPENER.open(urllib.request.Request(root + '/' + route + '?' + query,
                                          method='POST' if post else 'GET'), timeout=.6) as response:
        if not post:
            return json.loads(response.read(256 * 1024))


def run_setup(engine, events, cancel, manifest=None):
    """Read the engine's real stages while keeping the GTK thread responsive."""
    endpoint = queue.Queue()
    output = []
    try:
        proc = subprocess.Popen([engine, '--no-browser', '--no-launch'],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, errors='replace')
    except OSError as exc:
        events.put(('finished', (1, str(exc))))
        return

    def drain():
        with proc.stdout:
            for line in proc.stdout:
                candidate = line.removeprefix('PY.cad Setup: ').strip()
                if STATUS_URL.fullmatch(candidate):
                    endpoint.put(candidate)
                else:
                    output.append(line.strip())
                    del output[:-20]

    reader = threading.Thread(target=drain, daemon=True)
    reader.start()
    url = None
    cancelled = False
    last_error = ''
    while proc.poll() is None:
        if url is None:
            try:
                url = endpoint.get_nowait()
            except queue.Empty:
                pass
        if url:
            try:
                if cancel.is_set() and not cancelled:
                    request(url, 'close', True)
                    cancelled = True
                status = request(url, 'status')
                last_error = status.get('error') or last_error
                events.put(('status', status))
            except (OSError, ValueError):
                pass
        time.sleep(.25)
    reader.join(timeout=1)
    message=last_error or '\n'.join(output)[-2500:]
    events.put(('finished', (proc.returncode, message)))


P, I, U, B, D = C.c_void_p, C.c_int, C.c_uint, C.c_char_p, C.c_double
CLICK = C.CFUNCTYPE(None, P, P)
DELETE = C.CFUNCTYPE(I, P, P, P)
TIMER = C.CFUNCTYPE(I, P)


def bind(lib, name, result, *args):
    fn = getattr(lib, name)
    fn.restype, fn.argtypes = result, list(args)
    return fn


class Studio:
    def __init__(self, engine, preview=False):
        gtk = C.CDLL('libgtk-3.so.0')
        glib = C.CDLL('libglib-2.0.so.0')
        gobject = C.CDLL('libgobject-2.0.so.0')
        self.fn = {}
        specs = {
            'init_check': (I,P,P), 'window_new': (P,I),
            'window_set_title': (None,P,B), 'window_set_default_size': (None,P,I,I),
            'window_set_position': (None,P,I), 'window_set_resizable': (None,P,I),
            'box_new': (P,I,I), 'box_pack_start': (None,P,P,I,I,U),
            'scrolled_window_new': (P,P,P), 'scrolled_window_set_policy': (None,P,I,I),
            'container_add': (None,P,P), 'container_set_border_width': (None,P,U),
            'label_new': (P,B), 'label_set_text': (None,P,B), 'label_set_xalign': (None,P,C.c_float),
            'label_set_line_wrap': (None,P,I), 'label_set_max_width_chars': (None,P,I),
            'image_new_from_file': (P,B), 'image_set_from_file': (None,P,B),
            'progress_bar_new': (P,), 'progress_bar_set_fraction': (None,P,D), 'progress_bar_pulse': (None,P,),
            'button_new_with_label': (P,B), 'button_set_label': (None,P,B),
            'widget_set_name': (None,P,B), 'widget_set_sensitive': (None,P,I),
            'widget_show_all': (None,P), 'widget_destroy': (None,P),
            'widget_set_halign': (None,P,I), 'widget_set_size_request': (None,P,I,I),
            'css_provider_new': (P,), 'css_provider_load_from_data': (I,P,B,C.c_ssize_t,P),
            'style_context_add_provider_for_screen': (None,P,P,U), 'main': (None,), 'main_quit': (None,),
            'settings_get_default': (P,),
        }
        for name,(ret,*args) in specs.items():
            self.fn[name] = bind(gtk,'gtk_'+name,ret,*args)
        self.call = lambda name,*args: self.fn[name](*args)
        if not self.call('init_check',None,None):
            raise RuntimeError('GTK could not connect to a desktop display')
        self.signal = bind(gobject,'g_signal_connect_data',C.c_ulong,P,B,P,P,P,I)
        self.timeout = bind(glib,'g_timeout_add',U,U,P,P)
        get_screen = bind(gtk,'gdk_screen_get_default',P)
        provider = self.call('css_provider_new')
        if not self.call('css_provider_load_from_data',provider,CSS,-1,None):
            raise RuntimeError('Unable to apply setup window styles')
        self.call('style_context_add_provider_for_screen',get_screen(),provider,600)
        self.callbacks = []
        self.engine, self.preview = engine, preview
        self.events, self.cancel = queue.Queue(), threading.Event()
        self.busy = self.done = self.closing = False
        self.phase = 0
        self.packages = Packages()
        self.pulse = self.confirm_remove = False
        self.window = self.call('window_new',0)
        self.call('widget_set_name',self.window,b'studio')
        self.call('window_set_title',self.window,b'PY.cad | Studio Setup')
        self.call('window_set_default_size',self.window,752,590)
        self.call('window_set_position',self.window,1)
        self.call('window_set_resizable',self.window,0)
        outer = self.call('box_new',1,0)
        self.call('container_add',self.window,outer)
        reduced = I(1)
        get_property = bind(gobject,'g_object_get',None,P,B)
        get_property(self.call('settings_get_default'),b'gtk-enable-animations',C.byref(reduced),P())
        animate = bool(reduced.value) and os.environ.get('PYCAD_REDUCE_MOTION') != '1'
        self.banner = self.call('image_new_from_file',os.fsencode(ART/('construction.gif' if animate else 'banner.png')))
        self.pack(outer,self.banner)
        body = self.call('box_new',1,7)
        self.call('container_set_border_width',body,24)
        self.pack(outer,body)
        self.label(body,'INSTALLATION  /  LINUX X64  /  16.44',b'eyebrow')
        self.title = self.label(body,'Install PY.cad',b'heading')
        self.detail = self.label(body,'Set up PY.cad for your account. The installer checks the system and downloads required components.',b'detail')
        self.bar = self.call('progress_bar_new')
        self.pack(body,self.bar)
        self.stage = self.label(body,'READY TO INSTALL',b'eyebrow')
        self.steps = self.label(body,'',b'activity')
        self.render_steps(-1)
        self.download = self.label(body,'DOWNLOADS  /  WAITING TO START',b'eyebrow')
        self.transfer_bar = self.call('progress_bar_new')
        self.pack(body,self.transfer_bar)
        scroll=self.call('scrolled_window_new',None,None)
        self.call('scrolled_window_set_policy',scroll,2,1)
        self.call('widget_set_size_request',scroll,-1,72)
        self.pack(body,scroll)
        self.files = self.label(None,'Package activity will appear here.',b'activity')
        self.call('container_add',scroll,self.files)
        self.activity = self.label(body,'',b'activity')
        actions = self.call('box_new',0,10)
        self.pack(body,actions)
        self.primary = self.call('button_new_with_label',b'Install PY.cad')
        self.call('widget_set_name',self.primary,b'primary')
        self.pack(actions,self.primary)
        self.close = self.call('button_new_with_label',b'Close')
        self.pack(actions,self.close)
        for name, action in (('Setup logs', self.open_logs), ('Licenses', self.open_licenses)):
            button = self.call('button_new_with_label',name.encode())
            self.pack(actions,button)
            self.connect(button,b'clicked',CLICK,lambda *_, action=action: action())
        try:
            if not preview:
                validate(install_root())
                self.remove_button=self.call('button_new_with_label',b'Uninstall')
                self.pack(actions,self.remove_button)
                self.connect(self.remove_button,b'clicked',CLICK,lambda *_:self.remove_click())
        except (OSError,ValueError): pass
        self.connect(self.primary,b'clicked',CLICK,lambda *_:self.primary_click())
        self.connect(self.close,b'clicked',CLICK,lambda *_:self.close_click())
        self.connect(self.window,b'delete-event',DELETE,self.delete)
        self.later(150,self.tick)
        if animate:
            self.later(1660,self.finish_art)
        self.call('widget_show_all',self.window)

    def pack(self, box, child):
        self.call('box_pack_start',box,child,0,0,0)

    def label(self, box, text, name):
        label = self.call('label_new',text.encode())
        self.call('widget_set_name',label,name)
        self.call('label_set_xalign',label,0)
        self.call('label_set_line_wrap',label,1)
        self.call('label_set_max_width_chars',label,85)
        if box is not None: self.pack(box,label)
        return label

    def connect(self, obj, event, kind, fn):
        cb = kind(fn)
        self.callbacks.append(cb)
        self.signal(obj,event,C.cast(cb,P),None,None,0)

    def later(self, ms, fn):
        cb = TIMER(fn)
        self.callbacks.append(cb)
        self.timeout(ms,C.cast(cb,P),None)

    def set(self, obj, text):
        self.call('label_set_text',obj,str(text).replace('\x00','').encode())

    def open_path(self, path):
        try:
            subprocess.Popen(['xdg-open',str(path)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        except OSError:
            self.set(self.activity,str(path))

    def open_logs(self):
        base = Path(os.environ.get('XDG_DATA_HOME',''))
        if not base.is_absolute():
            base = Path.home()/'.local/share'
        logs = base/'pycad/installation/logs'
        if not self.preview and logs.is_dir():
            self.open_path(logs)
        else:
            self.set(self.activity,'Setup logs will be available after installation starts.')

    def open_licenses(self):
        path = HERE/'licenses.txt'
        if not path.is_file():
            path = HERE.parent/'assets/legal.txt'
        self.open_path(path)

    def render_steps(self, step):
        names=('System check','Workspace','Python runtime','CAD packages','Startup checks','Finish')
        marks=[('✓' if i<step else '●' if i==step else '○')+' '+name for i,name in enumerate(names)]
        self.set(self.steps,'   ·   '.join(marks[:3])+'\n'+'   ·   '.join(marks[3:]))

    def remove_click(self):
        if self.busy: return
        if not self.confirm_remove:
            self.confirm_remove=True
            self.call('button_set_label',self.remove_button,b'Confirm uninstall')
            self.set(self.detail,'Close PY.cad first. Confirm to move the installation into a recovery folder.')
            return
        self.busy=True
        self.call('widget_set_sensitive',self.primary,0)
        self.call('widget_set_sensitive',self.remove_button,0)
        def worker():
            try:
                backup,notes=remove()
                self.events.put(('removed',(0,'Recovery folder: '+str(backup)+' '+'. '.join(notes))))
            except (OSError,ValueError) as exc:
                self.events.put(('removed',(1,str(exc))))
        threading.Thread(target=worker,daemon=True).start()

    def finish_art(self, _):
        self.call('image_set_from_file',self.banner,os.fsencode(ART/'banner.png'))
        return 0

    def primary_click(self):
        if self.busy:
            return
        if self.done:
            if self.preview:
                self.close_click()
                return
            # Keep the temporary engine alive until --launch has returned.
            self.busy = True
            self.call('widget_set_sensitive',self.primary,0)
            self.set(self.stage,'OPENING PY.CAD')
            def launch():
                try:
                    result = subprocess.run([self.engine,'--launch','--no-browser'],capture_output=True,text=True)
                    self.events.put(('launched',(result.returncode,result.stderr[-500:])))
                except OSError as exc:
                    self.events.put(('launched',(1,str(exc))))
            threading.Thread(target=launch,daemon=True).start()
            return
        self.busy = True
        self.cancel.clear()
        self.confirm_remove=False
        self.packages=Packages()
        self.render_steps(-1)
        self.call('progress_bar_set_fraction',self.transfer_bar,0)
        if hasattr(self,'remove_button'): self.call('button_set_label',self.remove_button,b'Uninstall')
        self.call('widget_set_sensitive',self.primary,0)
        self.call('button_set_label',self.close,b'Cancel setup')
        self.call('progress_bar_set_fraction',self.bar,0)
        self.set(self.title,'Preparing setup')
        self.set(self.detail,'PY.cad will check your system before installing.')
        self.set(self.stage,'STARTING INSTALLATION')
        self.set(self.activity,'')
        self.set(self.files,'Waiting for transfer details…')
        if self.preview:
            self.phase = 0
            self.later(650,self.demo)
        else:
            threading.Thread(target=run_setup,args=(self.engine,self.events,self.cancel,HERE/'runtime-sources.json'),daemon=True).start()

    def demo(self, _):
        titles = ('Checking system','Preparing workspace','Setting up Python','Installing dependencies','Verifying installation','Finishing setup')
        if self.phase == len(titles) or self.cancel.is_set():
            self.events.put(('finished',(1 if self.cancel.is_set() else 0,'Preview only')))
            return 0
        self.events.put(('status',{'title':titles[self.phase],'step':self.phase,'notes':['Preview only — no files are installed.'],'output':'Downloading example-cad-package (3.0 MiB)\n Downloaded example-core-package (1.0 MiB)' if self.phase==3 else ''}))
        self.phase += 1
        return 1

    def tick(self, _):
        while True:
            try:
                kind, value = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == 'status' and not self.closing:
                step = max(0,min(6,int(value.get('step',0))))
                self.call('progress_bar_set_fraction',self.bar,step/6)
                self.set(self.title,value.get('title','Installing PY.cad'))
                self.set(self.stage,f'STAGE {min(step+1,6)} OF 6')
                self.render_steps(step)
                output=str(value.get('output',''))
                items=self.packages.observe(output)
                items.update({p['name']:(p.get('size',''),p.get('done',False)) for p in value.get('packages',[])})
                d=value.get('transfer') or {}
                active,total,count=d.get('active',False),d.get('total',0),d.get('bytes',0)
                self.pulse=step in (2,3) or (step==4 and any(line.startswith(("Get:","Downloading ")) for line in output.splitlines()))
                self.set(self.download,'DOWNLOADS  /  ACTIVITY' if self.pulse else 'DOWNLOADS  /  PACKAGE DETAILS')
                if active:
                    self.pulse=not total
                    self.set(self.download,'DOWNLOADS  /  '+d.get('name','Working'))
                    if total:
                        self.call('progress_bar_set_fraction',self.transfer_bar,min(1,count/total))
                if self.pulse or active:
                    lines=[line.strip() for line in output.replace('\r','\n').splitlines() if line.strip()]
                    latest=[f'{"✓" if done else "↓"} {name}'+(f' ({size})' if size else '') for name,(size,done) in reversed(list(items.items()))]
                    tail=(f'{count/1048576:.2f} / {total/1048576:.2f} MiB' if active and total else f'{count/1048576:.2f} MiB received' if active and count else lines[-1][-115:] if lines else 'Waiting for transfer details…')
                    self.set(self.files,'\n'.join([*latest,tail]) if latest else tail)
                elif items:
                    self.call('progress_bar_set_fraction',self.transfer_bar,1)
                    self.set(self.files,'\n'.join(('✓ ' if done else '– ')+name+(f' ({size})' if size else '') for name,(size,done) in reversed(list(items.items()))))
                else:
                    self.call('progress_bar_set_fraction',self.transfer_bar,0)
                notes = value.get('notes') or []
                self.set(self.activity,str(notes[-1] if notes else '')[-240:])
            elif kind=='transfer':
                count,total=value
                self.pulse=not total
                if total: self.call('progress_bar_set_fraction',self.transfer_bar,min(1,count/total))
                self.set(self.download,'DOWNLOADING  /  UV RUNTIME BOOTSTRAP')
                self.set(self.files,f'{count/1048576:.2f} MiB'+(f' / {total/1048576:.2f} MiB' if total else ' received'))
            elif kind=='transfer_note':
                self.set(self.files,value)
            elif kind=='transfer_end':
                self.pulse=False
            elif kind=='removed':
                self.busy=False
                code,message=value
                self.set(self.title,'PY.cad uninstalled' if not code else 'Uninstall needs attention')
                self.set(self.detail,message)
                self.call('widget_set_sensitive',self.primary,1)
                self.call('widget_set_sensitive',self.remove_button,bool(code))
                self.call('button_set_label',self.primary,b'Install PY.cad')
                self.call('button_set_label',self.remove_button,b'Uninstall')
                self.done=False
                self.confirm_remove=False
                if self.closing:
                    self.close_click()
                    return 0
            elif kind in ('finished','launched'):
                self.pulse=False
                self.busy = False
                if self.closing:
                    self.close_click()
                    return 0
                code, message = value
                self.call('button_set_label',self.close,b'Close')
                self.call('widget_set_sensitive',self.primary,1)
                if kind == 'launched':
                    if code == 0:
                        self.close_click()
                        return 0
                    self.set(self.stage,'COULD NOT OPEN PY.CAD')
                    self.set(self.activity,message[-240:])
                elif code == 0:
                    self.done = True
                    self.call('progress_bar_set_fraction',self.bar,1)
                    self.set(self.title,'Your workspace is ready')
                    self.set(self.detail,'Preview complete. No installation was performed.' if self.preview else 'Installation verified. You can open PY.cad now or from your Applications menu.')
                    self.set(self.stage,'COMPLETE')
                    self.render_steps(6)
                    self.set(self.download,'DOWNLOADS  /  COMPLETE')
                    self.set(self.activity,message if message.startswith('The uninstall shortcut') else '')
                    self.call('button_set_label',self.primary,b'Finish preview' if self.preview else b'Open PY.cad')
                else:
                    self.set(self.title,'Setup needs attention')
                    self.set(self.stage,'INSTALLATION STOPPED')
                    self.set(self.activity,message[-500:] or 'Setup did not finish. Review its log before retrying.')
                    self.call('button_set_label',self.primary,b'Retry setup')
        if self.pulse: self.call('progress_bar_pulse',self.transfer_bar)
        return 1

    def delete(self,*_):
        self.close_click()
        return 1

    def close_click(self):
        if self.busy:
            self.closing = True
            self.cancel.set()
            self.set(self.title,'Stopping setup')
            self.set(self.stage,'WAITING FOR THE INSTALLER TO STOP')
            self.call('widget_set_sensitive',self.close,0)
        else:
            self.call('widget_destroy',self.window)
            self.call('main_quit')


CSS = b'''
#studio { background: #101c2b; color: #e8f3fd; }
#studio label { color: #e8f3fd; }
#studio #eyebrow { color: #79dfd0; font: 700 10pt monospace; }
#studio #heading { color: #f2f8ff; font: 700 23pt sans-serif; }
#studio #detail, #studio #activity { color: #b6cadd; font-size: 10pt; }
#studio progressbar trough { background: #243b50; border: 0; border-radius: 5px; min-height: 8px; }
#studio progressbar progress { background: #68decf; border: 0; border-radius: 5px; min-height: 8px; }
#studio button { background: #233950; color: #e7f3ff; border: 1px solid #43627c; border-radius: 6px; padding: 7px 16px; box-shadow: none; text-shadow: none; }
#studio button:hover { background: #304d65; }
#studio button#primary { background: #76e2d3; color: #0a2431; border-color: #76e2d3; font-weight: 700; }
#studio button#primary label { color: #0a2431; }
#studio button:disabled { opacity: .55; }
'''

if __name__ == '__main__':
    try:
        studio = Studio(sys.argv[1],preview='--preview' in sys.argv[2:])
    except (OSError, RuntimeError) as exc:
        print(f'PY.cad Studio Setup: {exc}',file=sys.stderr)
        sys.exit(77)
    studio.call('main')
