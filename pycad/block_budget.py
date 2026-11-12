"""Iterative block-graph validation. No default size or nesting quota."""
from collections import deque
from .geometry import BlockReferenceEntity


def block_order(blocks, references=None):
    """Return dependencies before their users; reject missing/cyclic definitions.

    Kahn's algorithm does not consume Python call-stack depth, and never expands
    instances. Repeated references share one graph edge for ordering purposes.
    """
    references = references or (lambda block:(e.block_name for e in block.entities if isinstance(e,BlockReferenceEntity)))
    dependencies={name:set(references(block)) for name,block in blocks.items()}
    users={name:[] for name in blocks}
    for name, children in dependencies.items():
        for child in children:
            if child not in blocks:raise ValueError('Missing block definition: '+child)
            users[child].append(name)
    remaining={name:len(children) for name,children in dependencies.items()}
    ready=deque(name for name,n in remaining.items() if not n)
    order=[]
    while ready:
        name=ready.popleft();order.append(name)
        for user in users[name]:
            remaining[user]-=1
            if not remaining[user]:ready.append(user)
    if len(order)!=len(blocks):raise ValueError('Cyclic block reference: '+next(name for name,n in remaining.items() if n))
    return order


def check_expansion(blocks, entities, limit=None):
    order=block_order(blocks)
    for entity in entities:
        if isinstance(entity,BlockReferenceEntity) and entity.block_name not in blocks:
            raise ValueError('Missing block definition: '+entity.block_name)
    # Optional caller-supplied work bound is retained for scripting/API callers.
    # Opening, saving and editing do not pass a bound.
    if limit is not None:
        counts={}
        for name in order:
            block=blocks[name]
            counts[name]=sum(bool(s.get('visible',True)) for s in block.attributes)+sum(1+(counts[e.block_name] if isinstance(e,BlockReferenceEntity) else 0) for e in block.entities)
        total=sum(counts.values())+sum(1+(counts[e.block_name] if isinstance(e,BlockReferenceEntity) else 0) for e in entities)
        if total>limit:raise ValueError('Expanded drawing exceeds the caller-supplied display budget')
    return order
