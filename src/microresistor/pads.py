"""Probe pads -- contact regions drawn on their own layer.

A pad is not part of the resistor. It is usually a thicker, far more conductive
film landing on top of the resistive one, so it belongs on its own mask layer
and contributes contact resistance rather than sheet squares. That separation
is enforced by Resistor.build_cell, which refuses to draw a pad without being
told which layer to put it on.

Two placements, chosen by whether the pad has a lead:

  lead = None     the pad OVERLAPS the trace. It is centred on the terminal and
                  contacts it directly, with no strap. Simple, and the right
                  answer whenever the device is longer than the pad is wide.
  lead = Lead(..) the pad sits OUTSIDE the device, joined to the terminal by a
                  strap of the given length and width. This is how a real test
                  structure gets a 100 um probe pad onto a 10 um resistor --
                  an overlapping pad cannot, because the two would meet in the
                  middle and short it out.

The offset lives inside Lead rather than beside it on Pad, which makes the one
invalid combination -- a pad pushed away from the device with nothing joining
it back -- impossible to express.

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
class Lead:
    """A strap joining an offset pad back to its terminal.

    length_um is the clear gap between the terminal's outer edge and the pad's
    near edge -- i.e. how far the pad is pushed away from the device.

    width_um defaults to the terminal's own width, so the strap is as wide as
    the contact it lands on and adds no constriction of its own. Narrow it
    deliberately if you want the lead's resistance to be negligible-but-known,
    or to keep neighbouring devices clear.
    """
    length_um: float
    width_um: Optional[float] = None

    def __post_init__(self):
        if self.length_um <= 0:
            raise ValueError(
                "lead length_um must be positive; a pad with no gap to span "
                "needs no lead at all -- leave Pad.lead as None and the pad "
                "will overlap the trace directly")
        if self.width_um is not None and self.width_um <= 0:
            raise ValueError("lead width_um must be positive")


@dataclass(frozen=True)
class Pad:
    """A contact pad.

    size_um is the full width; height_um defaults to it, giving a square pad.
    The corner spec's radius_um (ROUNDED) or chamfer_um (TAPERED) must fit
    inside half the smaller dimension, or the treatment would consume the pad.

    lead is optional. Without one the pad overlaps the trace, centred on the
    terminal. With one it is pushed clear of the device and strapped back.
    """
    size_um: float
    height_um: Optional[float] = None
    corner: CornerSpec = field(default_factory=CornerSpec)
    lead: Optional[Lead] = None

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

    @property
    def has_lead(self) -> bool:
        """True when the pad is strapped out, False when it overlaps the trace."""
        return self.lead is not None

    def tag(self) -> str:
        """Short marker for cell names, e.g. ``PAD40TP5L30``."""
        size = tag(self.size_um)
        if self.height_um is not None:
            size = f"{size}x{tag(self.height_um)}"
        out = f"PAD{size}{corner_tag(self.corner)}"
        if self.has_lead:
            out += f"L{tag(self.lead.length_um)}"
            if self.lead.width_um is not None:
                out += f"W{tag(self.lead.width_um)}"
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

        Centred on the terminal -- overlapping the trace -- when there is no
        lead; pushed out along ``direction`` past the terminal's outer edge
        when there is.
        """
        half_w = um(self.size_um) // 2
        half_h = um(self.height()) // 2
        centre = terminal.center()
        if not self.has_lead or direction is None:
            return pya.Box(centre.x - half_w, centre.y - half_h,
                           centre.x + half_w, centre.y + half_h)

        dx, dy = direction
        gap = um(self.lead.length_um)
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
        """The strap joining a pad back to its terminal.

        Spans from the terminal's INNER edge to the pad, so it covers the whole
        terminal and the contact cannot depend on an exact edge coincidence.
        Returns None when the pad has no lead and simply overlaps the trace.
        """
        if not self.has_lead or direction is None:
            return None
        dx, dy = direction
        pad = self.box_at(terminal, direction)
        default = (terminal.height() if dx else terminal.width()) / 1000.0
        half_lead = um(self.lead.width_um
                       if self.lead.width_um is not None else default) // 2
        centre = terminal.center()
        if dx:
            lo, hi = (terminal.left, pad.right) if dx > 0 else (pad.left,
                                                                terminal.right)
            return pya.Box(lo, centre.y - half_lead, hi, centre.y + half_lead)
        lo, hi = (terminal.bottom, pad.top) if dy > 0 else (pad.bottom,
                                                            terminal.top)
        return pya.Box(centre.x - half_lead, lo, centre.x + half_lead, hi)

    def polygons_at(self, terminal, direction=None) -> List["pya.Polygon"]:
        """Pad, plus its lead if it has one, for a single terminal.

        Any lead is merged into the pad, so the result is one polygon per
        terminal rather than two that happen to touch.
        """
        region = self._shaped(self.box_at(terminal, direction))
        lead = self.lead_at(terminal, direction)
        if lead is not None:
            region.insert(lead)
            region.merge()
        return list(region.each())
