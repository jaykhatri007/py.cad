"""
extrude3d.py
Phase 4 (partial): extrude a closed 2D profile (Circle, closed Polyline, or
Rectangle) into a real 3D solid using CadQuery, which wraps genuine
OpenCASCADE (OCP) B-rep geometry - not a mesh approximation - and export it
to STEP or STL.

In v15, model3d.py persists independent extrusion profiles and view3d.py
provides software-rendered model inspection. This module remains the exact
CadQuery/OCP solid-regeneration and STEP/STL export boundary.
"""
import math
from .geometry import CircleEntity, PolylineEntity, RectangleEntity


class ExtrudeError(Exception):
    pass


def is_extrudable(entity) -> bool:
    """Whether `entity` is a closed 2D profile we know how to extrude."""
    if isinstance(entity, CircleEntity):
        return True
    if isinstance(entity, PolylineEntity):
        return entity.closed and len(entity.points) >= 3
    return False


def extrude_to_solid(entity, height: float):
    """Build a CadQuery solid from a closed 2D profile. Raises ExtrudeError
    with a human-readable message on failure (degenerate profile, etc.)."""
    import cadquery as cq

    if not math.isfinite(height) or height == 0:
        raise ExtrudeError("Extrude height must be finite and nonzero.")

    if isinstance(entity, CircleEntity):
        if not math.isfinite(entity.radius) or entity.radius <= 0:
            raise ExtrudeError("Circle radius must be finite and positive")
        solid = (cq.Workplane("XY")
                 .center(entity.center.x, entity.center.y)
                 .circle(entity.radius)
                 .extrude(height))
        return solid

    if isinstance(entity, PolylineEntity):
        if not entity.closed or len(entity.points) < 3:
            raise ExtrudeError("Only closed polylines/rectangles (3+ points) can be extruded.")
        pts = [(p.x, p.y) for p in entity.points]
        try:
            solid = (cq.Workplane("XY")
                     .polyline(pts)
                     .close()
                     .extrude(height))
        except Exception as ex:
            raise ExtrudeError(f"Could not build a solid from this profile: {ex}")
        return solid

    raise ExtrudeError("This entity type can't be extruded (only circles and closed polylines/rectangles).")


def extrude_and_export(entity, height: float, filepath: str):
    """Extrude `entity` by `height` and export the resulting solid to
    `filepath`. Format is inferred from the extension (.step/.stp/.stl)."""
    import cadquery as cq
    from .native_io import atomic_write
    solid = extrude_to_solid(entity, height)
    try:
        atomic_write(filepath, lambda path: cq.exporters.export(solid, path))
    except Exception as ex:
        raise ExtrudeError(f"Export failed: {ex}")
    return solid
