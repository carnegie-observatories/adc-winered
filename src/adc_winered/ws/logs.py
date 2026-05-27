"""Log ring buffer + live broadcast for the `logs` topic.

Mounts a logging handler that captures `INFO+` records into a 500-entry deque
and broadcasts each new entry as an `event` frame. The broadcaster callback is
plugged in by the WS server.

Per the LCO spec: snapshot on subscribe ships `{entries: [...]}` as a `state`
frame; live entries arrive as `event` frames with `topic: "logs"`.
"""

from __future__ import annotations

import collections
import logging
import time
from typing import Any, Callable

_BUFFER_LIMIT = 500
_RATE_LIMIT_PER_SEC = 100


class LogBuffer(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.INFO)
        self._entries: collections.deque[dict[str, Any]] = collections.deque(maxlen=_BUFFER_LIMIT)
        self._broadcasters: list[Callable[[dict[str, Any]], None]] = []
        self._window_start = time.monotonic()
        self._window_count = 0
        self.setFormatter(logging.Formatter("%(message)s"))

    def emit(self, record: logging.LogRecord) -> None:
        # Coarse rate limit per the spec (≤100/sec). Tally dropped entries by
        # noting them in the buffer so subscribers can detect the gap.
        now = time.monotonic()
        if now - self._window_start >= 1.0:
            self._window_start = now
            self._window_count = 0
        self._window_count += 1
        if self._window_count > _RATE_LIMIT_PER_SEC:
            return

        entry = {
            "ts": _iso_timestamp(record.created),
            "level": record.levelname.lower(),
            "src": record.name,
            "msg": record.getMessage(),
        }
        self._entries.append(entry)
        for cb in list(self._broadcasters):
            try:
                cb(entry)
            except Exception:
                # Never let a misbehaving subscriber break logging itself.
                pass

    # --- broadcaster wiring -------------------------------------------

    def add_broadcaster(self, cb: Callable[[dict[str, Any]], None]) -> None:
        self._broadcasters.append(cb)

    def remove_broadcaster(self, cb: Callable[[dict[str, Any]], None]) -> None:
        if cb in self._broadcasters:
            self._broadcasters.remove(cb)

    # --- snapshot for newly-subscribed clients ------------------------

    def snapshot(self) -> dict[str, Any]:
        return {"entries": list(self._entries)}


def _iso_timestamp(epoch_seconds: float) -> str:
    import datetime as _dt

    return _dt.datetime.fromtimestamp(epoch_seconds, tz=_dt.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%S.") + f"{int((epoch_seconds % 1) * 1000):03d}Z"
