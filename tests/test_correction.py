"""Unit tests for the IB-mode correction math."""

from __future__ import annotations

import math

import pytest

from adc_winered.correction import _LENS_CONE_TAN, ib_targets, shortest_delta_deg


def test_zenith_no_dispersion_correction() -> None:
    """At zenith, z = 0, y = 0, a = 90 -> targets are r+90 and r-90."""
    t = ib_targets(elevation_deg=90.0, rotator_deg=0.0)
    # r = 90 - 0 = 90, a = 90 -> a = 90+180-90 = 180, b = 90-180+90 = 0
    assert t.a == pytest.approx(180.0)
    assert t.b == pytest.approx(0.0)


def test_low_altitude_saturates_at_cone_angle() -> None:
    """Below the lens cone half-angle (z >= 59.01°), y clamps at 1, a = 0,
    so both targets collapse to r±180."""
    # Elevation 20° => z = 70°; tan(70°)/tan(59.01°) > 1, so clamps.
    t = ib_targets(elevation_deg=20.0, rotator_deg=0.0)
    # r = 90, a = 0 -> a_target = 90+180 = 270, b_target = 90-180 = -90
    assert t.a == pytest.approx(270.0)
    assert t.b == pytest.approx(-90.0)


def test_at_cone_angle_boundary() -> None:
    """Exactly at z = 59.01°, y = 1, a = 0."""
    elevation = 90.0 - math.degrees(math.atan(_LENS_CONE_TAN))
    t = ib_targets(elevation_deg=elevation, rotator_deg=0.0)
    assert t.a == pytest.approx(270.0, abs=1e-9)
    assert t.b == pytest.approx(-90.0, abs=1e-9)


def test_rotator_only_shifts_both_targets_equally() -> None:
    """Changing only the rotator shifts both targets by the same -delta."""
    t0 = ib_targets(elevation_deg=60.0, rotator_deg=0.0)
    t1 = ib_targets(elevation_deg=60.0, rotator_deg=30.0)
    # r = 90 - rotator => +30° rotator => -30° on both targets
    assert (t1.a - t0.a) == pytest.approx(-30.0)
    assert (t1.b - t0.b) == pytest.approx(-30.0)


def test_targets_are_symmetric_around_r() -> None:
    """For any (elevation, rotator), (target_a + target_b) / 2 == r = 90 - rotator."""
    for el in [30.0, 45.0, 60.0, 75.0]:
        for rot in [-90.0, 0.0, 45.0, 180.0]:
            t = ib_targets(elevation_deg=el, rotator_deg=rot)
            assert (t.a + t.b) / 2.0 == pytest.approx(90.0 - rot)


def test_shortest_delta_basic() -> None:
    assert shortest_delta_deg(0.0, 10.0) == pytest.approx(10.0)
    assert shortest_delta_deg(0.0, -10.0) == pytest.approx(-10.0)
    assert shortest_delta_deg(350.0, 10.0) == pytest.approx(20.0)
    assert shortest_delta_deg(10.0, 350.0) == pytest.approx(-20.0)
    # Boundary: 180° apart -> -180 (either direction is equivalent).
    assert shortest_delta_deg(0.0, 180.0) == pytest.approx(-180.0)
    assert shortest_delta_deg(0.0, -180.0) == pytest.approx(-180.0)
