"""corners.py -- the square-count model. Pure Python, no pya required.

This is the arithmetic that decides what resistance gets reported for a shaped
corner, so it is the part most able to be silently wrong.
"""

import math

import pytest

from microresistor.corners import (CHAMFER_K, Corner, CornerSpec,
                                   SQUARE_CORNER_SQUARES,
                                   TAPERED_CORNER_SQUARES, tag)


# --- construction and validation -----------------------------------------

def test_default_is_a_square_corner():
    spec = CornerSpec()
    assert spec.style is Corner.SQUARE
    assert spec.squares(10.0) == SQUARE_CORNER_SQUARES


def test_rounded_needs_a_radius():
    with pytest.raises(ValueError, match="positive radius_um"):
        CornerSpec(Corner.ROUNDED)


def test_tapered_needs_a_chamfer():
    with pytest.raises(ValueError, match="positive chamfer_um"):
        CornerSpec(Corner.TAPERED)


def test_arc_points_below_eight_is_rejected():
    # KLayout's corner rounding is measurably a no-op at 4 and 5 points, so a
    # low value would silently draw nothing.
    with pytest.raises(ValueError, match="at least 8"):
        CornerSpec(Corner.ROUNDED, radius_um=5, arc_points=4)


def test_rounded_radius_must_exceed_half_the_trace_width():
    spec = CornerSpec(Corner.ROUNDED, radius_um=5.0)
    with pytest.raises(ValueError, match="must exceed half the trace width"):
        spec.validate_for(width_um=10.0, straight_um=100.0)


def test_chamfer_wider_than_the_trace_is_rejected():
    spec = CornerSpec(Corner.TAPERED, chamfer_um=20.0)
    with pytest.raises(ValueError, match="would sever the trace"):
        spec.validate_for(width_um=10.0, straight_um=100.0)


def test_corner_that_does_not_fit_the_straight_run_is_rejected():
    spec = CornerSpec(Corner.ROUNDED, radius_um=30.0)
    with pytest.raises(ValueError, match="only 20.0 um of straight run"):
        spec.validate_for(width_um=10.0, straight_um=20.0)


# --- consumed length ------------------------------------------------------

def test_square_and_tapered_consume_one_trace_width():
    assert CornerSpec().consumed_um(10.0) == 10.0
    assert CornerSpec(Corner.TAPERED, chamfer_um=4).consumed_um(10.0) == 10.0


def test_rounded_consumes_the_radius_off_each_of_two_legs():
    assert CornerSpec(Corner.ROUNDED, radius_um=15).consumed_um(10.0) == 30.0


# --- squares per corner ---------------------------------------------------

def test_tapered_corner_is_worth_less_than_a_square_one():
    w = 10.0
    assert (CornerSpec(Corner.TAPERED, chamfer_um=4).squares(w)
            < CornerSpec().squares(w))
    assert CornerSpec(Corner.TAPERED, chamfer_um=4).squares(w) == \
        TAPERED_CORNER_SQUARES


def test_rounded_uses_the_analytic_annular_bend():
    # (pi/2) / ln(r_outer / r_inner) for a 90-degree bend.
    w, r = 10.0, 10.0
    expected = (math.pi / 2.0) / math.log(15.0 / 5.0)
    assert CornerSpec(Corner.ROUNDED, radius_um=r).squares(w) == \
        pytest.approx(expected)
    assert CornerSpec(Corner.ROUNDED, radius_um=r).squares(w) == \
        pytest.approx(1.4300, abs=1e-3)


def test_rounded_corner_is_worth_less_than_its_own_arc_length():
    # The whole point of the correction: current crowds on the inside of the
    # turn, so the bend carries fewer squares than a naive centreline count.
    w, r = 10.0, 10.0
    naive_arc_squares = (math.pi / 2.0) * r / w          # arc length / width
    assert CornerSpec(Corner.ROUNDED, radius_um=r).squares(w) < naive_arc_squares


def test_a_tighter_bend_is_worth_fewer_squares():
    w = 10.0
    tight = CornerSpec(Corner.ROUNDED, radius_um=6.0).squares(w)
    gentle = CornerSpec(Corner.ROUNDED, radius_um=40.0).squares(w)
    assert tight < gentle


def test_degenerate_bend_contributes_nothing():
    # At r = W/2 the inside of the turn collapses to a point; all the current
    # takes the short path.
    assert CornerSpec(Corner.ROUNDED, radius_um=5.0).squares(10.0) == 0.0


def test_override_wins_over_every_style():
    for spec in (CornerSpec(squares_override=0.3),
                 CornerSpec(Corner.TAPERED, chamfer_um=4, squares_override=0.3),
                 CornerSpec(Corner.ROUNDED, radius_um=20, squares_override=0.3)):
        assert spec.squares(10.0) == 0.3


def test_negative_override_is_rejected():
    with pytest.raises(ValueError, match="cannot be negative"):
        CornerSpec(squares_override=-1.0)


# --- the backward-compatibility identity ----------------------------------

@pytest.mark.parametrize("width,total,n_corners,cs", [
    (10.0, 520.0, 8, 0.56),
    (10.0, 520.0, 8, 0.50),
    (10.0, 520.0, 8, 1.00),
    (5.0, 1000.0, 20, 0.56),
    (2.5, 97.5, 4, 0.33),
])
def test_square_style_reduces_to_the_old_discount_formula(width, total,
                                                          n_corners, cs):
    """The generalised model must not move the 90-degree numbers.

    Old form:  naive - n*(1 - corner_squares)
    New form:  (total - n*consumed)/W + n*squares,  consumed = W
    """
    spec = CornerSpec(squares_override=cs)
    new = ((total - n_corners * spec.consumed_um(width)) / width
           + n_corners * spec.squares(width))
    old = total / width - n_corners * (1.0 - cs)
    assert new == pytest.approx(old)


# --- chamfer conversion constant ------------------------------------------

def test_chamfer_k_converts_a_cut_length_to_a_radius():
    # KLayout takes a radius; we expose the physical cut. Measured relation is
    # cut = r * (2 - sqrt(2)), so r = cut * CHAMFER_K.
    assert CHAMFER_K == pytest.approx(1.70711, abs=1e-5)
    cut = 5.0
    assert CornerSpec(Corner.TAPERED, chamfer_um=cut).extent_um() == \
        pytest.approx(cut * CHAMFER_K)
    # round trip
    assert CornerSpec(Corner.TAPERED, chamfer_um=cut).extent_um() * \
        (2 - math.sqrt(2)) == pytest.approx(cut)


def test_square_style_has_no_extent():
    assert CornerSpec().extent_um() == 0.0


def test_rounded_extent_is_the_radius():
    assert CornerSpec(Corner.ROUNDED, radius_um=12.5).extent_um() == 12.5


# --- naming ---------------------------------------------------------------

def test_tags_are_distinct_and_filename_safe():
    assert tag(CornerSpec()) == "SQ"
    assert tag(CornerSpec(Corner.ROUNDED, radius_um=12.5)) == "RN12p5"
    assert tag(CornerSpec(Corner.TAPERED, chamfer_um=5)) == "TP5"
