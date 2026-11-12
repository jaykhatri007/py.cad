"""
dxf_io.py
Import/export drawings to AutoCAD's DXF format using ezdxf.
This is what makes PyCAD files openable in real AutoCAD (and vice versa).

Phase 3 note on Dimensions: true associative DIMENSION entities require a
DXF dimension-style table and are non-trivial to round-trip generically, so
on export we "explode" a DimensionEntity into its constituent LINE and TEXT
primitives (extension lines, dimension line, measurement text) - this is a
common, safe interchange approach. Exploded dimensions are NOT reconstructed
as DimensionEntity objects on import (they come back as plain lines/text),
which is a known limitation.

Blocks/Xrefs use ezdxf's real block table + INSERT entities (not exploded),
so they round-trip as genuine, editable blocks in AutoCAD/LibreCAD/FreeCAD.
Layouts use ezdxf's real Paper Space layout + VIEWPORT support.
"""
import math
import ezdxf
import math
import os
import base64
import hashlib
from .native_io import atomic_write
from .validation import MAX_SOURCE_BYTES


class _ImportBudgetError(ValueError):
    pass
from .layout import Layout, Viewport
from ezdxf.colors import rgb2int
from .geometry import (Point, LineEntity, CircleEntity, ArcEntity, PolylineEntity,
                        RectangleEntity, TextEntity, DimensionEntity, HatchEntity, SplineEntity,
                        PointEntity, EllipseEntity, RayEntity, XLineEntity,
                        BlockDefinition, BlockReferenceEntity)
from .document import Document

from .linetypes import DXF_NAMES as LINETYPE_TO_DXF, FROM_DXF as LINETYPE_FROM_DXF


def _hex_to_rgb(hexstr: str):
    hexstr = hexstr.lstrip("#")
    if len(hexstr) != 6:
        return (255, 255, 255)
    return tuple(int(hexstr[i:i + 2], 16) for i in (0, 2, 4))


def _textstyle_name(name):
    return 'PYCAD_TEXT_'+hashlib.sha256(name.encode()).hexdigest()[:16]


def _export_entity(target, e, attribs: dict, document=None):
    attribs = dict(attribs)
    if e.transparency:
        attribs["transparency"] = ezdxf.colors.float2transparency(e.transparency/100.0)
    if e.hyperlink:
        class HyperlinkTarget:
            def __getattr__(self, name):
                method = getattr(target,name)
                if not name.startswith("add_") or not callable(method):return method
                def create(*args,**kwargs):
                    item=method(*args,**kwargs)
                    item.set_hyperlink(e.hyperlink)
                    return item
                return create
        _export_entity_geometry(HyperlinkTarget(),e,attribs,document)
    else:
        _export_entity_geometry(target,e,attribs,document)


