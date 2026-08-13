"""Command dispatch table.

Each handler takes `(controller, args)` and returns a dict for the `ack.result`
field on success, or raises `CommandError` for a failure that should land as
`ack.ok=False`.

Names and argument shapes follow the canonical APP_REGISTRY in
`lco-instrument-web/diagnostic.js` — snake_case, lens uppercase, etc.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from .. import __version__
from ..controller import ControlMode, Controller
from ..plc import Axis, PlcUnreachable, Slide
from .envelope import APP_NAME, PROTOCOL_VERSION, ErrorCode


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


async def version(_c: Controller, _args: dict[str, Any]) -> dict[str, Any]:
    return {"version": __version__, "protocol_version": PROTOCOL_VERSION, "app": APP_NAME}


async def set_adc_insertion(c: Controller, args: dict[str, Any]) -> dict[str, Any]:
    pos = _require_str(args, "pos", ("in", "out"))
    try:
        await c.set_slide(Slide.A, deploy_in=(pos == "in"))
    except PlcUnreachable as exc:
        raise CommandError(ErrorCode.PLC_UNREACHABLE, str(exc)) from exc
    return {"requested": True}


async def set_other_insertion(c: Controller, args: dict[str, Any]) -> dict[str, Any]:
    pos = _require_str(args, "pos", ("in", "out"))
    try:
        await c.set_slide(Slide.B, deploy_in=(pos == "in"))
    except PlcUnreachable as exc:
        raise CommandError(ErrorCode.PLC_UNREACHABLE, str(exc)) from exc
    return {"requested": True}


async def set_shutter(c: Controller, args: dict[str, Any]) -> dict[str, Any]:
    pos = _require_str(args, "pos", ("open", "closed"))
    try:
        await c.set_shutter(closed=(pos == "closed"))
    except PlcUnreachable as exc:
        raise CommandError(ErrorCode.PLC_UNREACHABLE, str(exc)) from exc
    return {"requested": True}


async def set_milky_flat(c: Controller, args: dict[str, Any]) -> dict[str, Any]:
    pos = _require_str(args, "pos", ("in", "out"))
    try:
        await c.set_milky_flat(deploy_in=(pos == "in"))
    except PlcUnreachable as exc:
        raise CommandError(ErrorCode.PLC_UNREACHABLE, str(exc)) from exc
    return {"requested": True}


async def set_control_mode(c: Controller, args: dict[str, Any]) -> dict[str, Any]:
    mode = _require_str(args, "mode", ("auto", "off"))
    await c.set_control_mode(ControlMode(mode))
    return {"mode": mode}


async def move_lens(c: Controller, args: dict[str, Any]) -> dict[str, Any]:
    lens = _require_str(args, "lens", ("A", "B"))
    angle = _require_float(args, "angle")
    try:
        await c.move_axis_to(Axis.A if lens == "A" else Axis.B, angle)
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


async def set_running(c: Controller, args: dict[str, Any]) -> dict[str, Any]:
    """v1: maps to the control-mode auto/off transition.

    The legacy "running" flag is conceptually a master halt; for v1 the server
    treats it as an alias of set_control_mode — no new state machine, same
    observable behavior. Revisit when the bench reveals a behavioral gap.
    """
    running = _require_bool(args, "running")
    await c.set_control_mode(ControlMode.AUTO if running else ControlMode.OFF)
    return {"running": running}


DISPATCH: dict[str, Handler] = {
    "version": version,
    "set_adc_insertion": set_adc_insertion,
    "set_other_insertion": set_other_insertion,
    "set_shutter": set_shutter,
    "set_milky_flat": set_milky_flat,
    "set_control_mode": set_control_mode,
    "move_lens": move_lens,
    "set_auto_update": set_auto_update,
    "trigger_manual_update": trigger_manual_update,
    "set_running": set_running,
}
