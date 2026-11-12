"""Small uniform-grid spatial index for interactive CAD picking and snaps.

The drawing model remains the source of truth. This index is a disposable
acceleration cache keyed by entity identity, so native files never depend on
its contents and undo/redo can invalidate it safely.
"""

import math
from collections import defaultdict

from .tolerance import bounds_overlap


class SpatialIndex:
    def __init__(self, cell_size=None):
        self.adaptive = cell_size is None
        cell_size = 100.0 if cell_size is None else cell_size
        if not math.isfinite(cell_size) or cell_size <= 0:
            raise ValueError("Spatial index cell size must be positive")
        self.cell_size = float(cell_size)
        self._cells = defaultdict(set)
        self._records = {}
        self._order = {}
        self._next_order = 0
        self._oversized = set()
        self._dirty = True

    def invalidate(self):
        self._dirty = True

    def clear(self):
        self._cells.clear()
        self._records.clear()
        self._order.clear()
        self._next_order = 0
        self._oversized.clear()
        self._dirty = False

    def rebuild(self, entities):
        for unused in self.rebuild_iter(entities):pass

    def rebuild_iter(self, entities):
        if self.adaptive and len(entities)>32:
            # Robust sampling sizes cells in drawing units, including metres
            # and tiny imported geometry. Ignore outlier coordinates.
            sample=[e.bbox() for e in entities[::max(1,len(entities)//512)]]
            xs=sorted((b[0]+b[2])/2 for b in sample)
            ys=sorted((b[1]+b[3])/2 for b in sample)
            lo,hi=int(len(sample)*.02),max(0,int(len(sample)*.98)-1)
            width,height=xs[hi]-xs[lo],ys[hi]-ys[lo]
            lengths=sorted(max(b[2]-b[0],b[3]-b[1]) for b in sample)
            step=(math.sqrt(width*height/len(entities))*4 if width*height>0
                  else max(width,height)/len(entities)*8)
            self.cell_size=max(1e-9,step,lengths[len(lengths)//2])
        self.clear()
        self._dirty = True
        for i,entity in enumerate(entities):
            self.insert(entity)
            if i%128==127:yield None
        self._dirty = False

    def _cell_range(self, bbox):
        x0, y0, x1, y1 = bbox
        return (
            range(math.floor(x0 / self.cell_size), math.floor(x1 / self.cell_size) + 1),
            range(math.floor(y0 / self.cell_size), math.floor(y1 / self.cell_size) + 1),
        )

    def insert(self, entity):
        bbox = tuple(float(value) for value in entity.bbox())
        if not all(math.isfinite(value) for value in bbox):
            return
        self._records[id(entity)] = (entity, bbox)
        if id(entity) not in self._order:
            self._order[id(entity)] = self._next_order
            self._next_order += 1
        xs, ys = self._cell_range(bbox)
        if len(xs)*len(ys)>4096:
            self._oversized.add(id(entity))
            return
        for ix in xs:
            for iy in ys:
                self._cells[(ix, iy)].add(id(entity))

    def remove(self, entity):
        record = self._records.pop(id(entity), None)
        self._order.pop(id(entity), None)
        if record is None:
            return
        if id(entity) in self._oversized:
            self._oversized.discard(id(entity))
            return
        xs, ys = self._cell_range(record[1])
        for ix in xs:
            for iy in ys:
                bucket = self._cells.get((ix, iy))
                if bucket is not None:
                    bucket.discard(id(entity))
                    if not bucket:
                        self._cells.pop((ix, iy), None)

    def query(self, bbox):
        if self._dirty:
            raise RuntimeError("Spatial index must be rebuilt before querying")
        candidates = set(self._oversized)
        xs, ys = self._cell_range(bbox)
        if len(xs)*len(ys)>4096:
            return [record[0] for record in self._records.values() if bounds_overlap(record[1],bbox)]
        for ix in xs:
            for iy in ys:
                candidates.update(self._cells.get((ix, iy), ()))
        return [
            record[0]
            for key in sorted(candidates, key=self._order.__getitem__)
            for record in [self._records[key]]
            if bounds_overlap(record[1], bbox)
        ]
