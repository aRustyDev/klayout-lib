"""marks.py -- alignment marks and the die outline."""

import pytest

marks = pytest.importorskip(
    "microresistor.marks",
    reason="needs pya: run under KLayout or `uv run --with klayout`")

from microresistor.units import um  # noqa: E402

pya = marks.pya


def _region(polys):
    region = pya.Region()
    for p in polys:
        region.insert(p)
    region.merge()
    return region


# --- cross ----------------------------------------------------------------

def test_cross_is_one_polygon_spanning_tip_to_tip():
    region = _region(marks.cross(100, 10))
    assert region.count() == 1
    assert region.bbox() == pya.Box(-um(50), -um(50), um(50), um(50))


def test_cross_area_is_two_arms_less_the_overlap():
    # Two 100x10 bars crossing share a 10x10 square.
    region = _region(marks.cross(100, 10))
    expected = 2 * um(100) * um(10) - um(10) ** 2
    assert region.area() == expected


def test_cross_is_centred_on_the_origin():
    bb = _region(marks.cross(100, 10)).bbox()
    assert bb.center() == pya.Point(0, 0)


def test_cross_rejects_an_arm_wider_than_the_mark():
    with pytest.raises(ValueError, match="smaller than size_um"):
        marks.cross(50, 50)


# --- frame ----------------------------------------------------------------

def test_frame_is_hollow():
    region = _region(marks.frame(60, 5))
    assert region.bbox() == pya.Box(-um(30), -um(30), um(30), um(30))
    outer = um(60) ** 2
    inner = um(50) ** 2
    assert region.area() == outer - inner


def test_frame_rejects_walls_that_close_it_up():
    with pytest.raises(ValueError, match="smaller than outer_um"):
        marks.frame(60, 30)


# --- box in box -----------------------------------------------------------

def test_box_in_box_leaves_an_equal_gap_all_round():
    outer, inner = marks.box_in_box(outer_um=60, wall_um=5, inner_um=40)
    outer_r, inner_r = _region(outer), _region(inner)
    # The inner box sits inside the frame's opening with clearance on all sides.
    assert (inner_r & outer_r).is_empty()
    ob, ib = outer_r.bbox(), inner_r.bbox()
    left = (ib.left - (ob.left + um(5)))
    right = ((ob.right - um(5)) - ib.right)
    assert left == right > 0


def test_box_in_box_rejects_an_inner_that_does_not_fit():
    with pytest.raises(ValueError, match="no gap"):
        marks.box_in_box(outer_um=60, wall_um=5, inner_um=50)


# --- assembled mark set ---------------------------------------------------

def test_alignment_marks_put_shapes_on_both_layers():
    layout = pya.Layout()
    layout.dbu = 0.001
    a, b = layout.layer(1, 0), layout.layer(3, 0)
    cell = marks.alignment_marks(layout, a, b)
    assert not pya.Region(cell.begin_shapes_rec(a)).is_empty()
    assert not pya.Region(cell.begin_shapes_rec(b)).is_empty()


def test_alignment_marks_registration_pair_does_not_overlap():
    """A box-in-box that overlaps when aligned cannot be read."""
    layout = pya.Layout()
    layout.dbu = 0.001
    a, b = layout.layer(1, 0), layout.layer(3, 0)
    cell = marks.alignment_marks(layout, a, b)
    prim = pya.Region(cell.begin_shapes_rec(a))
    sec = pya.Region(cell.begin_shapes_rec(b))
    assert (prim & sec).is_empty()


def test_build_mark_cell_accepts_arbitrary_layer_shape_pairs():
    layout = pya.Layout()
    layout.dbu = 0.001
    a = layout.layer(7, 0)
    cell = marks.build_mark_cell(layout, "M", [(a, marks.filled_box(20))])
    assert cell.name == "M"
    assert pya.Region(cell.begin_shapes_rec(a)).area() == um(20) ** 2


# --- die outline ----------------------------------------------------------

def test_die_outline_draws_a_centred_rectangle():
    layout = pya.Layout()
    layout.dbu = 0.001
    cell = layout.create_cell("TOP")
    layer = layout.layer(0, 0)
    box = marks.die_outline(layout, cell, layer, 5000, 5000)
    assert box.width() == um(5000)
    assert box.center() == pya.Point(0, 0)
    assert pya.Region(cell.begin_shapes_rec(layer)).count() == 1


def test_die_outline_honours_a_centre():
    layout = pya.Layout()
    layout.dbu = 0.001
    cell = layout.create_cell("TOP")
    box = marks.die_outline(layout, cell, layout.layer(0, 0), 100, 200,
                            centre=(50, 100))
    assert box.center() == pya.Point(um(50), um(100))


def test_die_outline_rejects_nonpositive_dimensions():
    layout = pya.Layout()
    layout.dbu = 0.001
    cell = layout.create_cell("TOP")
    with pytest.raises(ValueError, match="must be positive"):
        marks.die_outline(layout, cell, layout.layer(0, 0), 0, 100)


def test_fits_in_die_discriminates():
    die = pya.Box(-um(100), -um(100), um(100), um(100))
    assert marks.fits_in_die(pya.Box(-um(50), -um(50), um(50), um(50)), die)
    assert not marks.fits_in_die(
        pya.Box(-um(150), -um(50), um(150), um(50)), die)