def _export_entity_geometry(target, e, attribs: dict, document=None):
    """Write one PyCAD entity into `target` (modelspace OR a block layout -
    both support the same add_* API in ezdxf, which is what lets this
    function serve both regular entities and block-definition contents)."""
    if e.kind == 'MLEADER':
        from .mleaders import style_for
        style = style_for(document, e) if document is not None else e._mleader_style
        attribs = dict(attribs)
        if style['color'] != 'BYLAYER':
            attribs['true_color'] = ezdxf.colors.rgb2int(_hex_to_rgb(style['color']))
        lines, fills, labels = e.geometry(style)
        for a, b in lines:
            target.add_line(a.as_tuple(), b.as_tuple(), dxfattribs=attribs)
        for triangle in fills:
            target.add_solid([p.as_tuple() for p in triangle], dxfattribs=attribs)
        for text, position, height, rotation in labels:
            if text:
                _export_entity_geometry(target, TextEntity(position, text, height, rotation), {**attribs, 'style':'Standard'}, None)
    elif isinstance(e, RectangleEntity):
        target.add_lwpolyline([(p.x,p.y,e.bulges[i]) for i,p in enumerate(e.points)],format="xyb",close=True,dxfattribs={**attribs,"const_width":e.width})
    elif isinstance(e, PolylineEntity):
        target.add_lwpolyline([(p.x,p.y,e.bulges[i]) for i,p in enumerate(e.points)],format="xyb",close=e.closed,dxfattribs={**attribs,"const_width":e.width})
    elif isinstance(e, LineEntity):
        target.add_line((e.p1.x, e.p1.y), (e.p2.x, e.p2.y), dxfattribs=attribs)
    elif isinstance(e, PointEntity):
        target.add_point((e.point.x, e.point.y), dxfattribs=attribs)
    elif isinstance(e, ArcEntity):
        target.add_arc((e.center.x, e.center.y), e.radius, e.start_angle, e.end_angle, dxfattribs=attribs)
    elif isinstance(e, CircleEntity):
        target.add_circle((e.center.x, e.center.y), e.radius, dxfattribs=attribs)
    elif isinstance(e, EllipseEntity):
        angle = math.radians(e.rotation)
        target.add_ellipse((e.center.x, e.center.y),
                           major_axis=(e.major_radius * math.cos(angle), e.major_radius * math.sin(angle)),
                           ratio=e.minor_radius / e.major_radius, dxfattribs=attribs)
    elif isinstance(e, XLineEntity):
        dx, dy = e.p2.x - e.p1.x, e.p2.y - e.p1.y
        length = math.hypot(dx, dy)
        target.add_xline((e.p1.x, e.p1.y), (dx / length, dy / length), dxfattribs=attribs)
    elif isinstance(e, RayEntity):
        dx, dy = e.p2.x - e.p1.x, e.p2.y - e.p1.y
        length = math.hypot(dx, dy)
        target.add_ray((e.p1.x, e.p1.y), (dx / length, dy / length), dxfattribs=attribs)
    elif isinstance(e, SplineEntity):
        from .precision import spline_curve
        spline=target.add_spline(dxfattribs=attribs);spline.apply_construction_tool(spline_curve(e))
        if e.closed: spline.dxf.flags |= 1
        if e.curve_mode=="fit": spline.fit_points=[(p.x,p.y,0) for p in e.points]
    elif isinstance(e, TextEntity):
        from .textstyles import style_for, DEFAULT_STYLE
        style = style_for(document,e) if document is not None else DEFAULT_STYLE
        attribs = {**attribs,'style':attribs.get('style',_textstyle_name(e.style_name) if document else 'Standard')}
        if '\n' in e.text and (style['width_factor'] != 1 or style['oblique'] != 0):
            from .geometry import _rotate_pt
            for i, text in enumerate(e.text.split('\n')):
                position = _rotate_pt(Point(e.position.x,e.position.y-i*e.height*1.4),e.position,e.rotation)
                _export_entity_geometry(target,TextEntity(position,text,e.height,e.rotation,style_name=e.style_name),attribs,document)
            return
        if "\n" in e.text:
            # Escape literal DXF control characters before encoding paragraph breaks.
            content = e.text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}").replace("\n", "\\P")
            angle = math.radians(e.rotation)
            target.add_mtext(content,dxfattribs={**attribs,"char_height":e.height,"rotation":e.rotation,
                "attachment_point":1,"line_spacing_factor":1.4/1.667,
                "insert":(e.position.x-e.height*math.sin(angle),e.position.y+e.height*math.cos(angle))})
        else:
            txt = target.add_text(e.text, dxfattribs={**attribs, "height": e.height, "rotation": e.rotation,
                                                    'width':style['width_factor'],'oblique':style['oblique']})
            txt.dxf.insert = (e.position.x, e.position.y)
    elif isinstance(e, DimensionEntity):
        _export_dimension(target, e, attribs, document)
    elif isinstance(e, HatchEntity):
        _export_hatch(target, e, attribs)
    elif isinstance(e, BlockReferenceEntity):
        insert=target.add_blockref(e.block_name, insert=(e.insertion_point.x,e.insertion_point.y),dxfattribs={**attribs,"xscale":e.scale,"yscale":-e.scale if e.mirrored else e.scale,"rotation":e.rotation})
        if document is not None:
            block=document.blocks.get(e.block_name)
            if block and block.attributes: insert.add_auto_attribs({spec['tag']:e.attributes.get(spec['tag'],spec['default']) for spec in block.attributes})


