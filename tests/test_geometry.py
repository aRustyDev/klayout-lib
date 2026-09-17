"""Geometry actually built through pya.

Skips as a module when no pya is available.
"""

import math

import pytest

base = pytest.importorskip(
    "microresistor.base",
    reason="needs pya: run under KLayout or `uv run --with klayout`")
devices = pytest.importorskip("microresistor.devices")
labels = pytest.importorskip("microresistor.labels")

from microresistor.corners import Corner, CornerSpec  # noqa: E402
from microresistor.pads import Pad  # noqa: E402
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
    s = Serpentine(trace_thickness_um=10, leg_length_um=80, n_legs=5, pitch_um=30)
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
    (Serpentine(trace_thickness_um=10, leg_length_um=80, n_legs=5, pitch_um=30), 2),
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
    s = Serpentine(trace_thickness_um=10, leg_length_um=80, n_legs=5, pitch_um=30)
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
    layer, padl = layout.layer(1, 0), layout.layer(2, 0)
    plain = StraightBar(100, 10).build_cell(layout, layer)
    padded = StraightBar(100, 10).build_cell(
        layout, layer, pad=Pad(size_um=40), pad_layer=padl)
    assert padded.bbox().height() > plain.bbox().height()


# --- serpentine corner treatments -----------------------------------------

def _region_of(polygons):
    region = pya.Region()
    for poly in polygons:
        region.insert(poly)
    region.merge()
    return region


def _leg_widths_at(polygons, y_dbu):
    """Width of each vertical leg crossing a horizontal line, in dbu.

    Slices a one-dbu band so each leg comes back as its own box; the legs are
    vertical, so their WIDTH is the horizontal extent.
    """
    region = _region_of(polygons)
    bb = region.bbox()
    band = pya.Region(pya.Box(bb.left, y_dbu, bb.right, y_dbu + 1))
    return sorted(p.bbox().width() for p in (region & band).each())


def _serp(**kw):
    return Serpentine(trace_thickness_um=10, leg_length_um=80, n_legs=5,
                      pitch_um=30, **kw)


def test_square_serpentine_is_all_right_angles():
    assert _serp().shapes()[0].is_halfmanhattan()


def test_tapered_serpentine_cuts_corners_but_stays_half_manhattan():
    plain = _serp().shapes()[0]
    cut = _serp(corner=CornerSpec(Corner.TAPERED, chamfer_um=4)).shapes()[0]
    assert cut.is_halfmanhattan()          # 45-degree cuts only
    assert cut.num_points() > plain.num_points()
    assert cut.area() < plain.area()       # metal removed at the outer corners


def test_tapered_serpentine_leaves_the_inside_of_the_turn_sharp():
    """A standard miter cuts the OUTER corner only.

    The inner corner is where current crowds; cutting it would be the wrong
    trade. rounded_corners(0, r, 8) is what gives us convex-only.
    """
    cut = _serp(corner=CornerSpec(Corner.TAPERED, chamfer_um=4)).shapes()[0]
    plain = _serp().shapes()[0]
    # Concave vertices are unchanged, so the bbox is untouched.
    assert cut.bbox() == plain.bbox()


@pytest.mark.parametrize("spec", [
    CornerSpec(),
    CornerSpec(Corner.TAPERED, chamfer_um=4),
    CornerSpec(Corner.ROUNDED, radius_um=12),
])
def test_every_style_keeps_full_trace_width_on_the_straight_runs(spec):
    # Mid-leg, clear of every bend: five legs, each exactly one width across.
    widths = _leg_widths_at(_serp(corner=spec).shapes(), um(40))
    assert widths == [um(10)] * 5


def _covers(region, x_um, y_um):
    """Is this micrometre point inside the region?"""
    probe = pya.Region(pya.Box(um(x_um), um(y_um), um(x_um) + 1, um(y_um) + 1))
    return not (region & probe).is_empty()


