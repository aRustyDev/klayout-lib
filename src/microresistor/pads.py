"""Probe pads -- contact regions drawn on their own layer.

A pad is not part of the resistor. It is usually a thicker, far more conductive
film landing on top of the resistive one, so it belongs on its own mask layer
and contributes contact resistance rather than sheet squares. That separation
is enforced by Resistor.build_cell, which refuses to draw a pad without being
told which layer to put it on.

Two placements:

  offset_um = 0   the pad is centred ON the terminal. Simple, and fine when
                  the device is longer than the pad is wide.
  offset_um > 0   the pad sits OUTSIDE the device, joined to the terminal by a
                  lead. This is how a real test structure gets a 100 um probe
                  pad onto a 10 um resistor -- centring cannot, because the two
                  pads would meet in the middle and short it out.

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
    """A contact pad.

    size_um is the full width; height_um defaults to it, giving a square pad.
    The corner spec's radius_um (ROUNDED) or chamfer_um (TAPERED) must fit
    inside half the smaller dimension, or the treatment would consume the pad.

    offset_um is the clear gap between the terminal's outer edge and the pad's
    near edge. Zero centres the pad on the terminal; anything positive pushes
    it outward and draws a lead back to the terminal.
    """
    size_um: float
    height_um: Optional[float] = None
    corner: CornerSpec = field(default_factory=CornerSpec)
    offset_um: float = 0.0
    lead_width_um: Optional[float] = None

    def __post_init__(self):
        if self.size_um <= 0:
            raise ValueError("size_um must be positive")
        if self.height_um is not None and self.height_um <= 0:
            raise ValueError("height_um must be positive")
        if self.offset_um < 0:
            raise ValueError("offset_um cannot be negative")
        if self.lead_width_um is not None and self.lead_width_um <= 0:
            raise ValueError("lead_width_um must be positive")
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

    @property
    def is_offset(self) -> bool:
        return self.offset_um > 0

    def tag(self) -> str:
        """Short marker for cell names, e.g. ``PAD40TP5O60``."""
        size = tag(self.size_um)
        if self.height_um is not None:
            size = f"{size}x{tag(self.height_um)}"
        out = f"PAD{size}{corner_tag(self.corner)}"
        if self.is_offset:
            out += f"O{tag(self.offset_um)}"
        return out

    # -- geometry ---------------------------------------------------------

    def _shaped(self, box) -> "pya.Region":
        """The pad box with its corner style applied."""
        region = pya.Region()
        region.insert(box)
        region.merge()
        if self.corner.style is not Corner.SQUARE:
            # Every pad corner is convex, so only the outer radius is used.
            n = 8 if self.corner.style is Corner.TAPERED else self.corner.arc_points
            region = region.rounded_corners(0, um(self.corner.extent_um()), n)
        return region

    def box_at(self, terminal, direction=None) -> "pya.Box":
        """The unshaped pad box for a terminal.

        Centred on the terminal when not offset; pushed out along ``direction``
        by offset_um beyond the terminal's outer edge when it is.
        """
        half_w = um(self.size_um) // 2
        half_h = um(self.height()) // 2
        centre = terminal.center()
        if not self.is_offset or direction is None:
            return pya.Box(centre.x - half_w, centre.y - half_h,
                           centre.x + half_w, centre.y + half_h)

        dx, dy = direction
        gap = um(self.offset_um)
        if dx:
            edge = terminal.right if dx > 0 else terminal.left
            cx = edge + dx * (gap + half_w)
            cy = centre.y
        else:
            edge = terminal.top if dy > 0 else terminal.bottom
            cx = centre.x
            cy = edge + dy * (gap + half_h)
        return pya.Box(cx - half_w, cy - half_h, cx + half_w, cy + half_h)

    def lead_at(self, terminal, direction) -> Optional["pya.Box"]:
        """The lead joining an offset pad back to its terminal.

        Spans from the terminal's INNER edge to the pad, so it covers the whole
        terminal and the contact cannot depend on an exact edge coincidence.
        Returns None when the pad is centred and needs no lead.
        """
        if not self.is_offset or direction is None:
            return None
        dx, dy = direction
        pad = self.box_at(terminal, direction)
        default = (terminal.height() if dx else terminal.width()) / 1000.0
        half_lead = um(self.lead_width_um
                       if self.lead_width_um is not None else default) // 2
        centre = terminal.center()
        if dx:
            lo, hi = (terminal.left, pad.right) if dx > 0 else (pad.left,
                                                                terminal.right)
            return pya.Box(lo, centre.y - half_lead, hi, centre.y + half_lead)
        lo, hi = (terminal.bottom, pad.top) if dy > 0 else (pad.bottom,
                                                            terminal.top)
        return pya.Box(centre.x - half_lead, lo, centre.x + half_lead, hi)

    def polygons_at(self, terminal, direction=None) -> List["pya.Polygon"]:
        """Pad (and lead, if offset) for one terminal.

        The lead is merged with the pad, so the result is one polygon per
        terminal rather than two touching ones.
        """
        region = self._shaped(self.box_at(terminal, direction))
        lead = self.lead_at(terminal, direction)
        if lead is not None:
            region.insert(lead)
            region.merge()
        return list(region.each())