def _build_ezdxf_doc(document: Document) -> "ezdxf.document.Drawing":
    """Build a real ezdxf Drawing object from our Document - shared by both
    DXF export and DWG export (LibreDWG R2000 or optional ODA), so DWG
    support is just "export/import this same DXF representation through an
    external converter" rather than a second thing to maintain."""
    if document.extrusions or document.extensions.get("solids"):
        raise ValueError("This drawing contains 3D extrusions; save as .pycad or export STEP/STL. DXF/DWG 3D export is not supported yet.")
    doc = ezdxf.new("R2018", setup=True)
    from .linetypes import install_dxf
    install_dxf(doc)
    doc.header['$LTSCALE']=document.linetype_scale
    office_styles=document.extensions.get('office_linetypes',{})
    def exchange_linetype(name,default=None):
        return 'DASHED' if name in office_styles else LINETYPE_TO_DXF.get(name,default)

    doc.units = {"unitless":0,"in":1,"ft":2,"mm":4,"cm":5,"m":6}.get(document.units, 4)
    msp = doc.modelspace()
    for name,style in document.textstyles.items():
        entry=doc.styles.new(_textstyle_name(name),dxfattribs={'font':'txt','height':0,'last_height':style['height']})
        entry.set_extended_font_data(style['font_family'],bold=style['bold'],italic=style['italic'])

    for name, props in document.layers.layers.items():
        layer = doc.layers.get(name) if name in doc.layers else doc.layers.add(name=name)
        layer.off() if not props.get("visible", True) else layer.on()
        layer.lock() if props.get("locked", False) else layer.unlock()
        layer.freeze() if props.get("frozen", False) else layer.thaw()
        layer.dxf.linetype = exchange_linetype(props.get("linetype"), "Continuous")
        layer.dxf.lineweight = round(props.get("lineweight", .25)*100)
        layer.dxf.plot = int(props.get("plot", True))
        try:
            layer.rgb = _hex_to_rgb(props.get("color", "#FFFFFF"))
        except Exception:
            pass

    # Block/Xref definitions must exist in the DXF block table before any
    # INSERT can reference them by name.
    for name, block_def in document.blocks.items():
        if name in doc.blocks:
            continue
        block = doc.blocks.new(name=name)
        for sub_e in block_def.entities:
            sub_attribs = {"layer": sub_e.layer}
            sub_linetype = exchange_linetype(getattr(sub_e, "linetype", "CONTINUOUS"))
            if sub_linetype:
                sub_attribs["linetype"] = sub_linetype
            if sub_e.color and sub_e.color != "BYLAYER":
                sub_attribs["true_color"] = ezdxf.colors.rgb2int(_hex_to_rgb(sub_e.color))
            _export_entity(block, sub_e, sub_attribs, document)

    for name,block_def in document.blocks.items():
        block=doc.blocks[name]
        for spec in block_def.attributes:
            att=block.add_attdef(spec['tag'],insert=spec['position'],text=spec['default'],height=spec['height'],dxfattribs={'prompt':spec['prompt'],'rotation':spec['rotation'],'layer':spec['layer'],'style':_textstyle_name(spec['style_name'])})
            att.is_invisible=not spec['visible']

    exported = {}
    class GroupTarget:
        def __init__(self, target): self.target=target;self.created=[]
        def __getattr__(self,name):
            method=getattr(self.target,name)
            if not name.startswith('add_') or not callable(method): return method
            def create(*args,**kwargs):
                item=method(*args,**kwargs);self.created.append(item);return item
            return create
    group_target = GroupTarget(msp) if document.extensions.get('groups') else None
    for e in document.entities:
        attribs = {"layer": e.layer}
        linetype = exchange_linetype(getattr(e, "linetype", "CONTINUOUS"))
        if linetype:
            attribs["linetype"] = linetype
        if e.color and e.color != "BYLAYER":
            attribs["true_color"] = ezdxf.colors.rgb2int(_hex_to_rgb(e.color))
        if group_target:
            group_target.created=[]
            _export_entity(group_target,e,attribs,document)
            exported[e.id]=list(group_target.created)
        else:
            _export_entity(msp, e, attribs, document)
    for name,members in document.extensions.get('groups',{}).items():
        items=[e for key in members for e in exported.get(key,[])]
        if len(items)>=2:doc.groups.new(name).extend(items)

    for name, layout in document.layouts.items():
        dxf_layout = doc.layouts.get(name) if name in doc.layouts else doc.layouts.new(name)
        dxf_layout.page_setup(size=(layout.page_width, layout.page_height))
        from .sheets import title_geometry
        for entity in title_geometry(document,name): _export_entity(dxf_layout,entity,{'layer':'0'},document)
        for vp in layout.viewports:
            dxf_layout.add_viewport(
                center=(vp.x + vp.width / 2, vp.y + vp.height / 2),
                size=(vp.width, vp.height),
                view_center_point=(vp.center.x, vp.center.y),
                view_height=vp.height / vp.scale)

    return doc


def export_dxf(document: Document, filepath: str):
    if document.extrusions or document.extensions.get("solids"):
        raise ValueError("This drawing contains saved 3D extrusions. Save as .pycad, or export solids as STEP/STL from the 3D workspace; DXF 3D export is not supported yet.")
    doc = _build_ezdxf_doc(document)
    atomic_write(filepath, doc.saveas)


def _export_dimension(msp, e: DimensionEntity, attribs: dict, document=None):
    from .dimstyles import DEFAULT_STYLE, style_for, dimension_geometry, dimension_label
    style = style_for(document,e) if document is not None else DEFAULT_STYLE
    lines,fills,anchor,height = dimension_geometry(e,style)
    attribs = dict(attribs)
    if style['color'] != 'BYLAYER':attribs['true_color']=rgb2int(_hex_to_rgb(style['color']))
    for a,b in lines:msp.add_line(a.as_tuple(),b.as_tuple(),dxfattribs=attribs)
    for triangle in fills:
        msp.add_solid([p.as_tuple() for p in triangle]+[triangle[-1].as_tuple()],dxfattribs=attribs)
    txt=msp.add_text(dimension_label(e,style),dxfattribs={**attribs,'height':height})
    txt.dxf.insert=anchor.as_tuple()
    if e.dim_style not in ('radius','diameter'):
        txt.dxf.halign=1
        txt.dxf.align_point=anchor.as_tuple()


