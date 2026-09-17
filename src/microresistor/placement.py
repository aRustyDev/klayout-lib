"""Arranging built cells on the top cell."""

try:  # KLayout runtime
    import pya  # type: ignore
except ImportError:  # pragma: no cover - plain Python import path
    import klayout.db as pya  # type: ignore

from .labels import text_cell
from .units import um

LABEL_GAP_UM = 20.0


def _label(layout, top, cell, label_layer, label_mag, x, y):
    """Place a drawn-text label above a placed cell."""
    tc = text_cell(layout, cell.name, label_layer[0], label_layer[1], label_mag)
    top.insert(pya.CellInstArray(tc, pya.Trans(x, y)))


def stack(layout, top, cells, gap_um=100.0, label_layer=None, label_mag=10.0):
    """Stack cells bottom-to-top, left edges aligned at x=0."""
    y = 0
    for cell in cells:
        bb = cell.bbox()
        top.insert(pya.CellInstArray(
            cell.cell_index(), pya.Trans(-bb.left, y - bb.bottom)))
        if label_layer is not None:
            # NOTE: known quirk, preserved deliberately. After the translation
            # above the cell's top edge sits at y + bb.height(), so the label
            # offset below is short by bb.bottom. The two agree only when
            # bb.bottom == 0, which holds for every device except Serpentine
            # (its band extends width/2 below the first centreline vertex, so
            # bb.bottom is negative and its label ends up 25 um above the cell
            # instead of 20). Cosmetic; left as-is so this does not move any
            # geometry. Fix by dropping the `- bb.bottom` term.
            _label(layout, top, cell, label_layer, label_mag,
                   0, y - bb.bottom + bb.height() + um(LABEL_GAP_UM))
        y += bb.height() + um(gap_um)


def grid(layout, top, cells, cols=4, gap_um=100.0, label_layer=None,
         label_mag=10.0, label_headroom_um=40.0):
    """Place cells in a grid, row-major and bottom-up.

    A single column turns a sweep into a tall ribbon that wastes most of a die.
    Measured on this library's own 17-device sweep, with pads:

        cols=1   340 x 3010 um   aspect 8.85
        cols=3  1080 x 1230 um   aspect 1.14     <- squarest
        cols=6  2160 x  720 um   aspect 3.00

    Note the column count matters and more is not better: total area grows with
    cols, because each column is as wide as its widest member. Grid also does
    NOT help unconditionally -- a row of devices that are themselves wide and
    flat just becomes a wider, flatter block. It pays off on a mixed sweep at a
    tuned column count.

    Columns are as wide as their widest member and rows as tall as their
    tallest, so devices line up rather than staggering. ``label_headroom_um``
    reserves space above each row for its labels; it is separate from
    ``gap_um`` so labels cannot collide with the row above.

    Unlike stack(), labels here are placed from the cell's real top edge, so
    the bbox.bottom quirk noted above does not apply.
    """
    if cols < 1:
        raise ValueError("cols must be at least 1")

    rows = [cells[i:i + cols] for i in range(0, len(cells), cols)]
    col_w = [0] * cols
    row_h = []
    for row in rows:
        row_h.append(max((c.bbox().height() for c in row), default=0))
        for j, cell in enumerate(row):
            col_w[j] = max(col_w[j], cell.bbox().width())

    headroom = um(label_headroom_um) if label_layer is not None else 0
    gap = um(gap_um)

    y = 0
    for i, row in enumerate(rows):
        x = 0
        for j, cell in enumerate(row):
            bb = cell.bbox()
            top.insert(pya.CellInstArray(
                cell.cell_index(), pya.Trans(x - bb.left, y - bb.bottom)))
            if label_layer is not None:
                _label(layout, top, cell, label_layer, label_mag,
                       x, y + bb.height() + um(LABEL_GAP_UM))
            x += col_w[j] + gap
        y += row_h[i] + headroom + gap
