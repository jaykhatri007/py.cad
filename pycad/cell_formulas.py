"""Small non-executable spreadsheet grammar with dependency/cycle validation."""
import ast,math,re

def number(v):
    if type(v) not in (int,float) or not math.isfinite(v) or abs(v)>1e12:raise ValueError('Formula number outside finite range')
    return v

def address(name):
    match=re.fullmatch(r'([A-Z]+)([1-9][0-9]*)',name)
    if not match:raise ValueError('Invalid cell address')
    col=0
    for ch in match[1]:col=col*26+ord(ch)-64
    return int(match[2])-1,col-1

def calculate(cells):
    cache={};active=set()
    def cell(r,c):
        if r<0 or r>=len(cells) or c<0 or c>=len(cells[r]):raise ValueError('Cell outside table')
        key=(r,c)
        if key in cache:return cache[key]
        if key in active:raise ValueError('Circular formula')
        if len(active)>100:raise ValueError('Dependency chain too deep')
        active.add(key);raw=cells[r][c]
        if raw.startswith('='):
            expr=re.sub(r'\b([A-Z]+[1-9][0-9]*):([A-Z]+[1-9][0-9]*)\b',r'RANGE("\1","\2")',raw[1:].upper())
            try:tree=ast.parse(expr,mode='eval')
            except (SyntaxError,RecursionError):raise ValueError('Invalid formula')
            if sum(1 for _ in ast.walk(tree))>1000:raise ValueError('Formula too complex')
            pending=[(tree,0)]
            while pending:
                n,depth=pending.pop()
                if depth>80:raise ValueError('Formula nesting too deep')
                pending.extend((child,depth+1) for child in ast.iter_child_nodes(n))
            value=number(walk(tree.body))
        else:value=raw
        active.remove(key);cache[key]=value;return value
    def numeric(v):
        try:return number(float(v or 0))
        except (TypeError,ValueError):raise ValueError('Formula requires numeric cells')
    def walk(n):
        if isinstance(n,ast.Constant) and type(n.value) in (int,float):return number(n.value)
        if isinstance(n,ast.Name):return numeric(cell(*address(n.id)))
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.UAdd,ast.USub)):return numeric(walk(n.operand))*(-1 if isinstance(n.op,ast.USub) else 1)
        if isinstance(n,ast.BinOp) and isinstance(n.op,(ast.Add,ast.Sub,ast.Mult,ast.Div,ast.Pow)):
            a,b=numeric(walk(n.left)),numeric(walk(n.right))
            if isinstance(n.op,ast.Pow) and abs(b)>12:raise ValueError('Exponent too large')
            try:v=a+b if isinstance(n.op,ast.Add) else a-b if isinstance(n.op,ast.Sub) else a*b if isinstance(n.op,ast.Mult) else a/b if isinstance(n.op,ast.Div) else a**b
            except (ZeroDivisionError,OverflowError):raise ValueError('Formula arithmetic error')
            return number(v)
        if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and not n.keywords:
            if n.func.id=='RANGE' and len(n.args)==2 and all(isinstance(a,ast.Constant) and isinstance(a.value,str) for a in n.args):
                (r,c),(rr,cc)=[address(a.value) for a in n.args]
                if rr<r or cc<c or (rr-r+1)*(cc-c+1)>200000:raise ValueError('Invalid range')
                return [numeric(cell(y,x)) for y in range(r,rr+1) for x in range(c,cc+1)]
            if n.func.id in ('SUM','AVERAGE','MIN','MAX'):
                values=[]
                for arg in n.args:
                    value=walk(arg);values.extend(value if isinstance(value,list) else [numeric(value)])
                if not values:raise ValueError('Function needs values')
                return number(sum(values) if n.func.id=='SUM' else sum(values)/len(values) if n.func.id=='AVERAGE' else min(values) if n.func.id=='MIN' else max(values))
        raise ValueError('Unsupported formula')
    return [[cell(r,c) for c in range(len(row))] for r,row in enumerate(cells)]
