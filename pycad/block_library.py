"""Searchable drawing block browser with bounded thumbnails and insertion ghosts."""
import copy,hashlib,json
from PyQt6.QtCore import Qt,QTimer,QSize
from PyQt6.QtGui import QIcon,QPixmap,QPen,QColor
from PyQt6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLineEdit,QComboBox,QCheckBox,QListWidget,QListWidgetItem,QListView,QLabel,QInputDialog
from .workflow_ui import button,form
from . import coordination as c
from .geometry import Point,BlockReferenceEntity
from .tools import Tool

class LibraryInsert(Tool):
 name='LIBRARYINSERT'
 def __init__(self,mw,name,scale=1.,rotation=0.):
  super().__init__(mw)
  if name in c.managed_blocks(self.document):raise ValueError('Use the architecture/table tool for managed definitions')
  self.name_to_insert=name;self.scale=scale;self.rotation=rotation;preview=c.block_preview(self.document,name,scale,rotation);self.ref=preview.entities[0];self.cursor=None
  from .efficiency import fingerprint
  self.stamp=fingerprint(self.document)
  from .document_lifecycle import dispose_document
  dispose_document(preview)
 def status_prompt(self):return 'INSERT '+self.name_to_insert+': pick insertion point; Esc cancels'
 def on_move(self,x,y,kind):self.cursor=Point(x,y)
 def on_text_input(self,text):
  point=self.parse_point(text)
  if point:self.on_click(point.x,point.y,'',Qt.MouseButton.LeftButton.value)
 def on_click(self,x,y,kind,button):
  if button!=Qt.MouseButton.LeftButton.value:return
  from .native_io import document_to_dict,entity_to_dict,document_from_dict
  from .document import AddEntityCommand
  from .efficiency import fingerprint
  if self.mw.document is not self.document or self.name_to_insert not in self.document.blocks or fingerprint(self.document)!=self.stamp:raise ValueError('Drawing or block changed; restart insertion')
  ref=BlockReferenceEntity(self.name_to_insert,Point(x,y),scale=self.scale,rotation=self.rotation,layer=self.document.layers.current_layer);value=document_to_dict(self.document);value['entities'].append(entity_to_dict(ref));document_from_dict(value);self.document.undo_stack.push(AddEntityCommand(self.document,ref,'Insert library block'));self.finish()
 def draw_preview(self,painter,canvas):
  if self.cursor is None:return
  painter.save();painter.setPen(QPen(QColor('#65d9b2'),1.4,Qt.PenStyle.DashLine))
  try:
   clone=copy.deepcopy(self.ref);clone.translate(self.cursor.x,self.cursor.y);canvas._draw_entity(painter,clone)
  finally:painter.restore()

