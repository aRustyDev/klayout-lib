"""pads.py and the pad-layer split in build_cell.

The central invariant: pads land on their OWN layer and leave the resistor
layer untouched. The code this replaces merged pads straight into the
resistor's region on the resistor's layer, so that is the regression worth
pinning hardest.
"""

import math

import pytest

base = pytest.importorskip(
    "microresistor.base",
    reason="needs pya: run under KLayout or `uv run --with klayout`")
pads = pytest.importorskip("microresistor.pads")
devices = pytest.importorskip("microresistor.devices")

from microresistor.corners import Corner, CornerSpec  # noqa: E402
from microresistor.units import um  # noqa: E402

pya = base.pya
Pad = pads.Pad
GreekCross = devices.GreekCross
StraightBar = devices.StraightBar


def _region(cell, layer):
    return pya.Region(cell.begin_shapes_rec(layer))


def _corner_cut(polygon):
    """Length of the 45-degree cut on the lower-left corner of a polygon.

    Finds the vertex nearest the bbox's lower-left and returns its distance
    along the bottom edge -- i.e. how far the chamfer ate into the corner.
    """
    bb = polygon.bbox()
    xs = [p.x for p in polygon.each_point_hull()]
    ys = [p.y for p in polygon.each_point_hull()]
    on_bottom = [x for x, y in zip(xs, ys) if y == bb.bottom]
    return min(on_bottom) - bb.left


# --- pad construction -----------------------------------------------------

def test_square_pad_is_a_box_centred_on_the_terminal():
    terminal = StraightBar(100, 10).terminals()[0]
    polys = Pad(size_um=40).polygons_at(terminal)
    assert len(polys) == 1
    assert polys[0].num_points() == 4
    assert polys[0].bbox().center() == terminal.center()


def test_pad_defaults_to_square_but_accepts_a_height():
    terminal = StraightBar(100, 10).terminals()[0]
    tall = Pad(size_um=40, height_um=80).polygons_at(terminal)[0].bbox()
    assert tall.width() == um(40)
    assert tall.height() == um(80)


def test_tapered_pad_is_an_octagon():
    terminal = StraightBar(100, 10).terminals()[0]
    poly = Pad(size_um=40,
               corner=CornerSpec(Corner.TAPERED, chamfer_um=5)
               ).polygons_at(terminal)[0]
    assert poly.num_points() == 8
    # 45-degree cuts only, so the result stays half-manhattan.
    assert poly.is_halfmanhattan()


def test_tapered_pad_cut_matches_the_requested_chamfer():
    """Assert the ACHIEVED cut, not the conversion constant.

    CHAMFER_K encodes a measured KLayout relation rather than a documented
    one; this is the test that notices if that relation ever moves.
    """
    terminal = StraightBar(100, 10).terminals()[0]
    for chamfer in (2.0, 5.0, 10.0):
        poly = Pad(size_um=40,
                   corner=CornerSpec(Corner.TAPERED, chamfer_um=chamfer)
                   ).polygons_at(terminal)[0]
        assert _corner_cut(poly) == pytest.approx(um(chamfer), abs=2)


def test_tapered_pad_keeps_its_bounding_box():
    terminal = StraightBar(100, 10).terminals()[0]
    plain = Pad(size_um=40).polygons_at(terminal)[0].bbox()
    cut = Pad(size_um=40,
              corner=CornerSpec(Corner.TAPERED, chamfer_um=5)
              ).polygons_at(terminal)[0].bbox()
    assert cut == plain


def test_rounded_pad_has_many_vertices_and_less_area():
    terminal = StraightBar(100, 10).terminals()[0]
    plain = Pad(size_um=40).polygons_at(terminal)[0]
    round_ = Pad(size_um=40,
                 corner=CornerSpec(Corner.ROUNDED, radius_um=8, arc_points=64)
                 ).polygons_at(terminal)[0]
    assert round_.num_points() > 8
    assert round_.area() < plain.area()
    # Four quarter-circles replace four square corners: the area lost is
    # (4 - pi) * r^2.
    lost = plain.area() - round_.area()
    assert lost == pytest.approx((4 - math.pi) * um(8) ** 2, rel=0.02)


def test_corner_treatment_larger_than_half_the_pad_is_rejected():
    with pytest.raises(ValueError, match="would consume the pad"):
        Pad(size_um=40, corner=CornerSpec(Corner.ROUNDED, radius_um=30))
    with pytest.raises(ValueError, match="would consume the pad"):
        Pad(size_um=40, corner=CornerSpec(Corner.TAPERED, chamfer_um=30))


