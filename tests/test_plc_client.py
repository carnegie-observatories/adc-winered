"""PlcClient wiring tests.

No PLC and no ADS traffic here — these pin *how* we call pyads, which is where
the real-hardware bugs lived: the target IP was being derived from the AMS Net
ID (wrong whenever they differ, and always wrong through an SSH tunnel), and
the local Net ID setting was fed an IP address.
"""

from __future__ import annotations

import types

import pytest

from adc_winered import plc_client as mod
from adc_winered.plc_client import PlcClient


class _FakeConnection:
    def __init__(self, ams_net_id, ams_net_port, ip_address=None):
        self.ams_net_id = ams_net_id
        self.ams_net_port = ams_net_port
        self.ip_address = ip_address
        self.opened = False

    def open(self):
        self.opened = True

    def close(self):
        self.opened = False


@pytest.fixture
def fake_pyads(monkeypatch):
    calls: dict[str, object] = {"local_address": None, "ports": 0, "conn": None}

    def _connection(ams_net_id, ams_net_port, ip_address=None):
        conn = _FakeConnection(ams_net_id, ams_net_port, ip_address)
        calls["conn"] = conn
        return conn

    def _set_local_address(netid):
        calls["local_address"] = netid

    def _open_port():
        calls["ports"] = int(calls["ports"]) + 1

    fake = types.SimpleNamespace(
        Connection=_connection,
        set_local_address=_set_local_address,
        open_port=_open_port,
        close_port=lambda: None,
        ADSError=Exception,
    )
    monkeypatch.setattr(mod, "pyads", fake)
    return calls


async def test_host_is_passed_through_instead_of_derived_from_netid(fake_pyads) -> None:
    # The WINERED CX answers to 5.171.247.155.1.1 but lives at 10.7.45.150 —
    # pyads would otherwise dial 5.171.247.155.
    client = PlcClient(ams_net_id="5.171.247.155.1.1", host="10.7.45.150")
    await client.connect()

    conn = fake_pyads["conn"]
    assert conn.ams_net_id == "5.171.247.155.1.1"
    assert conn.ip_address == "10.7.45.150"
    assert conn.opened is True


async def test_ssh_tunnel_targets_loopback(fake_pyads) -> None:
    client = PlcClient(
        ams_net_id="5.171.247.155.1.1",
        host="127.0.0.1",
        local_ams_net_id="127.0.0.1.1.1",
    )
    await client.connect()

    conn = fake_pyads["conn"]
    assert conn.ip_address == "127.0.0.1"
    # The PLC accepts the session only if our Net ID matches one of its routes.
    assert fake_pyads["local_address"] == "127.0.0.1.1.1"


async def test_no_host_leaves_pyads_default_derivation(fake_pyads) -> None:
    client = PlcClient(ams_net_id="10.7.45.150.1.1")
    await client.connect()

    conn = fake_pyads["conn"]
    assert conn.ip_address is None          # pyads derives it from the Net ID
    assert fake_pyads["local_address"] is None
