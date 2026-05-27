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
