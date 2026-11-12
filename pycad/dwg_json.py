"""Conservative LibreDWG JSON -> in-memory entity adapter (no DXF file).

Unsupported structures reject the whole direct attempt; Auto can then use the
established compatibility importer. Never silently accept a partial direct map.
"""
import json
import math
from pathlib import Path

import ezdxf
from .dwg_native import DirectUnsupported


def handle(value):
    if not isinstance(value, list) or not value:
        return 0
    # HREF includes absolute_ref as fourth item; object handles have three.
    return int(value[3] if len(value) >= 4 else value[-1])


def color_attributes(value, layer=False):
    if not isinstance(value,dict): return {'color':int(value)}
    raw=value.get('rgb',0)
    rgb=int(raw,16) if isinstance(raw,str) else int(raw)
    flags=int(value.get('flag',0))
    if flags & 0x60:
        raise DirectUnsupported('DWG color-book/transparency data requires compatibility import')
    index=int(value.get('index',0))
    if layer and rgb >> 24 == 0xc3:
        index=index if 0<abs(index)<256 else rgb & 255
    result={'color':index}
    if (layer and rgb >> 24 == 0xc2) or (not layer and flags & 0x80):
        result['true_color']=rgb & 0xffffff
    return result


def import_json(path, original_source):
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        return from_data(data, original_source)
    except DirectUnsupported:
        raise
    except (KeyError, TypeError, ValueError, IndexError, AttributeError) as ex:
        raise DirectUnsupported('Direct DWG data could not be mapped: ' + str(ex)[:300]) from ex


