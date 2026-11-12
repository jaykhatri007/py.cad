"""Review wall endpoint gaps and hosted-opening overlaps before editing."""
import math
from .wall_joining import frames


def inspect(doc,tolerance=1):
    if type(tolerance) not in (int,float) or not math.isfinite(tolerance) or tolerance<=0:raise ValueError('Use a positive gap tolerance')
    walls=frames(doc);issues=[];cells={}
    for key,f in walls.items():
        for end,p in enumerate((f['a'],f['b'])):
            cell=(math.floor(p[0]/tolerance),math.floor(p[1]/tolerance))
            for dx in (-1,0,1):
                for dy in (-1,0,1):
                    for other,otherend,q in cells.get((cell[0]+dx,cell[1]+dy),[]):
                        if key==other or f['level']!=walls[other]['level']:continue
                        distance=math.dist(p,q)
                        if 1e-9<distance<=tolerance:issues.append(dict(kind='endpoint_gap',sources=[key,other],distance=distance,ends=[end,otherend],target=[(p[0]+q[0])/2,(p[1]+q[1])/2]))
            cells.setdefault(cell,[]).append((key,end,p))
    openings={}
    for key,r in doc.extensions.get('architecture',{}).items():
        if r['kind']=='opening' and doc.find_by_id(key):openings.setdefault(r['wall'],[]).append((key,r))
    for items in openings.values():
        for i,(key,r) in enumerate(items):
            for other,s in items[:i]:
                if abs(s['station']-r['station'])<(s['width']+r['width'])/2:issues.append(dict(kind='overlapping_openings',sources=[key,other]))
    return issues


def gap_actions(doc,tolerance=1):
    walls=frames(doc);targets={}
    for issue in inspect(doc,tolerance):
        if issue['kind']!='endpoint_gap':continue
        pairs=list(zip(issue['sources'],issue['ends']))
        if any(p in targets for p in pairs):raise ValueError('Ambiguous endpoint cluster; align these walls manually')
        for pair in pairs:targets[pair]=issue['target']
    actions=[]
    for key,f in walls.items():
        if not any((key,end) in targets for end in (0,1)):continue
        e=f['entity']
        if e not in doc.editable_entities() or e.mirrored or abs(e.scale-1)>1e-9:raise ValueError('Alignment requires editable, unscaled and unmirrored walls')
        a,b=targets.get((key,0),f['a']),targets.get((key,1),f['b']);length=math.dist(a,b)
        if length<=1e-9:raise ValueError('Alignment would collapse a wall')
        actions.append(dict(op='properties',ids=[key],values={'insertion_point.x':a[0],'insertion_point.y':a[1],'rotation':math.degrees(math.atan2(b[1]-a[1],b[0]-a[0])),'Architecture.length':length}))
    return actions
