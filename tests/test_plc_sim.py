"""PLC simulator tests — exercise the same interface the controller uses."""

from __future__ import annotations

import pytest

from adc_winered.plc import Axis, Slide, SlideState
from adc_winered.plc_sim import PlcSim


class FakeClock:
    """Monotonic clock that only advances when we say so. Keeps timing tests deterministic."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, dt: float) -> None:
        self.now += dt


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
async def sim(clock: FakeClock) -> PlcSim:
    s = PlcSim(rotator_velocity_deg_s=30.0, slide_settle_s=0.5, clock=clock)
    await s.connect()
    return s


async def test_initial_state_is_idle_at_zero(sim: PlcSim) -> None:
    snap = await sim.read()
    assert snap.axis_a.position_deg == 0.0
    assert snap.axis_a.done is True
    assert snap.axis_a.busy is False
    assert snap.slide_a is SlideState.OUT
    assert snap.slide_b is SlideState.OUT


async def test_move_axis_slews_at_velocity(clock: FakeClock, sim: PlcSim) -> None:
    await sim.move_axis(Axis.A, 90.0)
    # After 1 second at 30 deg/s: position == 30°, still moving.
    clock.advance(1.0)
    snap = await sim.read()
    assert snap.axis_a.position_deg == pytest.approx(30.0)
    assert snap.axis_a.busy is True
    assert snap.axis_a.done is False

    # After another 2 seconds: arrived at 90°, done.
    clock.advance(2.0)
    snap = await sim.read()
    assert snap.axis_a.position_deg == pytest.approx(90.0)
    assert snap.axis_a.busy is False
    assert snap.axis_a.done is True


async def test_move_axis_b_independent_of_a(clock: FakeClock, sim: PlcSim) -> None:
    await sim.move_axis(Axis.A, 60.0)
    await sim.move_axis(Axis.B, -30.0)
    clock.advance(1.0)
    snap = await sim.read()
    assert snap.axis_a.position_deg == pytest.approx(30.0)
    assert snap.axis_b.position_deg == pytest.approx(-30.0)
    assert snap.axis_b.done is True


async def test_stop_axis_freezes_in_place(clock: FakeClock, sim: PlcSim) -> None:
    await sim.move_axis(Axis.A, 90.0)
    clock.advance(1.0)  # got to ~30°
    await sim.stop_axis(Axis.A)
    snap_after_stop = await sim.read()
    clock.advance(5.0)
    snap_later = await sim.read()
    assert snap_later.axis_a.position_deg == pytest.approx(snap_after_stop.axis_a.position_deg)
    assert snap_later.axis_a.done is True


async def test_home_snaps_to_zero(clock: FakeClock, sim: PlcSim) -> None:
    await sim.move_axis(Axis.A, 90.0)
    clock.advance(10.0)
    await sim.home_axis(Axis.A)
    snap = await sim.read()
    assert snap.axis_a.position_deg == 0.0
    assert snap.axis_a.done is True


async def test_ready_is_false_until_homed(sim: PlcSim) -> None:
    snap = await sim.read()
    assert snap.axis_a.ready is False
    assert snap.axis_b.ready is False

    await sim.home_axis(Axis.A)
    snap = await sim.read()
    assert snap.axis_a.ready is True
    # Axis B hasn't been homed yet — still not ready.
    assert snap.axis_b.ready is False

    await sim.home_axis(Axis.B)
    snap = await sim.read()
    assert snap.axis_b.ready is True


async def test_slide_transitions_through_moving(clock: FakeClock, sim: PlcSim) -> None:
    await sim.set_slide(Slide.A, deploy_in=True)
    snap = await sim.read()
    assert snap.slide_a is SlideState.MOVING

    # Mid-settle: still moving.
    clock.advance(0.2)
    snap = await sim.read()
    assert snap.slide_a is SlideState.MOVING

    # Past settle: arrived IN.
    clock.advance(0.5)
    snap = await sim.read()
    assert snap.slide_a is SlideState.IN

    # Retract: MOVING -> OUT.
    await sim.set_slide(Slide.A, deploy_in=False)
    snap = await sim.read()
    assert snap.slide_a is SlideState.MOVING
    clock.advance(1.0)
    snap = await sim.read()
    assert snap.slide_a is SlideState.OUT


async def test_heartbeat_toggles_each_read(sim: PlcSim) -> None:
    h1 = (await sim.read()).heartbeat
    h2 = (await sim.read()).heartbeat
    h3 = (await sim.read()).heartbeat
    assert h1 != h2
    assert h2 != h3


async def test_plc_sim_satisfies_driver_protocol(sim: PlcSim) -> None:
    """PlcSim must be assignable to PlcDriver (structural Protocol check)."""
    from adc_winered.plc import PlcDriver

    driver: PlcDriver = sim
    assert driver is sim
