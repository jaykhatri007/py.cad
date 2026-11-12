"""Strict native state for the professional workflow extensions."""
import copy,math
from .document import SetAttrCommand


def validate(table):
    if not isinstance(table,dict) or set(table)-{'associations','variants','viewport_settings','quantity_adjustments'} or any(not isinstance(v,dict) for v in table.values()):raise ValueError('Invalid professional settings')
    def number(v,positive=False):
        if type(v) not in (int,float) or not math.isfinite(v) or (positive and v<=0):raise ValueError('Invalid professional number')
    def text(v):
        if not isinstance(v,str) or not v or len(v)>255:raise ValueError('Invalid professional text')
    for key,r in table.get('associations',{}).items():
        text(key)
        if not isinstance(r,dict) or set(r)!={'kind','sources','anchors'} or r['kind'] not in ('dimension','hatch'):raise ValueError('Invalid association')
        if not isinstance(r['sources'],list) or not r['sources']:raise ValueError('Association needs sources')
        for v in r['sources']:text(v)
        if not isinstance(r['anchors'],list):raise ValueError('Invalid anchors')
        for v in r['anchors']:text(v)
        if r['kind']=='dimension' and (len(r['sources'])!=2 or len(r['anchors'])!=2):raise ValueError('Dimension needs two anchors')
        if r['kind']=='hatch' and r['anchors']:raise ValueError('Hatches use closed boundaries')
    for key,r in table.get('variants',{}).items():
        text(key)
        if not isinstance(r,dict) or set(r)!={'base','state','hidden_layers','stretch_x','stretch_y','threshold_x','threshold_y'}:raise ValueError('Invalid block variant')
        text(r['base']);text(r['state'])
        if not isinstance(r['hidden_layers'],list):raise ValueError('Invalid visibility layers')
        for v in r['hidden_layers']:text(v)
        for k in ('stretch_x','stretch_y','threshold_x','threshold_y'):number(r[k])
    for key,r in table.get('viewport_settings',{}).items():
        text(key)
        if not isinstance(r,dict) or set(r)!={'rotation','clip','annotation_scale'}:raise ValueError('Invalid viewport settings')
        number(r['rotation']);number(r['annotation_scale'],True)
        if not isinstance(r['clip'],list) or (r['clip'] and len(r['clip'])<3):raise ValueError('Clip needs three paper points')
        for p in r['clip']:
            if not isinstance(p,list) or len(p)!=2:raise ValueError('Invalid clip point')
            for n in p:number(n)
    for key,r in table.get('quantity_adjustments',{}).items():
        text(key)
        if not isinstance(r,dict) or set(r)!={'deduction','waste_percent','reason'}:raise ValueError('Invalid quantity adjustment')
        number(r['deduction']);number(r['waste_percent']);text(r['reason'])
        if r['deduction']<0 or not 0<=r['waste_percent']<=100 or not r['reason'].strip():raise ValueError('Use nonnegative deduction, 0–100 waste and a reason')
    return table


def settings(doc):return doc.extensions.get('professional',{})


def save_section(doc,key,value,label):
    after=copy.deepcopy(doc.extensions);after.setdefault('professional',{})[key]=copy.deepcopy(value);validate(after['professional'])
    doc.undo_stack.push(SetAttrCommand(doc,doc,'extensions',doc.extensions,after,label))
