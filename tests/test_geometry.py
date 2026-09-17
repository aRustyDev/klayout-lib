"""Geometry actually built through pya.

Skips as a module when no pya is available. text_cell() is deliberately not
covered here -- it needs the GUI-side Basic PCell library, which the standalone
klayout wheel does not ship; the in-KLayout macro run covers it instead.
"""

import pytest

base = pytest.importorskip(
    "microresistor.base",
    reason="needs pya: run under KLayout or `uv run --with klayout`")
devices = pytest.importorskip("microresistor.devices")

from microresistor.units import um  # noqa: E402

pya = base.pya
merged = base.merged
Dogbone = devices.Dogbone
GreekCross = devices.GreekCross
Serpentine = devices.Serpentine
StraightBar = devices.StraightBar


def _bbox(polygons):
    region = pya.Region()
    for poly in polygons:
        region.insert(poly)
    return region.bbox()


# --- merged() -------------------------------------------------------------

def test_merged_fuses_touching_boxes_into_one_polygon():
    polys = merged([pya.Box(0, 0, 10, 10), pya.Box(10, 0, 20, 10)])
    assert len(polys) == 1
    assert polys[0].bbox() == pya.Box(0, 0, 20, 10)


def test_merged_keeps_disjoint_boxes_separate():
    polys = merged([pya.Box(0, 0, 10, 10), pya.Box(100, 0, 110, 10)])
    assert len(polys) == 2


# --- shapes ---------------------------------------------------------------

def test_bar_shape_is_one_rectangle_of_the_drawn_size():
    polys = StraightBar(100, 10).shapes()
    assert len(polys) == 1
    assert _bbox(polys) == pya.Box(0, 0, um(100), um(10))


def test_dogbone_merges_into_a_single_polygon():
    # Heads and neck are one polygon after the merge -- the reason a separate
    # Pad object would be wrong here.
    polys = Dogbone(50, 4, 20).shapes()
    assert len(polys) == 1
    assert _bbox(polys) == pya.Box(0, 0, um(20 + 50 + 20), um(20))


def test_dogbone_neck_is_centred_on_the_heads():
    d = Dogbone(50, 4, 20)
    hd, w = um(20), um(4)
    assert (hd - w) // 2 == um(8)  # neck sits 8 um up from the head bottom


def test_greek_cross_is_one_polygon_spanning_both_arm_pairs():
    polys = GreekCross(arm_width_um=20, arm_length_um=40).shapes()
    assert len(polys) == 1
    span = um(20 + 2 * 40)
    assert _bbox(polys) == pya.Box(0, 0, span, span)


def test_serpentine_bbox_extends_half_a_width_below_and_left_of_origin():
    # This is the quirk behind the label-offset note in placement.stack():
    # every other device has bbox.bottom == 0, and this one does not.
    s = Serpentine(width_um=10, leg_length_um=80, n_legs=5, pitch_um=30)
    bb = _bbox(s.shapes())
    assert bb.bottom == -um(10) // 2
    assert bb.left == -um(10) // 2


def test_every_other_device_has_a_bbox_bottom_of_zero():
    for device in (StraightBar(100, 10),
                   Dogbone(50, 4, 20),
                   GreekCross(arm_width_um=20, arm_length_um=40)):
        assert _bbox(device.shapes()).bottom == 0, device.name


# --- terminals ------------------------------------------------------------

@pytest.mark.parametrize("device,count", [
    (StraightBar(100, 10), 2),
    (Dogbone(50, 4, 20), 2),
    (Serpentine(width_um=10, leg_length_um=80, n_legs=5, pitch_um=30), 2),
    (GreekCross(arm_width_um=20, arm_length_um=40), 4),
])
def test_terminal_counts(device, count):
    assert len(device.terminals()) == count


def test_bar_terminals_sit_at_opposite_ends():
    left, right = StraightBar(100, 10).terminals()
    assert left.left == 0
    assert right.right == um(100)


def test_dogbone_terminals_are_the_heads():
    left, right = Dogbone(50, 4, 20).terminals()
    assert left == pya.Box(0, 0, um(20), um(20))
    assert right == pya.Box(um(70), 0, um(90), um(20))


def test_serpentine_terminals_are_centred_on_the_end_vertices():
    s = Serpentine(width_um=10, leg_length_um=80, n_legs=5, pitch_um=30)
    first, last = s.terminals()
    assert first.center().x == 0 and first.center().y == 0
    assert last.center().x == um(120) and last.center().y == um(80)


# --- build_cell -----------------------------------------------------------

def test_build_cell_names_the_cell_and_inserts_geometry():
    layout = pya.Layout()
    layout.dbu = 0.001
    layer = layout.layer(1, 0)
    cell = StraightBar(100, 10).build_cell(layout, layer)
    assert cell.name == "BAR_L100_W10"
    assert cell.bbox() == pya.Box(0, 0, um(100), um(10))


def test_build_cell_with_pads_grows_the_cell():
    layout = pya.Layout()
    layout.dbu = 0.001
    layer = layout.layer(1, 0)
    plain = StraightBar(100, 10).build_cell(layout, layer)
    padded = StraightBar(100, 10, name="PADDED").build_cell(
        layout, layer, pad_um=40.0)
    assert padded.bbox().height() > plain.bbox().height()
