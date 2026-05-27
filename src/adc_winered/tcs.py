"""Shared TCS interface and data shapes.

The controller depends on `TcsDriver`. Two implementations: `TcsClient` (real
Magellan TCS over TCP) and `TcsSim` (in-process fake). Only the fields the
correction algorithm actually needs are exposed — elevation and rotator. Add
more if and when a new mode needs them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class TcsSample:
    """Latest telescope state snapshot from the TCS."""

    elevation_deg: float
    rotator_deg: float


class TcsUnreachable(RuntimeError):
    """TCS connection dropped or the response was malformed."""


class TcsDriver(Protocol):
    async def connect(self) -> None: ...
    async def close(self) -> None: ...
    async def read(self) -> TcsSample: ...
