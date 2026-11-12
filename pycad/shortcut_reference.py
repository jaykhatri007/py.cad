"""Searchable action reference and persistent, conflict-checked shortcuts."""
import json
from PyQt6.QtGui import QKeySequence
from . import appsettings
from .workspace_presets import actions


def initialize(mw):
 records=actions(mw);mw._shortcut_defaults={k:a.shortcut().toString() for k,a in records.items()}
 try:
  values=json.loads(appsettings.get_settings().value('commands/shortcuts','{}'))
  if not isinstance(values,dict):return
  for key,value in values.items():
   if key in records and isinstance(value,str) and len(value)<=200:records[key].setShortcut(QKeySequence(value))
 except (ValueError,TypeError):pass


def assign(mw,key,value):
 records=actions(mw)
 if key not in records:raise ValueError('Action is no longer available')
 sequence=QKeySequence.fromString(value,QKeySequence.SequenceFormat.PortableText)
 if value and (sequence.isEmpty() or any(sequence[i].key()==0 or sequence[i].key()==0x1ffffff for i in range(sequence.count()))):raise ValueError('Invalid shortcut')
 # Global bare letters consume command entry; use an actual modified key or function key.
 from PyQt6.QtCore import Qt
 if value:
  for i in range(sequence.count()):
   combination=sequence[i]
   if combination.keyboardModifiers()==Qt.KeyboardModifier.NoModifier and combination.key()<Qt.Key.Key_Escape:raise ValueError('Use a modifier such as Ctrl/Alt, or a function key')
  for other,a in records.items():
   if other==key:continue
   other_seq=a.shortcut()
   if not other_seq.isEmpty() and (sequence.matches(other_seq)!=QKeySequence.SequenceMatch.NoMatch or other_seq.matches(sequence)!=QKeySequence.SequenceMatch.NoMatch):raise ValueError('Shortcut conflicts with '+a.text().replace('&',''))
 records[key].setShortcut(sequence)
 appsettings.get_settings().setValue('commands/shortcuts',json.dumps({k:a.shortcut().toString(QKeySequence.SequenceFormat.PortableText) for k,a in records.items()}))


def reset(mw):
 for key,a in actions(mw).items():
  if key in mw._shortcut_defaults:a.setShortcut(QKeySequence(mw._shortcut_defaults[key]))
 appsettings.get_settings().remove('commands/shortcuts')


def records(mw):
 from .main_window import COMMAND_ALIASES
 aliases={**COMMAND_ALIASES,**mw.user_aliases};result=[]
 for key,a in actions(mw).items():result.append(dict(key=key,name=a.text().replace('&',''),aliases='',shortcut=a.shortcut().toString(QKeySequence.SequenceFormat.PortableText),detail=a.toolTip() or a.statusTip()))
 for name in sorted(mw.canonical_commands):result.append(dict(key='',name=name,aliases=', '.join(k for k,v in sorted(aliases.items()) if v==name),shortcut='',detail='Type command or alias, then Enter'))
 return result
