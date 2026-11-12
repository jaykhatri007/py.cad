"""Shared numerical tolerance helpers for 2D geometry predicates.

CAD drawings routinely mix very large coordinates with near-coincident
vertices. Keeping the policy in one module makes future exact predicates,
offsets, and topology operations agree on what "touching" means.
"""

import math


EPSILON = 1e-9


def is_zero(value, tolerance=EPSILON):
    """Return whether ``value`` is numerically indistinguishable from zero."""
    return abs(value) <= tolerance


def is_close(first, second, tolerance=EPSILON):
    """Return whether two scalar values are equal within the CAD tolerance."""
    return abs(first - second) <= tolerance


def clamp(value, low=0.0, high=1.0):
    """Clamp a scalar to an interval without changing values already inside."""
    return max(low, min(high, value))


def bounds_overlap(first, second, tolerance=EPSILON):
    """Return whether two ``(xmin, ymin, xmax, ymax)`` boxes overlap."""
    return not (
        first[2] < second[0] - tolerance or
        first[0] > second[2] + tolerance or
        first[3] < second[1] - tolerance or
        first[1] > second[3] + tolerance
    )


def finite(value):
    """Small readability helper for geometry input validation."""
    return math.isfinite(value)