def _export_hatch(msp, e: HatchEntity, attribs: dict):
    hatch = msp.add_hatch(color=7, dxfattribs=attribs)
    for index, loop in enumerate([e.boundary,*e.holes]):
        flags = e.loop_flags[index] if e.loop_flags else (1 if index==0 else 0)
        hatch.paths.add_polyline_path([(p.x,p.y) for p in loop],is_closed=True,flags=flags)
    if e.pattern == "SOLID":
        hatch.set_solid_fill()
    elif e.pattern.startswith('GRADIENT_'):
        if e.pattern == 'GRADIENT_CONICAL':
            raise ValueError('Conical gradient has no DXF HATCH equivalent; use linear or radial before DXF export')
        fill_color=e.color
        if fill_color=='BYLAYER':
            layer=msp.doc.layers.get(e.layer)
            rgb=layer.rgb or ezdxf.colors.aci2rgb(abs(layer.dxf.color))
            fill_color='#%02x%02x%02x'%tuple(rgb)
        hatch.set_gradient(color1=_hex_to_rgb(fill_color),
            color2=_hex_to_rgb(e.gradient_color),rotation=e.angle,
            name='LINEAR' if e.pattern=='GRADIENT_LINEAR' else 'SPHERICAL')
    else:
        from .hatching import definitions
        hatch.set_pattern_fill(e.pattern,scale=1,angle=0,style={'normal':0,'outer':1,'ignore':2}[e.island_style],
                               pattern_type=2,definition=definitions(e))
        # The actual definition already includes origin, scale, rotation/double.
        hatch.dxf.pattern_angle=e.angle;hatch.dxf.pattern_scale=e.pattern_scale
    hatch.dxf.hatch_style={'normal':0,'outer':1,'ignore':2}[e.island_style]
    if e.background_color:hatch.bgcolor=_hex_to_rgb(e.background_color)


def _import_entity(e, layer: str, linetype: str):
    """Convert one ezdxf entity into a PyCAD entity, or return None if it's
    an unsupported/malformed type. Shared between modelspace and block
    content import."""
    t = e.dxftype()
    if t == "LINE":
        p1, p2 = e.dxf.start, e.dxf.end
        return LineEntity(Point(p1[0], p1[1]), Point(p2[0], p2[1]), layer=layer, linetype=linetype)
    if t == "POINT":
        point = e.dxf.location
        return PointEntity(Point(point[0], point[1]), layer=layer, linetype=linetype)
    if t == "CIRCLE":
        c = e.dxf.center
        return CircleEntity(Point(c[0], c[1]), e.dxf.radius, layer=layer, linetype=linetype)
    if t == "ELLIPSE":
        c = e.dxf.center
        major = e.dxf.major_axis
        major_radius = math.hypot(major[0], major[1])
        if major_radius <= 1e-12 or e.dxf.ratio <= 0:
            return None
        return EllipseEntity(Point(c[0], c[1]), major_radius, major_radius * e.dxf.ratio,
                             math.degrees(math.atan2(major[1], major[0])), layer=layer, linetype=linetype)
    if t in ("RAY", "XLINE"):
        base = e.dxf.start
        direction = e.dxf.unit_vector
        p1 = Point(base[0], base[1])
        p2 = Point(base[0] + direction[0], base[1] + direction[1])
        cls = RayEntity if t == "RAY" else XLineEntity
        return cls(p1, p2, layer=layer, linetype=linetype)
    if t == "ARC":
        c = e.dxf.center
        return ArcEntity(Point(c[0], c[1]), e.dxf.radius, e.dxf.start_angle, e.dxf.end_angle,
                          layer=layer, linetype=linetype)
    if t in ("LWPOLYLINE", "POLYLINE"):
        pts = [Point(float(p[0]),float(p[1])) for p in e.get_points(format="xy")] if t == "LWPOLYLINE" \
            else [Point(v.dxf.location[0], v.dxf.location[1]) for v in e.vertices]
        closed = bool(getattr(e, "closed", False)) or e.dxf.get("flags", 0) & 1
        bulges=[float(p[2]) for p in e.get_points(format="xyb")] if t=="LWPOLYLINE" else [v.dxf.get("bulge",0) for v in e.vertices]
        if not closed and bulges: bulges[-1]=0
        return PolylineEntity(pts,closed=bool(closed),bulges=bulges,width=e.dxf.get("const_width",0) if t=="LWPOLYLINE" else e.dxf.get("default_start_width",0),layer=layer,linetype=linetype)
    if t == "TEXT":
        pos = e.dxf.insert
        return TextEntity(Point(pos[0], pos[1]), e.dxf.text, height=e.dxf.height, rotation=e.dxf.get("rotation", 0), layer=layer)
    if t == "MTEXT":
        pos = e.dxf.insert
        rotation = e.get_rotation()
        height = e.dxf.char_height
        angle = math.radians(rotation)
        return TextEntity(Point(pos[0]+height*math.sin(angle),pos[1]-height*math.cos(angle)),e.plain_text(),height=height,rotation=rotation,layer=layer,linetype=linetype)
    if t == "SPLINE":
        fit=[Point(float(p[0]),float(p[1])) for p in e.fit_points]
        if len(fit)>=2: return SplineEntity(fit,closed=bool(e.closed),degree=e.dxf.degree,layer=layer)
        control=[Point(float(p[0]),float(p[1])) for p in e.control_points]
        if len(control)>=2: return SplineEntity(control,closed=bool(e.closed),degree=e.dxf.degree,knots=[float(k) for k in e.knots],weights=[float(w) for w in e.weights],curve_mode='nurbs',layer=layer)
    if t == "HATCH":
        boundary = []
        loops=[]
        flags=[]
        from ezdxf.path import from_hatch_boundary_path
        total_vertices = 0
        for source_path in e.paths:
            path = from_hatch_boundary_path(source_path, e.ocs(), elevation=e.dxf.elevation.z)
            for subpath in (path.sub_paths() if path.has_sub_paths else [path]):
                loop=[]
                for p in subpath.flattening(distance=0.01,segments=8):
                    loop.append(Point(p.x,p.y))
                    total_vertices += 1
                if len(loop)>1 and loop[-1].distance_to(loop[0])<1e-9:loop.pop()
                if len(loop)>=3:
                    loops.append(loop);flags.append(source_path.path_type_flags)
        if loops:
            ordered=sorted(zip(loops,flags),key=lambda pair:abs(sum(a.x*b.y-b.x*a.y for a,b in zip(pair[0],pair[0][1:]+pair[0][:1]))),reverse=True)
            loops,flags=map(list,zip(*ordered));boundary=loops[0]
        if boundary:
            pattern = "SOLID" if e.dxf.solid_fill else e.dxf.pattern_name
            angle=e.dxf.get('pattern_angle',0);scale=e.dxf.get('pattern_scale',1)
            options={}
            if e.pattern and not e.dxf.solid_fill:
                from ezdxf.tools.pattern import scale_pattern
                options['pattern_definition']=scale_pattern(e.pattern.as_list(),1/scale,-angle)
            if e.gradient and e.gradient.number_of_colors:
                pattern='GRADIENT_LINEAR' if e.gradient.name=='LINEAR' else 'GRADIENT_RADIAL'
                angle=e.gradient.rotation
                options['color']='#%02x%02x%02x'%tuple(e.gradient.color1)
                options['gradient_color']='#%02x%02x%02x'%tuple(e.gradient.color2)
            if e.bgcolor:options['background_color']='#%02x%02x%02x'%tuple(e.bgcolor)
            return HatchEntity(boundary, pattern=pattern, angle=angle, pattern_scale=scale,
                               island_style={0:'normal',1:'outer',2:'ignore'}.get(e.dxf.hatch_style,'normal'),
                               holes=loops[1:], loop_flags=flags, layer=layer,**options)
    return None


