"""Make src/ importable however pytest was invoked.

Redundant when pytest runs from the repo root (pyproject sets pythonpath),
but it means `pytest tests/` works from any cwd.
"""

import os
import sys

_SRC = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)
