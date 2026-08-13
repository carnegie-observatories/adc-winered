"""Shared PLC driver interface and data shapes.

`PlcDriver` is a Protocol implemented by both `plc_client.PlcClient` (real
hardware over ADS) and `plc_sim.PlcSim` (in-process fake). The controller and
the WS server only depend on this interface, so swapping real/sim at startup
is a config flag.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Protocol


class Axis(str, enum.Enum):
    A = "A"
    B = "B"


class Slide(str, enum.Enum):
    A = "A"
    B = "B"


class SlideState(str, enum.Enum):
    IN = "in"
    OUT = "out"
    MOVING = "moving"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class AxisStatus:
    position_deg: float
    busy: bool
    done: bool
    error: bool
    error_id: int
    # True when the axis has been successfully homed and is not in error.
    # Callers needing absolute position (e.g. the tracking loop) should refuse
    # to dispatch a move when `ready` is False.
    ready: bool = False


@dataclass(frozen=True, slots=True)
class PlcSnapshot:
    axis_a: AxisStatus
    axis_b: AxisStatus
    slide_a: SlideState
    slide_b: SlideState
    heartbeat: bool
    # Shutter and milky-flat diffuser have no position feedback — the PLC
    # echoes back the commanded state, so these are requests, not measurements.
    shutter_closed: bool = False
    milky_flat_deployed: bool = False


class PlcUnreachable(RuntimeError):
    """Raised when the PLC connection drops or is unavailable."""


class PlcDriver(Protocol):
    """Contract between the controller and any PLC backend (real or sim)."""

    async def connect(self) -> None: ...
    async def close(self) -> None: ...

    async def read(self) -> PlcSnapshot:
        """One-shot read of GVL_State."""

    async def move_axis(self, axis: Axis, target_deg: float) -> None:
        """Write target + pulse the Go bit. Returns immediately (non-blocking)."""

    async def stop_axis(self, axis: Axis) -> None: ...
    async def home_axis(self, axis: Axis) -> None: ...
    async def reset_axis(self, axis: Axis) -> None: ...

    async def set_slide(self, slide: Slide, deploy_in: bool) -> None:
        """deploy_in=True drives the solenoid to the IN position."""

    async def set_shutter(self, closed: bool) -> None:
        """closed=True closes the shutter (EL2084 ch.1 de-energized)."""

    async def set_milky_flat(self, deploy_in: bool) -> None:
        """deploy_in=True puts the diffuser in the beam (EL2084 ch.2 de-energized)."""
