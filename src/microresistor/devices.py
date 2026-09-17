"""The device library.

Each device is built in its own convenient local frame. Placement normalises
with cell.bbox(), so no device has to agree with any other about where its
origin sits.

Geometry and layer-independent structure only -- no resistivity, no film
thickness, no resistance. Those live in process.py; extraction math lives in
extraction.py; corner treatments and their square-count models live in
corners.py.

A note on the word "thickness". Process.thickness_nm is the DEPOSITED FILM
thickness, the z dimension, and it is what derives sheet resistance. The
serpentine's in-plane trace width is therefore spelled trace_thickness_um in
full, never plain "thickness", so the two can never be confused when geometry
code sits next to R_s code.
"""

try:  # KLayout runtime
    import pya  # type: ignore
except ImportError:  # pragma: no cover - plain Python import path
    import klayout.db as pya  # type: ignore

from dataclasses import dataclass, field
from typing import Optional

from .base import Resistor, apply_corners, merged
from .corners import Corner, CornerSpec
from .corners import tag as corner_tag
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

    The four corners where the neck meets the heads are CONCAVE, so a corner
    spec is applied as an inner radius -- the mirror of the serpentine, whose
    bends are convex. Filleting them relieves the current crowding at the
    junction; it does not change the square count, which counts the neck only.
    """
    length_um: float          # neck length
    width_um: float           # neck width
    head_um: float            # head is head_um x head_um
    corner: CornerSpec = field(default_factory=CornerSpec)
    name: str = ""

    def __post_init__(self):
        if self.head_um <= self.width_um:
            raise ValueError("head_um must exceed width_um or it is just a bar")
        if self.corner.style is not Corner.SQUARE:
            # The fillet sits in the step between neck and head, so it cannot
            # be deeper than half that step.
            step = (self.head_um - self.width_um) / 2.0
            extent = (self.corner.radius_um if self.corner.style is Corner.ROUNDED
                      else self.corner.chamfer_um)
            if extent > step:
                raise ValueError(
                    f"corner extent {extent} exceeds the neck-to-head step "
                    f"({step}); the junction fillet would not fit")
        if not self.name:
            self.name = (f"DOG_L{tag(self.length_um)}_W{tag(self.width_um)}"
                         f"_H{tag(self.head_um)}")
            if self.corner.style is not Corner.SQUARE:
                self.name += f"_{corner_tag(self.corner)}"

    def _raw_region(self):
        hd, L, w = um(self.head_um), um(self.length_um), um(self.width_um)
        y0 = (hd - w) // 2
        region = pya.Region()
        region.insert(pya.Box(0, 0, hd, hd))                  # left head
        region.insert(pya.Box(hd, y0, hd + L, y0 + w))        # neck
        region.insert(pya.Box(hd + L, 0, hd + L + hd, hd))    # right head
        region.merge()
        return region

    def shapes(self):
        region = self._raw_region()
        # Concave junction corners -> inner radius, outer left alone so the
        # head's own outside corners stay square.
        region = apply_corners(region, self.corner,
                               inner_um=self.corner.extent_um(), outer_um=0.0)
        return list(region.each())

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
    trace_thickness_um/2 to the left of x=0, so the bbox has a negative left
    edge. Placement normalises this.

    Bends are CONVEX corners, so a corner spec maps to an outer radius. ROUNDED
    additionally sets the inner radius to keep the trace width constant through
    the bend; TAPERED leaves the inside sharp, which is the standard miter.
    """
    trace_thickness_um: float
    leg_length_um: float
    n_legs: int
    pitch_um: float
    corner: CornerSpec = field(default_factory=CornerSpec)
    name: str = ""

    def __post_init__(self):
        if self.n_legs < 2:
            raise ValueError("a serpentine needs at least 2 legs")
        if self.pitch_um <= self.trace_thickness_um:
            raise ValueError("pitch_um must exceed trace_thickness_um "
                             "or legs touch")
        # Two corners share each straight run, so each may consume at most half
        # of the shortest run available.
        shortest = min(self.pitch_um, self.leg_length_um)
        self.corner.validate_for(self.trace_thickness_um, shortest)
        if not self.name:
            self.name = (f"SRP_W{tag(self.trace_thickness_um)}_N{self.n_legs}"
                         f"_L{tag(self.leg_length_um)}")
            if self.corner.style is not Corner.SQUARE:
                self.name += f"_{corner_tag(self.corner)}"

    # -- alternative constructor ------------------------------------------

    @classmethod
    def from_wave(cls, trace_thickness_um, amplitude_um, length_um,
                  wavelength_um=None, frequency_per_um=None,
                  corner=None, name=""):
        """Build a square meander from wave parameters.

        One period is a down-and-up, i.e. two legs, so pitch = wavelength / 2.
        Amplitude is zero-to-peak in the usual wave sense, so a device of
        amplitude A swings 2A and leg_length = 2 * amplitude.

        Give exactly one of wavelength_um or frequency_per_um (cycles per
        micrometre, f = 1 / wavelength).

        length_um is a REQUEST. The span is quantised to whole legs, so the
        built device spans (n_legs - 1) * pitch; read it back from the
        length_um property rather than assuming you got what you asked for.
        """
        if (wavelength_um is None) == (frequency_per_um is None):
            raise ValueError(
                "give exactly one of wavelength_um or frequency_per_um")
        if frequency_per_um is not None:
            if frequency_per_um <= 0:
                raise ValueError("frequency_per_um must be positive")
            wavelength_um = 1.0 / frequency_per_um
        if wavelength_um <= 0:
            raise ValueError("wavelength_um must be positive")
        if amplitude_um <= 0:
            raise ValueError("amplitude_um must be positive")
        if length_um <= 0:
            raise ValueError("length_um must be positive")

        pitch = wavelength_um / 2.0
        n_legs = max(2, int(round(length_um / pitch)) + 1)
        return cls(trace_thickness_um=trace_thickness_um,
                   leg_length_um=2.0 * amplitude_um,
                   n_legs=n_legs,
                   pitch_um=pitch,
                   corner=corner if corner is not None else CornerSpec(),
                   name=name)

    # -- wave view of the geometry ----------------------------------------

    @property
    def wavelength_um(self) -> float:
        """Spatial period: one down-and-up, i.e. two pitches."""
        return 2.0 * self.pitch_um

    @property
    def frequency_per_um(self) -> float:
        """Cycles per micrometre."""
        return 1.0 / self.wavelength_um

    @property
    def amplitude_um(self) -> float:
        """Zero-to-peak excursion: half the leg length."""
        return self.leg_length_um / 2.0

    @property
    def length_um(self) -> float:
        """Span actually built along the propagation axis."""
        return (self.n_legs - 1) * self.pitch_um

    # -- geometry ----------------------------------------------------------

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
        return pya.Path(pts, um(self.trace_thickness_um), 0, 0)

    def shapes(self):
        region = pya.Region()
        region.insert(self.path().polygon())
        region.merge()
        w = self.trace_thickness_um
        if self.corner.style is Corner.ROUNDED:
            # Both radii, so the band keeps a constant width through the bend.
            region = apply_corners(region, self.corner,
                                   inner_um=self.corner.radius_um - w / 2.0,
                                   outer_um=self.corner.radius_um + w / 2.0)
        elif self.corner.style is Corner.TAPERED:
            # Outer corner only: the standard miter leaves the inside sharp.
            region = apply_corners(region, self.corner, inner_um=0.0,
                                   outer_um=self.corner.extent_um())
        return list(region.each())

    def n_corners(self):
        return 2 * (self.n_legs - 1)

    def centreline_length_um(self):
        return (self.n_legs * self.leg_length_um
                + (self.n_legs - 1) * self.pitch_um)

    def terminals(self):
        pts = self.centreline()
        half = um(self.trace_thickness_um) // 2
        out = []
        for x, y in (pts[0], pts[-1]):
            cx, cy = um(x), um(y)
            out.append(pya.Box(cx - half, cy - half, cx + half, cy + half))
        return out

    def n_squares(self):
        """Straight runs plus corners.

        Each corner consumes some centreline and contributes its own count in
        place of it. For a sharp 90-degree corner this is algebraically the
        same as the older "naive minus a discount per corner" formula -- see
        corners.py and the identity test.
        """
        w = self.trace_thickness_um
        n = self.n_corners()
        straight = self.centreline_length_um() - n * self.corner.consumed_um(w)
        return straight / w + n * self.corner.squares(w)


