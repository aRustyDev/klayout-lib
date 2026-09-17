"""placement.py -- stack() and the new grid()."""

import pytest

placement = pytest.importorskip(
    "microresistor.placement",
    reason="needs pya: run under KLayout or `uv run --with klayout`")
devices = pytest.importorskip("microresistor.devices")

from microresistor.units import um  # noqa: E402

pya = placement.pya
StraightBar = devices.StraightBar


def _layout():
    layout = pya.Layout()
    layout.dbu = 0.001
    return layout, layout.create_cell("TOP"), layout.layer(1, 0)


def _cells(layout, layer, specs):
    return [StraightBar(L, W).build_cell(layout, layer) for L, W in specs]


SWEEP = [(10, 10), (20, 10), (50, 10), (100, 10),
         (200, 10), (100, 5), (100, 20), (100, 50)]


def test_grid_places_every_cell():
    layout, top, layer = _layout()
    cells = _cells(layout, layer, SWEEP)
    placement.grid(layout, top, cells, cols=4, gap_um=50.0)
    assert top.child_instances() == len(cells)


def _aspect(bb):
    return max(bb.width(), bb.height()) / min(bb.width(), bb.height())


def test_grid_always_reduces_height():
    """The one property that holds regardless of the device mix."""
    layout, top, layer = _layout()
    placement.stack(layout, top, _cells(layout, layer, SWEEP), gap_um=50.0)
    tall = top.bbox()

    layout2, top2, layer2 = _layout()
    placement.grid(layout2, top2, _cells(layout2, layer2, SWEEP), cols=4,
                   gap_um=50.0)
    assert top2.bbox().height() < tall.height()


def test_grid_does_not_improve_aspect_for_a_row_of_wide_flat_devices():
    """Measured, and worth pinning so nobody over-claims for grid().

    Eight bars that are themselves 10:1 make a WIDER ribbon in a grid, not a
    squarer block. Grid pays off on a mixed sweep at a tuned column count, not
    unconditionally -- see the next test.
    """
    layout, top, layer = _layout()
    placement.stack(layout, top, _cells(layout, layer, SWEEP), gap_um=50.0)
    stacked = _aspect(top.bbox())

    layout2, top2, layer2 = _layout()
    placement.grid(layout2, top2, _cells(layout2, layer2, SWEEP), cols=4,
                   gap_um=50.0)
    assert _aspect(top2.bbox()) > stacked


def test_grid_squares_up_a_mixed_sweep():
    """With tall devices in the mix, a tuned column count wins decisively.

    Measured on the library's own 17-device sweep: one column gives
    340 x 3010 um (aspect 8.85) and three columns 1080 x 1230 um (aspect 1.14).
    """
    def build(layout, layer):
        cells = _cells(layout, layer, SWEEP)
        for _ in range(4):      # a few tall devices, as the real sweep has
            cells.append(devices.Serpentine(
                trace_thickness_um=10, leg_length_um=200, n_legs=5,
                pitch_um=30).build_cell(layout, layer,
                                        name=f"SRP{len(cells)}"))
        return cells

    layout, top, layer = _layout()
    placement.stack(layout, top, build(layout, layer), gap_um=50.0)
    stacked = _aspect(top.bbox())

    layout2, top2, layer2 = _layout()
    placement.grid(layout2, top2, build(layout2, layer2), cols=3, gap_um=50.0)
    assert _aspect(top2.bbox()) < stacked


def test_grid_cells_do_not_overlap():
    layout, top, layer = _layout()
    cells = _cells(layout, layer, SWEEP)
    placement.grid(layout, top, cells, cols=4, gap_um=50.0)
    region = pya.Region(top.begin_shapes_rec(layer))
    # Eight disjoint bars stay eight polygons only if nothing collided.
    assert region.count() == len(cells)


def test_grid_columns_are_aligned():
    """Column j starts at the same x in every row, so devices line up."""
    layout, top, layer = _layout()
    cells = _cells(layout, layer, [(100, 10)] * 8)
    placement.grid(layout, top, cells, cols=4, gap_um=50.0)
    lefts = sorted({inst.bbox().left for inst in top.each_inst()})
    assert len(lefts) == 4          # four distinct column origins


def test_grid_with_one_column_matches_a_stack_footprint_width():
    layout, top, layer = _layout()
    placement.grid(layout, top, _cells(layout, layer, SWEEP), cols=1,
                   gap_um=50.0)
    assert top.bbox().width() == um(200)     # the widest device


def test_grid_rejects_a_nonpositive_column_count():
    layout, top, layer = _layout()
    with pytest.raises(ValueError, match="at least 1"):
        placement.grid(layout, top, _cells(layout, layer, [(10, 10)]), cols=0)


def test_grid_handles_a_ragged_last_row():
    layout, top, layer = _layout()
    cells = _cells(layout, layer, SWEEP[:5])     # 5 cells into 4 columns
    placement.grid(layout, top, cells, cols=4, gap_um=50.0)
    assert top.child_instances() == 5


def test_stack_still_places_everything():
    layout, top, layer = _layout()
    cells = _cells(layout, layer, SWEEP)
    placement.stack(layout, top, cells, gap_um=50.0)
    assert top.child_instances() == len(cells)
