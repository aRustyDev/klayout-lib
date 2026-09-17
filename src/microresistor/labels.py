"""Drawn text.

Isolated in its own module because it is the one thing here that needs the
GUI-side Basic PCell library: pya.Library.library_by_name("Basic") does not
exist under the standalone ``klayout`` wheel, so this module cannot be
exercised by pytest. Everything else in the package can.
"""

try:  # KLayout runtime
    import pya  # type: ignore
except ImportError:  # pragma: no cover - plain Python import path
    import klayout.db as pya  # type: ignore


def text_cell(layout, string, layer_num, datatype, mag_um):
    """Real polygons, not a GDS text record.

    The Text tool writes metadata that will not print on a mask. The Basic
    library TEXT PCell writes actual geometry. If the parameter names below
    are wrong for your KLayout build, inspect them with
    pcell_decl.get_parameters().

    Returns a cell INDEX (add_pcell_variant), not a Cell object -- which is
    what pya.CellInstArray wants anyway.
    """
    lib = pya.Library.library_by_name("Basic")
    decl = lib.layout().pcell_declaration("TEXT")
    params = {
        "text": string,
        "layer": pya.LayerInfo(layer_num, datatype),
        "mag": mag_um,
    }
    return layout.add_pcell_variant(lib, decl.id(), params)
