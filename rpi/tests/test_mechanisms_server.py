"""Protocol round-trips and relay bookkeeping against a live server + sim GPIO."""

from __future__ import annotations

import asyncio
import dataclasses
import json
from collections.abc import AsyncIterator

import pytest
import websockets

from wr_mechanisms.config import Settings
from wr_mechanisms.gpio import ENABLE, MILKY_FLAT, SHUTTER, SimRelays
from wr_mechanisms.mechanisms import Mechanisms
from wr_mechanisms.server import MechanismsServer

SIM = Settings(gpio_mode="sim")


def _stack(settings: Settings = SIM) -> tuple[MechanismsServer, SimRelays, Mechanisms]:
    relays = SimRelays(settings)
    mechanisms = Mechanisms(relays, settings)
    mechanisms.start()
    server = MechanismsServer(mechanisms, host="127.0.0.1", port=0)
    return server, relays, mechanisms


@pytest.fixture
async def stack() -> AsyncIterator[tuple[MechanismsServer, SimRelays, Mechanisms]]:
    server, relays, mechanisms = _stack()
    await server.start()
    try:
        yield server, relays, mechanisms
    finally:
        await server.stop()
        mechanisms.close()


async def _connect(server: MechanismsServer):
    return await websockets.connect(f"ws://127.0.0.1:{server.port}")


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


# --- protocol ---------------------------------------------------------------

async def test_hello_advertises_mechanisms_only(stack) -> None:
    """The topic list is the capability signal the browser panel checks."""
    server, _, _ = stack
    ws = await _connect(server)
    try:
        msg = json.loads(await ws.recv())
        assert msg["type"] == "hello"
        assert msg["app"] == "ADC"
        assert msg["protocol_version"] == 1
        assert msg["topics"] == ["mechanisms"]
    finally:
        await ws.close()


async def test_subscribe_returns_snapshot(stack) -> None:
    server, _, _ = stack
    ws = await _connect(server)
    try:
        await ws.recv()  # hello
        await ws.send(json.dumps({"type": "subscribe", "topics": ["mechanisms"]}))
        msg = await _recv_until(ws, lambda p: p.get("type") == "state")
        assert msg["topic"] == "mechanisms"
        assert set(msg["data"]) == {"shutter", "milky_flat"}
    finally:
        await ws.close()


async def test_subscribe_to_unknown_topic_is_ignored(stack) -> None:
    """This box has no lens, telescope or status — asking for them yields nothing."""
    server, _, _ = stack
    ws = await _connect(server)
    try:
        await ws.recv()  # hello
        await ws.send(json.dumps({"type": "subscribe", "topics": ["status", "lens"]}))
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(ws.recv(), timeout=0.3)
    finally:
        await ws.close()


async def test_commands_drive_relays_and_publish_state(stack) -> None:
    server, relays, _ = stack
    ws = await _connect(server)
    try:
        await ws.recv()  # hello
        await ws.send(json.dumps({"type": "subscribe", "topics": ["mechanisms"]}))
        await _recv_until(ws, lambda p: p.get("type") == "state")

        # Both mechanisms sit on normally-closed contacts, so closing the
        # shutter and inserting the diffuser are the energized directions.
        await ws.send(json.dumps({"type": "cmd", "id": "s1", "name": "set_shutter",
                                  "args": {"pos": "closed"}}))
        ack = await _recv_until(ws, lambda p: p.get("type") == "ack" and p.get("id") == "s1")
        assert ack["ok"] is True
        updated = await _recv_until(
            ws,
            lambda p: p.get("type") == "state" and p["data"]["shutter"] == "closed",
        )
        assert updated["data"]["milky_flat"] == "out"
        assert relays.is_energized(SHUTTER) is True

        await ws.send(json.dumps({"type": "cmd", "id": "m1", "name": "set_milky_flat",
                                  "args": {"pos": "in"}}))
        await _recv_until(ws, lambda p: p.get("type") == "ack" and p.get("id") == "m1")
        await _recv_until(ws, lambda p: p.get("type") == "state" and p["data"]["milky_flat"] == "in")
        assert relays.is_energized(MILKY_FLAT) is True
    finally:
        await ws.close()


async def test_recommanding_the_same_position_still_echoes(stack) -> None:
    """The browser panel clears its pending marker on the echo, not on a change."""
    server, _, _ = stack
    ws = await _connect(server)
    try:
        await ws.recv()  # hello
        await ws.send(json.dumps({"type": "subscribe", "topics": ["mechanisms"]}))
        snap = await _recv_until(ws, lambda p: p.get("type") == "state")
        assert snap["data"]["shutter"] == "open"

        await ws.send(json.dumps({"type": "cmd", "id": "s1", "name": "set_shutter",
                                  "args": {"pos": "open"}}))
        await _recv_until(ws, lambda p: p.get("type") == "ack")
        echo = await _recv_until(ws, lambda p: p.get("type") == "state")
        assert echo["data"]["shutter"] == "open"
    finally:
        await ws.close()


async def test_bad_position_is_rejected_without_touching_the_relay(stack) -> None:
    server, relays, _ = stack
    ws = await _connect(server)
    try:
        await ws.recv()  # hello
        before = len(relays.writes)
        await ws.send(json.dumps({"type": "cmd", "id": "s2", "name": "set_shutter",
                                  "args": {"pos": "ajar"}}))
        ack = await _recv_until(ws, lambda p: p.get("type") == "ack")
        assert ack["ok"] is False
        assert ack["error"]["code"] == "invalid_argument"
        assert len(relays.writes) == before
    finally:
        await ws.close()


