"""Controller state-machine and tracking-loop tests.

All tests run against `PlcSim` + `TcsSim` — no hardware. Time is squeezed by
using a short `control_interval_s` so the tracking loop actually fires.
"""

from __future__ import annotations

import asyncio

import pytest

from adc_winered.controller import (
    ControlMode,
    Controller,
    ControllerState,
)
from adc_winered.plc import Axis, Slide, SlideState
from adc_winered.plc_sim import PlcSim
from adc_winered.tcs_sim import TcsSim


async def _wait_until(predicate, timeout: float = 2.0, poll_s: float = 0.02) -> None:
    """Spin until predicate is true or we time out. Keeps tests resilient to scheduling."""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        if predicate():
            return
        await asyncio.sleep(poll_s)
    raise AssertionError("predicate never became true within timeout")


@pytest.fixture
async def ctrl():
    plc = PlcSim(rotator_velocity_deg_s=180.0, slide_settle_s=0.05)
    tcs = TcsSim(elevation_deg=60.0, rotator_deg=0.0)
    c = Controller(
        plc, tcs,
        control_interval_s=0.05,
        deadband_deg=0.5,
        plc_poll_interval_s=0.02,
        tcs_poll_interval_s=0.02,
    )
    await c.start()
    yield c, plc, tcs
    await c.stop()


async def test_start_goes_to_idle(ctrl) -> None:
    c, _, _ = ctrl
    await _wait_until(lambda: c.snapshot().state is ControllerState.IDLE)
    assert c.snapshot().mode is ControlMode.OFF


async def test_set_auto_transitions_to_tracking_and_publishes_targets(ctrl) -> None:
    c, _, _ = ctrl
    await _wait_until(lambda: c.snapshot().tcs is not None)
    await c.set_control_mode(ControlMode.AUTO)
    assert c.snapshot().state is ControllerState.TRACKING
    await _wait_until(lambda: c.snapshot().targets is not None)


async def test_tracking_dispatches_moves_to_close_deadband(ctrl) -> None:
    c, plc, _ = ctrl
    await _wait_until(lambda: c.snapshot().tcs is not None)
    await c.set_control_mode(ControlMode.AUTO)
    # At elevation 60°, rotator 0°, IB targets are r±180-a; neither is 0, so axis A
    # must converge away from 0.
    await _wait_until(
        lambda: (
            c.snapshot().plc is not None
            and c.snapshot().targets is not None
            and abs(c.snapshot().plc.axis_a.position_deg - c.snapshot().targets.a) <= 0.5
        ),
        timeout=4.0,
    )


async def test_set_off_returns_to_idle_and_stops_dispatching(ctrl) -> None:
    c, plc, _ = ctrl
    await _wait_until(lambda: c.snapshot().tcs is not None)
    await c.set_control_mode(ControlMode.AUTO)
    await _wait_until(
        lambda: (
            c.snapshot().plc is not None
            and c.snapshot().targets is not None
            and c.snapshot().plc.axis_a.done is True
            and abs(c.snapshot().plc.axis_a.position_deg - c.snapshot().targets.a) <= 0.5
        ),
        timeout=4.0,
    )
    await c.set_control_mode(ControlMode.OFF)
    assert c.snapshot().state is ControllerState.IDLE

    # Move the TCS to a very different state; the controller must NOT move the axis.
    snap_before = c.snapshot().plc.axis_a.position_deg
    tcs_sim = ctrl[2]
    tcs_sim.set_state(elevation_deg=30.0, rotator_deg=120.0)
    await asyncio.sleep(0.2)
    snap_after = c.snapshot().plc.axis_a.position_deg
    assert snap_before == pytest.approx(snap_after, abs=0.5)


async def test_manual_move_works_in_idle(ctrl) -> None:
    c, _, _ = ctrl
    await _wait_until(lambda: c.snapshot().state is ControllerState.IDLE)
    await c.move_axis_to(Axis.A, 45.0)
    await _wait_until(
        lambda: c.snapshot().plc is not None
        and abs(c.snapshot().plc.axis_a.position_deg - 45.0) < 0.5,
        timeout=2.0,
    )


async def test_set_slide_transitions(ctrl) -> None:
    c, _, _ = ctrl
    await _wait_until(lambda: c.snapshot().plc is not None)
    await c.set_slide(Slide.A, deploy_in=True)
    await _wait_until(
        lambda: c.snapshot().plc is not None and c.snapshot().plc.slide_a is SlideState.IN,
        timeout=1.0,
    )


async def test_subscribe_receives_snapshots(ctrl) -> None:
    c, _, _ = ctrl
    queue = c.subscribe()
    try:
        # Trigger a state change.
        await c.set_control_mode(ControlMode.AUTO)
        snap = await asyncio.wait_for(queue.get(), timeout=1.0)
        # Multiple snapshots may arrive — at least one of them is in TRACKING.
        states = [snap.state]
        while not queue.empty():
            states.append(queue.get_nowait().state)
        assert ControllerState.TRACKING in states
    finally:
        c.unsubscribe(queue)


async def test_deadband_suppresses_redundant_moves(ctrl) -> None:
    c, plc, tcs_sim = ctrl
    await _wait_until(lambda: c.snapshot().tcs is not None)
    await c.set_control_mode(ControlMode.AUTO)
    await _wait_until(
        lambda: (
            c.snapshot().plc is not None
            and c.snapshot().targets is not None
            and abs(c.snapshot().plc.axis_a.position_deg - c.snapshot().targets.a) <= 0.5
        ),
        timeout=4.0,
    )
    # Now nudge the TCS rotator by 0.1° — well inside the 0.5° deadband.
    cur = c.snapshot().tcs.rotator_deg
    tcs_sim.set_state(elevation_deg=c.snapshot().tcs.elevation_deg, rotator_deg=cur + 0.1)
    # Capture position, wait a few tracking cycles, verify it didn't move.
    pos_before = c.snapshot().plc.axis_a.position_deg
    await asyncio.sleep(0.2)
    pos_after = c.snapshot().plc.axis_a.position_deg
    assert pos_before == pytest.approx(pos_after, abs=0.2)
