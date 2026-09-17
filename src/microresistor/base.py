"""The resistor interface, and the geometry helpers every device needs.

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

from .corners import Corner, CornerSpec
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

    def cell_name(self, pad=None) -> str:
        """Cell name for this device, optionally qualified by its pad style.

        Without the qualifier, building one device twice with different pads
        would ask KLayout for the same cell name twice.
        """
        return self.name if pad is None else f"{self.name}_{pad.tag()}"

    def terminal_directions(self):
        """Outward unit direction per terminal, as (dx, dy) in {-1, 0, 1}.

        Taken from where each terminal sits relative to the device's own
        bounding-box centre, snapped to the dominant axis. That covers every
        device here -- a bar's ends point left and right, a cross's four arms
        point at the compass points -- and an awkwardly shaped device can
        override it.

        Offset pads need this: a pad has to know which way "away from the
        device" is before it can be pushed there.
        """
        region = pya.Region()
        for poly in self.shapes():
            region.insert(poly)
        centre = region.bbox().center()
        out = []
        for box in self.terminals():
            tc = box.center()
            dx, dy = tc.x - centre.x, tc.y - centre.y
            if abs(dx) >= abs(dy):
                out.append((1 if dx > 0 else -1, 0))
            else:
                out.append((0, 1 if dy > 0 else -1))
        return out

    def pad_polygons(self, pad):
        """Every pad polygon for this device, in its own local frame."""
        out = []
        for box, direction in zip(self.terminals(), self.terminal_directions()):
            out.extend(pad.polygons_at(box, direction))
        return out

    def pads_bridge(self, pad) -> bool:
        """Would these pads merge into one, shorting the device?

        A pad wide enough to span two terminals joins them, and the resistor
        under it measures zero. That is the worst failure this library can
        emit -- not a wrong resistance but a dead device, found on a probe
        station weeks later -- so it is worth one cheap check.

        An offset pad clears this by construction, which is the whole reason
        offsetting exists.
        """
        region = pya.Region()
        terminals = self.terminals()
        for poly in self.pad_polygons(pad):
            region.insert(poly)
        region.merge()
        return region.count() < len(terminals)

    def build_cell(self, layout, layer, pad=None, pad_layer=None, name=None,
                   allow_bridged_pads=False):
        """Emit this device as a cell.

        The resistor goes on ``layer``. Pads, if given, go on ``pad_layer`` as
        a SEPARATE region -- they are a different film, usually thick Au over a
        thin resistive layer, so merging them into the resistor would both
        corrupt its geometry and put them on the wrong mask.

        Refuses to draw pads that merge across terminals; pass
        ``allow_bridged_pads=True`` if you genuinely want a pad plane.
        """
        if pad is not None and pad_layer is None:
            raise ValueError(
                "pads need their own layer: pass pad_layer. A pad is a "
                "different film from the resistor and does not belong on the "
                "resistor's mask.")
        if pad is not None and not allow_bridged_pads and self.pads_bridge(pad):
            raise ValueError(
                f"{self.name}: a {pad.size_um} um pad spans this device's "
                f"terminals, so the pads merge and short the resistor. Give "
                f"the pad an offset_um so it sits outside the device, or use "
                f"a smaller pad, or allow_bridged_pads=True.")

        cell = layout.create_cell(name or self.cell_name(pad))

        region = pya.Region()
        for poly in self.shapes():
            region.insert(poly)
        region.merge()
        for poly in region.each():
            cell.shapes(layer).insert(poly)

        if pad is not None:
            pad_region = pya.Region()
            for poly in self.pad_polygons(pad):
                pad_region.insert(poly)
            pad_region.merge()
            for poly in pad_region.each():
                cell.shapes(pad_layer).insert(poly)

        return cell


def merged(boxes) -> List["pya.Polygon"]:
    region = pya.Region()
    for box in boxes:
        region.insert(box)
    region.merge()
    return list(region.each())


def apply_corners(region, spec: CornerSpec, inner_um=0.0, outer_um=0.0):
    """Apply a corner treatment to a merged region.

    ``inner_um`` shapes CONCAVE corners, ``outer_um`` CONVEX ones -- KLayout's
    own split, which is why devices translate their intent into this pair: a
    serpentine bend is convex, a dogbone's neck-to-head junction is concave.

    TAPERED pins the point count at 8 because that is what produces a single
    45-degree edge. Fewer (4, 5) is measurably a no-op; more (12) starts
    approximating an actual arc.
    """
    if spec.style is Corner.SQUARE:
        return region
    region.merge()   # rounded_corners applies merged semantics
    n = 8 if spec.style is Corner.TAPERED else spec.arc_points
    return region.rounded_corners(um(inner_um), um(outer_um), n)
