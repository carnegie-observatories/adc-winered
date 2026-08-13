"""`wr-mechanisms serve` entry point.

Wires Settings → relays → Mechanisms → MechanismsServer. Blocks until
SIGINT/SIGTERM, then de-energizes the relays and unwinds.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal

from . import __version__
from .config import ConfigError, Settings, load
from .gpio import RelayError, make_relays
from .mechanisms import Mechanisms
from .server import MechanismsServer

log = logging.getLogger("wr_mechanisms")


def main() -> int:
    parser = argparse.ArgumentParser(prog="wr-mechanisms")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("serve", help="Run the WebSocket server until interrupted.")
    args = parser.parse_args()

    # `serve` is the only verb; make it the default so the systemd unit can
    # just exec the console script.
    if args.cmd in (None, "serve"):
        try:
            settings = load()
        except ConfigError as exc:
            logging.basicConfig(level=logging.INFO)
            log.error("bad configuration: %s", exc)
            return 2
        return asyncio.run(_serve(settings))
    return 2


async def _serve(settings: Settings) -> int:
    logging.basicConfig(
        level=getattr(logging, settings.log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    mechanisms = Mechanisms(make_relays(settings), settings)
    try:
        mechanisms.start()
    except RelayError:
        log.exception("could not bring up the relays")
        return 1

    log.info(
        "wr-mechanisms %s starting: gpio=%s ws=%s:%d",
        __version__, settings.gpio_mode, settings.ws_host, settings.ws_port,
    )
    log.info(
        "polarity: shutter energized = %s, milky flat energized = %s",
        settings.shutter_energized_pos, settings.milky_flat_energized_pos,
    )

    server = MechanismsServer(mechanisms, host=settings.ws_host, port=settings.ws_port)
    try:
        await server.start()
    except Exception:
        log.exception("ws server failed to start")
        mechanisms.close()
        return 1

    stop_event = asyncio.Event()

    def _stop_signal(signum: int) -> None:
        log.info("received signal %d; shutting down", signum)
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _stop_signal, sig)

    try:
        await stop_event.wait()
    except KeyboardInterrupt:
        pass
    finally:
        await server.stop()
        mechanisms.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
