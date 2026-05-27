"""End-to-end: WS client drives a full server (sim PLC + sim TCS) to convergence.

This is the smoke test the CI runs to know the whole stack still hangs together.
It exercises every layer: WS marshaling, command dispatch, controller state
machine, tracking loop, PLC sim motion.
"""

from __future__ import annotations

import asyncio
import json

import pytest
import websockets

from adc_winered.controller import Controller
from adc_winered.plc_sim import PlcSim
from adc_winered.tcs_sim import TcsSim
from adc_winered.ws import LogBuffer, WsServer


async def test_end_to_end_tracking_via_ws() -> None:
    plc = PlcSim(rotator_velocity_deg_s=360.0, slide_settle_s=0.05)
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
        async with websockets.connect(f"ws://127.0.0.1:{server.port}") as ws:
            # 1. hello
            hello = json.loads(await ws.recv())
            assert hello["type"] == "hello"

            # 2. Subscribe to all topics.
            await ws.send(json.dumps({"type": "subscribe", "topics": ["status", "lens", "telescope"]}))

            # 3. Enable auto control.
            await ws.send(json.dumps({"type": "cmd", "id": "c1", "name": "setControlMode", "args": {"mode": "auto"}}))

            # 4. Wait for the lens topic to report both axes done at the IB targets.
            #    Drain frames; we don't care about ordering.
            converged = {"a": False, "b": False}
            deadline = asyncio.get_event_loop().time() + 5.0
            target_a: float | None = None
            target_b: float | None = None
            while not (converged["a"] and converged["b"]):
                if asyncio.get_event_loop().time() > deadline:
                    raise AssertionError(
                        f"tracking did not converge: targets=({target_a},{target_b}) converged={converged}"
                    )
                frame = json.loads(await asyncio.wait_for(ws.recv(), timeout=2.0))
                if frame.get("type") != "state":
                    continue
                if frame.get("topic") == "lens":
                    data = frame["data"]
                    target_a = data["lens_a"]["target"]
                    target_b = data["lens_b"]["target"]
                    if (
                        not data["lens_a"]["moving"]
                        and abs(data["lens_a"]["encoder"] - target_a) <= 0.5
                    ):
                        converged["a"] = True
                    if (
                        not data["lens_b"]["moving"]
                        and abs(data["lens_b"]["encoder"] - target_b) <= 0.5
                    ):
                        converged["b"] = True

            # 5. Insert the ADC slide.
            await ws.send(json.dumps({"type": "cmd", "id": "c2", "name": "setADCInsertion", "args": {"position": "in"}}))
            slide_in = False
            deadline = asyncio.get_event_loop().time() + 2.0
            while not slide_in:
                if asyncio.get_event_loop().time() > deadline:
                    raise AssertionError("slide did not insert in time")
                frame = json.loads(await asyncio.wait_for(ws.recv(), timeout=2.0))
                if frame.get("type") == "state" and frame.get("topic") == "status":
                    if frame["data"]["adc"] == "in":
                        slide_in = True

            # 6. Disable auto and confirm status flips.
            await ws.send(json.dumps({"type": "cmd", "id": "c3", "name": "setControlMode", "args": {"mode": "off"}}))
            saw_off = False
            deadline = asyncio.get_event_loop().time() + 2.0
            while not saw_off:
                if asyncio.get_event_loop().time() > deadline:
                    raise AssertionError("control mode did not transition to off")
                frame = json.loads(await asyncio.wait_for(ws.recv(), timeout=2.0))
                if frame.get("type") == "state" and frame.get("topic") == "status":
                    if frame["data"]["control"] == "off":
                        saw_off = True
    finally:
        await server.stop()
        await ctrl.stop()


async def test_cli_module_can_be_imported() -> None:
    """The CLI module imports cleanly and the entry point is callable."""
    from adc_winered import cli

    assert callable(cli.main)
