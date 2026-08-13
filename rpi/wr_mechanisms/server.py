"""WebSocket server for the `mechanisms` topic.

Same shape as `adc_winered.ws.server`, minus everything a mechanisms-only box
doesn't have: no controller, no tracking loop, no log topic. State changes only
in response to a command, so there is no publisher task — every accepted command
broadcasts the new snapshot to subscribers, and a fresh subscriber gets one
immediately.

One addition the ADC server has no need for: the same port also serves the
operator panel over plain HTTP (see `http.py`). The Pi is the whole deployment,
so it hands out the page that drives it.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any

import websockets
from websockets.asyncio.server import ServerConnection

from .commands import DISPATCH, CommandError
from .http import process_request
from .mechanisms import Mechanisms
from .protocol import (
    KNOWN_TOPICS,
    CmdFrame,
    ErrorCode,
    ParseError,
    SubscribeFrame,
    UnsubscribeFrame,
    ack_err,
    ack_ok,
    hello,
    parse_client_frame,
    state,
)

log = logging.getLogger(__name__)

TOPIC = "mechanisms"


class MechanismsServer:
    def __init__(
        self,
        mechanisms: Mechanisms,
        *,
        host: str = "0.0.0.0",
        port: int = 52403,
    ) -> None:
        self._mechanisms = mechanisms
        self._host = host
        self._port = port
        self._server: Any = None  # websockets.asyncio.server.Server
        self._connections: set[_ConnectionState] = set()

    async def start(self) -> None:
        # process_request serves the operator panel over plain HTTP on this
        # same port; WebSocket upgrades fall through to _handle.
        self._server = await websockets.serve(
            self._handle, self._host, self._port, process_request=process_request
        )

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        for conn in list(self._connections):
            await conn.close()

    @property
    def port(self) -> int:
        if self._server is None:
            return self._port
        # Use the bound port (handy when self._port was 0).
        return self._server.sockets[0].getsockname()[1]

    # --- connection lifecycle -------------------------------------------

    async def _handle(self, ws: ServerConnection) -> None:
        conn = _ConnectionState(ws)
        self._connections.add(conn)
        write_task = asyncio.create_task(self._write_loop(conn))
        try:
            await ws.send(hello())
            await self._read_loop(conn)
        except websockets.ConnectionClosed:
            pass
        finally:
            write_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await write_task
            self._connections.discard(conn)

    async def _read_loop(self, conn: _ConnectionState) -> None:
        async for raw in conn.ws:
            try:
                frame = parse_client_frame(raw)
            except ParseError as exc:
                # No id to ack — log and move on, as the spec leaves the
                # response to an unparseable frame undefined.
                log.warning("dropping unparseable frame from client: %s", exc)
                continue

            if isinstance(frame, SubscribeFrame):
                self._on_subscribe(conn, frame.topics)
            elif isinstance(frame, UnsubscribeFrame):
                conn.topics.difference_update(frame.topics)
            elif isinstance(frame, CmdFrame):
                self._on_cmd(conn, frame)

    async def _write_loop(self, conn: _ConnectionState) -> None:
        while True:
            msg = await conn.outbox.get()
            if msg is _SENTINEL:
                return
            await conn.ws.send(msg)

    # --- topic publishing -----------------------------------------------

    def _on_subscribe(self, conn: _ConnectionState, topics: list[str]) -> None:
        for topic in topics:
            if topic not in KNOWN_TOPICS:
                log.warning("ignoring subscribe to unknown topic %r", topic)
                continue
            conn.topics.add(topic)
            conn.enqueue(state(topic, self._mechanisms.snapshot()))

    def _on_cmd(self, conn: _ConnectionState, frame: CmdFrame) -> None:
        handler = DISPATCH.get(frame.name)
        if handler is None:
            conn.enqueue(ack_err(frame.id, ErrorCode.INVALID_ARGUMENT, f"unknown cmd: {frame.name}"))
            return
        try:
            result = handler(self._mechanisms, frame.args)
        except CommandError as exc:
            conn.enqueue(ack_err(frame.id, exc.code, exc.message))
            return
        except Exception as exc:
            log.exception("cmd %s blew up", frame.name)
            conn.enqueue(ack_err(frame.id, ErrorCode.HARDWARE, str(exc)))
            return
        conn.enqueue(ack_ok(frame.id, result))
        self.publish_state()

    def publish_state(self) -> None:
        """Broadcast the snapshot to every subscriber.

        No change detection here, unlike the PLC-backed server: a command is
        the only thing that can move this state, and the browser panel waits
        for the echo before clearing its pending marker. Suppressing the frame
        for a re-command of the position already held would leave that button
        dashed until it timed out.
        """
        frame = state(TOPIC, self._mechanisms.snapshot())
        for conn in list(self._connections):
            if TOPIC in conn.topics:
                conn.enqueue(frame)


class _ConnectionState:
    def __init__(self, ws: ServerConnection) -> None:
        self.ws = ws
        self.topics: set[str] = set()
        self.outbox: asyncio.Queue[Any] = asyncio.Queue(maxsize=256)

    def enqueue(self, message: str) -> None:
        try:
            self.outbox.put_nowait(message)
        except asyncio.QueueFull:
            log.warning("client outbox full; dropping message")

    async def close(self) -> None:
        await self.outbox.put(_SENTINEL)
        try:
            await self.ws.close()
        except Exception:
            pass


_SENTINEL = object()
