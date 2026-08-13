"""Topic projections from `ControllerSnapshot` to the wire JSON payload.

Each function takes a controller snapshot and returns the `data` dict that goes
inside a `state` frame. Topics are stateless — same input always produces the
same output — so equality of two outputs is the change-detection signal.
"""

from __future__ import annotations

from typing import Any

from ..controller import ControllerSnapshot, ControlMode, ControllerState
from ..plc import SlideState


def status_topic(snap: ControllerSnapshot) -> dict[str, Any]:
    slide_a = _slide_name(snap.plc.slide_a if snap.plc else None)
    slide_b = _slide_name(snap.plc.slide_b if snap.plc else None)
    return {
        "adc": slide_a,
        "other": slide_b,
        "control": "auto" if snap.mode is ControlMode.AUTO else "off",
        "update": snap.state is ControllerState.TRACKING,
        "running": snap.state not in (ControllerState.STOPPED, ControllerState.ERROR),
    }


def mechanisms_topic(snap: ControllerSnapshot) -> dict[str, Any]:
    """WINERED-only mechanisms: shutter and milky-flat diffuser.

    Deliberately a separate topic rather than extra `status` keys. `status`
    is the surface every ADC server shares (the Cocoa app included); these
    two mechanisms exist only on the WINERED bench. Advertising them as
    their own topic in `hello` is what lets the web client show the WINERED
    panel *only* when it is talking to this server.

    Neither mechanism has a feedback sensor, so both values echo the last
    command. The de-energized hardware state is shutter closed / diffuser in
    beam, which is also what a missing PLC snapshot reports.
    """
    plc = snap.plc
    return {
        "shutter": "closed" if (plc.shutter_closed if plc else True) else "open",
        "milky_flat": "in" if (plc.milky_flat_deployed if plc else True) else "out",
    }


def lens_topic(snap: ControllerSnapshot) -> dict[str, Any]:
    plc = snap.plc
    targets = snap.targets
    return {
        "lens_a": {
            "encoder": plc.axis_a.position_deg if plc else 0.0,
            "target": targets.a if targets else 0.0,
            "moving": plc.axis_a.busy if plc else False,
        },
        "lens_b": {
            "encoder": plc.axis_b.position_deg if plc else 0.0,
            "target": targets.b if targets else 0.0,
            "moving": plc.axis_b.busy if plc else False,
        },
    }


def telescope_topic(snap: ControllerSnapshot) -> dict[str, Any]:
    tcs = snap.tcs
    return {
        "elevation": tcs.elevation_deg if tcs else 0.0,
        "rotator": tcs.rotator_deg if tcs else 0.0,
    }


TOPIC_PROJECTORS = {
    "status": status_topic,
    "lens": lens_topic,
    "telescope": telescope_topic,
    "mechanisms": mechanisms_topic,
    # "logs" is special — built by the log buffer, not from the snapshot.
}


def _slide_name(s: SlideState | None) -> str:
    if s is SlideState.IN:
        return "in"
    if s is SlideState.OUT:
        return "out"
    if s is SlideState.MOVING:
        return "moving"
    return "error"
