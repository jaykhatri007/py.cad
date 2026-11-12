"""Local application presets: docking, ribbon, shortcuts and appearance only."""
import copy,json
from PyQt6.QtCore import QByteArray
from PyQt6.QtGui import QAction,QKeySequence
from .appsettings import get_settings

def actions(mw):
 result={};counts={}
 for a in mw.findChildren(QAction):
  if a.isSeparator() or not a.text():continue
  base=a.objectName() or a.text();i=counts.get(base,0);counts[base]=i+1;result[base+'::'+str(i)]=a
 return result

def capture(mw):
 from .appearance import settings
 c=mw.canvas;drafting={k:getattr(c,k) for k in ('grid_enabled','snap_enabled','ortho_enabled','grid_spacing','snap_radius_px')};drafting['snap_modes']=sorted(c.snap_modes)
 return dict(format=1,state=bytes(mw.saveState()).hex(),geometry=bytes(mw.saveGeometry()).hex(),ribbon_tab=mw.ribbon.currentIndex(),compact=mw.ribbon.compact,appearance=settings(),drafting=drafting,shortcuts={k:a.shortcut().toString() for k,a in actions(mw).items()})

def validate(record):
 if not isinstance(record,dict) or set(record)!={'format','state','geometry','ribbon_tab','compact','appearance','drafting','shortcuts'} or record['format']!=1:raise ValueError('Invalid workspace preset')
 for k in ('state','geometry'):
  if not isinstance(record[k],str) or len(record[k])>1024*1024:raise ValueError('Invalid workspace state')
  try:bytes.fromhex(record[k])
  except ValueError:raise ValueError('Invalid workspace bytes')
 if type(record['ribbon_tab']) is not int or record['ribbon_tab']<0 or type(record['compact']) is not bool:raise ValueError('Invalid ribbon settings')
 from .appearance import DEFAULTS,THEMES,ROLE_KEYS
 import re
 options=record['appearance']
 if not isinstance(options,dict) or set(options)!=set(DEFAULTS) or options['theme'] not in THEMES:raise ValueError('Invalid appearance in preset')
 for k,v in options.items():
  if k=='theme':continue
  if not isinstance(v,str) or not (k in ROLE_KEYS and v=='') and not re.fullmatch(r'#[0-9a-fA-F]{6}',v):raise ValueError('Invalid preset color')
 from .appearance import SNAPS
 from .validation import finite
 drafting=record['drafting']
 if not isinstance(drafting,dict) or set(drafting)!={'grid_enabled','snap_enabled','ortho_enabled','grid_spacing','snap_radius_px','snap_modes'}:raise ValueError('Invalid drafting settings')
 if any(type(drafting[k]) is not bool for k in ('grid_enabled','snap_enabled','ortho_enabled')):raise ValueError('Invalid drafting toggle')
 finite(drafting['grid_spacing'],'Grid spacing',True)
 if drafting['grid_spacing']>1e9 or type(drafting['snap_radius_px']) is not int or not 2<=drafting['snap_radius_px']<=40:raise ValueError('Invalid grid/snap settings')
 if not isinstance(drafting['snap_modes'],list) or any(v not in SNAPS for v in drafting['snap_modes']):raise ValueError('Invalid snap modes')
 if not isinstance(record['shortcuts'],dict) or len(record['shortcuts'])>10000 or any(not isinstance(k,str) or not isinstance(v,str) or len(k)>1024 or len(v)>200 for k,v in record['shortcuts'].items()):raise ValueError('Invalid shortcuts')
 return record

def restore(mw,record):
 from .appearance import save
 validate(record)
 # Qt can reject stale/corrupt binary docking data; roll back the window state.
 old=capture(mw)
 if not mw.restoreState(QByteArray.fromHex(record['state'].encode())):
  mw.restoreState(QByteArray.fromHex(old['state'].encode()));raise ValueError('Workspace layout could not be restored')
 if not mw.restoreGeometry(QByteArray.fromHex(record['geometry'].encode())):
  mw.restoreState(QByteArray.fromHex(old['state'].encode()));mw.restoreGeometry(QByteArray.fromHex(old['geometry'].encode()));raise ValueError('Workspace geometry could not be restored')
 mw.ribbon.set_compact(record['compact']);mw.ribbon.setCurrentIndex(min(record['ribbon_tab'],mw.ribbon.count()-1));save(mw,record['appearance'])
 c=mw.canvas
 for key,value in record['drafting'].items():setattr(c,key,set(value) if key=='snap_modes' else value)
 prefs=get_settings()
 for key in ('grid_spacing','snap_enabled','snap_modes'):prefs.setValue('drafting/'+key,record['drafting'][key])
 prefs.setValue('drafting/snap_radius',record['drafting']['snap_radius_px']);c.viewport().update()
 for key,a in actions(mw).items():
  if key in record['shortcuts']:a.setShortcut(QKeySequence(record['shortcuts'][key]))

def saved():
 raw=get_settings().value('editing/workspaces','{}')
 try:
  values=json.loads(raw)
  if not isinstance(values,dict):raise ValueError()
  return {k:validate(v) for k,v in values.items()}
 except (ValueError,TypeError):raise ValueError('Stored workspace presets are invalid')

def save(mw,name):
 if not isinstance(name,str) or not name.strip() or len(name)>100:raise ValueError('Enter a workspace name up to 100 characters')
 values=saved();values[name]=capture(mw);get_settings().setValue('editing/workspaces',json.dumps(values));return values[name]

def remove(name):
 values=saved();values.pop(name,None);get_settings().setValue('editing/workspaces',json.dumps(values))