def import_dxf(filepath: str, original_source=None) -> Document:
    from .validation import MAX_FILE_BYTES
    doc = ezdxf.readfile(filepath)
    return _document_from_ezdxf_doc(doc, original_source or filepath)


def _document_from_ezdxf_doc(doc, filepath: str) -> Document:
    document = Document()
    from .linetypes import validate_scale
    document.linetype_scale=validate_scale(doc.header.get('$LTSCALE',1.0))
    document.units = {0:"unitless",1:"in",2:"ft",4:"mm",5:"cm",6:"m"}.get(doc.units, "unitless")
    warnings = set()
    from .import_attributes import AttributeTags
    attribute_tags={block.name:AttributeTags(e.dxf.tag for e in block if e.dxftype()=='ATTDEF') for block in doc.blocks}
    for block_name,tags in attribute_tags.items():
        if tags.renamed:
            mapping=', '.join(f'{old} → {new}' for old,new in tags.renamed[:8])
            if len(tags.renamed)>8:mapping+=f', … ({len(tags.renamed)} renamed definitions total)'
            warnings.add(f'Duplicate attribute tags in block {block_name!r} renamed in the imported copy ({mapping}); all definitions retained; original source unchanged')
    substituted_linetypes=set()
    from .linetypes import PATTERNS
    for entry in doc.linetypes:
        raw_name=entry.dxf.name.upper();mapped=LINETYPE_FROM_DXF.get(raw_name)
        if mapped in PATTERNS and PATTERNS[mapped]:
            source=[tag.value for tag in entry.pattern_tags.tags if tag.code==49]
            expected=PATTERNS[mapped]
            if entry.pattern_tags.is_complex_type() or len(source)!=len(expected) or any(not math.isclose(a,b,rel_tol=1e-8,abs_tol=1e-9) for a,b in zip(source,expected)):
                substituted_linetypes.add(raw_name)
    for layer in doc.layers:
        name = layer.dxf.name
        if layer.dxf.linetype.upper() in substituted_linetypes:
            warnings.add(f'Linetype {layer.dxf.linetype} has a different source definition; displayed with the PY.cad library pattern')
        if layer.dxf.linetype.upper() not in LINETYPE_FROM_DXF:
            warnings.add(f'Custom layer linetype {layer.dxf.linetype} displayed as continuous')
        color = layer.rgb or ezdxf.colors.aci2rgb(abs(layer.dxf.color))
        document.layers.add_layer(name)
        document.layers.set_color(name, "#%02X%02X%02X" % tuple(color))
        document.layers.set_visible(name, not layer.is_off())
        document.layers.layers[name].update(frozen=layer.is_frozen(),
            linetype=LINETYPE_FROM_DXF.get(layer.dxf.linetype.upper(), "CONTINUOUS"),
            lineweight=max(0,layer.dxf.lineweight)/100 if layer.dxf.lineweight>=0 else .25,
            plot=bool(layer.dxf.get("plot",1)))
        document.layers.set_locked(name, layer.is_locked())

    handle_items = {}
    converted = 0
    def convert(e, depth=0):
        nonlocal converted
        converted += 1
        kind = e.dxftype()
        layer = e.dxf.get("layer", "0")
        raw_lt = e.dxf.get("linetype", "BYLAYER").upper()
        if raw_lt in substituted_linetypes:
            warnings.add(f'Linetype {raw_lt} has a different source definition; displayed with the PY.cad library pattern')
        if not math.isclose(e.dxf.get('ltscale',1.0),1.0):
            warnings.add('Individual DXF entity linetype scales are approximated using the drawing scale')
        linetype = LINETYPE_FROM_DXF.get(raw_lt, "CONTINUOUS")
        if raw_lt not in LINETYPE_FROM_DXF and raw_lt not in ("BYLAYER", "BYBLOCK"):
            warnings.add(f"Custom linetype {raw_lt} displayed as continuous")
        try:
            if kind == "INSERT":
                if not math.isclose(abs(e.dxf.xscale), abs(e.dxf.yscale)) or e.dxf.get("row_count",1)>1 or e.dxf.get("column_count",1)>1:
                    warnings.add("Unsupported non-uniform or array INSERT omitted")
                    return []
                point = e.dxf.insert
                if abs(point.z)>1e-9:
                    warnings.add("3D INSERT elevation flattened to XY")
                tags=attribute_tags.get(e.dxf.name,AttributeTags([]))
                attribute_values,renamed=tags.values((a.dxf.tag,a.dxf.text) for a in e.attribs)
                if renamed:
                    warnings.add(f'Attribute values in block {e.dxf.name!r} matched case-insensitively by occurrence to unique import tags; repeated values retained')
                item = BlockReferenceEntity(e.dxf.name, Point(point.x, point.y),
                    scale=abs(e.dxf.xscale), rotation=e.dxf.rotation+(180 if e.dxf.xscale<0 else 0),
                    mirrored=e.dxf.xscale*e.dxf.yscale<0, attributes=attribute_values, layer=layer, linetype=linetype)
            elif kind == "SOLID":
                pts=[e.dxf.get('vtx'+str(i)) for i in (0,1,3,2)]
                if any(abs(p.z)>1e-9 for p in pts):
                    warnings.add('3D SOLID face flattened to XY')
                boundary=[]
                for p in pts:
                    if not boundary or boundary[-1].as_tuple()!=(p.x,p.y):boundary.append(Point(p.x,p.y))
                if len(boundary)>1 and boundary[0].as_tuple()==boundary[-1].as_tuple():boundary.pop()
                if len(boundary)<3:return []
                item=HatchEntity(boundary,pattern='SOLID',layer=layer,linetype=linetype)
            elif kind == "DIMENSION":
                warnings.add("DXF dimension imported as graphic primitives; association is unavailable")
                return [item for virtual in e.virtual_entities() for item in convert(virtual, depth+1)]
            else:
                if kind == "MTEXT":
                    warnings.add("MTEXT imported as plain multiline text; rich formatting, columns, wrapping and non-top-left alignment are approximated")
                if kind == 'HATCH' and e.gradient and e.gradient.name not in ('LINEAR','SPHERICAL'):
                    warnings.add('Unsupported DXF gradient style approximated as radial; original DXF retained')
                if e.dxf.hasattr("extrusion") and tuple(e.dxf.extrusion)!=(0,0,1):
                    warnings.add(f"{kind} with non-XY extrusion omitted")
                    return []
                for attr in ("start", "end", "center", "insert"):
                    pt = e.dxf.get(attr) if e.dxf.is_supported(attr) else None
                    if pt is not None and hasattr(pt, "z") and abs(pt.z)>1e-9:
                        warnings.add(f"{kind} elevation flattened to XY")
                item = _import_entity(e, layer, linetype)
                if item is None:
                    warnings.add(f"Unsupported entity omitted: {kind}")
                    return []
            if isinstance(item, TextEntity):
                from .textstyles import DEFAULT_STYLE as TEXT_STYLE, validate_style as validate_text_style
                try:
                    source_style=doc.styles.get(e.dxf.get('style','Standard'))
                    family,italic,bold=source_style.get_extended_font_data()
                    value={**TEXT_STYLE,'font_family':family or 'Sans Serif','bold':bold,'italic':italic,
                           'width_factor':e.dxf.get('width',1) if kind=='TEXT' else 1,
                           'oblique':e.dxf.get('oblique',0) if kind=='TEXT' else 0}
                    validate_text_style(value)
                    native_name='DXF_'+_textstyle_name(e.dxf.get('style','Standard')+str(value))
                    document.textstyles[native_name]=value; item.style_name=native_name
                except (ValueError, KeyError):
                    warnings.add('Unsupported text formatting imported with Standard text style')
            if kind == 'HATCH' and e.gradient and e.gradient.number_of_colors:
                pass  # The gradient's first color is independent of entity ACI.
            elif e.dxf.hasattr("true_color"):
                item.color = "#%02X%02X%02X" % tuple(e.rgb)
            elif e.dxf.get("color",256) not in (0,256):
                item.color = "#%02X%02X%02X" % tuple(ezdxf.colors.aci2rgb(e.dxf.color))
            if e.dxf.hasattr("transparency"):
                item.transparency=min(90.0,max(0.0,e.transparency*100.0))
            link=e.get_hyperlink()[0]
            if link:
                from urllib.parse import urlparse
                parsed=urlparse(link)
                if parsed.scheme in ("http","https") and parsed.netloc and len(link)<=2048 and not any(ord(c)<32 for c in link):
                    item.hyperlink=link
                else:warnings.add("Non-web or malformed entity hyperlink omitted")
            if isinstance(item,HatchEntity) and item.holes:
                # Repeated loops occur in external CAD exports. They are not
                # separate islands and must not make the whole drawing fail.
                seen = set()
                clean = []
                clean_flags = []
                for index, loop in enumerate([item.boundary, *item.holes]):
                    key = frozenset((round(p.x, 9), round(p.y, 9)) for p in loop)
                    if key not in seen:
                        seen.add(key); clean.append(loop)
                        if item.loop_flags: clean_flags.append(item.loop_flags[index])
                if len(clean) != 1 + len(item.holes):
                    warnings.add('Duplicate hatch loops removed from the display copy; original source retained')
                item.boundary, item.holes = clean[0], clean[1:]
                item.loop_flags = clean_flags
            if isinstance(item, HatchEntity):
                if e.dxf.get("handle"): handle_items[e.dxf.handle] = item.id
                return compatible_hatches([item])
            if e.dxf.get('handle'):
                handle_items[e.dxf.handle] = item.id
            return [item]
        except (_ImportBudgetError, MemoryError, RecursionError):
            raise
        except Exception as ex:
            warnings.add(f"Malformed {kind} omitted: {type(ex).__name__}")
            return []

    def compatible_hatches(items):
        for hatch in items:
            hatch.boundary_mode = 'evenodd'
        return items

    # Preserve user names including leading underscores and anonymous symbol blocks.
    for block in doc.blocks:
        if block.name.upper().startswith(("*MODEL_SPACE", "*PAPER_SPACE")):
            continue
        items = [item for e in block if e.dxftype()!="ATTDEF" for item in convert(e)]
        base = block.block.dxf.base_point
        for item in items:
            item.translate(-base.x, -base.y)
        source = block.block.dxf.get("xref_path", "") or None
        attributes=[]
        for e,tag in zip((e for e in block if e.dxftype()=='ATTDEF'),attribute_tags[block.name].aliases):
            p=e.dxf.insert;attributes.append(dict(tag=tag,prompt=e.dxf.get('prompt',e.dxf.tag),default=e.dxf.text,position=[p.x-base.x,p.y-base.y],height=e.dxf.height,rotation=e.dxf.get('rotation',0),visible=not e.is_invisible,layer=e.dxf.layer,style_name='Standard'))
        document.blocks[block.name]=BlockDefinition(block.name,items,source,attributes=attributes)

    document.entities = [item for e in doc.modelspace() for item in convert(e)]
    groups = {}
    for name, group in doc.groups:
        members = [handle_items[e.dxf.handle] for e in group if e.dxf.handle in handle_items]
        members = list(dict.fromkeys(members))
        if len(members)>=2: groups[name] = members
    if groups: document.extensions['groups'] = groups
    from .block_budget import check_expansion
    check_expansion(document.blocks, document.entities)
    for sheet in doc.layouts:
        if sheet.name == "Model":
            continue
        record = sheet.dxf_layout.dxf
        width, height = record.paper_width, record.paper_height
        layout = Layout(sheet.name, width or 297, height or 210)
        for e in sheet:
            if e.dxftype() != "VIEWPORT":
                warnings.add("Paper-space annotations omitted; model viewports retained")
                continue
            if e.dxf.get("id",1) == 1:
                continue
            if e.dxf.get("view_twist_angle",0) or tuple(e.dxf.get("view_direction_vector",(0,0,1)))!=(0,0,1):
                warnings.add("Rotated/3D viewport omitted")
                continue
            c, vc = e.dxf.center, e.dxf.view_center_point
            w, h, vh = e.dxf.width, e.dxf.height, e.dxf.view_height
            if min(w,h,vh)>0:
                layout.viewports.append(Viewport(c.x-w/2,c.y-h/2,w,h,Point(vc.x,vc.y),h/vh))
        if layout.viewports:
            document.layouts[layout.name] = layout
    document.sync_associative()
    document.filepath = str(filepath)
    document.source_filepath = str(filepath)
    # Keep a bounded copy of the original interchange file inside the native
    # document so a later .pycad save can be reopened without depending on the
    # original path.  Large source drawings remain path-linked and are called
    # out in the import report rather than making the project unbounded.
    try:
        with open(filepath, "rb") as source_stream:
            raw_source = source_stream.read(MAX_SOURCE_BYTES + 1)
        if len(raw_source) <= MAX_SOURCE_BYTES:
            document.source_archive = {
                "filename": os.path.basename(str(filepath)),
                "sha256": hashlib.sha256(raw_source).hexdigest(),
                "data_base64": base64.b64encode(raw_source).decode("ascii"),
            }
        else:
            warnings.add("Original source was not embedded because it exceeds 16 MiB")
    except (OSError, TypeError):
        warnings.add("Original source could not be embedded")
    document.import_warnings = sorted(warnings)
    document.mark_saved()
    return document