def test_pad_rejects_nonpositive_dimensions():
    with pytest.raises(ValueError):
        Pad(size_um=0)
    with pytest.raises(ValueError):
        Pad(size_um=40, height_um=-1)


def test_pad_tags_distinguish_styles():
    assert Pad(size_um=40).tag() == "PAD40SQ"
    assert Pad(size_um=40,
               corner=CornerSpec(Corner.TAPERED, chamfer_um=5)
               ).tag() == "PAD40TP5"
    assert Pad(size_um=40, height_um=80).tag().startswith("PAD40x80")


# --- the layer split ------------------------------------------------------

def test_pads_land_on_the_pad_layer():
    layout = pya.Layout()
    layout.dbu = 0.001
    metal, padl = layout.layer(1, 0), layout.layer(2, 0)
    cell = StraightBar(100, 10).build_cell(
        layout, metal, pad=Pad(size_um=40), pad_layer=padl)
    assert not _region(cell, padl).is_empty()
    assert _region(cell, padl).count() == 2      # one per terminal


def test_pads_do_not_leak_onto_the_resistor_layer():
    """The exact bug in the code this replaces.

    The old build_cell merged pads into the resistor's own region on the
    resistor's own layer. The resistor layer must be identical with and
    without pads.
    """
    layout = pya.Layout()
    layout.dbu = 0.001
    metal, padl = layout.layer(1, 0), layout.layer(2, 0)
    plain = StraightBar(100, 10).build_cell(layout, metal)
    padded = StraightBar(100, 10).build_cell(
        layout, metal, pad=Pad(size_um=40), pad_layer=padl)
    assert (_region(plain, metal) ^ _region(padded, metal)).is_empty()
    # And the pads really were drawn, so the comparison above is not vacuous.
    assert not _region(padded, padl).is_empty()


def test_pad_without_a_layer_is_refused():
    layout = pya.Layout()
    layout.dbu = 0.001
    metal = layout.layer(1, 0)
    with pytest.raises(ValueError, match="pads need their own layer"):
        StraightBar(100, 10).build_cell(layout, metal, pad=Pad(size_um=40))


def test_four_terminal_device_gets_four_pads():
    layout = pya.Layout()
    layout.dbu = 0.001
    metal, padl = layout.layer(1, 0), layout.layer(2, 0)
    cell = GreekCross(arm_width_um=20, arm_length_um=40).build_cell(
        layout, metal, pad=Pad(size_um=15), pad_layer=padl)
    assert _region(cell, padl).count() == 4


def test_cell_names_distinguish_pad_styles():
    """Two pad styles on one device must not collide on create_cell."""
    layout = pya.Layout()
    layout.dbu = 0.001
    metal, padl = layout.layer(1, 0), layout.layer(2, 0)
    bar = StraightBar(100, 10)
    a = bar.build_cell(layout, metal, pad=Pad(size_um=40), pad_layer=padl)
    b = bar.build_cell(
        layout, metal,
        pad=Pad(size_um=40, corner=CornerSpec(Corner.TAPERED, chamfer_um=5)),
        pad_layer=padl)
    assert a.name != b.name
    assert bar.build_cell(layout, metal).name == "BAR_L100_W10"


# --- the bridging guard ---------------------------------------------------

def test_a_pad_that_spans_the_device_is_refused():
    """A pad wide enough to touch both terminals shorts the resistor.

    Measured on the real sweep: a 40 um pad bridges every bar shorter than
    about 40 um, which would have put four dead devices on the mask.
    """
    layout = pya.Layout()
    layout.dbu = 0.001
    metal, padl = layout.layer(1, 0), layout.layer(2, 0)
    with pytest.raises(ValueError, match="short the resistor"):
        StraightBar(10, 10).build_cell(
            layout, metal, pad=Pad(size_um=40), pad_layer=padl)


def test_bridging_can_be_opted_into():
    layout = pya.Layout()
    layout.dbu = 0.001
    metal, padl = layout.layer(1, 0), layout.layer(2, 0)
    cell = StraightBar(10, 10).build_cell(
        layout, metal, pad=Pad(size_um=40), pad_layer=padl,
        allow_bridged_pads=True)
    assert _region(cell, padl).count() == 1      # merged, as warned


@pytest.mark.parametrize("length,size,bridges", [
    (10, 40, True),
    (20, 40, True),
    (50, 40, True),
    (100, 40, False),
    (100, 10, False),
])
def test_pads_bridge_predicts_the_short(length, size, bridges):
    assert StraightBar(length, 10).pads_bridge(Pad(size_um=size)) is bridges


