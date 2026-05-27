"""TCS sim + client tests. The client runs against the sim's TCP serve()."""

from __future__ import annotations

import pytest

from adc_winered.tcs import TcsDriver
from adc_winered.tcs_client import TcsClient
from adc_winered.tcs_sim import TcsSim


async def test_tcs_sim_returns_default_state() -> None:
    sim = TcsSim()
    await sim.connect()
    sample = await sim.read()
    assert sample.elevation_deg == pytest.approx(60.0)
    assert sample.rotator_deg == pytest.approx(0.0)


async def test_tcs_sim_set_state_is_observed() -> None:
    sim = TcsSim()
    sim.set_state(elevation_deg=45.0, rotator_deg=-30.0)
    sample = await sim.read()
    assert sample.elevation_deg == pytest.approx(45.0)
    assert sample.rotator_deg == pytest.approx(-30.0)


async def test_tcs_sim_satisfies_driver_protocol() -> None:
    driver: TcsDriver = TcsSim()
    assert driver is not None


async def test_tcs_client_reads_from_sim_over_tcp() -> None:
    sim = TcsSim()
    sim.set_state(elevation_deg=42.0, rotator_deg=12.5)
    server = await sim.serve(host="127.0.0.1", port=0)
    try:
        port = server.sockets[0].getsockname()[1]
        client = TcsClient(host="127.0.0.1", port=port)
        await client.connect()
        sample = await client.read()
        assert sample.elevation_deg == pytest.approx(42.0)
        assert sample.rotator_deg == pytest.approx(12.5)
    finally:
        server.close()
        await server.wait_closed()


async def test_tcs_client_unreachable_when_no_server_listening() -> None:
    from adc_winered.tcs import TcsUnreachable

    # Use port 1 — privileged, definitely refused on localhost.
    client = TcsClient(host="127.0.0.1", port=1, timeout_s=0.5)
    with pytest.raises(TcsUnreachable):
        await client.connect()
