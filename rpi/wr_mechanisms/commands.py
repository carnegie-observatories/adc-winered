"""Command dispatch table.

The mechanisms subset of the ADC command set, with identical names and argument
shapes — `set_shutter {pos}` and `set_milky_flat {pos}` — so a client cannot
tell whether it is driving a PLC or a Pi. Handlers are synchronous: a relay
write is a register poke, not an I/O wait.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from . import __version__
from .gpio import RelayError
from .mechanisms import MILKY_FLAT_POSITIONS, SHUTTER_POSITIONS, Mechanisms
from .protocol import APP_NAME, PROTOCOL_VERSION, ErrorCode


@dataclass(frozen=True, slots=True)
class CommandError(Exception):
    code: ErrorCode
    message: str

    def __str__(self) -> str:
        return f"{self.code.value}: {self.message}"


Handler = Callable[[Mechanisms, dict[str, Any]], dict[str, Any]]


def _require_str(args: dict[str, Any], key: str, allowed: tuple[str, ...]) -> str:
    if key not in args:
        raise CommandError(ErrorCode.MISSING_ARGUMENT, f"{key!r} required")
    raw = args[key]
    if not isinstance(raw, str) or raw not in allowed:
        raise CommandError(
            ErrorCode.INVALID_ARGUMENT,
            f"{key!r} must be one of {list(allowed)}",
        )
    return raw


def version(_m: Mechanisms, _args: dict[str, Any]) -> dict[str, Any]:
    return {"version": __version__, "protocol_version": PROTOCOL_VERSION, "app": APP_NAME}


def set_shutter(m: Mechanisms, args: dict[str, Any]) -> dict[str, Any]:
    pos = _require_str(args, "pos", SHUTTER_POSITIONS)
    try:
        m.set_shutter(pos)
    except RelayError as exc:
        raise CommandError(ErrorCode.HARDWARE, str(exc)) from exc
    return {"requested": True}


def set_milky_flat(m: Mechanisms, args: dict[str, Any]) -> dict[str, Any]:
    pos = _require_str(args, "pos", MILKY_FLAT_POSITIONS)
    try:
        m.set_milky_flat(pos)
    except RelayError as exc:
        raise CommandError(ErrorCode.HARDWARE, str(exc)) from exc
    return {"requested": True}


DISPATCH: dict[str, Handler] = {
    "version": version,
    "set_shutter": set_shutter,
    "set_milky_flat": set_milky_flat,
}
