"""Disposable ordered child index for nested-block viewport drawing."""
from .spatial_index import SpatialIndex
from .geometry import RayEntity,XLineEntity

def visible_children(reference,box,revision):
    children=reference.resolved_entities
    if box is None or len(children)<=64:return children
    key=(id(children),len(children),revision,reference.insertion_point.x,reference.insertion_point.y,reference.scale,reference.rotation,reference.mirrored)
    if getattr(reference,'_display_index_key',None)!=key:
        index=SpatialIndex();index.rebuild(children);reference._display_index=index;reference._display_unbounded=[e for e in children if isinstance(e,(RayEntity,XLineEntity))];reference._display_index_key=key
    result=reference._display_index.query(box)
    if reference._display_unbounded:
        found={id(e) for e in result};result.extend(e for e in reference._display_unbounded if id(e) not in found);result.sort(key=lambda e:reference._display_index._order[id(e)])
    return result
