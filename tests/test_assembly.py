"""assembly.py -- mixing pad styles across one sweep.

The resolution policy imports no pya, so most of this runs with stubs on bare
Python. Only the build_cells tests need real devices.
"""

import pytest

from microresistor.assembly import AUTO, Assembly, PadPlan, build_cells


class _StubPad:
    def __init__(self, name, fits):
        self._name = name
        self._fits = fits

    def tag(self):
        return self._name


class _StubDevice:
    """A device that bridges any pad not in its `fits` set."""

    def __init__(self, name, fits=()):
        self.name = name
        self._fits = set(fits)

    def pads_bridge(self, pad):
        return pad.tag() not in self._fits

    def build_cell(self, layout, layer, pad=None, pad_layer=None, **kw):
        layout.append((self.name, pad.tag() if pad else None))
        return f"cell:{self.name}"


OVERLAP = _StubPad("OVERLAP", True)
LEADED = _StubPad("LEADED", True)
PLAN = PadPlan(overlap=OVERLAP, leaded=LEADED)


# --- AUTO resolution ------------------------------------------------------

def test_auto_prefers_the_overlapping_pad_when_it_fits():
    """An overlap adds no lead resistance, so it wins when it can."""
    device = _StubDevice("LONG", fits=("OVERLAP", "LEADED"))
    assert PLAN.resolve(device) is OVERLAP


def test_auto_falls_back_to_the_lead_when_the_overlap_would_bridge():
    device = _StubDevice("SHORT", fits=("LEADED",))
    assert PLAN.resolve(device) is LEADED


def test_auto_gives_up_when_nothing_fits():
    device = _StubDevice("TINY", fits=())
    assert PLAN.resolve(device) is None


def test_auto_respects_a_plan_with_only_one_style():
    device = _StubDevice("LONG", fits=("OVERLAP", "LEADED"))
    assert PadPlan(leaded=LEADED).resolve(device) is LEADED
    assert PadPlan().resolve(device) is None


# --- explicit choices -----------------------------------------------------

def test_an_explicit_pad_is_used_even_where_auto_would_differ():
    device = _StubDevice("LONG", fits=("OVERLAP", "LEADED"))
    assert PLAN.resolve(device) is OVERLAP           # auto would overlap
    assert PLAN.resolve(device, LEADED) is LEADED    # but we asked


def test_explicit_none_means_bare_and_is_not_the_same_as_auto():
    """None is a decision, AUTO is a deferral."""
    device = _StubDevice("LONG", fits=("OVERLAP", "LEADED"))
    assert PLAN.resolve(device, None) is None
    assert PLAN.resolve(device, AUTO) is OVERLAP


def test_an_explicit_pad_is_honoured_even_if_it_would_bridge():
    """Explicit means explicit; the guard in build_cell is what refuses."""
    device = _StubDevice("SHORT", fits=("LEADED",))
    assert PLAN.resolve(device, OVERLAP) is OVERLAP


def test_auto_is_a_singleton_so_identity_checks_hold():
    from microresistor.assembly import _Auto
    assert _Auto() is AUTO
    assert repr(AUTO) == "AUTO"


# --- describe -------------------------------------------------------------

@pytest.mark.parametrize("device,choice,expected", [
    (_StubDevice("L", fits=("OVERLAP", "LEADED")), AUTO, "auto: overlap fits"),
    (_StubDevice("S", fits=("LEADED",)), AUTO, "auto: overlap would bridge"),
    (_StubDevice("T", fits=()), AUTO, "every style in the plan would bridge"),
    (_StubDevice("L", fits=("OVERLAP", "LEADED")), LEADED, "explicit"),
    (_StubDevice("L", fits=("OVERLAP", "LEADED")), None, "no pad: asked for"),
])
def test_describe_explains_the_choice(device, choice, expected):
    assert expected in PLAN.describe(device, choice)


# --- build_cells ----------------------------------------------------------

def test_build_cells_accepts_bare_devices_and_pairs():
    calls = []
    entries = [
        _StubDevice("A", fits=("OVERLAP", "LEADED")),          # AUTO
        (_StubDevice("B", fits=("OVERLAP", "LEADED")), LEADED),  # explicit
        (_StubDevice("C", fits=("OVERLAP", "LEADED")), None),    # bare
        _StubDevice("D", fits=("LEADED",)),                      # AUTO -> lead
    ]
    asm = build_cells(calls, "metal", entries, plan=PLAN, pad_layer="pads")
    assert [p.tag() if p else None for p in asm.pads] == [
        "OVERLAP", "LEADED", None, "LEADED"]
    assert [d.name for d in asm.devices] == ["A", "B", "C", "D"]
    assert len(asm) == 4


def test_build_cells_reports_which_devices_ended_up_bare():
    entries = [
        _StubDevice("OK", fits=("OVERLAP",)),
        _StubDevice("NOPE", fits=()),
    ]
    asm = build_cells([], "metal", entries, plan=PLAN)
    assert [d.name for d in asm.bare] == ["NOPE"]


def test_build_cells_without_a_plan_leaves_everything_bare():
    asm = build_cells([], "metal",
                      [_StubDevice("A", fits=("OVERLAP",))])
    assert asm.pads == [None]


def test_build_cells_keeps_cells_devices_and_pads_aligned():
    entries = [_StubDevice(n, fits=("OVERLAP",)) for n in "ABC"]
    asm = build_cells([], "metal", entries, plan=PLAN)
    assert len(asm.cells) == len(asm.devices) == len(asm.pads) == 3
    assert asm.cells == ["cell:A", "cell:B", "cell:C"]


def test_empty_assembly_is_well_formed():
    asm = Assembly()
    assert len(asm) == 0
    assert asm.bare == []
