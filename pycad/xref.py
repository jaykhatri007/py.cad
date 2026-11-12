"""Resolve DXF reference paths without rewriting their serialized spelling."""

import os
from pathlib import Path, PureWindowsPath
from .geometry import BlockReferenceEntity


def reference_path(document, source):
    if os.name != 'nt' and PureWindowsPath(source).drive:
        raise ValueError('Windows reference path: use XREF → Relink selected to choose its Ubuntu DXF file')
    # Relative paths saved on Windows use backslashes. Keep the serialized
    # spelling intact until a deliberate relink, but resolve on either OS.
    path = Path(source.replace('\\', '/'))
    if not path.is_absolute() and document.filepath:
        path = Path(document.filepath).resolve().parent / path
    return path


def portable_path(document, source):
    path = Path(source).resolve()
    if document.filepath:
        try:
            return Path(os.path.relpath(path, Path(document.filepath).resolve().parent)).as_posix()
        except ValueError:  # different drive on Windows
            pass
    return path.as_posix()


def read_reference(path):
    from .dxf_io import import_any

    doc = import_any(str(path))

    def flatten(entities):
        pending=list(reversed(entities))
        while pending:
            entity=pending.pop()
            if isinstance(entity,BlockReferenceEntity):pending.extend(reversed(entity.resolved_entities))
            else:yield entity.clone()

    return list(flatten(doc.entities)), doc.layers.layers, doc.import_warnings
