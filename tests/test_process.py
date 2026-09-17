"""process.py -- pure Python, no pya required.

This is the arithmetic that could previously only be checked by launching the
GUI and reading printed output.
"""

import dataclasses

import pytest

from microresistor.process import Material, Process


def test_explicit_sheet_resistance_is_used_as_given():
    assert Process(sheet_resistance=50.0).r_s == 50.0


def test_sheet_resistance_derived_from_material_and_thickness():
    # NICHROME 1.10e-6 ohm-m over 100 nm -> 11 ohm/square.
    p = Process(material=Material.NICHROME, thickness_nm=100.0)
    assert p.r_s == pytest.approx(11.0)


def test_measured_sheet_resistance_wins_over_derived():
    # The derived value would be 11.0; the measurement must override it.
    p = Process(sheet_resistance=7.0,
                material=Material.NICHROME, thickness_nm=100.0)
    assert p.r_s == 7.0


def test_r_s_raises_when_nothing_is_known():
    with pytest.raises(ValueError, match="No sheet resistance available"):
        Process().r_s


def test_r_s_raises_when_material_given_without_thickness():
    with pytest.raises(ValueError):
        Process(material=Material.GOLD).r_s


def test_r_s_raises_when_thickness_given_without_material():
    with pytest.raises(ValueError):
        Process(thickness_nm=50.0).r_s


@pytest.mark.parametrize("process,expected", [
    (Process(), False),
    (Process(sheet_resistance=10.0), True),
    (Process(material=Material.NICHROME, thickness_nm=100.0), True),
    (Process(material=Material.NICHROME), False),
    (Process(thickness_nm=100.0), False),
])
def test_is_calibrated_matches_whether_r_s_evaluates(process, expected):
    assert process.is_calibrated is expected
    # is_calibrated must be an exact predicate for "r_s does not raise".
    if expected:
        assert process.r_s > 0
    else:
        with pytest.raises(ValueError):
            process.r_s


def test_predict_is_sheet_resistance_times_squares():
    assert Process(sheet_resistance=10.0).predict(5.0) == pytest.approx(50.0)


def test_predict_adds_contact_resistance_per_contact():
    p = Process(sheet_resistance=10.0, contact_resistance=2.0)
    assert p.predict(5.0, n_contacts=2) == pytest.approx(54.0)
    assert p.predict(5.0, n_contacts=4) == pytest.approx(58.0)


def test_predict_defaults_to_two_contacts():
    p = Process(sheet_resistance=10.0, contact_resistance=2.0)
    assert p.predict(5.0) == p.predict(5.0, n_contacts=2)


def test_predict_rejects_a_missing_square_count():
    # A GreekCross returns None from n_squares(); predicting from it would be
    # a fiction, so it must raise rather than return something plausible.
    with pytest.raises(ValueError, match="not a two-terminal element"):
        Process(sheet_resistance=10.0).predict(None)


def test_predict_raises_on_an_uncalibrated_process():
    with pytest.raises(ValueError, match="No sheet resistance available"):
        Process().predict(5.0)


def test_process_is_frozen():
    p = Process(sheet_resistance=10.0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        p.sheet_resistance = 20.0
