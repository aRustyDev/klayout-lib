"""Parametric microresistor generator for KLayout.

Design notes:
  - Geometry classes carry ONLY geometry and layer-independent structure.
    No resistivity, no thickness, no resistance. A GDS file cannot hold
    those things; they live in process.py. Turning measurements back into
    process parameters lives in extraction.py.
  - Resistor is an interface (shapes / terminals / n_squares), not a data
    container. That is what lets a 4-terminal Greek cross and a 2-terminal
    bar coexist without either one lying about its shape.
  - Each device is built in its own convenient local frame. Placement
    normalises with cell.bbox(), so no device has to agree with any other
    about where its origin sits.

Import layers:
  units, process, extraction, report  -- pure Python, no pya, no wheel needed
  base, devices, placement            -- need pya (KLayout) or the klayout wheel
  labels                              -- additionally needs the GUI Basic PCell lib

The pure names are imported eagerly below; the pya-dependent ones are resolved
lazily through PEP 562 __getattr__, so ``from microresistor.process import
Process`` works under a bare CPython with no pya installed, while
``from microresistor import StraightBar`` still reads normally. Importing this
package therefore costs nothing until a geometry name is actually touched.

Targets Python 3.9 -- the interpreter KLayout 0.30.x embeds.
"""

from importlib import import_module

from .extraction import sheet_resistance_vdp
from .process import Material, Process
from .report import report_lines
from .units import DBU, tag, um

# name -> submodule it lives in; each of these pulls in pya on first access.
_LAZY = {
    "Resistor": ".base",
    "merged": ".base",
    "StraightBar": ".devices",
    "Dogbone": ".devices",
    "Serpentine": ".devices",
    "GreekCross": ".devices",
    "text_cell": ".labels",
    "stack": ".placement",
}

__all__ = [
    "DBU", "um", "tag",
    "Material", "Process",
    "sheet_resistance_vdp",
    "Resistor", "merged",
    "StraightBar", "Dogbone", "Serpentine", "GreekCross",
    "text_cell", "stack", "report_lines",
]


def __getattr__(name):
    """Resolve the pya-dependent exports on first use (PEP 562)."""
    try:
        where = _LAZY[name]
    except KeyError:
        raise AttributeError(
            f"module {__name__!r} has no attribute {name!r}") from None
    value = getattr(import_module(where, __name__), name)
    globals()[name] = value   # cache, so __getattr__ runs once per name
    return value


def __dir__():
    return sorted(__all__)
