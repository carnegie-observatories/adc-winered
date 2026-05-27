"""In-process TCS simulator.

Two ways to use this:

1. As a `TcsDriver` (the default): the controller talks to it via `connect/read/close`.
   `set_state(...)` lets tests drive the simulated telescope deterministically.
2. As a TCP server (`serve()`): exposes the same line-protocol as the Magellan TCS
   on a local port so `TcsClient` and external tools can talk to it. Used by the
   end-to-end integration test and for manual bench bring-up.
"""

from __future__ import annotations

import asyncio
import math
import time
from dataclasses import dataclass

from .tcs import TcsSample, TcsUnreachable

_TERMINATOR = b"\n"


@dataclass(slots=True)
class _SimState:
    elevation_deg: float = 60.0
    rotator_deg: float = 0.0


class TcsSim:
    """In-process simulator with the `TcsDriver` shape."""

    def __init__(
        self,
        *,
        elevation_deg: float = 60.0,
        rotator_deg: float = 0.0,
        drift: bool = False,
        clock: object | None = None,
    ) -> None:
        self._state = _SimState(elevation_deg=elevation_deg, rotator_deg=rotator_deg)
        self._drift = drift
        self._clock = clock or time.monotonic
        self._t0 = self._clock()

    async def connect(self) -> None:
        self._t0 = self._clock()

    async def close(self) -> None:
        return None

    async def read(self) -> TcsSample:
        if self._drift:
            t = self._clock() - self._t0
            # Slow oscillation, same shape as the legacy attic simulator.
            self._state.elevation_deg = 50.0 + 20.0 * math.sin(t / 120.0)
            self._state.rotator_deg = (t * 10.0 / 60.0) % 360.0
        return TcsSample(self._state.elevation_deg, self._state.rotator_deg)

    def set_state(self, *, elevation_deg: float, rotator_deg: float) -> None:
        """Test hook: pin elevation/rotator to a known value."""
        self._state.elevation_deg = elevation_deg
        self._state.rotator_deg = rotator_deg

    async def serve(self, host: str = "127.0.0.1", port: int = 0) -> asyncio.Server:
        """Expose the Magellan line-protocol on a TCP port. Returns the server.

        port=0 picks a free port; useful for tests. The returned server is wired
        into the asyncio loop; the caller is responsible for closing it.
        """
        server = await asyncio.start_server(self._handle, host=host, port=port)
        return server

    async def _handle(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        try:
            line = await reader.readline()
            if not line:
                return
            command = line.decode("ascii", errors="replace").strip()
            response = self._response_for(command)
            if response is not None:
                writer.write(response.encode("ascii") + _TERMINATOR)
                await writer.drain()
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    def _response_for(self, command: str) -> str | None:
        # Refresh drift if enabled.
        if self._drift:
            t = self._clock() - self._t0
            self._state.elevation_deg = 50.0 + 20.0 * math.sin(t / 120.0)
            self._state.rotator_deg = (t * 10.0 / 60.0) % 360.0

        if command == "telel":
            return f"{self._state.elevation_deg:.6f}"
        if command == "rotatore":
            return f"{self._state.rotator_deg:.6f}"
        return None


__all__ = ["TcsSim", "TcsUnreachable"]
