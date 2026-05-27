"""High-level controller: state machine + tracking loop.

The controller owns the live picture of the instrument (latest PLC snapshot,
latest TCS sample, latest computed targets, control mode, error). The WS layer
reads from it for `state` frames and dispatches commands into it as `cmd`
frames; nothing else mutates controller state.

State machine
-------------

```
        connect/start             stop
INIT  ─────────────────►  IDLE  ────►  STOPPED
                          │  ▲
              set AUTO    │  │  set OFF
                          ▼  │
                       TRACKING
                          │  ▲
                  errors  │  │  recover/reset
                          ▼  │
                        ERROR
```

`TRACKING` runs an internal periodic step at `control_interval_s`. Each step:
sample TCS → compute IB targets → for each axis, if `|delta| > deadband`,
issue `move_axis`. A move command lasts only until the PLC reports `done`;
the next step re-evaluates. Manual moves (`move_lens`) bypass the tracking
loop but stay subject to the same `MOVING` sanity check.
"""

from __future__ import annotations

import asyncio
import enum
import logging
from dataclasses import dataclass

from .correction import RotatorTargets, ib_targets, shortest_delta_deg
from .plc import (
    Axis,
    AxisStatus,
    PlcDriver,
    PlcSnapshot,
    PlcUnreachable,
    Slide,
    SlideState,
)
from .tcs import TcsDriver, TcsSample, TcsUnreachable

log = logging.getLogger(__name__)


class ControlMode(str, enum.Enum):
    AUTO = "auto"
    OFF = "off"


class ControllerState(str, enum.Enum):
    INIT = "init"
    IDLE = "idle"
    TRACKING = "tracking"
    ERROR = "error"
    STOPPED = "stopped"


@dataclass(frozen=True, slots=True)
class ControllerSnapshot:
    state: ControllerState
    mode: ControlMode
    plc: PlcSnapshot | None
    tcs: TcsSample | None
    targets: RotatorTargets | None
    last_error: str | None


