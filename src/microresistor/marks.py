"""Alignment marks and the die outline.

Once a mask set has more than one patterned layer it needs marks, or the
layers cannot be registered to each other. This library grew a second layer the
moment pads moved off the resistor layer, so these are not decoration.

Two things are provided, and they do different jobs:

  cross()            a big solid cross, for the aligner to find. Coarse.
  box_in_box()       a frame on one layer and a smaller filled box on the
                     other. Misregistration shows as an asymmetric gap, and it
                     is read after the fact to measure how well you did.

The die outline is a different animal again: it is not a mark and usually not
even printed. It records where the die ends, which is what a dicing lane and a
floorplan are measured against.

Everything here is centred on the origin and returns polygons in database
units, so the caller places them.
"""

try:  # KLayout runtime
    import pya  # type: ignore
except ImportError:  # pragma: no cover - plain Python import path
    import klayout.db as pya  # type: ignore

from typing import List

from .units import um


def cross(size_um: float, arm_width_um: float) -> List["pya.Polygon"]:
    """A solid cross, ``size_um`` tip to tip, centred on the origin."""
    if arm_width_um >= size_um:
        raise ValueError("arm_width_um must be smaller than size_um")
    half, harm = um(size_um) // 2, um(arm_width_um) // 2
    region = pya.Region()
    region.insert(pya.Box(-half, -harm, half, harm))
    region.insert(pya.Box(-harm, -half, harm, half))
    region.merge()
    return list(region.each())


def frame(outer_um: float, wall_um: float) -> List["pya.Polygon"]:
    """A hollow square frame: ``outer_um`` across, walls ``wall_um`` thick."""
    if wall_um * 2 >= outer_um:
        raise ValueError("wall_um * 2 must be smaller than outer_um")
    half = um(outer_um) // 2
    inner = half - um(wall_um)
    region = pya.Region(pya.Box(-half, -half, half, half))
    region -= pya.Region(pya.Box(-inner, -inner, inner, inner))
    return list(region.each())


def filled_box(size_um: float) -> List["pya.Polygon"]:
    """A solid square, ``size_um`` across, centred on the origin."""
    half = um(size_um) // 2
    return [pya.Polygon(pya.Box(-half, -half, half, half))]


def box_in_box(outer_um: float = 60.0, wall_um: float = 5.0,
               inner_um: float = 40.0):
    """A registration pair: (frame for layer A, box for layer B).

    Perfectly aligned, the gap between the frame's inner wall and the box is
    equal on all four sides; the asymmetry when it is not IS the measurement.
    """
    gap = (outer_um - 2 * wall_um - inner_um) / 2.0
    if gap <= 0:
        raise ValueError(
            f"inner box {inner_um} leaves no gap inside a {outer_um} frame "
            f"with {wall_um} walls")
    return frame(outer_um, wall_um), filled_box(inner_um)


def build_mark_cell(layout, name: str, layer_shapes) -> "pya.Cell":
    """A cell holding one mark set.

    ``layer_shapes`` is a sequence of (layer_index, polygons) so a single mark
    can span layers -- which is the point of box_in_box.
    """
    cell = layout.create_cell(name)
    for layer, polygons in layer_shapes:
        for poly in polygons:
            cell.shapes(layer).insert(poly)
    return cell


def alignment_marks(layout, primary_layer, secondary_layer,
                    size_um: float = 100.0, arm_width_um: float = 10.0,
                    name: str = "ALIGN") -> "pya.Cell":
    """A ready-made mark set for a two-layer process.

    Coarse cross on the primary layer for the aligner to acquire, plus a
    box-in-box straddling both layers to measure the residual offset.
    """
    outer, inner = box_in_box()
    span = um(size_um)
    shifted_frame = [p.moved(span, 0) for p in outer]
    shifted_box = [p.moved(span, 0) for p in inner]
    return build_mark_cell(layout, name, [
        (primary_layer, cross(size_um, arm_width_um) + shifted_frame),
        (secondary_layer, shifted_box),
    ])


def die_outline(layout, cell, layer, width_um: float, height_um: float,
                centre=(0.0, 0.0)) -> "pya.Box":
    """Draw a die boundary rectangle and return it.

    Conventionally a non-printing layer: it records where the die ends for
    dicing and floorplanning rather than describing anything to pattern.
    """
    if width_um <= 0 or height_um <= 0:
        raise ValueError("die dimensions must be positive")
    cx, cy = um(centre[0]), um(centre[1])
    half_w, half_h = um(width_um) // 2, um(height_um) // 2
    box = pya.Box(cx - half_w, cy - half_h, cx + half_w, cy + half_h)
    cell.shapes(layer).insert(box)
    return box


def fits_in_die(content: "pya.Box", die: "pya.Box") -> bool:
    """Does everything drawn actually sit inside the die boundary?"""
    return die.contains(content.p1) and die.contains(content.p2)
