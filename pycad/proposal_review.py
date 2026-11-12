"""Explain geometric/quantity impacts of an already validated staged proposal."""
from collections import Counter
from .native_io import entity_to_dict


def impact_report(before,after):
    a={e.id:entity_to_dict(e) for e in before.entities};b={e.id:entity_to_dict(e) for e in after.entities}
    result=dict(added=len(b.keys()-a.keys()),removed=len(a.keys()-b.keys()),changed=sum(a[k]!=b[k] for k in a.keys()&b.keys()),
                kinds_before=dict(Counter(e.kind for e in before.entities)),kinds_after=dict(Counter(e.kind for e in after.entities)),units=after.units,
                note='Quantity impacts use current tags, model data and user-entered rates; unmeasured/unpriced objects are not a complete estimate.')
    try:
        from .boq import report
        x,y=report(before),report(after)
        result['quantities']=dict(priced_subtotal_before=x['priced_total'],priced_subtotal_after=y['priced_total'],currency=y['currency'],unpriced_after=y['unpriced_items'],unmeasured_after=len(y['unmeasured_ids']))
    except ValueError as ex:result['quantities_unavailable']=str(ex)
    return result
