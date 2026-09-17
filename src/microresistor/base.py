"""The resistor interface, and the one geometry helper every device needs.

Needs a pya. Under KLayout that is the built-in module; outside it, the
standalone ``klayout`` wheel provides the same db API, which is what makes the
device geometry testable with pytest.
"""

try:  # KLayout runtime
    import pya  # type: ignore
except ImportError:  # pragma: no cover - plain Python import path
    import klayout.db as pya  # type: ignore

from abc import ABC, abstractmethod
from typing import List, Optional

from .units import um


class Resistor(ABC):
    """A patternable resistor.

    Subclasses own their own geometry. The contract is only:
      shapes()    -> merged polygons, database units, local frame
      terminals() -> contact regions, same frame. Two of them, or four.
      n_squares() -> square count for R = R_s * N, or None if the device
                     is not a two-terminal series element.
    """

    name: str

    @abstractmethod
    def shapes(self) -> List["pya.Polygon"]:
        ...

    @abstractmethod
    def terminals(self) -> List["pya.Box"]:
        ...

    @abstractmethod
    def n_squares(self) -> Optional[float]:
        ...

    def build_cell(self, layout, layer, pad_um: Optional[float] = None):
        cell = layout.create_cell(self.name)
        region = pya.Region()
        for poly in self.shapes():
            region.insert(poly)
        if pad_um is not None:
            for box in self.terminals():
                cx, cy = box.center().x, box.center().y
                half = um(pad_um) // 2
                region.insert(pya.Box(cx - half, cy - half, cx + half, cy + half))
        region.merge()
        for poly in region.each():
            cell.shapes(layer).insert(poly)
        return cell


def merged(boxes) -> List["pya.Polygon"]:
    region = pya.Region()
    for box in boxes:
        region.insert(box)
    region.merge()
    return list(region.each())