class BlockLibrary(QDialog):
 def __init__(self,mw):
  super().__init__(mw);self.mw=mw;self.setObjectName('block_library');self.setWindowTitle('PY.cad — block library');self.resize(980,650);root=QVBoxLayout(self);self.search=QLineEdit();self.search.setPlaceholderText('Search block names and categories…');root.addWidget(self.search);bar=QHBoxLayout();root.addLayout(bar);self.category=QComboBox();bar.addWidget(self.category);self.favorite=QCheckBox('Favorites only');bar.addWidget(self.favorite);self.list=QListWidget();self.list.setViewMode(QListView.ViewMode.IconMode);self.list.setResizeMode(QListView.ResizeMode.Adjust);self.list.setIconSize(QSize(120,80));self.list.setGridSize(QSize(155,115));root.addWidget(self.list,1);self.note=QLabel('Current-drawing definitions. Thumbnails are bounded geometry samples; preview shows the selected definition.');self.note.setWordWrap(True);root.addWidget(self.note);self.pending=[];self.icons={};self.timer=QTimer(self);self.timer.setInterval(20);self.timer.timeout.connect(self.next_icon)
  meta=c.block_metadata();self.category.addItems(['All categories']+sorted({r['category'] for r in meta.values() if r['category']}));self.search.textChanged.connect(self.refresh);self.category.currentTextChanged.connect(self.refresh);self.favorite.toggled.connect(self.refresh);self.list.itemDoubleClicked.connect(lambda *_:self.insert());actions=QHBoxLayout();root.addLayout(actions)
  for label,fn in [('Preview…',self.preview),('Place with preview…',self.insert),('Favorite / unfavorite',self.toggle_favorite),('Set category…',self.set_category),('Close',self.accept)]:button(self,actions,label,fn)
  self.refresh()
 def refresh(self,*_):
  from .workspace_ui import tool_icon
  self.timer.stop();self.pending=[];self.list.clear();meta=c.block_metadata();managed=c.managed_blocks(self.mw.document);text=self.search.text().casefold();category=self.category.currentText()
  for name,b in self.mw.document.blocks.items():
   r=meta.get(name,dict(category='',favorite=False))
   if text and text not in (name+' '+r['category']).casefold() or self.favorite.isChecked() and not r['favorite'] or category!='All categories' and category!=r['category']:continue
   item=QListWidgetItem(self.icons.get(name,tool_icon('INSERT')),('★ ' if r['favorite'] else '')+name);item.setData(Qt.ItemDataRole.UserRole,name);item.setToolTip(name+'\nCategory: '+(r['category'] or 'None')+('\nManaged definition: use its source tool' if name in managed else ''));self.list.addItem(item)
   if name not in self.icons:self.pending.append(item)
  if self.list.count():self.list.setCurrentRow(0)
  self.timer.start()
 def next_icon(self):
  if not self.pending:self.timer.stop();return
  item=self.pending.pop(0);name=item.data(Qt.ItemDataRole.UserRole)
  try:
   from .canvas import CadCanvas
   from PyQt6.QtGui import QPainter,QPen,QColor
   from PyQt6.QtCore import QPointF
   from .appearance import colors
   doc=c.thumbnail_document(self.mw.document,name);canvas=CadCanvas(doc);pix=QPixmap(120,80);ui=colors(self);pix.fill(QColor(ui['ui_base']));painter=QPainter(pix)
   try:
    boxes=[q.bbox() for q in doc.entities]
    if boxes:
     x0=min(b[0] for b in boxes);y0=min(b[1] for b in boxes);x1=max(b[2] for b in boxes);y1=max(b[3] for b in boxes);scale=min(100/max(x1-x0,1),60/max(y1-y0,1));canvas.zoom=scale;canvas.world_to_screen=lambda x,y:QPointF(60+(x-(x0+x1)/2)*scale,40-(y-(y0+y1)/2)*scale);painter.setPen(QPen(QColor(ui['ui_text']),1.2))
     for entity in doc.entities:canvas._draw_entity(painter,entity)
   finally:
    from .document_lifecycle import dispose_document
    painter.end();canvas.deleteLater();dispose_document(doc)
   icon=QIcon(pix);self.icons[name]=icon;item.setIcon(icon)
  except (ValueError,KeyError):pass
 def done(self,result):
  self.timer.stop();self.pending.clear();super().done(result)
 def closeEvent(self,event):
  self.timer.stop();self.pending.clear();super().closeEvent(event)
 def selected(self):
  item=self.list.currentItem()
  if item is None:raise ValueError('Choose a block')
  return item.data(Qt.ItemDataRole.UserRole)
 def preview(self):
  from .canvas import CadCanvas
  doc=c.block_preview(self.mw.document,self.selected());dialog=QDialog(self);dialog.setWindowTitle('Block preview — '+self.selected());dialog.resize(760,500);root=QVBoxLayout(dialog);canvas=CadCanvas(doc);root.addWidget(canvas);button(dialog,root,'Close',dialog.accept);QTimer.singleShot(0,canvas.zoom_extents);dialog.exec()
  from .document_lifecycle import dispose_document
  dialog.deleteLater();dispose_document(doc)
 def insert(self):
  name=self.selected();r=form(self,'Block insertion',[('Scale',1.,None),('Rotation degrees','0',None)])
  if r:
   from .editing_ui import activate
   tool=LibraryInsert(self.mw,name,r['Scale'],float(r['Rotation degrees']));self.accept();activate(self.mw,tool)
 def toggle_favorite(self):
  name=self.selected();record=c.block_metadata().get(name,{});c.set_block_metadata(name,favorite=not record.get('favorite',False));self.refresh()
 def set_category(self):
  name=self.selected();value,ok=QInputDialog.getText(self,'Block category','Category',text=c.block_metadata().get(name,{}).get('category',''))
  if ok:
   c.set_block_metadata(name,category=value)
   if self.category.findText(value)<0:self.category.addItem(value)
   self.refresh()

def show(mw):return BlockLibrary(mw).exec()
