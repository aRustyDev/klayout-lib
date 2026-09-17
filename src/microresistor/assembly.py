"""Turning a device sweep plus a pad policy into cells.

A mask usually wants more than one pad style. A long bar is happiest with a pad
that simply overlaps its end; a short one cannot take that pad at all and needs
it moved outside on a lead. Mixing the two by hand means repeating the same
"does this fit?" reasoning at every entry in the sweep, and getting it wrong is
silent -- either a shorted device or a missing pad.

So: name a pad where you care, and let the plan decide where you do not.

    plan = PadPlan(overlap=Pad(size_um=40),
                   leaded=Pad(size_um=40, lead=Lead(length_um=30)))

    asm = build_cells(layout, metal, [
        StraightBar(10, 10),                      # AUTO -> leaded, too short
        StraightBar(200, 10),                     # AUTO -> overlap, it fits
        (GreekCross(...), plan.leaded),           # explicit
        (Dogbone(50, 4, 20), None),               # explicitly bare
    ], plan=plan, pad_layer=pads)

AUTO prefers the overlapping pad, because a direct overlap has no lead
resistance and no extra current constriction. It falls back to the leaded pad
only when the overlap would bridge the terminals and short the device, and to
no pad at all when neither fits.

This module imports no pya of its own -- it only calls methods on the devices
and pads handed to it -- so the policy is testable with stubs.
"""

from dataclasses import dataclass, field
from typing import List, Optional


class _Auto:
    """Sentinel: let the plan choose this device's pad by fit."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self):
        return "AUTO"


AUTO = _Auto()


@dataclass(frozen=True)
class PadPlan:
    """The pad styles a mask uses, and how to pick between them.

    Both are optional: a plan with only ``leaded`` set puts every automatic
    device on a lead, and an empty plan leaves every automatic device bare.
    """
    overlap: Optional["object"] = None
    leaded: Optional["object"] = None

    def resolve(self, device, choice=AUTO):
        """The pad this device should get.

        An explicit choice is honoured as given -- including ``None``, which
        means "draw this one bare" and is not the same as AUTO.
        """
        if choice is not AUTO:
            return choice
        for pad in (self.overlap, self.leaded):
            if pad is not None and not device.pads_bridge(pad):
                return pad
        return None

    def describe(self, device, choice=AUTO) -> str:
        """Why this device ended up with the pad it did -- for reports."""
        pad = self.resolve(device, choice)
        if pad is None:
            if choice is AUTO:
                return "no pad: every style in the plan would bridge"
            return "no pad: asked for"
        if choice is not AUTO:
            return f"{pad.tag()} (explicit)"
        if pad is self.overlap:
            return f"{pad.tag()} (auto: overlap fits)"
        return f"{pad.tag()} (auto: overlap would bridge)"


@dataclass
class Assembly:
    """What build_cells produced, kept aligned by index."""
    cells: List = field(default_factory=list)
    devices: List = field(default_factory=list)
    pads: List = field(default_factory=list)

    def __len__(self):
        return len(self.cells)

    @property
    def bare(self) -> List:
        """Devices that ended up with no pad at all."""
        return [d for d, p in zip(self.devices, self.pads) if p is None]


def build_cells(layout, layer, entries, plan=None, pad_layer=None,
                **build_kw) -> Assembly:
    """Build a cell per entry, resolving each device's pad through the plan.

    ``entries`` is an iterable of either a device, or a ``(device, choice)``
    pair where choice is a Pad, ``None`` for bare, or ``AUTO``.
    """
    plan = plan if plan is not None else PadPlan()
    out = Assembly()
    for entry in entries:
        if isinstance(entry, tuple):
            device, choice = entry
        else:
            device, choice = entry, AUTO
        pad = plan.resolve(device, choice)
        out.cells.append(device.build_cell(layout, layer, pad=pad,
                                           pad_layer=pad_layer, **build_kw))
        out.devices.append(device)
        out.pads.append(pad)
    return out
