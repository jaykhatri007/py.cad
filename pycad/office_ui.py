"""Desktop controls for the five office drafting workflows."""
import copy
import json
from pathlib import Path
from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout,
    QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMessageBox, QProgressDialog, QVBoxLayout)
from .office_data import OfficeSheet, door_recipe, label, linetype_recipe, load_project_set, pdf_notes, save_project_set
from .office_tools import (apply_door, catalog_payload, door_params, edit_review, export_office_block,
    insert_catalog, publish_project, save_linetype)
from .workflow_ui import button, fill, form, table
from .geometry import Point
from .tools import Tool

NAMES=('OFFICEBLOCKS','PARAMETRICDOOR','PDFREVIEW','PROJECTSHEETS','LINETYPEDESIGN')

def dialog(mw,title,width=720,height=475):
    d=QDialog(mw);d.setWindowTitle(title);d.resize(width,height)
    return d,QVBoxLayout(d)

def actions(d,layout,*items):
    bar=QHBoxLayout();layout.addLayout(bar)
    for title,action in items:button(d,bar,title,action)

class PointPlacement(Tool):
    name='OFFICEPLACE'
    def __init__(self,mw,title,operation):
        super().__init__(mw);self.prompt=title+': pick a point or enter x,y';self.operation=operation
    def on_click(self,x,y,kind,mouse):
        if mouse!=1:return
        if self.mw.document is not self.document or self.document.current_space!='Model':
            raise ValueError('Return to the original drawing in Model space.')
        ref=self.operation(Point(x,y))
        self.mw.canvas.selected_entities=[ref]
        self.finish()
    def on_text_input(self,text):
        p=self.parse_point(text)
        if p is None:raise ValueError('Enter x,y.')
        self.on_click(p.x,p.y,'',1)

def place(mw,title,operation):
    from .editing_ui import activate
    if mw.document.current_space!='Model':raise ValueError('Switch to Model space to place an object.')
    activate(mw,PointPlacement(mw,title,operation))

def door(mw,edit=False):
    doc=mw.document
    selected=mw.canvas.selected_entities
    ref=selected[0] if edit and len(selected)==1 and door_params(doc,selected[0]) else None
    if edit and ref is None:raise ValueError('Select one parametric door.')
    from .units import UNIT_MM
    current=door_params(doc,ref) if ref else door_recipe(900/UNIT_MM.get(doc.units,1),90,'Left','In')
    values=form(mw,'Edit parametric door' if ref else 'Insert parametric door',[
        (f'Width ({doc.units})',current['width'],None),('Opening angle',current['angle'],None),
        ('Hinge side',current['hand'],['Left','Right']),('Swing',current['swing'],['In','Out'])])
    if values:
        params=door_recipe(values[f'Width ({doc.units})'],values['Opening angle'],values['Hinge side'],values['Swing'])
        if ref:apply_door(doc,params,ref=ref);mw.refresh_selection_ui()
        else:place(mw,'Door hinge',lambda point:apply_door(doc,params,point=point))

def thumbnail(doc,name):
    from .coordination import thumbnail_document
    from .document_lifecycle import dispose_document
    from .canvas import CadCanvas
    from .appearance import colors
    preview=thumbnail_document(doc,name);canvas=CadCanvas(preview)
    pix=QPixmap(104,72);palette=colors(canvas);pix.fill(QColor(palette['ui_base']))
    p=QPainter(pix)
    try:
        p.setRenderHint(QPainter.RenderHint.Antialiasing);p.setPen(QPen(QColor(palette['ui_text']),1.2))
        boxes=[e.bbox() for e in preview.entities]
        if boxes:
            x0=min(b[0] for b in boxes);x1=max(b[2] for b in boxes);y0=min(b[1] for b in boxes);y1=max(b[3] for b in boxes)
            scale=min(88/max(x1-x0,1e-6),56/max(y1-y0,1e-6));canvas.zoom=scale
            canvas.world_to_screen=lambda x,y:QPointF(52+(x-(x0+x1)/2)*scale,36-(y-(y0+y1)/2)*scale)
            for e in preview.entities:canvas._draw_entity(p,e)
    finally:p.end();canvas.deleteLater();dispose_document(preview)
    return QIcon(pix)

