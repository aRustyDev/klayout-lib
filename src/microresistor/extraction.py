"""Turning measurements into process parameters.

This lives outside the geometry classes on purpose. A Greek cross is a shape;
converting a measured V and a forced I into a sheet resistance is analysis, and
the package rule is that geometry classes carry only geometry. Keeping the two
apart is also what makes this arithmetic testable without pya.
"""

import math


def sheet_resistance_vdp(v_measured, i_forced):
    """R_s from YOUR measured V and forced I, symmetric cross, f = 1.

    Force current through one opposing arm pair, measure voltage across the
    other. Contact resistance cancels, which is the whole point of the
    four-terminal structure.
    """
    return (math.pi / math.log(2)) * (v_measured / i_forced)
