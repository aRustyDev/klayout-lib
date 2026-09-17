"""Probe pads -- contact regions drawn on their own layer.

A pad is not part of the resistor. It is usually a thicker, far more conductive
film landing on top of the resistive one, so it belongs on its own mask layer
and contributes contact resistance rather than sheet squares. That separation
is enforced by Resistor.build_cell, which refuses to draw a pad without being
told which layer to put it on.

All four corners of a pad are convex, so both shaped styles go through
rounded_corners' outer radius; the inner radius stays zero.
"""

try:  # KLayout runtime
    import pya  # type: ignore
except ImportError:  # pragma: no cover - plain Python import path
    import klayout.db as pya  # type: ignore

from dataclasses import dataclass, field
from typing import List, Optional

from .corners import Corner, CornerSpec
from .corners import tag as corner_tag
from .units import tag, um


@dataclass(frozen=True)
class Pad:
    """A contact pad, centred on a terminal.

    size_um is the full width; height_um defaults to it, giving a square pad.
    The corner spec's radius_um (ROUNDED) or chamfer_um (TAPERED) must fit
    inside half the smaller dimension, or the treatment would consume the pad.
    """
    size_um: float
    height_um: Optional[float] = None
    corner: CornerSpec = field(default_factory=CornerSpec)

    def __post_init__(self):
        if self.size_um <= 0:
            raise ValueError("size_um must be positive")
        if self.height_um is not None and self.height_um <= 0:
            raise ValueError("height_um must be positive")
        half = min(self.size_um, self.height()) / 2.0
        if self.corner.style is Corner.ROUNDED and self.corner.radius_um > half:
            raise ValueError(
                f"corner radius {self.corner.radius_um} exceeds half the pad "
                f"({half}); the rounding would consume the pad")
        if self.corner.style is Corner.TAPERED and self.corner.chamfer_um > half:
            raise ValueError(
                f"chamfer {self.corner.chamfer_um} exceeds half the pad "
                f"({half}); the cut would consume the pad")

    def height(self) -> float:
        """Pad height in micrometres -- size_um unless overridden."""
        return self.size_um if self.height_um is None else self.height_um

    def tag(self) -> str:
        """Short marker for cell names, e.g. ``PAD40TP5``."""
        size = tag(self.size_um)
        if self.height_um is not None:
            size = f"{size}x{tag(self.height_um)}"
        return f"PAD{size}{corner_tag(self.corner)}"

    def box_at(self, terminal) -> "pya.Box":
        """The unshaped pad box, centred on a terminal box."""
        centre = terminal.center()
        half_w = um(self.size_um) // 2
        half_h = um(self.height()) // 2
        return pya.Box(centre.x - half_w, centre.y - half_h,
                       centre.x + half_w, centre.y + half_h)

    def polygons_at(self, terminal) -> List["pya.Polygon"]:
        """Pad polygons centred on a terminal box, corner style applied."""
        region = pya.Region()
        region.insert(self.box_at(terminal))
        region.merge()
        if self.corner.style is not Corner.SQUARE:
            # Every pad corner is convex, so only the outer radius is used.
            n = 8 if self.corner.style is Corner.TAPERED else self.corner.arc_points
            region = region.rounded_corners(0, um(self.corner.extent_um()), n)
        return list(region.each())
