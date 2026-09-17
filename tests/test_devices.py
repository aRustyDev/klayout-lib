"""devices.py -- the square-count arithmetic and constructor guards.

Importing devices needs a pya (KLayout's, or the standalone klayout wheel), so
the whole module skips when neither is present; the pure-Python tests still run.
No geometry is built here -- that is test_geometry.py.
"""

import pytest

devices = pytest.importorskip(
    "microresistor.devices",
    reason="needs pya: run under KLayout or `uv run --with klayout`")

Dogbone = devices.Dogbone
GreekCross = devices.GreekCross
Serpentine = devices.Serpentine
StraightBar = devices.StraightBar


# --- StraightBar ----------------------------------------------------------

def test_bar_squares_is_length_over_width():
    assert StraightBar(100, 10).n_squares() == pytest.approx(10.0)
    assert StraightBar(10, 10).n_squares() == pytest.approx(1.0)


def test_bar_squares_ignores_absolute_scale():
    # L20/W2 and L100/W10 are the same resistor at 1/100 the area; both are in
    # the DEVICES sweep precisely to test that claim on silicon.
    assert StraightBar(20, 2).n_squares() == StraightBar(100, 10).n_squares()


def test_bar_contact_defaults_to_the_narrower_of_width_and_a_quarter_length():
    assert StraightBar(100, 10).contact_um == 10        # min(10, 25)
    assert StraightBar(10, 10).contact_um == 2.5        # min(10, 2.5)


def test_bar_contact_is_not_overridden_when_given():
    assert StraightBar(100, 10, contact_um=3).contact_um == 3


def test_bar_default_name():
    assert StraightBar(100, 10).name == "BAR_L100_W10"
    assert StraightBar(2.5, 0.5).name == "BAR_L2p5_W0p5"


def test_explicit_name_survives_post_init():
    assert StraightBar(100, 10, name="CUSTOM").name == "CUSTOM"


# --- Dogbone --------------------------------------------------------------

def test_dogbone_squares_counts_the_neck_only():
    assert Dogbone(50, 4, 20).n_squares() == pytest.approx(12.5)


def test_dogbone_rejects_a_head_no_wider_than_the_neck():
    with pytest.raises(ValueError, match="head_um must exceed width_um"):
        Dogbone(50, 20, 20)
    with pytest.raises(ValueError):
        Dogbone(50, 20, 10)


def test_dogbone_default_name():
    assert Dogbone(50, 4, 20).name == "DOG_L50_W4_H20"


# --- Serpentine -----------------------------------------------------------

def test_serpentine_needs_at_least_two_legs():
    with pytest.raises(ValueError, match="at least 2 legs"):
        Serpentine(width_um=10, leg_length_um=80, n_legs=1, pitch_um=30)


def test_serpentine_rejects_a_pitch_that_makes_legs_touch():
    with pytest.raises(ValueError, match="pitch_um must exceed width_um"):
        Serpentine(width_um=10, leg_length_um=80, n_legs=5, pitch_um=10)


def test_serpentine_has_two_corners_per_fold():
    s = Serpentine(width_um=10, leg_length_um=80, n_legs=5, pitch_um=30)
    assert s.n_corners() == 8
    assert s.n_corners() == 2 * (s.n_legs - 1)


def test_serpentine_centreline_length():
    # 5 legs of 80 um, joined by 4 crossings of 30 um.
    s = Serpentine(width_um=10, leg_length_um=80, n_legs=5, pitch_um=30)
    assert s.centreline_length_um() == pytest.approx(520.0)


def test_serpentine_centreline_alternates_direction():
    s = Serpentine(width_um=10, leg_length_um=80, n_legs=3, pitch_um=30)
    assert s.centreline() == [
        (0.0, 0.0), (0.0, 80),
        (30.0, 80), (30.0, 0.0),
        (60.0, 0.0), (60.0, 80),
    ]


def test_serpentine_corner_correction_discounts_each_bend():
    # naive = 520/10 = 52 squares, which already counts 1.0 per corner.
    # Current crowds on the inside of a turn, so each of the 8 corners is
    # worth 0.56 rather than 1.0: 52 - 8*(1 - 0.56) = 48.48.
    s = Serpentine(width_um=10, leg_length_um=80, n_legs=5, pitch_um=30)
    assert s.n_squares() == pytest.approx(48.48)


def test_serpentine_corner_squares_is_tunable():
    s = Serpentine(width_um=10, leg_length_um=80, n_legs=5, pitch_um=30,
                   corner_squares=0.5)
    assert s.n_squares() == pytest.approx(52.0 - 8 * 0.5)


def test_serpentine_with_unity_corner_squares_equals_the_naive_count():
    s = Serpentine(width_um=10, leg_length_um=80, n_legs=5, pitch_um=30,
                   corner_squares=1.0)
    assert s.n_squares() == pytest.approx(52.0)


def test_serpentine_default_name():
    s = Serpentine(width_um=10, leg_length_um=80, n_legs=5, pitch_um=30)
    assert s.name == "SRP_W10_N5_L80"


# --- GreekCross -----------------------------------------------------------

def test_greek_cross_has_no_square_count():
    # Not None-as-error: a van der Pauw cross genuinely has no series square
    # count, and report/predict must treat that differently from "uncalibrated".
    assert GreekCross(arm_width_um=20, arm_length_um=40).n_squares() is None


def test_greek_cross_default_name():
    assert GreekCross(arm_width_um=20, arm_length_um=40).name == "VDP_W20_A40"


def test_greek_cross_no_longer_carries_extraction_math():
    # The R_s arithmetic moved to extraction.sheet_resistance_vdp(); a geometry
    # class must not carry it.
    assert not hasattr(GreekCross, "sheet_resistance")
