"""WebSocket protocol round-trips against a live server backed by sim drivers."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

import pytest
import websockets

from adc_winered.controller import Controller, ControlMode
from adc_winered.plc_sim import PlcSim
from adc_winered.tcs_sim import TcsSim
from adc_winered.ws import LogBuffer, WsServer


@pytest.fixture
async def stack() -> AsyncIterator[tuple[WsServer, Controller, TcsSim]]:
    plc = PlcSim(rotator_velocity_deg_s=180.0, slide_settle_s=0.05)
    tcs = TcsSim(elevation_deg=60.0, rotator_deg=0.0)
    ctrl = Controller(
        plc, tcs,
        control_interval_s=0.05,
        deadband_deg=0.5,
        plc_poll_interval_s=0.02,
        tcs_poll_interval_s=0.02,
    )
    await ctrl.start()
    logs = LogBuffer()
    server = WsServer(ctrl, logs, host="127.0.0.1", port=0)
    await server.start()
    try:
        yield server, ctrl, tcs
    finally:
        await server.stop()
        await ctrl.stop()


async def _connect(server: WsServer):
    uri = f"ws://127.0.0.1:{server.port}"
    return await websockets.connect(uri)


async def _recv_until(ws, predicate, timeout: float = 2.0) -> dict:
    deadline = asyncio.get_event_loop().time() + timeout
    while True:
        remaining = deadline - asyncio.get_event_loop().time()
        if remaining <= 0:
            raise AssertionError("predicate never satisfied within timeout")
        raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
        payload = json.loads(raw)
        if predicate(payload):
            return payload


async def test_hello_on_connect(stack) -> None:
    server, _, _ = stack
    ws = await _connect(server)
    try:
        msg = json.loads(await ws.recv())
        assert msg["type"] == "hello"
        assert msg["app"] == "ADC"  # matches lco-instrument-web APP_REGISTRY key
        assert msg["protocol_version"] == 1
        assert set(msg["topics"]) == {"status", "lens", "telescope", "logs"}
    finally:
        await ws.close()


async def test_subscribe_returns_state_snapshot(stack) -> None:
    server, _, _ = stack
    ws = await _connect(server)
    try:
        await ws.recv()  # hello
        await ws.send(json.dumps({"type": "subscribe", "topics": ["telescope"]}))
        msg = await _recv_until(ws, lambda p: p.get("type") == "state" and p.get("topic") == "telescope")
        assert msg["data"]["elevation"] == pytest.approx(60.0)
        assert msg["data"]["rotator"] == pytest.approx(0.0)
    finally:
        await ws.close()


async def test_cmd_returns_ack_ok(stack) -> None:
    server, _, _ = stack
    ws = await _connect(server)
    try:
        await ws.recv()  # hello
        await ws.send(json.dumps({
            "type": "cmd", "id": "c1", "name": "set_control_mode", "args": {"mode": "auto"}
        }))
        ack = await _recv_until(ws, lambda p: p.get("type") == "ack")
        assert ack == {"type": "ack", "id": "c1", "ok": True, "result": {"mode": "auto"}}
    finally:
        await ws.close()


async def test_cmd_unknown_returns_ack_error(stack) -> None:
    server, _, _ = stack
    ws = await _connect(server)
    try:
        await ws.recv()  # hello
        await ws.send(json.dumps({"type": "cmd", "id": "c2", "name": "noSuchCmd", "args": {}}))
        ack = await _recv_until(ws, lambda p: p.get("type") == "ack")
        assert ack["id"] == "c2"
        assert ack["ok"] is False
        assert ack["error"]["code"] == "invalid_argument"
    finally:
        await ws.close()


async def test_cmd_missing_argument_returns_ack_error(stack) -> None:
    server, _, _ = stack
    ws = await _connect(server)
    try:
        await ws.recv()
        await ws.send(json.dumps({"type": "cmd", "id": "c3", "name": "move_lens", "args": {"lens": "A"}}))
        ack = await _recv_until(ws, lambda p: p.get("type") == "ack")
        assert ack["ok"] is False
        assert ack["error"]["code"] == "missing_argument"
    finally:
        await ws.close()


async def test_state_change_pushes_state_frame(stack) -> None:
    server, ctrl, tcs = stack
    ws = await _connect(server)
    try:
        await ws.recv()  # hello
        await ws.send(json.dumps({"type": "subscribe", "topics": ["telescope"]}))
        # Initial snapshot.
        initial = await _recv_until(ws, lambda p: p.get("type") == "state" and p.get("topic") == "telescope")
        assert initial["data"]["elevation"] == pytest.approx(60.0)

        # Change TCS state — the publisher loop should push a new frame.
        tcs.set_state(elevation_deg=45.0, rotator_deg=10.0)
        updated = await _recv_until(
            ws,
            lambda p: p.get("type") == "state"
                       and p.get("topic") == "telescope"
                       and p.get("data", {}).get("elevation") == pytest.approx(45.0),
        )
        assert updated["data"]["rotator"] == pytest.approx(10.0)
    finally:
        await ws.close()


async def test_status_topic_reflects_control_mode(stack) -> None:
    server, ctrl, _ = stack
    ws = await _connect(server)
    try:
        await ws.recv()  # hello
        await ws.send(json.dumps({"type": "subscribe", "topics": ["status"]}))
        initial = await _recv_until(ws, lambda p: p.get("type") == "state" and p.get("topic") == "status")
        assert initial["data"]["control"] == "off"

        await ctrl.set_control_mode(ControlMode.AUTO)
        updated = await _recv_until(
            ws,
            lambda p: p.get("type") == "state"
                       and p.get("topic") == "status"
                       and p.get("data", {}).get("control") == "auto",
        )
        assert updated["data"]["update"] is True
    finally:
        await ws.close()


async def test_version_command(stack) -> None:
    server, _, _ = stack
    ws = await _connect(server)
    try:
        await ws.recv()  # hello
        await ws.send(json.dumps({"type": "cmd", "id": "v1", "name": "version", "args": {}}))
        ack = await _recv_until(ws, lambda p: p.get("type") == "ack")
        assert ack["ok"] is True
        assert ack["result"]["app"] == "ADC"
        assert ack["result"]["protocol_version"] == 1
        assert isinstance(ack["result"]["version"], str)
    finally:
        await ws.close()


async def test_set_running_aliases_control_mode(stack) -> None:
    server, ctrl, _ = stack
    ws = await _connect(server)
    try:
        await ws.recv()  # hello
        await ws.send(json.dumps({"type": "cmd", "id": "r1", "name": "set_running", "args": {"running": True}}))
        ack = await _recv_until(ws, lambda p: p.get("type") == "ack")
        assert ack["ok"] is True
        # Allow a tick for the controller to apply.
        await asyncio.sleep(0.05)
        assert ctrl.snapshot().mode.value == "auto"
    finally:
        await ws.close()


async def test_unsubscribe_stops_updates(stack) -> None:
    server, _, tcs = stack
    ws = await _connect(server)
    try:
        await ws.recv()  # hello
        await ws.send(json.dumps({"type": "subscribe", "topics": ["telescope"]}))
        await _recv_until(ws, lambda p: p.get("type") == "state" and p.get("topic") == "telescope")

        await ws.send(json.dumps({"type": "unsubscribe", "topics": ["telescope"]}))
        # Trigger a change that would have produced a frame.
        await asyncio.sleep(0.05)  # let the server process unsubscribe
        tcs.set_state(elevation_deg=20.0, rotator_deg=50.0)

        # No more telescope frames should arrive.
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(
                _recv_until(ws, lambda p: p.get("type") == "state" and p.get("topic") == "telescope"),
                timeout=0.3,
            )
    finally:
        await ws.close()