class Controller:
    """Async controller. Lifecycle: ``start()`` → ``stop()``."""

    def __init__(
        self,
        plc: PlcDriver,
        tcs: TcsDriver,
        *,
        control_interval_s: float = 30.0,
        deadband_deg: float = 0.7,
        plc_poll_interval_s: float = 0.2,
        tcs_poll_interval_s: float = 1.0,
    ) -> None:
        self._plc = plc
        self._tcs = tcs
        self._interval = control_interval_s
        self._deadband = deadband_deg
        self._plc_poll = plc_poll_interval_s
        self._tcs_poll = tcs_poll_interval_s

        self._state = ControllerState.INIT
        self._mode = ControlMode.OFF
        self._plc_snapshot: PlcSnapshot | None = None
        self._tcs_sample: TcsSample | None = None
        self._targets: RotatorTargets | None = None
        self._last_error: str | None = None
        self._listeners: list[asyncio.Queue[ControllerSnapshot]] = []

        self._tasks: list[asyncio.Task[None]] = []
        self._track_event = asyncio.Event()  # set => run a tracking step now

    # --- lifecycle ------------------------------------------------------

    async def start(self) -> None:
        await self._plc.connect()
        await self._tcs.connect()
        self._state = ControllerState.IDLE
        self._tasks = [
            asyncio.create_task(self._plc_poll_loop(), name="adc-plc-poll"),
            asyncio.create_task(self._tcs_poll_loop(), name="adc-tcs-poll"),
            asyncio.create_task(self._tracking_loop(), name="adc-track"),
        ]
        await self._publish()

    async def stop(self) -> None:
        for t in self._tasks:
            t.cancel()
        for t in self._tasks:
            try:
                await t
            except asyncio.CancelledError:
                pass
        self._tasks = []
        await self._plc.close()
        await self._tcs.close()
        self._state = ControllerState.STOPPED
        await self._publish()

    # --- public command surface ----------------------------------------

    async def set_control_mode(self, mode: ControlMode) -> None:
        if mode is self._mode:
            return
        self._mode = mode
        if mode is ControlMode.AUTO and self._state is ControllerState.IDLE:
            self._state = ControllerState.TRACKING
            self._track_event.set()
        elif mode is ControlMode.OFF and self._state is ControllerState.TRACKING:
            self._state = ControllerState.IDLE
        await self._publish()

    async def move_axis_to(self, axis: Axis, target_deg: float) -> None:
        await self._plc.move_axis(axis, target_deg)

    async def set_slide(self, slide: Slide, deploy_in: bool) -> None:
        await self._plc.set_slide(slide, deploy_in)

    async def trigger_update(self) -> None:
        """One-shot recompute + dispatch (used by the WS `setAutoUpdate` cmd)."""
        self._track_event.set()

    def snapshot(self) -> ControllerSnapshot:
        return ControllerSnapshot(
            state=self._state,
            mode=self._mode,
            plc=self._plc_snapshot,
            tcs=self._tcs_sample,
            targets=self._targets,
            last_error=self._last_error,
        )

    def subscribe(self) -> asyncio.Queue[ControllerSnapshot]:
        """Returns a queue of `ControllerSnapshot` deltas. Used by the WS layer."""
        q: asyncio.Queue[ControllerSnapshot] = asyncio.Queue(maxsize=32)
        self._listeners.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[ControllerSnapshot]) -> None:
        if q in self._listeners:
            self._listeners.remove(q)

    # --- internal loops -------------------------------------------------

    async def _plc_poll_loop(self) -> None:
        while True:
            try:
                snap = await self._plc.read()
                self._plc_snapshot = snap
                await self._publish()
            except PlcUnreachable as exc:
                self._enter_error(f"plc_unreachable: {exc}")
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.exception("PLC poll failed")
                self._enter_error(f"plc_poll_error: {exc}")
            await asyncio.sleep(self._plc_poll)

    async def _tcs_poll_loop(self) -> None:
        while True:
            try:
                sample = await self._tcs.read()
                self._tcs_sample = sample
                await self._publish()
            except TcsUnreachable as exc:
                log.warning("TCS read failed: %s", exc)
                # TCS dropouts are not fatal — keep last sample, leave state alone.
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("TCS poll failed")
            await asyncio.sleep(self._tcs_poll)

    async def _tracking_loop(self) -> None:
        while True:
            try:
                # Sleep until interval elapses OR an external trigger fires.
                try:
                    await asyncio.wait_for(self._track_event.wait(), timeout=self._interval)
                except asyncio.TimeoutError:
                    pass
                self._track_event.clear()

                if self._state is not ControllerState.TRACKING:
                    continue
                if self._tcs_sample is None or self._plc_snapshot is None:
                    continue

                targets = ib_targets(self._tcs_sample.elevation_deg, self._tcs_sample.rotator_deg)
                self._targets = targets
                await self._maybe_move(Axis.A, self._plc_snapshot.axis_a, targets.a)
                await self._maybe_move(Axis.B, self._plc_snapshot.axis_b, targets.b)
                await self._publish()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.exception("tracking step failed")
                self._enter_error(f"tracking_error: {exc}")

    async def _maybe_move(self, axis: Axis, status: AxisStatus, target_deg: float) -> None:
        if status.busy:
            return  # let it finish; next step re-evaluates
        if abs(shortest_delta_deg(status.position_deg, target_deg)) <= self._deadband:
            return
        try:
            await self._plc.move_axis(axis, target_deg)
        except PlcUnreachable as exc:
            self._enter_error(f"plc_unreachable: {exc}")

    # --- helpers --------------------------------------------------------

    def _enter_error(self, message: str) -> None:
        self._state = ControllerState.ERROR
        self._last_error = message
        log.error(message)

    async def _publish(self) -> None:
        snap = self.snapshot()
        for q in list(self._listeners):
            try:
                q.put_nowait(snap)
            except asyncio.QueueFull:
                # Drop the oldest by clearing one slot, then push.
                try:
                    q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    q.put_nowait(snap)
                except asyncio.QueueFull:
                    pass


__all__ = [
    "ControlMode",
    "Controller",
    "ControllerSnapshot",
    "ControllerState",
    "SlideState",
]
