"""Database units and name sanitising.

No pya, no geometry -- importable under plain CPython.

DBU is the single source of truth for the database unit. um() closes over it,
and the runner assigns ``layout.dbu = DBU`` from this same constant, so the
conversion factor and the layout cannot drift apart.
"""

DBU = 0.001  # database unit in um -> 1 nm grid


def um(x):
    """Micrometres -> integer database units."""
    return int(round(x / DBU))


def tag(value):
    """Sanitise a number for use inside a GDS cell name."""
    return f"{value:g}".replace(".", "p").replace("-", "m")