@dataclass
class GreekCross(Resistor):
    """Van der Pauw cross. A test structure, not a series element.

    Four terminals, no current direction, no centreline, no square count.
    Force 1-3, measure 2-4, and R_s falls out with contact resistance
    cancelled -- which is why n_squares() is None rather than a number.

    The R_s arithmetic itself is extraction, not geometry, so it lives in
    extraction.sheet_resistance_vdp() rather than on this class.

    The four reentrant corners where the arms meet are CONCAVE, so a corner
    spec is applied as an inner radius. It has no square-count meaning here --
    n_squares() is None either way -- but rounding them is standard practice
    to keep the current distribution near the cross centre well behaved.
    """
    arm_width_um: float
    arm_length_um: float
    corner: CornerSpec = field(default_factory=CornerSpec)
    name: str = ""

    def __post_init__(self):
        if self.corner.style is not Corner.SQUARE:
            extent = (self.corner.radius_um if self.corner.style is Corner.ROUNDED
                      else self.corner.chamfer_um)
            if extent > self.arm_length_um:
                raise ValueError(
                    f"corner extent {extent} exceeds the arm length "
                    f"({self.arm_length_um})")
        if not self.name:
            self.name = (f"VDP_W{tag(self.arm_width_um)}"
                         f"_A{tag(self.arm_length_um)}")
            if self.corner.style is not Corner.SQUARE:
                self.name += f"_{corner_tag(self.corner)}"

    def shapes(self):
        aw, al = um(self.arm_width_um), um(self.arm_length_um)
        span = aw + 2 * al
        region = pya.Region()
        region.insert(pya.Box(0, al, span, al + aw))      # horizontal arm pair
        region.insert(pya.Box(al, 0, al + aw, span))      # vertical arm pair
        region.merge()
        region = apply_corners(region, self.corner,
                               inner_um=self.corner.extent_um(),
                               outer_um=0.0)
        return list(region.each())

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
