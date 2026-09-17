"""The per-device summary table.

Returns lines instead of printing them, so the formatting is testable. Touches
only .name, .n_squares() and .pads_bridge() on each device, so it needs no pya
of its own.
"""

from typing import List


def report_lines(devices, process, pads=None) -> List[str]:
    """One line per device: square count, and a predicted R or why there isn't one.

    Three outcomes, kept distinct on purpose:
      - n_squares() is None  -> not a series element, extract R_s directly
      - process uncalibrated -> nobody has measured R_s yet
      - otherwise            -> a predicted resistance

    ``pads`` is an optional sequence aligned with ``devices``, one entry per
    device -- a Pad, or None for bare. Pass the ``pads`` from an Assembly and
    the table names the style each device actually got, which is what makes a
    mixed sweep readable and stops a missing pad going unnoticed.
    """
    out = []
    for i, d in enumerate(devices):
        n = d.n_squares()
        n_str = "   n/a" if n is None else f"{n:6.2f}"
        if n is None:
            note = "test structure -- extract R_s directly"
        elif not process.is_calibrated:
            note = "R_s not measured yet"
        else:
            note = f"{process.predict(n, n_contacts=2):.1f} ohm"
        line = f"{d.name:24s} squares={n_str}  {note}"
        if pads is not None:
            pad = pads[i] if i < len(pads) else None
            tag = pad.tag() if pad is not None else "NO PAD"
            line = f"{line:80s} {tag}"
        out.append(line)
    return out
