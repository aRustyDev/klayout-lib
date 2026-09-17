"""Drawn text.

Isolated in its own module because it is the one thing here that reaches for a
PCell library rather than building polygons directly.

The Basic library IS available outside KLayout, contrary to what this file used
to claim. In the standalone ``klayout`` wheel it is simply not auto-registered:
``import klayout.lib`` registers it, and that import has to happen BEFORE any
``Library`` access. Touch ``Library.library_names()`` first and Basic never
registers in that process at all -- measured, deterministic, and silent, which
is exactly the kind of ordering trap worth writing down.

Under KLayout itself ``pya`` has Basic pre-registered and no extra import is
needed.
"""

try:  # KLayout runtime
    import pya  # type: ignore
except ImportError:  # pragma: no cover - plain Python import path
    import klayout.db as pya  # type: ignore
    # MUST precede any pya.Library access, and there is none above this line.
    import klayout.lib  # type: ignore  # noqa: F401


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
