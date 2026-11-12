"""Native-ID revision comparisons and auditable quantity calculations."""
import copy
from .native_io import entity_to_dict


def compare(before,after):
    a={e.id:entity_to_dict(e) for e in before.entities};b={e.id:entity_to_dict(e) for e in after.entities}
    added=sorted(b.keys()-a.keys());removed=sorted(a.keys()-b.keys());changed=sorted(k for k in a.keys()&b.keys() if a[k]!=b[k])
    # A definition edit affects every native instance referencing that definition.
    def definitions(doc):return {n:dict(entities=[entity_to_dict(e) for e in v.entities],attributes=v.attributes,source=v.source_filepath,source_scale=v.source_scale) for n,v in doc.blocks.items()}
    da,db=definitions(before),definitions(after);definition_changes=sorted(n for n in da.keys()|db.keys() if da.get(n)!=db.get(n))
    changed_set=set(definition_changes)
    while True:
        parents={name for doc in (before,after) for name,b in doc.blocks.items() if any(e.kind=='INSERT' and e.block_name in changed_set for e in b.entities)}
        if parents<=changed_set:break
        changed_set.update(parents)
    definition_changes=sorted(changed_set)
    for e in after.entities:
        if e.id in a and e.kind=='INSERT' and e.block_name in definition_changes and e.id not in changed:changed.append(e.id)
    return dict(added=added,removed=removed,changed=sorted(changed),unchanged=len(a.keys()&b.keys())-len(changed),block_definitions_changed=definition_changes,units_match=before.units==after.units,settings_changed=before.extensions!=after.extensions,matching='Persistent native IDs; independent DXF/DWG imports may have different IDs')


def quantity_rows(doc,synchronize=True):
    from .boq import report
    from .pro_data import settings
    base=report(doc,synchronize=synchronize);rows=[]
    for source in base['items']:
        r=copy.deepcopy(source);adjust=settings(doc).get('quantity_adjustments',{}).get(r['source_id'],dict(deduction=0,waste_percent=base['waste_percent'],reason='Project-wide waste'))
        gross=r['quantity'];deduction=adjust['deduction']
        if deduction>gross+1e-9:raise ValueError('Deduction exceeds measured quantity for '+r['source_id'])
        net=max(0,gross-deduction);waste=net*adjust['waste_percent']/100
        r.update(gross_quantity=gross,deduction=deduction,net_quantity=net,waste_quantity=waste,adjusted_quantity=net+waste,adjustment_reason=adjust['reason'],adjusted_cost=None if r['rate'] is None else (net+waste)*r['rate']);rows.append(r)
    return dict(currency=base['currency'],rows=rows,warnings=base['warnings'],unmeasured_ids=base['unmeasured_ids'],note='Per-source waste replaces global waste for that source; no double counting')


def quantity_delta(before,after):
    a,b=quantity_rows(before),quantity_rows(after)
    if before.units!=after.units or a['currency']!=b['currency']:raise ValueError('Revision units and currencies must match')
    def group(report):
        values={}
        for r in report['rows']:
            key=(r['description'],r['material'],r.get('specification',''),r['unit']);v=values.setdefault(key,dict(quantity=0,sources=[]));v['quantity']+=r['adjusted_quantity'];v['sources'].append(r['source_id'])
        return values
    x,y=group(a),group(b);rows=[]
    for key in sorted(x.keys()|y.keys()):
        old=x.get(key,dict(quantity=0,sources=[]));new=y.get(key,dict(quantity=0,sources=[]));rows.append(dict(description=key[0],material=key[1],specification=key[2],unit=key[3],before=old['quantity'],after=new['quantity'],delta=new['quantity']-old['quantity'],before_ids=old['sources'],after_ids=new['sources']))
    return dict(currency=b['currency'],rows=rows,warnings=a['warnings']+b['warnings'])