def from_data(data, original_source):
    from .dxf_io import _document_from_ezdxf_doc
    objects = data['OBJECTS']
    if not isinstance(objects, list):
        raise DirectUnsupported('Missing DWG object table')
    by_handle = {handle(o.get('handle')):o for o in objects}
    doc = ezdxf.new('R2018')
    header = data.get('HEADER', {})
    doc.units = int(header.get('INSUNITS', 0))
    doc.header['$LTSCALE'] = float(header.get('LTSCALE', 1))

    def ref_name(record, key, default):
        target = by_handle.get(handle(record.get(key)))
        if not target:
            if handle(record.get(key)):
                raise DirectUnsupported('Unresolved DWG ' + key + ' reference')
            return default
        return target.get('name', default)

    for o in objects:
        kind = o.get('object')
        if kind == 'GROUP' and o.get('num_groups', len(o.get('groups', []))):
            raise DirectUnsupported('DWG groups require compatibility import')
        if kind != 'LAYER':
            continue
        name = o['name']
        entry = doc.layers.get(name) if name in doc.layers else doc.layers.new(name)
        for key,value in color_attributes(o.get('color',7),layer=True).items():
            setattr(entry.dxf,key,value)
        flag = int(o.get('flag0', 16))
        entry.dxf.flags = (flag & 1) | (4 if flag & 8 else 0)
        entry.dxf.plot = int(bool(flag & 16))
        if flag & 2: entry.off()
        lt = ref_name(o, 'ltype', 'Continuous')
        if lt.upper() != 'CONTINUOUS':
            raise DirectUnsupported('DWG layer linetypes require compatibility import')
        if o.get('frozen'): entry.freeze()
        if o.get('locked'): entry.lock()
        if o.get('off'): entry.off()
        if 'plotflag' in o: entry.dxf.plot = int(bool(o['plotflag']))

    blocks = {}
    membership = {}
    for o in objects:
        if o.get('object') != 'BLOCK_HEADER':
            continue
        name = o['name']
        key = handle(o.get('handle'))
        if name.upper() == '*MODEL_SPACE':
            blocks[key] = doc.modelspace()
        elif name.upper().startswith('*PAPER_SPACE'):
            blocks[key] = None
        else:
            if o.get('xref_pname') or o.get('blkisxref') or o.get('is_xref_dep'):
                raise DirectUnsupported('DWG external references require compatibility import')
            blocks[key] = doc.blocks.new(name, base_point=o.get('base_pt', [0,0,0]))
        refs = o.get('entities', [])
        for ref in refs:
            membership[handle(ref)] = key
        first, last = handle(o.get('first_entity')), handle(o.get('last_entity'))
        seen = set()
        while first:
            if first in seen or first not in by_handle:
                raise DirectUnsupported('Broken DWG block entity chain')
            seen.add(first); membership[first] = key
            if first == last: break
            record = by_handle[first]
            first = handle(record.get('next_entity')) or (first+1 if record.get('nolinks') else 0)
        if last and last not in seen and not refs:
            raise DirectUnsupported('Incomplete DWG block entity chain')

    entities = [o for o in objects if 'entity' in o]
    supported = {'LINE','POINT','CIRCLE','ARC','ELLIPSE','LWPOLYLINE','TEXT','MTEXT','INSERT','RAY','XLINE','HATCH','SOLID','SPLINE'}
    unsupported = sorted({o['entity'] for o in entities} - supported - {'BLOCK','ENDBLK'})
    if unsupported:
        raise DirectUnsupported('DWG objects require compatibility import: ' + ', '.join(unsupported))
    count = 0
    notices = []
    for o in entities:
        kind = o['entity']
        if kind in ('BLOCK','ENDBLK'):
            continue
        owner = handle(o.get('ownerhandle')) or membership.get(handle(o.get('handle')),0)
        target = blocks.get(owner)
        # R2000 model/paper-space entities can use entmode in place of owner.
        if not owner and int(o.get('entmode', 0)) == 2:
            target = doc.modelspace()
        if target is None:
            raise DirectUnsupported('DWG paper-space or unresolved entity ownership requires compatibility import')
        if o.get('eed') or o.get('reactors') or o.get('xdicobjhandle') and handle(o['xdicobjhandle']):
            raise DirectUnsupported('DWG entity application metadata requires compatibility import')
        attrs = {'layer':ref_name(o,'layer','0')}
        if int(o.get('ltype_flags',0)) not in (0,1,2) or o.get('invisible'):
            raise DirectUnsupported('DWG visibility or linetype overrides require compatibility import')
        attrs['linetype'] = {0:'BYLAYER',1:'BYBLOCK',2:'Continuous'}[int(o.get('ltype_flags',0))]
        attrs['ltscale'] = o.get('ltype_scale',1)
        extrusion = o.get('extrusion', [0,0,1])
        if tuple(extrusion) != (0,0,1):
            raise DirectUnsupported('Non-XY DWG geometry requires compatibility import')
        attrs.update(color_attributes(o.get('color',256)))
        if kind == 'LINE':
            target.add_line(o['start'], o['end'], dxfattribs=attrs)
        elif kind == 'POINT':
            target.add_point(o.get('point', [o.get('x',0),o.get('y',0),o.get('z',0)]), dxfattribs=attrs)
        elif kind == 'CIRCLE':
            target.add_circle(o['center'], o['radius'], dxfattribs=attrs)
        elif kind == 'ARC':
            target.add_arc(o['center'], o['radius'], math.degrees(o['start_angle']), math.degrees(o['end_angle']), dxfattribs=attrs)
        elif kind == 'ELLIPSE':
            if abs(o.get('start_angle',0))>1e-9 or abs(o.get('end_angle',2*math.pi)-2*math.pi)>1e-9:
                raise DirectUnsupported('Partial DWG ellipse requires compatibility import')
            target.add_ellipse(o['center'], o['sm_axis'], o['axis_ratio'], dxfattribs=attrs)
        elif kind in ('RAY','XLINE'):
            getattr(target, 'add_' + kind.lower())(o['point'], o['vector'], dxfattribs=attrs)
        elif kind == 'LWPOLYLINE':
            points = o['points']; bulges = o.get('bulges', [])
            if o.get('widths') or o.get('const_width', 0):
                notices.append('DWG polyline widths are displayed as centerlines, as in compatibility import')
            attrs['elevation'] = o.get('elevation', 0)
            target.add_lwpolyline([(p[0],p[1],bulges[i] if i<len(bulges) else 0) for i,p in enumerate(points)],
                                  format='xyb',close=bool(o.get('flag',0)&512),dxfattribs=attrs)
        elif kind == 'TEXT':
            if o.get('horiz_alignment',0) or o.get('vert_alignment',0):
                raise DirectUnsupported('Aligned DWG text requires compatibility import')
            target.add_text(o['text_value'], dxfattribs={**attrs,'insert':o['ins_pt'],'height':o['height'],
                            'rotation':math.degrees(o.get('rotation',0)), 'width':o.get('width_factor',1),
                            'oblique':math.degrees(o.get('oblique_angle',0))})
        elif kind == 'MTEXT':
            target.add_mtext(o['text'],dxfattribs={**attrs,'insert':o['ins_pt'],'char_height':o['text_height'],
                'width':o.get('rect_width',0),'attachment_point':o.get('attachment',1),'text_direction':o.get('x_axis_dir',[1,0,0])})
        elif kind == 'INSERT':
            if o.get('has_attribs'):
                raise DirectUnsupported('Attributed DWG block requires compatibility import')
            name = ref_name(o, 'block_header', '')
            if not name or name not in doc.blocks:
                raise DirectUnsupported('Missing DWG block definition')
            scale = o.get('scale',[1,1,1])
            target.add_blockref(name,o['ins_pt'],dxfattribs={**attrs,'xscale':scale[0],'yscale':scale[1],
                               'zscale':scale[2],'rotation':math.degrees(o.get('rotation',0))})
        elif kind == 'SPLINE':
            flags=(1 if o.get('closed_b') else 0) | (2 if o.get('periodic') else 0)
            spline=target.new_entity('SPLINE',dxfattribs={**attrs,'degree':o['degree'],'flags':flags})
            if o.get('fit_pts'):spline.fit_points=o['fit_pts']
            elif o.get('ctrl_pts'):
                points=o['ctrl_pts'];spline.control_points=[(p['x'],p['y'],p['z']) for p in points]
                spline.knots=o['knots']
                weights=[p.get('w',1) for p in points]
                if any(abs(w-1)>1e-12 for w in weights):spline.weights=weights;spline.dxf.flags|=4
            else:raise DirectUnsupported('DWG spline has no supported fit/control points')
        elif kind == 'HATCH':
            _hatch(target, o, attrs)
        elif kind == 'SOLID':
            target.add_solid([o['corner'+str(i)] for i in (1,2,3,4)],dxfattribs=attrs)
        count += 1
    document = _document_from_ezdxf_doc(doc, original_source)
    document.import_warnings = sorted(set(document.import_warnings + notices + [
        f'DWG direct reader: {count} source entities mapped in memory without an intermediate DXF file. '
        'This is a supported 2D drawing view, not a lossless DWG database. Original source unchanged.']))
    return document


