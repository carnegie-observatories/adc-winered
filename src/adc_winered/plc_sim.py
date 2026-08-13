"""In-process PLC simulator.

Same interface as `plc_client.PlcClient`. Models the two rotators as constant-
velocity slewers and the two slides as solenoids with a fixed settle time. The
shutter and milky-flat diffuser are plain outputs with no feedback, so the sim
just holds whatever was last commanded. Used by the controller, the WS protocol
tests, and end-to-end integration without any TwinCAT runtime.

This module deliberately does not import pyads — it must work on developer
laptops with no Beckhoff routing configured.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from .plc import (
    Axis,
    AxisStatus,
    PlcSnapshot,
    Slide,
    SlideState,
)


@dataclass(slots=True)
class _AxisSimState:
    position_deg: float = 0.0
    target_deg: float = 0.0
    busy: bool = False
    done: bool = True
    error: bool = False
    error_id: int = 0
    homed: bool = False


@dataclass(slots=True)
class _SlideSimState:
    deploy_in: bool = False
    state: SlideState = SlideState.OUT
    transition_at: float = 0.0  # monotonic deadline; 0 = idle


class PlcSim:
    """In-process simulator mirroring the FB_*Sim variants on the PLC side.

    Parameters set up the same way the controller would configure the real PLC:
    velocity in deg/s for the rotators, settle time in seconds for the slides.
    The simulation advances on each `read()` call from a single monotonic clock
    — no background tasks, no threads — which keeps tests deterministic.
    """

    def __init__(
        self,
        *,
        rotator_velocity_deg_s: float = 30.0,
        slide_settle_s: float = 0.5,
        clock: object | None = None,
    ) -> None:
        self._vel = rotator_velocity_deg_s
        self._settle = slide_settle_s
        self._clock = clock or time.monotonic
        self._last_tick = self._clock()
        self._a = _AxisSimState()
        self._b = _AxisSimState()
        self._slide_a = _SlideSimState()
        self._slide_b = _SlideSimState()
        # Shutter / milky flat are plain outputs on the PLC — no settle time,
        # no feedback — so the sim just holds the commanded value. Defaults
        # match the de-energized hardware state: shutter closed, diffuser in.
        self._shutter_closed = True
        self._milky_flat_deployed = True
        self._heartbeat = False
        self._connected = False

    async def connect(self) -> None:
        self._connected = True
        self._last_tick = self._clock()

    async def close(self) -> None:
        self._connected = False

    async def read(self) -> PlcSnapshot:
        self._advance()
        return PlcSnapshot(
            axis_a=self._snapshot_axis(self._a),
            axis_b=self._snapshot_axis(self._b),
            slide_a=self._slide_a.state,
            slide_b=self._slide_b.state,
            heartbeat=self._heartbeat,
            shutter_closed=self._shutter_closed,
            milky_flat_deployed=self._milky_flat_deployed,
        )

    async def move_axis(self, axis: Axis, target_deg: float) -> None:
        state = self._state_for(axis)
        state.target_deg = target_deg
        state.busy = True
        state.done = False
        state.error = False
        state.error_id = 0

    async def stop_axis(self, axis: Axis) -> None:
        state = self._state_for(axis)
        # Freeze where we are right now.
        self._advance()
        state.target_deg = state.position_deg
        state.busy = False
        state.done = True

    async def home_axis(self, axis: Axis) -> None:
        # Homing in the sim snaps position to 0 instantly and reports done.
        state = self._state_for(axis)
        state.position_deg = 0.0
        state.target_deg = 0.0
        state.busy = False
        state.done = True
        state.error = False
        state.error_id = 0
        state.homed = True

    async def reset_axis(self, axis: Axis) -> None:
        state = self._state_for(axis)
        state.error = False
        state.error_id = 0

    async def set_slide(self, slide: Slide, deploy_in: bool) -> None:
        sim = self._slide_for(slide)
        if sim.deploy_in == deploy_in and sim.state in (SlideState.IN, SlideState.OUT):
            target = SlideState.IN if deploy_in else SlideState.OUT
            if sim.state == target:
                return
        sim.deploy_in = deploy_in
        sim.state = SlideState.MOVING
        sim.transition_at = self._clock() + self._settle

    async def set_shutter(self, closed: bool) -> None:
        self._shutter_closed = bool(closed)

    async def set_milky_flat(self, deploy_in: bool) -> None:
        self._milky_flat_deployed = bool(deploy_in)

    # --- helpers --------------------------------------------------------

    def _state_for(self, axis: Axis) -> _AxisSimState:
        return self._a if axis is Axis.A else self._b

    def _slide_for(self, slide: Slide) -> _SlideSimState:
        return self._slide_a if slide is Slide.A else self._slide_b

    def _snapshot_axis(self, s: _AxisSimState) -> AxisStatus:
        return AxisStatus(
            position_deg=s.position_deg,
            busy=s.busy,
            done=s.done,
            error=s.error,
            error_id=s.error_id,
            ready=s.homed and not s.error,
        )

    def _advance(self) -> None:
        now = self._clock()
        dt = max(0.0, now - self._last_tick)
        self._last_tick = now
        self._heartbeat = not self._heartbeat
        self._advance_axis(self._a, dt)
        self._advance_axis(self._b, dt)
        self._advance_slide(self._slide_a, now)
        self._advance_slide(self._slide_b, now)

    def _advance_axis(self, s: _AxisSimState, dt: float) -> None:
        if not s.busy:
            return
        delta = s.target_deg - s.position_deg
        max_step = self._vel * dt
        if abs(delta) <= max_step:
            s.position_deg = s.target_deg
            s.busy = False
            s.done = True
            return
        s.position_deg += max_step if delta > 0 else -max_step

    def _advance_slide(self, s: _SlideSimState, now: float) -> None:
        if s.state != SlideState.MOVING:
            return
        if now >= s.transition_at:
            s.state = SlideState.IN if s.deploy_in else SlideState.OUT
            s.transition_at = 0.0


__all__ = ["PlcSim"]
