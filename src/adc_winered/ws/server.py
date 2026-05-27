"""WebSocket server.

One asyncio task per connection. Per-connection state: the set of subscribed
topics. The server publishes topic snapshots to every subscriber on change;
change detection is by JSON-stringified payload equality (cheap, correct, no
diff machinery).

Spec: /Users/william/workspace/lco-ansible/docs/ws-protocol.md
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from typing import Any

import websockets
from websockets.asyncio.server import ServerConnection

from ..controller import Controller
from .commands import DISPATCH, CommandError
from .envelope import (
    APP_NAME,
    KNOWN_TOPICS,
    PROTOCOL_VERSION,
    CmdFrame,
    ErrorCode,
    ParseError,
    SubscribeFrame,
    UnsubscribeFrame,
    ack_err,
    ack_ok,
    event_topic,
    hello,
    parse_client_frame,
    state,
)
from .logs import LogBuffer
from .topics import TOPIC_PROJECTORS

log = logging.getLogger(__name__)

_ = APP_NAME, PROTOCOL_VERSION  # re-exported for documentation searches


class WsServer:
    def __init__(
        self,
        controller: Controller,
        log_buffer: LogBuffer,
        *,
        host: str = "0.0.0.0",
        port: int = 52403,
    ) -> None:
        self._controller = controller
        self._logs = log_buffer
        self._host = host
        self._port = port
        self._server: Any = None  # websockets.asyncio.server.Server
        self._publisher_task: asyncio.Task[None] | None = None
        self._connections: set[_ConnectionState] = set()
        self._last_topic_data: dict[str, str] = {}

    async def start(self) -> None:
        self._server = await websockets.serve(self._handle, self._host, self._port)
        self._publisher_task = asyncio.create_task(self._publisher_loop(), name="adc-ws-publish")

    async def stop(self) -> None:
        if self._publisher_task is not None:
            self._publisher_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._publisher_task
            self._publisher_task = None
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
        log_cb = lambda entry: conn.enqueue(event_topic("logs", entry))  # noqa: E731
        self._logs.add_broadcaster(log_cb)
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
            self._logs.remove_broadcaster(log_cb)
            self._connections.discard(conn)

    async def _read_loop(self, conn: _ConnectionState) -> None:
        async for raw in conn.ws:
            try:
                frame = parse_client_frame(raw)
            except ParseError as exc:
                # No id to ack — log and move on. The spec doesn't define a
                # response for unparseable frames.
                log.warning("dropping unparseable frame from client: %s", exc)
                continue

            if isinstance(frame, SubscribeFrame):
                await self._on_subscribe(conn, frame.topics)
            elif isinstance(frame, UnsubscribeFrame):
                conn.topics.difference_update(frame.topics)
            elif isinstance(frame, CmdFrame):
                await self._on_cmd(conn, frame)

    async def _write_loop(self, conn: _ConnectionState) -> None:
        while True:
            msg = await conn.outbox.get()
            if msg is _SENTINEL:
                return
            await conn.ws.send(msg)

    # --- topic publishing -----------------------------------------------

    async def _on_subscribe(self, conn: _ConnectionState, topics: list[str]) -> None:
        for topic in topics:
            if topic not in KNOWN_TOPICS:
                log.warning("ignoring subscribe to unknown topic %r", topic)
                continue
            conn.topics.add(topic)
            payload = self._render_topic(topic)
            conn.enqueue(state(topic, payload))

    async def _on_cmd(self, conn: _ConnectionState, frame: CmdFrame) -> None:
        handler = DISPATCH.get(frame.name)
        if handler is None:
            conn.enqueue(ack_err(frame.id, ErrorCode.INVALID_ARGUMENT, f"unknown cmd: {frame.name}"))
            return
        try:
            result = await handler(self._controller, frame.args)
        except CommandError as exc:
            conn.enqueue(ack_err(frame.id, exc.code, exc.message))
            return
        except Exception as exc:
            log.exception("cmd %s blew up", frame.name)
            conn.enqueue(ack_err(frame.id, ErrorCode.HARDWARE, str(exc)))
            return
        conn.enqueue(ack_ok(frame.id, result))

    async def _publisher_loop(self) -> None:
        queue = self._controller.subscribe()
        try:
            while True:
                # Drain the queue to coalesce bursts; we publish only the latest.
                await queue.get()
                while True:
                    try:
                        queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break
                self._publish_changes()
        except asyncio.CancelledError:
            raise
        finally:
            self._controller.unsubscribe(queue)

    def _publish_changes(self) -> None:
        for topic in KNOWN_TOPICS:
            if topic == "logs":
                continue  # logs flow as events, not topic snapshots
            payload = self._render_topic(topic)
            serialized = json.dumps(payload, sort_keys=True)
            if self._last_topic_data.get(topic) == serialized:
                continue
            self._last_topic_data[topic] = serialized
            frame = state(topic, payload)
            for conn in list(self._connections):
                if topic in conn.topics:
                    conn.enqueue(frame)

    def _render_topic(self, topic: str) -> dict[str, Any]:
        if topic == "logs":
            return self._logs.snapshot()
        projector = TOPIC_PROJECTORS[topic]
        return projector(self._controller.snapshot())


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
