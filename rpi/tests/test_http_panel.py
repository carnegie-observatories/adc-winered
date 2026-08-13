"""The operator panel served over plain HTTP on the WebSocket port."""

from __future__ import annotations

import asyncio
import urllib.error
import urllib.request
from collections.abc import AsyncIterator

import pytest

from wr_mechanisms.config import Settings
from wr_mechanisms.gpio import SimRelays
from wr_mechanisms.http import PANEL
from wr_mechanisms.mechanisms import Mechanisms
from wr_mechanisms.server import MechanismsServer

SIM = Settings(gpio_mode="sim")


@pytest.fixture
async def server() -> AsyncIterator[MechanismsServer]:
    mechanisms = Mechanisms(SimRelays(SIM), SIM)
    mechanisms.start()
    srv = MechanismsServer(mechanisms, host="127.0.0.1", port=0)
    await srv.start()
    try:
        yield srv
    finally:
        await srv.stop()
        mechanisms.close()


async def _get(server: MechanismsServer, path: str) -> tuple[int, str, bytes]:
    """Fetch over HTTP from the event loop's thread pool (urllib blocks)."""
    url = f"http://127.0.0.1:{server.port}{path}"

    def fetch() -> tuple[int, str, bytes]:
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                return resp.status, resp.headers.get("Content-Type", ""), resp.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.headers.get("Content-Type", ""), exc.read()

    return await asyncio.get_running_loop().run_in_executor(None, fetch)


async def test_root_serves_the_panel(server) -> None:
    status, content_type, body = await _get(server, "/")
    assert status == 200
    assert content_type.startswith("text/html")
    assert b"<title>WINERED ADC" in body
    # The page has to be the real panel, not a placeholder: it must know how to
    # drive the two commands this server implements.
    assert b"set_shutter" in body
    assert b"set_milky_flat" in body


async def test_panel_path_and_query_string(server) -> None:
    status, _, body = await _get(server, "/mechanisms.html?host=wr-pi")
    assert status == 200
    assert b"<title>WINERED ADC" in body


async def test_healthz(server) -> None:
    status, content_type, body = await _get(server, "/healthz")
    assert status == 200
    assert content_type.startswith("text/plain")
    assert body.strip() == b"ok"


async def test_unknown_path_is_404(server) -> None:
    status, _, _ = await _get(server, "/nope")
    assert status == 404


async def test_websocket_still_upgrades_on_the_same_port(server) -> None:
    """Serving HTTP must not shadow the socket the page connects back to."""
    import json

    import websockets

    async with websockets.connect(f"ws://127.0.0.1:{server.port}") as ws:
        msg = json.loads(await ws.recv())
        assert msg["type"] == "hello"
        assert msg["topics"] == ["mechanisms"]


def test_panel_is_the_repo_page_not_a_copy() -> None:
    """The packaged asset is a symlink to `web/mechanisms.html`.

    A forked copy would drift from the page the PLC-backed deployment serves,
    and the drift would only show up on the bench.
    """
    repo_page = PANEL.parents[3] / "web" / "mechanisms.html"
    assert PANEL.is_symlink()
    assert PANEL.resolve() == repo_page.resolve()


def test_panel_defaults_its_host_to_where_it_was_served_from() -> None:
    """Served from the Pi, the page must connect back to the Pi."""
    assert 'location.hostname || "localhost"' in PANEL.read_text()
