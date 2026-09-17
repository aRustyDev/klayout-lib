"""Material and process -- everything the mask does not know.

No pya: a GDS file cannot hold resistivity, thickness or resistance, which is
exactly why these live apart from the geometry classes. Importable under plain
CPython, so the arithmetic here is unit-testable without KLayout.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Material(Enum):
    """Bulk room-temperature resistivity, ohm-metres.

    These are literature values for BULK material. They are not your film.
    A sputtered thin film runs higher than bulk because of grain-boundary
    and surface scattering, and the factor depends on thickness, deposition
    conditions and any subsequent anneal. Treat these as an order-of-
    magnitude sanity check only.

    Doped polysilicon, diffusion and n-well are deliberately absent: their
    resistivity is set by doping, so a single constant would be a fiction.
    """
    ALUMINUM = 2.65e-8
    COPPER = 1.68e-8
    GOLD = 2.44e-8
    TITANIUM = 4.20e-7
    NICHROME = 1.10e-6


@dataclass(frozen=True)
class Process:
    """Everything the mask does not know.

    Populate from your own measurements. sheet_resistance wins if given;
    otherwise it is derived from material and thickness_nm, with all the
    caveats in Material.__doc__.
    """
    sheet_resistance: Optional[float] = None   # ohm/square, measured
    contact_resistance: float = 0.0            # ohm per contact, measured
    thickness_nm: Optional[float] = None       # measured by profilometry
    material: Optional[Material] = None

    @property
    def r_s(self) -> float:
        if self.sheet_resistance is not None:
            return self.sheet_resistance
        if self.material is not None and self.thickness_nm is not None:
            return self.material.value / (self.thickness_nm * 1e-9)
        raise ValueError(
            "No sheet resistance available. Measure R_s (van der Pauw, or "
            "profilometry for t plus a probe-station R), or supply both "
            "material and thickness_nm."
        )

    @property
    def is_calibrated(self) -> bool:
        """True if r_s can be evaluated without raising.

        Ask this before calling predict(). Deliberately not folded into
        predict()'s return value: "this device has no square count" and
        "nobody has measured R_s yet" are different unknowns and should
        not both come back as None.
        """
        return (self.sheet_resistance is not None
                or (self.material is not None
                    and self.thickness_nm is not None))

    def predict(self, n_squares: float, n_contacts: int = 2) -> float:
        """R = R_s * N + n_contacts * R_contact.

        Requires is_calibrated and a real n_squares. Raises otherwise --
        a wrong resistance is worse than no resistance.
        """
        if n_squares is None:
            raise ValueError("no square count: not a two-terminal element")
        return self.r_s * n_squares + n_contacts * self.contact_resistance
