"""Arranging built cells on the top cell."""

try:  # KLayout runtime
    import pya  # type: ignore
except ImportError:  # pragma: no cover - plain Python import path
    import klayout.db as pya  # type: ignore

from .labels import text_cell
from .units import um


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
            # instead of 20). Cosmetic; left as-is so this refactor does not
            # move any geometry. Fix by dropping the `- bb.bottom` term.
            tc = text_cell(layout, cell.name, label_layer[0], label_layer[1],
                           label_mag)
            top.insert(pya.CellInstArray(
                tc, pya.Trans(0, y - bb.bottom + bb.height() + um(20.0))))
        y += bb.height() + um(gap_um)
