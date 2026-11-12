"""Per-viewport rotation, paper-coordinate clips and annotation size multiplier."""
import copy,math
from .geometry import Point
from .pro_data import settings,save_section


def config(doc,space,index):return settings(doc).get('viewport_settings',{}).get(space+'::'+str(index),dict(rotation=0.,clip=[],annotation_scale=1.))


def set_config(doc,space,index,rotation=0,clip=(),annotation_scale=1):
    layout=doc.layouts.get(space)
    if layout is None or not 0<=index<len(layout.viewports):raise ValueError('Choose a sheet viewport')
    record=dict(rotation=rotation,clip=[list(p) for p in clip],annotation_scale=annotation_scale)
    from .pro_data import validate
    validate({'viewport_settings':{'test':record}})
    for p in clip:
        if not 0<=p[0]<=layout.page_width or not 0<=p[1]<=layout.page_height:raise ValueError('Clip points must lie on the paper')
    if clip:
        from .geometry import HatchEntity
        from .takeoff_geometry import hatch_area
        if hatch_area(HatchEntity([Point(*p) for p in clip],pattern='SOLID'))<=1e-12:raise ValueError('Clip must enclose an area')
    values=copy.deepcopy(settings(doc).get('viewport_settings',{}));values[space+'::'+str(index)]=record;save_section(doc,'viewport_settings',values,'Viewport rotation / clip / annotation')


def paper_point(vp,x,y,rotation):
    theta=math.radians(rotation);x,y=x-vp.center.x,y-vp.center.y;c,s=math.cos(theta),math.sin(theta)
    return Point(vp.x+vp.width/2+(x*c-y*s)*vp.scale,vp.y+vp.height/2+(x*s+y*c)*vp.scale)


def clip_path(points,transform):
    from PyQt6.QtGui import QPainterPath
    path=QPainterPath()
    if points:
        path.moveTo(transform(*points[0]))
        for p in points[1:]:path.lineTo(transform(*p))
        path.closeSubpath()
    return path