def office_blocks(mw):
    from .appsettings import get_settings
    from .native_io import load_project
    from .document_lifecycle import dispose_document
    from PyQt6.QtCore import QSize,QTimer
    settings=get_settings();doc=mw.document
    d,root=dialog(mw,'Shared office blocks')
    folder=QLineEdit(str(settings.value('office/folder','')));folder.setReadOnly(True);root.addWidget(folder)
    search=QLineEdit();search.setPlaceholderText('Search shared block names…');root.addWidget(search)
    favorite=QCheckBox('Favorites only');root.addWidget(favorite)
    listing=QListWidget();listing.setIconSize(QSize(104,72));root.addWidget(listing)
    note=QLabel('Choose a local or shared folder. Add definitions from this drawing, then insert them into any drawing. Favorites are local.');note.setWordWrap(True);root.addWidget(note)
    favorites=set(json.loads(settings.value('office/favorites','[]')))
    icons={};pending=[];timer=QTimer(d);timer.setInterval(40)
    def next_icon():
        if not pending:timer.stop();return
        path,item=pending.pop(0)
        try:
            source=load_project(path)
            try:
                catalog_payload(source)
                icon=thumbnail(source,source.entities[0].block_name)
            finally:dispose_document(source)
            icons[path]=icon;item.setIcon(icon)
        except (ValueError,OSError):item.setToolTip('Unable to preview this block.')
    timer.timeout.connect(next_icon)
    def refresh():
        timer.stop();pending.clear();listing.clear()
        if not folder.text():return
        directory=Path(folder.text())
        for path in sorted(directory.glob('*.officeblock'),key=lambda p:p.name.casefold()):
            key=str(path)
            if search.text().casefold() not in path.stem.casefold() or favorite.isChecked() and key not in favorites:continue
            item=QListWidgetItem(('★ ' if key in favorites else '')+path.stem);item.setData(Qt.ItemDataRole.UserRole,key);listing.addItem(item)
            if key in icons:item.setIcon(icons[key])
            else:pending.append((key,item))
        if listing.count():listing.setCurrentRow(0)
        timer.start()
    def choose():
        value=QFileDialog.getExistingDirectory(d,'Choose a shared block folder',folder.text())
        if value:settings.setValue('office/folder',value);folder.setText(value);refresh()
    def selected():
        item=listing.currentItem()
        if not item:raise ValueError('Choose a library block.')
        return item.data(Qt.ItemDataRole.UserRole)
    def star():
        key=selected();favorites.symmetric_difference_update({key})
        settings.setValue('office/favorites',json.dumps(sorted(favorites)));refresh()
    def add():
        if not folder.text():raise ValueError('Choose a library folder first.')
        if not doc.blocks:raise ValueError('This drawing has no block definitions.')
        name,ok=QInputDialog.getItem(d,'Save block','Drawing definition',sorted(doc.blocks),0,False)
        if not ok:return
        path,_=QFileDialog.getSaveFileName(d,'Save shared block',str(Path(folder.text())/(name.replace('/','_').replace(chr(92),'_')+'.officeblock')),'Office blocks (*.officeblock)')
        if path:
            if not path.lower().endswith('.officeblock'):path+='.officeblock'
            if Path(path).resolve().parent!=Path(folder.text()).resolve():raise ValueError('Save into the selected library folder.')
            export_office_block(doc,name,path);icons.pop(path,None);refresh()
    def insert():
        source=load_project(selected())
        try:
            raw=catalog_payload(source);name=source.entities[0].block_name
        finally:dispose_document(source)
        use_existing=False
        if any(name.casefold()==k.casefold() for k in doc.blocks):
            choice,ok=QInputDialog.getItem(d,'Block name collision',name,['Import under a new name','Use drawing definition'],0,False)
            if not ok:return
            use_existing=choice=='Use drawing definition'
        place(mw,'Office block insertion',lambda point:insert_catalog(doc,raw,point,use_existing));d.accept()
    search.textChanged.connect(refresh);favorite.toggled.connect(refresh)
    actions(d,root,('Choose folder…',choose),('Save drawing block…',add),('Toggle favorite',star),('Insert…',insert),('Close',d.accept))
    refresh();d.exec();timer.stop()