class DWGSupportError(Exception):
    """Raised when a DWG reader or the optional DWG export converter is unavailable."""
    pass


def _require_odafc():
    from ezdxf.addons import odafc
    if not odafc.is_installed():
        raise DWGSupportError(
            "DWG export requires a separately installed ODA File Converter. The bundled "
            "LibreDWG reader opens DWG files; it does not provide DWG export. Save as .pycad or DXF, "
            "or install/configure ODA File Converter under its own terms for DWG export. "
            "See https://www.opendesign.com/guestfiles/oda_file_converter")
    return odafc


def import_dwg(filepath: str, mode=None) -> Document:
    import tempfile
    from . import dwg_support, dwg_native
    selected = mode or dwg_native.requested_mode()
    if selected not in dwg_native.MODES:
        raise ValueError('Unknown DWG import mode')
    fallback = ''
    if selected != 'compatibility':
        try:
            return dwg_native.read_direct(filepath)
        except (DWGSupportError, dwg_native.DirectUnsupported) as ex:
            if selected == 'direct': raise
            fallback = 'Direct DWG reader used compatibility fallback: ' + str(ex)
    with tempfile.TemporaryDirectory(prefix="pycad-dwg-api-") as directory:
        converted = dwg_support.convert_sync(filepath, directory)
        document = import_dxf(str(converted), original_source=str(filepath))
        document.import_warnings = sorted(set(document.import_warnings + [dwg_support.NOTE] + ([fallback] if fallback else [])))
        return document


