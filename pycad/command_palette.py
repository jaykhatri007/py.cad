"""Search real command routes and enabled QActions by labels, aliases and help."""
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QDialog,QVBoxLayout,QLineEdit,QListWidget,QListWidgetItem,QLabel

def entries(mw):
    from .ribbon_catalog import PANELS
    from .main_window import COMMAND_ALIASES
    aliases={**COMMAND_ALIASES,**getattr(mw,'user_aliases',{})};records=[];seen=set()
    for tab,panel,size,tools in PANELS:
        for tool in tools:
            if tool.status=='planned' or tool.command in seen or tool.command not in mw.command_names:continue
            seen.add(tool.command);short=' '.join(k for k,v in aliases.items() if v==tool.command);records.append(dict(label=f'{tool.label} · {tool.command}',search=f'{tool.label} {tool.command} {short} {tool.detail} {tab} {panel}',detail=tool.detail or f'{tab} / {panel}',enabled=True,callback=lambda c=tool.command:mw.run_ribbon_command(c)))
    for action in mw.findChildren(QAction):
        label=action.text().replace('&','').strip()
        if not label or action.isSeparator() or 'command palette' in label.lower():continue
        shortcut=action.shortcut().toString();tip=action.toolTip() or action.statusTip();records.append(dict(label=label+(f' · {shortcut}' if shortcut else ''),search=f'{label} {shortcut} {tip}',detail=tip,enabled=action.isEnabled(),callback=action.trigger))
    # Advanced command routes without a ribbon catalog entry remain discoverable.
    for command in ('OFFICEBLOCKS','PARAMETRICDOOR','PDFREVIEW','PROJECTSHEETS','LINETYPEDESIGN','BIND','BINDMISSING','CURSORDIMS','DRAFTINGTOOLS','POLYEDITOR','TRIMEXTEND','HATCHBOUNDARIES','DRAWSEARCH','DRAWINGTEMPLATES','SHORTCUTREFERENCE','COORDINATION','SHAREDPROPERTIES','BLOCKLIBRARY','REFCOORD','PROJECTSTANDARDS','TUTORIALS','RELEASECHECKS','EDITING','SELECTFILTER','ADVGRIPS','BOUNDARYREPAIR','DRAFTINGAIDS','WORKSPACEPRESETS','DRAWINGHEALTH','TRACKPOINT','CLEARTRACKING','PRODUCTION','SHEETSETS','DRAWCOMPARE','PUBLISHPREVIEW','ANNOTATIONTOOLS','ARCHDRAFT','BOQTRACE','AIPREVIEW','EFFICIENCY','IMPORTCACHE','RECOVERYCENTER','SELECTCYCLE','CLEANUPPREVIEW','BATCHDRAWINGS','REFDIAGNOSTICS','PERFDASHBOARD','DRAWINGTOOLS'):
        if command in mw.command_names:records.append(dict(label=command,search=command+' '+' '.join(k for k,v in aliases.items() if v==command),detail='Drawing workflow',enabled=True,callback=lambda c=command:mw.run_ribbon_command(c)))
    return records

def filter_entries(records,text):
    words=text.casefold().split();return [r for r in records if all(word in r['search'].casefold() for word in words)]

def show(mw):
    records=entries(mw);dialog=QDialog(mw);dialog.setWindowTitle('Command palette');dialog.resize(680,480);layout=QVBoxLayout(dialog);search=QLineEdit();search.setPlaceholderText('Search tools, command names, aliases or shortcuts…');layout.addWidget(search);items=QListWidget();layout.addWidget(items);description=QLabel();description.setWordWrap(True);layout.addWidget(description);visible=[]
    def refresh(text):
        visible[:]=filter_entries(records,text);items.clear()
        for r in visible:
            item=QListWidgetItem(r['label']);item.setToolTip(r['detail'])
            if not r['enabled']:item.setFlags(item.flags()&~Qt.ItemFlag.ItemIsEnabled)
            items.addItem(item)
        if items.count():items.setCurrentRow(0)
    def activate():
        row=items.currentRow()
        if 0<=row<len(visible) and visible[row]['enabled']:dialog.accept();visible[row]['callback']()
    search.textChanged.connect(refresh);search.returnPressed.connect(activate);items.itemActivated.connect(lambda *_:activate());items.currentRowChanged.connect(lambda i:description.setText(visible[i]['detail'] if 0<=i<len(visible) else ''));refresh('');search.setFocus();return dialog.exec()
