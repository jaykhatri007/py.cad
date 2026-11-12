"""Dispose model Undo stacks while Qt is alive, after application shutdown/save."""
import weakref
from PyQt6.QtCore import QCoreApplication,QEvent
from PyQt6 import sip
_DOCUMENTS=weakref.WeakSet()

def register(doc):
 _DOCUMENTS.add(doc)

def dispose_document(doc):
 """Only for abandoned private copies or final shutdown; preserves model data."""
 _DOCUMENTS.discard(doc);stack=getattr(doc,'undo_stack',None)
 if stack is None or sip.isdeleted(stack):return
 stack.blockSignals(True)
 try:stack.indexChanged.disconnect()
 except TypeError:pass
 stack.clear();stack.doc=None;stack.deleteLater()

def dispose_documents():
 for doc in list(_DOCUMENTS):dispose_document(doc)

def drain_deferred_deletes():QCoreApplication.sendPostedEvents(None,QEvent.Type.DeferredDelete)