async def test_missing_argument_is_rejected(stack) -> None:
    server, _, _ = stack
    ws = await _connect(server)
    try:
        await ws.recv()  # hello
        await ws.send(json.dumps({"type": "cmd", "id": "m2", "name": "set_milky_flat", "args": {}}))
        ack = await _recv_until(ws, lambda p: p.get("type") == "ack")
        assert ack["ok"] is False
        assert ack["error"]["code"] == "missing_argument"
    finally:
        await ws.close()


async def test_adc_only_commands_are_unknown_here(stack) -> None:
    server, _, _ = stack
    ws = await _connect(server)
    try:
        await ws.recv()  # hello
        await ws.send(json.dumps({"type": "cmd", "id": "x1", "name": "move_lens",
                                  "args": {"lens": "A", "angle": 10.0}}))
        ack = await _recv_until(ws, lambda p: p.get("type") == "ack")
        assert ack["ok"] is False
        assert ack["error"]["code"] == "invalid_argument"
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
    finally:
        await ws.close()


async def test_unsubscribe_stops_updates(stack) -> None:
    server, _, _ = stack
    ws = await _connect(server)
    try:
        await ws.recv()  # hello
        await ws.send(json.dumps({"type": "subscribe", "topics": ["mechanisms"]}))
        await _recv_until(ws, lambda p: p.get("type") == "state")
        await ws.send(json.dumps({"type": "unsubscribe", "topics": ["mechanisms"]}))

        await ws.send(json.dumps({"type": "cmd", "id": "s3", "name": "set_shutter",
                                  "args": {"pos": "open"}}))
        ack = await _recv_until(ws, lambda p: p.get("type") == "ack")
        assert ack["ok"] is True
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(
                _recv_until(ws, lambda p: p.get("type") == "state"), timeout=0.3
            )
    finally:
        await ws.close()


# --- relays -----------------------------------------------------------------

def test_enable_is_energized_at_startup_and_dropped_on_close() -> None:
    relays = SimRelays(SIM)
    mechanisms = Mechanisms(relays, SIM)
    mechanisms.start()
    assert relays.is_energized(ENABLE) is True

    mechanisms.set_shutter("closed")
    mechanisms.set_milky_flat("in")
    mechanisms.close()
    # Everything down, and enable last so 12 V never outlives the mechanisms.
    assert [name for name in (SHUTTER, MILKY_FLAT, ENABLE) if relays.is_energized(name)] == []
    assert relays.writes[-1] == (SIM.pin_enable, False)


def test_normally_closed_enable_contact_leaves_its_coil_off() -> None:
    """With NC enable, 12 V flows when the coil is *off* — so don't energize it."""
    nc_enable = dataclasses.replace(SIM, enable_energized=False)
    relays = SimRelays(nc_enable)
    Mechanisms(relays, nc_enable).start()
    assert relays.is_energized(ENABLE) is False
    assert relays.writes == [(SIM.pin_enable, False)]


def test_pins_follow_the_wiring_table() -> None:
    relays = SimRelays(SIM)
    mechanisms = Mechanisms(relays, SIM)
    mechanisms.start()
    relays.writes.clear()

    # The energized position of each mechanism, so both writes are True.
    mechanisms.set_milky_flat("in")
    mechanisms.set_shutter("closed")
    assert relays.writes == [(13, True), (6, True)]


def test_coil_off_state_follows_the_energized_position() -> None:
    """Swapping the mechanical polarity swaps what "coil off" means.

    Which is the whole point of the setting: normally-open contacts would put
    these two the other way round.
    """
    inverted = dataclasses.replace(
        SIM, shutter_energized_pos="open", milky_flat_energized_pos="out"
    )
    relays = SimRelays(inverted)
    mechanisms = Mechanisms(relays, inverted)
    mechanisms.start()
    assert mechanisms.snapshot() == {"shutter": "closed", "milky_flat": "in"}

    mechanisms.set_shutter("open")
    assert relays.is_energized(SHUTTER) is True
    assert mechanisms.snapshot()["shutter"] == "open"


def test_startup_state_is_the_coil_off_state() -> None:
    """Before any command both coils are off, and their normally-closed
    contacts leave the mechanisms powered: shutter open, diffuser retracted.

    Not to be confused with the *stopped-service* state. Enable is
    normally-open, so stopping the service cuts 12 V and the actuators fall
    back to shutter closed / diffuser in beam — invisible to this model, which
    only knows coil states.
    """
    relays = SimRelays(SIM)
    mechanisms = Mechanisms(relays, SIM)
    mechanisms.start()
    assert mechanisms.snapshot() == {"shutter": "open", "milky_flat": "out"}


def test_defaults_match_the_wr_pi_bench() -> None:
    """Every polarity as wired on wr-pi.

    Pinned here so changing one back is a deliberate act, not a merge accident —
    nothing else in the stack would notice an inversion.
    """
    s = Settings()
    assert s.active_high is False           # D26 high left the 12 V enable off
    assert s.enable_energized is True       # enable runs on a NO contact
    # Both mechanisms on NC contacts: energizing the coil removes their 12 V.
    assert s.shutter_energized_pos == "closed"
    assert s.milky_flat_energized_pos == "in"


def test_unknown_position_raises_before_any_write() -> None:
    relays = SimRelays(SIM)
    mechanisms = Mechanisms(relays, SIM)
    mechanisms.start()
    relays.writes.clear()
    with pytest.raises(ValueError):
        mechanisms.set_shutter("ajar")
    assert relays.writes == []