def review_pdf(mw):
    from .underlays import read_underlay
    doc=mw.document
    d,root=dialog(mw,'PDF review')
    pages=QComboBox();root.addWidget(pages)
    grid=table(root,['#','Author','Comment','Status'],'pdf_review_notes')
    note=QLabel('Amber pins are open; green pins are resolved. Flattened markups are visible in the PDF image.');note.setWordWrap(True);root.addWidget(note)
    def refresh(select=None):
        select=select or pages.currentData();pages.blockSignals(True);pages.clear()
        reviews=doc.extensions.get('office_reviews',{})
        for r in doc.underlays:
            if r['id'] in reviews:pages.addItem(f"{r['name']} · page {r['page']} · {reviews[r['id']]['space']}",r['id'])
        index=pages.findData(select)
        if index>=0:pages.setCurrentIndex(index)
        pages.blockSignals(False);show()
    def chosen():
        uid=pages.currentData()
        if uid is None:raise ValueError('Import a review page first.')
        return next(r for r in doc.underlays if r['id']==uid),doc.extensions['office_reviews'][uid]
    def show():
        if pages.currentData() is None:fill(grid,[]);return
        _,review=chosen()
        fill(grid,[(i,n['author'],n['text'],'Resolved' if n['resolved'] else 'Open') for i,n in enumerate(review['notes'],1)])
        grid.resizeRowsToContents()
    def alignment(record,review):
        r=form(d,'Align review overlay',[
            ('Space',review['space'],['Model',*doc.layouts]),('Origin X',str(record['origin'][0]),None),
            ('Origin Y',str(record['origin'][1]),None),('Page width',str(record['width']),None),
            ('Rotation (degrees)',str(record['rotation']),None),('Opacity (0 to 1)',str(record['opacity']),None),
            ('Visible',record['visible'],None)])
        if not r:return
        changed={**record,'origin':[float(r['Origin X']),float(r['Origin Y'])],'width':float(r['Page width']),
                 'rotation':float(r['Rotation (degrees)']),'opacity':float(r['Opacity (0 to 1)']),'visible':r['Visible']}
        edit_review(doc,changed,{**review,'space':r['Space']});refresh(record['id'])
    def attach():
        path,_=QFileDialog.getOpenFileName(d,'Choose annotated PDF','','PDF (*.pdf)')
        if not path:return
        page,ok=QInputDialog.getInt(d,'Review page','Page number',1,1,10000)
        if not ok:return
        notes=pdf_notes(path,page-1);space=doc.current_space
        record=read_underlay(path,doc.units if space=='Model' else 'mm',page)
        record.update(plot=False,opacity=.42)
        alignment(record,dict(notes=notes,space=space))
    def toggle():
        record,review=chosen();i=grid.currentRow()
        if not 0<=i<len(review['notes']):raise ValueError('Select a comment.')
        review=copy.deepcopy(review);review['notes'][i]['resolved']=not review['notes'][i]['resolved']
        edit_review(doc,record,review);refresh();grid.selectRow(i)
    def inspect():
        _,review=chosen();i=grid.currentRow()
        if not 0<=i<len(review['notes']):raise ValueError('Select a comment.')
        msg=QMessageBox(d);msg.setWindowTitle('Review comment');msg.setTextFormat(Qt.TextFormat.PlainText)
        msg.setText(review['notes'][i]['text']);msg.exec()
    pages.currentIndexChanged.connect(show)
    actions(d,root,('Import PDF page…',attach),('Align / show…',lambda:alignment(*chosen())),('Open comment…',inspect),('Toggle resolved',toggle),('Close',d.accept))
    refresh();d.exec()

