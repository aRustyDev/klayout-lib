"""extraction.py -- pure Python, no pya required."""

import math

import pytest

from microresistor.extraction import sheet_resistance_vdp


def test_van_der_pauw_prefactor():
    # R_s = (pi / ln 2) * (V / I); at V = I = 1 that is the prefactor alone.
    assert sheet_resistance_vdp(1.0, 1.0) == pytest.approx(math.pi / math.log(2))
    assert sheet_resistance_vdp(1.0, 1.0) == pytest.approx(4.532, abs=1e-3)


def test_linear_in_measured_voltage():
    assert sheet_resistance_vdp(2.0, 1.0) == pytest.approx(
        2 * sheet_resistance_vdp(1.0, 1.0))


def test_inverse_in_forced_current():
    assert sheet_resistance_vdp(1.0, 2.0) == pytest.approx(
        sheet_resistance_vdp(1.0, 1.0) / 2)


def test_realistic_measurement():
    # Force 1 mA, measure 4.4127 mV. That is a 4.4127 ohm four-terminal
    # resistance, which the pi/ln2 prefactor turns into 20 ohm/square --
    # note the prefactor is 4.532, so R_measured and R_s are NOT the same
    # number even at 1 mA.
    assert sheet_resistance_vdp(4.4127e-3, 1e-3) == pytest.approx(20.0, rel=1e-3)


def test_prefactor_is_not_unity():
    # Guards the easy misreading above: R_s != V/I.
    assert sheet_resistance_vdp(1.0, 1.0) > 4.5
