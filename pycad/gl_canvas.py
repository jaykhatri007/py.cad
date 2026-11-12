"""Optional accelerated viewport sharing the complete QPainter drawing path.

Qt handles text, hatches, grips, layouts and previews on the same drawing path
as the software renderer. It requires a working desktop OpenGL context; use the
software renderer on offscreen/remote systems. No speed guarantee is made.
"""

import math
from .canvas import CadCanvas
from .geometry import Point


class GLCadCanvas(CadCanvas):
    def __init__(self, document, parent=None):
        super().__init__(document, parent)
        # Kept for scripts using the historical class name. The application
        # now installs a tested PaintSurface through GraphicsController.

    @property
    def gpu_available(self):
        from .graphics_surface import PaintSurface
        return isinstance(self.viewport(), PaintSurface) and self.viewport().isValid()

    @staticmethod
    def _tessellate_circle(center, radius, segments=64):
        return [
            Point(
                center.x + radius * math.cos(2 * math.pi * i / segments),
                center.y + radius * math.sin(2 * math.pi * i / segments),
            )
            for i in range(segments)
        ]

    @staticmethod
    def _tessellate_arc(center, radius, start_angle, end_angle, segments=48):
        span = (end_angle - start_angle) % 360.0
        return [
            Point(
                center.x
                + radius * math.cos(math.radians(start_angle + span * i / segments)),
                center.y
                + radius * math.sin(math.radians(start_angle + span * i / segments)),
            )
            for i in range(segments + 1)
        ]
