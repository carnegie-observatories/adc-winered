"""Command dispatch table.

Each handler takes `(controller, args)` and returns a dict for the `ack.result`
field on success, or raises `CommandError` for a failure that should land as
`ack.ok=False`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from ..controller import ControlMode, Controller
from ..plc import Axis, PlcUnreachable, Slide
from .envelope import ErrorCode


@dataclass(frozen=True, slots=True)
class CommandError(Exception):
    code: ErrorCode
    message: str

    def __str__(self) -> str:
        return f"{self.code.value}: {self.message}"


Handler = Callable[[Controller, dict[str, Any]], Awaitable[dict[str, Any]]]


def _require(args: dict[str, Any], key: str) -> Any:
    if key not in args:
        raise CommandError(ErrorCode.MISSING_ARGUMENT, f"{key!r} required")
    return args[key]


def _require_str(args: dict[str, Any], key: str, allowed: tuple[str, ...]) -> str:
    raw = _require(args, key)
    if not isinstance(raw, str) or raw not in allowed:
        raise CommandError(
            ErrorCode.INVALID_ARGUMENT,
            f"{key!r} must be one of {list(allowed)}",
        )
    return raw


def _require_float(args: dict[str, Any], key: str) -> float:
    raw = _require(args, key)
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise CommandError(ErrorCode.INVALID_ARGUMENT, f"{key!r} must be a number")
    return float(raw)


def _require_bool(args: dict[str, Any], key: str) -> bool:
    raw = _require(args, key)
    if not isinstance(raw, bool):
        raise CommandError(ErrorCode.INVALID_ARGUMENT, f"{key!r} must be a boolean")
    return raw


async def set_adc_insertion(c: Controller, args: dict[str, Any]) -> dict[str, Any]:
    position = _require_str(args, "position", ("in", "out"))
    try:
        await c.set_slide(Slide.A, deploy_in=(position == "in"))
    except PlcUnreachable as exc:
        raise CommandError(ErrorCode.PLC_UNREACHABLE, str(exc)) from exc
    return {"requested": True}


async def set_other_insertion(c: Controller, args: dict[str, Any]) -> dict[str, Any]:
    position = _require_str(args, "position", ("in", "out"))
    try:
        await c.set_slide(Slide.B, deploy_in=(position == "in"))
    except PlcUnreachable as exc:
        raise CommandError(ErrorCode.PLC_UNREACHABLE, str(exc)) from exc
    return {"requested": True}


async def set_control_mode(c: Controller, args: dict[str, Any]) -> dict[str, Any]:
    mode = _require_str(args, "mode", ("auto", "off"))
    await c.set_control_mode(ControlMode(mode))
    return {"mode": mode}


async def move_lens(c: Controller, args: dict[str, Any]) -> dict[str, Any]:
    lens = _require_str(args, "lens", ("a", "b"))
    angle = _require_float(args, "angle")
    try:
        await c.move_axis_to(Axis.A if lens == "a" else Axis.B, angle)
    except PlcUnreachable as exc:
        raise CommandError(ErrorCode.PLC_UNREACHABLE, str(exc)) from exc
    return {"requested": True}


async def set_auto_update(c: Controller, args: dict[str, Any]) -> dict[str, Any]:
    enabled = _require_bool(args, "enabled")
    await c.set_control_mode(ControlMode.AUTO if enabled else ControlMode.OFF)
    return {"enabled": enabled}


async def trigger_manual_update(c: Controller, _args: dict[str, Any]) -> dict[str, Any]:
    await c.trigger_update()
    return {"requested": True}


DISPATCH: dict[str, Handler] = {
    "setADCInsertion": set_adc_insertion,
    "setOtherInsertion": set_other_insertion,
    "setControlMode": set_control_mode,
    "moveLens": move_lens,
    "setAutoUpdate": set_auto_update,
    "triggerManualUpdate": trigger_manual_update,
}