def export_dwg(document: Document, filepath: str):
    from .dwg_native import export_r2000, tool_path
    try:
        tool_path('dwgwrite')
    except DWGSupportError:
        odafc = _require_odafc()
        doc = _build_ezdxf_doc(document)
        atomic_write(filepath, lambda path: odafc.export_dwg(doc, path, replace=True))
    else:
        export_r2000(document, filepath)


def import_any(filepath: str) -> Document:
    """Dispatches to LibreDWG import or plain DXF based on the file extension -
    the single entry point main_window.py's Open should call."""
    filepath = str(filepath)
    if filepath.lower().endswith(".pycad"):
        from .native_io import load_project
        return load_project(filepath)
    if filepath.lower().endswith(".dwg"):
        return import_dwg(filepath)
    return import_dxf(filepath)


def export_any(document: Document, filepath: str):
    filepath = str(filepath)
    suffix = os.path.splitext(filepath)[1].lower()
    if suffix == ".pycad":
        from .native_io import save_project
        save_project(document, filepath)
    elif suffix in (".dxf", ".dwg"):
        if document.import_warnings and document.source_filepath and os.path.abspath(filepath) == os.path.abspath(document.source_filepath):
            raise ValueError("This import omitted or approximated content. Save to a new file to protect the source drawing.")
        (export_dwg if suffix == ".dwg" else export_dxf)(document, filepath)
    else:
        raise ValueError("Use .pycad, .dxf or .dwg as the file extension")


