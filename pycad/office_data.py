"""Portable office catalog and multi-drawing sheet-set data."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from pathlib import Path
import json
import math
import os
import re
import tempfile

def atomic_bytes(path, data):
    path = Path(path)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.pycad-', delete=False) as f:
        temp = Path(f.name)
        try:
            f.write(data)
            f.close()
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)

def read_object(path, limit=2_000_000):
    with Path(path).open('rb') as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError('File exceeds its size limit.')
    result = json.loads(raw)
    if not isinstance(result, dict):
        raise ValueError('Expected a PY.cad data object.')
    return result

def write_object(path, value):
    atomic_bytes(path, (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n').encode())

def label(value, length=100):
    if not isinstance(value, str) or not value.strip() or len(value)>length or any(ord(c)<32 for c in value):
        raise ValueError('Enter a non-empty name without control characters.')
    return value.strip()

@dataclass(frozen=True)
class OfficeSheet:
    drawing: str
    layout: str
    number: str

def sheet_rows(rows):
    result=[]
    numbers=set()
    for row in rows:
        item=OfficeSheet(label(row.drawing,4096),label(row.layout),label(row.number,60))
        key=item.number.casefold()
        if key in numbers:
            raise ValueError('Duplicate sheet number: '+item.number)
        numbers.add(key)
        result.append(item)
    if not 1<=len(result)<=250:
        raise ValueError('A project set must contain 1–250 sheets.')
    return result

def save_project_set(path,rows,revision):
    path=Path(path).resolve()
    relative=[]
    for row in sheet_rows(rows):
        source=Path(row.drawing).resolve()
        try: name=os.path.relpath(source,path.parent)
        except ValueError: name=str(source)
        relative.append(asdict(OfficeSheet(name,row.layout,row.number)))
    write_object(path,dict(format='PY.cad project sheets 1',revision=label(revision,40),sheets=relative))

def load_project_set(path):
    path=Path(path).resolve()
    value=read_object(path)
    if value.get('format')!='PY.cad project sheets 1' or not isinstance(value.get('sheets'),list):
        raise ValueError('Not a PY.cad project sheet set.')
    rows=[]
    for r in value['sheets']:
        if not isinstance(r,dict) or set(r)!={'drawing','layout','number'}:
            raise ValueError('Invalid sheet record.')
        drawing=label(r['drawing'],4096)
        rows.append(OfficeSheet(str((path.parent/drawing).resolve()),r['layout'],r['number']))
    return sheet_rows(rows),label(value.get('revision'),40)

def pdf_notes(path,page_index):
    from pypdf import PdfReader
    if Path(path).stat().st_size > 50 * 1024 * 1024:
        raise ValueError("PDF reviews support files up to 50 MiB.")
    reader=PdfReader(path)
    if not 0<=page_index<len(reader.pages):
        raise ValueError('PDF page does not exist.')
    page=reader.pages[page_index]
    box=page.cropbox
    left,bottom,right,top=map(float,(box.left,box.bottom,box.right,box.top))
    if right<=left or top<=bottom:
        raise ValueError('PDF page has invalid bounds.')
    rotation=int(page.rotation)%360
    result=[]
    for ref in (page.get('/Annots') or [])[:500]:
        try:obj=ref.get_object()
        except (ValueError,TypeError,AttributeError):continue
        if not isinstance(obj,dict):continue
        kind=str(obj.get('/Subtype',''))
        if kind not in ('/Text','/FreeText','/Highlight','/StrikeOut','/Underline','/Ink','/Square','/Circle','/Stamp','/Line','/Polygon','/PolyLine','/Caret','/Squiggly'):
            continue
        rect=obj.get('/Rect')
        if not rect or len(rect)!=4: continue
        try:x0,y0,x1,y1=map(float,rect)
        except (ValueError,TypeError):continue
        if not all(map(math.isfinite,(x0,y0,x1,y1))): continue
        x,y=((x0+x1)/2-left)/(right-left),((y0+y1)/2-bottom)/(top-bottom)
        # Normalized from the displayed page's lower-left.
        x,y={0:(x,y),90:(y,1-x),180:(1-x,1-y),270:(1-y,x)}.get(rotation,(x,y))
        if not (0<=x<=1 and 0<=y<=1): continue
        body=str(obj.get('/Contents','')).strip() or kind.lstrip('/')
        result.append(dict(text=body[:1500],author=str(obj.get('/T',''))[:100],x=x,y=y,resolved=False))
    return result

def linetype_recipe(name,dash,gap,text,height):
    name=label(name,48).upper()
    if not re.fullmatch(r'[A-Z][A-Z0-9_-]*',name):
        raise ValueError('Use letters, digits, underscores or hyphens for the style name.')
    text=label(text,24)
    vals=tuple(float(x) for x in (dash,gap,height))
    if any(not math.isfinite(x) or not 1e-5<=x<=1e7 for x in vals):
        raise ValueError('Dash length, gap and text height must be positive.')
    return dict(name=name,dash=vals[0],gap=vals[1],text=text,height=vals[2])

def door_recipe(width, angle, hand, swing):
    width, angle = float(width), float(angle)
    if not 1e-5 <= width <= 1e8 or not 1 <= angle <= 180 or hand not in ('Left','Right') or swing not in ('In','Out'):
        raise ValueError('Enter a positive door width and an opening angle of 1–180°.')
    return dict(width=width, angle=angle, hand=hand, swing=swing)

def validate_office(value, payload):
    for name, r in value.get('office_doors',{}).items():
        if not isinstance(r,dict) or set(r)!={'width','angle','hand','swing'} or r != door_recipe(**r):
            raise ValueError('Invalid door parameters.')
    for name, r in value.get('office_linetypes',{}).items():
        from .linetypes import NAMES
        if not isinstance(r,dict) or set(r)!={'name','dash','gap','text','height'} or r != linetype_recipe(**r) or name!=r['name'] or name in NAMES or name in ('BYLAYER','BYBLOCK'):
            raise ValueError('Invalid custom linetype.')
    for r in value.get('office_reviews',{}).values():
        if not isinstance(r,dict) or set(r)!={'notes','space'} or not isinstance(r['space'],str) or not isinstance(r['notes'],list) or len(r['notes'])>500:
            raise ValueError('Invalid review page.')
        for n in r['notes']:
            if (not isinstance(n,dict) or set(n)!={'text','author','x','y','resolved'}
                or not isinstance(n['text'],str) or len(n['text'])>1500 or not isinstance(n['author'],str) or len(n['author'])>100
                or type(n['resolved']) is not bool or any(type(n[k]) not in (int,float) or not 0<=n[k]<=1 for k in ('x','y'))):
                raise ValueError('Invalid review annotation.')
