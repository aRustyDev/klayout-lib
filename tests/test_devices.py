"""devices.py -- the square-count arithmetic and constructor guards.

Importing devices needs a pya (KLayout's, or the standalone klayout wheel), so
the whole module skips when neither is present; the pure-Python tests still run.
No geometry is built here -- that is test_geometry.py.
"""

import pytest

devices = pytest.importorskip(
    "microresistor.devices",
    reason="needs pya: run under KLayout or `uv run --with klayout`")

from microresistor.corners import Corner, CornerSpec  # noqa: E402 (pure, no pya)

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
        Serpentine(trace_thickness_um=10, leg_length_um=80, n_legs=1, pitch_um=30)


def test_serpentine_rejects_a_pitch_that_makes_legs_touch():
    with pytest.raises(ValueError, match="pitch_um must exceed trace_thickness_um"):
        Serpentine(trace_thickness_um=10, leg_length_um=80, n_legs=5, pitch_um=10)


def test_serpentine_has_two_corners_per_fold():
    s = Serpentine(trace_thickness_um=10, leg_length_um=80, n_legs=5, pitch_um=30)
    assert s.n_corners() == 8
    assert s.n_corners() == 2 * (s.n_legs - 1)


def test_serpentine_centreline_length():
    # 5 legs of 80 um, joined by 4 crossings of 30 um.
    s = Serpentine(trace_thickness_um=10, leg_length_um=80, n_legs=5, pitch_um=30)
    assert s.centreline_length_um() == pytest.approx(520.0)


def test_serpentine_centreline_alternates_direction():
    s = Serpentine(trace_thickness_um=10, leg_length_um=80, n_legs=3, pitch_um=30)
    assert s.centreline() == [
        (0.0, 0.0), (0.0, 80),
        (30.0, 80), (30.0, 0.0),
        (60.0, 0.0), (60.0, 80),
    ]


def test_serpentine_corner_correction_discounts_each_bend():
    # naive = 520/10 = 52 squares, which already counts 1.0 per corner.
    # Current crowds on the inside of a turn, so each of the 8 corners is
    # worth 0.56 rather than 1.0: 52 - 8*(1 - 0.56) = 48.48.
    s = Serpentine(trace_thickness_um=10, leg_length_um=80, n_legs=5, pitch_um=30)
    assert s.n_squares() == pytest.approx(48.48)


def test_serpentine_corner_squares_is_tunable():
    s = Serpentine(trace_thickness_um=10, leg_length_um=80, n_legs=5, pitch_um=30,
                   corner=CornerSpec(squares_override=0.5))
    assert s.n_squares() == pytest.approx(52.0 - 8 * 0.5)


def test_serpentine_with_unity_corner_squares_equals_the_naive_count():
    s = Serpentine(trace_thickness_um=10, leg_length_um=80, n_legs=5, pitch_um=30,
                   corner=CornerSpec(squares_override=1.0))
    assert s.n_squares() == pytest.approx(52.0)


def test_serpentine_default_name():
    s = Serpentine(trace_thickness_um=10, leg_length_um=80, n_legs=5, pitch_um=30)
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


# --- Serpentine.from_wave -------------------------------------------------

def _wave(**kw):
    base = dict(trace_thickness_um=10, amplitude_um=40, length_um=120,
                wavelength_um=60)
    base.update(kw)
    return Serpentine.from_wave(**base)


def test_from_wave_maps_onto_the_geometric_constructor():
    # One period is a down-and-up, so pitch is half the wavelength, and
    # amplitude is zero-to-peak, so the leg spans twice it.
    s = _wave()
    assert s.pitch_um == 30.0
    assert s.leg_length_um == 80.0
    assert s.n_legs == 5
    assert s.trace_thickness_um == 10


def test_from_wave_round_trips_through_the_derived_properties():
    s = _wave()
    assert s.wavelength_um == 60.0
    assert s.amplitude_um == 40.0
    assert s.length_um == 120.0
    assert s.frequency_per_um == pytest.approx(1 / 60.0)


def test_frequency_is_the_reciprocal_of_wavelength():
    by_lambda = _wave(wavelength_um=60)
    by_freq = Serpentine.from_wave(trace_thickness_um=10, amplitude_um=40,
                                   length_um=120, frequency_per_um=1 / 60.0)
    assert by_freq.pitch_um == pytest.approx(by_lambda.pitch_um)
    assert by_freq.n_legs == by_lambda.n_legs


def test_from_wave_needs_exactly_one_of_wavelength_or_frequency():
    with pytest.raises(ValueError, match="exactly one"):
        Serpentine.from_wave(trace_thickness_um=10, amplitude_um=40,
                             length_um=120)
    with pytest.raises(ValueError, match="exactly one"):
        Serpentine.from_wave(trace_thickness_um=10, amplitude_um=40,
                             length_um=120, wavelength_um=60,
                             frequency_per_um=1 / 60.0)


@pytest.mark.parametrize("kw", [
    {"wavelength_um": -1}, {"frequency_per_um": -1},
    {"amplitude_um": 0}, {"length_um": 0},
])
def test_from_wave_rejects_nonpositive_parameters(kw):
    args = dict(trace_thickness_um=10, amplitude_um=40, length_um=120)
    if "wavelength_um" not in kw and "frequency_per_um" not in kw:
        args["wavelength_um"] = 60
    args.update(kw)
    with pytest.raises(ValueError):
        Serpentine.from_wave(**args)


def test_requested_length_is_quantised_to_whole_legs():
    # 100 um at a 30 um pitch is not a whole number of legs: round(100/30) = 3
    # legs of span, so 4 legs and a 90 um span. The property reports what was
    # actually built, not what was asked for.
    s = _wave(length_um=100)
    assert s.n_legs == 4
    assert s.length_um == 90.0


def test_a_very_short_request_still_yields_a_legal_serpentine():
    s = _wave(length_um=1)
    assert s.n_legs == 2


def test_from_wave_carries_the_corner_spec():
    s = _wave(corner=CornerSpec(Corner.ROUNDED, radius_um=12))
    assert s.corner.style is Corner.ROUNDED
    assert "RN12" in s.name


def test_from_wave_and_geometric_constructor_agree_on_squares():
    wave = _wave()
    geom = Serpentine(trace_thickness_um=10, leg_length_um=80, n_legs=5,
                      pitch_um=30)
    assert wave.n_squares() == geom.n_squares()