def project_sheets(mw):
    from .native_io import load_project
    from .document_lifecycle import dispose_document
    d,root=dialog(mw,'Project sheet set',890,480)
    top=QFormLayout();root.addLayout(top);rev=QLineEdit('00');top.addRow('Issue revision',rev)
    grid=table(root,['Sheet number','Layout','Saved drawing'],'project_sheet_list')
    rows=[]
    def refresh(select=-1):
        fill(grid,[(r.number,r.layout,r.drawing) for r in rows])
        if 0<=select<len(rows):grid.selectRow(select)
    def add():
        path,_=QFileDialog.getOpenFileName(d,'Choose a saved PY.cad drawing','','PY.cad drawings (*.pycad *.json);;All files (*)')
        if not path:return
        source=load_project(path)
        try:layouts=list(source.layouts);metadata=copy.deepcopy(source.extensions.get('sheets',{}))
        finally:dispose_document(source)
        if not layouts:raise ValueError('This drawing has no paper layouts.')
        layout,ok=QInputDialog.getItem(d,'Select layout','Paper layout',layouts,0,False)
        if not ok:return
        number,ok=QInputDialog.getText(d,'Sheet number','Number',text=metadata.get(layout,{}).get('number',f'A-{len(rows)+1:02}'))
        if ok:rows.append(OfficeSheet(str(Path(path).resolve()),layout,label(number,60)));refresh(len(rows)-1)
    def index():
        i=grid.currentRow()
        if not 0<=i<len(rows):raise ValueError('Select a sheet.')
        return i
    def rename():
        i=index();r=rows[i];number,ok=QInputDialog.getText(d,'Sheet number','Number',text=r.number)
        if ok:rows[i]=OfficeSheet(r.drawing,r.layout,label(number,60));refresh(i)
    def remove():
        i=index();rows.pop(i);refresh(min(i,len(rows)-1))
    def move(delta):
        i=index();j=i+delta
        if 0<=j<len(rows):rows[i],rows[j]=rows[j],rows[i];refresh(j)
    def save():
        path,_=QFileDialog.getSaveFileName(d,'Save project sheet set','','Project sheet set (*.pycadsheets)')
        if path:save_project_set(path if path.endswith('.pycadsheets') else path+'.pycadsheets',rows,rev.text())
    def read():
        path,_=QFileDialog.getOpenFileName(d,'Open project sheet set','','Project sheet set (*.pycadsheets)')
        if path:
            loaded,revision=load_project_set(path);rows[:]=loaded;rev.setText(revision);refresh(0)
    def publish():
        path,_=QFileDialog.getSaveFileName(d,'Publish combined PDF','','PDF (*.pdf)')
        if not path:return
        progress=QProgressDialog('Publishing saved layouts…','Cancel',0,len(rows),d)
        progress.setWindowModality(Qt.WindowModality.WindowModal);progress.setMinimumDuration(0)
        def update(i,total):
            progress.setValue(i)
            if progress.wasCanceled():raise ValueError('Publishing canceled.')
        try:publish_project(tuple(rows),rev.text(),path if path.lower().endswith('.pdf') else path+'.pdf',update)
        finally:progress.close()
        QMessageBox.information(d,'Project sheet set','Combined PDF published.')
    actions(d,root,('Add layout…',add),('Sheet number…',rename),('Move up',lambda:move(-1)),('Move down',lambda:move(1)),('Remove',remove))
    actions(d,root,('Open set…',read),('Save set…',save),('Publish PDF…',publish),('Close',d.accept))
    d.exec()

def linetypes(mw):
    from .office_ink import draw_path
    doc=mw.document;d,root=dialog(mw,'Custom linetype designer',540,385)
    settings=QFormLayout();root.addLayout(settings)
    existing=QComboBox();existing.addItems(['New style',*sorted(doc.extensions.get('office_linetypes',{}))]);settings.addRow('Edit style',existing)
    inputs={}
    for key,title,initial in [('name','Style name','GAS_MAIN'),('dash','Dash length','14'),('gap','Gap','10'),('text','Repeated text','GAS'),('height','Text height','3')]:
        w=inputs[key]=QLineEdit(initial);settings.addRow(title,w)
    layer=QComboBox();layer.addItem('Save only',None)
    for name in doc.layers.names():layer.addItem(name,name)
    layer.setCurrentIndex(layer.findData(doc.layers.current_layer));settings.addRow('Assign to layer',layer)
    preview=QLabel();root.addWidget(preview)
    def recipe():return linetype_recipe(**{k:w.text() for k,w in inputs.items()})
    def redraw():
        image=QPixmap(460,82);image.fill(QColor('#263139'));p=QPainter(image)
        try:
            p.setRenderHint(QPainter.RenderHint.Antialiasing);p.setPen(QPen(QColor('#9ce5cd'),2))
            r=recipe();path=QPainterPath(QPointF(15,55));path.cubicTo(158,10,300,73,445,28);draw_path(p,path,r,105/(r['dash']+r['gap']))
        except ValueError:
            p.setPen(QColor('#ffc383'));p.drawText(QPointF(14,45),'Enter a name, label and positive dimensions.')
        finally:p.end()
        preview.setPixmap(image)
    def select():
        value=doc.extensions.get('office_linetypes',{}).get(existing.currentText())
        if value:
            for k,v in value.items():inputs[k].setText(str(v))
    def save():
        r=recipe()
        if r['name'] in doc.extensions.get('office_linetypes',{}) and r['name']!=existing.currentText():
            if QMessageBox.question(d,'Replace linetype?',f"Replace {r['name']} in this drawing?")!=QMessageBox.StandardButton.Yes:return
        save_linetype(doc,r,layer.currentData());d.accept()
    existing.currentTextChanged.connect(select)
    for w in inputs.values():w.textChanged.connect(redraw)
    actions(d,root,('Save linetype',save),('Cancel',d.reject));redraw();d.exec()

def commands(mw):
    return dict(zip(NAMES,[lambda:office_blocks(mw),lambda:door(mw),lambda:review_pdf(mw),
                           lambda:project_sheets(mw),lambda:linetypes(mw)]))
