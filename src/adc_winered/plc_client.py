"""ADS PLC client.

Thin async wrapper around `pyads`. All blocking ADS calls run via
`asyncio.to_thread` so the controller's event loop stays responsive. The PLC
clears the per-axis `bGo` rising-edge bits after consuming them — the caller
just writes target + sets `bGo := TRUE`.

Symbol names mirror the GVL layout in `plc/WineredADC/GVLs/`.
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

_HEARTBEAT = "GVL_State.bHeartbeat"


class PlcClient:
    """Real PLC backend over Beckhoff ADS."""

    def __init__(self, ams_net_id: str, ams_port: int = 851, ip: str | None = None) -> None:
        self._ams_net_id = ams_net_id
        self._ams_port = ams_port
        self._ip = ip
        self._plc: pyads.Connection | None = None

    async def connect(self) -> None:
        def _open() -> pyads.Connection:
            if self._ip:
                pyads.set_local_address(self._ip)
            conn = pyads.Connection(self._ams_net_id, self._ams_port)
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
                   if k in ("position", "busy", "done", "error", "error_id")},
                **{f"b_{k}": plc.read_by_name(v) for k, v in _AXIS_SYMBOLS[Axis.B].items()
                   if k in ("position", "busy", "done", "error", "error_id")},
                "slide_a": plc.read_by_name(_SLIDE_SYMBOLS[Slide.A]["state"]),
                "slide_b": plc.read_by_name(_SLIDE_SYMBOLS[Slide.B]["state"]),
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
            ),
            axis_b=AxisStatus(
                position_deg=float(vals["b_position"]),
                busy=bool(vals["b_busy"]),
                done=bool(vals["b_done"]),
                error=bool(vals["b_error"]),
                error_id=int(vals["b_error_id"]),
            ),
            slide_a=_STATE_BY_INT.get(int(vals["slide_a"]), SlideState.ERROR),
            slide_b=_STATE_BY_INT.get(int(vals["slide_b"]), SlideState.ERROR),
            heartbeat=bool(vals["heartbeat"]),
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
