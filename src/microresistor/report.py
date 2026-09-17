"""The per-device summary table.

Returns lines instead of printing them, so the formatting is testable. Touches
only .name, .n_squares() and .pads_bridge() on each device, so it needs no pya
of its own.
"""

from typing import List


def report_lines(devices, process, pad=None) -> List[str]:
    """One line per device: square count, and a predicted R or why there isn't one.

    Three outcomes, kept distinct on purpose:
      - n_squares() is None  -> not a series element, extract R_s directly
      - process uncalibrated -> nobody has measured R_s yet
      - otherwise            -> a predicted resistance

    Pass ``pad`` to have the table say which devices cannot take it. A device
    silently missing its pads is exactly the kind of thing you notice weeks
    later on a probe station, so it gets said out loud here.
    """
    out = []
    for d in devices:
        n = d.n_squares()
        n_str = "   n/a" if n is None else f"{n:6.2f}"
        if n is None:
            note = "test structure -- extract R_s directly"
        elif not process.is_calibrated:
            note = "R_s not measured yet"
        else:
            note = f"{process.predict(n, n_contacts=2):.1f} ohm"
        if pad is not None and d.pads_bridge(pad):
            note += "  [NO PAD: would bridge and short]"
        out.append(f"{d.name:24s} squares={n_str}  {note}")
    return out
