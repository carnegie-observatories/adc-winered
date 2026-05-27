"""`adc-winered serve` entry point.

Wires Settings → drivers (real or sim) → Controller → LogBuffer → WsServer.
Blocks until SIGINT/SIGTERM, then unwinds cleanly.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys

from .config import Settings
from .controller import Controller
from .plc import PlcDriver
from .plc_client import PlcClient
from .plc_sim import PlcSim
from .tcs import TcsDriver
from .tcs_client import TcsClient
from .tcs_sim import TcsSim
from .ws import LogBuffer, WsServer

log = logging.getLogger("adc_winered")


def main() -> int:
    parser = argparse.ArgumentParser(prog="adc-winered")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("serve", help="Run the WebSocket server until interrupted.")
    args = parser.parse_args()

    if args.cmd == "serve":
        return asyncio.run(_serve())
    return 2


async def _serve() -> int:
    settings = Settings()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    log_buffer = LogBuffer()
    logging.getLogger().addHandler(log_buffer)

    plc = _make_plc(settings)
    tcs = _make_tcs(settings)
    ctrl = Controller(
        plc, tcs,
        control_interval_s=settings.control_interval_s,
        deadband_deg=settings.deadband_deg,
    )

    log.info(
        "adc-winered starting: plc=%s tcs=%s ws=%s:%d",
        settings.plc_mode, settings.tcs_mode, settings.ws_host, settings.ws_port,
    )

    try:
        await ctrl.start()
    except Exception:
        log.exception("controller failed to start")
        return 1

    server = WsServer(ctrl, log_buffer, host=settings.ws_host, port=settings.ws_port)
    try:
        await server.start()
    except Exception:
        log.exception("ws server failed to start")
        await ctrl.stop()
        return 1

    stop_event = asyncio.Event()

    def _stop_signal(signum: int) -> None:
        log.info("received signal %d; shutting down", signum)
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _stop_signal, sig)
        except NotImplementedError:
            pass  # Windows fallback; default Ctrl+C still raises KeyboardInterrupt

    try:
        await stop_event.wait()
    except KeyboardInterrupt:
        pass
    finally:
        await server.stop()
        await ctrl.stop()
    return 0


def _make_plc(s: Settings) -> PlcDriver:
    if s.plc_mode == "real":
        if not s.plc_ams_net_id:
            log.error("ADC_PLC_AMS_NET_ID is required when ADC_PLC_MODE=real")
            sys.exit(2)
        return PlcClient(ams_net_id=s.plc_ams_net_id, ams_port=s.plc_ams_port, ip=s.plc_ip or None)
    return PlcSim(rotator_velocity_deg_s=s.rotator_velocity_deg_s, slide_settle_s=s.slide_settle_s)


def _make_tcs(s: Settings) -> TcsDriver:
    if s.tcs_mode == "real":
        return TcsClient(host=s.tcs_host, port=s.tcs_port)
    return TcsSim(drift=s.tcs_sim_drift)