def _hatch(target, o, attrs):
    if o.get('is_gradient_fill') or o.get('num_colors',0):
        raise DirectUnsupported('DWG gradient hatch requires compatibility import')
    hatch = target.add_hatch(dxfattribs=attrs)
    hatch.dxf.hatch_style = o.get('style',0)
    hatch.dxf.elevation = (0,0,o.get('elevation',0))
    if o.get('is_solid_fill'):
        hatch.set_solid_fill()
    else:
        definition=[]
        for line in o.get('deflines',[]):
            definition.append([math.degrees(line['angle']),line['pt0'],line['offset'],line.get('dashes',[])])
        if not definition:
            raise DirectUnsupported('DWG hatch pattern definition is unavailable')
        angle=math.degrees(o.get('angle',0));scale=o.get('scale_spacing',1)
        # DWG deflines are already transformed; apply inverse before ezdxf setter.
        from ezdxf.tools.pattern import scale_pattern
        hatch.set_pattern_fill(o['name'],scale=scale,angle=angle,
                               definition=scale_pattern(definition,1/scale,-angle))
    paths=o['paths']
    if not paths: raise DirectUnsupported('DWG hatch has no boundary')
    for path in paths:
        flag=path['flag']
        if flag & 2:
            points=path['polyline_paths']
            hatch.paths.add_polyline_path([(p['point'][0],p['point'][1],p.get('bulge',0)) for p in points],
                                          is_closed=bool(path.get('closed',True)),flags=flag)
        else:
            edge = hatch.paths.add_edge_path(flags=flag)
            for segment in path['segs']:
                kind = segment['curve_type']
                if kind == 1:
                    edge.add_line(segment['first_endpoint'],segment['second_endpoint'])
                elif kind == 2:
                    edge.add_arc(segment['center'],segment['radius'],math.degrees(segment['start_angle']),
                                 math.degrees(segment['end_angle']),ccw=bool(segment['is_ccw']))
                else:
                    raise DirectUnsupported('DWG elliptical/spline hatch edges require compatibility import')
