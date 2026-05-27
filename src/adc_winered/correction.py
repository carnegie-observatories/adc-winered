"""ADC dispersion-correction math.

Port of the IB-mode formula from the legacy reference implementation
(`/Users/william/workspace/adc/src/ADC/ADC_Controller.m:774-809`). Pure functions,
no I/O, no state — easy to unit-test and easy to extend with new modes.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# tan(59.01°): the lens cone half-angle baked into the original ADC optical design.
# Used to scale tan(zenith_distance) into the cos-domain prism-separation argument.
_LENS_CONE_TAN = math.tan(math.radians(59.01))


@dataclass(frozen=True, slots=True)
class RotatorTargets:
    """Target angles for the two prism rotators, in degrees."""

    a: float
    b: float


def ib_targets(elevation_deg: float, rotator_deg: float) -> RotatorTargets:
    """IB-mode prism angles for the given telescope state.

    elevation_deg: telescope elevation above horizon, degrees (0..90).
    rotator_deg:  telescope rotator / position angle, degrees.

    Returns the absolute rotator targets (target_A, target_B) in degrees. The
    caller decides what to do with them (compare to current encoder, dispatch
    a move, etc.).
    """
    z = 90.0 - elevation_deg
    # tan(z)/tan(59.01°), clamped at 1.0 below the lens cone half-angle: the
    # correction saturates and both prisms align (a = 0).
    y = min(1.0, math.tan(math.radians(z)) / _LENS_CONE_TAN)
    a = math.degrees(math.acos(y))
    r = 90.0 - rotator_deg
    return RotatorTargets(a=r + 180.0 - a, b=r - 180.0 + a)


def shortest_delta_deg(current: float, target: float) -> float:
    """Signed shortest angular distance from `current` to `target`, in [-180, 180).

    The boundary case (exactly 180° apart) returns -180 rather than +180. Either
    direction is the same physical rotation; the caller is expected to use the
    magnitude (`abs(...)`) for deadband comparisons.
    """
    return ((target - current + 180.0) % 360.0) - 180.0
