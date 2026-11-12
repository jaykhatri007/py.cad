"""Net odd-even hatch area for disjoint, non-touching simple polygon loops."""
from .geometry import LineEntity
from .spatial_index import SpatialIndex
from .geom_ops import point_in_polygon


def hatch_area(hatch):
    from .hatching import render_loops
    loops=[list(loop) for loop in render_loops(hatch)];edges=[];info={}
    for loop in loops:
        if len(loop)>1 and loop[0].distance_to(loop[-1])<1e-12:loop.pop()
    for k,loop in enumerate(loops):
        if len(loop)<3:raise ValueError('Hatch loop is not a closed measurable boundary')
        for i,(a,b) in enumerate(zip(loop,loop[1:]+loop[:1])):
            if a.distance_to(b)<1e-12:continue
            edge=LineEntity(a,b);info[id(edge)]=(k,i,len(loop),len(edges));edges.append(edge)
    index=SpatialIndex();index.rebuild(edges)
    def cross(a,b,p):return (b.x-a.x)*(p.y-a.y)-(b.y-a.y)*(p.x-a.x)
    def intersects(a,b,c,d):
        aa,bb,cc,dd=cross(a,b,c),cross(a,b,d),cross(c,d,a),cross(c,d,b)
        return aa*bb<=0 and cc*dd<=0
    for edge in edges:
        k,i,n,order=info[id(edge)]
        for other in index.query(edge.bbox()):
            q,j,m,other_order=info[id(other)]
            if order>=other_order or (k==q and (abs(i-j)==1 or {i,j}=={0,n-1})):continue
            if intersects(edge.p1,edge.p2,other.p1,other.p2):
                raise ValueError('Crossing or touching hatch loops need boundary repair before quantity measurement')
    total=0
    for i,loop in enumerate(loops):
        area=abs(sum(a.x*b.y-a.y*b.x for a,b in zip(loop,loop[1:]+loop[:1])))/2
        depth=sum(point_in_polygon(loop[0],other) for j,other in enumerate(loops) if i!=j)
        total+=area*(-1 if depth%2 else 1)
    return max(0,total)
