"""units.py -- pure Python, no pya required."""

from microresistor.units import DBU, tag, um


def test_dbu_is_one_nanometre_in_um():
    assert DBU == 0.001


def test_um_scales_to_integer_database_units():
    assert um(0) == 0
    assert um(1) == 1000
    assert um(100) == 100_000
    assert um(2.5) == 2500


def test_um_returns_int_not_float():
    assert isinstance(um(2.5), int)


def test_um_handles_negative_coordinates():
    # Serpentine's bbox has negative left and bottom edges, so this matters.
    assert um(-5) == -5000


def test_um_rounds_rather_than_truncates():
    assert um(0.0016) == 2
    assert um(0.0014) == 1


def test_tag_replaces_decimal_point_with_p():
    assert tag(2.5) == "2p5"
    assert tag(0.5) == "0p5"


def test_tag_replaces_minus_with_m():
    assert tag(-1) == "m1"
    assert tag(-2.5) == "m2p5"


def test_tag_drops_trailing_zeros_via_g_format():
    # %g is what keeps cell names short: 100.0 must not become "100p0".
    assert tag(100) == "100"
    assert tag(100.0) == "100"
    assert tag(10) == "10"
