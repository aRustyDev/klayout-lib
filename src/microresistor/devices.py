"""The device library.

Each device is built in its own convenient local frame. Placement normalises
with cell.bbox(), so no device has to agree with any other about where its
origin sits.

Geometry and layer-independent structure only -- no resistivity, no thickness,
no resistance. Those live in process.py; extraction math lives in extraction.py.
"""

try:  # KLayout runtime
    import pya  # type: ignore
except ImportError:  # pragma: no cover - plain Python import path
    import klayout.db as pya  # type: ignore

from dataclasses import dataclass
from typing import Optional

from .base import Resistor, merged
from .units import tag, um


@dataclass
class StraightBar(Resistor):
    """Uniform bar. Local frame: (0,0) at the bottom-left corner."""
    length_um: float
    width_um: float
    contact_um: Optional[float] = None
    name: str = ""

    def __post_init__(self):
        if self.contact_um is None:
            self.contact_um = min(self.width_um, self.length_um / 4.0)
        if not self.name:
            self.name = f"BAR_L{tag(self.length_um)}_W{tag(self.width_um)}"

    def shapes(self):
        return merged([pya.Box(0, 0, um(self.length_um), um(self.width_um))])

    def terminals(self):
        c, w, L = um(self.contact_um), um(self.width_um), um(self.length_um)
        return [pya.Box(0, 0, c, w), pya.Box(L - c, 0, L, w)]

    def n_squares(self):
        # Drawn geometry only. The measured value will differ by the
        # lithography/lift-off bias: W_eff = W_drawn - dW.
        return self.length_um / self.width_um


@dataclass
class Dogbone(Resistor):
    """Narrow neck with square heads. Heads ARE the contacts.

    There is no separate pad object here: after the merge it is one
    polygon, which is exactly why forcing (Pad, Pad) onto every resistor
    does not work.
    """
    length_um: float          # neck length
    width_um: float           # neck width
    head_um: float            # head is head_um x head_um
    name: str = ""

    def __post_init__(self):
        if self.head_um <= self.width_um:
            raise ValueError("head_um must exceed width_um or it is just a bar")
        if not self.name:
            self.name = (f"DOG_L{tag(self.length_um)}_W{tag(self.width_um)}"
                         f"_H{tag(self.head_um)}")

    def shapes(self):
        hd, L, w = um(self.head_um), um(self.length_um), um(self.width_um)
        y0 = (hd - w) // 2
        return merged([
            pya.Box(0, 0, hd, hd),                       # left head
            pya.Box(hd, y0, hd + L, y0 + w),             # neck
            pya.Box(hd + L, 0, hd + L + hd, hd),         # right head
        ])

    def terminals(self):
        hd, L = um(self.head_um), um(self.length_um)
        return [pya.Box(0, 0, hd, hd), pya.Box(hd + L, 0, hd + L + hd, hd)]

    def n_squares(self):
        # Neck only. The heads contribute an end resistance that is not
        # analytic -- current spreading in the head is a 2-D problem. The
        # point of the dogbone is that the spreading happens where the
        # sheet is wide, so the term is small AND repeatable.
        return self.length_um / self.width_um


@dataclass
class Serpentine(Resistor):
    """Folded trace built from a pya.Path centreline.

    Local frame: first centreline vertex at (0,0). The band extends
    width_um/2 to the left of x=0, so the bbox has a negative left edge.
    Placement normalises this.
    """
    width_um: float
    leg_length_um: float
    n_legs: int
    pitch_um: float
    corner_squares: float = 0.56   # 0.5 in some texts
    name: str = ""

    def __post_init__(self):
        if self.n_legs < 2:
            raise ValueError("a serpentine needs at least 2 legs")
        if self.pitch_um <= self.width_um:
            raise ValueError("pitch_um must exceed width_um or legs touch")
        if not self.name:
            self.name = (f"SRP_W{tag(self.width_um)}_N{self.n_legs}"
                         f"_L{tag(self.leg_length_um)}")

    def centreline(self):
        pts = []
        for i in range(self.n_legs):
            x = i * self.pitch_um
            if i % 2 == 0:
                pts += [(x, 0.0), (x, self.leg_length_um)]
            else:
                pts += [(x, self.leg_length_um), (x, 0.0)]
        return pts

    def path(self):
        pts = [pya.Point(um(x), um(y)) for x, y in self.centreline()]
        # bgn_ext = end_ext = 0: the trace ends flush with the terminal
        # vertices, which keeps the square count consistent with the
        # centreline length.
        return pya.Path(pts, um(self.width_um), 0, 0)

    def shapes(self):
        region = pya.Region()
        region.insert(self.path().polygon())
        region.merge()
        return list(region.each())

    def n_corners(self):
        return 2 * (self.n_legs - 1)

    def centreline_length_um(self):
        return (self.n_legs * self.leg_length_um
                + (self.n_legs - 1) * self.pitch_um)

    def terminals(self):
        pts = self.centreline()
        half = um(self.width_um) // 2
        out = []
        for x, y in (pts[0], pts[-1]):
            cx, cy = um(x), um(y)
            out.append(pya.Box(cx - half, cy - half, cx + half, cy + half))
        return out

    def n_squares(self):
        # A naive centreline_length / W already counts exactly 1.0 squares
        # per bend, because the centreline crosses each W x W corner box
        # over a length of W. Current crowds on the inside of the turn, so
        # the corner is worth less than a square. Swap the counts.
        naive = self.centreline_length_um() / self.width_um
        return naive - self.n_corners() * (1.0 - self.corner_squares)


@dataclass
class GreekCross(Resistor):
    """Van der Pauw cross. A test structure, not a series element.

    Four terminals, no current direction, no centreline, no square count.
    Force 1-3, measure 2-4, and R_s falls out with contact resistance
    cancelled -- which is why n_squares() is None rather than a number.

    The R_s arithmetic itself is extraction, not geometry, so it lives in
    extraction.sheet_resistance_vdp() rather than on this class.
    """
    arm_width_um: float
    arm_length_um: float
    name: str = ""

    def __post_init__(self):
        if not self.name:
            self.name = (f"VDP_W{tag(self.arm_width_um)}"
                         f"_A{tag(self.arm_length_um)}")

    def shapes(self):
        aw, al = um(self.arm_width_um), um(self.arm_length_um)
        span = aw + 2 * al
        return merged([
            pya.Box(0, al, span, al + aw),      # horizontal arm pair
            pya.Box(al, 0, al + aw, span),      # vertical arm pair
        ])

    def terminals(self):
        aw, al = um(self.arm_width_um), um(self.arm_length_um)
        span = aw + 2 * al
        t = min(al, aw)
        return [
            pya.Box(0, al, t, al + aw),                 # 1 west
            pya.Box(al, 0, al + aw, t),                 # 2 south
            pya.Box(span - t, al, span, al + aw),       # 3 east
            pya.Box(al, span - t, al + aw, span),       # 4 north
        ]

    def n_squares(self):
        return None
