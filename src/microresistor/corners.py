"""Corner treatments, and what each one does to the square count.

No pya: this is the model, not the drawing. Keeping it here means the whole
square-count story is testable under a bare CPython, which matters because it is
the part that can be silently wrong.

The governing rule, from process.py: a wrong resistance is worse than no
resistance. A corner treatment changes both the shape drawn AND the resistance
of that shape, so the two must travel together. A CornerSpec therefore carries
its own square-count model rather than leaving a constant sitting beside it.

How the square count works
--------------------------
A corner consumes some length of the centreline and contributes some number of
squares in its place::

    n_squares = (centreline_len - n_corners * consumed) / W
                + n_corners * squares

For a sharp 90-degree corner (consumed = W, squares = 0.56) this expands to
``total/W - n*(1 - 0.56)``, which is exactly the "naive minus a discount" form
this library used before corner styles existed. That identity is deliberate and
is asserted in the tests.
"""

import math
from dataclasses import dataclass
from enum import Enum
from typing import Optional

# A "circle" approximated with 8 segments is an octagon, so KLayout's
# rounded_corners(0, r, 8) cuts each convex corner with a single 45-degree edge.
# The cut length is NOT r: measured against klayout 0.30.12 at r = 100, 200, 400
# and 1000 dbu, the cut came back 59, 117, 234 and 586 -- i.e. r*(2 - sqrt(2)).
# So to obtain a cut of c, ask for an outer radius of c * CHAMFER_K.
#
# This relation is measured, not documented by KLayout, so the geometry tests
# assert the ACHIEVED cut rather than trusting this constant.
CHAMFER_K = 1.0 / (2.0 - math.sqrt(2.0))   # ~1.70711

# Squares contributed by one corner, by style. Both are literature values and
# both are approximations -- texts disagree, commonly 0.5 to 0.65 for the sharp
# case. Treat them the way Material's docstring asks you to treat bulk
# resistivity: an order-of-magnitude sanity check, to be replaced by your own
# measurement via squares_override.
SQUARE_CORNER_SQUARES = 0.56
TAPERED_CORNER_SQUARES = 0.50


class Corner(Enum):
    """How a corner is drawn."""
    SQUARE = "square"      # 90 degrees, the only thing this library drew before
    ROUNDED = "rounded"    # circular arc of a given centreline radius
    TAPERED = "tapered"    # single 45-degree chamfer across the corner


@dataclass(frozen=True)
class CornerSpec:
    """A corner treatment: what to draw, and what it is worth electrically.

    Carries INTENT -- a centreline bend radius, a chamfer cut length -- rather
    than KLayout's (r_inner, r_outer) pair. Only the device knows its own trace
    width and which of its corners are convex, so the translation to KLayout's
    parameters belongs there, not here.
    """
    style: Corner = Corner.SQUARE
    radius_um: float = 0.0             # ROUNDED: centreline bend radius
    chamfer_um: float = 0.0            # TAPERED: cut length along each edge
    arc_points: int = 64               # points per FULL circle
    squares_override: Optional[float] = None

    def __post_init__(self):
        if self.arc_points < 8:
            raise ValueError("arc_points must be at least 8: KLayout's corner "
                             "rounding is a no-op at 4 and 5 points")
        if self.style is Corner.ROUNDED and self.radius_um <= 0:
            raise ValueError("ROUNDED needs a positive radius_um")
        if self.style is Corner.TAPERED and self.chamfer_um <= 0:
            raise ValueError("TAPERED needs a positive chamfer_um")
        if self.squares_override is not None and self.squares_override < 0:
            raise ValueError("squares_override cannot be negative")

    # -- geometry translation helpers -------------------------------------

    def extent_um(self) -> float:
        """Radius to hand KLayout for a treated corner, in micrometres.

        Used for whichever of the inner/outer pair the device is treating --
        convex for a serpentine bend, concave for a dogbone junction. Zero for
        SQUARE. For TAPERED this is the chamfer converted through CHAMFER_K,
        because KLayout takes a radius and we expose a cut length.
        """
        if self.style is Corner.ROUNDED:
            return self.radius_um
        if self.style is Corner.TAPERED:
            return self.chamfer_um * CHAMFER_K
        return 0.0

    # -- the square-count model -------------------------------------------

    def consumed_um(self, width_um: float) -> float:
        """Centreline length this corner removes from the straight runs.

        A sharp or chamfered corner occupies the W x W box the centreline
        crosses over a length of W. A circular bend of centreline radius r cuts
        the corner earlier, taking r off each of the two legs that meet there.
        """
        if self.style is Corner.ROUNDED:
            return 2.0 * self.radius_um
        return width_um

    def squares(self, width_um: float) -> float:
        """Squares contributed by one corner of this style.

        ROUNDED is analytic: for a 90-degree annular bend with inner radius a
        and outer radius b, the sheet count is (pi/2) / ln(b/a). It needs no
        literature constant, and it behaves correctly at the limits -- as the
        radius approaches W/2 the inner edge degenerates to a point, ln(b/a)
        diverges, and the corner contributes nothing.
        """
        if self.squares_override is not None:
            return self.squares_override
        if self.style is Corner.SQUARE:
            return SQUARE_CORNER_SQUARES
        if self.style is Corner.TAPERED:
            return TAPERED_CORNER_SQUARES
        inner = self.radius_um - width_um / 2.0
        outer = self.radius_um + width_um / 2.0
        if inner <= 0:
            # Degenerate bend: the inside of the turn is a point. All the
            # current takes the short path and the corner is worth nothing.
            return 0.0
        return (math.pi / 2.0) / math.log(outer / inner)

    def validate_for(self, width_um: float, straight_um: float) -> None:
        """Check this spec can actually be drawn on a trace of this width.

        Raises rather than returning a flag: a corner that does not fit is a
        design error, not a condition to branch on.
        """
        if self.style is Corner.ROUNDED:
            if self.radius_um <= width_um / 2.0:
                raise ValueError(
                    f"radius_um={self.radius_um} must exceed half the trace "
                    f"width ({width_um / 2.0}) or the bend has no inside edge")
        if self.style is Corner.TAPERED:
            if self.chamfer_um > width_um:
                raise ValueError(
                    f"chamfer_um={self.chamfer_um} exceeds the trace width "
                    f"({width_um}); the cut would sever the trace")
        consumed = self.consumed_um(width_um)
        if consumed > straight_um:
            raise ValueError(
                f"corner consumes {consumed} um but only {straight_um} um of "
                f"straight run is available between corners")


def tag(spec: CornerSpec) -> str:
    """Short, filename-safe marker for a corner style, for cell names."""
    if spec.style is Corner.SQUARE:
        return "SQ"
    if spec.style is Corner.ROUNDED:
        return f"RN{spec.radius_um:g}".replace(".", "p")
    return f"TP{spec.chamfer_um:g}".replace(".", "p")
