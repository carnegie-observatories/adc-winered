"""ADS PLC client.

Thin async wrapper around `pyads`. All blocking ADS calls run via
`asyncio.to_thread` so the controller's event loop stays responsive. The PLC
clears the per-axis `bGo` rising-edge bits after consuming them — the caller
just writes target + sets `bGo := TRUE`.

Symbol names mirror the GVL layout in `plc/adc/adc/GVLs/`.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pyads

from .plc import (
    Axis,
    AxisStatus,
    PlcSnapshot,
    PlcUnreachable,
    Slide,
    SlideState,
)

_STATE_BY_INT: dict[int, SlideState] = {
    0: SlideState.OUT,
    1: SlideState.IN,
    2: SlideState.MOVING,
    3: SlideState.ERROR,
}

_AXIS_SYMBOLS = {
    Axis.A: {
        "position": "GVL_State.rAxisA_Position",
        "busy": "GVL_State.bAxisA_Busy",
        "done": "GVL_State.bAxisA_Done",
        "error": "GVL_State.bAxisA_Error",
        "error_id": "GVL_State.nAxisA_ErrorId",
        "ready": "GVL_State.bAxisA_Ready",
        "target": "GVL_Cmd.rAxisA_Target",
        "go": "GVL_Cmd.bAxisA_Go",
        "stop": "GVL_Cmd.bAxisA_Stop",
        "home": "GVL_Cmd.bAxisA_Home",
        "reset": "GVL_Cmd.bAxisA_Reset",
    },
    Axis.B: {
        "position": "GVL_State.rAxisB_Position",
        "busy": "GVL_State.bAxisB_Busy",
        "done": "GVL_State.bAxisB_Done",
        "error": "GVL_State.bAxisB_Error",
        "error_id": "GVL_State.nAxisB_ErrorId",
        "ready": "GVL_State.bAxisB_Ready",
        "target": "GVL_Cmd.rAxisB_Target",
        "go": "GVL_Cmd.bAxisB_Go",
        "stop": "GVL_Cmd.bAxisB_Stop",
        "home": "GVL_Cmd.bAxisB_Home",
        "reset": "GVL_Cmd.bAxisB_Reset",
    },
}

_SLIDE_SYMBOLS = {
    Slide.A: {"state": "GVL_State.eSlideA", "deploy": "GVL_Cmd.bSlideA_Deploy"},
    Slide.B: {"state": "GVL_State.eSlideB", "deploy": "GVL_Cmd.bSlideB_Deploy"},
}

# Shutter / milky flat: plain DOs on the EL2084, no feedback sensors. The
# GVL_State bits echo the command. Both channels are wired so that the PLC
# de-energizes the output to reach the named condition — that inversion lives
# in FB_AdcController, so these symbols read in physical terms.
_SHUTTER_STATE = "GVL_State.bShutter_Closed"
_SHUTTER_CMD = "GVL_Cmd.bShutter_Closed"
_MILKY_FLAT_STATE = "GVL_State.bMilkyFlat_Deployed"
_MILKY_FLAT_CMD = "GVL_Cmd.bMilkyFlat_Deploy"

_HEARTBEAT = "GVL_State.bHeartbeat"


class PlcClient:
    """Real PLC backend over Beckhoff ADS."""

    def __init__(
        self,
        ams_net_id: str,
        ams_port: int = 851,
        host: str | None = None,
        local_ams_net_id: str | None = None,
    ) -> None:
        """`host` is where the TCP connection goes; `ams_net_id` is who we ask
        for once connected. They are independent — this PLC answers to
        5.171.247.155.1.1 while living at 10.7.45.150 — and pyads defaults
        `host` to the Net ID's first four octets, which is wrong both there and
        through an SSH tunnel. Pass it explicitly.

        `local_ams_net_id` is our own AMS Net ID; the PLC accepts the session
        only if it has a route matching it (see docs/bring-up.md).
        """
        self._ams_net_id = ams_net_id
        self._ams_port = ams_port
        self._host = host
        self._local_ams_net_id = local_ams_net_id
        self._plc: pyads.Connection | None = None

    async def connect(self) -> None:
        def _open() -> pyads.Connection:
            if self._local_ams_net_id:
                # Despite the "Linux only" docstring, this works on macOS too
                # (verified against pyads 3.5.2 / adslib on Darwin arm64).
                pyads.open_port()
                pyads.set_local_address(self._local_ams_net_id)
                pyads.close_port()
            conn = pyads.Connection(
                self._ams_net_id, self._ams_port, ip_address=self._host or None
            )
            conn.open()
            return conn

        try:
            self._plc = await asyncio.to_thread(_open)
        except pyads.ADSError as exc:
            raise PlcUnreachable(f"could not open ADS connection: {exc}") from exc

    async def close(self) -> None:
        plc, self._plc = self._plc, None
        if plc is not None:
            await asyncio.to_thread(plc.close)

    async def read(self) -> PlcSnapshot:
        plc = self._require_connection()

        def _read_all() -> dict[str, Any]:
            return {
                **{f"a_{k}": plc.read_by_name(v) for k, v in _AXIS_SYMBOLS[Axis.A].items()
                   if k in ("position", "busy", "done", "error", "error_id", "ready")},
                **{f"b_{k}": plc.read_by_name(v) for k, v in _AXIS_SYMBOLS[Axis.B].items()
                   if k in ("position", "busy", "done", "error", "error_id", "ready")},
                "slide_a": plc.read_by_name(_SLIDE_SYMBOLS[Slide.A]["state"]),
                "slide_b": plc.read_by_name(_SLIDE_SYMBOLS[Slide.B]["state"]),
                "shutter_closed": plc.read_by_name(_SHUTTER_STATE),
                "milky_flat_deployed": plc.read_by_name(_MILKY_FLAT_STATE),
                "heartbeat": plc.read_by_name(_HEARTBEAT),
            }

        try:
            vals = await asyncio.to_thread(_read_all)
        except pyads.ADSError as exc:
            raise PlcUnreachable(f"ADS read failed: {exc}") from exc

        return PlcSnapshot(
            axis_a=AxisStatus(
                position_deg=float(vals["a_position"]),
                busy=bool(vals["a_busy"]),
                done=bool(vals["a_done"]),
                error=bool(vals["a_error"]),
                error_id=int(vals["a_error_id"]),
                ready=bool(vals["a_ready"]),
            ),
            axis_b=AxisStatus(
                position_deg=float(vals["b_position"]),
                busy=bool(vals["b_busy"]),
                done=bool(vals["b_done"]),
                error=bool(vals["b_error"]),
                error_id=int(vals["b_error_id"]),
                ready=bool(vals["b_ready"]),
            ),
            slide_a=_STATE_BY_INT.get(int(vals["slide_a"]), SlideState.ERROR),
            slide_b=_STATE_BY_INT.get(int(vals["slide_b"]), SlideState.ERROR),
            heartbeat=bool(vals["heartbeat"]),
            shutter_closed=bool(vals["shutter_closed"]),
            milky_flat_deployed=bool(vals["milky_flat_deployed"]),
        )

    async def move_axis(self, axis: Axis, target_deg: float) -> None:
        syms = _AXIS_SYMBOLS[axis]
        await self._write_many({syms["target"]: float(target_deg), syms["go"]: True})

    async def stop_axis(self, axis: Axis) -> None:
        await self._write_many({_AXIS_SYMBOLS[axis]["stop"]: True})

    async def home_axis(self, axis: Axis) -> None:
        await self._write_many({_AXIS_SYMBOLS[axis]["home"]: True})

    async def reset_axis(self, axis: Axis) -> None:
        await self._write_many({_AXIS_SYMBOLS[axis]["reset"]: True})

    async def set_slide(self, slide: Slide, deploy_in: bool) -> None:
        await self._write_many({_SLIDE_SYMBOLS[slide]["deploy"]: bool(deploy_in)})

    async def set_shutter(self, closed: bool) -> None:
        await self._write_many({_SHUTTER_CMD: bool(closed)})

    async def set_milky_flat(self, deploy_in: bool) -> None:
        await self._write_many({_MILKY_FLAT_CMD: bool(deploy_in)})

    # --- helpers --------------------------------------------------------

    def _require_connection(self) -> pyads.Connection:
        if self._plc is None:
            raise PlcUnreachable("PLC client is not connected")
        return self._plc

    async def _write_many(self, values: dict[str, Any]) -> None:
        plc = self._require_connection()

        def _write() -> None:
            for symbol, value in values.items():
                plc.write_by_name(symbol, value)

        try:
            await asyncio.to_thread(_write)
        except pyads.ADSError as exc:
            raise PlcUnreachable(f"ADS write failed: {exc}") from exc