def export_warnings(document):
    warnings = list(document.import_warnings)
    if document.underlays:
        warnings.append('Embedded PDF/image underlays are omitted from DXF/DWG; save .pycad or plot PDF to retain them.')
    from .units import DEFAULT_SETTINGS as UNIT_DEFAULTS
    if document.unit_settings != UNIT_DEFAULTS:
        warnings.append("Custom length/angle display formats and precision require native .pycad; DXF/DWG retains drawing units but not these display settings.")
    if document.constraints:
        warnings.append("Persistent constraints are not exported to DXF/DWG; save .pycad to retain driving relationships.")
    all_entities = document.entities + [e for b in document.blocks.values() for e in b.entities]
    if any(e.kind == 'TEXT' for e in all_entities):
        warnings.append('Text font families are stored as DXF style metadata; fonts are not embedded and receiving programs may substitute them. Width/oblique multiline text becomes individual TEXT rows.')
    if any(e.kind == 'MLEADER' for e in all_entities):
        warnings.append('Multileaders become LINE/SOLID/TEXT graphics; styles and branch editing require .pycad.')
    if any(isinstance(e, DimensionEntity) for e in all_entities):
        warnings.append("Dimensions become LINE/TEXT graphics; editable dimensions and associations require .pycad.")
    if any(isinstance(e, SplineEntity) for e in all_entities):
        warnings.append("Spline interpolation may differ in other CAD programs.")
    if any(isinstance(e, BlockReferenceEntity) and e.clip_boundary for e in all_entities):
        warnings.append("DXF export does not retain reference clipping.")
    if any(b.is_xref for b in document.blocks.values()):
        warnings.append("Xrefs are embedded as blocks; external links require .pycad.")
    if any(isinstance(e, HatchEntity) and e.source_entity_id for e in all_entities):
        warnings.append("Hatch source associations require .pycad.")
    return sorted(set(warnings))
