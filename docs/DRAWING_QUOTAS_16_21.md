# Drawing quotas removed — PY.cad 16.21

The application no longer imposes the six drawing quotas from 16.20:

| Previous fixed quota | 16.21 behavior |
|---|---|
| 100 MiB DWG/DXF input or converted DXF | No application byte-size cutoff |
| 100 MiB native file/import-worker result | No application byte-size cutoff when opening or saving |
| 500,000 stored entities | No drawing entity-count cutoff |
| 2,000,000 expanded display allocations | No default expansion-count cutoff |
| 1,000,000 stored vertices | No drawing vertex-count cutoff |
| 32 nested block levels | No application block-depth cutoff |

The drawing layer/block/layout table quota and imported hatch path/vertex quotas are also removed. EXPLODE no longer refuses an operation because it would cross the old entity count. Old numerical constant names remain as infinite compatibility values; application file/import/save paths do not use them to impose quotas. Scripting callers can still deliberately pass a work bound to check_expansion; application opening, saving and editing do not.

## Deep blocks

Block dependency validation uses an iterative graph traversal. Display-tree cloning, deep copying, transformation, bounds, painting, picking and text-cache preparation use explicit stacks rather than recursive descent. This removes the old 32-level truncation and avoids using Python's recursion depth as an implicit block-depth limit in these operations. Missing definitions and circular references are rejected. A circular reference is an invalid infinite dependency, not a large valid drawing.

## What this means in practice

This removes product quotas; it does not create unlimited memory or guarantee that every drawing can be processed. The application and its parsers still load drawing data into memory and create transformed display copies. A heavily branching block graph can expand enormously even from a small source file. Available RAM, storage, CPU time, the operating system, Python, Qt and the DWG reader remain practical limits. An OS out-of-memory termination cannot be guaranteed to recover gracefully. Save work before opening exceptionally large drawings.

Supported data formats, numeric-coordinate ranges, entity semantics and individual tool limits remain. Invalid numbers/records, duplicate IDs, missing references and malformed files remain errors. This change does not add support for otherwise unsupported DWG features or make imports lossless. Existing conversion/parser timeouts, cancellation controls, bounded hatch preview rendering and clipboard/underlay limits remain operational controls. The optional embedded copy of the original source remains limited to 16 MiB; larger originals are not embedded, but their drawing content can still be opened and edited. Those originals should be kept separately.

## Verification scope

Regressions cover real native opening/saving above 100 MiB, DXF opening above 100 MiB, DWG source staging/output checks above 100 MiB, 500,001 entity records, 1,000,001 vertices, a 5,000-node dependency chain, an expansion graph exceeding the former display quota without allocating that expansion, native round-tripping beyond 32 nested blocks, and 1,500-level display-tree operations. Invalid numeric data, missing references and cycles remain rejected.

The large DXF byte-size case uses valid comment records; the native size case uses real saved text entities as well as a whitespace-padded native file. These are controlled regression inputs, not representative benchmarks for arbitrary large drawings. The DWG byte-size test validates staging/output handling, not conversion of a real 100 MiB DWG. The user's particular drawing and native Windows/macOS/GPU behavior remain unverified.

Close the old version, install the matching 16.21 package and launch its shortcut. Existing 16.20 drawing and editing features are retained.
