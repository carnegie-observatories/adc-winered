"""Magellan TCS client (async, line-based TCP).

Each request sends a command followed by `\\n` and reads back a line of the same
shape (the legacy protocol verified by the attic prototype `magio.py`). The two
fields used by the dispersion correction are:

- `telel`     - telescope elevation, degrees
- `rotatore`  - rotator encoder, degrees

A new connection per `read()` is intentional and matches the legacy semantics:
the original `MagIO.get_airmass()` opened, queried, and closed within one call.
TCS-side state is per-request, so the cost is negligible and there's no idle
connection to worry about on either side.
"""

from __future__ import annotations

import asyncio

from .tcs import TcsSample, TcsUnreachable

DEFAULT_PORT = 5800
_TERMINATOR = b"\n"
_REQUEST_TIMEOUT_S = 5.0


class TcsClient:
    def __init__(
        self,
        host: str,
        port: int = DEFAULT_PORT,
        *,
        timeout_s: float = _REQUEST_TIMEOUT_S,
    ) -> None:
        self._host = host
        self._port = port
        self._timeout = timeout_s

    async def connect(self) -> None:
        # No persistent connection. Probe once so wiring problems surface at startup.
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self._host, self._port), timeout=self._timeout
            )
        except (OSError, asyncio.TimeoutError) as exc:
            raise TcsUnreachable(f"TCS connect failed: {exc}") from exc
        writer.close()
        await writer.wait_closed()
        _ = reader  # explicit: we only wanted to confirm reachability

    async def close(self) -> None:
        return None

    async def read(self) -> TcsSample:
        elevation = float(await self._query("telel"))
        rotator = float(await self._query("rotatore"))
        return TcsSample(elevation_deg=elevation, rotator_deg=rotator)

    async def _query(self, command: str) -> str:
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self._host, self._port), timeout=self._timeout
            )
        except (OSError, asyncio.TimeoutError) as exc:
            raise TcsUnreachable(f"TCS connect failed: {exc}") from exc
        try:
            writer.write(command.encode("ascii") + _TERMINATOR)
            await writer.drain()
            try:
                line = await asyncio.wait_for(reader.readline(), timeout=self._timeout)
            except asyncio.TimeoutError as exc:
                raise TcsUnreachable(f"TCS '{command}' timed out") from exc
            if not line:
                raise TcsUnreachable(f"TCS closed without response to '{command}'")
            return line.decode("ascii", errors="replace").strip()
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
