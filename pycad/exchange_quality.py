"""Conservative structural and extent comparisons, not DWG fidelity certification."""
import collections
import math


def compare_documents(first,second):
    def describe(doc):
        boxes=[e.bbox() for e in doc.entities]
        return dict(kinds=dict(collections.Counter(e.kind for e in doc.entities)),
                    extents=[min(b[0] for b in boxes),min(b[1] for b in boxes),max(b[2] for b in boxes),max(b[3] for b in boxes)] if boxes else None,
                    units=doc.units,blocks=len(doc.blocks),sheets=len(doc.layouts),warnings=list(doc.import_warnings))
    a,b=describe(first),describe(second)
    return dict(first=a,second=b,kinds_equal=a['kinds']==b['kinds'],units_equal=a['units']==b['units'],
                extents_equal=close_extents(a['extents'],b['extents']),note='Counts and extents cannot prove lossless object, styling or application-data preservation.')


def close_extents(a,b):
    if a is None or b is None:return a==b
    return all(math.isclose(x,y,rel_tol=1e-7,abs_tol=1e-6) for x,y in zip(a,b))


def verify_export_extents(expected,recovered):
    from ezdxf import bbox
    def bounds(drawing):
        box=bbox.extents(drawing.modelspace())
        return [box.extmin.x,box.extmin.y,box.extmax.x,box.extmax.y] if box.has_data else None
    if not close_extents(bounds(expected),bounds(recovered)):
        raise ValueError('DWG export model extents changed during read-back; destination unchanged. Save .pycad or DXF instead.')
