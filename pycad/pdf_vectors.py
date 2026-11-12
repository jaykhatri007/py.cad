"""Supported PDF page vector paths to editable polylines; never raster/OCR."""
import math
from pathlib import Path
from .geometry import Point,PolylineEntity

def compose(a,b):return (a[0]*b[0]+a[2]*b[1],a[1]*b[0]+a[3]*b[1],a[0]*b[2]+a[2]*b[3],a[1]*b[2]+a[3]*b[3],a[0]*b[4]+a[2]*b[5]+a[4],a[1]*b[4]+a[3]*b[5]+a[5])

def import_page(path,page_number=1,scale=1.,offset=(0,0),curve_steps=24,cleanup_tolerance=1e-7):
    from pypdf import PdfReader,PdfWriter
    from pypdf.generic import ContentStream
    from .productivity import number,positive
    positive(scale);number(cleanup_tolerance)
    if cleanup_tolerance<0 or type(curve_steps) is not int or not 4<=curve_steps<=256:raise ValueError('Use nonnegative cleanup tolerance and 4–256 curve segments')
    if Path(path).stat().st_size>256*1024*1024:raise ValueError('Split PDF files larger than 256 MiB before import')
    reader=PdfReader(path)
    if reader.is_encrypted:raise ValueError('Unlock the PDF before importing')
    if type(page_number) is not int or not 1<=page_number<=len(reader.pages):raise ValueError('Page outside PDF document')
    writer=PdfWriter();page=writer.add_page(reader.pages[page_number-1]);page.transfer_rotation_to_content();box=page.cropbox;unit=float(page.get('/UserUnit',1));positive(unit)
    matrix=(1.,0.,0.,1.,0.,0.);color='#000000';stack=[];paths=[];current=[];entities=[];warnings=set();seen=set();removed=0
    def transform(x,y):
        x,y=float(x),float(y);a,b,c,d,e,f=matrix
        return Point((a*x+c*y+e-float(box.left))*scale*unit+offset[0],(b*x+d*y+f-float(box.bottom))*scale*unit+offset[1])
    def flush(closed=False):
        nonlocal current
        if current:paths.append((current,closed));current=[]
    def emit(close=False):
        nonlocal paths,removed
        flush(close)
        for points,closed in paths:
            out=[]
            for p in points:
                if not out or math.hypot(p.x-out[-1].x,p.y-out[-1].y)>cleanup_tolerance:out.append(p)
            if len(out)>2 and math.hypot(out[0].x-out[-1].x,out[0].y-out[-1].y)<=cleanup_tolerance:out.pop();closed=True
            if len(out)<2:removed+=1;continue
            key=(closed,tuple((round(p.x,9),round(p.y,9)) for p in out),color)
            if key in seen:removed+=1;continue
            seen.add(key);entities.append(PolylineEntity(out,closed=closed,color=color))
        paths=[]
    def rgb(values):return '#'+''.join(f'{max(0,min(255,round(float(v)*255))):02x}' for v in values)
    content=page.get_contents()
    for args,op in ([] if content is None else ContentStream(content,writer).operations):
        if op==b'q':stack.append((matrix,color))
        elif op==b'Q':
            if stack:matrix,color=stack.pop()
            else:warnings.add('Unbalanced PDF graphics state')
        elif op==b'cm':matrix=compose(matrix,tuple(map(float,args)))
        elif op==b'm':flush();current=[transform(*args)]
        elif op==b'l':
            if current:current.append(transform(*args))
        elif op==b're':
            flush();x,y,w,h=map(float,args);paths.append(([transform(x,y),transform(x+w,y),transform(x+w,y+h),transform(x,y+h)],True))
        elif op==b'h':
            if current:start=current[0];flush(True);current=[start]
        elif op in (b'c',b'v',b'y'):
            if not current:continue
            start=current[-1]
            if op==b'c':p1,p2,p3=[transform(*args[i:i+2]) for i in (0,2,4)]
            elif op==b'v':p1=start;p2,p3=[transform(*args[i:i+2]) for i in (0,2)]
            else:p1,p3=[transform(*args[i:i+2]) for i in (0,2)];p2=p3
            for i in range(1,curve_steps+1):
                t=i/curve_steps;u=1-t;current.append(Point(u**3*start.x+3*u*u*t*p1.x+3*u*t*t*p2.x+t**3*p3.x,u**3*start.y+3*u*u*t*p1.y+3*u*t*t*p2.y+t**3*p3.y))
        elif op in (b'S',b's',b'B',b'B*',b'b',b'b*',b'f',b'F',b'f*'):
            if op not in (b'S',b's'):warnings.add('Filled PDF paths imported as outlines')
            emit(op in (b's',b'b',b'b*',b'f',b'F',b'f*'))
        elif op==b'n':paths=[];current=[]
        elif op==b'RG':color=rgb(args)
        elif op==b'G':color=rgb([args[0]]*3)
        elif op==b'K':
            c,m,y,k=map(float,args);color=rgb([1-min(1,c+k),1-min(1,m+k),1-min(1,y+k)])
        elif op in (b'W',b'W*'):warnings.add('Clipping is not reproduced; review geometry beyond clip boundaries')
        elif op==b'Do':warnings.add('Images and Form XObjects skipped; use PDFATTACH for full appearance')
        elif op in (b'Tj',b'TJ',b"'",b'"'):warnings.add('PDF text skipped; vector paths only')
        elif op in (b'd',b'w',b'gs'):warnings.add('Dash, width and transparency styling simplified')
    return entities,dict(page=page_number,pages=len(reader.pages),objects=len(entities),removed_degenerate_or_duplicate=removed,warnings=sorted(warnings),scale=scale,curves=f'{curve_steps} segments per cubic',note='Supported 2D vector paths; original PDF unchanged')