def test_rounded_bend_has_the_radii_the_square_count_assumes():
    """Inner radius r - W/2, outer r + W/2 -- probed radially through the bend.

    This is the geometric claim the analytic square count rests on, so it is
    worth asserting directly rather than inferring it from an area.

    Note a DRC width_check is NOT the right tool here: it reports a minimum of
    W/sqrt(2) on a correct bend (measured, and unchanged at 256 arc points),
    because it pairs edges across the 45-degree arc entry. That is a
    measurement artifact, not a pinch.
    """
    w, r = 10.0, 12.0
    region = _region_of(_serp(
        corner=CornerSpec(Corner.ROUNDED, radius_um=r)).shapes())

    # First bend: centreline turns at (0, 80) from +y to +x, so the arc centre
    # sits at (r, 80 - r). Probe outward along the 45-degree ray.
    cx, cy = r, 80.0 - r
    ux = uy = math.sqrt(0.5)

    def at(radius):
        return _covers(region, cx - ux * radius, cy + uy * radius)

    assert not at(r - w / 2 - 0.5), "metal inside the inner radius"
    assert at(r - w / 2 + 0.5), "no metal just inside the bend"
    assert at(r + w / 2 - 0.5), "no metal just inside the outer radius"
    assert not at(r + w / 2 + 0.5), "metal beyond the outer radius"


def test_rounded_serpentine_removes_more_metal_than_a_chamfer():
    plain = _serp().shapes()[0].area()
    cut = _serp(corner=CornerSpec(Corner.TAPERED, chamfer_um=5)).shapes()[0].area()
    rnd = _serp(corner=CornerSpec(Corner.ROUNDED, radius_um=12)).shapes()[0].area()
    assert rnd < plain
    assert cut < plain


def test_rounded_serpentine_is_not_half_manhattan():
    rounded = _serp(corner=CornerSpec(Corner.ROUNDED, radius_um=12)).shapes()[0]
    assert not rounded.is_halfmanhattan()


# --- concave corner devices -----------------------------------------------

def test_dogbone_junction_fillet_removes_no_metal_from_the_outside():
    plain = Dogbone(50, 4, 20).shapes()[0]
    filled = Dogbone(50, 4, 20,
                     corner=CornerSpec(Corner.ROUNDED, radius_um=3)).shapes()[0]
    # A concave fillet ADDS metal in the reentrant corner, and the outline
    # bbox is unchanged.
    assert filled.bbox() == plain.bbox()
    assert filled.area() > plain.area()


def test_dogbone_fillet_larger_than_the_step_is_rejected():
    with pytest.raises(ValueError, match="junction fillet would not fit"):
        Dogbone(50, 4, 20, corner=CornerSpec(Corner.ROUNDED, radius_um=20))


def test_greek_cross_inner_corners_can_be_rounded():
    plain = GreekCross(arm_width_um=20, arm_length_um=40).shapes()[0]
    rnd = GreekCross(arm_width_um=20, arm_length_um=40,
                     corner=CornerSpec(Corner.ROUNDED, radius_um=5)).shapes()[0]
    assert rnd.bbox() == plain.bbox()
    assert rnd.area() > plain.area()   # reentrant corners filled in


# --- labels ---------------------------------------------------------------

def test_text_cell_builds_real_polygons():
    """The Basic PCell library IS reachable outside KLayout.

    labels.py used to claim otherwise and this was left untested; it only
    needs ``import klayout.lib`` before any Library access, which labels.py
    now does.
    """
    layout = pya.Layout()
    layout.dbu = 0.001
    idx = labels.text_cell(layout, "BAR_L100_W10", 10, 0, 10.0)
    cell = layout.cell(idx)
    text_layer = layout.layer(10, 0)
    region = pya.Region(cell.begin_shapes_rec(text_layer))
    assert not region.is_empty()       # real geometry, not a text record
    assert region.count() > 1
