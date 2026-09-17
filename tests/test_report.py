"""report.py -- pure Python, no pya required.

report_lines() only reads .name and .n_squares(), so a stub device is enough;
that independence is the reason it is its own module.
"""

from microresistor.process import Material, Process
from microresistor.report import report_lines


class _StubDevice:
    def __init__(self, name, squares):
        self.name = name
        self._squares = squares

    def n_squares(self):
        return self._squares


def test_one_line_per_device():
    lines = report_lines([_StubDevice("A", 1.0), _StubDevice("B", 2.0)],
                         Process())
    assert len(lines) == 2


def test_uncalibrated_process_says_so_rather_than_guessing():
    line, = report_lines([_StubDevice("BAR_L100_W10", 10.0)], Process())
    assert "R_s not measured yet" in line
    assert " 10.00" in line


def test_device_without_a_square_count_is_marked_a_test_structure():
    # A GreekCross, even against a fully calibrated process: the two unknowns
    # must stay distinguishable.
    line, = report_lines([_StubDevice("VDP_W20_A40", None)],
                         Process(sheet_resistance=10.0))
    assert "test structure -- extract R_s directly" in line
    assert "n/a" in line


def test_calibrated_process_predicts_a_resistance():
    line, = report_lines([_StubDevice("BAR_L100_W10", 10.0)],
                         Process(sheet_resistance=10.0))
    assert "100.0 ohm" in line


def test_prediction_includes_contact_resistance():
    line, = report_lines(
        [_StubDevice("BAR_L100_W10", 10.0)],
        Process(sheet_resistance=10.0, contact_resistance=5.0))
    assert "110.0 ohm" in line  # 10*10 + 2*5


def test_derived_process_predicts_too():
    line, = report_lines([_StubDevice("BAR_L100_W10", 10.0)],
                         Process(material=Material.NICHROME,
                                 thickness_nm=100.0))
    assert "110.0 ohm" in line  # 11 ohm/sq * 10 squares


def test_name_column_is_padded_to_a_fixed_width():
    line, = report_lines([_StubDevice("SHORT", 1.0)], Process())
    assert line.startswith("SHORT" + " " * 19)