def test_a_four_terminal_device_is_checked_against_all_four():
    # Arms are 40 um long, so a 60 um pad reaches the centre from every side.
    cross = GreekCross(arm_width_um=20, arm_length_um=40)
    assert cross.pads_bridge(Pad(size_um=90))
    assert not cross.pads_bridge(Pad(size_um=15))


# --- offset pads with leads -----------------------------------------------

def test_offset_pad_sits_outside_the_device():
    bar = StraightBar(10, 10)
    left, right = bar.pad_polygons(Pad(size_um=40, offset_um=30))
    device = pya.Region()
    for p in bar.shapes():
        device.insert(p)
    dev_bb = device.bbox()
    # The pads reach well beyond both ends of a 10 um bar.
    assert pya.Region(left).bbox().left < dev_bb.left
    assert pya.Region(right).bbox().right > dev_bb.right


def test_offset_pad_rescues_a_device_too_short_to_be_centred():
    """The whole point of offsetting.

    A 40 um pad centred on a 10 um bar shorts it; offset, the same pad fits.
    """
    bar = StraightBar(10, 10)
    assert bar.pads_bridge(Pad(size_um=40))
    assert not bar.pads_bridge(Pad(size_um=40, offset_um=30))


@pytest.mark.parametrize("length", [10, 20, 50, 100, 200])
def test_offset_pads_never_bridge_across_the_sweep(length):
    assert not StraightBar(length, 10).pads_bridge(
        Pad(size_um=40, offset_um=30))


def test_offset_pad_and_lead_are_one_polygon():
    """The lead must actually touch the pad, or the contact is open."""
    polys = StraightBar(100, 10).pad_polygons(Pad(size_um=40, offset_um=30))
    assert len(polys) == 2          # one per terminal, lead merged in


def test_lead_overlaps_the_terminal():
    """Contact cannot depend on an exact edge coincidence."""
    bar = StraightBar(100, 10)
    terminal = bar.terminals()[0]
    pad = Pad(size_um=40, offset_um=30)
    region = pya.Region()
    for p in pad.polygons_at(terminal, (-1, 0)):
        region.insert(p)
    assert not (region & pya.Region(terminal)).is_empty()


def test_lead_width_defaults_to_the_terminal_and_can_be_overridden():
    bar = StraightBar(100, 10)
    terminal = bar.terminals()[0]
    default = Pad(size_um=40, offset_um=30).lead_at(terminal, (-1, 0))
    narrow = Pad(size_um=40, offset_um=30,
                 lead_width_um=4).lead_at(terminal, (-1, 0))
    assert default.height() == um(10)      # the terminal's own width
    assert narrow.height() == um(4)


def test_offset_respects_the_requested_gap():
    bar = StraightBar(100, 10)
    terminal = bar.terminals()[0]
    pad_box = Pad(size_um=40, offset_um=30).box_at(terminal, (-1, 0))
    # Clear gap between the terminal's outer edge and the pad's near edge.
    assert terminal.left - pad_box.right == um(30)


def test_four_terminal_device_pushes_pads_to_four_compass_points():
    cross = GreekCross(arm_width_um=20, arm_length_um=40)
    assert cross.terminal_directions() == [(-1, 0), (0, -1), (1, 0), (0, 1)]
    polys = cross.pad_polygons(Pad(size_um=40, offset_um=20))
    assert len(polys) == 4


def test_centred_pads_are_unchanged_by_the_offset_feature():
    """offset_um = 0 must behave exactly as before."""
    terminal = StraightBar(100, 10).terminals()[0]
    a = Pad(size_um=40).polygons_at(terminal)
    b = Pad(size_um=40, offset_um=0).polygons_at(terminal, (-1, 0))
    assert len(a) == len(b) == 1
    assert a[0].bbox() == b[0].bbox()


def test_offset_shows_up_in_the_tag():
    assert Pad(size_um=40, offset_um=30).tag() == "PAD40SQO30"
    assert Pad(size_um=40).tag() == "PAD40SQ"


def test_offset_pad_rejects_a_negative_gap():
    with pytest.raises(ValueError, match="cannot be negative"):
        Pad(size_um=40, offset_um=-1)


def test_offset_pads_land_on_the_pad_layer_only():
    layout = pya.Layout()
    layout.dbu = 0.001
    metal, padl = layout.layer(1, 0), layout.layer(2, 0)
    plain = StraightBar(10, 10).build_cell(layout, metal)
    padded = StraightBar(10, 10).build_cell(
        layout, metal, pad=Pad(size_um=40, offset_um=30), pad_layer=padl)
    assert (_region(plain, metal) ^ _region(padded, metal)).is_empty()
    assert _region(padded, padl).count() == 2
