"""Make `wr_mechanisms` importable when the suite is run from the repo root.

The Pi package is a separate project (`rpi/pyproject.toml`) that is never
installed into the ADC server's venv, so `uv run pytest rpi/tests` needs the
package directory on the path.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
